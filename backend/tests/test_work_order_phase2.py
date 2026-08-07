from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppError
from app.core.security import create_access_token
from app.models.configuration import CfgNumberRule
from app.models.inventory import InvStock, InvStockTransaction
from app.models.inventory_advanced import InvWarehouseAccess
from app.models.logging import SysOperationLog
from app.models.master_data import MdMaterial, MdWarehouse
from app.models.platform import ExtEventOutbox
from app.models.production import MfgMps
from app.models.system import SysUser
from app.services.auth_service import UserContext
from app.services.production_service import report_work


def headers():
    return {"Authorization": f"Bearer {create_access_token('user-1', ['production:manage'])}"}


def seed_work_order_data(session):
    session.add_all(
        [
            CfgNumberRule(
                id="rule-mfg-work-order",
                org_id="org-1",
                rule_key="mfg_work_order",
                prefix="WO",
                date_format="%Y%m%d",
                sequence_length=4,
                reset_cycle="day",
            ),
            MdMaterial(id="finished-1", org_id="org-1", code="FG-1", name="Finished goods"),
            MdMaterial(id="component-1", org_id="org-1", code="CMP-1", name="Component"),
            MdWarehouse(id="warehouse-1", org_id="org-1", code="WH-1", name="Main warehouse"),
            InvWarehouseAccess(
                org_id="org-1", warehouse_id="warehouse-1", user_id="user-1", access_level="manage"
            ),
            InvStock(
                id="component-stock",
                org_id="org-1",
                warehouse_id="warehouse-1",
                material_id="component-1",
                quantity=Decimal("12"),
                available_quantity=Decimal("12"),
                average_cost=Decimal("3"),
            ),
        ]
    )
    session.commit()


def create_approved_bom(client):
    created = client.post(
        "/api/production/boms",
        json={
            "material_id": "finished-1",
            "bom_version": "1.0",
            "effective_from": "2026-08-01",
            "items": [{"material_id": "component-1", "quantity": "2"}],
        },
        headers=headers(),
    )
    bom_id = created.json()["data"]["id"]
    assert client.post(f"/api/production/boms/{bom_id}/submit", headers=headers()).json()["code"] == 0
    assert client.post(f"/api/production/boms/{bom_id}/approve", headers=headers()).json()["code"] == 0
    return bom_id


def create_released_work_order(client):
    created = client.post(
        "/api/production/work-orders",
        json={
            "material_id": "finished-1",
            "warehouse_id": "warehouse-1",
            "quantity": "5",
            "plan_date": "2026-08-02",
        },
        headers=headers(),
    )
    assert created.json()["code"] == 0
    work_order = created.json()["data"]
    assert work_order["status"] == "draft"
    assert work_order["bom_snapshot"]["items"] == [
        {"material_id": "component-1", "quantity": "2"}
    ]
    released = client.post(f"/api/production/work-orders/{work_order['id']}/release", headers=headers())
    assert released.json()["code"] == 0
    return released.json()["data"]


def service_context(session):
    return UserContext(user=session.get(SysUser, "user-1"), permissions={"*"})


def test_work_order_issue_report_complete_updates_inventory_and_is_traceable(client_and_session):
    """Removing ledger posts or the completion event breaks the public production trace."""
    client, session = client_and_session
    seed_work_order_data(session)
    create_approved_bom(client)
    work_order = create_released_work_order(client)

    issue = client.post(
        f"/api/production/work-orders/{work_order['id']}/issue",
        json={"items": [{"material_id": "component-1", "quantity": "10"}]},
        headers=headers(),
    )
    assert issue.json()["code"] == 0
    report = client.post(
        f"/api/production/work-orders/{work_order['id']}/reports",
        json={"good_quantity": "5", "scrap_quantity": "0", "hours": "3"},
        headers=headers(),
    )
    assert report.json()["code"] == 0
    completed = client.post(f"/api/production/work-orders/{work_order['id']}/complete", headers=headers())

    assert completed.json()["code"] == 0
    assert completed.json()["data"]["status"] == "completed"
    assert session.query(InvStockTransaction).filter_by(
        source_type="mfg_material_issue", source_id=issue.json()["data"]["id"]
    ).count() == 1
    assert session.query(InvStockTransaction).filter_by(
        source_type="mfg_completion", source_id=work_order["id"]
    ).count() == 1
    assert session.get(InvStock, "component-stock").quantity == Decimal("2.000000")
    finished_stock = session.query(InvStock).filter_by(
        org_id="org-1", warehouse_id="warehouse-1", material_id="finished-1"
    ).one()
    assert finished_stock.quantity == Decimal("5.000000")
    assert session.query(ExtEventOutbox).filter_by(
        event_type="work_order.completed", aggregate_id=work_order["id"]
    ).count() == 1
    assert session.query(SysOperationLog).filter_by(resource="mfg_work_order", target_id=work_order["id"]).count() >= 4


def test_work_order_rejects_issue_over_bom_quantity_and_double_completion(client_and_session):
    """Permitting excess component consumption or repeated completion corrupts quantities and stock."""
    client, session = client_and_session
    seed_work_order_data(session)
    create_approved_bom(client)
    work_order = create_released_work_order(client)

    over_issue = client.post(
        f"/api/production/work-orders/{work_order['id']}/issue",
        json={"items": [{"material_id": "component-1", "quantity": "11"}]},
        headers=headers(),
    )
    report = client.post(
        f"/api/production/work-orders/{work_order['id']}/reports",
        json={"good_quantity": "5", "scrap_quantity": "0", "hours": "3"},
        headers=headers(),
    )
    first_completion = client.post(f"/api/production/work-orders/{work_order['id']}/complete", headers=headers())
    second_completion = client.post(f"/api/production/work-orders/{work_order['id']}/complete", headers=headers())

    assert over_issue.json()["code"] == 400
    assert report.json()["code"] == 0
    assert first_completion.json()["code"] == 0
    assert second_completion.json()["code"] == 0
    assert second_completion.json()["data"]["id"] == first_completion.json()["data"]["id"]
    assert session.query(InvStockTransaction).filter_by(
        source_type="mfg_completion", source_id=work_order["id"]
    ).count() == 1


def test_work_order_return_restores_stock_and_released_order_can_be_cancelled(client_and_session):
    """A return must be ledger-backed, and cancelled work orders must reject further material movement."""
    client, session = client_and_session
    seed_work_order_data(session)
    create_approved_bom(client)
    work_order = create_released_work_order(client)
    issue = client.post(
        f"/api/production/work-orders/{work_order['id']}/issue",
        json={"items": [{"material_id": "component-1", "quantity": "4"}]},
        headers=headers(),
    )
    returned = client.post(
        f"/api/production/material-issues/{issue.json()['data']['id']}/return",
        json={"items": [{"material_id": "component-1", "quantity": "1"}]},
        headers=headers(),
    )
    cancelled = client.post(f"/api/production/work-orders/{work_order['id']}/cancel", headers=headers())
    issue_after_cancel = client.post(
        f"/api/production/work-orders/{work_order['id']}/issue",
        json={"items": [{"material_id": "component-1", "quantity": "1"}]},
        headers=headers(),
    )

    assert returned.json()["code"] == 0
    assert session.query(InvStockTransaction).filter_by(
        source_type="mfg_material_return", source_id=returned.json()["data"]["id"]
    ).count() == 1
    assert session.get(InvStock, "component-stock").quantity == Decimal("9.000000")
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert issue_after_cancel.json()["code"] == 400


def test_work_order_keeps_a_validated_mps_source_link(client_and_session):
    """Removing source ownership validation must reject a linked planning document instead of silently accepting it."""
    client, session = client_and_session
    seed_work_order_data(session)
    create_approved_bom(client)
    session.add(
        MfgMps(
            id="mps-source-1",
            org_id="org-1",
            doc_no="MPS-SOURCE-1",
            material_id="finished-1",
            warehouse_id="warehouse-1",
            plan_date=date(2026, 8, 2),
            plan_quantity=Decimal("5"),
        )
    )
    session.commit()

    created = client.post(
        "/api/production/work-orders",
        json={
            "material_id": "finished-1",
            "warehouse_id": "warehouse-1",
            "quantity": "5",
            "plan_date": "2026-08-02",
            "source_type": "mfg_mps",
            "source_id": "mps-source-1",
        },
        headers=headers(),
    )

    assert created.json()["code"] == 0
    assert created.json()["data"]["source_type"] == "mfg_mps"
    assert created.json()["data"]["source_id"] == "mps-source-1"


@pytest.mark.parametrize(
    "payload",
    [
        SimpleNamespace(good_quantity=Decimal("-1"), scrap_quantity=Decimal("2"), hours=Decimal("1")),
        SimpleNamespace(good_quantity=Decimal("2"), scrap_quantity=Decimal("-1"), hours=Decimal("1")),
    ],
)
def test_report_work_rejects_negative_quantities_without_pydantic(client_and_session, payload):
    """Removing service validation lets non-HTTP callers create invalid report totals."""
    client, session = client_and_session
    seed_work_order_data(session)
    create_approved_bom(client)
    work_order = create_released_work_order(client)

    with pytest.raises(AppError) as error:
        report_work(session, work_order["id"], payload, service_context(session))

    assert error.value.code == 400


def test_work_order_source_link_rejects_cross_org_unknown_and_incomplete_references(client_and_session):
    """Weak source validation permits a work order to point at foreign or nonexistent planning records."""
    client, session = client_and_session
    seed_work_order_data(session)
    create_approved_bom(client)
    session.add(
        MfgMps(
            id="mps-other-org",
            org_id="org-2",
            doc_no="MPS-OTHER-ORG",
            material_id="finished-1",
            warehouse_id="warehouse-1",
            plan_date=date(2026, 8, 2),
            plan_quantity=Decimal("5"),
        )
    )
    session.commit()
    payload = {
        "material_id": "finished-1",
        "warehouse_id": "warehouse-1",
        "quantity": "5",
        "plan_date": "2026-08-02",
        "source_type": "mfg_mps",
    }

    cross_org = client.post(
        "/api/production/work-orders", json={**payload, "source_id": "mps-other-org"}, headers=headers()
    )
    unknown = client.post(
        "/api/production/work-orders", json={**payload, "source_id": "mps-missing"}, headers=headers()
    )
    incomplete = client.post("/api/production/work-orders", json=payload, headers=headers())

    assert cross_org.json()["code"] == 404
    assert unknown.json()["code"] == 404
    assert incomplete.json()["code"] == 400


def test_sql_contains_complete_repeatable_work_order_schema_upgrade():
    """Dropping Task 3 bootstrap columns or guarded upgrades breaks existing MySQL installations."""
    sql = (Path(__file__).parents[2] / "database" / "init.sql").read_text(encoding="utf-8").lower()

    expected_columns = {
        "mfg_work_order": (
            "warehouse_id char(36) not null",
            "bom_id char(36) not null",
            "plan_date date not null",
            "reported_good_quantity decimal(18,6) not null default 0",
            "reported_scrap_quantity decimal(18,6) not null default 0",
            "completed_quantity decimal(18,6) not null default 0",
            "bom_snapshot json not null",
            "source_type varchar(64) null",
            "source_id char(36) null",
            "created_by char(36) null",
            "updated_by char(36) null",
        ),
        "mfg_work_order_material": (
            "returned_quantity decimal(18,6) not null default 0",
            "line_no int not null default 1",
        ),
            "mfg_material_issue": ("work_order_id char(36) null", "warehouse_id char(36) not null"),
        "mfg_material_issue_item": ("issue_id char(36) not null", "returned_quantity decimal(18,6) not null default 0"),
        "mfg_material_return": ("issue_id char(36) not null", "warehouse_id char(36) not null"),
        "mfg_material_return_item": ("return_id char(36) not null", "unit_cost decimal(18,6) not null default 0"),
        "mfg_work_report": (
            "good_quantity decimal(18,6) not null default 0",
            "scrap_quantity decimal(18,6) not null default 0",
            "hours decimal(18,6) not null default 0",
            "created_by char(36) null",
        ),
    }
    for table_name, columns in expected_columns.items():
        definition = sql.split(f"create table if not exists {table_name}", 1)[1].split("engine=", 1)[0]
        for column in columns:
            assert column in definition, f"{table_name}.{column}"

    assert "create procedure phase2_add_task3_column" in sql
    assert "call phase2_add_task3_column('mfg_work_order', 'warehouse_id'" in sql
    assert "call phase2_add_task3_column('mfg_work_report', 'scrap_quantity'" in sql
    for table_name in (
        "mfg_material_issue",
        "mfg_material_issue_item",
        "mfg_material_return",
        "mfg_material_return_item",
    ):
        assert f"call phase2_add_task3_column('{table_name}', 'is_deleted'" in sql
