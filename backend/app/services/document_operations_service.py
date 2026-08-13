from __future__ import annotations

import csv
import logging
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.exceptions import AppError
from app.core.time import local_now
from app.models.collaboration import BizExportJob, BizSavedView
from app.models.system import SysUser
from app.services.auth_service import UserContext, build_user_context
from app.services.document_service import TYPE_CONFIG, _assert_type_access, execute_command, list_documents

EXPORT_ROOT = Path(__file__).resolve().parents[2] / "var" / "exports"
ALLOWED_FILTERS = {"status", "keyword", "date_from", "date_to", "sort"}
LOGGER = logging.getLogger("erp.document_export")


def _csv_cell(value: Any) -> Any:
    """Prevent spreadsheet clients from evaluating exported business text as a formula."""
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _clean_filters(filters: dict[str, Any]) -> dict[str, Any]:
    unknown = set(filters) - ALLOWED_FILTERS
    if unknown:
        raise AppError(f"不支持的筛选字段：{', '.join(sorted(unknown))}", code=400)
    result = {key: value for key, value in filters.items() if value not in (None, "", [])}
    result["sort"] = str(result.get("sort") or "-updated_at")
    if result["sort"].lstrip("-") not in {"updated_at", "document_date", "amount", "doc_no"}:
        raise AppError("不支持的排序字段", code=400)
    if result.get("keyword") and len(str(result["keyword"])) > 128:
        raise AppError("检索关键词不能超过 128 个字符", code=400)
    if result.get("status") and len(str(result["status"])) > 32:
        raise AppError("状态筛选不能超过 32 个字符", code=400)
    try:
        date_from = date.fromisoformat(str(result["date_from"])) if result.get("date_from") else None
        date_to = date.fromisoformat(str(result["date_to"])) if result.get("date_to") else None
    except ValueError as exc:
        raise AppError("日期筛选格式必须为 YYYY-MM-DD", code=400) from exc
    if date_from and date_to and date_from > date_to:
        raise AppError("开始日期不能晚于结束日期", code=400)
    return result


def list_saved_views(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(select(BizSavedView).where(
        BizSavedView.org_id == context.org_id,
        BizSavedView.is_deleted.is_(False),
        or_(BizSavedView.owner_id == context.id, BizSavedView.is_shared.is_(True)),
    ).order_by(BizSavedView.owner_id != context.id, BizSavedView.name)).all()
    return [{
        "id": row.id, "name": row.name, "business_type": row.business_type,
        "filters": row.filters_json, "is_shared": row.is_shared,
        "is_owner": row.owner_id == context.id,
    } for row in rows]


def create_saved_view(db: Session, payload, context: UserContext) -> BizSavedView:
    if payload.business_type:
        _assert_type_access(context, payload.business_type)
    name = payload.name.strip()
    if not name:
        raise AppError("保存视图名称不能为空", code=400)
    row = BizSavedView(
        org_id=context.org_id, owner_id=context.id, name=name,
        business_type=payload.business_type, filters_json=_clean_filters(payload.filters),
        is_shared=payload.is_shared,
    )
    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError as exc:
        raise AppError("已存在同名保存视图", code=409) from exc
    return row


def delete_saved_view(db: Session, view_id: str, context: UserContext) -> None:
    row = db.scalar(select(BizSavedView).where(
        BizSavedView.id == view_id, BizSavedView.org_id == context.org_id,
        BizSavedView.is_deleted.is_(False),
    ))
    if row is None:
        raise AppError("保存视图不存在", code=404)
    if row.owner_id != context.id and not context.user.is_superuser:
        raise AppError("只能删除自己创建的视图", code=403)
    row.is_deleted = True
    db.flush()


def create_export_job(db: Session, payload, context: UserContext) -> BizExportJob:
    if payload.business_type:
        _assert_type_access(context, payload.business_type)
    row = BizExportJob(
        org_id=context.org_id, owner_id=context.id, business_type=payload.business_type,
        filters_json=_clean_filters(payload.filters), status="pending",
    )
    db.add(row)
    db.flush()
    return row


def process_export_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.scalar(select(BizExportJob).where(BizExportJob.id == job_id).with_for_update())
        if job is None or job.status not in {"pending", "processing"}:
            return
        user = db.scalar(select(SysUser).where(SysUser.id == job.owner_id, SysUser.org_id == job.org_id, SysUser.is_deleted.is_(False)))
        if user is None:
            raise AppError("导出用户不存在", code=404)
        context = build_user_context(db, user)
        if job.business_type:
            _assert_type_access(context, job.business_type)
        job.status = "processing"
        db.commit()
        filters = dict(job.filters_json or {})
        date_from = date.fromisoformat(filters["date_from"]) if filters.get("date_from") else None
        date_to = date.fromisoformat(filters["date_to"]) if filters.get("date_to") else None
        rows: list[dict] = []
        page = 1
        while True:
            result = list_documents(
                db, context, business_type=job.business_type, status=filters.get("status"),
                keyword=filters.get("keyword"), date_from=date_from,
                date_to=date_to, page=page, page_size=200,
                sort=filters.get("sort", "-updated_at"),
            )
            rows.extend(result["items"])
            if len(rows) >= result["total"] or len(result["items"]) < 200:
                break
            page += 1
            if page > 250:
                raise AppError("单次导出最多支持 50000 条数据，请缩小筛选范围", code=400)
        file_key = f"{job.org_id}/{job.id}.csv"
        path = EXPORT_ROOT / file_key
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["业务类型", "单据编号", "标题", "状态", "单据日期", "业务对象", "金额", "更新时间"])
            for row in rows:
                writer.writerow([_csv_cell(value) for value in [
                    row.get("business_type"), row.get("doc_no"), row.get("title"), row.get("status_label"),
                    row.get("document_date"), row.get("party_name"), row.get("amount"), row.get("updated_at"),
                ]])
        job = db.get(BizExportJob, job_id)
        job.status = "completed"
        job.file_key = file_key
        job.file_name = f"ERP业务单据-{job.id[:8]}.csv"
        job.row_count = len(rows)
        job.completed_at = local_now()
        db.commit()
    except Exception as exc:
        LOGGER.exception("业务单据导出任务失败：%s", job_id)
        db.rollback()
        job = db.get(BizExportJob, job_id)
        if job is not None:
            job.status = "failed"
            job.error_message = str(exc)[:500]
            job.completed_at = local_now()
            db.commit()
    finally:
        db.close()


def list_export_jobs(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(select(BizExportJob).where(
        BizExportJob.org_id == context.org_id, BizExportJob.owner_id == context.id,
        BizExportJob.is_deleted.is_(False),
    ).order_by(BizExportJob.created_at.desc()).limit(20)).all()
    return [{
        "id": row.id, "business_type": row.business_type, "status": row.status,
        "file_name": row.file_name, "row_count": row.row_count,
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat(timespec="seconds"),
        "completed_at": row.completed_at.isoformat(timespec="seconds") if row.completed_at else None,
        "download_url": f"/documents/exports/{row.id}/download" if row.status == "completed" else None,
    } for row in rows]


def get_export_file(db: Session, job_id: str, context: UserContext) -> tuple[BizExportJob, Path]:
    row = db.scalar(select(BizExportJob).where(
        BizExportJob.id == job_id, BizExportJob.org_id == context.org_id,
        BizExportJob.owner_id == context.id, BizExportJob.is_deleted.is_(False),
    ))
    if row is None:
        raise AppError("导出任务不存在", code=404)
    if row.status != "completed" or not row.file_key:
        raise AppError("导出文件尚未生成", code=409)
    path = EXPORT_ROOT / row.file_key
    if not path.is_file():
        raise AppError("导出文件已丢失，请重新导出", code=404)
    return row, path


def run_bulk_command(db: Session, payload, context: UserContext) -> dict:
    if len(payload.business_ids) != len(set(payload.business_ids)):
        raise AppError("批量操作不能包含重复单据", code=400)
    results = []
    for business_id in payload.business_ids:
        try:
            data = execute_command(db, context, payload.business_type, business_id, payload.command)
            results.append({"business_id": business_id, "success": True, "data": data})
        except AppError as exc:
            db.rollback()
            results.append({"business_id": business_id, "success": False, "message": exc.msg, "code": exc.code})
    succeeded = sum(1 for item in results if item["success"])
    return {"items": results, "total": len(results), "succeeded": succeeded, "failed": len(results) - succeeded}
