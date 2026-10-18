"""Repair user-facing values in the currently seeded ERP business records.

This is intentionally narrower than seed_realistic_data.py: it preserves all
business rows and workflow states while replacing synthetic filler labels and
repairing the relations needed to resolve readable party/source names.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import MetaData, select, update

from app.core.database import engine
from app.models import *  # noqa: F401,F403 - load complete model metadata
from tools.seed_realistic_data import REALISTIC_FIELD_VALUES, REALISTIC_NAMES, seed_count, uid


def main() -> None:
    metadata = MetaData()
    metadata.reflect(bind=engine)

    with engine.begin() as connection:
        # Remove suffixes from regular names across all named master records.
        for table_name, names in REALISTIC_NAMES.items():
            table = metadata.tables.get(table_name)
            if table is None or "name" not in table.c or "id" not in table.c:
                continue
            for index in range(1, min(seed_count(table_name), len(names)) + 1):
                connection.execute(
                    update(table)
                    .where(table.c.id == uid(table_name, index))
                    .values(name=names[index - 1])
                )

        # Set the explicitly reviewed fields by the deterministic seed row ID.
        for table_name, fields in REALISTIC_FIELD_VALUES.items():
            table = metadata.tables.get(table_name)
            if table is None or "id" not in table.c:
                continue
            row_count = max((len(values) for values in fields.values()), default=0)
            for index in range(1, row_count + 1):
                values: dict[str, object] = {}
                for field_name, pool in fields.items():
                    if field_name not in table.c or not pool:
                        continue
                    value: object = pool[(index - 1) % len(pool)]
                    if field_name in {"rate", "original_value", "accumulated_depreciation"}:
                        value = Decimal(str(value))
                    values[field_name] = value
                if values:
                    connection.execute(
                        update(table).where(table.c.id == uid(table_name, index)).values(**values)
                    )

        # Existing PLM snapshots were serialized as an object instead of a
        # list; the page iterates this field when rendering the impact column.
        plm = metadata.tables["plm_change_request"]
        connection.execute(
            update(plm)
            .where(plm.c.impact_snapshot.is_(None))
            .values(impact_snapshot=[])
        )
        for index in range(1, 7):
            connection.execute(
                update(plm)
                .where(plm.c.id == uid("plm_change_request", index))
                .values(impact_snapshot=[])
            )

        # Product revisions also carried generic filler text in both the
        # version and summary columns shown on the PLM page.
        revisions = metadata.tables["plm_product_revision"]
        revision_values = REALISTIC_FIELD_VALUES["plm_product_revision"]
        for index in range(1, max(map(len, revision_values.values())) + 1):
            values = {
                field: pool[(index - 1) % len(pool)]
                for field, pool in revision_values.items()
                if field in revisions.c and pool
            }
            connection.execute(
                update(revisions).where(revisions.c.id == uid("plm_product_revision", index)).values(**values)
            )

        customers = metadata.tables["md_customer"]
        suppliers = metadata.tables["md_supplier"]
        for index in range(1, 7):
            connection.execute(
                update(customers)
                .where(customers.c.id == uid("md_customer", index))
                .values(name=REALISTIC_NAMES["md_customer"][index - 1])
            )
            connection.execute(
                update(suppliers)
                .where(suppliers.c.id == uid("md_supplier", index))
                .values(name=REALISTIC_NAMES["md_supplier"][index - 1])
            )

        # Reconciliation statements must point at a party record from the
        # correct customer/supplier table or the UI falls back to “未关联往来方”.
        statements = metadata.tables["fin_reconciliation_statement"]
        for index in range(1, 7):
            statement = connection.execute(
                select(statements.c.statement_type).where(statements.c.id == uid("fin_reconciliation_statement", index))
            ).scalar_one_or_none()
            party_table = customers if statement == "ar" else suppliers
            party_index = (index + 1) // 2
            connection.execute(
                update(statements)
                .where(statements.c.id == uid("fin_reconciliation_statement", index))
                .values(party_id=uid("md_customer" if party_table is customers else "md_supplier", party_index))
            )

        # Inventory reservation source rows now resolve to actual sales orders.
        reservations = metadata.tables["inv_reservation"]
        for index in range(1, 7):
            connection.execute(
                update(reservations)
                .where(reservations.c.id == uid("inv_reservation", index))
                .values(source_type="sales_order", source_id=uid("sales_order", index))
            )

        # Resolve transaction organizations and source orders to real records.
        org_table = metadata.tables["sys_org"]
        users = metadata.tables["sys_user"]
        primary_org = connection.execute(
            select(users.c.org_id).order_by(users.c.id)
        ).scalars().first()
        if not primary_org:
            primary_org = connection.execute(
                select(org_table.c.id).order_by(org_table.c.created_at, org_table.c.id)
            ).scalars().first()
        org_values = [
            (uid("sys_org", 2), "ORG-SUZHOU-HQ", "苏州恒启工业系统有限公司"),
            (uid("sys_org", 3), "ORG-HANGZHOU-JS", "杭州嘉实自动化科技有限公司"),
        ]
        for org_id, code, name in org_values:
            existing = connection.execute(select(org_table.c.id).where(org_table.c.code == code)).scalar_one_or_none()
            if existing is None:
                connection.execute(
                    org_table.insert().values(
                        id=org_id, code=code, name=name, parent_id=primary_org, status="active",
                        created_at=datetime.now(), updated_at=datetime.now()
                    )
                )
        org_transactions = metadata.tables["org_intercompany_transaction"]
        for index in range(1, 7):
            connection.execute(
                update(org_transactions)
                .where(org_transactions.c.id == uid("org_intercompany_transaction", index))
                .values(
                    from_org_id=primary_org,
                    to_org_id=org_values[(index - 1) % 2][0],
                    source_type="sales_order",
                    source_id=uid("sales_order", index),
                )
            )

        # Tax invoice source and customer references follow the seeded orders.
        invoices = metadata.tables["tax_invoice"]
        invoice_tax_rates = [Decimal("13"), Decimal("9"), Decimal("6"), Decimal("3"), Decimal("0"), Decimal("0")]
        invoice_codes = ["VAT-13", "VAT-09", "VAT-06", "VAT-03", "VAT-EXEMPT", "VAT-EXPORT"]
        for index in range(1, 7):
            gross_amount = Decimal(str(42000 + index * 8500))
            rate = invoice_tax_rates[index - 1]
            tax_amount = (gross_amount * rate / (Decimal("100") + rate)).quantize(Decimal("0.01")) if rate else Decimal("0")
            connection.execute(
                update(invoices)
                .where(invoices.c.id == uid("tax_invoice", index))
                .values(
                    source_type="sales_order",
                    source_id=uid("sales_order", index),
                    party_id=uid("md_customer", index),
                    tax_code=invoice_codes[index - 1],
                    amount=gross_amount,
                    tax_amount=tax_amount,
                )
            )

        # The document index stores a denormalized party label; refresh it from
        # the repaired customer/supplier master data.
        documents = metadata.tables["biz_document"]
        document_parties = connection.execute(
            select(documents.c.id, documents.c.party_type, documents.c.party_id)
        ).mappings().all()
        for row in document_parties:
            if row["party_type"] == "customer":
                party_table = customers
            elif row["party_type"] == "supplier":
                party_table = suppliers
            else:
                continue
            party_name = connection.execute(
                select(party_table.c.name).where(party_table.c.id == row["party_id"])
            ).scalar_one_or_none()
            if party_name:
                connection.execute(
                    update(documents).where(documents.c.id == row["id"]).values(party_name=party_name)
                )

    print("已修复客户/供应商/仓库、库存、财务、CRM、生产、人事、资产、平台与 PLM 页面演示字段。")


if __name__ == "__main__":
    main()
