from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.exceptions import AppError
from app.models.cost import CostAllocation, CostProjectEntry, CostPeriodClose
from app.models.inventory import InvStock
from app.models.logging import SysOperationLog
from app.models.system import SysUser
from app.services.auth_service import UserContext
from app.services.cost_service import (
    assert_period_open,
    calculate_project_cost,
    close_period,
    create_allocation,
    post_allocation,
    reopen_period,
)


def _context(session, permissions=None):
    return UserContext(
        user=session.get(SysUser, "user-1"),
        permissions=set(permissions or {"*"}),
    )


def test_allocation_by_quantity_preserves_total_and_project_cost(client_and_session):
    _, session = client_and_session
    context = _context(session)

    allocation = create_allocation(
        session,
        {
            "allocation_date": date(2026, 8, 2),
            "amount": "100",
            "basis": "quantity",
            "source_type": "expense",
            "source_id": "expense-1",
            "items": [
                {"project_id": "p1", "quantity": "1"},
                {"project_id": "p2", "quantity": "3"},
            ],
        },
        context,
    )
    posted = post_allocation(session, allocation.id, context)

    assert posted.status == "posted"
    entries = session.scalars(
        select(CostProjectEntry).where(CostProjectEntry.allocation_id == allocation.id)
    ).all()
    assert {entry.project_id: entry.amount for entry in entries} == {
        "p1": Decimal("25.00"),
        "p2": Decimal("75.00"),
    }
    assert sum((entry.amount for entry in entries), Decimal("0")) == Decimal("100.00")
    assert calculate_project_cost(session, "p1", "2026-08", context)["total_amount"] == Decimal("25.00")


def test_allocation_supports_hours_and_assigns_cent_remainder_to_final_item(client_and_session):
    _, session = client_and_session
    context = _context(session)

    allocation = create_allocation(
        session,
        {
            "allocation_date": date(2026, 8, 2),
            "amount": "10",
            "basis": "hours",
            "items": [
                {"project_id": "p1", "hours": "1"},
                {"project_id": "p2", "hours": "1"},
                {"project_id": "p3", "hours": "1"},
            ],
        },
        context,
    )
    post_allocation(session, allocation.id, context)

    amounts = session.scalars(
        select(CostProjectEntry.amount)
        .where(CostProjectEntry.allocation_id == allocation.id)
        .order_by(CostProjectEntry.line_no)
    ).all()
    assert amounts == [Decimal("3.33"), Decimal("3.33"), Decimal("3.34")]


def test_allocation_rejects_zero_basis_and_duplicate_idempotency_key(client_and_session):
    _, session = client_and_session
    context = _context(session)
    with pytest.raises(AppError) as error:
        create_allocation(
            session,
            {"amount": "10", "basis": "amount", "items": [{"project_id": "p1", "amount": "0"}]},
            context,
        )
    assert error.value.code == 400

    payload = {
        "allocation_date": date(2026, 8, 2),
        "amount": "10",
        "basis": "quantity",
        "idempotency_key": "idem-1",
        "items": [{"project_id": "p1", "quantity": "1"}],
    }
    first = create_allocation(session, payload, context)
    second = create_allocation(session, payload, context)
    assert second.id == first.id
    assert session.query(CostAllocation).count() == 1


def test_project_cost_aggregates_material_subcontract_labor_and_expense_sources(client_and_session):
    _, session = client_and_session
    context = _context(session)
    session.add_all(
        [
            CostProjectEntry(
                org_id="org-1", project_id="p1", period="2026-08", entry_date=date(2026, 8, 2),
                line_no=1, category="material", source_type="mfg_material_issue", source_id="i1", amount=Decimal("10"),
            ),
            CostProjectEntry(
                org_id="org-1", project_id="p1", period="2026-08", entry_date=date(2026, 8, 2),
                line_no=2, category="subcontract", source_type="subcontract_receipt", source_id="s1", amount=Decimal("20"),
            ),
            CostProjectEntry(
                org_id="org-1", project_id="p1", period="2026-08", entry_date=date(2026, 8, 2),
                line_no=3, category="labor", source_type="mfg_work_report", source_id="r1", amount=Decimal("30"),
            ),
            CostProjectEntry(
                org_id="org-1", project_id="p1", period="2026-08", entry_date=date(2026, 8, 2),
                line_no=4, category="expense", source_type="fin_expense", source_id="e1", amount=Decimal("40"),
            ),
        ]
    )
    session.flush()

    result = calculate_project_cost(session, "p1", "2026-08", context)
    assert result["total_amount"] == Decimal("100.00")
    assert result["by_category"] == {
        "material": Decimal("10.00"),
        "subcontract": Decimal("20.00"),
        "labor": Decimal("30.00"),
        "expense": Decimal("40.00"),
    }


def test_close_period_rejects_negative_stock_and_locks_cost_events(client_and_session):
    _, session = client_and_session
    context = _context(session)
    session.add(
        InvStock(
            org_id="org-1", warehouse_id="warehouse-1", material_id="material-1",
            quantity=Decimal("-1"), locked_quantity=Decimal("0"), available_quantity=Decimal("-1"),
            average_cost=Decimal("0"),
        )
    )
    session.flush()
    with pytest.raises(AppError) as error:
        close_period(session, "org-1", "2026-08", context)
    assert error.value.code == 400
    session.query(InvStock).delete()
    session.flush()

    closed = close_period(session, "org-1", "2026-08", context)
    assert closed.status == "closed"
    with pytest.raises(AppError) as error:
        assert_period_open(session, "org-1", date(2026, 8, 2))
    assert error.value.code == 400
    with pytest.raises(AppError) as error:
        create_allocation(
            session,
            {"allocation_date": date(2026, 8, 2), "amount": "10", "basis": "quantity", "items": [{"project_id": "p1", "quantity": "1"}]},
            context,
        )
    assert error.value.code == 400


def test_reopen_period_requires_permission_and_writes_operation_log(client_and_session):
    _, session = client_and_session
    admin = _context(session, {"cost:period:reopen"})
    closed = close_period(session, "org-1", "2026-08", admin)
    assert closed.status == "closed"

    with pytest.raises(AppError) as error:
        reopen_period(session, "org-1", "2026-08", _context(session, {"cost:view"}))
    assert error.value.code == 403

    opened = reopen_period(session, "org-1", "2026-08", admin)
    assert opened.status == "open"
    actions = session.scalars(
        select(SysOperationLog.action).where(SysOperationLog.resource == "cost_period_close")
    ).all()
    assert actions == ["close", "reopen"]


def test_period_close_is_idempotent_for_already_closed_period(client_and_session):
    _, session = client_and_session
    context = _context(session)
    first = close_period(session, "org-1", "2026-08", context)
    second = close_period(session, "org-1", "2026-08", context)
    assert second.id == first.id
    assert session.query(CostPeriodClose).count() == 1
