import csv
import io
import json
from datetime import date
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.time import local_now
from app.models.collaboration import BizReportDefinition, BizReportRun
from app.schemas.analytics import ReportDefinitionCreate, ReportRunRequest
from app.services.auth_service import UserContext
from app.services.dashboard_service import dashboard_phase2, report_center


REPORT_CATALOG: dict[str, dict[str, str]] = {
    "management_kpi": {
        "name": "经营管理 KPI",
        "description": "销售履约、库存价值、应收风险、质量与生产完成率。",
    },
    "operations_kpi": {
        "name": "运营模块 KPI",
        "description": "生产、库存、CRM、质量、人力与项目成本的运营概览。",
    },
}


def _serialize_definition(row: BizReportDefinition | None, *, report_key: str, builtin: bool = False) -> dict:
    catalog = REPORT_CATALOG[report_key]
    return {
        "id": f"builtin:{report_key}" if builtin else row.id,
        "report_key": report_key,
        "name": row.name if row is not None else catalog["name"],
        "description": row.description if row is not None else catalog["description"],
        "parameters": row.parameters_json if row is not None else {"period": "YYYY-MM"},
        "status": row.status if row is not None else "active",
        "is_builtin": builtin,
        "created_at": row.created_at.isoformat() if row is not None else None,
    }


def list_report_definitions(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(
        select(BizReportDefinition)
        .where(BizReportDefinition.org_id == context.org_id, BizReportDefinition.is_deleted.is_(False))
        .order_by(BizReportDefinition.created_at.desc())
    ).all()
    by_key = {row.report_key: row for row in rows}
    return [
        _serialize_definition(by_key.get(key), report_key=key, builtin=key not in by_key)
        for key in REPORT_CATALOG
    ]


def create_report_definition(db: Session, payload: ReportDefinitionCreate, context: UserContext) -> BizReportDefinition:
    if payload.report_key not in REPORT_CATALOG:
        raise AppError("不支持的报表类型", code=400)
    row = db.scalar(
        select(BizReportDefinition).where(
            BizReportDefinition.org_id == context.org_id,
            BizReportDefinition.report_key == payload.report_key,
            BizReportDefinition.is_deleted.is_(False),
        )
    )
    if row is None:
        row = BizReportDefinition(
            org_id=context.org_id,
            report_key=payload.report_key,
            name=payload.name.strip(),
            description=payload.description.strip(),
            parameters_json=payload.parameters,
            owner_id=context.id,
        )
        db.add(row)
    else:
        row.name = payload.name.strip()
        row.description = payload.description.strip()
        row.parameters_json = payload.parameters
        row.status = "active"
        row.version += 1
    db.flush()
    return row


def _resolve_definition(db: Session, report_id: str, context: UserContext) -> tuple[str, str]:
    if report_id.startswith("builtin:"):
        report_key = report_id.removeprefix("builtin:")
        if report_key not in REPORT_CATALOG:
            raise AppError("报表不存在", code=404)
        return report_id, report_key
    row = db.scalar(
        select(BizReportDefinition).where(
            BizReportDefinition.id == report_id,
            BizReportDefinition.org_id == context.org_id,
            BizReportDefinition.status == "active",
            BizReportDefinition.is_deleted.is_(False),
        )
    )
    if row is None or row.report_key not in REPORT_CATALOG:
        raise AppError("报表不存在或已停用", code=404)
    return row.id, row.report_key


def _execute_report(db: Session, report_key: str, context: UserContext, request: ReportRunRequest) -> dict:
    period = request.period
    if report_key == "management_kpi":
        result = report_center(db, context, period)
    elif report_key == "operations_kpi":
        if not period:
            raise AppError("运营模块 KPI 必须指定期间", code=400)
        result = dashboard_phase2(db, context, period, request.warehouse_id)
    else:
        raise AppError("不支持的报表类型", code=400)
    return jsonable_encoder(result)


def run_report(db: Session, report_id: str, request: ReportRunRequest, context: UserContext) -> dict:
    definition_id, report_key = _resolve_definition(db, report_id, context)
    result = _execute_report(db, report_key, context, request)
    run = BizReportRun(
        org_id=context.org_id,
        report_definition_id=definition_id,
        report_key=report_key,
        requested_by=context.id,
        parameters_json=request.model_dump(exclude_none=True),
        status="completed",
        result_json=result,
    )
    db.add(run)
    db.flush()
    return serialize_run(run)


def list_report_runs(db: Session, context: UserContext, limit: int = 50) -> list[dict]:
    rows = db.scalars(
        select(BizReportRun)
        .where(BizReportRun.org_id == context.org_id, BizReportRun.is_deleted.is_(False))
        .order_by(BizReportRun.created_at.desc())
        .limit(max(1, min(limit, 100)))
    ).all()
    return [serialize_run(row, include_result=False) for row in rows]


def get_report_run(db: Session, run_id: str, context: UserContext) -> BizReportRun:
    row = db.scalar(
        select(BizReportRun).where(
            BizReportRun.id == run_id,
            BizReportRun.org_id == context.org_id,
            BizReportRun.is_deleted.is_(False),
        )
    )
    if row is None:
        raise AppError("报表运行记录不存在", code=404)
    return row


def serialize_run(row: BizReportRun, *, include_result: bool = True) -> dict:
    data = {
        "id": row.id,
        "report_definition_id": row.report_definition_id,
        "report_key": row.report_key,
        "parameters": row.parameters_json,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
        "error_message": row.error_message,
    }
    if include_result:
        data["result"] = row.result_json
    return data


def report_run_csv(row: BizReportRun) -> tuple[str, bytes]:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["report_key", "period", "section", "metric", "value"])
    period = row.parameters_json.get("period", "")
    result = row.result_json or {}
    for section, values in result.items():
        if isinstance(values, dict):
            for key, value in values.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                writer.writerow([row.report_key, period, section, key, value])
        else:
            writer.writerow([row.report_key, period, "", section, values])
    filename = f"{row.report_key}_{period or date.today().isoformat()}_{row.id[:8]}.csv"
    return filename, output.getvalue().encode("utf-8-sig")
