"""DEF-001: current natural month must not be closed; missing month auto-opens."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import AppError
from app.services.ledger_service import (
    assert_fiscal_period_open,
    close_fiscal_period,
    get_or_create_period,
    list_periods,
    reject_closing_current_natural_month,
)


class _FakePeriod:
    def __init__(self, period: str, status: str = "open", org_id: str = "org-1"):
        self.id = f"fp-{period}"
        self.org_id = org_id
        self.period = period
        self.status = status
        self.start_date = date.fromisoformat(f"{period}-01")
        # end_date approximate; fine for open assert range checks using real calendar later
        year, month = map(int, period.split("-"))
        import calendar
        last = calendar.monthrange(year, month)[1]
        self.end_date = date(year, month, last)
        self.closed_at = None
        self.closed_by = None
        self.reopened_at = None
        self.reopened_by = None
        self.is_deleted = False


def test_reject_closing_current_natural_month():
    with patch("app.services.ledger_service.local_today", return_value=date(2026, 10, 15)):
        with pytest.raises(AppError) as exc:
            reject_closing_current_natural_month("2026-10")
        assert "不能关闭当前自然月" in exc.value.msg
        assert "2026-10" in exc.value.msg
        assert exc.value.code == 409
        # historical month allowed (no raise)
        reject_closing_current_natural_month("2026-09")
        reject_closing_current_natural_month("2025-12")


def test_close_fiscal_period_blocks_current_month():
    db = MagicMock()
    context = SimpleNamespace(org_id="org-1", id="u1", user=SimpleNamespace(id="u1"))
    with patch("app.services.ledger_service.local_today", return_value=date(2026, 10, 15)):
        with pytest.raises(AppError) as exc:
            close_fiscal_period(db, "2026-10", context)
        assert "不能关闭当前自然月" in exc.value.msg
        db.scalar.assert_not_called()


def test_close_fiscal_period_allows_historical_month():
    db = MagicMock()
    period_row = _FakePeriod("2026-09", status="open")
    context = SimpleNamespace(org_id="org-1", id="u1", user=SimpleNamespace(id="u1", username="admin"))

    def scalar_side_effect(stmt=None, *args, **kwargs):
        # first call get_or_create via scalar; then draft_count
        # We patch get_or_create_period instead for clarity
        return 0

    with patch("app.services.ledger_service.local_today", return_value=date(2026, 10, 15)), \
         patch("app.services.ledger_service.get_or_create_period", return_value=period_row) as goc, \
         patch("app.services.ledger_service.write_operation_log") as wol, \
         patch("app.services.ledger_service.local_now", return_value=date(2026, 10, 15)):
        db.scalar.return_value = 0  # no draft vouchers
        result = close_fiscal_period(db, "2026-09", context)
        assert result.status == "closed"
        assert result.closed_by == "u1"
        goc.assert_called_once()
        wol.assert_called_once()
        db.flush.assert_called()


def test_get_or_create_period_creates_open_when_missing():
    db = MagicMock()
    db.scalar.return_value = None  # missing

    with patch("app.services.ledger_service.local_today", return_value=date(2026, 10, 15)):
        row = get_or_create_period(db, "org-1", "2026-10")
        assert row.period == "2026-10"
        assert row.status == "open"
        db.add.assert_called_once()
        db.flush.assert_called()


def test_assert_fiscal_period_open_auto_creates_current_month():
    db = MagicMock()
    created = _FakePeriod("2026-10", status="open")
    with patch("app.services.ledger_service.get_or_create_period", return_value=created) as goc:
        row = assert_fiscal_period_open(db, "org-1", date(2026, 10, 15))
        assert row.status == "open"
        goc.assert_called_once_with(db, "org-1", "2026-10")


def test_list_periods_ensures_current_month_open():
    db = MagicMock()
    current = _FakePeriod("2026-10", status="open")
    historical = _FakePeriod("2026-09", status="closed")

    class _Scalars:
        def all(self_inner):
            return [current, historical]

    db.scalars.return_value = _Scalars()
    context = SimpleNamespace(org_id="org-1")

    with patch("app.services.ledger_service.local_today", return_value=date(2026, 10, 15)), \
         patch("app.services.ledger_service.get_or_create_period", return_value=current) as goc:
        items = list_periods(db, context)
        goc.assert_called_once_with(db, "org-1", "2026-10")
        assert items[0]["period"] == "2026-10"
        assert items[0]["status"] == "open"


def test_cost_close_period_blocks_current_month():
    from app.services.cost_service import close_period

    db = MagicMock()
    context = SimpleNamespace(org_id="org-1", id="u1", user=SimpleNamespace(id="u1"), permissions={"*"})
    with patch("app.services.ledger_service.local_today", return_value=date(2026, 10, 15)):
        with pytest.raises(AppError) as exc:
            close_period(db, "org-1", "2026-10", context)
        assert "不能关闭当前自然月" in exc.value.msg
