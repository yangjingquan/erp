from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.time import local_now
from app.models.workflow import WfActionLog, WfDefinition, WfInstance, WfNode, WfTask
from app.services.auth_service import UserContext


def serialize_definition(definition: WfDefinition) -> dict:
    return {
        "id": definition.id,
        "business_type": definition.business_type,
        "name": definition.name,
        "version": definition.version,
        "status": definition.status,
        "nodes": [
            {
                "key": node.node_key,
                "name": node.node_name,
                "node_type": node.node_type,
                "approver_type": node.approver_type,
                "approver_value": node.approver_value,
                "sort_order": node.sort_order,
            }
            for node in definition.nodes
        ],
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
        db.add(
            WfNode(
                definition_id=definition.id,
                node_key=str(node.get("key") or f"node-{index}"),
                node_name=str(node.get("name") or f"审批节点 {index}"),
                node_type=str(node.get("node_type") or "approval"),
                sort_order=int(node.get("sort_order") or index),
                approver_type=str(node.get("approver_type") or "role"),
                approver_value=node.get("approver_value"),
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
    db.add(WfActionLog(instance_id=instance.id, task_id=task.id, action="reject", user_id=context.id, comment=comment))
    db.flush()
    return instance
