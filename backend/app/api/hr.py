from fastapi import APIRouter,Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.exceptions import AppError
from app.core.response import ok
from app.schemas.hr import EmployeeCreate, EmployeePasswordUpdate, EmployeeUpdate, AttendanceCreate
from app.services.auth_service import UserContext
from app.services.hr_service import *
from app.models.hr import HrEmployee, HrPayroll
from app.models.system import SysUser
router=APIRouter(prefix="/api/hr",tags=["hr"])
@router.get("/employees")
def employees(context:UserContext=Depends(get_current_user),db:Session=Depends(get_db)):
    rows = list_employees(db, context)
    result = []
    for row in rows:
        account = db.get(SysUser, row.user_id) if row.user_id else None
        result.append({"id": row.id, "employee_no": row.employee_no, "name": row.name, "department_id": row.department_id, "status": row.status, "base_salary": str(row.base_salary), "allowance": str(row.allowance), "user_id": row.user_id, "account_username": account.username if account else None})
    return ok(result)
@router.get("/payroll")
def payroll(period: str | None = None, context:UserContext=Depends(get_current_user),db:Session=Depends(get_db)):
    statement = select(HrPayroll).where(HrPayroll.org_id == context.org_id)
    if period: statement = statement.where(HrPayroll.period == period)
    rows = db.scalars(statement.order_by(HrPayroll.period.desc())).all()
    return ok([{"id": row.id, "period": row.period, "status": row.status, "total_amount": str(row.total_amount)} for row in rows])
@router.post("/employees")
def employee(payload:EmployeeCreate,context:UserContext=Depends(require_permission("hr:employee:manage")),db:Session=Depends(get_db)): row=create_employee(db,payload.model_dump(),context);db.commit();return ok({"id":row.id,"name":row.name,"status":row.status})
@router.put("/employees/{employee_id}")
def update_employee_api(employee_id:str,payload:EmployeeUpdate,context:UserContext=Depends(require_permission("hr:employee:manage")),db:Session=Depends(get_db)): row=update_employee(db,employee_id,payload.model_dump(),context);db.commit();return ok({"id":row.id,"name":row.name,"status":row.status})
@router.put("/employees/{employee_id}/password")
def change_employee_password_api(employee_id:str,payload:EmployeePasswordUpdate,context:UserContext=Depends(require_permission("hr:employee:manage")),db:Session=Depends(get_db)): change_employee_password(db,employee_id,payload.password,context);db.commit();return ok(msg="员工账号密码已更新")
@router.post("/employees/{employee_id}/attendance")
def attendance(employee_id:str,payload:AttendanceCreate,context:UserContext=Depends(require_permission("hr:employee:manage")),db:Session=Depends(get_db)): row=record_attendance(db,employee_id,payload.model_dump(),context);db.commit();return ok({"id":row.id})
@router.post("/payroll/{period}/calculate")
def calculate(period:str,context:UserContext=Depends(require_permission("hr:salary:manage")),db:Session=Depends(get_db)): row=calculate_payroll(db,period,context);db.commit();return ok({"id":row.id,"status":row.status,"total_amount":str(row.total_amount)})
@router.get("/payroll/{payroll_id}/details")
def payroll_details(payroll_id: str, context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(HrPayroll).where(HrPayroll.id == payroll_id, HrPayroll.org_id == context.org_id))
    if row is None:
        raise AppError("薪资批次不存在", code=404)
    employee_ids = [item.get("employee_id") for item in (row.items_json or []) if item.get("employee_id")]
    employees = {item.id: item for item in db.scalars(select(HrEmployee).where(HrEmployee.id.in_(employee_ids), HrEmployee.org_id == context.org_id)).all()} if employee_ids else {}
    return ok([{"employee_id": item.get("employee_id"), "employee_no": item.get("employee_no") or (employees.get(item.get("employee_id")).employee_no if employees.get(item.get("employee_id")) else None), "employee_name": item.get("name") or (employees.get(item.get("employee_id")).name if employees.get(item.get("employee_id")) else None), "base_amount": item.get("base_amount", item.get("amount", "0")), "deduction": item.get("deduction", "0"), "absent_days": item.get("absent_days", 0), "late_days": item.get("late_days", 0), "leave_days": item.get("leave_days", 0), "amount": item.get("amount", "0")} for item in (row.items_json or [])])
@router.post("/payroll/{payroll_id}/approve")
def approve(payroll_id:str,context:UserContext=Depends(require_permission("hr:salary:manage")),db:Session=Depends(get_db)): row=approve_payroll(db,payroll_id,context);db.commit();return ok({"id":row.id,"status":row.status})
@router.post("/payroll/{payroll_id}/pay")
def pay(payroll_id:str,context:UserContext=Depends(require_permission("hr:salary:manage")),db:Session=Depends(get_db)): row=pay_payroll(db,payroll_id,context);db.commit();return ok({"id":row.id,"status":row.status})
