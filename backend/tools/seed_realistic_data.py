"""Populate the local ERP with deterministic, realistic-looking demo data.

This utility is intentionally local-only.  It uses the existing SQLAlchemy
models and writes enough rows for list pages to exercise pagination while
keeping all labels and business keys suitable for a Chinese enterprise demo.
"""

from __future__ import annotations

import calendar
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import MetaData, Table, insert
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import Base, engine
from app.models import *  # noqa: F401,F403 - registers the complete model catalog


ORG = "00000000-0000-0000-0000-000000000001"
ADMIN = "00000000-0000-0000-0000-000000000004"
DEPT = "00000000-0000-0000-0000-000000000002"


def uid(table: str, index: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"erp-realistic/{table}/{index}"))


def month_value(index: int) -> str:
    month = (index % 18) + 1
    year = 2026 + (month - 1) // 12
    return f"{year:04d}-{((month - 1) % 12) + 1:02d}"


# Realistic per-table status/type pools so that seeded rows can participate in
# the documented state machines instead of being stuck at a single sentinel
# value.  Values are cycled by index.  Master-data tables intentionally fall
# back to the "active/inactive" default defined in ENUM_FALLBACK.
STATUS_POOLS: dict[str, dict[str, list[str]]] = {
    "sales_quote": {"status": ["draft", "submitted", "approved", "rejected"]},
    "sales_order": {"status": ["draft", "submitted", "approved", "completed"]},
    "sales_delivery": {"status": ["draft", "completed"]},
    "sales_return": {"status": ["draft", "submitted", "completed"]},
    "sales_receivable": {"status": ["open", "partial", "settled"], "source_type": ["sales_delivery"]},
    "purchase_request": {"status": ["draft", "submitted", "approved", "rejected"]},
    "purchase_order": {"status": ["draft", "submitted", "approved", "completed"]},
    "purchase_receipt": {"status": ["draft", "completed"]},
    "purchase_return": {"status": ["draft", "submitted", "completed"]},
    "purchase_payable": {"status": ["open", "partial", "settled"], "source_type": ["purchase_receipt"]},
    "fin_receipt": {"status": ["confirmed", "partial", "settled"]},
    "fin_payment": {"status": ["confirmed", "partial", "settled"]},
    "fin_expense": {"status": ["draft", "submitted", "approved", "settled"]},
    "fin_voucher": {"status": ["draft", "posted", "reversed"]},
    "fin_account": {"status": ["active", "inactive"]},
    "fin_budget": {"status": ["draft", "approved"]},
    "fin_cash_forecast": {"status": ["draft", "approved"]},
    "fin_reconciliation_statement": {"status": ["draft", "confirmed"]},
    "fin_bank_statement": {"status": ["imported", "matched"]},
    "fin_bank_statement_line": {"status": ["pending", "matched", "partial"]},
    "fin_asset": {"status": ["active", "scrapped"]},
    "fin_fiscal_period": {"status": ["open", "closed"]},
    "fin_period_close_checklist": {"status": ["pending", "completed"]},
    "mfg_bom": {"status": ["draft", "submitted", "approved", "disabled"]},
    "mfg_mps": {"status": ["draft", "planned"]},
    "mfg_mrp_run": {"status": ["draft", "completed"]},
    "mfg_plan_run": {"status": ["draft", "completed"]},
    "mfg_planned_order": {"status": ["pending", "confirmed", "ignored"], "order_type": ["purchase", "manufacture"]},
    "mfg_work_order": {"status": ["draft", "released", "in_progress", "completed"]},
    "mfg_routing": {"status": ["draft", "submitted", "approved", "disabled"]},
    "mfg_work_center": {"status": ["active", "inactive"]},
    "mfg_subcontract_order": {"status": ["draft", "released", "completed", "cancelled"]},
    "mfg_work_order_exception": {"status": ["open", "resolved"]},
    "mfg_work_order_schedule": {"status": ["planned", "completed"]},
    "qa_inspection": {"status": ["draft", "submitted", "completed", "closed"]},
    "qa_nonconformance": {"status": ["open", "investigating", "closed"]},
    "qa_plan": {"status": ["draft", "active"]},
    "qa_capa_action": {"status": ["open", "completed"]},
    "qa_customer_claim": {"status": ["open", "investigating", "approved", "rejected", "closed"]},
    "qa_spc_record": {"status": ["in_control", "out_of_control"]},
    "crm_lead": {"status": ["new", "contacted", "qualified", "converted", "lost"]},
    "crm_opportunity": {"stage": ["new", "prospecting", "negotiation", "won", "lost"]},
    "hr_employee": {"status": ["active", "inactive"]},
    "hr_leave_request": {"status": ["draft", "submitted", "approved", "rejected"]},
    "hr_attendance": {"status": ["present", "absent", "late", "leave"]},
    "hr_payroll_run": {"status": ["draft", "approved", "paid"]},
    "hr_recruitment_candidate": {"status": ["new", "interview", "hired", "rejected"]},
    "eam_asset": {"status": ["active", "inactive"]},
    "eam_work_order": {"status": ["open", "assigned", "in_progress", "resolved", "closed"]},
    "eam_maintenance_plan": {"status": ["active", "inactive"]},
    "svc_case": {"status": ["open", "assigned", "in_progress", "resolved", "closed"]},
    "svc_contract": {"status": ["active", "expired"]},
    "svc_visit": {"status": ["planned", "completed"]},
    "plm_change_request": {"status": ["draft", "submitted", "approved", "effective"]},
    "plm_change_order": {"status": ["draft", "approved", "effective"]},
    "plm_change_impact": {"status": ["pending", "applied", "rejected"]},
    "plm_product_revision": {"status": ["draft", "submitted", "effective", "obsolete"]},
    "srm_rfq": {"status": ["draft", "quoted", "accepted"]},
    "srm_supplier_score": {"status": ["draft", "confirmed"]},
    "tax_code": {"status": ["active", "inactive"]},
    "tax_invoice": {"status": ["draft", "submitted", "issued", "red_issued"]},
    "org_intercompany_transaction": {"status": ["draft", "confirmed"]},
    "project": {"status": ["draft", "active", "closed"]},
    "project_milestone": {"status": ["pending", "completed"]},
    "project_wbs": {"status": ["active", "completed"]},
    "low_code_definition": {"status": ["draft", "published"]},
    "metric_definition": {"status": ["draft", "published"]},
    "ai_exception_alert": {"status": ["open", "resolved"], "severity": ["low", "medium", "high"]},
    "sys_api_client": {"status": ["active", "disabled"]},
    "ext_event_outbox": {"status": ["pending", "processed", "failed"]},
    "ext_event_delivery": {"status": ["pending", "delivered", "failed"]},
    "ext_event_subscription": {"status": ["active", "disabled"]},
    "inv_transfer": {"status": ["draft", "approved", "completed"]},
    "inv_count": {"status": ["draft", "completed"]},
    "inv_warehouse_task": {"status": ["ready", "in_progress", "completed"], "task_type": ["pick", "pack", "check"]},
    "inv_pick_wave": {"status": ["draft", "released", "completed"]},
    "inv_reservation": {"status": ["active", "released"]},
    "inv_batch": {"status": ["active", "used"]},
    "inv_location": {"status": ["active", "inactive"]},
    "inv_zone": {"status": ["active", "inactive"]},
    "inv_warehouse_access": {"status": ["active", "inactive"]},
    "tms_shipment": {"status": ["draft", "planned", "dispatched", "in_transit", "delivered"]},
    "ocr_document": {"status": ["completed", "needs_review"]},
    "biz_document": {"status": ["draft", "submitted", "approved", "completed"]},
    "biz_export_job": {"status": ["pending", "processing", "completed", "failed"]},
    "biz_saved_view": {"status": ["active", "inactive"]},
    "biz_report_definition": {"status": ["active", "inactive"]},
    "biz_report_run": {"status": ["completed", "failed"]},
    "cost_allocation": {"status": ["draft", "posted"]},
    "cost_period_close": {"status": ["open", "closed"]},
    "wf_definition": {"status": ["draft", "active"]},
    "wf_instance": {"status": ["running", "completed", "rejected"]},
    "wf_task": {"status": ["pending", "approved", "rejected"]},
}

# Fallback pools for enum-style columns that are not listed per-table above.
ENUM_FALLBACK: dict[str, list[str]] = {
    "status": ["active", "inactive"],
    "stage": ["new", "prospecting", "negotiation", "won"],
    "severity": ["low", "medium", "high"],
    "result": ["pass"],
    "disposition": ["use_as_is"],
    "account_type": ["asset", "liability", "equity", "cost", "revenue", "expense"],
    "balance_direction": ["debit", "credit"],
    "dimension_type": ["department"],
    "depreciation_method": ["straight_line"],
    "basis": ["manual"],
    "source_type": ["manual"],
    "statement_type": ["ar", "ap"],
    "match_type": ["rule", "manual"],
    "direction": ["in", "out"],
    "task_type": ["pick", "pack", "check"],
    "order_type": ["purchase", "manufacture"],
    "inspection_type": ["incoming", "process", "final"],
    "change_type": ["engineering"],
    "object_type": ["bom", "routing", "purchase", "work_order"],
    "service_type": ["repair", "maintenance", "inspection"],
    "invoice_type": ["input", "output"],
    "event_type": ["created", "updated"],
    "membership_type": ["user"],
    "action_type": ["create"],
    "notification_type": ["info"],
    "document_type": ["sales_order"],
    "visibility": ["private"],
    "reset_cycle": ["monthly"],
}


def enum_value(table_name: str, key: str, index: int) -> str:
    pool = STATUS_POOLS.get(table_name, {}).get(key) or ENUM_FALLBACK.get(key, ["active"])
    return pool[(index - 1) % len(pool)]


def table_rows(table: Table, index: int) -> dict[str, object]:
    name = table.name
    row: dict[str, object] = {}
    for column in table.columns:
        key = column.name
        if key == "id":
            row[key] = uid(name, index)
        elif key == "org_id":
            row[key] = ORG
        elif key in {"user_id", "owner_id", "created_by", "updated_by", "requester_id", "applicant_id", "manager_id", "assigned_to", "reported_by", "approved_by", "posted_by", "closed_by", "completed_by", "confirmed_by", "technician_id"}:
            row[key] = ADMIN
        elif key == "department_id":
            row[key] = DEPT
        elif key == "parent_id":
            row[key] = None
        elif key in {"material_id", "alternate_material_id"}:
            row[key] = uid("md_material", (index % 40) + 1)
        elif key in {"unit_id"}:
            row[key] = uid("md_unit", (index % 40) + 1)
        elif key in {"tax_rate_id"}:
            row[key] = uid("md_tax_rate", (index % 40) + 1)
        elif key in {"warehouse_id", "from_warehouse_id", "to_warehouse_id"}:
            row[key] = uid("md_warehouse", (index % 20) + 1)
        elif key == "customer_id":
            row[key] = uid("md_customer", (index % 40) + 1)
        elif key == "supplier_id":
            row[key] = uid("md_supplier", (index % 40) + 1)
        elif key == "employee_id":
            row[key] = uid("hr_employee", (index % 40) + 1)
        elif key == "asset_id":
            row[key] = uid("eam_asset", (index % 20) + 1)
        elif key == "project_id":
            row[key] = uid("project", (index % 20) + 1)
        elif key == "work_order_id":
            row[key] = uid("mfg_work_order", (index % 40) + 1)
        elif key == "inspection_id":
            row[key] = uid("qa_inspection", index)
        elif key == "bom_id":
            row[key] = uid("mfg_bom", (index % 40) + 1)
        elif key == "routing_id":
            row[key] = uid("mfg_routing", (index % 20) + 1)
        elif key == "work_center_id":
            row[key] = uid("mfg_work_center", (index % 20) + 1)
        elif key == "mps_id":
            row[key] = uid("mfg_mps", (index % 20) + 1)
        elif key == "run_id":
            row[key] = uid("mfg_plan_run", (index % 20) + 1)
        elif key == "request_id":
            row[key] = uid("purchase_request", (index % 40) + 1)
        elif key == "order_id":
            row[key] = uid("sales_order", (index % 40) + 1)
        elif key in {"quote_id", "return_id", "statement_id", "voucher_id", "receipt_id", "payment_id", "payable_id", "receivable_id", "allocation_id", "plan_id", "change_order_id", "change_request_id", "contract_id", "case_id", "subscription_id", "event_id", "wave_id", "location_id", "batch_id", "transaction_id", "operation_id", "wbs_id", "source_id", "document_id", "object_id", "source_event", "inbound_transaction_id", "outbound_transaction_id", "cost_layer_id", "formal_document_id", "project_id"}:
            row[key] = uid(name + key, index)
        elif key.endswith("_json") or key in {"items_json", "schema_json", "workflow_json", "evidence_json", "payload_json", "result_json", "snapshot_json", "source_snapshot", "input_snapshot", "output_snapshot", "bom_snapshot", "routing_snapshot", "details", "dimensions_json", "goals_json", "response_json", "event_types", "scopes"}:
            row[key] = [] if "items" in key or key in {"event_types", "scopes"} else {}
        elif key in {"created_at", "updated_at", "event_time", "occurred_at", "report_time", "scheduled_at", "effective_at", "closed_at", "reopened_at", "completed_at", "delivered_at", "confirmed_at", "posted_at"}:
            row[key] = datetime.now()
        elif key in {"date", "order_date", "quote_date", "request_date", "expense_date", "payment_date", "receipt_date", "delivery_date", "return_date", "promised_date", "document_date", "allocation_date", "entry_date", "plan_date", "plan_from", "plan_to", "due_date", "start_date", "end_date", "expected_date", "purchase_date", "effective_from", "effective_to", "production_date", "expiry_date", "attendance_date", "next_due", "next_maintenance_date", "planned_date", "actual_date", "event_date", "statement_date", "transaction_date", "schedule_date", "transfer_date", "count_date", "voucher_date", "valid_until", "period_start", "period_end"}:
            row[key] = date.today() + timedelta(days=(index % 15) - 7)
        elif key in {"is_deleted", "required", "allow_posting", "is_base", "blocking", "is_shared", "serial_tracking"}:
            row[key] = False
        elif key in {"version", "line_no", "priority", "sequence_length", "precision_scale", "decimal_places", "interval_days", "daily_capacity_hours", "useful_life_months", "threshold_days", "sample_size", "attempt_count", "retry_count", "failure_count", "response_status", "row_count", "credit_days"}:
            row[key] = (index % 20) + 1
        elif key in {"amount", "total_amount", "actual_amount", "budget_amount", "original_value", "accumulated_depreciation", "standard_cost", "sale_price", "purchase_price", "credit_limit", "quote_amount", "processing_fee", "processing_fee_amount", "inflow_amount", "outflow_amount", "net_amount", "total_debit", "total_credit", "debit_amount", "credit_amount", "value", "freight_amount", "statement_amount", "reconciled_amount", "matched_amount", "unit_cost", "total_cost", "material_cost", "labor_cost", "overhead_cost", "subcontract_cost", "scrap_cost", "variance_amount", "actual_unit_cost", "base_salary", "allowance", "score", "target", "rate", "tax_amount", "delivery_score", "quality_score", "service_score", "total_score", "defect_rate", "sample_value", "lsl", "usl", "cpk", "impact_quantity", "quantity", "min_stock", "max_stock", "plan_quantity", "receivable_amount", "payable_amount", "residual_rate", "efficiency_rate", "labor_rate", "overhead_rate", "required_quantity", "issued_quantity", "returned_quantity", "completed_quantity", "reported_good_quantity", "reported_scrap_quantity", "planned_quantity", "good_quantity", "scrap_quantity", "hours", "scheduled_hours", "actual_hours", "original_quantity", "remaining_quantity", "released_quantity", "locked_quantity", "available_quantity", "average_cost", "estimated_price", "unit_price", "tax_rate"}:
            row[key] = Decimal(str(10 + index * 3))
        elif key in {"status", "result", "disposition", "severity", "stage", "account_type", "balance_direction", "dimension_type", "depreciation_method", "basis", "source_type", "statement_type", "match_type", "direction", "task_type", "order_type", "inspection_type", "change_type", "object_type", "service_type", "invoice_type", "event_type", "membership_type", "action_type", "notification_type", "document_type", "visibility", "reset_cycle"}:
            row[key] = enum_value(name, key, index)
        else:
            row[key] = f"{name.replace('_', ' ').title()} {index:02d}"

    # Human-facing master data and document numbers.
    prefixes = {
        "md_unit": "UOM", "md_tax_rate": "VAT", "md_material": "MAT", "md_customer": "CUS", "md_supplier": "SUP", "md_warehouse": "WH",
        "sales_quote": "QT", "sales_order": "SO", "sales_delivery": "SD", "sales_return": "SR",
        "purchase_request": "PRQ", "purchase_order": "PO", "purchase_receipt": "GR", "purchase_return": "PTR",
        "mfg_bom": "BOM", "mfg_mps": "MPS", "mfg_mrp_run": "MRP", "mfg_work_order": "WO", "mfg_routing": "RT", "mfg_work_center": "WC", "qa_inspection": "QI", "crm_lead": "LD", "crm_opportunity": "OP",
        "fin_expense": "EXP", "fin_receipt": "RCV", "fin_payment": "PAY", "fin_voucher": "VCH", "hr_employee": "EMP", "hr_recruitment_candidate": "CAN", "eam_asset": "AST", "tms_shipment": "SHP",
    }
    if "code" in table.c and name in prefixes:
        row["code"] = f"{prefixes[name]}-{index:04d}"
    if "doc_no" in table.c:
        row["doc_no"] = f"{prefixes.get(name, name[:3].upper())}{date.today():%Y%m}{index:04d}"
    if "rfq_no" in table.c:
        row["rfq_no"] = f"RFQ-{date.today():%Y%m}-{index:04d}"
    if "run_no" in table.c:
        row["run_no"] = f"PLAN-{date.today():%Y%m}-{index:04d}"
    if "voucher_no" in table.c:
        row["voucher_no"] = f"VCH-{date.today():%Y%m}-{index:04d}"
    if name == "fin_currency" and "code" in table.c:
        row["code"] = "CNY" if index == 1 else f"C{index:02d}"
        row["name"] = "人民币" if index == 1 else f"结算币种{index:02d}"
        row["symbol"] = "¥" if index == 1 else "¤"
    if "period" in table.c:
        row["period"] = month_value(index)
    if "last_depreciation_period" in table.c:
        row["last_depreciation_period"] = month_value(index)
    if "name" in table.c:
        row["name"] = f"{prefixes.get(name, '业务')}示例{index:02d}"
    if name == "biz_document":
        doc_types = ["sales_order", "purchase_order", "sales_delivery", "purchase_receipt", "qa_inspection", "fin_expense", "mfg_work_order"]
        doc_type = doc_types[(index - 1) % len(doc_types)]
        row["business_type"] = doc_type
        row["business_id"] = uid(doc_type, ((index - 1) % 40) + 1)
        row["party_type"] = "customer" if doc_type.startswith("sales") else "supplier"
        row["party_id"] = uid("md_customer" if row["party_type"] == "customer" else "md_supplier", ((index - 1) % 40) + 1)
        row["party_name"] = f"华东{('客户' if row['party_type'] == 'customer' else '供应商')}{index:02d}"
        row["source_type"] = doc_type
    if "display_name" in table.c:
        row["display_name"] = f"运营专员{index:02d}"
    if "description" in table.c:
        row["description"] = f"围绕华东区域交付的第 {index:02d} 条业务记录"
    if "title" in table.c:
        row["title"] = f"华东客户服务事项 {index:02d}"
    if "note" in table.c:
        row["note"] = "已完成业务核对，等待下一节点处理"
    if "remark" in table.c:
        row["remark"] = "季度经营计划配套记录"
    if "email" in table.c:
        row["email"] = f"contact{index:02d}@example.cn"
    if "phone" in table.c:
        row["phone"] = f"138{index:08d}"
    if "account_no" in table.c:
        row["account_no"] = f"622202260000{index:06d}"
    if "currency" in table.c:
        row["currency"] = "CNY"
    if "base_currency" in table.c:
        row["base_currency"] = "CNY"
    if "quote_currency" in table.c:
        row["quote_currency"] = "USD"
    if "source_file" in table.c:
        row["source_file"] = f"invoice_{index:02d}.pdf"
    if "file_name" in table.c:
        row["file_name"] = f"运营报表_{index:02d}.csv"
    if "file_key" in table.c:
        row["file_key"] = f"exports/operations/{index:02d}.csv"
    if "account_code" in table.c:
        row["account_code"] = f"{6001 + (index % 20)}"
    if "account_name" in table.c:
        row["account_name"] = "主营业务收入"
    if "asset_code" in table.c:
        row["asset_code"] = f"AST-{index:04d}"
    if "employee_no" in table.c:
        row["employee_no"] = f"EMP-{index:04d}"
    if "project_code" in table.c:
        row["project_code"] = f"PRJ-{index:04d}"
    if "project_name" in table.c:
        row["project_name"] = f"智能仓储升级项目 {index:02d}"
    if "object_key" in table.c:
        row["object_key"] = f"service_request_{index:02d}"
    if "metric_key" in table.c:
        row["metric_key"] = f"ops_metric_{index:02d}"
    if "alert_key" in table.c:
        row["alert_key"] = f"alert_{index:02d}"
    if "client_key" in table.c:
        row["client_key"] = f"client_{index:02d}"
    if "endpoint_url" in table.c:
        row["endpoint_url"] = "https://api.example.cn/erp/events"
    if "secret_hash" in table.c:
        row["secret_hash"] = "sha256:local-demo-secret"
    if "signing_secret" in table.c:
        row["signing_secret"] = "local-demo-signing-secret"
    return row


def main() -> None:
    metadata = MetaData()
    metadata.reflect(bind=engine)
    # A few tables intentionally remain empty because they are immutable
    # framework registries or association tables that are populated by their
    # parent business operation.
    skip = {
        "sys_org", "sys_department", "sys_user", "sys_role", "sys_menu", "sys_permission", "sys_user_role", "sys_role_menu", "sys_role_permission", "sys_user_data_scope",
        "sys_schema_migration", "cfg_global_parameter", "cfg_number_rule", "ext_module_registry",
    }
    results: list[str] = []
    selected = set(sys.argv[1:])
    for name in sorted(metadata.tables):
        if name in skip or name.startswith("sys_") and name in {"sys_operation_log", "sys_login_log"}:
            continue
        if selected and name not in selected:
            continue
        table = metadata.tables[name]
        success = 0
        for index in range(1, 41):
            row = table_rows(table, index)
            try:
                with engine.begin() as connection:
                    connection.execute(insert(table).values(row))
                success += 1
            except SQLAlchemyError:
                # Detail tables may depend on a parent operation that the
                # corresponding page does not expose.  Keep the seed robust:
                # successful parent tables still provide useful page data.
                continue
        if success:
            results.append(f"{name}:{success}")
    print("\n".join(results))


if __name__ == "__main__":
    main()
