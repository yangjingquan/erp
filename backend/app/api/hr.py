from fastapi import APIRouter,Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.core.response import ok
from app.schemas.hr import EmployeeCreate,AttendanceCreate
from app.services.auth_service import UserContext
from app.services.hr_service import *
from app.models.hr import HrEmployee, HrPayroll
router=APIRouter(prefix="/api/hr",tags=["hr"])
@router.get("/employees")
def employees(context:UserContext=Depends(get_current_user),db:Session=Depends(get_db)):
    rows = db.scalars(select(HrEmployee).where(HrEmployee.org_id == context.org_id).order_by(HrEmployee.created_at.desc())).all()
    return ok([{"id": row.id, "employee_no": row.employee_no, "name": row.name, "status": row.status} for row in rows])
@router.get("/payroll")
def payroll(period: str | None = None, context:UserContext=Depends(get_current_user),db:Session=Depends(get_db)):
    statement = select(HrPayroll).where(HrPayroll.org_id == context.org_id)
    if period: statement = statement.where(HrPayroll.period == period)
    rows = db.scalars(statement.order_by(HrPayroll.period.desc())).all()
    return ok([{"id": row.id, "period": row.period, "status": row.status, "total_amount": str(row.total_amount)} for row in rows])
@router.post("/employees")
def employee(payload:EmployeeCreate,context:UserContext=Depends(get_current_user),db:Session=Depends(get_db)): row=create_employee(db,payload.model_dump(),context);db.commit();return ok({"id":row.id,"name":row.name,"status":row.status})
@router.post("/employees/{employee_id}/attendance")
def attendance(employee_id:str,payload:AttendanceCreate,context:UserContext=Depends(get_current_user),db:Session=Depends(get_db)): row=record_attendance(db,employee_id,payload.model_dump(),context);db.commit();return ok({"id":row.id})
@router.post("/payroll/{period}/calculate")
def calculate(period:str,context:UserContext=Depends(get_current_user),db:Session=Depends(get_db)): row=calculate_payroll(db,period,context);db.commit();return ok({"id":row.id,"status":row.status,"total_amount":str(row.total_amount)})
@router.post("/payroll/{payroll_id}/approve")
def approve(payroll_id:str,context:UserContext=Depends(get_current_user),db:Session=Depends(get_db)): row=approve_payroll(db,payroll_id,context);db.commit();return ok({"id":row.id,"status":row.status})
@router.post("/payroll/{payroll_id}/pay")
def pay(payroll_id:str,context:UserContext=Depends(get_current_user),db:Session=Depends(get_db)): row=pay_payroll(db,payroll_id,context);db.commit();return ok({"id":row.id,"status":row.status})
