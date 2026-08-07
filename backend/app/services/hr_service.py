from datetime import date
from decimal import Decimal
from sqlalchemy import select
from app.core.exceptions import AppError
from app.models.hr import HrAttendance,HrEmployee,HrPayroll
def create_employee(db,payload,context): row=HrEmployee(org_id=context.org_id,**payload);db.add(row);db.flush();return row
def record_attendance(db,employee_id,payload,context):
 e=db.scalar(select(HrEmployee).where(HrEmployee.id==employee_id,HrEmployee.org_id==context.org_id));
 if e is None: raise AppError("员工不存在",code=404)
 if e.status!="active": raise AppError("非在职员工不能考勤",code=400)
 if db.scalar(select(HrAttendance).where(HrAttendance.employee_id==employee_id,HrAttendance.attendance_date==payload["attendance_date"])): raise AppError("当天考勤已存在",code=400)
 row=HrAttendance(org_id=context.org_id,employee_id=employee_id,**payload);db.add(row);db.flush();return row
def calculate_payroll(db,period,context):
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
