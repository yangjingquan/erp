from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FinanceSchema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class AccountCreate(FinanceSchema):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    account_type: str = Field(pattern="^(asset|liability|equity|cost|revenue|expense)$")
    balance_direction: str = Field(pattern="^(debit|credit)$")
    parent_id: str | None = Field(default=None, max_length=36)
    allow_posting: bool = True


class DimensionCreate(FinanceSchema):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    dimension_type: str = Field(pattern="^(department|customer|supplier|employee|project|custom)$")
    required: bool = False


class FiscalPeriodCreate(FinanceSchema):
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("会计期间结束日期不能早于开始日期")
        if self.period != self.start_date.strftime("%Y-%m"):
            raise ValueError("期间编码必须与开始日期月份一致")
        if self.period != self.end_date.strftime("%Y-%m"):
            raise ValueError("会计期间开始和结束日期必须在同一月份")
        return self


class BankAccountCreate(FinanceSchema):
    name: str = Field(min_length=1, max_length=128)
    bank_name: str = Field(min_length=1, max_length=128)
    account_no: str = Field(min_length=4, max_length=64)
    currency: str = Field(default="CNY", min_length=3, max_length=8)
    ledger_account_id: str = Field(min_length=1, max_length=36)


class VoucherEntryCreate(FinanceSchema):
    account_code: str = Field(min_length=1, max_length=64)
    summary: str = Field(default="", max_length=255)
    debit_amount: Decimal = Field(default=Decimal("0"), ge=0)
    credit_amount: Decimal = Field(default=Decimal("0"), ge=0)
    dimensions: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_side(self):
        if (self.debit_amount > 0) == (self.credit_amount > 0):
            raise ValueError("凭证明细必须且只能填写借方或贷方金额")
        return self


class ManualVoucherCreate(FinanceSchema):
    voucher_date: date
    entries: list[VoucherEntryCreate] = Field(min_length=2)


class AssetCreate(FinanceSchema):
    asset_code: str = Field(min_length=1, max_length=64)
    asset_name: str = Field(min_length=1, max_length=128)
    category: str | None = Field(default=None, max_length=64)
    purchase_date: date
    original_value: Decimal = Field(gt=0)
    useful_life_months: int = Field(default=60, ge=1, le=1200)
    residual_rate: Decimal = Field(default=Decimal("0"), ge=0, lt=1)
    depreciation_account_code: str = Field(default="1602", min_length=1, max_length=64)
    expense_account_code: str = Field(default="6602", min_length=1, max_length=64)


class DepreciationRun(FinanceSchema):
    period: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
