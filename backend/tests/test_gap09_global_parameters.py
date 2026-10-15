"""GAP-09: 成本方法 / 超额领料 / 检验必填 三个全局参数生效."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.core.exceptions import AppError
from app.models.configuration import CfgGlobalParameter
from app.models.inventory import InvStock, InvStockTransaction
from app.models.master_data import MdMaterial
from app.models.production import MfgWorkOrder, MfgWorkOrderMaterial
from app.models.quality import QaInspection
from app.services.inventory_service import complete_purchase_receipt
from app.services.production_service import issue_material
from app.services.purchase_service import create_receipt_from_order
from tests.gap_helpers import approved_purchase_order, receive


def _param(db, key, value):
    db.add(CfgGlobalParameter(org_id="org-test", parameter_key=key, parameter_value=value))
    db.commit()


def test_standard_cost_method(db, ctx, md):
    _param(db, "inventory.costing_method", "standard")
    receive(db, ctx, md, "10", "5")
    stock = db.scalar(select(InvStock).where(InvStock.material_id == md.mat.id))
    assert stock.average_cost == Decimal("8")  # material standard_cost


def _work_order(db, md, required="5"):
    product = MdMaterial(org_id="org-test", code="FG1", name="成品")
    db.add(product); db.flush()
    wo = MfgWorkOrder(org_id="org-test", doc_no="WO-1", material_id=product.id, warehouse_id=md.wh.id, bom_id="bom", plan_date=date.today(), quantity=Decimal("1"), status="released")
    db.add(wo); db.flush()
    db.add(MfgWorkOrderMaterial(work_order_id=wo.id, material_id=md.mat.id, required_quantity=Decimal(required)))
    db.commit()
    return wo


def test_over_issue_blocked_by_default(db, ctx, md):
    receive(db, ctx, md, "10", "5")
    wo = _work_order(db, md)
    with pytest.raises(AppError) as exc:
        issue_material(db, wo.id, [SimpleNamespace(material_id=md.mat.id, quantity=Decimal("6"))], ctx)
    assert "超过 BOM 计划数量" in exc.value.msg


def test_over_issue_allowed_by_parameter(db, ctx, md):
    _param(db, "mfg.allow_over_issue", "true")
    receive(db, ctx, md, "10", "5")
    wo = _work_order(db, md)
    issue = issue_material(db, wo.id, [SimpleNamespace(material_id=md.mat.id, quantity=Decimal("6"))], ctx)
    assert issue.items[0].unit_cost == Decimal("5")  # moving average cost


def test_inspection_required_blocks_receipt(db, ctx, md):
    _param(db, "qa.inspection_required", "true")
    order = approved_purchase_order(db, ctx, md)
    receipt = create_receipt_from_order(db, order.id, ctx)
    with pytest.raises(AppError) as exc:
        complete_purchase_receipt(db, receipt.id, ctx)
    assert "来料检验" in exc.value.msg
    db.rollback()
    db.add(QaInspection(org_id="org-test", inspection_type="incoming", source_type="purchase_receipt", source_id=receipt.id, status="submitted", result="failed", results_json=[]))
    db.commit()
    with pytest.raises(AppError):
        complete_purchase_receipt(db, receipt.id, ctx)
    db.rollback()
    db.add(QaInspection(org_id="org-test", inspection_type="incoming", source_type="purchase_receipt", source_id=receipt.id, status="submitted", result="passed", results_json=[]))
    db.commit()
    assert complete_purchase_receipt(db, receipt.id, ctx).status == "completed"


def test_inspection_not_required_by_default(db, ctx, md):
    _, receipt = receive(db, ctx, md)
    assert receipt.status == "completed"
