"""GAP-07: 扫码收货生成应付和凭证，并回写订单."""
from decimal import Decimal

from sqlalchemy import select

from app.models.finance import PurchasePayable
from app.models.inventory_advanced import InvLocation
from app.models.purchase import PurchaseOrder
from app.services.inventory_advanced_service import create_scan_token, process_scan
from app.services.purchase_service import create_receipt_from_order
from tests.gap_helpers import approved_purchase_order, voucher_lines


def test_scan_receive_creates_payable(db, ctx, md):
    loc = InvLocation(org_id="org-test", warehouse_id=md.wh.id, code="L1", name="库位1", status="active")
    db.add(loc); db.commit()
    order = approved_purchase_order(db, ctx, md, "3", "7")
    receipt = create_receipt_from_order(db, order.id, ctx)
    ctx.warehouse_ids = {md.wh.id}
    token = create_scan_token(db, ctx)
    result = process_scan(db, token, "scan-1", "receive", receipt.id, {"warehouse_id": md.wh.id, "location_id": loc.id, "material_id": md.mat.id, "quantity": "3"})
    payable = db.scalar(select(PurchasePayable).where(PurchasePayable.source_id == receipt.id))
    assert payable is not None and payable.total_amount == Decimal("21.00")
    assert result["payable_id"] == payable.id
    assert voucher_lines(db, "purchase_receipt", receipt.id)["2202"][1] == Decimal("21")
    assert db.get(PurchaseOrder, order.id).status == "completed"
