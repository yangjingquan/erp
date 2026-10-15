"""GAP-10: 费用报销、采购申请提交时发起审批流，审批结果回写单据."""
from datetime import date
from decimal import Decimal

import pytest

from app.api import finance as finance_api
from app.api import purchase as purchase_api
from app.core.exceptions import AppError
from app.models.business_extensions import PurchaseRequest
from app.models.finance import FinExpense
from app.models.workflow import WfDefinition, WfNode
from app.schemas.purchase import PurchaseRequestCreate
from app.services.business_extension_service import create_request
from app.services.workflow_service import approve_task, list_pending_tasks, reject_task


def _definition(db, business_type):
    d = WfDefinition(org_id="org-test", business_type=business_type, name="测试流程", status="active")
    d.nodes = [WfNode(node_key="n1", node_name="主管审批", sort_order=1, approver_type="role")]
    db.add(d); db.commit()


def _task_id(db, ctx, business_id):
    tasks = [t for t in list_pending_tasks(db, ctx) if t.get("business_id") == business_id]
    assert tasks, "workflow task should appear in 我的待办"
    return tasks[0].get("task_id") or tasks[0].get("id")


def test_expense_without_workflow_keeps_behavior(db, ctx):
    data = finance_api.expense({"amount": "100", "expense_type": "差旅"}, ctx, db)
    assert data.body if hasattr(data, "body") else data
    row = db.query(FinExpense).one()
    assert row.status == "draft"
    finance_api.approve_expense_api(row.id, ctx, db)
    assert db.get(FinExpense, row.id).status == "approved"


def test_expense_workflow_approve_and_reject(db, ctx):
    _definition(db, "expense")
    finance_api.expense({"amount": "100", "expense_type": "差旅"}, ctx, db)
    finance_api.expense({"amount": "50", "expense_type": "招待"}, ctx, db)
    first, second = sorted(db.query(FinExpense).all(), key=lambda r: r.amount, reverse=True)
    with pytest.raises(AppError) as exc:
        finance_api.approve_expense_api(first.id, ctx, db)
    assert "审批流" in exc.value.msg
    approve_task(db, _task_id(db, ctx, first.id), ctx); db.commit()
    reject_task(db, _task_id(db, ctx, second.id), ctx); db.commit()
    assert db.get(FinExpense, first.id).status == "approved"
    assert db.get(FinExpense, second.id).status == "rejected"


def test_purchase_request_workflow(db, ctx, md):
    _definition(db, "purchase_request")
    req = create_request(db, PurchaseRequestCreate(request_date=date.today(), supplier_id=md.sup.id, items=[{"material_id": md.mat.id, "quantity": "2"}]), ctx)
    purchase_api.request_action(req.id, "submit", ctx, db)
    with pytest.raises(AppError):
        purchase_api.request_action(req.id, "approve", ctx, db)
    approve_task(db, _task_id(db, ctx, req.id), ctx); db.commit()
    assert db.get(PurchaseRequest, req.id).status == "approved"


def test_lists_flag_in_workflow(db, ctx, md):
    from app.services.business_extension_service import list_requests
    from app.services.finance_service import list_expenses
    _definition(db, "expense"); _definition(db, "purchase_request")
    finance_api.expense({"amount": "10", "expense_type": "差旅"}, ctx, db)
    req = create_request(db, PurchaseRequestCreate(request_date=date.today(), supplier_id=md.sup.id, items=[{"material_id": md.mat.id, "quantity": "1"}]), ctx)
    purchase_api.request_action(req.id, "submit", ctx, db)
    assert list_expenses(db, ctx)[0]["in_workflow"] is True
    assert list_requests(db, ctx)[0]["in_workflow"] is True
