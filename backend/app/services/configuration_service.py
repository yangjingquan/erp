from datetime import date

from jinja2 import Template
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.configuration import CfgFieldDefinition, CfgNumberRule, CfgPrintTemplate
from app.services.auth_service import UserContext


def next_doc_no(db: Session, rule_key: str, org_id: str, document_date: date) -> str:
    rule = db.scalar(
        select(CfgNumberRule)
        .where(CfgNumberRule.rule_key == rule_key, CfgNumberRule.org_id == org_id)
        .with_for_update()
    )
    if rule is None:
        raise AppError(f"未配置单据编号规则：{rule_key}", code=400)
    date_key = document_date.strftime(rule.date_format or "%Y%m%d")
    if rule.current_date_key != date_key:
        rule.current_date_key = date_key
        rule.current_sequence = 0
    rule.current_sequence += 1
    db.flush()
    return f"{rule.prefix}{date_key}{rule.current_sequence:0{rule.sequence_length}d}"


def get_field_definition(
    db: Session,
    business_type: str,
    field_key: str,
    context: UserContext,
) -> dict:
    row = db.scalar(
        select(CfgFieldDefinition).where(
            CfgFieldDefinition.org_id == context.org_id,
            CfgFieldDefinition.business_type == business_type,
            CfgFieldDefinition.field_key == field_key,
        )
    )
    if row is None:
        return {"field_key": field_key, "visible": True, "required": False, "readonly": False}
    visible = row.visible and (
        not row.permission_code
        or context.user.is_superuser
        or row.permission_code in context.permissions
        or "*" in context.permissions
    )
    return {
        "field_key": row.field_key,
        "label": row.label,
        "field_type": row.field_type,
        "visible": visible,
        "required": row.required,
        "readonly": row.readonly,
        "config": row.config_json or {},
    }


def render_print_template(db: Session, template_id: str, document: dict) -> str:
    row = db.get(CfgPrintTemplate, template_id)
    if row is None or row.status != "active":
        raise AppError("打印模板不存在或已停用", code=404)
    return Template(row.template_html).render(**document)


def serialize_print_template(row: CfgPrintTemplate) -> dict:
    return {
        "id": row.id,
        "business_type": row.business_type,
        "name": row.name,
        "template_html": row.template_html,
        "status": row.status,
    }


def list_print_templates(db: Session, context: UserContext) -> list[dict]:
    rows = db.scalars(
        select(CfgPrintTemplate)
        .where(CfgPrintTemplate.org_id == context.org_id)
        .order_by(CfgPrintTemplate.name.asc())
    ).all()
    return [serialize_print_template(row) for row in rows]


def create_print_template(db: Session, payload: dict, context: UserContext) -> dict:
    existing = db.scalar(
        select(CfgPrintTemplate).where(
            CfgPrintTemplate.org_id == context.org_id,
            CfgPrintTemplate.business_type == payload.get("business_type"),
            CfgPrintTemplate.name == payload.get("name"),
        )
    )
    if existing:
        raise AppError("同业务类型下打印模板名称已存在", code=409)
    row = CfgPrintTemplate(
        org_id=context.org_id,
        business_type=str(payload.get("business_type") or ""),
        name=str(payload.get("name") or ""),
        template_html=str(payload.get("template_html") or ""),
        status=str(payload.get("status") or "active"),
    )
    if not row.business_type or not row.name or not row.template_html:
        raise AppError("业务类型、模板名称和模板内容不能为空", code=400)
    db.add(row)
    db.flush()
    return serialize_print_template(row)
