from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.models.configuration import CfgGlobalParameter
from app.models.platform import ExtEventOutbox
from app.services.event_service import claim_pending_events, emit_event
from app.services.phase2_parameter_service import get_phase2_parameter
from app.services.startup_check import schema_status_from_tables


PHASE2_MUTABLE_TABLES = (
    "ext_event_outbox",
    "mfg_bom",
    "mfg_bom_item",
    "mfg_routing",
    "mfg_routing_operation",
    "mfg_work_order",
    "mfg_work_order_material",
    "mfg_work_report",
    "inv_zone",
    "inv_location",
    "inv_batch",
    "inv_cost_layer",
    "cost_period_close",
    "cost_allocation_rule",
    "crm_lead",
    "crm_opportunity",
    "crm_contact",
    "crm_activity",
    "qa_inspection",
    "qa_inspection_item",
    "qa_nonconformance",
    "hr_employee",
    "hr_attendance",
    "hr_leave_request",
    "hr_payroll_run",
)


def test_phase2_tables_are_required_by_schema_contract():
    status = schema_status_from_tables({"sys_user", "sales_order"})

    assert "mfg_bom" in status.missing_tables
    assert "crm_lead" in status.missing_tables


def test_emit_event_is_idempotent_for_same_aggregate_and_type(client_and_session):
    _, session = client_and_session

    first = emit_event(
        session,
        "work_order.completed",
        "mfg_work_order",
        "wo-1",
        {"quantity": "2"},
    )
    second = emit_event(
        session,
        "work_order.completed",
        "mfg_work_order",
        "wo-1",
        {"quantity": "2"},
    )

    assert first.id == second.id
    assert session.query(ExtEventOutbox).count() == 1


def test_emit_event_recovers_from_a_stale_lookup_duplicate(client_and_session, monkeypatch):
    _, session = client_and_session
    existing = ExtEventOutbox(
        event_type="work_order.completed",
        aggregate_type="mfg_work_order",
        aggregate_id="wo-race",
        payload_json={"quantity": "2"},
    )
    session.add(existing)
    session.commit()

    real_scalar = session.scalar
    lookup_count = 0

    def stale_first_lookup(*args, **kwargs):
        nonlocal lookup_count
        lookup_count += 1
        if lookup_count == 1:
            return None
        assert args[0]._for_update_arg is not None
        return real_scalar(*args, **kwargs)

    monkeypatch.setattr(session, "scalar", stale_first_lookup)

    recovered = emit_event(
        session,
        "work_order.completed",
        "mfg_work_order",
        "wo-race",
        {"quantity": "2"},
    )

    assert recovered.id == existing.id
    assert session.query(ExtEventOutbox).count() == 1


def test_claim_pending_events_returns_only_due_pending_events(client_and_session):
    _, session = client_and_session
    due = emit_event(session, "work_order.released", "mfg_work_order", "wo-2", {})
    overdue = emit_event(session, "work_order.started", "mfg_work_order", "wo-3", {})
    deferred = emit_event(session, "work_order.paused", "mfg_work_order", "wo-4", {})
    overdue.next_retry_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    deferred.next_retry_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=1)
    session.flush()

    claimed = claim_pending_events(session, limit=10)

    assert {event.id for event in claimed} == {due.id, overdue.id}
    assert {event.status for event in claimed} == {"processing"}
    assert {event.claim_token for event in claimed} == {claimed[0].claim_token}
    assert claim_pending_events(session, limit=10) == []


def test_outbox_uses_the_established_audit_and_soft_delete_fields(client_and_session):
    _, session = client_and_session

    event = emit_event(session, "work_order.cancelled", "mfg_work_order", "wo-5", {})

    assert event.is_deleted is False
    assert event.created_at is not None
    assert event.updated_at is not None
    assert event.version == 1


def test_phase2_sql_tables_include_audit_and_soft_delete_columns():
    sql = (Path(__file__).parents[2] / "database" / "init.sql").read_text(encoding="utf-8").lower()

    for table in PHASE2_MUTABLE_TABLES:
        table_sql = sql.split(f"create table if not exists {table}", 1)[1].split("engine=", 1)[0]
        assert "is_deleted tinyint(1) not null default 0" in table_sql, table
        assert "created_at datetime(6) not null default current_timestamp(6)" in table_sql, table
        assert "updated_at datetime(6) not null default current_timestamp(6) on update current_timestamp(6)" in table_sql, table
        assert "version int not null default 1" in table_sql, table


def test_get_phase2_parameter_returns_configured_value_or_default(client_and_session):
    _, session = client_and_session
    session.add(
        CfgGlobalParameter(
            org_id="org-1",
            parameter_key="inventory.costing_method",
            parameter_value="fifo",
        )
    )
    session.flush()

    assert get_phase2_parameter(
        session, "org-1", "inventory.costing_method", "weighted_average"
    ) == "fifo"
    assert get_phase2_parameter(
        session, "org-1", "missing.parameter", "weighted_average"
    ) == "weighted_average"
