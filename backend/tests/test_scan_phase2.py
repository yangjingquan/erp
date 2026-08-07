from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.exceptions import AppError
from app.models.configuration import CfgGlobalParameter
from app.models.inventory import InvStockTransaction
from app.models.inventory_advanced import InvWarehouseAccess
from app.models.master_data import MdMaterial, MdWarehouse
from app.models.purchase import PurchaseReceipt, PurchaseReceiptItem
from app.models.system import SysUser
from app.schemas.inventory_advanced import BatchCreate, LocationCreate
from app.schemas.inventory_advanced import ScanProcessCreate
from app.services import inventory_advanced_service as scan_service
from app.services.auth_service import UserContext


def _context(session) -> UserContext:
    return UserContext(
        user=session.get(SysUser, "user-1"),
        permissions={"inventory:manage"},
        warehouse_ids={"warehouse-1"},
    )


def _seed_receipt(session) -> None:
    session.add_all(
        [
            MdWarehouse(id="warehouse-1", org_id="org-1", code="WH-1", name="Main"),
            MdWarehouse(id="warehouse-2", org_id="org-1", code="WH-2", name="Other"),
            MdMaterial(id="material-1", org_id="org-1", code="MAT-1", name="Material one"),
            InvWarehouseAccess(
                org_id="org-1", warehouse_id="warehouse-1", user_id="user-1", access_level="manage"
            ),
            PurchaseReceipt(
                id="receipt-1", org_id="org-1", doc_no="PR-1", order_id="order-1", supplier_id="supplier-1",
                warehouse_id="warehouse-1", status="draft", receipt_date=date.today(),
            ),
        ]
    )
    session.flush()
    session.add(PurchaseReceiptItem(receipt_id="receipt-1", material_id="material-1", quantity=Decimal("2"), unit_price=Decimal("10")))
    session.commit()


def _scan_payload(session, context) -> dict:
    location = scan_service.create_location(
        session, "warehouse-1", None, LocationCreate(code="A-01", name="A-01"), context
    )
    batch = scan_service.create_batch(
        session, "material-1", BatchCreate(batch_no="LOT-1", expiry_date=date.today() + timedelta(days=30)), context
    )
    session.commit()
    return {
        "warehouse_id": "warehouse-1",
        "location_id": location.id,
        "batch_id": batch.id,
        "material_id": "material-1",
        "quantity": "2",
        "unit_cost": "10",
    }


def test_same_scan_id_returns_original_result_without_duplicate_stock_transaction(client_and_session):
    """Removing persisted scan-id lookup would create a second FIFO/ledger transaction."""
    _, session = client_and_session
    _seed_receipt(session)
    context = _context(session)
    payload = _scan_payload(session, context)

    token = scan_service.create_scan_token(session, context)
    first = scan_service.process_scan(session, token, "scan-1", "receive", "receipt-1", payload)
    second = scan_service.process_scan(session, token, "scan-1", "receive", "receipt-1", payload)

    assert first == second
    assert session.scalars(
        select(InvStockTransaction).where(
            InvStockTransaction.source_type == "scan", InvStockTransaction.source_id == "scan-1"
        )
    ).all().__len__() == 1


def test_scan_rejects_expired_token_wrong_warehouse_and_unknown_action(client_and_session):
    """Removing token binding or action validation would admit an unauthorized stock movement."""
    _, session = client_and_session
    _seed_receipt(session)
    context = _context(session)
    payload = _scan_payload(session, context)

    token = scan_service.create_scan_token(session, context)
    wrong_warehouse_payload = {**payload, "warehouse_id": "warehouse-2"}
    with pytest.raises(AppError) as warehouse_error:
        scan_service.process_scan(session, token, "scan-wrong-warehouse", "receive", "receipt-1", wrong_warehouse_payload)
    with pytest.raises(AppError) as action_error:
        scan_service.process_scan(session, token, "scan-unknown", "adjust", "receipt-1", payload)

    session.add(CfgGlobalParameter(org_id="org-1", parameter_key="scan.token.ttl", parameter_value="0"))
    session.commit()
    expired_token = scan_service.create_scan_token(session, context)
    with pytest.raises(AppError) as expired_error:
        scan_service.process_scan(session, expired_token, "scan-expired", "receive", "receipt-1", payload)

    assert warehouse_error.value.code == 403
    assert action_error.value.code == 400
    assert expired_error.value.code == 401


def test_receive_scan_validates_document_and_marks_completed_document_unavailable(client_and_session):
    """Removing document status and line-quantity checks would allow duplicate receipt completion."""
    _, session = client_and_session
    _seed_receipt(session)
    context = _context(session)
    payload = _scan_payload(session, context)
    token = scan_service.create_scan_token(session, context)

    result = scan_service.process_scan(session, token, "scan-complete", "receive", "receipt-1", payload)
    session.commit()

    assert result["document_status"] == "completed"
    assert session.get(PurchaseReceipt, "receipt-1").status == "completed"
    with pytest.raises(AppError) as error:
        scan_service.process_scan(session, token, "scan-later", "receive", "receipt-1", payload)
    assert error.value.code == 400


def test_list_scan_tasks_returns_scoped_open_receipts(client_and_session):
    """Dropping warehouse/document filtering would expose closed or unauthorized scanner work."""
    _, session = client_and_session
    _seed_receipt(session)

    tasks = scan_service.list_scan_tasks(session, _context(session))

    assert {task["action"] for task in tasks} == {"receive", "count"}
    assert next(task for task in tasks if task["action"] == "receive") == {
        "action": "receive", "document_id": "receipt-1", "document_no": "PR-1", "warehouse_id": "warehouse-1", "status": "draft"
    }


def test_scan_retry_returns_persisted_original_response_even_if_request_changes(client_and_session):
    _, session = client_and_session
    _seed_receipt(session)
    context = _context(session)
    payload = _scan_payload(session, context)
    token = scan_service.create_scan_token(session, context)

    first = scan_service.process_scan(session, token, "scan-original", "receive", "receipt-1", {**payload, "unit_cost": "999"})
    retry = scan_service.process_scan(session, token, "scan-original", "receive", "another-receipt", {**payload, "quantity": "1", "unit_cost": "1"})

    assert retry == first
    assert first["unit_cost"] == "10"


def test_scan_schema_restricts_actions_and_requires_operation_fields():
    with pytest.raises(ValueError):
        ScanProcessCreate(
            token="token", scan_id="scan", action="adjust", document_id="doc", warehouse_id="wh"
        )
    with pytest.raises(ValueError):
        ScanProcessCreate(
            token="token", scan_id="scan", action="receive", document_id="doc", warehouse_id="wh", material_id="m", quantity=1
        )
