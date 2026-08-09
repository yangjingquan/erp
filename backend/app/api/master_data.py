from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.schemas.master_data import (
    CustomerCreate,
    MaterialCreate,
    SupplierCreate,
    TaxRateCreate,
    UnitCreate,
    WarehouseCreate,
)
from app.services.auth_service import UserContext
from app.services.master_data_service import (
    create_item,
    export_items,
    get_config,
    import_items,
    list_items,
    serialize_item,
    set_item_status,
    update_item,
)

router = APIRouter(prefix="/api/master", tags=["master-data"])

PAYLOAD_MODELS = {
    "materials": MaterialCreate,
    "customers": CustomerCreate,
    "suppliers": SupplierCreate,
    "warehouses": WarehouseCreate,
    "units": UnitCreate,
    "tax-rates": TaxRateCreate,
}


@router.get("/{resource}/export")
def export_master_data(
    resource: str,
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_config(resource)
    stream = export_items(db, resource, context.org_id)
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{resource}.xlsx"'},
    )


@router.get("/{resource}")
def list_master_data(
    resource: str,
    keyword: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=200, ge=1, le=500),
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = get_config(resource)
    rows, total, active, inactive = list_items(db, resource, context.org_id, keyword, page, page_size)
    return ok({"items": [serialize_item(item, config["fields"]) for item in rows], "total": total, "active": active, "inactive": inactive, "page": page, "page_size": page_size})


@router.post("/{resource}/import")
def import_master_data(
    resource: str,
    file: UploadFile = File(...),
    context: UserContext = Depends(require_permission("master:manage")),
    db: Session = Depends(get_db),
):
    result = import_items(db, resource, context.org_id, file.file, context.user)
    return ok(result, "导入完成")


@router.post("/{resource}")
def create_master_data(
    resource: str,
    payload: dict,
    context: UserContext = Depends(require_permission("master:manage")),
    db: Session = Depends(get_db),
):
    model_cls = PAYLOAD_MODELS.get(resource)
    if model_cls is None:
        get_config(resource)
        raise RuntimeError("主数据类型缺少校验模型")
    data = model_cls.model_validate(payload).model_dump()  # type: ignore[union-attr]
    item = create_item(db, resource, context.org_id, data, context.user)
    return ok(serialize_item(item, get_config(resource)["fields"]))


@router.put("/{resource}/{item_id}")
def update_master_data(resource: str, item_id: str, payload: dict, context: UserContext = Depends(require_permission("master:manage")), db: Session = Depends(get_db)):
    model_cls = PAYLOAD_MODELS.get(resource)
    if model_cls is None:
        get_config(resource)
        raise RuntimeError("主数据类型缺少校验模型")
    current = db.get(get_config(resource)["model"], item_id)
    if current is None or current.org_id != context.org_id:
        from app.core.exceptions import AppError
        raise AppError("主数据记录不存在", code=404)
    merged = {field: getattr(current, field, None) for field in get_config(resource)["fields"]}
    merged.update(payload)
    data = model_cls.model_validate(merged).model_dump()
    return ok(serialize_item(update_item(db, resource, item_id, context.org_id, data, context.user), get_config(resource)["fields"]))


@router.post("/{resource}/{item_id}/status")
def update_master_status(resource: str, item_id: str, payload: dict, context: UserContext = Depends(require_permission("master:manage")), db: Session = Depends(get_db)):
    row = set_item_status(db, resource, item_id, context.org_id, str(payload.get("status", "")), context.user)
    return ok(serialize_item(row, get_config(resource)["fields"]))
