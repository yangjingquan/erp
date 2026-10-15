"""GAP-02: 反审核 & 列表驳回."""
from datetime import date
from decimal import Decimal

import pytest

from app.core.exceptions import AppError
from app.schemas.purchase import PurchaseOrderCreate, PurchaseOrderItemCreate
from app.services import document_service
from app.services.purchase_service import (
    create_purchase_order, create_receipt_from_order, reject_purchase_order_manual,
    submit_purchase_order, unapprove_purchase_order, update_purchase_order,
)
from app.services.sales_service import reject_sales_order_manual, unapprove_sales_order
from tests.gap_helpers import approved_purchase_order, approved_sales_order


def _payload(md, qty="3"):
    return PurchaseOrderCreate(supplier_id=md.sup.id, order_date=date.today(), items=[
        PurchaseOrderItemCreate(material_id=md.mat.id, quantity=Decimal(qty), unit_price=Decimal("2"), warehouse_id=md.wh.id)])


def test_purchase_unapprove_without_downstream(db, ctx, md):
    order = approved_purchase_order(db, ctx, md)
    assert unapprove_purchase_order(db, order.id, ctx).status == "draft"


def test_purchase_unapprove_blocked_by_receipt(db, ctx, md):
    order = approved_purchase_order(db, ctx, md)
    create_receipt_from_order(db, order.id, ctx)
    with pytest.raises(AppError) as exc:
        unapprove_purchase_order(db, order.id, ctx)
    assert "不能反审核" in exc.value.msg


def test_purchase_reject_then_edit_and_resubmit(db, ctx, md):
    order = create_purchase_order(db, _payload(md), ctx)
    submit_purchase_order(db, order.id, ctx)
    assert reject_purchase_order_manual(db, order.id, ctx).status == "rejected"
    update_purchase_order(db, order.id, _payload(md, "5"), ctx)
    assert submit_purchase_order(db, order.id, ctx).status == "submitted"


def test_reject_requires_submitted(db, ctx, md):
    order = create_purchase_order(db, _payload(md), ctx)
    with pytest.raises(AppError):
        reject_purchase_order_manual(db, order.id, ctx)


def test_sales_unapprove_and_reject(db, ctx, md):
    order = approved_sales_order(db, ctx, md)
    assert unapprove_sales_order(db, order.id, ctx).status == "draft"
    from app.services.sales_service import submit_sales_order
    submit_sales_order(db, order.id, ctx)
    assert reject_sales_order_manual(db, order.id, ctx).status == "rejected"


def test_document_actions_expose_reject_unapprove():
    cfg = document_service.ACTION_CONFIG
    for t in ("sales_order", "purchase_order"):
        assert "reject" in [a[0] for a in cfg[t]["submitted"]]
        assert "unapprove" in [a[0] for a in cfg[t]["approved"]]
        assert cfg[t]["rejected"][0][0] == "submit"
