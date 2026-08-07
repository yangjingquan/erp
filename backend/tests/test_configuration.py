from datetime import date

from app.models.configuration import CfgFieldDefinition, CfgNumberRule, CfgPrintTemplate
from app.services.configuration_service import get_field_definition, next_doc_no, render_print_template
from app.services.auth_service import UserContext


def test_number_rule_generates_sequential_configured_numbers(client_and_session):
    _, session = client_and_session
    from app.models.system import SysUser

    user = session.query(SysUser).one()
    session.add(
        CfgNumberRule(
            id="rule-1",
            org_id=user.org_id,
            rule_key="sales_order",
            prefix="SO",
            date_format="%Y%m%d",
            sequence_length=4,
            reset_cycle="day",
        )
    )
    session.commit()

    first = next_doc_no(session, "sales_order", user.org_id, date(2026, 8, 2))
    second = next_doc_no(session, "sales_order", user.org_id, date(2026, 8, 2))

    assert first == "SO202608020001"
    assert second == "SO202608020002"


def test_field_definition_hides_sensitive_field_without_permission(client_and_session):
    _, session = client_and_session
    from app.models.system import SysUser

    user = session.query(SysUser).one()
    session.add(
        CfgFieldDefinition(
            id="field-1",
            org_id=user.org_id,
            business_type="sales_order",
            field_key="cost_amount",
            label="成本金额",
            field_type="number",
            permission_code="sales:cost:view",
        )
    )
    session.commit()
    context = UserContext(user=user, permissions=set())

    definition = get_field_definition(session, "sales_order", "cost_amount", context)

    assert definition["visible"] is False


def test_print_template_renders_document_values(client_and_session):
    _, session = client_and_session
    from app.models.system import SysUser

    user = session.query(SysUser).one()
    template = CfgPrintTemplate(
        id="print-1",
        org_id=user.org_id,
        business_type="sales_order",
        name="销售订单",
        template_html="<h1>{{ doc_no }}</h1><p>{{ customer }}</p>",
    )
    session.add(template)
    session.commit()

    html = render_print_template(session, "print-1", {"doc_no": "SO001", "customer": "客户 A"})

    assert "SO001" in html
    assert "客户 A" in html


def test_print_template_api_lists_and_creates_templates(client_and_session):
    client, _ = client_and_session
    from app.core.security import create_access_token

    headers = {"Authorization": f"Bearer {create_access_token('user-1', ['config:manage'])}"}
    payload = {
        "business_type": "sales_order",
        "name": "销售订单打印",
        "template_html": "<h1>{{ doc_no }}</h1>",
        "status": "active",
    }

    created = client.post("/api/config/print-templates", json=payload, headers=headers)
    listed = client.get("/api/config/print-templates", headers=headers)

    assert created.json()["code"] == 0
    assert listed.json()["data"][0]["name"] == "销售订单打印"
