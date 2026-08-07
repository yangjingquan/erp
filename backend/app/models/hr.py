from datetime import date
from decimal import Decimal
from sqlalchemy import Date, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped,mapped_column
from app.models.base import AuditMixin,UUIDModel
class HrEmployee(AuditMixin,UUIDModel):
 __tablename__="hr_employee";org_id:Mapped[str]=mapped_column(String(36),nullable=False,index=True);employee_no:Mapped[str]=mapped_column(String(64),nullable=False);name:Mapped[str]=mapped_column(String(128),nullable=False);department_id:Mapped[str|None]=mapped_column(String(36));status:Mapped[str]=mapped_column(String(32),default="active",nullable=False);base_salary:Mapped[Decimal]=mapped_column(Numeric(18,2),default=0,nullable=False);allowance:Mapped[Decimal]=mapped_column(Numeric(18,2),default=0,nullable=False);__table_args__=(UniqueConstraint("org_id","employee_no",name="uk_hr_employee_no"),)
class HrAttendance(AuditMixin,UUIDModel):
 __tablename__="hr_attendance";org_id:Mapped[str]=mapped_column(String(36),nullable=False,index=True);employee_id:Mapped[str]=mapped_column(String(36),nullable=False);attendance_date:Mapped[date]=mapped_column(Date,nullable=False);status:Mapped[str]=mapped_column(String(32),default="present",nullable=False);__table_args__=(UniqueConstraint("employee_id","attendance_date",name="uk_hr_attendance_employee_date"),)
class HrPayroll(AuditMixin,UUIDModel):
 __tablename__="hr_payroll_run";org_id:Mapped[str]=mapped_column(String(36),nullable=False,index=True);period:Mapped[str]=mapped_column(String(16),nullable=False);status:Mapped[str]=mapped_column(String(32),default="draft",nullable=False);total_amount:Mapped[Decimal]=mapped_column(Numeric(18,2),default=0,nullable=False);items_json:Mapped[list]=mapped_column(JSON,default=list,nullable=False);__table_args__=(UniqueConstraint("org_id","period",name="uk_hr_payroll_period"),)
