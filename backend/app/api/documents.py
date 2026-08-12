from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.schemas.documents import DocumentCommand, DocumentCommentCreate
from app.services.auth_service import UserContext
from app.services.document_service import (
    add_comment,
    delete_attachment,
    execute_command,
    get_attachment,
    get_document_workspace,
    list_documents,
    list_notifications,
    mark_notification_read,
    save_attachment,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])
notification_router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def documents(
    business_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    keyword: str | None = Query(default=None, max_length=128),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort: str = Query(default="-updated_at"),
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(list_documents(
        db, context, business_type=business_type, status=status, keyword=keyword,
        date_from=date_from, date_to=date_to, page=page, page_size=page_size, sort=sort,
    ))


@router.get("/attachments/{attachment_id}/download")
def download_attachment(
    attachment_id: str,
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row, path = get_attachment(db, context, attachment_id)
    return FileResponse(
        path,
        media_type=row.content_type,
        filename=row.file_name,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(row.file_name)}"},
    )


@router.delete("/attachments/{attachment_id}")
def remove_attachment(
    attachment_id: str,
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    delete_attachment(db, context, attachment_id)
    return ok({"id": attachment_id}, "附件已删除")


@router.get("/{business_type}/{business_id}")
def document_workspace(
    business_type: str,
    business_id: str,
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(get_document_workspace(db, context, business_type, business_id))


@router.post("/{business_type}/{business_id}/commands")
def run_command(
    business_type: str,
    business_id: str,
    payload: DocumentCommand,
    context: UserContext = Depends(require_permission("sales:manage")),
    db: Session = Depends(get_db),
):
    return ok(execute_command(db, context, business_type, business_id, payload.command))


@router.post("/{business_type}/{business_id}/comments")
def create_comment(
    business_type: str,
    business_id: str,
    payload: DocumentCommentCreate,
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = add_comment(db, context, business_type, business_id, payload.content)
    return ok({"id": row.id, "content": row.content, "author_name": row.author_name, "created_at": row.created_at.isoformat(timespec="seconds")})


@router.post("/{business_type}/{business_id}/attachments")
async def upload_attachment(
    business_type: str,
    business_id: str,
    file: UploadFile = File(...),
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    content = await file.read()
    row = save_attachment(db, context, business_type, business_id, file.filename or "attachment", file.content_type or "application/octet-stream", content)
    return ok({"id": row.id, "file_name": row.file_name, "content_type": row.content_type, "size_bytes": row.size_bytes, "download_url": f"/documents/attachments/{row.id}/download"})


@notification_router.get("")
def notifications(
    unread_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(list_notifications(db, context, unread_only, page, page_size))


@notification_router.post("/{notification_id}/read")
def read_notification(
    notification_id: str,
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok({"updated": mark_notification_read(db, context, notification_id)})


@notification_router.post("/read-all")
def read_all_notifications(
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok({"updated": mark_notification_read(db, context)})
