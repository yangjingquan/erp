"""GAP-06: 薪资审批计提、发放生成凭证."""
from decimal import Decimal

from app.models.hr import HrPayroll
from app.services.hr_service import approve_payroll, pay_payroll
from tests.gap_helpers import voucher_lines


def test_payroll_vouchers(db, ctx):
    row = HrPayroll(org_id="org-test", period="2026-10", status="calculated", total_amount=Decimal("8000.00"), items_json=[])
    db.add(row); db.flush()
    approve_payroll(db, row.id, ctx)
    assert voucher_lines(db, "payroll_accrual", row.id) == {"6602": (Decimal("8000"), 0), "2211": (0, Decimal("8000"))}
    pay_payroll(db, row.id, ctx)
    assert voucher_lines(db, "payroll", row.id) == {"2211": (Decimal("8000"), 0), "1002": (0, Decimal("8000"))}
    assert voucher_lines(db, "payroll_accrual", row.id)  # still exactly one accrual voucher


def test_pay_backfills_accrual_for_legacy_batch(db, ctx):
    row = HrPayroll(org_id="org-test", period="2026-09", status="approved", total_amount=Decimal("100.00"), items_json=[])
    db.add(row); db.flush()
    pay_payroll(db, row.id, ctx)
    assert voucher_lines(db, "payroll_accrual", row.id)
    assert voucher_lines(db, "payroll", row.id)
