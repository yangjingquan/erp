from datetime import date
from decimal import Decimal
from pydantic import BaseModel,Field
class EmployeeCreate(BaseModel): employee_no:str=Field(min_length=1,max_length=64);name:str=Field(min_length=1,max_length=128);department_id:str|None=None;status:str=Field(default="active",pattern="^(active|inactive)$");base_salary:Decimal=Field(ge=0);allowance:Decimal=Field(default=0,ge=0);account_username:str|None=Field(default=None,min_length=3,max_length=64);account_password:str|None=Field(default=None,min_length=8,max_length=128)
class EmployeeUpdate(BaseModel): name:str=Field(min_length=1,max_length=128);department_id:str|None=None;status:str=Field(pattern="^(active|inactive)$");base_salary:Decimal=Field(ge=0);allowance:Decimal=Field(default=0,ge=0)
class EmployeePasswordUpdate(BaseModel): password:str=Field(min_length=8,max_length=128)
class AttendanceCreate(BaseModel): attendance_date:date;status:str=Field(default="present",min_length=1,max_length=32)
