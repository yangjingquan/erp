from app.models.system import SysUser
from app.models.workflow import WfDefinition, WfNode
from app.services.auth_service import UserContext
from app.services.workflow_service import approve_task, reject_task, start_workflow


def add_definition(session, user):
    definition = WfDefinition(
        id="definition-1",
        org_id=user.org_id,
        business_type="sales_order",
        name="销售审批",
        version=1,
        status="active",
        config_json={},
    )
    session.add_all(
        [
            definition,
            WfNode(
                id="node-1",
                definition_id=definition.id,
                node_key="manager",
                node_name="经理审批",
                sort_order=1,
                approver_type="user",
                approver_value=user.id,
            ),
            WfNode(
                id="node-2",
                definition_id=definition.id,
                node_key="finance",
                node_name="财务审批",
                sort_order=2,
                approver_type="user",
                approver_value=user.id,
            ),
        ]
    )
    session.commit()


def test_workflow_approval_transitions_and_completes(client_and_session):
    _, session = client_and_session
    user = session.query(SysUser).one()
    add_definition(session, user)
    context = UserContext(user=user, permissions={"*"})

    instance = start_workflow(session, "sales_order", "order-1", context)
    first_task = instance.tasks[0]
    approve_task(session, first_task.id, context, "通过")
    second_task = next(task for task in instance.tasks if task.node_key == "finance")
    approve_task(session, second_task.id, context, "通过")

    assert instance.status == "completed"


def test_workflow_rejection_marks_instance_rejected(client_and_session):
    _, session = client_and_session
    user = session.query(SysUser).one()
    add_definition(session, user)
    context = UserContext(user=user, permissions={"*"})

    instance = start_workflow(session, "sales_order", "order-2", context)
    reject_task(session, instance.tasks[0].id, context, "金额不符")

    assert instance.status == "rejected"


def test_workflow_definition_can_be_saved_and_loaded_from_api(client_and_session):
    client, _ = client_and_session
    from app.core.security import create_access_token

    headers = {"Authorization": f"Bearer {create_access_token('user-1', ['workflow:manage'])}"}
    payload = {
        "name": "销售订单审批",
        "status": "active",
        "nodes": [
            {"key": "manager", "name": "经理审批", "approver_type": "user", "approver_value": "user-1"},
            {"key": "finance", "name": "财务审批", "approver_type": "role", "approver_value": "finance"},
        ],
    }

    saved = client.put("/api/workflow/definitions/sales_order", json=payload, headers=headers)
    loaded = client.get("/api/workflow/definitions/sales_order", headers=headers)

    assert saved.json()["code"] == 0
    assert loaded.json()["data"]["name"] == "销售订单审批"
    assert [node["key"] for node in loaded.json()["data"]["nodes"]] == ["manager", "finance"]
