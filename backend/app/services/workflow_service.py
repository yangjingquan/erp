import logging
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.time import local_now
from app.models.workflow import WfActionLog, WfDefinition, WfInstance, WfNode, WfTask
from app.services.auth_service import UserContext

LOGGER = logging.getLogger("erp.workflow")

# Human-friendly approver labels used by the settings page, mapped to the
# approver_type/approver_value the engine understands.  Specific users/roles
# are stored in approver_value when the UI provides an id.
APPROVER_LABELS = {
    "department_manager": "部门负责人",
    "finance_role": "财务角色",
    "user": "指定用户",
    "role": "指定角色",
}
_APPROVER_TYPE_BY_LABEL = {label: key for key, label in APPROVER_LABELS.items()}


def _approver_label(node: WfNode) -> str:
    return APPROVER_LABELS.get(node.approver_type, APPROVER_LABELS.get("role"))


def _node_payload(node: WfNode) -> dict:
    return {
        "key": node.node_key,
        "name": node.node_name,
        "node_type": node.node_type,
        "approver": _approver_label(node),
        "approver_type": node.approver_type,
        "approver_value": node.approver_value,
        "sort_order": node.sort_order,
    }


def serialize_definition(definition: WfDefinition) -> dict:
    return {
        "id": definition.id,
        "business_type": definition.business_type,
        "name": definition.name,
        "version": definition.version,
        "status": definition.status,
        "nodes": [_node_payload(node) for node in definition.nodes],
    }


def get_workflow_definition(db: Session, business_type: str, context: UserContext) -> dict:
    definition = db.scalar(
        select(WfDefinition)
        .where(WfDefinition.org_id == context.org_id, WfDefinition.business_type == business_type)
        .order_by(WfDefinition.version.desc())
    )
    if definition is None:
        return {"business_type": business_type, "name": "", "version": 0, "status": "draft", "nodes": []}
    return serialize_definition(definition)


def save_workflow_definition(db: Session, business_type: str, payload: dict, context: UserContext) -> dict:
    definition = db.scalar(
        select(WfDefinition)
        .where(WfDefinition.org_id == context.org_id, WfDefinition.business_type == business_type)
        .order_by(WfDefinition.version.desc())
    )
    if definition is None:
        definition = WfDefinition(
            org_id=context.org_id,
            business_type=business_type,
            name=str(payload.get("name") or business_type),
            version=1,
            status=str(payload.get("status") or "draft"),
            config_json={},
        )
        db.add(definition)
        db.flush()
    else:
        definition.name = str(payload.get("name") or definition.name)
        definition.status = str(payload.get("status") or definition.status)
        definition.nodes.clear()
    for index, node in enumerate(payload.get("nodes") or [], start=1):
        approver_type = str(node.get("approver_type") or "")
        approver_value = node.get("approver_value")
        # Accept the settings page's Chinese label and map it to a type when
        # the caller does not provide an explicit approver_type.
        if not approver_type:
            label = str(node.get("approver") or "")
            approver_type = _APPROVER_TYPE_BY_LABEL.get(label, "role")
        if approver_type not in APPROVER_LABELS:
            approver_type = "role"
        db.add(
            WfNode(
                definition_id=definition.id,
                node_key=str(node.get("key") or f"node-{index}"),
                node_name=str(node.get("name") or f"审批节点 {index}"),
                node_type=str(node.get("node_type") or "approval"),
                sort_order=int(node.get("sort_order") or index),
                approver_type=approver_type,
                approver_value=approver_value,
                condition_json=node.get("condition_json"),
            )
        )
    db.flush()
    return serialize_definition(definition)


def start_workflow(db: Session, business_type: str, business_id: str, context: UserContext) -> WfInstance:
    definition = db.scalar(
        select(WfDefinition)
        .where(
            WfDefinition.org_id == context.org_id,
            WfDefinition.business_type == business_type,
            WfDefinition.status == "active",
        )
        .order_by(WfDefinition.version.desc())
    )
    if definition is None or not definition.nodes:
        raise AppError("未配置有效审批流程", code=400)
    first = definition.nodes[0]
    instance = WfInstance(
        org_id=context.org_id,
        business_type=business_type,
        business_id=business_id,
        definition_id=definition.id,
        current_node_key=first.node_key,
        status="running",
        started_by=context.id,
    )
    db.add(instance)
    db.flush()
    task = _task_for_node(instance, first)
    db.add(task)
    db.flush()
    db.add(WfActionLog(instance_id=instance.id, task_id=task.id, action="start", user_id=context.id))
    db.flush()
    return instance


def has_running_workflow(db: Session, business_type: str, business_id: str, context: UserContext) -> bool:
    row = db.scalar(
        select(WfInstance.id).where(
            WfInstance.org_id == context.org_id,
            WfInstance.business_type == business_type,
            WfInstance.business_id == business_id,
            WfInstance.status == "running",
        )
    )
    return row is not None


def start_workflow_if_active(db: Session, business_type: str, business_id: str, context: UserContext) -> WfInstance | None:
    """Start an approval flow when an active definition exists.

    Returns None when no workflow is configured for the business type so that
    direct document approval keeps working as the fallback path.
    """
    definition = db.scalar(
        select(WfDefinition)
        .where(
            WfDefinition.org_id == context.org_id,
            WfDefinition.business_type == business_type,
            WfDefinition.status == "active",
        )
        .order_by(WfDefinition.version.desc())
    )
    if definition is None or not definition.nodes:
        return None
    if has_running_workflow(db, business_type, business_id, context):
        return None
    return start_workflow(db, business_type, business_id, context)


def _task_for_node(instance: WfInstance, node: WfNode) -> WfTask:
    return WfTask(
        instance_id=instance.id,
        node_key=node.node_key,
        assignee_user_id=node.approver_value if node.approver_type == "user" else None,
        assignee_role_id=node.approver_value if node.approver_type == "role" else None,
        status="pending",
    )


def _get_task(db: Session, task_id: str, context: UserContext) -> tuple[WfTask, WfInstance, WfDefinition]:
    task = db.get(WfTask, task_id)
    if task is None:
        raise AppError("审批任务不存在", code=404)
    instance = db.get(WfInstance, task.instance_id)
    definition = db.get(WfDefinition, instance.definition_id) if instance else None
    if instance is None or definition is None:
        raise AppError("审批实例不完整", code=500)
    if task.status != "pending" or instance.status != "running":
        raise AppError("审批任务当前不可处理", code=400)
    if (
        not context.user.is_superuser
        and task.assignee_user_id
        and task.assignee_user_id != context.id
    ):
        raise AppError("不是当前审批人", code=403)
    return task, instance, definition


def approve_task(db: Session, task_id: str, context: UserContext, comment: str = "") -> WfInstance:
    task, instance, definition = _get_task(db, task_id, context)
    task.status = "approved"
    task.comment = comment
    task.completed_at = local_now()
    nodes = sorted(definition.nodes, key=lambda item: item.sort_order)
    current_index = next(index for index, node in enumerate(nodes) if node.node_key == task.node_key)
    next_node = nodes[current_index + 1] if current_index + 1 < len(nodes) else None
    if next_node is None:
        instance.current_node_key = None
        instance.status = "completed"
        instance.completed_at = local_now()
        _apply_workflow_outcome(db, instance, "approved", context)
    else:
        instance.current_node_key = next_node.node_key
        next_task = _task_for_node(instance, next_node)
        instance.tasks.append(next_task)
    db.add(WfActionLog(instance_id=instance.id, task_id=task.id, action="approve", user_id=context.id, comment=comment))
    db.flush()
    return instance


def reject_task(db: Session, task_id: str, context: UserContext, comment: str = "") -> WfInstance:
    task, instance, _ = _get_task(db, task_id, context)
    task.status = "rejected"
    task.comment = comment
    task.completed_at = local_now()
    instance.status = "rejected"
    instance.current_node_key = None
    _apply_workflow_outcome(db, instance, "rejected", context)
    db.add(WfActionLog(instance_id=instance.id, task_id=task.id, action="reject", user_id=context.id, comment=comment))
    db.flush()
    return instance


def _apply_workflow_outcome(db: Session, instance: WfInstance, outcome: str, context: UserContext) -> None:
    """Mirror a completed/rejected workflow onto the underlying document.

    This is what makes a configured approval flow actually drive the business
    document status instead of existing as an isolated definition.  The
    document transition is best-effort so the workflow engine can also run in
    isolation (e.g. tests) without a real document behind every instance.
    """
    business_type = instance.business_type
    business_id = instance.business_id
    try:
        if business_type == "sales_order":
            from app.services.sales_service import approve_sales_order, reject_sales_order
            if outcome == "approved":
                approve_sales_order(db, business_id, context)
            else:
                reject_sales_order(db, business_id, context)
        elif business_type == "purchase_order":
            from app.services.purchase_service import approve_purchase_order, reject_purchase_order
            if outcome == "approved":
                approve_purchase_order(db, business_id, context)
            else:
                reject_purchase_order(db, business_id, context)
        elif business_type == "purchase_request":
            from app.services.business_extension_service import transition_request
            transition_request(db, business_id, "approved" if outcome == "approved" else "rejected", context)
        elif business_type == "quote":
            from app.services.business_extension_service import transition_quote
            transition_quote(db, business_id, "approved" if outcome == "approved" else "rejected", context)
        elif business_type == "fin_expense":
            from app.services.finance_service import approve_expense
            if outcome == "approved":
                approve_expense(db, business_id, context)
            # Rejected expenses stay in draft for rework.
        # Unknown business types are intentionally left to the direct command path.
    except AppError as exc:
        LOGGER.warning("审批结果未回写单据 business_type=%s business_id=%s: %s", business_type, business_id, exc.msg)


def list_pending_tasks(db: Session, context: UserContext) -> list[dict]:
    """Return approval tasks the current user may act on."""
    task_stmt = (
        select(WfTask, WfInstance, WfDefinition)
        .join(WfInstance, WfInstance.id == WfTask.instance_id)
        .join(WfDefinition, WfDefinition.id == WfInstance.definition_id)
        .where(
            WfInstance.org_id == context.org_id,
            WfInstance.status == "running",
            WfTask.status == "pending",
        )
        .order_by(WfTask.created_at.desc())
    )
    rows = db.execute(task_stmt).all()
    items = []
    for task, instance, definition in rows:
        # Superusers see everything; otherwise only tasks assigned to the user
        # or left unassigned (role-based) are listed.
        if not context.user.is_superuser and task.assignee_user_id and task.assignee_user_id != context.id:
            continue
        node = next((item for item in definition.nodes if item.node_key == task.node_key), None)
        items.append({
            "task_id": task.id,
            "business_type": instance.business_type,
            "business_id": instance.business_id,
            "document_label": _document_label(db, instance.business_type, instance.business_id),
            "node_name": node.node_name if node else task.node_key,
            "status": task.status,
            "created_at": task.created_at.isoformat(timespec="seconds") if task.created_at else None,
        })
    return items


def _document_label(db: Session, business_type: str, business_id: str) -> str:
    from app.services.document_service import TYPE_CONFIG
    config = TYPE_CONFIG.get(business_type)
    if config is None:
        return business_type
    row = db.get(config["model"], business_id)
    doc_field = config.get("doc")
    doc_no = getattr(row, doc_field, None) if (row is not None and doc_field) else None
    label = config.get("label", business_type)
    return f"{label} {doc_no}" if doc_no else f"{label} {business_id[:8]}"
