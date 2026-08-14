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
from app.api.inventory_advanced import router as inventory_advanced_router
from app.api.finance import router as finance_router
from app.api.dashboard import router as dashboard_router
from app.api.analytics import router as analytics_router
from app.api.search import router as search_router
from app.api.backup import router as backup_router
from app.api.admin import router as admin_router
from app.api.production import router as production_router
from app.api.cost import router as cost_router
from app.api.crm import router as crm_router
from app.api.quality import router as quality_router
from app.api.hr import router as hr_router
from app.api.platform import router as platform_router
from app.api.phase2 import router as phase2_router
from app.api.documents import notification_router, router as documents_router
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.middleware.error_handler import register_exception_handlers
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.idempotency import IdempotencyMiddleware
from app.services.startup_check import check_schema
from app.services.runtime_migrations import (
    ensure_api_client_schema,
    ensure_employee_account_column,
    ensure_purchase_request_supplier_column,
    ensure_quality_inspection_columns,
    ensure_p1_control_schema,
    ensure_p0_wms_schema,
    ensure_p0_completion_schema,
    ensure_p1_p2_extension_schema,
)
from app.services.permission_service import ensure_permission_catalog

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI):
    db = SessionLocal()
    try:
        try:
            ensure_employee_account_column(db)
            ensure_purchase_request_supplier_column(db)
            ensure_api_client_schema(db)
            ensure_quality_inspection_columns(db)
            ensure_p1_control_schema(db)
            ensure_p0_wms_schema(db)
            ensure_p0_completion_schema(db)
            ensure_p1_p2_extension_schema(db)
            ensure_permission_catalog(db)
            # Permission catalog upgrades may insert page/function rows. Keep
            # the startup transaction short so SQLite/dev environments and
            # concurrent login requests are not blocked by the lifespan session.
            db.commit()
        except Exception:
            logging.getLogger("erp.startup").exception("运行时数据库字段迁移失败")
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
app.add_middleware(IdempotencyMiddleware)
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
app.include_router(inventory_advanced_router)
app.include_router(finance_router)
app.include_router(dashboard_router)
app.include_router(analytics_router)
app.include_router(search_router)
app.include_router(backup_router)
app.include_router(admin_router)
app.include_router(production_router)
app.include_router(cost_router)
app.include_router(crm_router)
app.include_router(quality_router)
app.include_router(hr_router)
app.include_router(platform_router)
app.include_router(phase2_router)
app.include_router(documents_router)
app.include_router(notification_router)
