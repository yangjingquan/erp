from dataclasses import dataclass

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


REQUIRED_TABLES = {
    "sys_org",
    "sys_department",
    "sys_user",
    "sys_role",
    "sys_menu",
    "sys_permission",
    "md_material",
    "md_customer",
    "md_supplier",
    "md_warehouse",
    "md_unit",
    "md_tax_rate",
    "sales_quote",
    "sales_order",
    "sales_delivery",
    "sales_return",
    "sales_receivable",
    "purchase_request",
    "purchase_order",
    "purchase_receipt",
    "purchase_return",
    "purchase_payable",
    "inv_stock",
    "inv_stock_transaction",
    "inv_transfer",
    "inv_count",
    "inv_warning",
    "fin_receipt",
    "fin_payment",
    "fin_expense",
    "fin_asset",
    "fin_voucher",
    "fin_voucher_entry",
    "fin_account",
    "fin_accounting_dimension",
    "fin_fiscal_period",
    "fin_bank_account",
    "fin_asset_depreciation",
    "wf_definition",
    "cfg_number_rule",
    "sys_operation_log",
    "mfg_bom",
    "mfg_bom_item",
    "mfg_mps",
    "mfg_mrp_run",
    "mfg_mrp_result",
    "mfg_routing",
    "mfg_routing_operation",
    "mfg_work_center",
    "mfg_capacity_calendar",
    "mfg_work_order",
    "mfg_work_order_cost",
    "mfg_work_order_material",
    "mfg_work_report",
    "mfg_subcontract_order",
    "mfg_subcontract_receipt",
    "inv_zone",
    "inv_location",
    "inv_batch",
    "inv_cost_layer",
    "cost_period_close",
    "cost_allocation_rule",
    "cost_allocation",
    "cost_allocation_item",
    "cost_project",
    "cost_project_entry",
    "crm_lead",
    "crm_opportunity",
    "crm_contact",
    "crm_activity",
    "qa_inspection",
    "qa_inspection_item",
    "qa_nonconformance",
    "qa_capa_action",
    "hr_employee",
    "hr_attendance",
    "hr_leave_request",
    "hr_payroll_run",
    "ext_event_outbox",
    "biz_document",
    "biz_document_relation",
    "biz_attachment",
    "biz_comment",
    "biz_saved_view",
    "biz_export_job",
    "sys_notification",
    "sys_idempotency_record",
}


@dataclass(frozen=True)
class SchemaStatus:
    connected: bool
    initialized: bool
    missing_tables: list[str]
    guidance: str
    error: str | None = None


def schema_status_from_tables(table_names: set[str]) -> SchemaStatus:
    missing = sorted(REQUIRED_TABLES - table_names)
    return SchemaStatus(
        connected=True,
        initialized=not missing,
        missing_tables=missing,
        guidance="" if not missing else "ERP 数据库未初始化，请先执行 database/init.sql",
    )


def check_schema(db: Session) -> SchemaStatus:
    try:
        table_names = set(inspect(db.bind).get_table_names())
    except SQLAlchemyError as exc:
        return SchemaStatus(
            connected=False,
            initialized=False,
            missing_tables=sorted(REQUIRED_TABLES),
            guidance="请检查 MySQL 是否启动以及数据库连接配置",
            error=exc.__class__.__name__,
        )
    return schema_status_from_tables(table_names)
