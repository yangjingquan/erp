from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_permission
from app.core.database import get_db
from app.core.response import ok
from app.models.configuration import CfgGlobalParameter
from app.services.auth_service import UserContext
from app.services.configuration_service import create_print_template, delete_print_template, list_print_templates, render_document_print, update_print_template

router = APIRouter(prefix="/api/config", tags=["configuration"])


@router.get("/print-templates")
def print_templates(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(list_print_templates(db, context))


@router.get("/print-templates/render")
def render_print(
    business_type: str = Query(min_length=1),
    business_id: str = Query(min_length=1),
    template_id: str | None = Query(default=None),
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ok(render_document_print(db, context, business_type=business_type, business_id=business_id, template_id=template_id))


@router.post("/print-templates")
def create_template(payload: dict, context: UserContext = Depends(require_permission("config:manage")), db: Session = Depends(get_db)):
    result = create_print_template(db, payload, context)
    db.commit()
    return ok(result, "打印模板已创建")


@router.put("/print-templates/{template_id}")
def update_template(template_id: str, payload: dict, context: UserContext = Depends(require_permission("config:manage")), db: Session = Depends(get_db)):
    result = update_print_template(db, template_id, payload, context)
    db.commit()
    return ok(result, "打印模板已更新")


@router.delete("/print-templates/{template_id}")
def delete_template(template_id: str, context: UserContext = Depends(require_permission("config:manage")), db: Session = Depends(get_db)):
    delete_print_template(db, template_id, context)
    return ok(msg="打印模板已删除")


@router.get("/field/{business_type}/{field_key}")
def field_definition(
    business_type: str,
    field_key: str,
    context: UserContext = Depends(require_permission("config:manage")),
    db: Session = Depends(get_db),
) -> dict:
    from app.services.configuration_service import get_field_definition

    return ok(get_field_definition(db, business_type, field_key, context))


@router.get("/parameters")
def parameters(context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    rows = db.query(CfgGlobalParameter).filter(CfgGlobalParameter.org_id == context.org_id).all()
    return ok([
        {
            "id": row.id,
            "parameter_key": row.parameter_key,
            "parameter_value": row.parameter_value,
            "value_type": row.value_type,
            "description": row.description,
        }
        for row in rows
    ])


@router.put("/parameters/{parameter_key}")
def update_parameter(
    parameter_key: str,
    payload: dict,
    context: UserContext = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    row = db.query(CfgGlobalParameter).filter(
        CfgGlobalParameter.org_id == context.org_id,
        CfgGlobalParameter.parameter_key == parameter_key,
    ).one_or_none()
    if row is None:
        row = CfgGlobalParameter(
            org_id=context.org_id,
            parameter_key=parameter_key,
            parameter_value=str(payload.get("parameter_value", "")),
            value_type=payload.get("value_type", "string"),
            description=payload.get("description"),
        )
        db.add(row)
    else:
        row.parameter_value = str(payload.get("parameter_value", ""))
        row.value_type = payload.get("value_type", row.value_type)
        row.description = payload.get("description", row.description)
    db.commit()
    db.refresh(row)
    return ok({"id": row.id, "parameter_key": row.parameter_key, "parameter_value": row.parameter_value})
