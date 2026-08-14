from collections import defaultdict
from datetime import date
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
    AiExceptionAlert, EamAsset, EamWorkOrder, HrLeaveRequest, LowCodeDefinition, MetricDefinition,
    OrgIntercompanyTransaction, PlmChangeImpact, PlmChangeOrder, PlmChangeRequest,
    PlmProductRevision, Project, ProjectEntry, ProjectMilestone, ProjectWbs, SrmRfq,
    SrmSupplierScore, SvcCase, SvcContract, SvcVisit, TaxCode, TaxInvoice,
)
from app.models.sales import SalesOrder
from app.services.auth_service import UserContext
from app.services.configuration_service import next_doc_no


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


def list_rfqs(db, context, status=None):
    return [_row(row, ["rfq_no", "supplier_id", "material_id", "quantity", "due_date", "quote_amount", "promised_date", "status", "supplier_note"]) for row in _list(db, SrmRfq, context, status=status)]


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


def create_project_entry(db, payload, context):
    if db.scalar(select(Project.id).where(Project.id == payload.project_id, Project.org_id == context.org_id, Project.is_deleted.is_(False))) is None: raise AppError("项目不存在", code=404)
    row = ProjectEntry(org_id=context.org_id, **payload.model_dump()); db.add(row); db.flush(); return row


def list_project_entries(db, project_id, context):
    if db.scalar(select(Project.id).where(Project.id == project_id, Project.org_id == context.org_id, Project.is_deleted.is_(False))) is None: raise AppError("项目不存在", code=404)
    return [_row(row, ["project_id", "wbs_id", "entry_date", "category", "source_type", "source_id", "amount"]) for row in db.scalars(select(ProjectEntry).where(ProjectEntry.org_id == context.org_id, ProjectEntry.project_id == project_id, ProjectEntry.is_deleted.is_(False)).order_by(ProjectEntry.entry_date.desc())).all()]


def list_assets(db, context, status=None):
    return [_row(row, ["asset_code", "asset_name", "serial_no", "location", "status", "next_maintenance_date"]) for row in _list(db, EamAsset, context, status=status)]


def create_asset(db, payload, context):
    if db.scalar(select(EamAsset.id).where(EamAsset.org_id == context.org_id, EamAsset.asset_code == payload.asset_code, EamAsset.is_deleted.is_(False))): raise AppError("资产编码已存在", code=409)
    row = EamAsset(org_id=context.org_id, **payload.model_dump()); db.add(row); db.flush(); return row


def create_asset_work_order(db, payload, context):
    if db.scalar(select(EamAsset.id).where(EamAsset.id == payload.asset_id, EamAsset.org_id == context.org_id, EamAsset.is_deleted.is_(False))) is None: raise AppError("资产不存在", code=404)
    row = EamWorkOrder(org_id=context.org_id, work_order_no=_doc_no(db, "eam_work_order", context.org_id), owner_id=context.id, **payload.model_dump()); db.add(row); db.flush(); return row


def list_asset_work_orders(db, context):
    return [_row(row, ["work_order_no", "asset_id", "service_type", "description", "status", "owner_id", "due_date", "resolution"]) for row in _list(db, EamWorkOrder, context)]


def list_service_cases(db, context, status=None):
    return [_row(row, ["case_no", "customer_id", "contract_id", "title", "priority", "status", "owner_id", "due_date", "resolution"]) for row in _list(db, SvcCase, context, status=status)]


def create_service_contract(db, payload, context):
    if payload.end_date < payload.start_date: raise AppError("服务合同结束日期不能早于开始日期", code=422)
    row = SvcContract(org_id=context.org_id, contract_no=_doc_no(db, "svc_contract", context.org_id), **payload.model_dump()); db.add(row); db.flush(); return row


def create_service_case(db, payload, context):
    row = SvcCase(org_id=context.org_id, case_no=_doc_no(db, "svc_case", context.org_id), owner_id=context.id, **payload.model_dump()); db.add(row); db.flush(); return row


def transition_service_case(db, case_id, status, context):
    row = db.scalar(select(SvcCase).where(SvcCase.id == case_id, SvcCase.org_id == context.org_id, SvcCase.is_deleted.is_(False)))
    if row is None: raise AppError("服务工单不存在", code=404)
    allowed = {"open": {"assigned", "cancelled"}, "assigned": {"in_progress", "cancelled"}, "in_progress": {"resolved", "cancelled"}, "resolved": {"closed"}, "closed": set(), "cancelled": set()}
    if status not in allowed.get(row.status, set()): raise AppError("服务工单状态流转不合法", code=409)
    row.status = status; db.flush(); return row


def create_visit(db, payload, context):
    if db.scalar(select(SvcCase.id).where(SvcCase.id == payload.case_id, SvcCase.org_id == context.org_id, SvcCase.is_deleted.is_(False))) is None: raise AppError("服务工单不存在", code=404)
    row = SvcVisit(org_id=context.org_id, **payload.model_dump()); db.add(row); db.flush(); return row


def customer_360(db, customer_id, context):
    customer = db.scalar(select(MdCustomer).where(MdCustomer.id == customer_id, MdCustomer.org_id == context.org_id, MdCustomer.is_deleted.is_(False)))
    if customer is None: raise AppError("客户不存在", code=404)
    contacts = db.scalars(select(CrmContact).where(CrmContact.org_id == context.org_id, CrmContact.customer_id == customer_id, CrmContact.is_deleted.is_(False))).all()
    leads = db.scalars(select(CrmLead).where(CrmLead.org_id == context.org_id, CrmLead.customer_id == customer_id, CrmLead.is_deleted.is_(False))).all()
    opportunities = db.scalars(select(CrmOpportunity).where(CrmOpportunity.org_id == context.org_id, CrmOpportunity.customer_id == customer_id, CrmOpportunity.is_deleted.is_(False))).all()
    orders = db.scalars(select(SalesOrder).where(SalesOrder.org_id == context.org_id, SalesOrder.customer_id == customer_id, SalesOrder.is_deleted.is_(False))).all()
    contracts = db.scalars(select(SvcContract).where(SvcContract.org_id == context.org_id, SvcContract.customer_id == customer_id, SvcContract.is_deleted.is_(False))).all()
    cases = db.scalars(select(SvcCase).where(SvcCase.org_id == context.org_id, SvcCase.customer_id == customer_id, SvcCase.is_deleted.is_(False))).all()
    return {
        "customer": _row(customer, ["code", "name", "short_name", "owner_id", "contact_name", "contact_phone", "status"]),
        "contacts": [_row(item, ["name", "phone", "email", "title"]) for item in contacts],
        "leads": [_row(item, ["lead_no", "name", "status", "source"]) for item in leads],
        "opportunities": [_row(item, ["opportunity_no", "name", "stage", "estimated_amount", "expected_close_date"]) for item in opportunities],
        "orders": [_row(item, ["doc_no", "status", "order_date", "expected_date", "total_amount"]) for item in orders],
        "contracts": [_row(item, ["contract_no", "start_date", "end_date", "value", "status"]) for item in contracts],
        "service_cases": [_row(item, ["case_no", "title", "priority", "status", "due_date"]) for item in cases],
        "summary": {
            "contact_count": len(contacts),
            "lead_count": len(leads),
            "opportunity_count": len(opportunities),
            "order_count": len(orders),
            "open_case_count": len([item for item in cases if item.status not in {"closed", "cancelled"}]),
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
    return [{"id": row.id, "user_id": row.user_id, "user_name": users.get(row.user_id).display_name if users.get(row.user_id) else row.user_id, "org_id": row.org_id, "membership_type": row.membership_type, "status": row.status, "is_default": row.is_default} for row in rows]


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
    return {"metric": _row(row, ["metric_key", "name", "formula", "target", "owner_id"]), "value": None, "baseline": None, "quality": "待接入事实表", "evidence": [{"source": "metric_definition", "id": row.id, "message": "当前版本先保存口径和证据链入口，运行值由事实表任务填充"}]}


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
