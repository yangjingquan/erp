from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import AppError
from app.core.time import local_now, local_today
from app.models.finance import (
    FinAccount,
    FinAccountingDimension,
    FinAsset,
    FinAssetDepreciation,
    FinBankAccount,
    FinFiscalPeriod,
    FinVoucher,
    FinVoucherEntry,
)
from app.services.audit_service import write_operation_log
from app.services.auth_service import UserContext

CENT = Decimal("0.01")
DEFAULT_ACCOUNTS = (
    ("1002", "银行存款", "asset", "debit"),
    ("1122", "应收账款", "asset", "debit"),
    ("1403", "原材料", "asset", "debit"),
    ("1405", "库存商品", "asset", "debit"),
    ("1601", "固定资产", "asset", "debit"),
    ("1602", "累计折旧", "asset", "credit"),
    ("2202", "应付账款", "liability", "credit"),
    ("2211", "应付职工薪酬", "liability", "credit"),
    ("4101", "制造费用", "cost", "credit"),
    ("5001", "生产成本", "cost", "debit"),
    ("6001", "主营业务收入", "revenue", "credit"),
    ("6602", "管理费用", "expense", "debit"),
)


def _money(value: Decimal | int | str | None) -> Decimal:
    return Decimal(str(value or 0)).quantize(CENT, rounding=ROUND_HALF_UP)


def _page(items: list[dict], total: int, page: int, page_size: int, summary: dict | None = None) -> dict:
    return {"items": items, "total": total, "page": page, "page_size": page_size, "summary": summary or {}}


def _period_dates(period: str) -> tuple[date, date]:
    try:
        year, month = (int(value) for value in period.split("-", 1))
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)
    except (TypeError, ValueError) as exc:
        raise AppError("会计期间格式必须为 YYYY-MM", code=400) from exc


def ensure_default_accounts(db: Session, org_id: str) -> None:
    existing = set(db.scalars(select(FinAccount.code).where(FinAccount.org_id == org_id)).all())
    for code, name, account_type, direction in DEFAULT_ACCOUNTS:
        if code not in existing:
            db.add(FinAccount(
                org_id=org_id,
                code=code,
                name=name,
                account_type=account_type,
                balance_direction=direction,
                allow_posting=True,
                status="active",
            ))
    db.flush()


def get_or_create_period(db: Session, org_id: str, period: str) -> FinFiscalPeriod:
    row = db.scalar(select(FinFiscalPeriod).where(FinFiscalPeriod.org_id == org_id, FinFiscalPeriod.period == period))
    if row is None:
        start_date, end_date = _period_dates(period)
        row = FinFiscalPeriod(org_id=org_id, period=period, start_date=start_date, end_date=end_date, status="open")
        db.add(row)
        db.flush()
    return row


def assert_fiscal_period_open(db: Session, org_id: str, business_date: date) -> FinFiscalPeriod:
    row = get_or_create_period(db, org_id, business_date.strftime("%Y-%m"))
    if row.status != "open":
        raise AppError(f"会计期间 {row.period} 已结账", code=409)
    if not (row.start_date <= business_date <= row.end_date):
        raise AppError("业务日期不在会计期间范围内", code=400)
    return row


def list_accounts(db: Session, context: UserContext, page: int, page_size: int) -> dict:
    ensure_default_accounts(db, context.org_id)
    filters = [FinAccount.org_id == context.org_id, FinAccount.is_deleted.is_(False)]
    total = db.scalar(select(func.count()).select_from(FinAccount).where(*filters)) or 0
    rows = db.scalars(select(FinAccount).where(*filters).order_by(FinAccount.code).offset((page - 1) * page_size).limit(page_size)).all()
    return _page([{
        "id": row.id, "code": row.code, "name": row.name, "account_type": row.account_type,
        "balance_direction": row.balance_direction, "parent_id": row.parent_id,
        "allow_posting": row.allow_posting, "status": row.status,
    } for row in rows], total, page, page_size)


def create_account(db: Session, payload, context: UserContext) -> FinAccount:
    parent = None
    if payload.parent_id:
        parent = db.scalar(select(FinAccount).where(FinAccount.id == payload.parent_id, FinAccount.org_id == context.org_id, FinAccount.is_deleted.is_(False)))
        if parent is None:
            raise AppError("上级科目不存在", code=404)
    row = FinAccount(
        org_id=context.org_id, code=payload.code.strip(), name=payload.name.strip(),
        account_type=payload.account_type, balance_direction=payload.balance_direction,
        parent_id=parent.id if parent else None, allow_posting=payload.allow_posting, status="active",
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError as exc:
        raise AppError("科目编码已存在", code=409) from exc
    write_operation_log(db, user=context.user, action="create", resource="fin_account", target_id=row.id)
    return row


def update_account(db: Session, account_id: str, payload, context: UserContext) -> FinAccount:
    row = db.scalar(select(FinAccount).where(FinAccount.id == account_id, FinAccount.org_id == context.org_id, FinAccount.is_deleted.is_(False)))
    if row is None:
        raise AppError("会计科目不存在", code=404)
    if payload.parent_id and payload.parent_id == row.id:
        raise AppError("科目不能设置自己为上级科目", code=400)
    row.code, row.name = payload.code.strip(), payload.name.strip()
    row.account_type, row.balance_direction = payload.account_type, payload.balance_direction
    row.parent_id, row.allow_posting = payload.parent_id, payload.allow_posting
    row.version += 1
    return row


def delete_account(db: Session, account_id: str, context: UserContext) -> None:
    row = db.scalar(select(FinAccount).where(FinAccount.id == account_id, FinAccount.org_id == context.org_id, FinAccount.is_deleted.is_(False)))
    if row is None:
        raise AppError("会计科目不存在", code=404)
    child = db.scalar(select(FinAccount.id).where(FinAccount.org_id == context.org_id, FinAccount.parent_id == row.id, FinAccount.is_deleted.is_(False)))
    used = db.scalar(select(FinVoucherEntry.id).where(FinVoucherEntry.account_code == row.code).limit(1))
    if child:
        raise AppError("当前科目存在下级科目，不能删除", code=409)
    if used:
        raise AppError("当前科目已被凭证使用，不能删除", code=409)
    row.is_deleted = True
    row.version += 1


def list_dimensions(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(select(FinAccountingDimension).where(
        FinAccountingDimension.org_id == context.org_id,
        FinAccountingDimension.is_deleted.is_(False),
    ).order_by(FinAccountingDimension.code)).all()
    return [{"id": row.id, "code": row.code, "name": row.name, "dimension_type": row.dimension_type, "required": row.required, "status": row.status} for row in rows]


def create_dimension(db: Session, payload, context: UserContext) -> FinAccountingDimension:
    row = FinAccountingDimension(
        org_id=context.org_id, code=payload.code.strip(), name=payload.name.strip(),
        dimension_type=payload.dimension_type, required=payload.required, status="active",
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError as exc:
        raise AppError("核算维度编码已存在", code=409) from exc
    write_operation_log(db, user=context.user, action="create", resource="fin_accounting_dimension", target_id=row.id)
    return row


def list_periods(db: Session, context: UserContext) -> list[dict]:
    current = local_today().strftime("%Y-%m")
    get_or_create_period(db, context.org_id, current)
    rows = db.scalars(select(FinFiscalPeriod).where(
        FinFiscalPeriod.org_id == context.org_id,
        FinFiscalPeriod.is_deleted.is_(False),
    ).order_by(FinFiscalPeriod.period.desc())).all()
    return [{"id": row.id, "period": row.period, "start_date": row.start_date.isoformat(), "end_date": row.end_date.isoformat(), "status": row.status, "closed_at": row.closed_at.isoformat(timespec="seconds") if row.closed_at else None} for row in rows]


def create_period(db: Session, payload, context: UserContext) -> FinFiscalPeriod:
    existing = db.scalar(select(FinFiscalPeriod).where(FinFiscalPeriod.org_id == context.org_id, FinFiscalPeriod.period == payload.period))
    if existing:
        return existing
    overlap = db.scalar(select(FinFiscalPeriod.id).where(
        FinFiscalPeriod.org_id == context.org_id,
        FinFiscalPeriod.start_date <= payload.end_date,
        FinFiscalPeriod.end_date >= payload.start_date,
        FinFiscalPeriod.is_deleted.is_(False),
    ))
    if overlap:
        raise AppError("会计期间日期范围与现有期间重叠", code=409)
    row = FinFiscalPeriod(org_id=context.org_id, period=payload.period, start_date=payload.start_date, end_date=payload.end_date, status="open")
    db.add(row)
    db.flush()
    write_operation_log(db, user=context.user, action="create", resource="fin_fiscal_period", target_id=row.id)
    return row


def close_fiscal_period(db: Session, period: str, context: UserContext) -> FinFiscalPeriod:
    row = get_or_create_period(db, context.org_id, period)
    if row.status == "closed":
        return row
    draft_count = db.scalar(select(func.count()).select_from(FinVoucher).where(
        FinVoucher.org_id == context.org_id, FinVoucher.period == period, FinVoucher.status == "draft",
    )) or 0
    if draft_count:
        raise AppError(f"期间内仍有 {draft_count} 张未记账凭证", code=409)
    row.status = "closed"
    row.closed_at = local_now()
    row.closed_by = context.id
    write_operation_log(db, user=context.user, action="close", resource="fin_fiscal_period", target_id=row.id, detail={"period": period})
    db.flush()
    return row


def reopen_fiscal_period(db: Session, period: str, context: UserContext) -> FinFiscalPeriod:
    row = db.scalar(select(FinFiscalPeriod).where(FinFiscalPeriod.org_id == context.org_id, FinFiscalPeriod.period == period))
    if row is None:
        raise AppError("会计期间不存在", code=404)
    row.status = "open"
    row.reopened_at = local_now()
    row.reopened_by = context.id
    write_operation_log(db, user=context.user, action="reopen", resource="fin_fiscal_period", target_id=row.id, detail={"period": period})
    db.flush()
    return row


def list_bank_accounts(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(select(FinBankAccount).where(FinBankAccount.org_id == context.org_id, FinBankAccount.is_deleted.is_(False)).order_by(FinBankAccount.name)).all()
    return [{
        "id": row.id, "name": row.name, "bank_name": row.bank_name,
        "account_no_masked": f"****{row.account_no[-4:]}", "currency": row.currency,
        "ledger_account_id": row.ledger_account_id, "status": row.status,
    } for row in rows]


def create_bank_account(db: Session, payload, context: UserContext) -> FinBankAccount:
    account = db.scalar(select(FinAccount).where(
        FinAccount.id == payload.ledger_account_id, FinAccount.org_id == context.org_id,
        FinAccount.status == "active", FinAccount.is_deleted.is_(False),
    ))
    if account is None:
        raise AppError("关联会计科目不存在或已停用", code=404)
    row = FinBankAccount(
        org_id=context.org_id, name=payload.name.strip(), bank_name=payload.bank_name.strip(),
        account_no=payload.account_no.strip(), currency=payload.currency.strip().upper(),
        ledger_account_id=account.id, status="active",
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError as exc:
        raise AppError("银行账号已存在", code=409) from exc
    write_operation_log(db, user=context.user, action="create", resource="fin_bank_account", target_id=row.id)
    return row


def _validate_voucher_entries(db: Session, context: UserContext, entries) -> tuple[list[FinVoucherEntry], Decimal]:
    ensure_default_accounts(db, context.org_id)
    account_codes = {item.account_code for item in entries}
    accounts = db.scalars(select(FinAccount).where(
        FinAccount.org_id == context.org_id, FinAccount.code.in_(account_codes),
        FinAccount.status == "active", FinAccount.allow_posting.is_(True), FinAccount.is_deleted.is_(False),
    )).all()
    account_map = {row.code: row for row in accounts}
    missing = sorted(account_codes - set(account_map))
    if missing:
        raise AppError(f"会计科目不存在、停用或不可记账：{', '.join(missing)}", code=400)
    dimension_rows = db.scalars(select(FinAccountingDimension).where(
        FinAccountingDimension.org_id == context.org_id, FinAccountingDimension.required.is_(True),
        FinAccountingDimension.status == "active", FinAccountingDimension.is_deleted.is_(False),
    )).all()
    required_dimensions = {row.code for row in dimension_rows}
    active_dimension_codes = set(db.scalars(select(FinAccountingDimension.code).where(
        FinAccountingDimension.org_id == context.org_id, FinAccountingDimension.status == "active",
        FinAccountingDimension.is_deleted.is_(False),
    )).all())
    debit = sum((_money(item.debit_amount) for item in entries), Decimal("0"))
    credit = sum((_money(item.credit_amount) for item in entries), Decimal("0"))
    if debit <= 0 or debit != credit:
        raise AppError("凭证借贷必须相等且大于零", code=400)
    rows: list[FinVoucherEntry] = []
    for index, item in enumerate(entries, start=1):
        dimensions = dict(item.dimensions or {})
        unknown_dimensions = sorted(set(dimensions) - active_dimension_codes)
        if unknown_dimensions:
            raise AppError(f"凭证明细包含无效核算维度：{', '.join(unknown_dimensions)}", code=400)
        missing_dimensions = sorted(code for code in required_dimensions if not str(dimensions.get(code, "")).strip())
        if missing_dimensions:
            raise AppError(f"凭证明细缺少必填核算维度：{', '.join(missing_dimensions)}", code=400)
        account = account_map[item.account_code]
        rows.append(FinVoucherEntry(
            line_no=index, account_id=account.id, account_code=account.code, account_name=account.name,
            summary=item.summary.strip() or "手工凭证", debit_amount=_money(item.debit_amount),
            credit_amount=_money(item.credit_amount), dimensions_json=dimensions,
        ))
    return rows, debit


def create_manual_voucher(db: Session, payload, context: UserContext) -> FinVoucher:
    assert_fiscal_period_open(db, context.org_id, payload.voucher_date)
    entries, total = _validate_voucher_entries(db, context, payload.entries)
    from app.services.finance_service import _new_finance_doc_no
    row = FinVoucher(
        org_id=context.org_id, voucher_no=_new_finance_doc_no("FV", context),
        voucher_date=payload.voucher_date, period=payload.voucher_date.strftime("%Y-%m"),
        source_type="manual", status="draft", total_debit=total, total_credit=total,
    )
    row.entries = entries
    db.add(row)
    db.flush()
    write_operation_log(db, user=context.user, action="create", resource="fin_voucher", target_id=row.id)
    return row


def post_voucher(db: Session, voucher_id: str, context: UserContext) -> FinVoucher:
    row = db.scalar(select(FinVoucher).options(selectinload(FinVoucher.entries)).where(
        FinVoucher.id == voucher_id, FinVoucher.org_id == context.org_id,
    ).with_for_update())
    if row is None:
        raise AppError("会计凭证不存在", code=404)
    if row.status == "posted":
        return row
    if row.status != "draft":
        raise AppError("当前凭证状态不允许记账", code=409)
    assert_fiscal_period_open(db, context.org_id, row.voucher_date)
    debit = sum((_money(item.debit_amount) for item in row.entries), Decimal("0"))
    credit = sum((_money(item.credit_amount) for item in row.entries), Decimal("0"))
    if debit <= 0 or debit != credit or debit != _money(row.total_debit) or credit != _money(row.total_credit):
        raise AppError("凭证借贷不平衡或合计与明细不一致", code=409)
    row.status = "posted"
    row.posted_at = local_now()
    row.posted_by = context.id
    write_operation_log(db, user=context.user, action="post", resource="fin_voucher", target_id=row.id)
    db.flush()
    return row


def reverse_voucher(db: Session, voucher_id: str, context: UserContext) -> FinVoucher:
    original = db.scalar(select(FinVoucher).options(selectinload(FinVoucher.entries)).where(
        FinVoucher.id == voucher_id, FinVoucher.org_id == context.org_id,
    ).with_for_update())
    if original is None:
        raise AppError("会计凭证不存在", code=404)
    if original.status == "reversed" and original.reversal_voucher_id:
        return db.get(FinVoucher, original.reversal_voucher_id)
    if original.status != "posted":
        raise AppError("只有已记账凭证可以冲销", code=409)
    reversal_date = local_today()
    assert_fiscal_period_open(db, context.org_id, reversal_date)
    from app.services.finance_service import _new_finance_doc_no
    reversal = FinVoucher(
        org_id=context.org_id, voucher_no=_new_finance_doc_no("RV", context),
        voucher_date=reversal_date, period=reversal_date.strftime("%Y-%m"), source_type="reversal",
        source_id=original.id, status="posted", total_debit=original.total_credit,
        total_credit=original.total_debit, posted_at=local_now(), posted_by=context.id,
        reversed_from_id=original.id,
    )
    reversal.entries = [FinVoucherEntry(
        line_no=item.line_no, account_id=item.account_id, account_code=item.account_code,
        account_name=item.account_name, summary=f"冲销 {original.voucher_no}：{item.summary or ''}"[:255],
        debit_amount=item.credit_amount, credit_amount=item.debit_amount,
        dimensions_json=dict(item.dimensions_json or {}),
    ) for item in original.entries]
    db.add(reversal)
    db.flush()
    original.status = "reversed"
    original.reversal_voucher_id = reversal.id
    write_operation_log(db, user=context.user, action="reverse", resource="fin_voucher", target_id=original.id, detail={"reversal_voucher_id": reversal.id})
    return reversal


def list_assets(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(select(FinAsset).where(FinAsset.org_id == context.org_id).order_by(FinAsset.asset_code)).all()
    return [{
        "id": row.id, "asset_code": row.asset_code, "asset_name": row.asset_name, "category": row.category,
        "purchase_date": row.purchase_date.isoformat() if row.purchase_date else None,
        "original_value": str(_money(row.original_value)), "accumulated_depreciation": str(_money(row.accumulated_depreciation)),
        "net_value": str(_money(row.original_value - row.accumulated_depreciation)),
        "useful_life_months": row.useful_life_months, "residual_rate": str(row.residual_rate),
        "last_depreciation_period": row.last_depreciation_period, "status": row.status,
    } for row in rows]


def create_asset(db: Session, payload, context: UserContext) -> FinAsset:
    ensure_default_accounts(db, context.org_id)
    required_codes = {payload.depreciation_account_code, payload.expense_account_code}
    found_codes = set(db.scalars(select(FinAccount.code).where(
        FinAccount.org_id == context.org_id, FinAccount.code.in_(required_codes),
        FinAccount.status == "active", FinAccount.is_deleted.is_(False),
    )).all())
    if found_codes != required_codes:
        raise AppError("折旧相关会计科目不存在或已停用", code=400)
    duplicate = db.scalar(select(FinAsset.id).where(FinAsset.org_id == context.org_id, FinAsset.asset_code == payload.asset_code.strip()))
    if duplicate:
        raise AppError("固定资产编码已存在", code=409)
    row = FinAsset(
        org_id=context.org_id, asset_code=payload.asset_code.strip(), asset_name=payload.asset_name.strip(),
        category=payload.category.strip() if payload.category else None, purchase_date=payload.purchase_date,
        original_value=_money(payload.original_value), accumulated_depreciation=Decimal("0"),
        useful_life_months=payload.useful_life_months, residual_rate=payload.residual_rate,
        depreciation_method="straight_line", depreciation_account_code=payload.depreciation_account_code,
        expense_account_code=payload.expense_account_code, status="active",
    )
    db.add(row)
    db.flush()
    write_operation_log(db, user=context.user, action="create", resource="fin_asset", target_id=row.id)
    return row


def run_asset_depreciation(db: Session, asset_id: str, period: str, context: UserContext) -> FinAssetDepreciation:
    asset = db.scalar(select(FinAsset).where(FinAsset.id == asset_id, FinAsset.org_id == context.org_id).with_for_update())
    if asset is None:
        raise AppError("固定资产不存在", code=404)
    if asset.status != "active":
        raise AppError("只有在用资产可以计提折旧", code=409)
    start_date, _ = _period_dates(period)
    if asset.purchase_date and start_date < asset.purchase_date.replace(day=1):
        raise AppError("不能在资产购置月份之前计提折旧", code=400)
    assert_fiscal_period_open(db, context.org_id, start_date)
    existing = db.scalar(select(FinAssetDepreciation).where(FinAssetDepreciation.asset_id == asset.id, FinAssetDepreciation.period == period))
    if existing:
        return existing
    residual_value = _money(asset.original_value * asset.residual_rate)
    depreciable = _money(asset.original_value - residual_value)
    remaining = _money(depreciable - asset.accumulated_depreciation)
    if remaining <= 0:
        raise AppError("固定资产已足额计提折旧", code=409)
    amount = min(_money(depreciable / Decimal(asset.useful_life_months)), remaining)
    from app.services.finance_service import _new_finance_doc_no
    voucher = FinVoucher(
        org_id=context.org_id, voucher_no=_new_finance_doc_no("DP", context), voucher_date=start_date,
        period=period, source_type="asset_depreciation", source_id=asset.id, status="draft",
        total_debit=amount, total_credit=amount,
    )
    account_rows = db.scalars(select(FinAccount).where(FinAccount.org_id == context.org_id, FinAccount.code.in_({asset.expense_account_code, asset.depreciation_account_code}))).all()
    account_map = {row.code: row for row in account_rows}
    voucher.entries = [
        FinVoucherEntry(line_no=1, account_id=account_map[asset.expense_account_code].id, account_code=asset.expense_account_code, account_name=account_map[asset.expense_account_code].name, summary=f"{period} {asset.asset_name} 折旧", debit_amount=amount, credit_amount=0, dimensions_json={}),
        FinVoucherEntry(line_no=2, account_id=account_map[asset.depreciation_account_code].id, account_code=asset.depreciation_account_code, account_name=account_map[asset.depreciation_account_code].name, summary=f"{period} {asset.asset_name} 折旧", debit_amount=0, credit_amount=amount, dimensions_json={}),
    ]
    db.add(voucher)
    db.flush()
    post_voucher(db, voucher.id, context)
    row = FinAssetDepreciation(org_id=context.org_id, asset_id=asset.id, period=period, amount=amount, voucher_id=voucher.id, status="posted")
    db.add(row)
    asset.accumulated_depreciation = _money(asset.accumulated_depreciation + amount)
    asset.last_depreciation_period = period
    db.flush()
    write_operation_log(db, user=context.user, action="depreciate", resource="fin_asset", target_id=asset.id, detail={"period": period, "amount": str(amount), "voucher_id": voucher.id})
    return row
