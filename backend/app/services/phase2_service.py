import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.time import local_now, local_today
from app.models.crm import CrmContact, CrmFollowUp, CrmLead, CrmOpportunity
from app.models.master_data import MdCustomer, MdSupplier
from app.models.system import SysOrg, SysOrgMembership, SysUser
from app.models.phase2_extensions import (
    AiExceptionAlert, EamAsset, EamMaintenancePlan, EamWorkOrder, HrLeaveRequest, LowCodeDefinition, MetricDefinition,
    OrgIntercompanyTransaction, PlmChangeImpact, PlmChangeOrder, PlmChangeRequest,
    PlmProductRevision, Project, ProjectEntry, ProjectMilestone, ProjectWbs, SrmRfq,
    SrmSupplierScore, SvcCase, SvcContract, SvcVisit, TaxCode, TaxInvoice,
)
from app.models.sales import SalesOrder
from app.models.finance import FinReceipt
from app.models.hr import HrAttendance
from app.services.auth_service import UserContext
from app.services.configuration_service import next_doc_no

LOGGER = logging.getLogger("erp.phase2")


def _serialize(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date,)):
        return value.isoformat()
    return value


def _row(row, fields):
    return {field: _serialize(getattr(row, field, None)) for field in fields} | {"id": row.id}


def _doc_no(db: Session, rule_key: str, org_id: str) -> str:
    """Use configured numbering when present and remain usable in a fresh DB."""
    try:
        return next_doc_no(db, rule_key, org_id, local_today())
    except AppError as exc:
        if "编号规则" not in exc.msg:
            raise
        return f"{rule_key.upper().replace('_', '-')}-{local_today().strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"


def _list(db, model, context, *, keyword: str | None = None, status: str | None = None):
    query = select(model).where(model.org_id == context.org_id, model.is_deleted.is_(False))
    if status and hasattr(model, "status"):
        query = query.where(model.status == status)
    if keyword:
        text = f"%{keyword.strip()}%"
        candidates = [getattr(model, field) for field in ("name", "title", "code", "project_code", "asset_code", "case_no", "change_no", "rfq_no") if hasattr(model, field)]
        if candidates:
            from sqlalchemy import or_
            query = query.where(or_(*[field.like(text) for field in candidates]))
    return db.scalars(query.order_by(model.created_at.desc())).all()


def list_revisions(db, context, keyword=None):
    return [_row(row, ["material_id", "revision", "status", "effective_from", "effective_to", "change_summary", "snapshot_json"]) for row in _list(db, PlmProductRevision, context, keyword=keyword)]


def create_revision(db, payload, context):
    if payload.effective_to and payload.effective_from and payload.effective_to < payload.effective_from:
        raise AppError("版本失效日期不能早于生效日期", code=422)
    exists = db.scalar(select(PlmProductRevision).where(PlmProductRevision.org_id == context.org_id, PlmProductRevision.material_id == payload.material_id, PlmProductRevision.revision == payload.revision, PlmProductRevision.is_deleted.is_(False)))
    if exists:
        raise AppError("同一物料版本号已存在", code=409)
    row = PlmProductRevision(org_id=context.org_id, material_id=payload.material_id, revision=payload.revision, effective_from=payload.effective_from, effective_to=payload.effective_to, change_summary=payload.change_summary, snapshot_json=payload.snapshot, status="draft")
    db.add(row); db.flush(); return row


def transition_revision(db, revision_id, status, context):
    row = db.scalar(select(PlmProductRevision).where(PlmProductRevision.id == revision_id, PlmProductRevision.org_id == context.org_id, PlmProductRevision.is_deleted.is_(False)))
    if row is None: raise AppError("产品版本不存在", code=404)
    allowed = {"draft": {"submitted", "obsolete"}, "submitted": {"effective", "obsolete"}, "effective": {"obsolete"}, "obsolete": set()}
    if status not in allowed.get(row.status, set()): raise AppError("产品版本状态流转不合法", code=409)
    row.status = status; db.flush(); return row


def list_change_requests(db, context, status=None):
    rows = _list(db, PlmChangeRequest, context, status=status)
    return [_row(row, ["change_no", "title", "change_type", "description", "status", "owner_id", "due_date", "impact_snapshot"]) for row in rows]


def create_change_request(db, payload, context):
    row = PlmChangeRequest(org_id=context.org_id, change_no=_doc_no(db, "plm_change_request", context.org_id), title=payload.title, change_type=payload.change_type, description=payload.description, status="draft", owner_id=context.id, due_date=payload.due_date, impact_snapshot=payload.impact_snapshot)
    db.add(row); db.flush(); return row


def transition_change_request(db, request_id, status, context):
    row = db.scalar(select(PlmChangeRequest).where(PlmChangeRequest.id == request_id, PlmChangeRequest.org_id == context.org_id, PlmChangeRequest.is_deleted.is_(False)))
    if row is None: raise AppError("工程变更申请不存在", code=404)
    allowed = {"draft": {"submitted", "cancelled"}, "submitted": {"approved", "rejected", "cancelled"}, "approved": {"effective"}, "rejected": set(), "effective": set(), "cancelled": set()}
    if status not in allowed.get(row.status, set()): raise AppError(f"变更申请当前状态不允许流转到 {status}", code=409)
    row.status = status
    if status == "effective":
        ecn = PlmChangeOrder(org_id=context.org_id, ecn_no=_doc_no(db, "plm_change_order", context.org_id), request_id=row.id, status="effective", approved_by=context.id, effective_at=local_now())
        db.add(ecn); db.flush()
        for item in row.impact_snapshot or []:
            if item.get("object_type") and item.get("object_id"):
                db.add(PlmChangeImpact(org_id=context.org_id, change_order_id=ecn.id, object_type=item["object_type"], object_id=item["object_id"], impact=str(item.get("impact", "待评估")), status="pending"))
    db.flush(); return row


def list_change_impacts(db, change_id, context):
    request = db.scalar(select(PlmChangeRequest).where(PlmChangeRequest.id == change_id, PlmChangeRequest.org_id == context.org_id, PlmChangeRequest.is_deleted.is_(False)))
    if request is None: raise AppError("工程变更申请不存在", code=404)
    order = db.scalar(select(PlmChangeOrder).where(PlmChangeOrder.request_id == request.id, PlmChangeOrder.org_id == context.org_id, PlmChangeOrder.is_deleted.is_(False)).order_by(PlmChangeOrder.created_at.desc()))
    if order is None: return []
    rows = db.scalars(select(PlmChangeImpact).where(PlmChangeImpact.change_order_id == order.id, PlmChangeImpact.org_id == context.org_id, PlmChangeImpact.is_deleted.is_(False))).all()
    return [_row(item, ["change_order_id", "object_type", "object_id", "impact", "status"]) for item in rows]


def resolve_change_impact(db, impact_id, status, context):
    row = db.scalar(select(PlmChangeImpact).where(PlmChangeImpact.id == impact_id, PlmChangeImpact.org_id == context.org_id, PlmChangeImpact.is_deleted.is_(False)))
    if row is None: raise AppError("变更影响项不存在", code=404)
    if status not in {"applied", "accepted", "rejected"}: raise AppError("影响项状态不合法", code=422)
    if status == "applied":
        _apply_impact_to_object(db, row, context)
    row.status = status; db.flush(); return row


def _apply_impact_to_object(db, impact: PlmChangeImpact, context) -> None:
    """Write an applied engineering change back onto the affected object.

    Applying a change makes the old revision unusable so the wrong version can
    no longer be produced: BOM/routing are disabled, work orders and purchase
    orders are cancelled.  This is best-effort — a stale object id only logs a
    warning and the impact itself still records as applied.
    """
    from app.models.production import MfgBom, MfgRouting, MfgWorkOrder
    from app.models.purchase import PurchaseOrder

    obj_type = impact.object_type
    obj_id = impact.object_id
    try:
        if obj_type == "bom":
            obj = db.scalar(select(MfgBom).where(MfgBom.id == obj_id, MfgBom.org_id == context.org_id))
            if obj is not None and obj.status != "disabled":
                obj.status = "disabled"; obj.updated_by = context.id
        elif obj_type == "routing":
            obj = db.scalar(select(MfgRouting).where(MfgRouting.id == obj_id, MfgRouting.org_id == context.org_id))
            if obj is not None and obj.status != "disabled":
                obj.status = "disabled"; obj.updated_by = context.id
        elif obj_type == "work_order":
            obj = db.scalar(select(MfgWorkOrder).where(MfgWorkOrder.id == obj_id, MfgWorkOrder.org_id == context.org_id))
            if obj is None:
                obj = db.scalar(select(MfgWorkOrder).where(MfgWorkOrder.doc_no == obj_id, MfgWorkOrder.org_id == context.org_id))
            if obj is not None and obj.status not in {"completed", "cancelled"}:
                obj.status = "cancelled"; obj.updated_by = context.id
        elif obj_type == "purchase":
            obj = db.scalar(select(PurchaseOrder).where(PurchaseOrder.id == obj_id, PurchaseOrder.org_id == context.org_id))
            if obj is None:
                obj = db.scalar(select(PurchaseOrder).where(PurchaseOrder.doc_no == obj_id, PurchaseOrder.org_id == context.org_id))
            if obj is not None and obj.status not in {"completed", "cancelled"}:
                obj.status = "cancelled"
        db.flush()
    except Exception as exc:  # noqa: BLE001 - impact status must still be recorded
        LOGGER.warning("工程变更影响落地失败 object_type=%s object_id=%s: %s", obj_type, obj_id, exc)


def list_rfqs(db, context, status=None):
    return [_row(row, ["rfq_no", "supplier_id", "material_id", "quantity", "due_date", "quote_amount", "promised_date", "status", "supplier_note"]) for row in _list(db, SrmRfq, context, status=status)]


def compare_rfqs(db, context, material_id=None):
    conditions = [SrmRfq.org_id == context.org_id, SrmRfq.is_deleted.is_(False), SrmRfq.status == "quoted"]
    if material_id:
        conditions.append(SrmRfq.material_id == material_id)
    rows = db.scalars(select(SrmRfq).where(*conditions).order_by(SrmRfq.quote_amount.asc(), SrmRfq.promised_date.asc())).all()
    return [_row(row, ["rfq_no", "supplier_id", "material_id", "quantity", "quote_amount", "promised_date", "supplier_note"]) | {"rank": index + 1} for index, row in enumerate(rows)]


def create_rfq(db, payload, context):
    supplier = db.scalar(select(MdSupplier).where(MdSupplier.id == payload.supplier_id, MdSupplier.org_id == context.org_id, MdSupplier.is_deleted.is_(False)))
    if supplier is None: raise AppError("供应商不存在或不属于当前组织", code=400)
    row = SrmRfq(org_id=context.org_id, rfq_no=_doc_no(db, "srm_rfq", context.org_id), supplier_id=payload.supplier_id, material_id=payload.material_id, quantity=payload.quantity, due_date=payload.due_date)
    db.add(row); db.flush(); return row


def update_rfq_quote(db, rfq_id, payload, context):
    row = db.scalar(select(SrmRfq).where(SrmRfq.id == rfq_id, SrmRfq.org_id == context.org_id, SrmRfq.is_deleted.is_(False)))
    if row is None: raise AppError("询价单不存在", code=404)
    if row.status in {"accepted", "cancelled"}: raise AppError("当前询价单不可修改报价", code=409)
    row.quote_amount = payload.quote_amount; row.promised_date = payload.promised_date; row.supplier_note = payload.supplier_note; row.status = "quoted"; db.flush(); return row


def accept_rfq(db, rfq_id, context):
    row = db.scalar(select(SrmRfq).where(SrmRfq.id == rfq_id, SrmRfq.org_id == context.org_id, SrmRfq.is_deleted.is_(False)))
    if row is None: raise AppError("询价单不存在", code=404)
    if row.status != "quoted" or row.quote_amount is None: raise AppError("只有已报价询价单可以接受", code=409)
    row.status = "accepted"; db.flush(); return row


def list_supplier_scores(db, context, supplier_id=None):
    conditions = [SrmSupplierScore.org_id == context.org_id, SrmSupplierScore.is_deleted.is_(False)]
    if supplier_id: conditions.append(SrmSupplierScore.supplier_id == supplier_id)
    rows = db.scalars(select(SrmSupplierScore).where(*conditions).order_by(SrmSupplierScore.period.desc())).all()
    return [_row(item, ["supplier_id", "period", "delivery_score", "quality_score", "service_score", "total_score", "evidence_json"]) for item in rows]


def upsert_supplier_score(db, payload, context):
    if db.scalar(select(MdSupplier.id).where(MdSupplier.id == payload.supplier_id, MdSupplier.org_id == context.org_id, MdSupplier.is_deleted.is_(False))) is None: raise AppError("供应商不存在或不属于当前组织", code=404)
    row = db.scalar(select(SrmSupplierScore).where(SrmSupplierScore.org_id == context.org_id, SrmSupplierScore.supplier_id == payload.supplier_id, SrmSupplierScore.period == payload.period, SrmSupplierScore.is_deleted.is_(False)))
    if row is None: row = SrmSupplierScore(org_id=context.org_id, supplier_id=payload.supplier_id, period=payload.period); db.add(row)
    row.delivery_score = payload.delivery_score; row.quality_score = payload.quality_score; row.service_score = payload.service_score; row.total_score = (payload.delivery_score + payload.quality_score + payload.service_score) / 3; row.evidence_json = payload.evidence
    db.flush(); return row


def list_projects(db, context):
    rows = _list(db, Project, context)
    entries = db.scalars(select(ProjectEntry).where(ProjectEntry.org_id == context.org_id, ProjectEntry.is_deleted.is_(False))).all()
    totals = defaultdict(Decimal)
    for entry in entries: totals[entry.project_id] += entry.amount
    return [_row(row, ["project_code", "name", "customer_id", "manager_id", "status", "budget_amount", "actual_amount", "start_date", "end_date"]) | {"actual_amount": str(totals[row.id]), "variance": str(Decimal(row.budget_amount or 0) - totals[row.id])} for row in rows]


def create_project(db, payload, context):
    if payload.end_date and payload.start_date and payload.end_date < payload.start_date: raise AppError("项目结束日期不能早于开始日期", code=422)
    if db.scalar(select(Project.id).where(Project.org_id == context.org_id, Project.project_code == payload.project_code, Project.is_deleted.is_(False))): raise AppError("项目编码已存在", code=409)
    row = Project(org_id=context.org_id, project_code=payload.project_code, name=payload.name, customer_id=payload.customer_id, manager_id=context.id, budget_amount=payload.budget_amount, start_date=payload.start_date, end_date=payload.end_date)
    db.add(row); db.flush(); return row


def create_wbs(db, payload, context):
    project = db.scalar(select(Project).where(Project.id == payload.project_id, Project.org_id == context.org_id, Project.is_deleted.is_(False)))
    if project is None: raise AppError("项目不存在", code=404)
    row = ProjectWbs(org_id=context.org_id, project_id=payload.project_id, parent_id=payload.parent_id, code=payload.code, name=payload.name, planned_amount=payload.planned_amount)
    db.add(row); db.flush(); return row


def list_project_wbs(db, project_id, context):
    if db.scalar(select(Project.id).where(Project.id == project_id, Project.org_id == context.org_id, Project.is_deleted.is_(False))) is None: raise AppError("项目不存在", code=404)
    rows = db.scalars(select(ProjectWbs).where(ProjectWbs.org_id == context.org_id, ProjectWbs.project_id == project_id, ProjectWbs.is_deleted.is_(False)).order_by(ProjectWbs.code)).all()
    return [_row(item, ["project_id", "parent_id", "code", "name", "status", "planned_amount", "actual_amount"]) for item in rows]


def create_milestone(db, payload, context):
    if db.scalar(select(Project.id).where(Project.id == payload.project_id, Project.org_id == context.org_id, Project.is_deleted.is_(False))) is None: raise AppError("项目不存在", code=404)
    row = ProjectMilestone(org_id=context.org_id, **payload.model_dump()); db.add(row); db.flush(); return row


def list_milestones(db, project_id, context):
    rows = db.scalars(select(ProjectMilestone).where(ProjectMilestone.org_id == context.org_id, ProjectMilestone.project_id == project_id, ProjectMilestone.is_deleted.is_(False)).order_by(ProjectMilestone.due_date)).all()
    return [_row(item, ["project_id", "wbs_id", "name", "due_date", "status"]) for item in rows]


def project_dashboard(db, project_id, context):
    project = db.scalar(select(Project).where(Project.id == project_id, Project.org_id == context.org_id, Project.is_deleted.is_(False)))
    if project is None: raise AppError("项目不存在", code=404)
    entries = db.scalars(select(ProjectEntry).where(ProjectEntry.org_id == context.org_id, ProjectEntry.project_id == project_id, ProjectEntry.is_deleted.is_(False))).all()
    revenue = sum((Decimal(item.amount) for item in entries if item.category == "revenue"), Decimal("0")); cost = sum((Decimal(item.amount) for item in entries if item.category != "revenue"), Decimal("0"))
    return {"project": _row(project, ["project_code", "name", "status", "budget_amount", "start_date", "end_date"]), "revenue": str(revenue), "cost": str(cost), "profit": str(revenue - cost), "margin": str((revenue - cost) / revenue if revenue else Decimal("0")), "wbs": list_project_wbs(db, project_id, context), "milestones": list_milestones(db, project_id, context)}


def create_project_entry(db, payload, context):
    if db.scalar(select(Project.id).where(Project.id == payload.project_id, Project.org_id == context.org_id, Project.is_deleted.is_(False))) is None: raise AppError("项目不存在", code=404)
    row = ProjectEntry(org_id=context.org_id, **payload.model_dump()); db.add(row); db.flush(); return row


def list_project_entries(db, project_id, context):
    if db.scalar(select(Project.id).where(Project.id == project_id, Project.org_id == context.org_id, Project.is_deleted.is_(False))) is None: raise AppError("项目不存在", code=404)
    return [_row(row, ["project_id", "wbs_id", "entry_date", "category", "source_type", "source_id", "amount"]) for row in db.scalars(select(ProjectEntry).where(ProjectEntry.org_id == context.org_id, ProjectEntry.project_id == project_id, ProjectEntry.is_deleted.is_(False)).order_by(ProjectEntry.entry_date.desc())).all()]


def _get_asset(db, asset_id: str, context):
    row = db.scalar(select(EamAsset).where(EamAsset.id == asset_id, EamAsset.org_id == context.org_id, EamAsset.is_deleted.is_(False)))
    if row is None:
        raise AppError("资产不存在", code=404)
    return row


def _get_assignee(db, user_id: str | None, context):
    if not user_id:
        return None
    row = db.scalar(select(SysUser).where(SysUser.id == user_id, SysUser.org_id == context.org_id, SysUser.status == "active", SysUser.is_deleted.is_(False)))
    if row is None:
        raise AppError("责任人不存在或已停用", code=422)
    return row


def list_assignees(db, context):
    rows = db.scalars(select(SysUser).where(SysUser.org_id == context.org_id, SysUser.status == "active", SysUser.is_deleted.is_(False)).order_by(SysUser.display_name, SysUser.username)).all()
    return [{"id": row.id, "display_name": row.display_name or row.username, "username": row.username} for row in rows]


def _refresh_asset_next_maintenance(db, asset: EamAsset, context) -> None:
    plans = db.scalars(select(EamMaintenancePlan).where(EamMaintenancePlan.org_id == context.org_id, EamMaintenancePlan.asset_id == asset.id, EamMaintenancePlan.status == "active", EamMaintenancePlan.is_deleted.is_(False))).all()
    asset.next_maintenance_date = min((plan.next_due for plan in plans), default=None)


def list_assets(db, context, status=None):
    rows = _list(db, EamAsset, context, status=status)
    plans = db.scalars(select(EamMaintenancePlan).where(EamMaintenancePlan.org_id == context.org_id, EamMaintenancePlan.is_deleted.is_(False))).all()
    work_orders = db.scalars(select(EamWorkOrder).where(EamWorkOrder.org_id == context.org_id, EamWorkOrder.is_deleted.is_(False))).all()
    plan_counts = defaultdict(int)
    open_counts = defaultdict(int)
    total_counts = defaultdict(int)
    for plan in plans:
        plan_counts[plan.asset_id] += 1
    for work_order in work_orders:
        total_counts[work_order.asset_id] += 1
        if work_order.status not in {"closed", "cancelled"}:
            open_counts[work_order.asset_id] += 1
    return [_row(row, ["asset_code", "asset_name", "serial_no", "location", "status", "next_maintenance_date", "retired_at", "retirement_reason"]) | {"maintenance_plan_count": plan_counts[row.id], "work_order_count": total_counts[row.id], "open_work_order_count": open_counts[row.id]} for row in rows]


def create_asset(db, payload, context):
    if db.scalar(select(EamAsset.id).where(EamAsset.org_id == context.org_id, EamAsset.asset_code == payload.asset_code, EamAsset.is_deleted.is_(False))):
        raise AppError("资产编码已存在", code=409)
    row = EamAsset(org_id=context.org_id, **payload.model_dump())
    db.add(row); db.flush(); return row


def update_asset(db, asset_id, payload, context):
    row = _get_asset(db, asset_id, context)
    values = payload.model_dump(exclude_unset=True)
    if values.get("status") == "retired":
        active_work_order = db.scalar(select(EamWorkOrder.id).where(EamWorkOrder.asset_id == row.id, EamWorkOrder.org_id == context.org_id, EamWorkOrder.status.not_in({"closed", "cancelled"}), EamWorkOrder.is_deleted.is_(False)))
        if active_work_order:
            raise AppError("存在未关闭的资产工单，不能报废资产", code=409)
        row.retired_at = row.retired_at or local_now()
    elif values.get("status") == "active":
        row.retired_at = None
        row.retirement_reason = None
    for field, value in values.items():
        setattr(row, field, value)
    db.flush(); return row


def create_asset_work_order(db, payload, context):
    asset = _get_asset(db, payload.asset_id, context)
    if asset.status == "retired":
        raise AppError("已报废资产不能新建工单", code=409)
    _get_assignee(db, payload.owner_id, context)
    plan = None
    if payload.maintenance_plan_id:
        plan = db.scalar(select(EamMaintenancePlan).where(EamMaintenancePlan.id == payload.maintenance_plan_id, EamMaintenancePlan.asset_id == asset.id, EamMaintenancePlan.org_id == context.org_id, EamMaintenancePlan.is_deleted.is_(False)))
        if plan is None:
            raise AppError("保养计划不存在或不属于当前资产", code=422)
    values = payload.model_dump()
    row = EamWorkOrder(org_id=context.org_id, work_order_no=_doc_no(db, "eam_work_order", context.org_id), **values)
    db.add(row); db.flush()
    return row


def list_maintenance_plans(db, context, asset_id=None):
    conditions = [EamMaintenancePlan.org_id == context.org_id, EamMaintenancePlan.is_deleted.is_(False)]
    if asset_id: conditions.append(EamMaintenancePlan.asset_id == asset_id)
    rows = db.scalars(select(EamMaintenancePlan).where(*conditions).order_by(EamMaintenancePlan.next_due)).all()
    return [_row(item, ["asset_id", "name", "interval_days", "next_due", "status", "last_work_order_id", "last_completed_at"]) for item in rows]


def create_maintenance_plan(db, payload, context):
    asset = _get_asset(db, payload.asset_id, context)
    if asset.status == "retired":
        raise AppError("已报废资产不能建立保养计划", code=409)
    row = EamMaintenancePlan(org_id=context.org_id, **payload.model_dump())
    db.add(row); db.flush()
    _refresh_asset_next_maintenance(db, asset, context)
    return row


def generate_maintenance_work_order(db, plan_id, context):
    plan = db.scalar(select(EamMaintenancePlan).where(EamMaintenancePlan.id == plan_id, EamMaintenancePlan.org_id == context.org_id, EamMaintenancePlan.is_deleted.is_(False)))
    if plan is None:
        raise AppError("保养计划不存在", code=404)
    if plan.status != "active":
        raise AppError("当前保养计划不可生成工单", code=409)
    existing = db.scalar(select(EamWorkOrder).where(EamWorkOrder.maintenance_plan_id == plan.id, EamWorkOrder.org_id == context.org_id, EamWorkOrder.status.not_in({"closed", "cancelled"}), EamWorkOrder.is_deleted.is_(False)))
    if existing:
        raise AppError("该保养计划已有未关闭工单", code=409)
    asset = _get_asset(db, plan.asset_id, context)
    row = EamWorkOrder(org_id=context.org_id, work_order_no=_doc_no(db, "eam_work_order", context.org_id), asset_id=asset.id, service_type="maintenance", description=f"保养计划：{plan.name}", due_date=plan.next_due, maintenance_plan_id=plan.id, status="open")
    db.add(row); db.flush()
    plan.last_work_order_id = row.id
    return row


def update_asset_work_order(db, work_order_id, payload, context):
    row = db.scalar(select(EamWorkOrder).where(EamWorkOrder.id == work_order_id, EamWorkOrder.org_id == context.org_id, EamWorkOrder.is_deleted.is_(False)))
    if row is None: raise AppError("资产工单不存在", code=404)
    if row.status in {"closed", "cancelled"}: raise AppError("已关闭或已取消的工单不能修改", code=409)
    _get_assignee(db, payload.owner_id, context)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.flush(); return row


def transition_asset_work_order(db, work_order_id, status, context, payload=None):
    row = db.scalar(select(EamWorkOrder).where(EamWorkOrder.id == work_order_id, EamWorkOrder.org_id == context.org_id, EamWorkOrder.is_deleted.is_(False)))
    if row is None: raise AppError("资产工单不存在", code=404)
    allowed = {"open": {"assigned", "cancelled"}, "assigned": {"in_progress", "cancelled"}, "in_progress": {"resolved", "cancelled"}, "resolved": {"closed", "reopened"}, "closed": {"reopened"}, "reopened": {"in_progress", "cancelled"}}
    if status not in allowed.get(row.status, set()): raise AppError("资产工单状态流转不合法", code=409)
    values = payload.model_dump(exclude_unset=True) if payload else {}
    for field, value in values.items():
        setattr(row, field, value)
    now = local_now()
    if status == "assigned":
        if not row.owner_id: raise AppError("派工前必须指定责任人", code=422)
        _get_assignee(db, row.owner_id, context); row.assigned_at = now
    elif status == "in_progress":
        row.started_at = row.started_at or now
        asset = _get_asset(db, row.asset_id, context)
        if asset.status != "retired": asset.status = "maintenance"
    elif status == "resolved":
        if not row.resolution or not row.resolution.strip(): raise AppError("解决工单前必须填写处理结果", code=422)
        row.resolved_at = now
    elif status == "closed":
        if not row.resolution or not row.resolution.strip(): raise AppError("关闭工单前必须填写处理结果", code=422)
        row.closed_at = now; row.closed_by = context.id
        if row.maintenance_plan_id:
            plan = db.scalar(select(EamMaintenancePlan).where(EamMaintenancePlan.id == row.maintenance_plan_id, EamMaintenancePlan.org_id == context.org_id, EamMaintenancePlan.is_deleted.is_(False)))
            if plan:
                plan.last_completed_at = now
                plan.next_due = (now.date() + timedelta(days=plan.interval_days))
        asset = _get_asset(db, row.asset_id, context)
        active = db.scalar(select(EamWorkOrder.id).where(EamWorkOrder.asset_id == asset.id, EamWorkOrder.org_id == context.org_id, EamWorkOrder.id != row.id, EamWorkOrder.status.not_in({"closed", "cancelled"}), EamWorkOrder.is_deleted.is_(False)))
        if asset.status != "retired" and not active: asset.status = "active"
        _refresh_asset_next_maintenance(db, asset, context)
    elif status == "cancelled":
        asset = _get_asset(db, row.asset_id, context)
        active = db.scalar(select(EamWorkOrder.id).where(EamWorkOrder.asset_id == asset.id, EamWorkOrder.id != row.id, EamWorkOrder.status.not_in({"closed", "cancelled"}), EamWorkOrder.is_deleted.is_(False)))
        if asset.status != "retired" and not active: asset.status = "active"
    elif status == "reopened":
        row.resolved_at = None; row.closed_at = None; row.closed_by = None
    row.status = status; db.flush(); return row


def list_asset_work_orders(db, context):
    return [_row(row, ["work_order_no", "asset_id", "service_type", "description", "status", "owner_id", "due_date", "resolution", "maintenance_plan_id", "actual_hours", "parts_cost", "labor_cost", "assigned_at", "started_at", "resolved_at", "closed_at"]) for row in _list(db, EamWorkOrder, context)]


def list_service_cases(db, context, status=None):
    rows = _list(db, SvcCase, context, status=status)
    visit_counts = defaultdict(int)
    for case_id in db.scalars(select(SvcVisit.case_id).where(SvcVisit.org_id == context.org_id, SvcVisit.is_deleted.is_(False))).all():
        visit_counts[case_id] += 1
    today = local_today()
    return [_row(row, ["case_no", "customer_id", "contract_id", "title", "priority", "status", "owner_id", "due_date", "resolution", "sla_hours", "first_response_at", "resolved_at", "closed_at", "customer_feedback", "satisfaction_score"]) | {"sla_status": "overdue" if row.due_date and row.due_date < today and row.status not in {"closed", "cancelled"} else "within_sla", "visit_count": visit_counts[row.id]} for row in rows]


def list_service_contracts(db, context, customer_id=None):
    conditions = [SvcContract.org_id == context.org_id, SvcContract.is_deleted.is_(False)]
    if customer_id: conditions.append(SvcContract.customer_id == customer_id)
    rows = db.scalars(select(SvcContract).where(*conditions).order_by(SvcContract.end_date.desc())).all()
    return [_row(row, ["contract_no", "customer_id", "start_date", "end_date", "value", "status"]) for row in rows]


def create_service_contract(db, payload, context):
    if payload.end_date < payload.start_date: raise AppError("服务合同结束日期不能早于开始日期", code=422)
    if db.scalar(select(MdCustomer.id).where(MdCustomer.id == payload.customer_id, MdCustomer.org_id == context.org_id, MdCustomer.is_deleted.is_(False))) is None: raise AppError("客户不存在", code=404)
    row = SvcContract(org_id=context.org_id, contract_no=_doc_no(db, "svc_contract", context.org_id), **payload.model_dump()); db.add(row); db.flush(); return row


def create_service_case(db, payload, context):
    if db.scalar(select(MdCustomer.id).where(MdCustomer.id == payload.customer_id, MdCustomer.org_id == context.org_id, MdCustomer.is_deleted.is_(False))) is None: raise AppError("客户不存在", code=404)
    if payload.contract_id and db.scalar(select(SvcContract.id).where(SvcContract.id == payload.contract_id, SvcContract.customer_id == payload.customer_id, SvcContract.org_id == context.org_id, SvcContract.is_deleted.is_(False))) is None: raise AppError("服务合同不存在或不属于该客户", code=422)
    _get_assignee(db, payload.owner_id, context)
    row = SvcCase(org_id=context.org_id, case_no=_doc_no(db, "svc_case", context.org_id), **payload.model_dump())
    if row.due_date is None:
        row.due_date = (local_now() + timedelta(hours=row.sla_hours or 48)).date()
    db.add(row); db.flush(); return row


def update_service_case(db, case_id, payload, context):
    row = db.scalar(select(SvcCase).where(SvcCase.id == case_id, SvcCase.org_id == context.org_id, SvcCase.is_deleted.is_(False)))
    if row is None: raise AppError("服务工单不存在", code=404)
    if row.status in {"closed", "cancelled"}: raise AppError("已关闭或已取消的服务工单不能修改", code=409)
    _get_assignee(db, payload.owner_id, context)
    for field, value in payload.model_dump(exclude_unset=True).items(): setattr(row, field, value)
    db.flush(); return row


def transition_service_case(db, case_id, status, context, payload=None):
    row = db.scalar(select(SvcCase).where(SvcCase.id == case_id, SvcCase.org_id == context.org_id, SvcCase.is_deleted.is_(False)))
    if row is None: raise AppError("服务工单不存在", code=404)
    allowed = {"open": {"assigned", "cancelled"}, "assigned": {"in_progress", "cancelled"}, "in_progress": {"resolved", "cancelled"}, "resolved": {"closed", "reopened"}, "closed": {"reopened"}, "reopened": {"in_progress", "cancelled"}, "cancelled": set()}
    if status not in allowed.get(row.status, set()): raise AppError("服务工单状态流转不合法", code=409)
    values = payload.model_dump(exclude_unset=True) if payload else {}
    for field, value in values.items(): setattr(row, field, value)
    now = local_now()
    if status == "assigned":
        if not row.owner_id: raise AppError("派工前必须指定责任人", code=422)
        _get_assignee(db, row.owner_id, context); row.first_response_at = row.first_response_at or now
    elif status == "in_progress":
        row.first_response_at = row.first_response_at or now
    elif status == "resolved":
        if not row.resolution or not row.resolution.strip(): raise AppError("解决服务工单前必须填写解决方案", code=422)
        row.resolved_at = now
    elif status == "closed":
        if not row.resolution or not row.resolution.strip(): raise AppError("关闭服务工单前必须填写解决方案", code=422)
        row.closed_at = now
    elif status == "reopened":
        row.resolved_at = None; row.closed_at = None
    row.status = status; db.flush(); return row


def create_visit(db, payload, context):
    case = db.scalar(select(SvcCase).where(SvcCase.id == payload.case_id, SvcCase.org_id == context.org_id, SvcCase.is_deleted.is_(False)))
    if case is None: raise AppError("服务工单不存在", code=404)
    _get_assignee(db, payload.technician_id, context)
    row = SvcVisit(org_id=context.org_id, **payload.model_dump())
    db.add(row)
    if payload.technician_id:
        case.owner_id = payload.technician_id
        case.first_response_at = case.first_response_at or local_now()
        if case.status == "open": case.status = "assigned"
    db.flush(); return row


def update_visit(db, visit_id, payload, context):
    row = db.scalar(select(SvcVisit).where(SvcVisit.id == visit_id, SvcVisit.org_id == context.org_id, SvcVisit.is_deleted.is_(False)))
    if row is None: raise AppError("服务回访不存在", code=404)
    values = payload.model_dump(exclude_unset=True)
    if values.get("status") == "completed" and not (values.get("outcome") or row.outcome): raise AppError("完成回访前必须填写回访结果", code=422)
    for field, value in values.items(): setattr(row, field, value)
    if row.status == "completed": row.completed_at = row.completed_at or local_now()
    db.flush(); return row


def list_visits(db, context, case_id=None):
    conditions = [SvcVisit.org_id == context.org_id, SvcVisit.is_deleted.is_(False)]
    if case_id: conditions.append(SvcVisit.case_id == case_id)
    rows = db.scalars(select(SvcVisit).where(*conditions).order_by(SvcVisit.scheduled_at)).all()
    return [_row(item, ["case_id", "scheduled_at", "technician_id", "status", "notes", "outcome", "completed_at", "feedback_score"]) for item in rows]


def customer_360(db, customer_id, context):
    customer = db.scalar(select(MdCustomer).where(MdCustomer.id == customer_id, MdCustomer.org_id == context.org_id, MdCustomer.is_deleted.is_(False)))
    if customer is None: raise AppError("客户不存在", code=404)
    contacts = db.scalars(select(CrmContact).where(CrmContact.org_id == context.org_id, CrmContact.customer_id == customer_id, CrmContact.is_deleted.is_(False))).all()
    leads = db.scalars(select(CrmLead).where(CrmLead.org_id == context.org_id, CrmLead.customer_id == customer_id, CrmLead.is_deleted.is_(False))).all()
    opportunities = db.scalars(select(CrmOpportunity).where(CrmOpportunity.org_id == context.org_id, CrmOpportunity.customer_id == customer_id, CrmOpportunity.is_deleted.is_(False))).all()
    orders = db.scalars(select(SalesOrder).where(SalesOrder.org_id == context.org_id, SalesOrder.customer_id == customer_id, SalesOrder.is_deleted.is_(False))).all()
    contracts = db.scalars(select(SvcContract).where(SvcContract.org_id == context.org_id, SvcContract.customer_id == customer_id, SvcContract.is_deleted.is_(False))).all()
    cases = db.scalars(select(SvcCase).where(SvcCase.org_id == context.org_id, SvcCase.customer_id == customer_id, SvcCase.is_deleted.is_(False))).all()
    case_ids = [item.id for item in cases]
    visits = db.scalars(select(SvcVisit).where(SvcVisit.org_id == context.org_id, SvcVisit.case_id.in_(case_ids), SvcVisit.is_deleted.is_(False)).order_by(SvcVisit.scheduled_at.desc())).all() if case_ids else []
    opportunity_ids = [item.id for item in opportunities]
    follow_ups = db.scalars(select(CrmFollowUp).where(CrmFollowUp.org_id == context.org_id, CrmFollowUp.opportunity_id.in_(opportunity_ids), CrmFollowUp.is_deleted.is_(False)).order_by(CrmFollowUp.occurred_at.desc())).all() if opportunity_ids else []
    receipts = db.scalars(select(FinReceipt).where(FinReceipt.org_id == context.org_id, FinReceipt.customer_id == customer_id).order_by(FinReceipt.receipt_date.desc())).all()
    return {
        "customer": _row(customer, ["code", "name", "short_name", "owner_id", "contact_name", "contact_phone", "status"]),
        "contacts": [_row(item, ["name", "phone", "email", "title"]) for item in contacts],
        "leads": [_row(item, ["lead_no", "name", "status", "source"]) for item in leads],
        "opportunities": [_row(item, ["opportunity_no", "name", "stage", "estimated_amount", "expected_close_date"]) for item in opportunities],
        "orders": [_row(item, ["doc_no", "status", "order_date", "expected_date", "total_amount"]) for item in orders],
        "contracts": [_row(item, ["contract_no", "start_date", "end_date", "value", "status"]) for item in contracts],
        "service_cases": [_row(item, ["case_no", "title", "priority", "status", "due_date", "owner_id", "resolution", "customer_feedback", "satisfaction_score"]) for item in cases],
        "service_visits": [_row(item, ["case_id", "scheduled_at", "technician_id", "status", "notes", "outcome", "completed_at", "feedback_score"]) for item in visits],
        "follow_ups": [_row(item, ["opportunity_id", "content", "occurred_at", "due_date", "status"]) for item in follow_ups],
        "receipts": [_row(item, ["doc_no", "amount", "receipt_date", "status"]) for item in receipts],
        "summary": {
            "contact_count": len(contacts),
            "lead_count": len(leads),
            "opportunity_count": len(opportunities),
            "order_count": len(orders),
            "open_case_count": len([item for item in cases if item.status not in {"closed", "cancelled"}]),
            "visit_count": len(visits),
            "receipt_amount": _serialize(sum((item.amount for item in receipts), Decimal("0"))),
        },
    }


def create_tax_code(db, payload, context):
    if db.scalar(select(TaxCode.id).where(TaxCode.org_id == context.org_id, TaxCode.code == payload["code"], TaxCode.is_deleted.is_(False))): raise AppError("税码已存在", code=409)
    row = TaxCode(org_id=context.org_id, **payload); db.add(row); db.flush(); return row


def list_tax_codes(db, context):
    return [_row(row, ["code", "name", "rate", "status"]) for row in _list(db, TaxCode, context)]


def create_invoice(db, payload, context):
    row = TaxInvoice(org_id=context.org_id, invoice_no=_doc_no(db, "tax_invoice", context.org_id), **payload.model_dump()); db.add(row); db.flush(); return row


def transition_invoice(db, invoice_id, status, context):
    row = db.scalar(select(TaxInvoice).where(TaxInvoice.id == invoice_id, TaxInvoice.org_id == context.org_id, TaxInvoice.is_deleted.is_(False)))
    if row is None: raise AppError("发票不存在", code=404)
    allowed = {"draft": {"submitted", "cancelled"}, "submitted": {"issued", "rejected"}, "issued": {"red_issued"}}
    if status not in allowed.get(row.status, set()): raise AppError("发票状态流转不合法", code=409)
    row.status = status; db.flush(); return row


def create_intercompany(db, payload, context):
    if payload.from_org_id == payload.to_org_id: raise AppError("内部交易的转出与转入组织不能相同", code=422)
    row = OrgIntercompanyTransaction(org_id=context.org_id, transaction_no=_doc_no(db, "intercompany", context.org_id), **payload.model_dump()); db.add(row); db.flush(); return row


def list_intercompany(db, context):
    return [_row(row, ["transaction_no", "from_org_id", "to_org_id", "source_type", "source_id", "amount", "currency", "status"]) for row in _list(db, OrgIntercompanyTransaction, context)]


def list_memberships(db, context):
    rows = db.scalars(select(SysOrgMembership).where(SysOrgMembership.org_id == context.org_id, SysOrgMembership.is_deleted.is_(False)).order_by(SysOrgMembership.created_at.desc())).all()
    users = {row.id: row for row in db.scalars(select(SysUser).where(SysUser.id.in_([item.user_id for item in rows]))).all()} if rows else {}
    orgs = {row.id: row for row in db.scalars(select(SysOrg).where(SysOrg.id.in_([item.org_id for item in rows]))).all()} if rows else {}
    return [membership_row(db, row, users=users, orgs=orgs) for row in rows]


def membership_row(db, row, *, users=None, orgs=None):
    users = users or {}
    orgs = orgs or {}
    user = users.get(row.user_id) or db.get(SysUser, row.user_id)
    org = orgs.get(row.org_id) or db.get(SysOrg, row.org_id)
    return {"id": row.id, "user_id": row.user_id, "user_name": user.display_name if user else row.user_id, "org_id": row.org_id, "org_name": org.name if org else row.org_id, "membership_type": row.membership_type, "status": row.status, "is_default": row.is_default}


def create_membership(db, payload, context):
    if db.scalar(select(SysOrg.id).where(SysOrg.id == payload.org_id, SysOrg.status == "active", SysOrg.is_deleted.is_(False))) is None:
        raise AppError("组织不存在或已停用", code=404)
    if db.scalar(select(SysUser.id).where(SysUser.id == payload.user_id, SysUser.is_deleted.is_(False))) is None:
        raise AppError("用户不存在", code=404)
    existing = db.scalar(select(SysOrgMembership).where(SysOrgMembership.user_id == payload.user_id, SysOrgMembership.org_id == payload.org_id))
    if existing:
        if existing.is_deleted:
            existing.is_deleted = False; existing.status = "active"; existing.membership_type = payload.membership_type
        else:
            raise AppError("该用户已加入组织", code=409)
        db.flush(); return existing
    row = SysOrgMembership(user_id=payload.user_id, org_id=payload.org_id, membership_type=payload.membership_type, is_default=False, status="active")
    db.add(row); db.flush(); return row


def update_membership(db, membership_id, payload, context):
    row = db.scalar(select(SysOrgMembership).where(SysOrgMembership.id == membership_id, SysOrgMembership.org_id == context.org_id, SysOrgMembership.is_deleted.is_(False)))
    if row is None:
        raise AppError("组织成员不存在", code=404)
    if db.scalar(select(SysOrg.id).where(SysOrg.id == payload.org_id, SysOrg.status == "active", SysOrg.is_deleted.is_(False))) is None:
        raise AppError("组织不存在或已停用", code=404)
    duplicate = db.scalar(select(SysOrgMembership.id).where(
        SysOrgMembership.user_id == row.user_id,
        SysOrgMembership.org_id == payload.org_id,
        SysOrgMembership.id != membership_id,
        SysOrgMembership.is_deleted.is_(False),
    ))
    if duplicate:
        raise AppError("该用户已加入目标组织", code=409)
    row.org_id = payload.org_id
    row.membership_type = payload.membership_type
    row.status = payload.status
    db.flush()
    return row


def delete_membership(db, membership_id, context):
    row = db.scalar(select(SysOrgMembership).where(SysOrgMembership.id == membership_id, SysOrgMembership.org_id == context.org_id, SysOrgMembership.is_deleted.is_(False)))
    if row is None:
        raise AppError("组织成员不存在", code=404)
    row.is_deleted = True
    row.status = "inactive"
    db.flush()


def list_tax_invoices(db, context):
    return [_row(row, ["invoice_no", "invoice_type", "source_type", "source_id", "party_id", "amount", "tax_amount", "tax_code", "status"]) for row in _list(db, TaxInvoice, context)]


def create_low_code(db, payload, context):
    if db.scalar(select(LowCodeDefinition.id).where(LowCodeDefinition.org_id == context.org_id, LowCodeDefinition.object_key == payload.object_key, LowCodeDefinition.is_deleted.is_(False))): raise AppError("低代码对象编码已存在", code=409)
    row = LowCodeDefinition(org_id=context.org_id, object_key=payload.object_key, name=payload.name, schema_json=payload.definition_schema, workflow_json=payload.workflow); db.add(row); db.flush(); return row


def list_low_code(db, context):
    return [_row(row, ["object_key", "name", "schema_json", "workflow_json", "status", "version"]) for row in _list(db, LowCodeDefinition, context)]


def publish_low_code(db, object_id, context):
    row = db.scalar(select(LowCodeDefinition).where(LowCodeDefinition.id == object_id, LowCodeDefinition.org_id == context.org_id, LowCodeDefinition.is_deleted.is_(False)))
    if row is None: raise AppError("低代码对象不存在", code=404)
    if not row.schema_json: raise AppError("发布前至少配置一个字段", code=422)
    row.status = "published"; row.version += 1; db.flush(); return row


def create_metric(db, payload, context):
    if db.scalar(select(MetricDefinition.id).where(MetricDefinition.org_id == context.org_id, MetricDefinition.metric_key == payload.metric_key, MetricDefinition.is_deleted.is_(False))): raise AppError("指标编码已存在", code=409)
    row = MetricDefinition(org_id=context.org_id, owner_id=context.id, **payload.model_dump()); db.add(row); db.flush(); return row


def list_metrics(db, context):
    return [_row(row, ["metric_key", "name", "formula", "target", "owner_id", "status"]) for row in _list(db, MetricDefinition, context)]


def explain_metric(db, metric_key, context):
    row = db.scalar(select(MetricDefinition).where(MetricDefinition.org_id == context.org_id, MetricDefinition.metric_key == metric_key, MetricDefinition.is_deleted.is_(False)))
    if row is None: raise AppError("指标不存在", code=404)
    facts = {
        "open_service_cases": db.scalar(select(func.count(SvcCase.id)).where(SvcCase.org_id == context.org_id, SvcCase.status.not_in(["closed", "cancelled"]), SvcCase.is_deleted.is_(False))) or 0,
        "overdue_service_cases": db.scalar(select(func.count(SvcCase.id)).where(SvcCase.org_id == context.org_id, SvcCase.status.not_in(["closed", "cancelled"]), SvcCase.due_date < local_today(), SvcCase.is_deleted.is_(False))) or 0,
        "sales_order_amount": db.scalar(select(func.coalesce(func.sum(SalesOrder.total_amount), 0)).where(SalesOrder.org_id == context.org_id, SalesOrder.status.not_in(["cancelled"]), SalesOrder.is_deleted.is_(False))) or 0,
    }
    value = facts.get(metric_key)
    quality = "verified" if value is not None else "formula_not_mapped"
    message = f"事实表：{metric_key}；当前值 {value}" if value is not None else "公式未映射到标准事实表，请补充指标执行器配置"
    return {"metric": _row(row, ["metric_key", "name", "formula", "target", "owner_id"]), "value": _serialize(value) if value is not None else None, "baseline": None, "quality": quality, "evidence": [{"source": "erp_fact_table", "id": metric_key, "message": message, "facts": facts}]}


def scan_ai_alerts(db, context):
    open_cases = db.scalar(select(func.count(SvcCase.id)).where(SvcCase.org_id == context.org_id, SvcCase.status.not_in(["closed", "cancelled"]), SvcCase.due_date < local_today(), SvcCase.is_deleted.is_(False))) or 0
    if open_cases:
        key = f"service-overdue-{local_today().isoformat()}"
        existing = db.scalar(select(AiExceptionAlert).where(AiExceptionAlert.org_id == context.org_id, AiExceptionAlert.alert_key == key, AiExceptionAlert.is_deleted.is_(False)))
        if existing is None:
            db.add(AiExceptionAlert(org_id=context.org_id, alert_key=key, title=f"有 {open_cases} 个服务工单已逾期", severity="high", source_type="svc_case", evidence_json={"overdue_count": open_cases}, recommended_action="打开服务工单工作台并分派责任人", status="open"))
            db.flush()
    return list_ai_alerts(db, context)


def list_ai_alerts(db, context):
    return [_row(row, ["alert_key", "title", "severity", "source_type", "source_id", "evidence_json", "recommended_action", "status"]) for row in _list(db, AiExceptionAlert, context)]


def list_leave_requests(db, context):
    return [_row(row, ["employee_id", "leave_type", "start_date", "end_date", "reason", "status", "approved_by"]) for row in _list(db, HrLeaveRequest, context)]


def list_attendance(db, context, attendance_date=None):
    conditions = [HrAttendance.org_id == context.org_id, HrAttendance.is_deleted.is_(False)]
    if attendance_date:
        conditions.append(HrAttendance.attendance_date == attendance_date)
    rows = db.scalars(select(HrAttendance).where(*conditions).order_by(HrAttendance.attendance_date.desc())).all()
    return [_row(row, ["employee_id", "attendance_date", "status"]) for row in rows]


def create_leave_request(db, payload, context):
    if payload.end_date < payload.start_date:
        raise AppError("请假结束日期不能早于开始日期", code=422)
    row = HrLeaveRequest(org_id=context.org_id, **payload.model_dump(), status="draft")
    db.add(row); db.flush(); return row


def transition_leave_request(db, leave_id, status, context):
    row = db.scalar(select(HrLeaveRequest).where(HrLeaveRequest.id == leave_id, HrLeaveRequest.org_id == context.org_id, HrLeaveRequest.is_deleted.is_(False)))
    if row is None: raise AppError("请假申请不存在", code=404)
    allowed = {"draft": {"submitted", "cancelled"}, "submitted": {"approved", "rejected"}}
    if status not in allowed.get(row.status, set()): raise AppError("请假申请状态流转不合法", code=409)
    row.status = status; row.approved_by = context.id if status in {"approved", "rejected"} else None; db.flush(); return row


def resolve_ai_alert(db, alert_id, resolution, context):
    row = db.scalar(select(AiExceptionAlert).where(AiExceptionAlert.id == alert_id, AiExceptionAlert.org_id == context.org_id, AiExceptionAlert.is_deleted.is_(False)))
    if row is None: raise AppError("异常提醒不存在", code=404)
    if row.status == "resolved": return row
    row.status = "resolved"; row.recommended_action = f"已处理：{resolution}"; db.flush(); return row
