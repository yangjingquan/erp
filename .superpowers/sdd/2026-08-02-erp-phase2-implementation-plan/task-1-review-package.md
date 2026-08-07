# Task 1 review package (Git unavailable)

## Implementer report
# Task 1 Report: Phase-2 foundation, model registration, and repeatable initialization

## Scope delivered

Implemented the Task 1 foundation only:

- Registered the phase-2 platform model during application startup so SQLite test fixtures include it before `Base.metadata.create_all`.
- Added the `ExtEventOutbox` model and its `(event_type, aggregate_type, aggregate_id)` uniqueness contract.
- Added idempotent event emission, due pending-event claiming, and organization-scoped phase-2 parameter lookup with a caller-supplied default.
- Extended startup schema validation with the phase-2 production, inventory/cost, CRM, quality, HR, and outbox table contract.
- Extended `database/init.sql` with inert phase-2 table foundations, outbox uniqueness, repeatable menu/module/number-rule/parameter seeds.

No later-domain workflows, API routes, or business rules were added.

## Changed files

- `backend/app/models/__init__.py` — imports `ExtEventOutbox` to register the platform model.
- `backend/app/models/platform.py` — new outbox model and uniqueness constraint.
- `backend/app/main.py` — imports the model package before application startup.
- `backend/app/services/event_service.py` — new idempotent emit and pending-event claim service.
- `backend/app/services/phase2_parameter_service.py` — new parameter lookup with default fallback.
- `backend/app/services/startup_check.py` — adds the phase-2 required-table schema contract.
- `backend/tests/test_phase2_foundation.py` — new integration-style SQLite foundation tests.
- `database/init.sql` — phase-2 table names, outbox uniqueness, and repeatable phase-2 seed data.

## TDD evidence

### RED

Required command, run from `backend` before implementation:

```text
$ pytest tests/test_phase2_foundation.py -q
ImportError while loading conftest ...
E   ModuleNotFoundError: No module named 'fastapi'
```

The bare shell interpreter is not the project environment, so it cannot load the pre-existing FastAPI fixture. The project virtual environment then demonstrated the intended feature-level RED state before production code existed:

```text
$ ./.venv/bin/python -m pytest tests/test_phase2_foundation.py -q
ERROR collecting tests/test_phase2_foundation.py
E   ModuleNotFoundError: No module named 'app.models.platform'
1 error in 0.08s
```

The failing tests target these production breaks: absent phase-2 schema requirements, a missing outbox model/service, duplicate aggregate-event rows, claiming deferred events, and absent parameter defaulting.

### GREEN

```text
$ ./.venv/bin/python -m pytest tests/test_phase2_foundation.py -q && ./.venv/bin/python -m compileall -q app
....                                                                     [100%]
4 passed, 1 warning in 0.60s
```

`compileall` produced no output and exited 0. The sole warning is pre-existing FastAPI/TestClient deprecation output from the installed dependency stack.

Additional compatibility verification:

```text
$ ./.venv/bin/python -m pytest -q
........................................................                 [100%]
56 passed, 1 warning in 8.42s
```

## SQL contract verification

```text
$ rg -n "CREATE TABLE IF NOT EXISTS (mfg_|inv_(zone|location|batch|cost_layer)|cost_|crm_|qa_|hr_|ext_event_outbox)" database/init.sql
915:CREATE TABLE IF NOT EXISTS ext_event_outbox (
929:CREATE TABLE IF NOT EXISTS mfg_bom (
938:CREATE TABLE IF NOT EXISTS mfg_bom_item (
947:CREATE TABLE IF NOT EXISTS mfg_routing (
955:CREATE TABLE IF NOT EXISTS mfg_routing_operation (
963:CREATE TABLE IF NOT EXISTS mfg_work_order (
973:CREATE TABLE IF NOT EXISTS mfg_work_order_material (
982:CREATE TABLE IF NOT EXISTS mfg_work_report (
990:CREATE TABLE IF NOT EXISTS inv_zone (
999:CREATE TABLE IF NOT EXISTS inv_location (
1009:CREATE TABLE IF NOT EXISTS inv_batch (
1019:CREATE TABLE IF NOT EXISTS inv_cost_layer (
1031:CREATE TABLE IF NOT EXISTS cost_period_close (
1040:CREATE TABLE IF NOT EXISTS cost_allocation_rule (
1049:CREATE TABLE IF NOT EXISTS crm_lead (
1059:CREATE TABLE IF NOT EXISTS crm_opportunity (
1069:CREATE TABLE IF NOT EXISTS crm_contact (
1078:CREATE TABLE IF NOT EXISTS crm_activity (
1088:CREATE TABLE IF NOT EXISTS qa_inspection (
1099:CREATE TABLE IF NOT EXISTS qa_inspection_item (
1107:CREATE TABLE IF NOT EXISTS qa_nonconformance (
1116:CREATE TABLE IF NOT EXISTS hr_employee (
1126:CREATE TABLE IF NOT EXISTS hr_attendance (
1135:CREATE TABLE IF NOT EXISTS hr_leave_request (
1146:CREATE TABLE IF NOT EXISTS hr_payroll_run (
```

## Self-review

- The SQLAlchemy and MySQL outbox definitions both enforce the same aggregate-event uniqueness invariant.
- `emit_event` first looks up an existing row and flushes only a newly created one, so repeated calls in one transaction return the original event.
- `claim_pending_events` selects only `pending` rows whose retry time is absent or due, transitions selected rows to `processing`, and flushes so a subsequent claim will not return them.
- Parameter lookup is constrained by both organization and key, returning the documented caller default for a missing row or null stored value.
- The phase-2 SQL tables are foundation schemas only; no later production, inventory, cost, CRM, quality, or HR behavior was introduced.
- Existing test fixtures remain SQLite-compatible; the complete backend test suite passes in the committed project virtual environment.

## Concerns and environment limitations

- MySQL/Docker initialization was not executed. `docker version --format '{{.Server.Version}}'` could not access the local Docker socket: `permission denied while trying to connect to the docker API at unix:///Users/yangjingquan/.docker/run/docker.sock`. The SQL name contract was verified statically, but MySQL execution remains an environment-limited follow-up.
- The shell's bare `pytest` lacks FastAPI because its virtual environment is not activated. All verification used `backend/.venv/bin/python -m pytest`, which contains the project dependencies.
- No commit was created because this workspace has no usable Git metadata (`fatal: not a git repository`).

## Changed-file snapshot

### backend/app/models/__init__.py
"""SQLAlchemy model package."""

from app.models.business_extensions import (  # noqa: F401,E402
    PurchaseRequest,
    PurchaseRequestItem,
    PurchaseReturnItem,
    SalesQuote,
    SalesQuoteItem,
    SalesReturnItem,
)
from app.models.platform import ExtEventOutbox  # noqa: F401,E402

### backend/app/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.system import router as system_router
from app.api.master_data import router as master_data_router
from app.api.config import router as config_router
from app.api.workflow import router as workflow_router
from app.api.sales import router as sales_router
from app.api.purchase import router as purchase_router
from app.api.inventory import router as inventory_router
from app.api.finance import router as finance_router
from app.api.dashboard import router as dashboard_router
from app.api.search import router as search_router
from app.api.backup import router as backup_router
from app.api.admin import router as admin_router
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.middleware.error_handler import register_exception_handlers
from app.middleware.request_context import RequestContextMiddleware
from app.services.startup_check import check_schema

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    db = SessionLocal()
    try:
        schema_status = check_schema(db)
        application.state.schema_status = schema_status
        if not schema_status.connected:
            logging.getLogger("erp.startup").warning(
                "MySQL unavailable: %s", schema_status.guidance
            )
        elif not schema_status.initialized:
            logging.getLogger("erp.startup").warning(schema_status.guidance)
        yield
    finally:
        db.close()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_exception_handlers(app)
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(system_router)
app.include_router(master_data_router)
app.include_router(config_router)
app.include_router(workflow_router)
app.include_router(sales_router)
app.include_router(purchase_router)
app.include_router(inventory_router)
app.include_router(finance_router)
app.include_router(dashboard_router)
app.include_router(search_router)
app.include_router(backup_router)
app.include_router(admin_router)

### backend/app/services/startup_check.py
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
    "wf_definition",
    "cfg_number_rule",
    "sys_operation_log",
    "mfg_bom",
    "mfg_bom_item",
    "mfg_routing",
    "mfg_routing_operation",
    "mfg_work_order",
    "mfg_work_order_material",
    "mfg_work_report",
    "inv_zone",
    "inv_location",
    "inv_batch",
    "inv_cost_layer",
    "cost_period_close",
    "cost_allocation_rule",
    "crm_lead",
    "crm_opportunity",
    "crm_contact",
    "crm_activity",
    "qa_inspection",
    "qa_inspection_item",
    "qa_nonconformance",
    "hr_employee",
    "hr_attendance",
    "hr_leave_request",
    "hr_payroll_run",
    "ext_event_outbox",
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

### backend/app/models/platform.py
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDModel


class ExtEventOutbox(UUIDModel):
    __tablename__ = "ext_event_outbox"
    __table_args__ = (
        UniqueConstraint(
            "event_type",
            "aggregate_type",
            "aggregate_id",
            name="uk_ext_event_outbox_aggregate_event",
        ),
    )

    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(128), nullable=False)
    aggregate_id: Mapped[str] = mapped_column(String(36), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

### backend/app/services/event_service.py
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.platform import ExtEventOutbox


def emit_event(
    db: Session,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict,
) -> ExtEventOutbox:
    event = db.scalar(
        select(ExtEventOutbox).where(
            ExtEventOutbox.event_type == event_type,
            ExtEventOutbox.aggregate_type == aggregate_type,
            ExtEventOutbox.aggregate_id == aggregate_id,
        )
    )
    if event is not None:
        return event

    event = ExtEventOutbox(
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload_json=payload,
    )
    db.add(event)
    db.flush()
    return event


def claim_pending_events(db: Session, limit: int = 50) -> list[ExtEventOutbox]:
    if limit <= 0:
        return []

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    events = db.scalars(
        select(ExtEventOutbox)
        .where(
            ExtEventOutbox.status == "pending",
            or_(
                ExtEventOutbox.next_retry_at.is_(None),
                ExtEventOutbox.next_retry_at <= now,
            ),
        )
        .order_by(ExtEventOutbox.created_at, ExtEventOutbox.id)
        .limit(limit)
    ).all()
    for event in events:
        event.status = "processing"
    db.flush()
    return events

### backend/app/services/phase2_parameter_service.py
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.configuration import CfgGlobalParameter


def get_phase2_parameter(db: Session, org_id: str, key: str, default: str) -> str:
    parameter = db.scalar(
        select(CfgGlobalParameter).where(
            CfgGlobalParameter.org_id == org_id,
            CfgGlobalParameter.parameter_key == key,
        )
    )
    if parameter is None or parameter.parameter_value is None:
        return default
    return parameter.parameter_value

### backend/tests/test_phase2_foundation.py
from datetime import datetime, timedelta, timezone

from app.models.configuration import CfgGlobalParameter
from app.models.platform import ExtEventOutbox
from app.services.event_service import claim_pending_events, emit_event
from app.services.phase2_parameter_service import get_phase2_parameter
from app.services.startup_check import schema_status_from_tables


def test_phase2_tables_are_required_by_schema_contract():
    status = schema_status_from_tables({"sys_user", "sales_order"})

    assert "mfg_bom" in status.missing_tables
    assert "crm_lead" in status.missing_tables


def test_emit_event_is_idempotent_for_same_aggregate_and_type(client_and_session):
    _, session = client_and_session

    first = emit_event(
        session,
        "work_order.completed",
        "mfg_work_order",
        "wo-1",
        {"quantity": "2"},
    )
    second = emit_event(
        session,
        "work_order.completed",
        "mfg_work_order",
        "wo-1",
        {"quantity": "2"},
    )

    assert first.id == second.id
    assert session.query(ExtEventOutbox).count() == 1


def test_claim_pending_events_returns_only_due_pending_events(client_and_session):
    _, session = client_and_session
    due = emit_event(session, "work_order.released", "mfg_work_order", "wo-2", {})
    overdue = emit_event(session, "work_order.started", "mfg_work_order", "wo-3", {})
    deferred = emit_event(session, "work_order.paused", "mfg_work_order", "wo-4", {})
    overdue.next_retry_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    deferred.next_retry_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=1)
    session.flush()

    claimed = claim_pending_events(session, limit=10)

    assert {event.id for event in claimed} == {due.id, overdue.id}
    assert {event.status for event in claimed} == {"processing"}


def test_get_phase2_parameter_returns_configured_value_or_default(client_and_session):
    _, session = client_and_session
    session.add(
        CfgGlobalParameter(
            org_id="org-1",
            parameter_key="inventory.costing_method",
            parameter_value="fifo",
        )
    )
    session.flush()

    assert get_phase2_parameter(
        session, "org-1", "inventory.costing_method", "weighted_average"
    ) == "fifo"
    assert get_phase2_parameter(
        session, "org-1", "missing.parameter", "weighted_average"
    ) == "weighted_average"

### database/init.sql phase-2 references
911-  config_json JSON NULL,
912-  UNIQUE KEY uk_ext_openapi_endpoint_key (endpoint_key)
913-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
914-
915:CREATE TABLE IF NOT EXISTS ext_event_outbox (
916-  id CHAR(36) PRIMARY KEY,
917-  event_type VARCHAR(128) NOT NULL,
918-  aggregate_type VARCHAR(128) NOT NULL,
919-  aggregate_id CHAR(36) NOT NULL,
--
921-  status VARCHAR(32) NOT NULL DEFAULT 'pending',
922-  retry_count INT NOT NULL DEFAULT 0,
923-  next_retry_at DATETIME(6) NULL,
924-  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
925:  UNIQUE KEY uk_ext_event_outbox_aggregate_event (event_type, aggregate_type, aggregate_id),
926:  KEY idx_ext_event_outbox_status_retry (status, next_retry_at)
927-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
928-
929:CREATE TABLE IF NOT EXISTS mfg_bom (
930-  id CHAR(36) PRIMARY KEY,
931-  org_id CHAR(36) NOT NULL,
932-  material_id CHAR(36) NOT NULL,
933-  version VARCHAR(32) NOT NULL DEFAULT '1.0',
934-  status VARCHAR(32) NOT NULL DEFAULT 'draft',
935:  UNIQUE KEY uk_mfg_bom_material_version (org_id, material_id, version)
936-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
937-
938:CREATE TABLE IF NOT EXISTS mfg_bom_item (
939-  id CHAR(36) PRIMARY KEY,
940-  bom_id CHAR(36) NOT NULL,
941-  material_id CHAR(36) NOT NULL,
942-  quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
943-  line_no INT NOT NULL DEFAULT 1,
944:  KEY idx_mfg_bom_item_bom (bom_id)
945-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
946-
947:CREATE TABLE IF NOT EXISTS mfg_routing (
948-  id CHAR(36) PRIMARY KEY,
949-  org_id CHAR(36) NOT NULL,
950-  material_id CHAR(36) NOT NULL,
951-  status VARCHAR(32) NOT NULL DEFAULT 'draft',
952:  KEY idx_mfg_routing_material (org_id, material_id)
953-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
954-
955:CREATE TABLE IF NOT EXISTS mfg_routing_operation (
956-  id CHAR(36) PRIMARY KEY,
957-  routing_id CHAR(36) NOT NULL,
958-  operation_name VARCHAR(128) NOT NULL,
959-  line_no INT NOT NULL DEFAULT 1,
960:  KEY idx_mfg_routing_operation_routing (routing_id)
961-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
962-
963:CREATE TABLE IF NOT EXISTS mfg_work_order (
964-  id CHAR(36) PRIMARY KEY,
965-  org_id CHAR(36) NOT NULL,
966-  doc_no VARCHAR(64) NOT NULL,
967-  material_id CHAR(36) NOT NULL,
968-  quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
969-  status VARCHAR(32) NOT NULL DEFAULT 'draft',
970:  UNIQUE KEY uk_mfg_work_order_doc_no (org_id, doc_no)
971-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
972-
973:CREATE TABLE IF NOT EXISTS mfg_work_order_material (
974-  id CHAR(36) PRIMARY KEY,
975-  work_order_id CHAR(36) NOT NULL,
976-  material_id CHAR(36) NOT NULL,
977-  required_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
978-  issued_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
979:  KEY idx_mfg_work_order_material_order (work_order_id)
980-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
981-
982:CREATE TABLE IF NOT EXISTS mfg_work_report (
983-  id CHAR(36) PRIMARY KEY,
984-  work_order_id CHAR(36) NOT NULL,
985-  reported_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
986-  report_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
987:  KEY idx_mfg_work_report_order (work_order_id)
988-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
989-
990:CREATE TABLE IF NOT EXISTS inv_zone (
991-  id CHAR(36) PRIMARY KEY,
992-  org_id CHAR(36) NOT NULL,
993-  warehouse_id CHAR(36) NOT NULL,
994-  code VARCHAR(64) NOT NULL,
995-  name VARCHAR(128) NOT NULL,
996:  UNIQUE KEY uk_inv_zone_code (warehouse_id, code)
997-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
998-
999:CREATE TABLE IF NOT EXISTS inv_location (
1000-  id CHAR(36) PRIMARY KEY,
1001-  org_id CHAR(36) NOT NULL,
1002-  warehouse_id CHAR(36) NOT NULL,
1003-  zone_id CHAR(36) NULL,
1004-  code VARCHAR(64) NOT NULL,
1005-  name VARCHAR(128) NOT NULL,
1006:  UNIQUE KEY uk_inv_location_code (warehouse_id, code)
1007-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1008-
1009:CREATE TABLE IF NOT EXISTS inv_batch (
1010-  id CHAR(36) PRIMARY KEY,
1011-  org_id CHAR(36) NOT NULL,
1012-  material_id CHAR(36) NOT NULL,
1013-  batch_no VARCHAR(64) NOT NULL,
1014-  production_date DATE NULL,
1015-  expiry_date DATE NULL,
1016:  UNIQUE KEY uk_inv_batch_material_no (org_id, material_id, batch_no)
1017-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1018-
1019:CREATE TABLE IF NOT EXISTS inv_cost_layer (
1020-  id CHAR(36) PRIMARY KEY,
1021-  org_id CHAR(36) NOT NULL,
1022-  material_id CHAR(36) NOT NULL,
1023-  warehouse_id CHAR(36) NOT NULL,
1024-  source_type VARCHAR(64) NOT NULL,
1025-  source_id CHAR(36) NOT NULL,
1026-  remaining_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
1027-  unit_cost DECIMAL(18,6) NOT NULL DEFAULT 0,
1028:  KEY idx_inv_cost_layer_material (org_id, material_id, warehouse_id)
1029-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1030-
1031:CREATE TABLE IF NOT EXISTS cost_period_close (
1032-  id CHAR(36) PRIMARY KEY,
1033-  org_id CHAR(36) NOT NULL,
1034-  period VARCHAR(16) NOT NULL,
1035-  status VARCHAR(32) NOT NULL DEFAULT 'open',
1036-  closed_at DATETIME(6) NULL,
1037:  UNIQUE KEY uk_cost_period_close (org_id, period)
1038-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1039-
1040-CREATE TABLE IF NOT EXISTS cost_allocation_rule (
1041-  id CHAR(36) PRIMARY KEY,
--
1045-  status VARCHAR(32) NOT NULL DEFAULT 'active',
1046-  UNIQUE KEY uk_cost_allocation_rule_key (org_id, rule_key)
1047-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1048-
1049:CREATE TABLE IF NOT EXISTS crm_lead (
1050-  id CHAR(36) PRIMARY KEY,
1051-  org_id CHAR(36) NOT NULL,
1052-  name VARCHAR(128) NOT NULL,
1053-  source VARCHAR(64) NULL,
1054-  owner_id CHAR(36) NULL,
1055-  status VARCHAR(32) NOT NULL DEFAULT 'new',
1056:  KEY idx_crm_lead_owner_status (owner_id, status)
1057-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1058-
1059-CREATE TABLE IF NOT EXISTS crm_opportunity (
1060-  id CHAR(36) PRIMARY KEY,
--
1084-  occurred_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
1085-  KEY idx_crm_activity_owner_time (owner_id, occurred_at)
1086-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1087-
1088:CREATE TABLE IF NOT EXISTS qa_inspection (
1089-  id CHAR(36) PRIMARY KEY,
1090-  org_id CHAR(36) NOT NULL,
1091-  doc_no VARCHAR(64) NOT NULL,
1092-  source_type VARCHAR(64) NULL,
1093-  source_id CHAR(36) NULL,
1094-  status VARCHAR(32) NOT NULL DEFAULT 'draft',
1095-  result VARCHAR(32) NULL,
1096:  UNIQUE KEY uk_qa_inspection_doc_no (org_id, doc_no)
1097-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1098-
1099:CREATE TABLE IF NOT EXISTS qa_inspection_item (
1100-  id CHAR(36) PRIMARY KEY,
1101-  inspection_id CHAR(36) NOT NULL,
1102-  item_name VARCHAR(128) NOT NULL,
1103-  result VARCHAR(32) NULL,
1104:  KEY idx_qa_inspection_item_inspection (inspection_id)
1105-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1106-
1107-CREATE TABLE IF NOT EXISTS qa_nonconformance (
1108-  id CHAR(36) PRIMARY KEY,
--
1112-  description VARCHAR(500) NULL,
1113-  KEY idx_qa_nonconformance_inspection (inspection_id)
1114-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1115-
1116:CREATE TABLE IF NOT EXISTS hr_employee (
1117-  id CHAR(36) PRIMARY KEY,
1118-  org_id CHAR(36) NOT NULL,
1119-  employee_no VARCHAR(64) NOT NULL,
1120-  name VARCHAR(128) NOT NULL,
1121-  department_id CHAR(36) NULL,
1122-  status VARCHAR(32) NOT NULL DEFAULT 'active',
1123:  UNIQUE KEY uk_hr_employee_no (org_id, employee_no)
1124-) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
1125-
1126-CREATE TABLE IF NOT EXISTS hr_attendance (
1127-  id CHAR(36) PRIMARY KEY,
--
1230-('30000000-0000-0000-0000-000000000006', '00000000-0000-0000-0000-000000000001', 'sales_quote', 'QT', '%Y%m%d', 4, 'day'),
1231-('30000000-0000-0000-0000-000000000007', '00000000-0000-0000-0000-000000000001', 'purchase_request', 'PRQ', '%Y%m%d', 4, 'day'),
1232-('30000000-0000-0000-0000-000000000008', '00000000-0000-0000-0000-000000000001', 'purchase_return', 'PTR', '%Y%m%d', 4, 'day'),
1233-('30000000-0000-0000-0000-000000000009', '00000000-0000-0000-0000-000000000001', 'sales_return', 'STR', '%Y%m%d', 4, 'day'),
1234:('30000000-0000-0000-0000-000000000010', '00000000-0000-0000-0000-000000000001', 'mfg_work_order', 'WO', '%Y%m%d', 4, 'day'),
1235:('30000000-0000-0000-0000-000000000011', '00000000-0000-0000-0000-000000000001', 'qa_inspection', 'QI', '%Y%m%d', 4, 'day')
1236-ON DUPLICATE KEY UPDATE prefix = VALUES(prefix), date_format = VALUES(date_format), sequence_length = VALUES(sequence_length);
1237-
1238-INSERT INTO cfg_global_parameter (id, org_id, parameter_key, parameter_value, value_type, description)
1239-VALUES
1240:('50000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'inventory.costing_method', 'weighted_average', 'string', '库存成本计价方法'),
1241-('50000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 'mfg.allow_over_issue', 'false', 'boolean', '生产领料是否允许超发'),
1242-('50000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000001', 'qa.inspection_required', 'true', 'boolean', '质量检验是否必填')
1243-ON DUPLICATE KEY UPDATE parameter_value = VALUES(parameter_value), value_type = VALUES(value_type), description = VALUES(description);
1244-
1245-INSERT INTO ext_module_registry (id, module_key, module_name, phase, enabled)
1246-VALUES
1247:('40000000-0000-0000-0000-000000000001', 'production', '生产管理', 'phase2', 0),
1248:('40000000-0000-0000-0000-000000000002', 'crm', 'CRM', 'phase2', 0),
1249:('40000000-0000-0000-0000-000000000003', 'quality', '质量管理', 'phase2', 0),
1250:('40000000-0000-0000-0000-000000000004', 'hr', '人事考勤薪资', 'phase2', 0),
1251:('40000000-0000-0000-0000-000000000010', 'inventory_cost', '库存与成本', 'phase2', 0),
1252:('40000000-0000-0000-0000-000000000011', 'platform', '平台能力', 'phase2', 0),
1253-('40000000-0000-0000-0000-000000000005', 'group_org', '集团多组织', 'phase3', 0),
1254-('40000000-0000-0000-0000-000000000006', 'bi', 'BI 报表框架', 'phase3', 0),
1255-('40000000-0000-0000-0000-000000000007', 'ocr', 'OCR 发票识别', 'phase3', 0),
1256-('40000000-0000-0000-0000-000000000008', 'ai_alert', 'AI 预警', 'phase3', 0),
