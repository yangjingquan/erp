from datetime import date
from decimal import Decimal
from pydantic import BaseModel,Field
class EmployeeCreate(BaseModel): employee_no:str=Field(min_length=1,max_length=64);name:str=Field(min_length=1,max_length=128);base_salary:Decimal=Field(ge=0);allowance:Decimal=Field(default=0,ge=0)
class AttendanceCreate(BaseModel): attendance_date:date;status:str=Field(default="present",min_length=1,max_length=32)
