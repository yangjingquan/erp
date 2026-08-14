from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.time import local_now, local_today
from app.models.quality import QaCapaAction, QaDefectCatalog, QaInspection, QaNonconformity, QaPlan
from app.models.system import SysUser
from app.services.audit_service import write_operation_log
from app.services.auth_service import UserContext


def create_quality_plan(db: Session, payload: dict, context: UserContext) -> QaPlan:
    name = str(payload.get("name", "")).strip()
    if not name:
        raise AppError("检验计划名称不能为空", code=422)
    normalized_items: list[dict] = []
    item_names: set[str] = set()
    for item in payload["items"]:
        item_name = str(item.get("item", "")).strip() if isinstance(item, dict) else ""
        if not item_name:
            raise AppError("检验计划项目必须包含 item 字段", code=422)
        if item_name in item_names:
            raise AppError(f"检验计划项目重复：{item_name}", code=422)
        item_names.add(item_name)
        normalized_items.append({**item, "item": item_name, "value": str(item.get("value", "待检")).strip() or "待检", "passed": None})
    duplicate = db.scalar(select(QaPlan).where(
        QaPlan.org_id == context.org_id,
        QaPlan.name == name,
        QaPlan.is_deleted.is_(False),
    ))
    if duplicate is not None:
        raise AppError("检验计划名称已存在", code=409)
    row = QaPlan(org_id=context.org_id, name=name, items_json=normalized_items)
    db.add(row)
    db.flush()
    return row


def list_quality_plans(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(select(QaPlan).where(QaPlan.org_id == context.org_id, QaPlan.is_deleted.is_(False)).order_by(QaPlan.created_at.desc())).all()
    return [{"id": row.id, "name": row.name, "items": row.items_json, "item_count": len(row.items_json or [])} for row in rows]


def list_defects(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(select(QaDefectCatalog).where(QaDefectCatalog.org_id == context.org_id, QaDefectCatalog.is_deleted.is_(False)).order_by(QaDefectCatalog.code)).all()
    return [{"id": row.id, "code": row.code, "name": row.name, "severity": row.severity, "status": row.status} for row in rows]


def create_defect(db: Session, payload: dict, context: UserContext) -> QaDefectCatalog:
    code = str(payload["code"]).strip().upper()
    name = str(payload["name"]).strip()
    if not code or not name:
        raise AppError("缺陷编码和名称不能为空", code=422)
    duplicate = db.scalar(select(QaDefectCatalog).where(QaDefectCatalog.org_id == context.org_id, QaDefectCatalog.code == code, QaDefectCatalog.is_deleted.is_(False)))
    if duplicate is not None:
        raise AppError("缺陷编码已存在", code=409)
    row = QaDefectCatalog(org_id=context.org_id, code=code, name=name, severity=payload["severity"], status=payload["status"])
    db.add(row); db.flush(); return row


def create_inspection(
    db: Session,
    inspection_type: str,
    source_type: str,
    source_id: str,
    context: UserContext,
    *, plan_id: str | None = None,
    sample_size: int | None = None,
) -> QaInspection:
    plan = None
    if plan_id:
        plan = db.scalar(select(QaPlan).where(QaPlan.id == plan_id, QaPlan.org_id == context.org_id, QaPlan.is_deleted.is_(False)))
        if plan is None:
            raise AppError("检验计划不存在", code=404)
    row = QaInspection(
        org_id=context.org_id,
        inspection_type=inspection_type,
        source_type=source_type,
        source_id=source_id,
        plan_id=plan_id,
        sample_size=sample_size,
        results_json=[{"item": item.get("item"), "value": "待检", "passed": None} for item in (plan.items_json if plan else [])],
    )
    db.add(row)
    db.flush()
    return row


def _get_inspection(db: Session, inspection_id: str, context: UserContext) -> QaInspection:
    row = db.scalar(
        select(QaInspection).where(
            QaInspection.id == inspection_id,
            QaInspection.org_id == context.org_id,
            QaInspection.is_deleted.is_(False),
        )
    )
    if row is None:
        raise AppError("检验单不存在", code=404)
    return row


def _normalise_inspection_results(row: QaInspection, results: list[dict]) -> list[dict]:
    if not results:
        raise AppError("检验结果不能为空", code=422)
    expected_names = [str(item.get("item", "")).strip() for item in (row.results_json or []) if isinstance(item, dict)]
    expected_names = [name for name in expected_names if name]
    seen: set[str] = set()
    normalized: list[dict] = []
    pass_values = {"pass", "passed", "ok", "合格", "通过", "是", "true"}
    fail_values = {"fail", "failed", "ng", "不合格", "不通过", "否", "false"}
    for item in results:
        name = str(item.get("item", "")).strip()
        value = str(item.get("value", "")).strip()
        if not name or not value:
            raise AppError("每个检验项目都必须填写项目名称和结果值", code=422)
        if name in seen:
            raise AppError(f"检验项目重复：{name}", code=422)
        seen.add(name)
        passed = item.get("passed")
        if passed is None:
            lowered = value.lower()
            if lowered in pass_values:
                passed = True
            elif lowered in fail_values:
                passed = False
            else:
                raise AppError(f"检验项目“{name}”必须明确是否通过", code=422)
        normalized.append({**item, "item": name, "value": value, "passed": bool(passed)})
    if expected_names:
        missing = [name for name in expected_names if name not in seen]
        unexpected = [name for name in seen if name not in expected_names]
        if missing:
            raise AppError(f"请完成全部检验项目，缺少：{'、'.join(missing)}", code=422)
        if unexpected:
            raise AppError(f"存在不属于检验计划的项目：{'、'.join(unexpected)}", code=422)
    return normalized


def _failed_item_names(results: list[dict]) -> list[str]:
    return [str(item.get("item") or "未命名项目") for item in results if not item.get("passed")]


def submit_inspection(
    db: Session,
    inspection_id: str,
    results: list[dict],
    context: UserContext,
) -> QaInspection:
    row = _get_inspection(db, inspection_id, context)
    if row.status != "draft":
        raise AppError("检验单当前不可提交", code=400)
    normalized_results = _normalise_inspection_results(row, results)
    failed_items = _failed_item_names(normalized_results)
    row.results_json = normalized_results
    row.result = "failed" if failed_items else "passed"
    row.status = "submitted"
    if row.result == "failed":
        nonconformance = db.scalar(
            select(QaNonconformity).where(
                QaNonconformity.org_id == context.org_id,
                QaNonconformity.inspection_id == row.id,
                QaNonconformity.is_deleted.is_(False),
            )
        )
        if nonconformance is None:
            nonconformance = QaNonconformity(
                org_id=context.org_id,
                inspection_id=row.id,
                description=f"检验项目不合格：{'、'.join(failed_items)}",
            )
            db.add(nonconformance)
    db.flush()
    return row


def close_inspection(
    db: Session,
    inspection_id: str,
    disposition: str,
    context: UserContext,
) -> QaInspection:
    row = _get_inspection(db, inspection_id, context)
    valid_dispositions = {"rework", "accept", "scrap", "return_to_supplier"}
    if row.status != "submitted" or disposition not in valid_dispositions:
        raise AppError("关闭检验单必须提交有效处置结论", code=400)
    if row.result == "failed":
        nonconformance = db.scalar(
            select(QaNonconformity).where(
                QaNonconformity.org_id == context.org_id,
                QaNonconformity.inspection_id == row.id,
                QaNonconformity.is_deleted.is_(False),
            )
        )
        if nonconformance is None or nonconformance.status != "closed":
            raise AppError("不合格检验必须先完成 NCR/CAPA 闭环", code=409)
    row.disposition = disposition
    row.status = "closed"
    db.flush()
    return row


def _get_nonconformance(
    db: Session, nonconformance_id: str, context: UserContext
) -> QaNonconformity:
    row = db.scalar(
        select(QaNonconformity).where(
            QaNonconformity.id == nonconformance_id,
            QaNonconformity.org_id == context.org_id,
            QaNonconformity.is_deleted.is_(False),
        )
    )
    if row is None:
        raise AppError("不合格记录不存在", code=404)
    return row


def _require_active_user(
    db: Session, user_id: str, context: UserContext, *, field_name: str = "责任人"
) -> SysUser:
    user = db.scalar(
        select(SysUser).where(
            SysUser.id == user_id,
            SysUser.org_id == context.org_id,
            SysUser.status == "active",
            SysUser.is_deleted.is_(False),
        )
    )
    if user is None:
        raise AppError(f"{field_name}不存在或已停用", code=400)
    return user


def _serialize_action(row: QaCapaAction) -> dict:
    return {
        "id": row.id,
        "action_type": row.action_type,
        "description": row.description,
        "owner_id": row.owner_id,
        "due_date": row.due_date,
        "status": row.status,
        "completion_evidence": row.completion_evidence,
        "completed_at": row.completed_at,
        "completed_by": row.completed_by,
        "overdue": row.status != "completed" and row.due_date < local_today(),
    }


def _serialize_nonconformance(
    row: QaNonconformity,
    inspection: QaInspection | None,
    actions: list[QaCapaAction],
) -> dict:
    return {
        "id": row.id,
        "inspection_id": row.inspection_id,
        "inspection_type": inspection.inspection_type if inspection else None,
        "source_type": inspection.source_type if inspection else None,
        "source_id": inspection.source_id if inspection else None,
        "description": row.description,
        "status": row.status,
        "severity": row.severity,
        "disposition": row.disposition,
        "owner_id": row.owner_id,
        "due_date": row.due_date,
        "root_cause": row.root_cause,
        "closure_evidence": row.closure_evidence,
        "closed_at": row.closed_at,
        "closed_by": row.closed_by,
        "overdue": row.status != "closed" and row.due_date is not None and row.due_date < local_today(),
        "actions": [_serialize_action(action) for action in actions],
    }


def list_nonconformances(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(
        select(QaNonconformity)
        .where(
            QaNonconformity.org_id == context.org_id,
            QaNonconformity.is_deleted.is_(False),
        )
        .order_by(QaNonconformity.created_at.desc())
    ).all()
    if not rows:
        return []

    ids = [row.id for row in rows]
    inspection_ids = [row.inspection_id for row in rows]
    inspections = {
        row.id: row
        for row in db.scalars(
            select(QaInspection).where(
                QaInspection.org_id == context.org_id,
                QaInspection.id.in_(inspection_ids),
            )
        ).all()
    }
    actions_by_nonconformance: dict[str, list[QaCapaAction]] = defaultdict(list)
    for action in db.scalars(
        select(QaCapaAction)
        .where(
            QaCapaAction.org_id == context.org_id,
            QaCapaAction.nonconformance_id.in_(ids),
            QaCapaAction.is_deleted.is_(False),
        )
        .order_by(QaCapaAction.created_at)
    ).all():
        actions_by_nonconformance[action.nonconformance_id].append(action)
    return [
        _serialize_nonconformance(
            row, inspections.get(row.inspection_id), actions_by_nonconformance[row.id]
        )
        for row in rows
    ]


def update_nonconformance_investigation(
    db: Session,
    nonconformance_id: str,
    payload: dict,
    context: UserContext,
) -> QaNonconformity:
    row = _get_nonconformance(db, nonconformance_id, context)
    if row.status == "closed":
        raise AppError("已关闭的不合格记录不可修改", code=409)
    _require_active_user(db, payload["owner_id"], context)
    if payload["due_date"] < local_today():
        raise AppError("整改期限不能早于今天", code=400)
    for field in ("severity", "disposition", "owner_id", "due_date", "root_cause"):
        setattr(row, field, payload[field])
    row.status = "investigating"
    write_operation_log(
        db,
        user=context.user,
        action="investigate",
        resource="qa_nonconformance",
        target_id=row.id,
        detail={"owner_id": row.owner_id, "due_date": str(row.due_date)},
    )
    db.flush()
    return row


def create_capa_action(
    db: Session,
    nonconformance_id: str,
    payload: dict,
    context: UserContext,
) -> QaCapaAction:
    nonconformance = _get_nonconformance(db, nonconformance_id, context)
    if nonconformance.status != "investigating" or not nonconformance.root_cause:
        raise AppError("请先完成不合格调查和根因分析", code=409)
    _require_active_user(db, payload["owner_id"], context, field_name="措施责任人")
    if payload["due_date"] < local_today():
        raise AppError("措施期限不能早于今天", code=400)
    row = QaCapaAction(
        org_id=context.org_id,
        nonconformance_id=nonconformance.id,
        **payload,
    )
    db.add(row)
    db.flush()
    write_operation_log(
        db,
        user=context.user,
        action="create_capa",
        resource="qa_nonconformance",
        target_id=nonconformance.id,
        detail={"action_id": row.id, "action_type": row.action_type},
    )
    return row


def complete_capa_action(
    db: Session,
    action_id: str,
    completion_evidence: str,
    context: UserContext,
) -> QaCapaAction:
    row = db.scalar(
        select(QaCapaAction).where(
            QaCapaAction.id == action_id,
            QaCapaAction.org_id == context.org_id,
            QaCapaAction.is_deleted.is_(False),
        )
    )
    if row is None:
        raise AppError("CAPA 措施不存在", code=404)
    if row.status == "completed":
        raise AppError("CAPA 措施已完成", code=409)
    nonconformance = _get_nonconformance(db, row.nonconformance_id, context)
    if nonconformance.status == "closed":
        raise AppError("不合格记录已关闭", code=409)
    row.complete(evidence=completion_evidence, user_id=context.id)
    write_operation_log(
        db,
        user=context.user,
        action="complete_capa",
        resource="qa_capa_action",
        target_id=row.id,
        detail={"nonconformance_id": nonconformance.id},
    )
    db.flush()
    return row


def close_nonconformance(
    db: Session,
    nonconformance_id: str,
    closure_evidence: str,
    context: UserContext,
) -> QaNonconformity:
    row = _get_nonconformance(db, nonconformance_id, context)
    if row.status == "closed":
        raise AppError("不合格记录已关闭", code=409)
    if not all((row.owner_id, row.due_date, row.root_cause, row.disposition)):
        raise AppError("关闭前必须完成责任人、期限、根因和处置结论", code=409)
    actions = db.scalars(
        select(QaCapaAction).where(
            QaCapaAction.org_id == context.org_id,
            QaCapaAction.nonconformance_id == row.id,
            QaCapaAction.is_deleted.is_(False),
        )
    ).all()
    action_types = {action.action_type for action in actions}
    if not {"corrective", "preventive"}.issubset(action_types):
        raise AppError("关闭前必须同时制定纠正措施和预防措施", code=409)
    if any(action.status != "completed" or not action.completion_evidence for action in actions):
        raise AppError("关闭前必须完成全部 CAPA 措施并提交证据", code=409)

    row.status = "closed"
    row.closure_evidence = closure_evidence
    row.closed_at = local_now()
    row.closed_by = context.id
    inspection = _get_inspection(db, row.inspection_id, context)
    inspection.status = "closed"
    inspection.disposition = row.disposition
    write_operation_log(
        db,
        user=context.user,
        action="close",
        resource="qa_nonconformance",
        target_id=row.id,
        detail={"inspection_id": inspection.id, "disposition": row.disposition},
    )
    db.flush()
    return row
