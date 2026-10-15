"""GAP-03: 报价修改/删除、采购退货修改、商机输单."""
from datetime import date
from decimal import Decimal

import pytest

from app.core.exceptions import AppError
from app.models.business_extensions import SalesQuote
from app.models.crm import CrmOpportunity
from app.schemas.sales import SalesOrderItemCreate, SalesQuoteCreate
from app.services.business_extension_service import create_quote, delete_quote, list_quotes, transition_quote, update_quote
from app.services.crm_service import transition_opportunity


def _quote(md, qty="2", price="10"):
    return SalesQuoteCreate(customer_id=md.cus.id, quote_date=date.today(), items=[SalesOrderItemCreate(material_id=md.mat.id, quantity=Decimal(qty), unit_price=Decimal(price))])


def test_update_and_delete_draft_quote(db, ctx, md):
    quote = create_quote(db, _quote(md), ctx)
    updated = update_quote(db, quote.id, _quote(md, "3", "10"), ctx)
    assert updated.total_amount == Decimal("30.00")
    delete_quote(db, quote.id, ctx)
    assert list_quotes(db, ctx) == []


def test_non_draft_quote_locked(db, ctx, md):
    quote = create_quote(db, _quote(md), ctx)
    transition_quote(db, quote.id, "submitted", ctx)
    with pytest.raises(AppError):
        update_quote(db, quote.id, _quote(md, "3"), ctx)
    with pytest.raises(AppError):
        delete_quote(db, quote.id, ctx)


def test_purchase_return_update(db, ctx, md):
    from app.schemas.purchase import PurchaseReturnCreate, PurchaseReturnUpdate
    from app.services.business_extension_service import create_purchase_return, update_purchase_return
    fields = PurchaseReturnCreate.model_fields
    item_type = fields["items"].annotation.__args__[0]
    payload = PurchaseReturnCreate(supplier_id=md.sup.id, warehouse_id=md.wh.id, return_date=date.today(), items=[item_type(material_id=md.mat.id, quantity=Decimal("1"), unit_price=Decimal("5"))])
    row = create_purchase_return(db, payload, ctx)
    payload2 = PurchaseReturnUpdate(**{**payload.model_dump(), "items": [{"material_id": md.mat.id, "quantity": Decimal("2"), "unit_price": Decimal("5")}]})
    row = update_purchase_return(db, row.id, payload2, ctx)
    assert row.total_amount == Decimal("10.00")


def _opp(db):
    row = CrmOpportunity(org_id="org-test", opportunity_no="OP-1", name="测试商机", stage="proposal")
    db.add(row); db.commit()
    return row


def test_opportunity_lost_requires_reason(db, ctx):
    opp = _opp(db)
    with pytest.raises(AppError) as exc:
        transition_opportunity(db, opp.id, "lost", ctx)
    assert "原因" in exc.value.msg
    row = transition_opportunity(db, opp.id, "lost", ctx, loss_reason="价格过高")
    assert row.stage == "lost" and row.loss_reason == "价格过高"
    with pytest.raises(AppError):
        transition_opportunity(db, opp.id, "proposal", ctx)
