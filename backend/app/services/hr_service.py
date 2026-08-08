from datetime import date
from decimal import Decimal
import re
from sqlalchemy import select
from app.core.exceptions import AppError
from app.models.hr import HrAttendance,HrEmployee,HrPayroll
from app.models.system import SysUser
from app.core.security import hash_password

def _visible_employee(db, employee_id, context):
    statement = select(HrEmployee).where(HrEmployee.id == employee_id, HrEmployee.org_id == context.org_id, HrEmployee.is_deleted.is_(False))
    if not context.user.is_superuser:
        if context.data_scope_type == "own":
            statement = statement.where(HrEmployee.user_id == context.id)
        elif context.data_scope_type != "all":
            statement = statement.where(HrEmployee.department_id == context.department_id)
    return db.scalar(statement)

def list_employees(db, context):
    statement = select(HrEmployee).where(HrEmployee.org_id == context.org_id, HrEmployee.is_deleted.is_(False))
    if not context.user.is_superuser:
        if context.data_scope_type == "own":
            statement = statement.where(HrEmployee.user_id == context.id)
        elif context.data_scope_type != "all":
            statement = statement.where(HrEmployee.department_id == context.department_id)
    return db.scalars(statement.order_by(HrEmployee.created_at.desc())).all()

def create_employee(db,payload,context):
    account_username = payload.pop("account_username", None)
    account_password = payload.pop("account_password", None)
    if account_password and not account_username:
        raise AppError("设置账号密码时必须填写登录账号", code=400)
    if db.scalar(select(HrEmployee).where(HrEmployee.org_id == context.org_id, HrEmployee.employee_no == payload["employee_no"], HrEmployee.is_deleted.is_(False))):
        raise AppError("员工工号已存在", code=409)
    account = None
    if account_username:
        if db.scalar(select(SysUser).where(SysUser.username == account_username, SysUser.is_deleted.is_(False))):
            raise AppError("登录账号已存在", code=409)
        account = SysUser(org_id=context.org_id, department_id=payload.get("department_id"), username=account_username, display_name=payload["name"], password_hash=hash_password(account_password), status="active", is_superuser=False)
        db.add(account)
        db.flush()
        payload["user_id"] = account.id
    row=HrEmployee(org_id=context.org_id,**payload);db.add(row);db.flush();return row

def update_employee(db, employee_id, payload, context):
    row = _visible_employee(db, employee_id, context)
    if row is None: raise AppError("员工不存在或超出数据范围", code=404)
    for field, value in payload.items(): setattr(row, field, value)
    if row.user_id:
        account = db.get(SysUser, row.user_id)
        if account: account.display_name = row.name; account.department_id = row.department_id
    db.flush(); return row

def change_employee_password(db, employee_id, password, context):
    row = _visible_employee(db, employee_id, context)
    if row is None: raise AppError("员工不存在或超出数据范围", code=404)
    if not row.user_id: raise AppError("该员工尚未绑定登录账号", code=400)
    account = db.get(SysUser, row.user_id)
    if account is None: raise AppError("员工账号不存在", code=404)
    account.password_hash = hash_password(password)
    db.flush()
    return account

def record_attendance(db,employee_id,payload,context):
 e=db.scalar(select(HrEmployee).where(HrEmployee.id==employee_id,HrEmployee.org_id==context.org_id));
 if e is None: raise AppError("员工不存在",code=404)
 if e.status!="active": raise AppError("非在职员工不能考勤",code=400)
 if db.scalar(select(HrAttendance).where(HrAttendance.employee_id==employee_id,HrAttendance.attendance_date==payload["attendance_date"])): raise AppError("当天考勤已存在",code=400)
 row=HrAttendance(org_id=context.org_id,employee_id=employee_id,**payload);db.add(row);db.flush();return row
def calculate_payroll(db,period,context):
 if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", period): raise AppError("薪资期间必须为 YYYY-MM",code=400)
 row=db.scalar(select(HrPayroll).where(HrPayroll.org_id==context.org_id,HrPayroll.period==period))
 if row and row.status in {"approved","paid"}: raise AppError("已审批薪资不能重算",code=400)
 employees=db.scalars(select(HrEmployee).where(HrEmployee.org_id==context.org_id,HrEmployee.status=="active")).all();items=[];total=Decimal("0")
 for e in employees:
  amount=(e.base_salary+e.allowance).quantize(Decimal("0.01"));total+=amount;items.append({"employee_id":e.id,"amount":str(amount)})
 if row is None: row=HrPayroll(org_id=context.org_id,period=period)
 row.total_amount=total;row.items_json=items;row.status="calculated";db.add(row);db.flush();return row
def approve_payroll(db,payroll_id,context):
 row=db.get(HrPayroll,payroll_id)
 if row is None or row.org_id!=context.org_id: raise AppError("薪资批次不存在",code=404)
 if row.status!="calculated": raise AppError("只有已计算薪资可审批",code=400)
 row.status="approved";db.flush();return row
def pay_payroll(db,payroll_id,context):
 row=db.get(HrPayroll,payroll_id)
 if row is None or row.org_id!=context.org_id: raise AppError("薪资批次不存在",code=404)
 if row.status!="approved": raise AppError("只有已审批薪资可支付",code=400)
 row.status="paid";db.flush();return row
