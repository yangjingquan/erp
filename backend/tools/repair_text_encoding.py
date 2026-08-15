"""Repair double-encoded human-facing text created by the local data setup."""

from __future__ import annotations

import sys
import re
from pathlib import Path

from sqlalchemy import MetaData, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal, engine


TARGET_COLUMNS = {
    "ai_exception_alert": {"recommended_action", "title"},
    "biz_attachment": {"file_name"},
    "biz_document": {"party_name", "title"},
    "biz_export_job": {"file_name"},
    "biz_report_definition": {"description", "name"},
    "biz_saved_view": {"name"},
    "cost_project": {"project_name"},
    "cost_project_entry": {"category"},
    "crm_activity": {"subject"},
    "crm_contact": {"name", "title"},
    "crm_lead": {"name"},
    "crm_opportunity": {"name"},
    "eam_maintenance_plan": {"name"},
    "eam_work_order": {"description"},
    "ext_event_subscription": {"name"},
    "fin_account": {"name"},
    "fin_accounting_dimension": {"name"},
    "fin_asset": {"category"},
    "fin_bank_account": {"name"},
    "fin_bank_statement": {"source_file"},
    "fin_bank_statement_line": {"note"},
    "fin_budget": {"note"},
    "fin_cash_forecast": {"note"},
    "fin_currency": {"name"},
    "fin_expense": {"description"},
    "fin_payment": {"account_name", "remark"},
    "fin_receipt": {"account_name", "remark"},
    "fin_reconciliation_statement": {"note"},
    "fin_voucher_entry": {"account_name", "summary"},
    "hr_benefit_record": {"note"},
    "hr_employee": {"name"},
    "hr_employee_lifecycle": {"note"},
    "hr_recruitment_candidate": {"name", "note"},
    "inv_location": {"name"},
    "inv_reservation": {"note"},
    "inv_zone": {"name"},
    "low_code_definition": {"name"},
    "md_customer": {"name", "short_name"},
    "md_material": {"category", "name"},
    "md_supplier": {"name", "short_name"},
    "md_tax_rate": {"name"},
    "md_unit": {"name"},
    "md_warehouse": {"name"},
    "metric_definition": {"formula", "name"},
    "mfg_alternate_material": {"reason"},
    "mfg_capacity_calendar": {"note"},
    "mfg_work_center": {"name"},
    "mfg_work_order_exception": {"description"},
    "ocr_document": {"source_file"},
    "plm_change_request": {"description", "title"},
    "project": {"name"},
    "project_entry": {"category"},
    "project_milestone": {"name"},
    "project_wbs": {"name"},
    "purchase_request": {"remark"},
    "qa_capa_action": {"description"},
    "qa_customer_claim": {"title"},
    "qa_defect_catalog": {"name"},
    "qa_nonconformance": {"description"},
    "qa_plan": {"name"},
    "qa_quality_cost": {"note"},
    "qa_supplier_quality": {"note"},
    "sales_order": {"remark"},
    "svc_case": {"title"},
    "tax_code": {"name"},
    "tms_shipment": {"note"},
    "tms_shipment_event": {"note"},
    "wf_definition": {"name"},
}

CP1252_SPECIAL = {
    0x20AC: 0x80,
    0x201A: 0x82,
    0x192: 0x83,
    0x201E: 0x84,
    0x2026: 0x85,
    0x2020: 0x86,
    0x2021: 0x87,
    0x2C6: 0x88,
    0x2030: 0x89,
    0x160: 0x8A,
    0x2039: 0x8B,
    0x152: 0x8C,
    0x17D: 0x8E,
    0x2018: 0x91,
    0x2019: 0x92,
    0x201C: 0x93,
    0x201D: 0x94,
    0x2022: 0x95,
    0x2013: 0x96,
    0x2014: 0x97,
    0x2DC: 0x98,
    0x2122: 0x99,
    0x161: 0x9A,
    0x203A: 0x9B,
    0x153: 0x9C,
    0x178: 0x9F,
}


def repair(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    def decode_segment(segment: str) -> str | None:
        try:
            raw = bytearray()
            for char in segment:
                code = ord(char)
                if code <= 0xFF:
                    raw.append(code)
                else:
                    raw.append(CP1252_SPECIAL[code])
            decoded = bytes(raw).decode("utf-8")
        except (KeyError, UnicodeDecodeError):
            return None
        return decoded if "�" not in decoded else None

    candidate = decode_segment(value)
    if candidate is None:
        candidate = value
        for match in re.finditer(r"[^\x00-\x7F]+", value):
            decoded = decode_segment(match.group(0))
            if decoded is not None:
                candidate = candidate.replace(match.group(0), decoded, 1)
    if candidate == value:
        return None
    if "�" in candidate:
        return None
    return candidate


def main() -> None:
    metadata = MetaData()
    metadata.reflect(bind=engine)
    changed = 0
    by_table: dict[str, int] = {}
    with SessionLocal() as db:
        for table_name, columns in TARGET_COLUMNS.items():
            table = metadata.tables.get(table_name)
            if table is None or not table.primary_key.columns:
                continue
            primary_keys = list(table.primary_key.columns)
            for row in db.execute(select(table)).mappings():
                values: dict[str, str] = {}
                for column_name in columns:
                    if column_name not in table.c:
                        continue
                    fixed = repair(row[column_name])
                    if fixed is not None:
                        values[column_name] = fixed
                if not values:
                    continue
                predicate = [column == row[column.name] for column in primary_keys]
                db.execute(table.update().where(*predicate).values(**values))
                changed += len(values)
                by_table[table_name] = by_table.get(table_name, 0) + len(values)
        db.commit()
    print(f"修复字段数：{changed}")
    for table_name, count in sorted(by_table.items()):
        print(f"{table_name}: {count}")


if __name__ == "__main__":
    main()
