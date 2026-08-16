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


def update_print_template(db: Session, template_id: str, payload: dict, context: UserContext) -> dict:
    row = db.get(CfgPrintTemplate, template_id)
    if row is None or row.org_id != context.org_id:
        raise AppError("打印模板不存在", code=404)
    business_type = str(payload.get("business_type") or row.business_type)
    name = str(payload.get("name") or row.name)
    template_html = str(payload.get("template_html") or row.template_html)
    status = str(payload.get("status") or row.status)
    if not business_type or not name or not template_html:
        raise AppError("业务类型、模板名称和模板内容不能为空", code=400)
    existing = db.scalar(
        select(CfgPrintTemplate).where(
            CfgPrintTemplate.org_id == context.org_id,
            CfgPrintTemplate.business_type == business_type,
            CfgPrintTemplate.name == name,
            CfgPrintTemplate.id != template_id,
        )
    )
    if existing:
        raise AppError("同业务类型下打印模板名称已存在", code=409)
    row.business_type = business_type
    row.name = name
    row.template_html = template_html
    row.status = status
    db.flush()
    return serialize_print_template(row)


def delete_print_template(db: Session, template_id: str, context: UserContext) -> None:
    row = db.get(CfgPrintTemplate, template_id)
    if row is None or row.org_id != context.org_id:
        raise AppError("打印模板不存在", code=404)
    db.delete(row)
    db.commit()


def render_document_print(
    db: Session,
    context: UserContext,
    *,
    business_type: str,
    business_id: str,
    template_id: str | None = None,
) -> dict:
    """Render a print template against a real business document.

    Returns the rendered HTML plus a small context so the caller can open a
    print preview window.  When ``template_id`` is omitted the latest active
    template for the business type is used.
    """
    from app.services.document_service import TYPE_CONFIG, _snapshot

    config = TYPE_CONFIG.get(business_type)
    if config is None:
        raise AppError("不支持打印该业务类型", code=404)
    row = db.get(config["model"], business_id)
    if row is None or getattr(row, "org_id", None) != context.org_id:
        raise AppError("业务单据不存在", code=404)
    if template_id:
        template = db.get(CfgPrintTemplate, template_id)
        if template is None or template.org_id != context.org_id:
            raise AppError("打印模板不存在", code=404)
    else:
        template = db.scalar(
            select(CfgPrintTemplate)
            .where(
                CfgPrintTemplate.org_id == context.org_id,
                CfgPrintTemplate.business_type == business_type,
                CfgPrintTemplate.status == "active",
            )
            .order_by(CfgPrintTemplate.id.desc())
            .limit(1)
        )
        if template is None:
            raise AppError("该业务类型未配置有效打印模板", code=404)
    document = _snapshot(db, business_type, row)
    model_dict = document.pop("summary_json", None) or {}
    for key, value in model_dict.items():
        document.setdefault(key, value)
    html = render_print_template(db, template.id, document)
    return {
        "template_id": template.id,
        "template_name": template.name,
        "business_type": business_type,
        "business_id": business_id,
        "doc_no": document.get("doc_no"),
        "title": document.get("title"),
        "html": html,
    }
