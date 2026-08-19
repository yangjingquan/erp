from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import func, inspect as sa_inspect, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.time import local_now
from app.models.collaboration import (
    BizAttachment,
    BizComment,
    BizDocument,
    BizDocumentRelation,
    SysNotification,
)
from app.models.finance import (
    FinExpense,
    FinPayment,
    FinReceipt,
    FinVoucher,
    PurchasePayable,
    SalesReceivable,
)
from app.models.inventory import InvCount, InvStockTransaction, InvTransfer
from app.models.logging import SysOperationLog
from app.models.master_data import MdCustomer, MdMaterial, MdSupplier, MdWarehouse
from app.models.production import MfgWorkOrder
from app.models.purchase import PurchaseOrder, PurchaseReceipt, PurchaseReturn
from app.models.quality import QaInspection
from app.models.sales import SalesDelivery, SalesOrder, SalesReturn
from app.models.system import SysDepartment, SysUser
from app.models.phase2_extensions import EamAsset, EamWorkOrder, PlmChangeRequest, Project, SrmRfq, SvcCase, SvcVisit, TaxInvoice
from app.models.workflow import WfActionLog, WfInstance
from app.services.auth_service import UserContext, apply_data_scope, data_scope_condition


ATTACHMENT_ROOT = Path(__file__).resolve().parents[2] / "var" / "attachments"
MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024

TYPE_CONFIG: dict[str, dict[str, Any]] = {
    "sales_order": {"model": SalesOrder, "label": "销售订单", "doc": "doc_no", "date": "order_date", "amount": "total_amount", "party": ("customer", "customer_id")},
    "sales_delivery": {"model": SalesDelivery, "label": "销售出库", "doc": "doc_no", "date": "delivery_date", "amount": "total_amount", "party": ("customer", "customer_id")},
    "sales_return": {"model": SalesReturn, "label": "销售退货", "doc": "doc_no", "date": "return_date", "amount": "total_amount", "party": ("customer", "customer_id")},
    "sales_receivable": {"model": SalesReceivable, "label": "应收账款", "doc": "doc_no", "date": "due_date", "amount": "total_amount", "party": ("customer", "customer_id")},
    "fin_receipt": {"model": FinReceipt, "label": "收款单", "doc": "doc_no", "date": "receipt_date", "amount": "amount", "party": ("customer", "customer_id")},
    "purchase_order": {"model": PurchaseOrder, "label": "采购订单", "doc": "doc_no", "date": "order_date", "amount": "total_amount", "party": ("supplier", "supplier_id")},
    "purchase_receipt": {"model": PurchaseReceipt, "label": "采购入库", "doc": "doc_no", "date": "receipt_date", "amount": "total_amount", "party": ("supplier", "supplier_id")},
    "purchase_return": {"model": PurchaseReturn, "label": "采购退货", "doc": "doc_no", "date": "return_date", "amount": "total_amount", "party": ("supplier", "supplier_id")},
    "purchase_payable": {"model": PurchasePayable, "label": "应付账款", "doc": "doc_no", "date": "due_date", "amount": "total_amount", "party": ("supplier", "supplier_id")},
    "fin_payment": {"model": FinPayment, "label": "付款单", "doc": "doc_no", "date": "payment_date", "amount": "amount", "party": ("supplier", "supplier_id")},
    "fin_expense": {"model": FinExpense, "label": "费用报销", "doc": "doc_no", "date": "expense_date", "amount": "amount"},
    "fin_voucher": {"model": FinVoucher, "label": "会计凭证", "doc": "voucher_no", "date": "voucher_date", "amount": "total_debit"},
    "mfg_work_order": {"model": MfgWorkOrder, "label": "生产工单", "doc": "doc_no", "date": "plan_date", "amount": None},
    "qa_inspection": {"model": QaInspection, "label": "质量检验", "doc": None, "date": None, "amount": None},
    "inv_transfer": {"model": InvTransfer, "label": "库存调拨", "doc": "doc_no", "date": "transfer_date", "amount": None},
    "inv_count": {"model": InvCount, "label": "库存盘点", "doc": "doc_no", "date": "count_date", "amount": None},
    "inventory_transaction": {"model": InvStockTransaction, "label": "库存事务", "doc": None, "date": "transaction_date", "amount": "amount", "fixed_status": "posted"},
    "plm_change": {"model": PlmChangeRequest, "label": "工程变更", "doc": "change_no", "date": "due_date", "amount": None},
    "srm_rfq": {"model": SrmRfq, "label": "供应商询价", "doc": "rfq_no", "date": "due_date", "amount": "quote_amount", "party": ("supplier", "supplier_id")},
    "project": {"model": Project, "label": "项目", "doc": "project_code", "date": "start_date", "amount": "budget_amount", "party": ("customer", "customer_id")},
    "eam_asset": {"model": EamAsset, "label": "资产", "doc": "asset_code", "date": None, "amount": None},
    "eam_work_order": {"model": EamWorkOrder, "label": "资产工单", "doc": "work_order_no", "date": "due_date", "amount": None},
    "svc_case": {"model": SvcCase, "label": "服务工单", "doc": "case_no", "date": "due_date", "amount": None, "party": ("customer", "customer_id")},
    "svc_visit": {"model": SvcVisit, "label": "服务回访", "doc": None, "date": "scheduled_at", "amount": None},
    "tax_invoice": {"model": TaxInvoice, "label": "税务发票", "doc": "invoice_no", "date": None, "amount": "amount"},
}

STATUS_LABELS = {
    "draft": "草稿", "submitted": "待审核", "approved": "已审核", "completed": "已完成",
    "open": "待核销", "partial": "部分核销", "settled": "已结清", "confirmed": "已确认",
    "posted": "已过账", "rejected": "已驳回", "cancelled": "已取消", "closed": "已关闭", "active": "在用", "maintenance": "保养中", "retired": "已报废", "assigned": "已派工", "resolved": "已解决", "reopened": "已重开",
    "released": "已下达", "in_progress": "进行中", "reversed": "已冲销",
}

ACTION_CONFIG = {
    "sales_order": {
        "draft": [("submit", "提交审核", "primary")],
        "submitted": [("approve", "审核通过", "success")],
        "approved": [("create_delivery", "生成出库单", "warning")],
    },
    "sales_delivery": {"draft": [("complete", "完成出库", "success")]},
    "purchase_order": {
        "draft": [("submit", "提交审核", "primary")],
        "submitted": [("approve", "审核通过", "success")],
        "approved": [("create_receipt", "生成入库单", "warning")],
    },
    "purchase_receipt": {"draft": [("complete", "完成入库", "success")]},
    "mfg_work_order": {
        "draft": [("release", "下达工单", "primary")],
        "released": [("complete", "完工结转", "success"), ("cancel", "取消", "danger")],
        "in_progress": [("complete", "完工结转", "success"), ("cancel", "取消", "danger")],
    },
    "inv_transfer": {"draft": [("approve", "审核", "primary")], "approved": [("complete", "完成调拨", "success")]},
    "inv_count": {"draft": [("complete", "完成盘点", "success")]},
    "fin_voucher": {"draft": [("post", "记账", "success")], "posted": [("reverse", "冲销", "danger")]},
}

TYPE_MODULE = {
    "sales_order": "sales", "sales_delivery": "sales", "sales_return": "sales",
    "sales_receivable": "finance", "fin_receipt": "finance", "fin_expense": "finance",
    "fin_voucher": "finance", "fin_payment": "finance", "purchase_payable": "finance",
    "purchase_order": "purchase", "purchase_receipt": "purchase", "purchase_return": "purchase",
    "mfg_work_order": "production", "qa_inspection": "quality",
    "inv_transfer": "inventory", "inv_count": "inventory", "inventory_transaction": "inventory",
    "plm_change": "production", "srm_rfq": "purchase", "project": "cost", "eam_asset": "production", "eam_work_order": "production", "svc_case": "crm", "svc_visit": "crm", "tax_invoice": "finance",
}


def _now() -> datetime:
    return local_now()


def _can_access_type(context: UserContext, business_type: str) -> bool:
    if context.user.is_superuser:
        return True
    if "*" in context.permissions:
        return True
    module = TYPE_MODULE.get(business_type)
    return bool(module and any(permission.startswith(f"{module}:") for permission in context.permissions))


def _assert_type_access(context: UserContext, business_type: str) -> None:
    if not _can_access_type(context, business_type):
        raise AppError("无权访问该业务单据", code=403)


def _can_manage_type(context: UserContext, business_type: str) -> bool:
    if context.user.is_superuser:
        return True
    module = TYPE_MODULE.get(business_type)
    return "*" in context.permissions or bool(module and f"{module}:manage" in context.permissions)


def _assert_command_access(context: UserContext, business_type: str) -> None:
    _assert_type_access(context, business_type)
    if not _can_manage_type(context, business_type):
        raise AppError("无权执行该业务单据操作", code=403)


def _plain(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return value


def _model_dict(row: Any) -> dict[str, Any]:
    result = {attribute.key: _plain(getattr(row, attribute.key)) for attribute in sa_inspect(row).mapper.column_attrs}
    for relationship in sa_inspect(row).mapper.relationships:
        if relationship.key not in {"items", "entries", "reconciles"}:
            continue
        value = getattr(row, relationship.key)
        if relationship.uselist:
            result[relationship.key] = [
                {attribute.key: _plain(getattr(item, attribute.key)) for attribute in sa_inspect(item).mapper.column_attrs}
                for item in value
            ]
    return result


def _party_name(db: Session, party_type: str | None, party_id: str | None, org_id: str) -> str | None:
    if not party_type or not party_id:
        return None
    model = MdCustomer if party_type == "customer" else MdSupplier
    row = db.scalar(select(model).where(model.id == party_id, model.org_id == org_id))
    return f"{row.code} · {row.name}" if row is not None else None


def _source_reference(business_type: str, row: Any) -> tuple[str | None, str | None]:
    if business_type == "sales_delivery":
        return "sales_order", row.order_id
    if business_type == "sales_return":
        return "sales_delivery", row.source_delivery_id
    if business_type == "purchase_receipt":
        return "purchase_order", row.order_id
    if business_type == "purchase_return":
        return "purchase_receipt", row.source_receipt_id
    if business_type == "fin_voucher" and row.source_type:
        return {"receipt": "fin_receipt", "payment": "fin_payment", "expense": "fin_expense"}.get(row.source_type, row.source_type), row.source_id
    return getattr(row, "source_type", None), getattr(row, "source_id", None)


def _snapshot(db: Session, business_type: str, row: Any) -> dict[str, Any]:
    config = TYPE_CONFIG[business_type]
    party_type, party_attr = config.get("party", (None, None))
    party_id = getattr(row, party_attr, None) if party_attr else None
    row_date = getattr(row, config["date"], None) if config.get("date") else None
    if isinstance(row_date, datetime):
        row_date = row_date.date()
    amount = getattr(row, config["amount"], 0) if config.get("amount") else 0
    doc_no = getattr(row, config["doc"], None) if config.get("doc") else None
    doc_no = str(doc_no or row.id)
    source_type, source_id = _source_reference(business_type, row)
    status = str(config.get("fixed_status") or getattr(row, "status", "active"))
    org_id = str(row.org_id)
    owner_id = getattr(row, "owner_id", None) or getattr(row, "created_by", None)
    department_id = getattr(row, "department_id", None)
    if not department_id and owner_id:
        department_id = db.scalar(select(SysUser.department_id).where(
            SysUser.id == owner_id,
            SysUser.org_id == org_id,
            SysUser.is_deleted.is_(False),
        ))
    return {
        "org_id": org_id,
        "business_type": business_type,
        "business_id": str(row.id),
        "doc_no": doc_no,
        "title": f"{config['label']} {doc_no}",
        "status": status,
        "document_date": row_date,
        "owner_id": owner_id,
        "department_id": department_id,
        "party_type": party_type,
        "party_id": party_id,
        "party_name": _party_name(db, party_type, party_id, org_id),
        "amount": Decimal(str(amount or 0)),
        "source_type": source_type,
        "source_id": source_id,
        "summary_json": _model_dict(row),
    }


def _sync_row(db: Session, business_type: str, row: Any) -> BizDocument:
    values = _snapshot(db, business_type, row)
    document = db.scalar(select(BizDocument).where(
        BizDocument.org_id == values["org_id"],
        BizDocument.business_type == business_type,
        BizDocument.business_id == values["business_id"],
    ))
    if document is None:
        document = BizDocument(**values)
        db.add(document)
    else:
        for key, value in values.items():
            setattr(document, key, value)
    db.flush()
    return document


def sync_documents(db: Session, context: UserContext, business_type: str | None = None) -> None:
    requested = [business_type] if business_type else list(TYPE_CONFIG)
    for type_name in requested:
        config = TYPE_CONFIG.get(type_name)
        if config is None:
            continue
        model = config["model"]
        statement = select(model).where(model.org_id == context.org_id)
        if hasattr(model, "is_deleted"):
            statement = statement.where(model.is_deleted.is_(False))
        for row in db.scalars(statement).unique().all():
            _sync_row(db, type_name, row)
    _sync_inferred_relations(db, context.org_id)
    db.commit()


def _relation_values(db: Session, org_id: str) -> list[tuple[str, str, str, str, str]]:
    values: list[tuple[str, str, str, str, str]] = []
    for row in db.scalars(select(SalesDelivery).where(SalesDelivery.org_id == org_id)).all():
        values.append(("sales_order", row.order_id, "sales_delivery", row.id, "fulfills"))
    for row in db.scalars(select(SalesReturn).where(SalesReturn.org_id == org_id, SalesReturn.source_delivery_id.is_not(None))).all():
        values.append(("sales_delivery", str(row.source_delivery_id), "sales_return", row.id, "returns"))
    for row in db.scalars(select(SalesReceivable).where(SalesReceivable.org_id == org_id)).all():
        values.append((row.source_type, row.source_id, "sales_receivable", row.id, "creates_receivable"))
    for receipt in db.scalars(select(FinReceipt).where(FinReceipt.org_id == org_id)).unique().all():
        for reconcile in receipt.reconciles:
            values.append(("sales_receivable", reconcile.receivable_id, "fin_receipt", receipt.id, "settled_by"))
    for row in db.scalars(select(PurchaseReceipt).where(PurchaseReceipt.org_id == org_id)).all():
        values.append(("purchase_order", row.order_id, "purchase_receipt", row.id, "receives"))
    for row in db.scalars(select(PurchaseReturn).where(PurchaseReturn.org_id == org_id, PurchaseReturn.source_receipt_id.is_not(None))).all():
        values.append(("purchase_receipt", str(row.source_receipt_id), "purchase_return", row.id, "returns"))
    for row in db.scalars(select(PurchasePayable).where(PurchasePayable.org_id == org_id)).all():
        values.append((row.source_type, row.source_id, "purchase_payable", row.id, "creates_payable"))
    for payment in db.scalars(select(FinPayment).where(FinPayment.org_id == org_id)).unique().all():
        for reconcile in payment.reconciles:
            values.append(("purchase_payable", reconcile.payable_id, "fin_payment", payment.id, "settled_by"))
    for row in db.scalars(select(FinVoucher).where(FinVoucher.org_id == org_id, FinVoucher.source_id.is_not(None))).all():
        source_type = {"receipt": "fin_receipt", "payment": "fin_payment", "expense": "fin_expense"}.get(str(row.source_type), str(row.source_type))
        values.append((source_type, str(row.source_id), "fin_voucher", row.id, "posts_to"))
    for row in db.scalars(select(InvStockTransaction).where(InvStockTransaction.org_id == org_id)).all():
        values.append((row.source_type, row.source_id, "inventory_transaction", row.id, "posts_inventory"))
    for row in db.scalars(select(QaInspection).where(QaInspection.org_id == org_id)).all():
        values.append((row.source_type, row.source_id, "qa_inspection", row.id, "inspected_by"))
    for row in db.scalars(select(EamWorkOrder).where(EamWorkOrder.org_id == org_id)).all():
        values.append(("eam_asset", row.asset_id, "eam_work_order", row.id, "has_work_order"))
    for row in db.scalars(select(SvcVisit).where(SvcVisit.org_id == org_id)).all():
        values.append(("svc_case", row.case_id, "svc_visit", row.id, "has_visit"))
    return [value for value in values if value[0] in TYPE_CONFIG and value[2] in TYPE_CONFIG]


def _sync_inferred_relations(db: Session, org_id: str) -> None:
    for from_type, from_id, to_type, to_id, relation_type in _relation_values(db, org_id):
        exists = db.scalar(select(BizDocumentRelation.id).where(
            BizDocumentRelation.org_id == org_id,
            BizDocumentRelation.from_type == from_type,
            BizDocumentRelation.from_id == from_id,
            BizDocumentRelation.to_type == to_type,
            BizDocumentRelation.to_id == to_id,
            BizDocumentRelation.relation_type == relation_type,
        ))
        if exists is None:
            db.add(BizDocumentRelation(
                org_id=org_id, from_type=from_type, from_id=from_id, to_type=to_type,
                to_id=to_id, relation_type=relation_type,
            ))
    db.flush()


def _available_actions(db: Session, row: BizDocument) -> list[tuple[str, str, str]]:
    actions = ACTION_CONFIG.get(row.business_type, {}).get(row.status, [])
    if row.business_type == "sales_order" and row.status == "approved":
        delivery_exists = db.scalar(select(SalesDelivery.id).where(
            SalesDelivery.org_id == row.org_id,
            SalesDelivery.order_id == row.business_id,
            SalesDelivery.status != "cancelled",
        ))
        if delivery_exists is not None:
            actions = [action for action in actions if action[0] != "create_delivery"]
    return actions


def _serialize_document(row: BizDocument, context: UserContext | None = None, db: Session | None = None) -> dict[str, Any]:
    actions = _available_actions(db, row) if db is not None else ACTION_CONFIG.get(row.business_type, {}).get(row.status, [])
    return {
        "id": row.id, "business_type": row.business_type, "business_id": row.business_id,
        "doc_no": row.doc_no, "title": row.title, "status": row.status,
        "status_label": STATUS_LABELS.get(row.status, row.status),
        "document_date": row.document_date.isoformat() if row.document_date else None,
        "owner_id": row.owner_id, "party_id": row.party_id,
        "party_name": row.party_name or row.party_id, "amount": str(row.amount),
        "updated_at": row.updated_at.isoformat(sep=" ", timespec="seconds"),
        "available_actions": [
            {"command": command, "label": label, "type": action_type}
            for command, label, action_type in actions
        ] if context is None or _can_manage_type(context, row.business_type) else [],
    }


def _display_payload(db: Session, document: BizDocument, source: Any) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    details = [
        {"label": "单据编号", "value": document.doc_no},
        {"label": "状态", "value": STATUS_LABELS.get(document.status, document.status)},
        {"label": "业务对象", "value": document.party_name or document.party_id or "-"},
        {"label": "单据日期", "value": document.document_date.isoformat() if document.document_date else "-"},
        {"label": "含税金额", "value": f"¥{document.amount}"},
    ]
    expected_date = getattr(source, "expected_date", None) or getattr(source, "due_date", None)
    if expected_date:
        details.append({"label": "预计/到期日期", "value": _plain(expected_date)})
    owner_id = getattr(source, "owner_id", None) or getattr(source, "created_by", None)
    owner = db.get(SysUser, owner_id) if owner_id else None
    if owner:
        details.append({"label": "责任人", "value": owner.display_name})
    department_id = getattr(source, "department_id", None)
    department = db.get(SysDepartment, department_id) if department_id else None
    if department:
        details.append({"label": "部门", "value": department.name})
    remark = getattr(source, "remark", None) or getattr(source, "description", None)
    if remark:
        details.append({"label": "备注", "value": str(remark)})
    details.append({"label": "更新时间", "value": document.updated_at.isoformat(sep=" ", timespec="seconds")})

    display_items: list[dict[str, Any]] = []
    raw_items = getattr(source, "items", None) or getattr(source, "entries", None) or []
    for index, item in enumerate(raw_items, start=1):
        material_id = getattr(item, "material_id", None)
        warehouse_id = getattr(item, "warehouse_id", None)
        material = db.get(MdMaterial, material_id) if material_id else None
        warehouse = db.get(MdWarehouse, warehouse_id) if warehouse_id else None
        if material_id:
            display_items.append({
                "行号": getattr(item, "line_no", index),
                "物料": f"{material.code} · {material.name}" if material else material_id,
                "仓库": f"{warehouse.code} · {warehouse.name}" if warehouse else (warehouse_id or "-"),
                "数量": _plain(getattr(item, "quantity", 0)),
                "已履约": _plain(getattr(item, "delivered_quantity", getattr(item, "received_quantity", 0))),
                "含税单价": _plain(getattr(item, "unit_price", 0)),
                "金额": _plain(getattr(item, "amount", 0)),
            })
        elif hasattr(item, "account_code"):
            display_items.append({
                "行号": getattr(item, "line_no", index),
                "科目": f"{item.account_code} · {item.account_name}",
                "摘要": item.summary or "-",
                "借方": _plain(item.debit_amount),
                "贷方": _plain(item.credit_amount),
            })
    return details, display_items


def list_documents(
    db: Session, context: UserContext, *, business_type: str | None, status: str | None,
    keyword: str | None, date_from: date | None, date_to: date | None,
    page: int, page_size: int, sort: str,
) -> dict[str, Any]:
    if business_type:
        _assert_type_access(context, business_type)
    sync_documents(db, context, business_type)
    base_filters = [BizDocument.org_id == context.org_id, BizDocument.is_deleted.is_(False)]
    scope_condition = data_scope_condition(
        BizDocument,
        context.user,
        context.data_scope_type,
        org_id=context.org_id,
    )
    if scope_condition is not True:
        base_filters.append(scope_condition)
    if business_type:
        base_filters.append(BizDocument.business_type == business_type)
    else:
        allowed_types = [type_name for type_name in TYPE_CONFIG if _can_access_type(context, type_name)]
        base_filters.append(BizDocument.business_type.in_(allowed_types))
    if keyword:
        pattern = f"%{keyword.strip()}%"
        base_filters.append(or_(BizDocument.doc_no.ilike(pattern), BizDocument.title.ilike(pattern), BizDocument.party_name.ilike(pattern)))
    if date_from:
        base_filters.append(BizDocument.document_date >= date_from)
    if date_to:
        base_filters.append(BizDocument.document_date <= date_to)
    filters = [*base_filters]
    if status:
        filters.append(BizDocument.status == status)
    sort_columns = {"document_date": BizDocument.document_date, "amount": BizDocument.amount, "doc_no": BizDocument.doc_no, "updated_at": BizDocument.updated_at}
    descending = sort.startswith("-")
    sort_column = sort_columns.get(sort.lstrip("-"), BizDocument.updated_at)
    order = sort_column.desc() if descending else sort_column.asc()
    total = db.scalar(select(func.count()).select_from(BizDocument).where(*filters)) or 0
    rows = db.scalars(select(BizDocument).where(*filters).order_by(order, BizDocument.id).offset((page - 1) * page_size).limit(page_size)).all()
    status_rows = db.execute(select(BizDocument.status, func.count(BizDocument.id), func.coalesce(func.sum(BizDocument.amount), 0)).where(*base_filters).group_by(BizDocument.status)).all()
    summary = {
        "total": sum(row[1] for row in status_rows),
        "amount": str(sum((row[2] for row in status_rows), Decimal("0"))),
        "statuses": {row[0]: {"count": row[1], "amount": str(row[2])} for row in status_rows},
    }
    return {"items": [_serialize_document(row, context, db) for row in rows], "total": total, "page": page, "page_size": page_size, "summary": summary}


def _get_source_row(db: Session, business_type: str, business_id: str, context: UserContext) -> Any:
    _assert_type_access(context, business_type)
    config = TYPE_CONFIG.get(business_type)
    if config is None:
        raise AppError("不支持的业务单据类型", code=400)
    model = config["model"]
    statement = apply_data_scope(select(model).where(model.id == business_id), model, context)
    row = db.scalar(statement)
    if row is None or getattr(row, "is_deleted", False):
        raise AppError("业务单据不存在", code=404)
    return row


def get_document_workspace(db: Session, context: UserContext, business_type: str, business_id: str) -> dict[str, Any]:
    source = _get_source_row(db, business_type, business_id, context)
    _sync_row(db, business_type, source)
    sync_documents(db, context)
    document = db.scalar(select(BizDocument).where(BizDocument.org_id == context.org_id, BizDocument.business_type == business_type, BizDocument.business_id == business_id))
    all_relations = db.scalars(select(BizDocumentRelation).where(
        BizDocumentRelation.org_id == context.org_id,
        BizDocumentRelation.is_deleted.is_(False),
    ).order_by(BizDocumentRelation.created_at, BizDocumentRelation.id)).all()
    root = (business_type, business_id)
    queue: list[tuple[tuple[str, str], int]] = [(root, 0)]
    visited = {root}
    used_edges: set[str] = set()
    relation_items: list[dict[str, Any]] = []
    graph_edges: list[dict[str, str]] = []
    while queue:
        current, depth = queue.pop(0)
        if depth >= 8:
            continue
        for relation in all_relations:
            from_key = (relation.from_type, relation.from_id)
            to_key = (relation.to_type, relation.to_id)
            if current not in {from_key, to_key}:
                continue
            if relation.id not in used_edges:
                graph_edges.append({
                    "id": relation.id, "from_type": relation.from_type, "from_id": relation.from_id,
                    "to_type": relation.to_type, "to_id": relation.to_id,
                    "relation_type": relation.relation_type,
                })
                used_edges.add(relation.id)
            other_key = to_key if current == from_key else from_key
            if other_key in visited:
                continue
            visited.add(other_key)
            queue.append((other_key, depth + 1))
            other = db.scalar(select(BizDocument).where(
                BizDocument.org_id == context.org_id,
                BizDocument.business_type == other_key[0],
                BizDocument.business_id == other_key[1],
            ))
            relation_items.append({
                "id": relation.id,
                "relation_type": relation.relation_type,
                "direction": "downstream" if current == from_key else "upstream",
                "depth": depth + 1,
                "document": _serialize_document(other, context, db) if other else {"business_type": other_key[0], "business_id": other_key[1], "doc_no": other_key[1]},
            })
    comments = db.scalars(select(BizComment).where(BizComment.org_id == context.org_id, BizComment.object_type == business_type, BizComment.object_id == business_id, BizComment.is_deleted.is_(False)).order_by(BizComment.created_at)).all()
    attachments = db.scalars(select(BizAttachment).where(BizAttachment.org_id == context.org_id, BizAttachment.object_type == business_type, BizAttachment.object_id == business_id, BizAttachment.is_deleted.is_(False)).order_by(BizAttachment.created_at.desc())).all()
    operation_logs = db.scalars(select(SysOperationLog).where(SysOperationLog.org_id == context.org_id, SysOperationLog.target_id == business_id).order_by(SysOperationLog.created_at)).all()
    workflow_instances = db.scalars(select(WfInstance).where(WfInstance.org_id == context.org_id, WfInstance.business_type == business_type, WfInstance.business_id == business_id).order_by(WfInstance.started_at)).all()
    workflow_ids = [item.id for item in workflow_instances]
    workflow_logs = db.scalars(select(WfActionLog).where(WfActionLog.instance_id.in_(workflow_ids)).order_by(WfActionLog.created_at)).all() if workflow_ids else []
    timeline = [{"type": "created", "label": "单据创建", "user_id": getattr(source, "created_by", None), "time": document.created_at.isoformat(timespec="seconds"), "comment": None}]
    timeline.extend({"type": "operation", "label": log.action, "user_id": log.user_id, "time": log.created_at.isoformat(timespec="seconds"), "comment": None} for log in operation_logs)
    timeline.extend({"type": "workflow", "label": log.action, "user_id": log.user_id, "time": log.created_at.isoformat(timespec="seconds"), "comment": log.comment} for log in workflow_logs)
    timeline.sort(key=lambda item: item["time"])
    display_details, display_items = _display_payload(db, document, source)
    return {
        "document": _serialize_document(document, context, db), "details": _model_dict(source),
        "display_details": display_details, "display_items": display_items,
        "relations": relation_items, "relation_graph": {"root": {"business_type": business_type, "business_id": business_id}, "edges": graph_edges}, "timeline": timeline,
        "comments": [{"id": row.id, "author_id": row.author_id, "author_name": row.author_name, "content": row.content, "created_at": row.created_at.isoformat(timespec="seconds")} for row in comments],
        "attachments": [{"id": row.id, "file_name": row.file_name, "content_type": row.content_type, "size_bytes": row.size_bytes, "uploaded_by": row.uploaded_by, "created_at": row.created_at.isoformat(timespec="seconds"), "download_url": f"/documents/attachments/{row.id}/download"} for row in attachments],
        "workflow": [{"id": row.id, "status": row.status, "current_node_key": row.current_node_key, "started_at": row.started_at.isoformat(timespec="seconds"), "completed_at": row.completed_at.isoformat(timespec="seconds") if row.completed_at else None} for row in workflow_instances],
    }


def add_comment(db: Session, context: UserContext, business_type: str, business_id: str, content: str) -> BizComment:
    source = _get_source_row(db, business_type, business_id, context)
    clean_content = content.strip()
    if not clean_content:
        raise AppError("评论内容不能为空", code=400)
    row = BizComment(org_id=context.org_id, object_type=business_type, object_id=business_id, author_id=context.id, author_name=context.user.display_name, content=clean_content)
    db.add(row)
    owner_id = getattr(source, "owner_id", None) or getattr(source, "created_by", None)
    if owner_id and owner_id != context.id:
        db.add(SysNotification(org_id=context.org_id, recipient_id=owner_id, notification_type="comment", severity="info", title="单据有新评论", content=f"{context.user.display_name}：{clean_content[:120]}", object_type=business_type, object_id=business_id, action_url=f"/documents/{business_type}/{business_id}"))
    db.commit()
    db.refresh(row)
    return row


def save_attachment(db: Session, context: UserContext, business_type: str, business_id: str, file_name: str, content_type: str, content: bytes) -> BizAttachment:
    _get_source_row(db, business_type, business_id, context)
    if not content:
        raise AppError("附件内容不能为空", code=400)
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise AppError("附件不能超过 20MB", code=400)
    safe_name = Path(file_name).name.strip()
    if not safe_name or safe_name in {".", ".."}:
        raise AppError("附件名称无效", code=400)
    file_key = f"{context.org_id}/{business_type}/{business_id}/{uuid4().hex}"
    path = ATTACHMENT_ROOT / file_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    row = BizAttachment(org_id=context.org_id, object_type=business_type, object_id=business_id, file_key=file_key, file_name=safe_name, content_type=(content_type or "application/octet-stream")[:128], size_bytes=len(content), uploaded_by=context.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_attachment(db: Session, context: UserContext, attachment_id: str) -> tuple[BizAttachment, Path]:
    row = db.get(BizAttachment, attachment_id)
    if row is None or row.org_id != context.org_id or row.is_deleted:
        raise AppError("附件不存在", code=404)
    path = ATTACHMENT_ROOT / row.file_key
    if not path.is_file():
        raise AppError("附件文件已丢失，请联系管理员", code=404)
    return row, path


def delete_attachment(db: Session, context: UserContext, attachment_id: str) -> None:
    row, path = get_attachment(db, context, attachment_id)
    if row.uploaded_by != context.id and not context.user.is_superuser:
        raise AppError("只能删除自己上传的附件", code=403)
    row.is_deleted = True
    db.commit()
    path.unlink(missing_ok=True)


def list_notifications(db: Session, context: UserContext, unread_only: bool, page: int, page_size: int) -> dict[str, Any]:
    filters = [SysNotification.org_id == context.org_id, SysNotification.recipient_id == context.id, SysNotification.is_deleted.is_(False)]
    if unread_only:
        filters.append(SysNotification.read_at.is_(None))
    total = db.scalar(select(func.count()).select_from(SysNotification).where(*filters)) or 0
    unread = db.scalar(select(func.count()).select_from(SysNotification).where(SysNotification.org_id == context.org_id, SysNotification.recipient_id == context.id, SysNotification.is_deleted.is_(False), SysNotification.read_at.is_(None))) or 0
    rows = db.scalars(select(SysNotification).where(*filters).order_by(SysNotification.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [{"id": row.id, "type": row.notification_type, "severity": row.severity, "title": row.title, "content": row.content, "action_url": row.action_url, "read_at": row.read_at.isoformat(timespec="seconds") if row.read_at else None, "created_at": row.created_at.isoformat(timespec="seconds")} for row in rows], "total": total, "unread": unread, "page": page, "page_size": page_size}


def mark_notification_read(db: Session, context: UserContext, notification_id: str | None = None) -> int:
    statement = select(SysNotification).where(SysNotification.org_id == context.org_id, SysNotification.recipient_id == context.id, SysNotification.is_deleted.is_(False), SysNotification.read_at.is_(None))
    if notification_id:
        statement = statement.where(SysNotification.id == notification_id)
    rows = db.scalars(statement).all()
    for row in rows:
        row.read_at = _now()
    db.commit()
    return len(rows)


def execute_command(db: Session, context: UserContext, business_type: str, business_id: str, command: str) -> dict[str, Any]:
    _assert_command_access(context, business_type)
    if business_type == "sales_order":
        from app.services.sales_service import approve_sales_order, create_delivery_from_order, submit_sales_order
        from app.services.workflow_service import has_running_workflow, start_workflow_if_active
        if command == "submit":
            result = submit_sales_order(db, business_id, context)
            start_workflow_if_active(db, "sales_order", business_id, context)
            document = _sync_row(db, business_type, result)
            db.commit()
            return {"document": _serialize_document(document, context, db)}
        if command == "approve":
            if has_running_workflow(db, "sales_order", business_id, context):
                raise AppError("该单据已进入审批流，请在我的待办中处理", code=409)
            result = approve_sales_order(db, business_id, context)
            document = _sync_row(db, business_type, result)
            db.commit()
            return {"document": _serialize_document(document, context, db)}
        if command == "create_delivery":
            result = create_delivery_from_order(db, business_id, context)
            _sync_row(db, "sales_delivery", result)
            _sync_inferred_relations(db, context.org_id)
            db.commit()
            return {"created": _serialize_document(db.scalar(select(BizDocument).where(BizDocument.org_id == context.org_id, BizDocument.business_type == "sales_delivery", BizDocument.business_id == result.id)), context, db)}
    if business_type == "sales_delivery" and command == "complete":
        from app.services.finance_service import create_receivable_from_sales_delivery
        from app.services.inventory_service import complete_sales_delivery
        delivery = complete_sales_delivery(db, business_id, context)
        receivable = create_receivable_from_sales_delivery(db, delivery.id, context)
        _sync_row(db, "sales_delivery", delivery)
        _sync_row(db, "sales_receivable", receivable)
        _sync_inferred_relations(db, context.org_id)
        db.commit()
        return {"document": _serialize_document(db.scalar(select(BizDocument).where(BizDocument.org_id == context.org_id, BizDocument.business_type == "sales_delivery", BizDocument.business_id == delivery.id)), context, db), "created": {"business_type": "sales_receivable", "business_id": receivable.id}}
    if business_type == "purchase_order":
        from app.services.purchase_service import approve_purchase_order, create_receipt_from_order, submit_purchase_order
        from app.services.workflow_service import has_running_workflow, start_workflow_if_active
        if command == "submit":
            result = submit_purchase_order(db, business_id, context)
            start_workflow_if_active(db, "purchase_order", business_id, context)
        elif command == "approve":
            if has_running_workflow(db, "purchase_order", business_id, context):
                raise AppError("该单据已进入审批流，请在我的待办中处理", code=409)
            result = approve_purchase_order(db, business_id, context)
        elif command == "create_receipt":
            result = create_receipt_from_order(db, business_id, context)
            _sync_row(db, "purchase_receipt", result)
            _sync_inferred_relations(db, context.org_id)
            db.commit()
            return {"created": _serialize_document(db.scalar(select(BizDocument).where(BizDocument.org_id == context.org_id, BizDocument.business_type == "purchase_receipt", BizDocument.business_id == result.id)), context, db)}
        else:
            raise AppError("当前采购订单不支持该操作", code=400)
        document = _sync_row(db, business_type, result)
        db.commit()
        return {"document": _serialize_document(document, context, db)}
    if business_type == "purchase_receipt" and command == "complete":
        from app.services.finance_service import create_payable_from_purchase_receipt
        from app.services.inventory_service import complete_purchase_receipt
        receipt = complete_purchase_receipt(db, business_id, context)
        payable = create_payable_from_purchase_receipt(db, receipt.id, context)
        _sync_row(db, business_type, receipt)
        _sync_row(db, "purchase_payable", payable)
        _sync_inferred_relations(db, context.org_id)
        db.commit()
        return {"document": _serialize_document(_sync_row(db, business_type, receipt), context, db), "created": {"business_type": "purchase_payable", "business_id": payable.id}}
    if business_type == "mfg_work_order":
        from app.services.production_service import cancel_work_order, complete_work_order, release_work_order
        if command == "release":
            result = release_work_order(db, business_id, context)
        elif command == "complete":
            result = complete_work_order(db, business_id, context)
        elif command == "cancel":
            result = cancel_work_order(db, business_id, context)
        else:
            raise AppError("当前生产工单不支持该操作", code=400)
        document = _sync_row(db, business_type, result)
        _sync_inferred_relations(db, context.org_id)
        db.commit()
        return {"document": _serialize_document(document, context, db)}
    if business_type == "inv_transfer":
        from app.services.inventory_service import approve_transfer, complete_transfer
        if command == "approve":
            result = approve_transfer(db, business_id, context)
        elif command == "complete":
            result = complete_transfer(db, business_id, context)
        else:
            raise AppError("当前调拨单不支持该操作", code=400)
        document = _sync_row(db, business_type, result)
        _sync_inferred_relations(db, context.org_id)
        db.commit()
        return {"document": _serialize_document(document, context, db)}
    if business_type == "inv_count" and command == "complete":
        from app.services.inventory_service import complete_count
        result = complete_count(db, business_id, context)
        document = _sync_row(db, business_type, result)
        _sync_inferred_relations(db, context.org_id)
        db.commit()
        return {"document": _serialize_document(document, context, db)}
    if business_type == "fin_voucher":
        from app.services.ledger_service import post_voucher, reverse_voucher
        if command == "post":
            result = post_voucher(db, business_id, context)
            document = _sync_row(db, business_type, result)
        elif command == "reverse":
            result = reverse_voucher(db, business_id, context)
            _sync_row(db, business_type, result)
            document = _sync_row(db, business_type, db.get(FinVoucher, business_id))
        else:
            raise AppError("当前会计凭证不支持该操作", code=400)
        _sync_inferred_relations(db, context.org_id)
        db.commit()
        return {"document": _serialize_document(document, context, db)}
    raise AppError("当前单据状态不支持该操作", code=400)
