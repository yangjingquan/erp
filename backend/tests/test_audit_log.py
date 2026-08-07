from app.models.logging import SysOperationLog
from app.services.audit_service import write_operation_log


def test_operation_log_persists_actor_action_and_json_detail(client_and_session):
    _, session = client_and_session
    user = session.query(__import__("app.models.system", fromlist=["SysUser"]).SysUser).one()

    log = write_operation_log(
        session,
        user=user,
        action="create",
        resource="material",
        target_id="material-1",
        detail={"code": "MAT-001"},
        request_id="request-1",
    )

    stored = session.get(SysOperationLog, log.id)
    assert stored is not None
    assert stored.user_id == user.id
    assert stored.detail_json["code"] == "MAT-001"
