from datetime import date, datetime
from decimal import Decimal

import pytest
from app.core.exceptions import AppError
from app.models.crm import CrmLead, CrmOpportunity
from app.models.hr import HrEmployee
from app.models.quality import QaNonconformity
from app.models.system import SysUser
from app.services.auth_service import UserContext
from app.services.crm_service import create_lead, convert_lead, transition_lead
from app.services.hr_service import calculate_payroll, create_employee, record_attendance
from app.services.quality_service import close_inspection, create_inspection, submit_inspection


def ctx(session, permissions=None):
    return UserContext(user=session.get(SysUser, "user-1"), permissions=set(permissions or {"*"}))


def test_crm_conversion_is_idempotent(client_and_session):
    _, session = client_and_session
    context = ctx(session)
    lead = create_lead(session, {"name": "Acme", "phone": "13800000000"}, context)
    transition_lead(session, lead.id, "contacted", context)
    transition_lead(session, lead.id, "qualified", context)
    first = convert_lead(session, lead.id, context)
    second = convert_lead(session, lead.id, context)
    assert first == second


def test_quality_failed_result_requires_disposition_and_creates_one_exception(client_and_session):
    _, session = client_and_session
    context = ctx(session)
    inspection = create_inspection(session, "incoming", "purchase_receipt", "receipt-1", context)
    submitted = submit_inspection(session, inspection.id, [{"item": "appearance", "value": "fail"}], context)
    assert submitted.result == "failed"
    assert session.query(QaNonconformity).filter_by(inspection_id=inspection.id).count() == 1
    with pytest.raises(AppError):
        close_inspection(session, inspection.id, None, context)
    assert close_inspection(session, inspection.id, "rework", context).status == "closed"


def test_hr_rejects_duplicate_attendance_and_calculates_decimal_payroll(client_and_session):
    _, session = client_and_session
    context = ctx(session)
    employee = create_employee(session, {"employee_no": "E-1", "name": "Alice", "base_salary": Decimal("1000.00"), "allowance": Decimal("100.10")}, context)
    record_attendance(session, employee.id, {"attendance_date": date(2026, 8, 2), "status": "present"}, context)
    with pytest.raises(AppError):
        record_attendance(session, employee.id, {"attendance_date": date(2026, 8, 2), "status": "present"}, context)
    payroll = calculate_payroll(session, "2026-08", context)
    assert payroll.total_amount == Decimal("1100.10")
