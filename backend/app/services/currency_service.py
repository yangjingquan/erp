from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.finance import FinCurrency, FinExchangeRate
from app.services.auth_service import UserContext


def list_currencies(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(select(FinCurrency).where(FinCurrency.org_id == context.org_id, FinCurrency.is_deleted.is_(False)).order_by(FinCurrency.code)).all()
    return [{"id": row.id, "code": row.code, "name": row.name, "symbol": row.symbol, "decimal_places": row.decimal_places, "is_base": row.is_base, "status": row.status} for row in rows]


def create_currency(db: Session, payload, context: UserContext) -> FinCurrency:
    code = payload.code.upper()
    if payload.is_base and db.scalar(select(FinCurrency.id).where(FinCurrency.org_id == context.org_id, FinCurrency.is_base.is_(True), FinCurrency.status == "active", FinCurrency.is_deleted.is_(False))) is not None:
        raise AppError("每个组织只能设置一个本位币", code=409)
    row = FinCurrency(org_id=context.org_id, code=code, name=payload.name, symbol=payload.symbol, decimal_places=payload.decimal_places, is_base=payload.is_base, status=payload.status)
    try:
        with db.begin_nested():
            db.add(row); db.flush()
    except IntegrityError as exc:
        raise AppError("币种编码已存在", code=409) from exc
    return row


def list_exchange_rates(db: Session, context: UserContext, currency: str | None = None) -> list[dict]:
    statement = select(FinExchangeRate).where(FinExchangeRate.org_id == context.org_id, FinExchangeRate.is_deleted.is_(False))
    if currency:
        code = currency.upper(); statement = statement.where((FinExchangeRate.base_currency == code) | (FinExchangeRate.quote_currency == code))
    rows = db.scalars(statement.order_by(FinExchangeRate.rate_date.desc(), FinExchangeRate.base_currency, FinExchangeRate.quote_currency)).all()
    return [{"id": row.id, "base_currency": row.base_currency, "quote_currency": row.quote_currency, "rate_date": row.rate_date.isoformat(), "rate": str(row.rate), "source": row.source} for row in rows]


def upsert_exchange_rate(db: Session, payload, context: UserContext) -> FinExchangeRate:
    base = payload.base_currency.upper(); quote = payload.quote_currency.upper()
    currencies = {row.code for row in db.scalars(select(FinCurrency).where(FinCurrency.org_id == context.org_id, FinCurrency.status == "active", FinCurrency.is_deleted.is_(False), FinCurrency.code.in_([base, quote]))).all()}
    if currencies != {base, quote}:
        raise AppError("基础币种和目标币种必须先在币种档案中启用", code=400)
    row = db.scalar(select(FinExchangeRate).where(FinExchangeRate.org_id == context.org_id, FinExchangeRate.base_currency == base, FinExchangeRate.quote_currency == quote, FinExchangeRate.rate_date == payload.rate_date, FinExchangeRate.is_deleted.is_(False)).with_for_update())
    if row is None:
        row = FinExchangeRate(org_id=context.org_id, base_currency=base, quote_currency=quote, rate_date=payload.rate_date, rate=payload.rate, source=payload.source)
        db.add(row)
    else:
        row.rate = payload.rate; row.source = payload.source; row.version += 1
    db.flush(); return row


def convert_amount(db: Session, amount: Decimal, base_currency: str, quote_currency: str, rate_date, context: UserContext) -> dict:
    base = base_currency.upper(); quote = quote_currency.upper()
    if base == quote:
        return {"amount": str(Decimal(amount)), "rate": "1", "base_currency": base, "quote_currency": quote, "rate_date": rate_date.isoformat()}
    row = db.scalar(select(FinExchangeRate).where(FinExchangeRate.org_id == context.org_id, FinExchangeRate.base_currency == base, FinExchangeRate.quote_currency == quote, FinExchangeRate.rate_date <= rate_date, FinExchangeRate.is_deleted.is_(False)).order_by(FinExchangeRate.rate_date.desc()))
    if row is None:
        raise AppError("未找到指定日期可用汇率", code=404)
    return {"amount": str((Decimal(amount) * Decimal(row.rate)).quantize(Decimal("0.01"))), "rate": str(row.rate), "base_currency": base, "quote_currency": quote, "rate_date": row.rate_date.isoformat()}
