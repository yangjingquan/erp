from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
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
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = get_config(resource)
    return ok([serialize_item(item, config["fields"]) for item in list_items(db, resource, context.org_id)])


@router.post("/{resource}/import")
def import_master_data(
    resource: str,
    file: UploadFile = File(...),
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = import_items(db, resource, context.org_id, file.file, context.user)
    return ok(result, "导入完成")


@router.post("/{resource}")
def create_master_data(
    resource: str,
    payload: dict,
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    model_cls = PAYLOAD_MODELS.get(resource)
    if model_cls is None:
        get_config(resource)
    data = model_cls.model_validate(payload).model_dump()  # type: ignore[union-attr]
    item = create_item(db, resource, context.org_id, data, context.user)
    return ok(serialize_item(item, get_config(resource)["fields"]))
