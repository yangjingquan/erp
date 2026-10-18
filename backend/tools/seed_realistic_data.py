"""Populate ERP business tables with coherent, realistic Chinese records.

It uses the existing SQLAlchemy models and keeps business keys and status
values suitable for a Chinese manufacturing company. It never changes login
users, roles, or role grants.
"""

from __future__ import annotations

import calendar
import argparse
import hashlib
import re
import secrets
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import (
    Boolean as SQLBoolean,
    Date as SQLDate,
    DateTime as SQLDateTime,
    Integer as SQLInteger,
    JSON as SQLJSON,
    MetaData,
    Numeric as SQLNumeric,
    String as SQLString,
    Table,
    Text as SQLText,
    UniqueConstraint,
    delete,
    func,
    insert,
    select,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import Base, engine
from app.models import *  # noqa: F401,F403 - registers the complete model catalog


ORG: str | None = None
ADMIN: str | None = None
DEPT: str | None = None

REALISTIC_NAMES: dict[str, list[str]] = {
    "md_unit": ["件", "套", "千克", "米", "台", "箱"],
    "md_tax_rate": ["标准货物税率", "设备服务税率", "运输服务税率", "出口零税率"],
    "md_material": [
        "伺服驱动器 SD-220", "铝合金安装底座 AL-104", "精密轴承 6204-Z",
        "安全继电器 SR-08", "工业连接器 CN-24", "不锈钢紧固件 M8",
    ],
    "md_customer": [
        "宁波宏越智能装备有限公司", "苏州恒启工业系统有限公司",
        "杭州嘉实自动化科技有限公司", "嘉兴远锋精密机械有限公司",
        "无锡东辰机电设备有限公司", "绍兴华信制造技术有限公司",
    ],
    "md_supplier": [
        "东莞信恒机电有限公司", "常州精研轴承有限公司", "宁波海岳金属制品有限公司",
        "苏州科拓电气有限公司", "嘉兴安达工业材料有限公司", "杭州锐通自动化有限公司",
    ],
    "md_warehouse": ["宁波主生产仓", "宁波售后备件仓", "苏州原材料仓", "杭州成品仓"],
    "hr_employee": ["陈晓宁", "周明远", "林若岚", "顾承宇", "许安琪", "沈嘉禾"],
    "hr_recruitment_candidate": ["梁诗涵", "唐嘉宁", "方昱辰", "叶舒妍", "罗景然", "蒋思齐"],
    "crm_lead": [
        "宁波宏越产线智能化升级", "苏州恒启精密装配自动化改造", "杭州嘉实智能仓储控制系统建设",
        "嘉兴远锋制造执行系统升级", "无锡东辰柔性装配线改造", "绍兴华信设备数据采集平台建设",
    ],
    "crm_opportunity": [
        "宁波宏越智能装配项目", "苏州恒启伺服单元改造项目", "杭州嘉实仓储升级项目",
        "嘉兴远锋产线改造项目", "无锡东辰备件框架采购", "绍兴华信设备联网项目",
    ],
    "project": [
        "宁波精密装配线数字化改造", "苏州智能仓储升级", "杭州售后备件中心建设",
        "嘉兴伺服单元国产化项目",
    ],
    "eam_asset": ["立式加工中心 VMC-850", "数控车床 NL-320", "自动锁螺丝工作站 AS-12", "空压机组 AC-75"],
    "mfg_work_center": ["精密加工一组", "机电装配二组", "成品检测工位", "包装与发运工位"],
    "mfg_routing": ["伺服单元装配工艺", "铝合金底座加工工艺", "驱动器老化验证工艺"],
    "qa_defect_catalog": ["装配尺寸偏差", "端子压接不良", "表面划伤", "电气绝缘异常"],
    "fin_account": ["银行存款", "应收账款", "主营业务收入", "管理费用", "应付账款", "主营业务成本"],
    "fin_currency": ["人民币", "美元", "欧元", "日元", "港币", "英镑"],
    "sys_api_client": [
        "仓储库存同步服务", "财务对账接口服务", "供应商协同门户接口",
        "客户订单接入服务", "生产进度同步服务", "售后服务数据接口",
    ],
    "ext_event_subscription": [
        "销售订单变更订阅", "库存预警订阅", "质量闭环订阅",
        "采购收货事件订阅", "生产工单进度订阅", "售后服务状态订阅",
    ],
    "fin_accounting_dimension": ["责任部门", "客户", "供应商", "员工", "项目", "自定义核算项"],
    "fin_asset": ["立式加工中心", "数控车床", "自动锁螺丝工作站", "空压机组", "三坐标测量仪", "智能仓储堆垛机"],
    "tax_code": ["一般货物税率", "交通运输服务税率", "技术服务税率", "小规模纳税人征收率", "免税项目", "出口零税率"],
    "low_code_definition": ["售后服务申请", "设备维修申请", "客户回访登记", "质量问题反馈", "备件领用申请", "服务合同变更"],
    "plm_change_request": ["伺服驱动器固件版本升级", "安装底座孔位公差优化", "轴承供应商切换评估", "安全继电器替代料导入", "连接器端子镀层调整", "紧固件表面处理变更"],
}

REALISTIC_FIELD_VALUES: dict[str, dict[str, list[object]]] = {
    "md_customer": {
        "short_name": ["宏越装备", "恒启工业", "嘉实自动化", "远锋精密", "东辰机电", "华信制造"],
        "contact_name": ["王静怡", "陈立新", "周婉清", "赵启航", "孙雅雯", "高志远"],
        "contact_phone": ["13862857314", "13906125487", "15851402863", "18605739142", "13771482605", "15157584306"],
        "address": [
            "浙江省宁波市鄞州区首南街道科创路88号",
            "江苏省苏州市工业园区星湖街218号",
            "浙江省杭州市滨江区江南大道3850号",
            "浙江省嘉兴市南湖区亚太路1001号",
            "江苏省无锡市新吴区菱湖大道200号",
            "浙江省绍兴市越城区袍江工业区三江路66号",
        ],
    },
    "md_supplier": {
        "short_name": ["信恒机电", "精研轴承", "海岳金属", "科拓电气", "安达材料", "锐通自动化"],
        "contact_name": ["刘海峰", "吴晓梅", "郑文博", "何雨桐", "马建国", "蒋思远"],
        "contact_phone": ["13751286420", "13915067248", "15857413906", "18605127834", "13586420719", "18958146027"],
        "address": [
            "广东省东莞市松山湖园区科技九路12号",
            "江苏省常州市武进区湖塘科技产业园创研路18号",
            "浙江省宁波市北仑区霞浦街道永定河路36号",
            "江苏省苏州市相城区高铁新城南天成路88号",
            "浙江省嘉兴市秀洲区高照街道桃园路168号",
            "浙江省杭州市钱塘区白杨街道20号大街600号",
        ],
    },
    "md_warehouse": {
        "address": [
            "浙江省宁波市鄞州区姜山镇明曙路188号",
            "浙江省宁波市鄞州区首南街道科创路88号西侧",
            "江苏省苏州市工业园区唯亭街道双马街6号",
            "浙江省杭州市钱塘区临江街道纬五路399号",
        ],
    },
    "crm_lead": {
        "source": ["宁波智能制造产业展会", "合作伙伴推荐", "企业官网咨询", "行业协会交流", "老客户转介绍", "技术研讨会"],
        "phone": ["13862857314", "13906125487", "15851402863", "18605739142", "13771482605", "15157584306"],
    },
    "inv_location": {
        "code": ["NB-A-01", "NB-B-01", "SZ-A-01", "HZ-P-01", "NB-A-02", "SZ-B-01"],
        "name": ["原料立体货架", "售后备件货架", "电气元件货架", "成品待发区", "装配辅料货架", "轴承专用货架"],
    },
    "inv_batch": {"batch_no": ["LOT-202610-001", "LOT-202610-002", "LOT-202610-003", "LOT-202610-004", "LOT-202610-005", "LOT-202610-006"]},
    "inv_warehouse_task": {"task_no": ["WT-202610-0001", "WT-202610-0002", "WT-202610-0003", "WT-202610-0004", "WT-202610-0005", "WT-202610-0006"]},
    "inv_pick_wave": {"wave_no": ["WAVE-202610-0001", "WAVE-202610-0002", "WAVE-202610-0003", "WAVE-202610-0004", "WAVE-202610-0005", "WAVE-202610-0006"]},
    "fin_accounting_dimension": {
        "code": ["DIM-DEPT", "DIM-CUSTOMER", "DIM-SUPPLIER", "DIM-EMPLOYEE", "DIM-PROJECT", "DIM-CUSTOM"],
        "dimension_type": ["department", "customer", "supplier", "employee", "project", "custom"],
    },
    "fin_bank_account": {
        "name": ["日常结算账户", "采购付款专户", "销售回款账户", "工资代发账户", "税费结算账户", "备用金账户"],
        "bank_name": ["宁波银行鄞州支行", "中国工商银行苏州工业园区支行", "中国建设银行杭州滨江支行", "招商银行宁波分行", "中国银行嘉兴分行", "交通银行绍兴分行"],
        "account_no": ["6212262026101001", "6222022600018426", "6217002026103289", "6225882026104612", "6216612026105374", "6222602026106841"],
    },
    "fin_asset": {
        "asset_name": ["立式加工中心 VMC-850", "数控车床 NL-320", "自动锁螺丝工作站 AS-12", "空压机组 AC-75", "三坐标测量仪 CMM-544", "智能仓储堆垛机 STK-20"],
        "category": ["生产设备", "生产设备", "自动化设备", "动力设备", "检测设备", "仓储设备"],
        "original_value": ["286000", "156000", "98000", "640000", "125000", "42000"],
        "accumulated_depreciation": ["57200", "156000", "24500", "640000", "25000", "42000"],
        "useful_life_months": [120, 120, 84, 120, 96, 120],
    },
    "fin_reconciliation_statement": {"statement_no": ["AR-REC-202610-001", "AP-REC-202610-001", "AR-REC-202610-002", "AP-REC-202610-002", "AR-REC-202610-003", "AP-REC-202610-003"]},
    "fin_bank_statement": {"statement_no": ["BANK-202610-0001", "BANK-202610-0002", "BANK-202610-0003", "BANK-202610-0004", "BANK-202610-0005", "BANK-202610-0006"]},
    "fin_bank_statement_line": {
        "counterparty": ["宁波宏越智能装备有限公司", "东莞信恒机电有限公司", "苏州恒启工业系统有限公司", "常州精研轴承有限公司", "杭州嘉实自动化科技有限公司", "宁波海岳金属制品有限公司"],
        "reference_no": ["SO-202610-0003", "PO-202610-0003", "SO-202610-0004", "PO-202610-0004", "SO-202610-0006", "PO-202610-0006"],
    },
    "mfg_bom": {"bom_version": ["V1.0", "V1.1", "V2.0", "V2.1", "V1.2", "V3.0"]},
    "hr_recruitment_candidate": {
        "candidate_no": ["CAN-202610-0001", "CAN-202610-0002", "CAN-202610-0003", "CAN-202610-0004", "CAN-202610-0005", "CAN-202610-0006"],
        "phone": ["13656148273", "15962140738", "18867132054", "13758046921", "18668271543", "15505817426"],
        "position": ["采购工程师", "机械设计工程师", "质量工程师", "设备维护工程师", "生产计划专员", "财务会计"],
        "source": ["社会招聘", "员工推荐", "招聘网站", "校园招聘", "行业人才交流会", "猎头推荐"],
    },
    "eam_asset": {
        "asset_name": ["立式加工中心 VMC-850", "数控车床 NL-320", "自动锁螺丝工作站 AS-12", "空压机组 AC-75"],
        "serial_no": ["VMC850-NB-240318", "NL320-SZ-231106", "AS12-HZ-240522", "AC75-JX-220914"],
        "location": ["宁波主生产仓·机加工车间", "苏州原材料仓·精密加工区", "杭州成品仓·装配线二工位", "嘉兴动力站房·空压机房"],
    },
    "eam_maintenance_plan": {"name": ["主轴润滑与精度校准", "刀塔检查与导轨保养", "锁付扭矩校验", "空压机滤芯与压力检查", "测量系统年度校准", "堆垛机轨道巡检"]},
    "cfg_print_template": {
        "name": ["销售订单正式版", "采购订单正式版", "销售出库单", "采购入库单", "生产工单流转单", "会计凭证标准版"],
        "business_type": ["sales_order", "purchase_order", "sales_delivery", "purchase_receipt", "mfg_work_order", "fin_voucher"],
    },
    "org_intercompany_transaction": {"transaction_no": ["IC-202610-0001", "IC-202610-0002", "IC-202610-0003", "IC-202610-0004", "IC-202610-0005", "IC-202610-0006"]},
    "tax_code": {"code": ["VAT-13", "VAT-09", "VAT-06", "VAT-03", "VAT-EXEMPT", "VAT-EXPORT"], "rate": ["13", "9", "6", "3", "0", "0"]},
    "tax_invoice": {"invoice_no": ["25332000000000128461", "25332000000000128479", "25332000000000128508", "25332000000000128516", "25332000000000128524", "25332000000000128532"]},
    "low_code_definition": {"object_key": ["after_sales_request", "equipment_repair", "customer_visit", "quality_feedback", "spare_part_request", "service_contract_change"]},
    "plm_change_request": {"title": ["伺服驱动器固件版本升级", "安装底座孔位公差优化", "轴承供应商切换评估", "安全继电器替代料导入", "连接器端子镀层调整", "紧固件表面处理变更"]},
    "plm_product_revision": {
        "revision": ["SD-220 Rev.C", "AL-104 Rev.B", "6204-Z Rev.D", "SR-08 Rev.B", "CN-24 Rev.C", "M8 Rev.F"],
        "change_summary": [
            "提升驱动器低速运行稳定性", "优化底座安装孔位公差", "更新轴承润滑等级与供应来源",
            "完成安全继电器替代料认证验证", "改善连接器端子耐腐蚀镀层工艺", "提高紧固件表面处理耐盐雾性能",
        ],
    },
}

TABLE_LABELS = {
    "sales_quote": "设备报价", "sales_order": "客户订单", "sales_delivery": "销售发货",
    "sales_return": "客户退货", "purchase_request": "采购申请", "purchase_order": "供应商订单",
    "purchase_receipt": "采购收货", "purchase_return": "采购退货", "qa_inspection": "质量检验",
    "qa_nonconformance": "质量异常", "mfg_bom": "产品物料清单", "mfg_work_order": "生产工单",
    "fin_expense": "差旅报销", "fin_voucher": "会计凭证", "hr_leave_request": "员工请假申请",
    "crm_follow_up": "客户跟进记录", "svc_case": "客户服务工单", "plm_change_request": "产品变更申请",
    "biz_document": "业务单据", "tms_shipment": "华东区域配送任务",
}

SEED_COUNTS = {
    "md_unit": 6, "md_tax_rate": 4, "md_material": 6, "md_customer": 6,
    "md_supplier": 6, "md_warehouse": 4, "hr_employee": 6, "eam_asset": 4,
    "project": 4, "mfg_work_center": 4, "mfg_routing": 3, "qa_defect_catalog": 4,
    "sales_quote": 6, "sales_order": 6, "sales_delivery": 3, "sales_return": 1,
    "sales_order_item": 6, "sales_delivery_item": 3, "sales_return_item": 1,
    "sales_receivable": 3,
    "purchase_request": 6, "purchase_order": 6, "purchase_receipt": 3, "purchase_return": 1,
    "purchase_order_item": 6, "purchase_receipt_item": 3, "purchase_return_item": 1,
    "purchase_payable": 3, "fin_receipt": 2, "fin_receipt_reconcile": 2,
    "fin_payment": 2, "fin_payment_reconcile": 2,
    "inv_stock_transaction": 8,
    "mfg_bom": 6, "mfg_mps": 4, "mfg_mrp_run": 4, "mfg_plan_run": 4,
    "mfg_work_order": 6, "qa_inspection": 6, "fin_voucher": 6,
    "fin_voucher_entry": 12,
    # One retained login user can only have one access row per warehouse.
    "inv_warehouse_access": 4,
}


def seed_count(table_name: str) -> int:
    return SEED_COUNTS.get(table_name, 6)


SALES_DELIVERY_ORDER_INDEX = (3, 4, 6)
PURCHASE_RECEIPT_ORDER_INDEX = (3, 4, 6)


def order_amount(index: int) -> Decimal:
    return Decimal(str(42000 + index * 8500)).quantize(Decimal("0.01"))


def ordered_table_names(metadata: MetaData, skip: set[str]) -> list[str]:
    included = set(metadata.tables) - skip
    dependencies = {
        name: {
            foreign_key.target_fullname.rsplit(".", 1)[0].rsplit(".", 1)[-1]
            for foreign_key in Base.metadata.tables.get(name, metadata.tables[name]).foreign_keys
            if foreign_key.target_fullname.rsplit(".", 1)[0].rsplit(".", 1)[-1] in included
            and foreign_key.target_fullname.rsplit(".", 1)[0].rsplit(".", 1)[-1] != name
        }
        for name in included
    }
    ordered: list[str] = []
    remaining = set(included)
    while remaining:
        ready = sorted(name for name in remaining if not (dependencies[name] & remaining))
        if not ready:
            # Cyclic optional references use deterministic IDs and are checked
            # again against the live foreign-key graph after the seed completes.
            ready = [min(remaining)]
        ordered.extend(ready)
        remaining.difference_update(ready)
    return ordered


def uid(table: str, index: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"erp-realistic/{table}/{index}"))


def month_value(index: int) -> str:
    month = (index % 18) + 1
    year = 2026 + (month - 1) // 12
    return f"{year:04d}-{((month - 1) % 12) + 1:02d}"


def insert_if_absent(connection, table: Table, values: dict[str, object]) -> None:
    row_id = values.get("id")
    if row_id is not None and connection.scalar(select(table.c.id).where(table.c.id == row_id)):
        return
    connection.execute(insert(table).values({key: value for key, value in values.items() if key in table.c}))


def clear_business_rows_and_rebuild_catalog(metadata: MetaData, connection) -> None:
    """Clear all rows except retained identity/grant tables, then restore the catalog IDs."""
    keep = {"sys_user", "sys_role", "sys_user_role", "sys_role_menu", "sys_role_permission"}
    menu_table = metadata.tables["sys_menu"]
    permission_table = metadata.tables["sys_permission"]
    menu_rows = [dict(row) for row in connection.execute(select(menu_table)).mappings()]
    permission_rows = [dict(row) for row in connection.execute(select(permission_table)).mappings()]
    if not menu_rows or not permission_rows:
        raise RuntimeError("现有菜单或权限目录为空，无法在保留角色授权的前提下重建")

    preserved_user_roles = [tuple(row) for row in connection.execute(select(metadata.tables["sys_user_role"]))]
    preserved_role_permissions = [tuple(row) for row in connection.execute(select(metadata.tables["sys_role_permission"]))]
    preserved_role_menus = [tuple(row) for row in connection.execute(select(metadata.tables["sys_role_menu"]))]

    for name in sorted(metadata.tables):
        if name not in keep:
            connection.execute(delete(metadata.tables[name]))

    connection.execute(insert(menu_table), menu_rows)
    connection.execute(insert(permission_table), permission_rows)

    from app.services.permission_service import ensure_permission_catalog

    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        ensure_permission_catalog(session)
        session.flush()
        session.commit()

    if preserved_user_roles != [tuple(row) for row in connection.execute(select(metadata.tables["sys_user_role"]))]:
        raise RuntimeError("用户角色关联在菜单重建后发生变化")
    if preserved_role_permissions != [tuple(row) for row in connection.execute(select(metadata.tables["sys_role_permission"]))]:
        raise RuntimeError("角色权限关联在菜单重建后发生变化")
    current_role_menus = {tuple(row) for row in connection.execute(select(metadata.tables["sys_role_menu"]))}
    if not set(preserved_role_menus).issubset(current_role_menus):
        raise RuntimeError("原有角色菜单授权未完整恢复")


def ensure_preserved_user_context(metadata: MetaData, connection) -> None:
    """Recreate only the org and department rows referenced by retained users/roles."""
    global ORG, ADMIN, DEPT
    users_table = metadata.tables["sys_user"]
    roles_table = metadata.tables["sys_role"]
    org_table = metadata.tables["sys_org"]
    department_table = metadata.tables["sys_department"]
    membership_table = metadata.tables["sys_org_membership"]
    now = datetime.now()

    users = connection.execute(
        select(users_table.c.id, users_table.c.org_id, users_table.c.department_id).order_by(users_table.c.id)
    ).mappings().all()
    role_org_ids = connection.execute(select(roles_table.c.org_id)).scalars().all()
    if not users:
        raise RuntimeError("保留的登录用户表为空，无法建立业务数据操作人上下文")

    ADMIN = str(users[0]["id"])
    primary_org_id = users[0]["org_id"] or (role_org_ids[0] if role_org_ids else uid("sys_org", 1))
    ORG = str(primary_org_id)
    referenced_orgs = list(dict.fromkeys(
        [str(user["org_id"]) for user in users if user["org_id"]]
        + [str(org_id) for org_id in role_org_ids if org_id]
    )) or [ORG]

    org_names = ["宁波澄海智能装备有限公司", "苏州恒启工业系统有限公司", "杭州嘉实自动化科技有限公司"]
    for index, org_id in enumerate(referenced_orgs, start=1):
        insert_if_absent(connection, org_table, {
            "id": org_id, "code": f"ORG-{org_id.replace('-', '')[:8].upper()}",
            "name": org_names[(index - 1) % len(org_names)], "parent_id": None,
            "status": "active", "created_at": now, "updated_at": now,
        })

    # Group transactions need actual organizations to resolve their names.
    # These records do not grant user membership or cross-organization access.
    for index, (org_id, code, org_name) in enumerate([
        (uid("sys_org", 2), "ORG-SUZHOU-HQ", "苏州恒启工业系统有限公司"),
        (uid("sys_org", 3), "ORG-HANGZHOU-JS", "杭州嘉实自动化科技有限公司"),
    ], start=2):
        insert_if_absent(connection, org_table, {
            "id": org_id, "code": code, "name": org_name, "parent_id": ORG,
            "status": "active", "created_at": now, "updated_at": now,
        })

    departments_by_id: dict[str, str] = {}
    for index, user in enumerate(users, start=1):
        org_id = str(user["org_id"] or ORG)
        department_id = str(user["department_id"] or uid("sys_department", index))
        departments_by_id.setdefault(department_id, org_id)
    if not departments_by_id:
        departments_by_id[uid("sys_department", 1)] = ORG
    DEPT = next(iter(departments_by_id))
    department_names = ["供应链管理部", "智能制造部", "质量与工艺部", "财务管理部"]
    for index, (department_id, org_id) in enumerate(departments_by_id.items(), start=1):
        insert_if_absent(connection, department_table, {
            "id": department_id, "org_id": org_id,
            "code": f"DPT-{department_id.replace('-', '')[:8].upper()}",
            "name": department_names[(index - 1) % len(department_names)],
            "parent_id": None, "manager_id": ADMIN, "status": "active",
            "created_at": now, "updated_at": now,
        })

    for index, user in enumerate(users, start=1):
        org_id = str(user["org_id"] or ORG)
        insert_if_absent(connection, membership_table, {
            "id": uid("sys_org_membership", index), "user_id": str(user["id"]),
            "org_id": org_id, "membership_type": "member", "is_default": True,
            "status": "active", "created_at": now, "updated_at": now,
        })


# Realistic per-table status/type pools so that seeded rows can participate in
# the documented state machines instead of being stuck at a single sentinel
# value.  Values are cycled by index.  Master-data tables intentionally fall
# back to the "active/inactive" default defined in ENUM_FALLBACK.
STATUS_POOLS: dict[str, dict[str, list[str]]] = {
    "sales_quote": {"status": ["draft", "submitted", "approved", "rejected"]},
    "sales_order": {"status": ["draft", "submitted", "completed", "completed", "rejected", "completed"]},
    "sales_delivery": {"status": ["draft", "completed"]},
    "sales_return": {"status": ["draft", "submitted", "completed"]},
    "sales_receivable": {"status": ["open", "partial", "settled"], "source_type": ["sales_delivery"]},
    "purchase_request": {"status": ["draft", "submitted", "approved", "rejected"]},
    "purchase_order": {"status": ["draft", "submitted", "partially_received", "completed", "rejected", "completed"]},
    "purchase_receipt": {"status": ["draft", "completed"]},
    "purchase_return": {"status": ["draft", "submitted", "completed"]},
    "purchase_payable": {"status": ["open", "partial", "settled"], "source_type": ["purchase_receipt"]},
    "fin_receipt": {"status": ["draft", "confirmed", "partial", "settled"]},
    "fin_payment": {"status": ["draft", "confirmed", "partial", "settled"]},
    "fin_expense": {"status": ["draft", "submitted", "approved", "settled"]},
    "fin_voucher": {"status": ["draft", "posted", "reversed"]},
    "fin_account": {"status": ["active", "inactive"]},
    "fin_budget": {"status": ["draft", "approved"]},
    "fin_cash_forecast": {"status": ["draft", "approved"]},
    "fin_reconciliation_statement": {"status": ["draft", "confirmed"]},
    "fin_bank_statement": {"status": ["imported", "matched"]},
    "fin_bank_statement_line": {"status": ["unmatched", "matched", "partial"]},
    "fin_asset": {"status": ["active", "scrapped"]},
    "fin_asset_depreciation": {"status": ["posted"]},
    "fin_fiscal_period": {"status": ["open", "closed"]},
    "fin_period_close_checklist": {"status": ["pending", "completed"]},
    "mfg_bom": {"status": ["draft", "submitted", "approved", "disabled"]},
    "mfg_mps": {"status": ["draft", "planned"]},
    "mfg_mrp_run": {"status": ["draft", "completed"]},
    "mfg_mrp_result": {"status": ["pending", "confirmed"]},
    "mfg_plan_run": {"status": ["draft", "completed"]},
    "mfg_plan_exception": {"status": ["open", "resolved"], "severity": ["low", "medium", "high"], "exception_type": ["capacity_overload", "material_shortage"]},
    "mfg_demand_line": {"status": ["open", "confirmed", "cancelled"], "source_type": ["sales_order", "sales_quote"]},
    "mfg_alternate_material": {"status": ["approved", "rejected"]},
    "mfg_work_order_cost": {"status": ["calculated", "posted"]},
    "mfg_subcontract_receipt": {"status": ["completed"]},
    "mfg_planned_order": {"status": ["pending", "confirmed", "ignored"], "order_type": ["purchase", "manufacture"]},
    "mfg_work_order": {"status": ["draft", "released", "in_progress", "completed"]},
    "mfg_routing": {"status": ["draft", "submitted", "approved", "disabled"]},
    "mfg_work_center": {"status": ["active", "inactive"]},
    "mfg_subcontract_order": {"status": ["draft", "released", "completed", "cancelled"]},
    "mfg_work_order_exception": {"status": ["open", "resolved"], "severity": ["high", "medium", "low"]},
    "mfg_work_order_schedule": {"status": ["planned", "completed"]},
    "qa_inspection": {"status": ["draft", "submitted", "completed", "closed"], "inspection_type": ["incoming", "process", "final"], "result": ["passed", "failed"], "disposition": ["accept", "rework", "scrap", "return_to_supplier"]},
    "qa_nonconformance": {"status": ["open", "investigating", "closed"], "severity": ["minor", "major", "critical"], "disposition": ["rework", "accept", "scrap", "return_to_supplier"]},
    "qa_defect_catalog": {"status": ["active", "inactive"], "severity": ["minor", "major", "critical"]},
    "qa_plan": {"status": ["draft", "active"]},
    "qa_capa_action": {"status": ["open", "completed"], "action_type": ["corrective", "preventive"]},
    "qa_supplier_quality": {"status": ["submitted", "reviewed", "confirmed"], "capa_status": ["not_required", "pending", "in_progress", "closed"]},
    "qa_quality_cost": {"status": ["estimated", "confirmed"], "cost_type": ["prevention", "appraisal", "internal_failure", "external_failure"]},
    "qa_spc_exception": {"status": ["pending_review", "containment", "root_cause", "corrective_action", "retest", "closed"], "control_status": ["out_of_control", "in_control"]},
    "qa_customer_claim": {"status": ["open", "investigating", "approved", "rejected", "closed"]},
    "qa_spc_record": {"status": ["in_control", "out_of_control"]},
    "crm_lead": {"status": ["new", "contacted", "qualified", "converted", "lost"]},
    "crm_opportunity": {"stage": ["new", "prospecting", "negotiation", "won", "lost"]},
    "hr_employee": {"status": ["active", "inactive"]},
    "hr_employee_lifecycle": {"event_type": ["hired", "promoted", "transferred", "terminated"], "from_status": ["active", "active", "active", "active"], "to_status": ["active", "active", "inactive", "inactive"]},
    "hr_performance_review": {"status": ["draft", "submitted", "approved"], "rating": ["pending", "excellent", "good", "needs_improvement"]},
    "hr_leave_request": {
        "status": ["draft", "submitted", "approved", "rejected"],
        "leave_type": ["annual", "sick", "personal", "compensatory"],
    },
    "hr_attendance": {"status": ["present", "absent", "late", "leave"]},
    "hr_payroll_run": {"status": ["draft", "approved", "paid"]},
    "hr_benefit_record": {"status": ["active", "inactive"]},
    "hr_recruitment_candidate": {"status": ["new", "interview", "hired", "rejected"]},
    "eam_asset": {"status": ["active", "inactive"]},
    "eam_work_order": {"status": ["open", "assigned", "in_progress", "resolved", "closed"]},
    "eam_maintenance_plan": {"status": ["active", "inactive"]},
    "svc_case": {"status": ["open", "assigned", "in_progress", "resolved", "closed"]},
    "svc_contract": {"status": ["draft", "active", "expired"]},
    "svc_visit": {"status": ["scheduled", "completed"]},
    "plm_change_request": {"status": ["draft", "submitted", "approved", "effective"]},
    "plm_change_order": {"status": ["draft", "approved", "effective"]},
    "plm_change_impact": {"status": ["pending", "applied", "rejected"]},
    "plm_product_revision": {"status": ["draft", "submitted", "effective", "obsolete"]},
    "srm_rfq": {"status": ["draft", "quoted", "accepted"]},
    "srm_supplier_score": {"status": ["draft", "confirmed"]},
    "tax_code": {"status": ["active", "inactive"]},
    "tax_invoice": {"status": ["draft", "submitted", "issued", "red_issued"]},
    "org_intercompany_transaction": {"status": ["draft", "confirmed"]},
    "project": {"status": ["draft", "active", "closed"]},
    "project_milestone": {"status": ["pending", "completed"]},
    "project_wbs": {"status": ["open", "in_progress", "completed"]},
    "low_code_definition": {"status": ["draft", "published"]},
    "metric_definition": {"status": ["draft", "published"]},
    "ai_exception_alert": {"status": ["open", "resolved"], "severity": ["low", "medium", "high"]},
    "sys_api_client": {"status": ["active", "disabled"]},
    "ext_event_outbox": {"status": ["pending", "processed", "failed"]},
    "ext_event_delivery": {"status": ["pending", "delivered", "failed"]},
    "ext_event_subscription": {"status": ["active", "disabled"]},
    "inv_transfer": {"status": ["draft", "approved", "completed"]},
    "inv_count": {"status": ["draft", "completed"]},
    "inv_warehouse_task": {"status": ["ready", "in_progress", "completed"], "task_type": ["pick", "pack", "check"]},
    "inv_pick_wave": {"status": ["draft", "released", "completed"]},
    "inv_reservation": {"status": ["reserved", "released"]},
    "inv_batch": {"status": ["active", "used"]},
    "inv_location": {"status": ["active", "inactive"]},
    "inv_zone": {"status": ["active", "inactive"]},
    "inv_warehouse_access": {"status": ["active", "inactive"]},
    "tms_shipment": {"status": ["draft", "planned", "dispatched", "in_transit", "delivered"]},
    "ocr_document": {"status": ["pending", "completed", "needs_review"]},
    "biz_attachment": {"visibility": ["internal", "restricted"]},
    "sys_notification": {"severity": ["info", "warning", "critical"]},
    "tms_shipment_event": {"status": ["planned", "dispatched", "in_transit", "delivered"]},
    "biz_document": {"status": ["draft", "submitted", "approved", "completed"]},
    "biz_export_job": {"status": ["pending", "processing", "completed", "failed"]},
    "biz_saved_view": {"status": ["active", "inactive"]},
    "biz_report_definition": {"status": ["active", "inactive"]},
    "biz_report_run": {"status": ["completed", "failed"]},
    "cost_allocation": {"status": ["draft", "posted"]},
    "cost_period_close": {"status": ["open", "closed"]},
    "wf_definition": {"status": ["draft", "active"]},
    "wf_instance": {"status": ["running", "completed", "rejected"]},
    "wf_task": {"status": ["pending", "approved", "rejected"]},
}

# Fallback pools for enum-style columns that are not listed per-table above.
ENUM_FALLBACK: dict[str, list[str]] = {
    "leave_type": ["annual", "sick", "personal", "compensatory"],
    "status": ["active", "inactive"],
    "stage": ["new", "prospecting", "negotiation", "won"],
    "severity": ["minor", "major", "critical"],
    "result": ["passed", "failed"],
    "disposition": ["accept", "rework", "scrap", "return_to_supplier"],
    "control_status": ["in_control", "out_of_control"],
    "capa_status": ["not_required", "pending", "in_progress", "closed"],
    "rating": ["pending", "excellent", "good", "needs_improvement"],
    "from_status": ["active", "inactive"],
    "to_status": ["active", "inactive"],
    "cost_type": ["prevention", "appraisal", "internal_failure", "external_failure"],
    "exception_type": ["equipment_failure", "material_shortage", "capacity_overload"],
    "account_type": ["asset", "liability", "equity", "cost", "revenue", "expense"],
    "balance_direction": ["debit", "credit"],
    "dimension_type": ["department"],
    "depreciation_method": ["straight_line"],
    "basis": ["manual"],
    "source_type": ["manual"],
    "statement_type": ["ar", "ap"],
    "match_type": ["rule", "manual"],
    "direction": ["in", "out"],
    "task_type": ["pick", "pack", "check"],
    "order_type": ["purchase", "manufacture"],
    "inspection_type": ["incoming", "process", "final"],
    "change_type": ["engineering"],
    "object_type": ["bom", "routing", "purchase", "work_order"],
    "service_type": ["repair", "maintenance", "inspection"],
    "invoice_type": ["input", "output"],
    "event_type": ["created", "updated"],
    "membership_type": ["user"],
    "action_type": ["create"],
    "notification_type": ["info"],
    "document_type": ["sales_order"],
    "visibility": ["internal", "restricted"],
    "reset_cycle": ["day", "month", "year"],
}


# Document / order workflow tables must never seed the master-data sentinel "active".
DOCUMENT_WORKFLOW_TABLES = frozenset({
    "sales_quote", "sales_order", "sales_delivery", "sales_return",
    "purchase_request", "purchase_order", "purchase_receipt", "purchase_return",
    "hr_leave_request", "fin_expense", "fin_voucher", "biz_document",
    "inv_transfer", "inv_count", "mfg_work_order", "mfg_bom",
})
DOCUMENT_STATUS_FALLBACK = ["draft", "submitted", "approved", "completed"]


def enum_value(table_name: str, key: str, index: int) -> str:
    pool = STATUS_POOLS.get(table_name, {}).get(key)
    if not pool and key == "status" and table_name in DOCUMENT_WORKFLOW_TABLES:
        pool = DOCUMENT_STATUS_FALLBACK
    if not pool:
        pool = ENUM_FALLBACK.get(key, ["active"])
    value = pool[(index - 1) % len(pool)]
    # Hard stop: never write illegal "active" into document workflow status columns.
    if key == "status" and table_name in DOCUMENT_WORKFLOW_TABLES and value == "active":
        value = DOCUMENT_STATUS_FALLBACK[(index - 1) % len(DOCUMENT_STATUS_FALLBACK)]
    return value


def table_rows(table: Table, index: int) -> dict[str, object]:
    name = table.name
    row: dict[str, object] = {}
    for column in table.columns:
        key = column.name
        if key == "id":
            row[key] = uid(name, index)
        elif key == "org_id":
            row[key] = ORG
        elif key in {"user_id", "owner_id", "created_by", "updated_by", "requester_id", "applicant_id", "manager_id", "assigned_to", "reported_by", "approved_by", "posted_by", "closed_by", "completed_by", "confirmed_by", "technician_id"}:
            row[key] = ADMIN
        elif key == "department_id":
            row[key] = DEPT
        elif key == "parent_id":
            row[key] = None
        elif key in {"material_id", "alternate_material_id"}:
            row[key] = uid("md_material", ((index - 1) % seed_count("md_material")) + 1)
        elif key in {"unit_id"}:
            row[key] = uid("md_unit", ((index - 1) % seed_count("md_unit")) + 1)
        elif key in {"tax_rate_id"}:
            row[key] = uid("md_tax_rate", ((index - 1) % seed_count("md_tax_rate")) + 1)
        elif key in {"warehouse_id", "from_warehouse_id", "to_warehouse_id"}:
            row[key] = uid("md_warehouse", ((index - 1) % seed_count("md_warehouse")) + 1)
        elif key == "customer_id":
            row[key] = uid("md_customer", ((index - 1) % seed_count("md_customer")) + 1)
        elif key == "supplier_id":
            row[key] = uid("md_supplier", ((index - 1) % seed_count("md_supplier")) + 1)
        elif key == "employee_id":
            row[key] = uid("hr_employee", ((index - 1) % seed_count("hr_employee")) + 1)
        elif key == "asset_id":
            row[key] = uid("eam_asset", ((index - 1) % seed_count("eam_asset")) + 1)
        elif key == "project_id":
            row[key] = uid("project", ((index - 1) % seed_count("project")) + 1)
        elif key == "work_order_id":
            row[key] = uid("mfg_work_order", ((index - 1) % seed_count("mfg_work_order")) + 1)
        elif key == "inspection_id":
            row[key] = uid("qa_inspection", ((index - 1) % seed_count("qa_inspection")) + 1)
        elif key == "bom_id":
            row[key] = uid("mfg_bom", ((index - 1) % seed_count("mfg_bom")) + 1)
        elif key == "routing_id":
            row[key] = uid("mfg_routing", ((index - 1) % seed_count("mfg_routing")) + 1)
        elif key == "work_center_id":
            row[key] = uid("mfg_work_center", ((index - 1) % seed_count("mfg_work_center")) + 1)
        elif key == "mps_id":
            row[key] = uid("mfg_mps", ((index - 1) % seed_count("mfg_mps")) + 1)
        elif key == "run_id":
            row[key] = uid("mfg_plan_run", ((index - 1) % seed_count("mfg_plan_run")) + 1)
        elif key == "definition_id":
            row[key] = uid("wf_definition", ((index - 1) % seed_count("wf_definition")) + 1)
        elif key == "instance_id":
            row[key] = uid("wf_instance", index)
        elif key == "request_id":
            row[key] = uid("purchase_request", ((index - 1) % seed_count("purchase_request")) + 1)
        elif key == "order_id":
            target = "purchase_order" if name == "purchase_order_item" else "sales_order"
            row[key] = uid(target, ((index - 1) % seed_count(target)) + 1)
        elif key in {"quote_id", "return_id", "statement_id", "voucher_id", "receipt_id", "payment_id", "payable_id", "receivable_id", "allocation_id", "plan_id", "change_order_id", "change_request_id", "contract_id", "case_id", "subscription_id", "event_id", "wave_id", "location_id", "batch_id", "transaction_id", "operation_id", "wbs_id", "source_id", "document_id", "object_id", "source_event", "inbound_transaction_id", "outbound_transaction_id", "cost_layer_id", "formal_document_id", "project_id"}:
            row[key] = uid(name + key, index)
        elif key.endswith("_id"):
            target = key[:-3]
            tables = table.metadata.tables
            prefix = name.split("_", 1)[0]
            candidates = [target, f"{prefix}_{target}"]
            candidates.extend(table_name for table_name in tables if table_name.endswith(f"_{target}"))
            target_table = next((candidate for candidate in candidates if candidate in tables), None)
            if target_table:
                row[key] = uid(target_table, ((index - 1) % seed_count(target_table)) + 1)
            else:
                row[key] = None if column.nullable else uid(name + key, index)
        elif key.endswith("_json") or key in {"items_json", "schema_json", "workflow_json", "evidence_json", "payload_json", "result_json", "snapshot_json", "source_snapshot", "input_snapshot", "output_snapshot", "bom_snapshot", "routing_snapshot", "details", "dimensions_json", "goals_json", "response_json", "event_types", "scopes"}:
            row[key] = [] if "items" in key or key in {"event_types", "scopes", "impact_snapshot"} else {}
        elif key in {"created_at", "updated_at", "event_time", "occurred_at", "report_time", "scheduled_at", "effective_at", "closed_at", "reopened_at", "completed_at", "delivered_at", "confirmed_at", "posted_at"}:
            row[key] = datetime.now()
        elif key in {"date", "order_date", "quote_date", "request_date", "expense_date", "payment_date", "receipt_date", "delivery_date", "return_date", "promised_date", "document_date", "allocation_date", "entry_date", "plan_date", "plan_from", "plan_to", "due_date", "start_date", "end_date", "expected_date", "purchase_date", "effective_from", "effective_to", "production_date", "expiry_date", "attendance_date", "next_due", "next_maintenance_date", "planned_date", "actual_date", "event_date", "forecast_date", "statement_date", "transaction_date", "schedule_date", "transfer_date", "count_date", "voucher_date", "rate_date", "capacity_date", "valid_until", "period_start", "period_end"}:
            row[key] = date.today() + timedelta(days=(index % 15) - 7)
        elif key in {"is_deleted", "required", "allow_posting", "is_base", "blocking", "is_shared", "serial_tracking"}:
            row[key] = False
        elif key in {"version", "line_no", "priority", "sequence_length", "precision_scale", "decimal_places", "interval_days", "daily_capacity_hours", "useful_life_months", "threshold_days", "sample_size", "attempt_count", "retry_count", "failure_count", "response_status", "row_count", "credit_days"}:
            row[key] = (index % 20) + 1
        elif key in {"amount", "total_amount", "actual_amount", "budget_amount", "original_value", "accumulated_depreciation", "standard_cost", "sale_price", "purchase_price", "credit_limit", "quote_amount", "processing_fee", "processing_fee_amount", "inflow_amount", "outflow_amount", "net_amount", "total_debit", "total_credit", "debit_amount", "credit_amount", "value", "freight_amount", "statement_amount", "reconciled_amount", "matched_amount", "unit_cost", "total_cost", "material_cost", "labor_cost", "overhead_cost", "subcontract_cost", "scrap_cost", "variance_amount", "actual_unit_cost", "base_salary", "allowance", "score", "target", "rate", "tax_amount", "delivery_score", "quality_score", "service_score", "total_score", "defect_rate", "sample_value", "lsl", "usl", "cpk", "impact_quantity", "quantity", "min_stock", "max_stock", "plan_quantity", "receivable_amount", "payable_amount", "residual_rate", "efficiency_rate", "labor_rate", "overhead_rate", "required_quantity", "issued_quantity", "returned_quantity", "completed_quantity", "reported_good_quantity", "reported_scrap_quantity", "planned_quantity", "good_quantity", "scrap_quantity", "hours", "scheduled_hours", "actual_hours", "original_quantity", "remaining_quantity", "released_quantity", "locked_quantity", "available_quantity", "average_cost", "estimated_price", "unit_price", "tax_rate"}:
            row[key] = Decimal(str(10 + index * 3))
        elif key in {"status", "leave_type", "result", "disposition", "severity", "stage", "account_type", "balance_direction", "dimension_type", "depreciation_method", "basis", "source_type", "statement_type", "match_type", "direction", "task_type", "order_type", "inspection_type", "change_type", "object_type", "service_type", "invoice_type", "event_type", "membership_type", "action_type", "notification_type", "document_type", "visibility", "reset_cycle", "control_status", "capa_status", "rating", "from_status", "to_status", "cost_type", "exception_type"}:
            row[key] = enum_value(name, key, index)
        elif isinstance(column.type, SQLDateTime):
            row[key] = datetime.now()
        elif isinstance(column.type, SQLDate):
            row[key] = date.today()
        elif isinstance(column.type, SQLBoolean):
            row[key] = False
        elif isinstance(column.type, SQLInteger):
            row[key] = 0
        elif isinstance(column.type, SQLNumeric):
            row[key] = Decimal("0")
        elif isinstance(column.type, SQLJSON):
            row[key] = {}
        elif isinstance(column.type, (SQLString, SQLText)):
            row[key] = f"{TABLE_LABELS.get(name, '华东经营事项')} {index:02d}"
        else:
            row[key] = None if column.nullable else f"{TABLE_LABELS.get(name, '华东经营事项')} {index:02d}"

    # Human-facing master data and document numbers.
    prefixes = {
        "md_unit": "UOM", "md_tax_rate": "VAT", "md_material": "MAT", "md_customer": "CUS", "md_supplier": "SUP", "md_warehouse": "WH",
        "sales_quote": "QT", "sales_order": "SO", "sales_delivery": "SD", "sales_return": "SR",
        "purchase_request": "PRQ", "purchase_order": "PO", "purchase_receipt": "GR", "purchase_return": "PTR",
        "mfg_bom": "BOM", "mfg_mps": "MPS", "mfg_mrp_run": "MRP", "mfg_work_order": "WO", "mfg_routing": "RT", "mfg_work_center": "WC", "qa_inspection": "QI", "crm_lead": "LD", "crm_opportunity": "OP",
        "fin_expense": "EXP", "fin_receipt": "RCV", "fin_payment": "PAY", "fin_voucher": "VCH", "hr_employee": "EMP", "hr_recruitment_candidate": "CAN", "eam_asset": "AST", "tms_shipment": "SHP",
    }
    if "code" in table.c and name in prefixes:
        row["code"] = f"{prefixes[name]}-{index:04d}"
    if "doc_no" in table.c:
        row["doc_no"] = f"{prefixes.get(name, name[:3].upper())}{date.today():%Y%m}{index:04d}"
    if "rfq_no" in table.c:
        row["rfq_no"] = f"RFQ-{date.today():%Y%m}-{index:04d}"
    if "run_no" in table.c:
        row["run_no"] = f"PLAN-{date.today():%Y%m}-{index:04d}"
    if "voucher_no" in table.c:
        row["voucher_no"] = f"VCH-{date.today():%Y%m}-{index:04d}"
    if name == "fin_currency" and "code" in table.c:
        currencies = [("CNY", "人民币", "¥"), ("USD", "美元", "$"), ("EUR", "欧元", "€"), ("JPY", "日元", "¥"), ("HKD", "港币", "HK$"), ("GBP", "英镑", "£")]
        row["code"], row["name"], row["symbol"] = currencies[(index - 1) % len(currencies)]
    if "period" in table.c:
        row["period"] = month_value(index)
    if "last_depreciation_period" in table.c:
        row["last_depreciation_period"] = month_value(index)
    for period_key in {"budget_period", "supplier_period", "review_period", "period_key"}:
        if period_key in table.c:
            row[period_key] = month_value(index)
    if "date_format" in table.c:
        row["date_format"] = "%Y%m"
    if "name" in table.c:
        names = REALISTIC_NAMES.get(name)
        if names:
            base_name = names[(index - 1) % len(names)]
            row["name"] = base_name
        else:
            row["name"] = TABLE_LABELS.get(name, "业务档案")
    if name == "biz_document":
        doc_types = ["sales_order", "purchase_order", "sales_delivery", "purchase_receipt", "qa_inspection", "fin_expense", "mfg_work_order"]
        doc_type = doc_types[(index - 1) % len(doc_types)]
        row["business_type"] = doc_type
        row["business_id"] = uid(doc_type, ((index - 1) % seed_count(doc_type)) + 1)
        row["party_type"] = "customer" if doc_type.startswith("sales") else "supplier"
        party_table = "md_customer" if row["party_type"] == "customer" else "md_supplier"
        party_index = ((index - 1) % seed_count(party_table)) + 1
        row["party_id"] = uid(party_table, party_index)
        party_name = REALISTIC_NAMES[party_table][party_index - 1]
        row["party_name"] = party_name
        row["source_type"] = doc_type
    if name in {"sales_order", "purchase_order"}:
        amount = order_amount(index)
        if name == "sales_order":
            row["status"] = ["draft", "submitted", "completed", "completed", "rejected", "completed"][index - 1]
        else:
            row["status"] = ["draft", "submitted", "partially_received", "completed", "rejected", "completed"][index - 1]
        row["total_amount"] = amount
        if name == "sales_order":
            row["receivable_amount"] = amount
        else:
            row["payable_amount"] = amount
    if name in {"sales_order_item", "purchase_order_item"}:
        amount = order_amount(index)
        row["quantity"] = Decimal("10")
        row["unit_price"] = (amount / Decimal("10")).quantize(Decimal("0.000001"))
        row["amount"] = amount
        row["tax_rate"] = Decimal("0")
        row["line_no"] = 1
    if name == "sales_delivery":
        order_index = SALES_DELIVERY_ORDER_INDEX[index - 1]
        row["order_id"] = uid("sales_order", order_index)
        row["customer_id"] = uid("md_customer", order_index)
        row["warehouse_id"] = uid("md_warehouse", ((order_index - 1) % seed_count("md_warehouse")) + 1)
        row["status"] = "completed"
        row["total_amount"] = order_amount(order_index)
    if name == "sales_delivery_item":
        order_index = SALES_DELIVERY_ORDER_INDEX[index - 1]
        row["delivery_id"] = uid("sales_delivery", index)
        row["order_item_id"] = uid("sales_order_item", order_index)
        row["material_id"] = uid("md_material", order_index)
        row["quantity"] = Decimal("10")
        row["unit_price"] = (order_amount(order_index) / Decimal("10")).quantize(Decimal("0.000001"))
        row["amount"] = order_amount(order_index)
    if name == "purchase_receipt":
        order_index = PURCHASE_RECEIPT_ORDER_INDEX[index - 1]
        row["order_id"] = uid("purchase_order", order_index)
        row["supplier_id"] = uid("md_supplier", order_index)
        row["warehouse_id"] = uid("md_warehouse", ((order_index - 1) % seed_count("md_warehouse")) + 1)
        row["status"] = "completed"
        row["total_amount"] = order_amount(order_index) * (Decimal("0.7") if order_index == 3 else Decimal("1"))
    if name == "purchase_receipt_item":
        order_index = PURCHASE_RECEIPT_ORDER_INDEX[index - 1]
        received = Decimal("7") if order_index == 3 else Decimal("10")
        row["receipt_id"] = uid("purchase_receipt", index)
        row["order_item_id"] = uid("purchase_order_item", order_index)
        row["material_id"] = uid("md_material", order_index)
        row["quantity"] = received
        row["unit_price"] = (order_amount(order_index) / Decimal("10")).quantize(Decimal("0.000001"))
        row["amount"] = order_amount(order_index) * (Decimal("0.7") if order_index == 3 else Decimal("1"))
    if name == "purchase_order_item":
        row["received_quantity"] = Decimal("7") if index == 3 else (Decimal("10") if index in {4, 6} else Decimal("0"))
    if name == "fin_fiscal_period":
        period = str(row["period"])
        period_start = date.fromisoformat(f"{period}-01")
        next_month = period_start.replace(day=28) + timedelta(days=4)
        period_end = next_month.replace(day=1) - timedelta(days=1)
        row["start_date"] = period_start
        row["end_date"] = period_end
        row["status"] = "open" if period == date.today().strftime("%Y-%m") else enum_value(name, "status", index)
        row["closed_at"] = None if row["status"] == "open" else datetime.now()
    if name == "wf_instance":
        row["business_type"] = "sales_order"
        row["business_id"] = uid("sales_order", index)
        row["definition_id"] = uid("wf_definition", ((index - 1) % seed_count("wf_definition")) + 1)
        row["current_node_key"] = "node-1"
        row["status"] = "running"
    if name == "wf_node":
        row["node_key"] = "node-1"
    if name == "wf_task":
        row["node_key"] = "node-1"
        row["status"] = "pending"
    if name == "md_material":
        # Keep inventory warnings in a useful range: only a few SKUs
        # carry a meaningful safety stock, and most materials use min_stock=0
        # (ignored by warning rules that require min_stock > 0).
        if index <= 3:
            row["min_stock"] = Decimal("80")
            row["max_stock"] = Decimal("500")
        else:
            row["min_stock"] = Decimal("0")
            row["max_stock"] = Decimal(str(200 + index * 5))
    if name == "hr_leave_request":
        row["leave_type"] = enum_value(name, "leave_type", index)
        row["status"] = enum_value(name, "status", index)
        reasons = {
            "annual": "安排年度休假，已完成工作交接",
            "sick": "因身体不适前往门诊就医",
            "personal": "办理家庭事务并已提交交接安排",
            "compensatory": "按本月加班记录申请调休",
        }
        row["reason"] = reasons[enum_value(name, "leave_type", index)]
    if name == "project":
        row["budget_amount"] = Decimal(str(250000 + index * 50000))
    if name == "project_wbs":
        row["planned_amount"] = Decimal(str(65000 + index * 12500))
    if name == "project_entry":
        project_index = ((index - 1) % seed_count("project")) + 1
        project_wbs_index = project_index
        entries = {
            1: ("purchase", "purchase_receipt", 1, order_amount(3) * Decimal("0.7")),
            2: ("revenue", "sales_delivery", 1, order_amount(3)),
            3: ("inventory", "purchase_receipt", 2, order_amount(4)),
            4: ("labor", "mfg_work_order", 4, Decimal("18500.00")),
            5: ("expense", "fin_expense", 2, Decimal("2350.00")),
            6: ("revenue", "sales_delivery", 3, order_amount(6)),
        }
        category, source_type, source_index, amount = entries[index]
        row["project_id"] = uid("project", project_index)
        row["wbs_id"] = uid("project_wbs", project_wbs_index)
        row["category"] = category
        row["source_type"] = source_type
        row["source_id"] = uid(source_type, source_index)
        row["amount"] = amount.quantize(Decimal("0.01"))
    if name == "fin_account":
        accounts = [
            ("1002", "银行存款", "asset", "debit"),
            ("1122", "应收账款", "asset", "debit"),
            ("2202", "应付账款", "liability", "credit"),
            ("6001", "主营业务收入", "revenue", "credit"),
            ("6602", "管理费用", "expense", "debit"),
            ("5001", "生产成本", "cost", "debit"),
        ]
        row["code"], row["name"], row["account_type"], row["balance_direction"] = accounts[index - 1]
        row["status"] = "active"
    if name == "fin_expense":
        expense_types = ["交通费用", "差旅费用", "办公费用", "业务招待", "其他费用", "交通费用"]
        descriptions = [
            "客户现场交付交通支出",
            "苏州供应商质量评审差旅",
            "生产线安全标识与办公耗材采购",
            "重点客户项目技术交流接待",
            "售后备件仓搬迁杂项支出",
            "华东区域客户现场服务通行费",
        ]
        row["expense_type"] = expense_types[index - 1]
        row["description"] = descriptions[index - 1]
        row["amount"] = Decimal(str(1500 + index * 425)).quantize(Decimal("0.01"))
    if name == "mfg_work_order_exception":
        exception_types = ["equipment_failure", "material_shortage", "capacity_overload"]
        descriptions = {
            "equipment_failure": "主轴运行温度偏高，设备已转入点检维护",
            "material_shortage": "伺服驱动器到料批次待质量复核，当前工序暂缓投产",
            "capacity_overload": "成品检测工位本周排程接近班次产能上限",
        }
        resolutions = {
            "equipment_failure": "完成冷却回路清洁与主轴复测，设备恢复运行",
            "material_shortage": "供应商补齐合格批次并完成来料复验",
            "capacity_overload": "调整工序计划至第二班次，复核后恢复排程",
        }
        row["exception_type"] = exception_types[(index - 1) % len(exception_types)]
        row["description"] = descriptions[row["exception_type"]]
        if row["status"] == "resolved":
            row["resolution"] = resolutions[row["exception_type"]]
            row["resolved_at"] = datetime.now()
        else:
            row["resolution"] = None
            row["resolved_at"] = None
    if name == "qa_plan":
        row["items_json"] = [
            {"item": "外观与标识检查", "standard": "符合图纸及包装规范"},
            {"item": "关键尺寸复核", "standard": "符合产品检验规范"},
        ]
    if name == "qa_inspection":
        source_table_by_type = {"incoming": "purchase_receipt", "process": "mfg_work_order", "final": "sales_delivery"}
        inspection_type = enum_value(name, "inspection_type", index)
        row["inspection_type"] = inspection_type
        source_table = source_table_by_type[inspection_type]
        source_indices = {
            "incoming": [1, 2],
            "process": [2, 5],
            "final": [1, 2],
        }
        occurrence = (index - 1) // 3
        row["source_type"] = source_table
        row["source_id"] = uid(source_table, source_indices[inspection_type][occurrence])
        row["result"] = None if row["status"] in {"draft", "submitted"} else ("failed" if index % 3 == 0 else "passed")
        passed = row["result"] != "failed"
        row["results_json"] = [
            {"item": "外观与标识检查", "value": "符合规范" if passed else "发现表面划伤", "passed": passed},
            {"item": "关键尺寸复核", "value": "图纸公差范围内" if passed else "尺寸偏差待复核", "passed": passed},
        ]
        row["disposition"] = ("rework" if not passed else "accept") if row["status"] == "closed" else None
    if name == "qa_nonconformance":
        row["inspection_id"] = uid("qa_inspection", ((index - 1) % seed_count("qa_inspection")) + 1)
        row["supplier_id"] = uid("md_supplier", ((index - 1) % seed_count("md_supplier")) + 1)
        row["description"] = ["压接端子拉脱力低于工艺下限", "装配面局部划伤", "来料轴承游隙超出检验范围"][(index - 1) % 3]
        row["root_cause"] = "来料批次抽检发现尺寸波动，已隔离同批物料并复核量具校准记录" if row["status"] != "open" else None
        row["disposition"] = enum_value(name, "disposition", index)
        row["closed_at"] = datetime.now() if row["status"] == "closed" else None
        row["closure_evidence"] = "返工复检合格，质量负责人已确认" if row["status"] == "closed" else None
    if name == "qa_capa_action":
        row["nonconformance_id"] = uid("qa_nonconformance", ((index - 1) % seed_count("qa_nonconformance")) + 1)
        row["description"] = "更新来料抽样频次并复核供应商过程能力" if index % 2 else "增加压接高度首件确认与巡检记录"
        row["completion_evidence"] = "已修订检验作业指导书并完成现场培训" if row["status"] == "completed" else None
        row["completed_at"] = datetime.now() if row["status"] == "completed" else None
    if name == "qa_spc_record":
        row["metric"] = "主轴振动值"
        in_control = row["status"] == "in_control"
        row["lsl"], row["usl"] = Decimal("8.0"), Decimal("18.0")
        row["sample_value"] = Decimal("13.0") if in_control else Decimal("22.5")
        row["cpk"] = Decimal("1.42") if in_control else Decimal("0.68")
    if name == "qa_spc_exception":
        row["spc_record_id"] = uid("qa_spc_record", ((index - 1) % seed_count("qa_spc_record")) + 1)
        row["material_id"] = uid("md_material", ((index - 1) % seed_count("md_material")) + 1)
        row["metric"] = "主轴振动值"
        row["control_status"] = "out_of_control"
        row["owner_id"] = ADMIN
        row["due_date"] = date.today() + timedelta(days=7)
        row["containment_action"] = "暂缓该设备后续批次放行并追加抽检" if row["status"] != "pending_review" else None
        row["root_cause"] = "刀具磨损导致加工过程振动上升" if row["status"] in {"corrective_action", "retest", "closed"} else None
        row["closure_evidence"] = "更换刀具后连续三批抽检均处于控制界限内" if row["status"] == "closed" else None
        row["closed_at"] = datetime.now() if row["status"] == "closed" else None
    if name == "qa_quality_cost":
        row["note"] = ["来料抽检工时", "量具校准费用", "返工工时", "客户现场复检费用"][(index - 1) % 4]
        row["source_type"] = "qa_inspection" if index % 2 else "qa_nonconformance"
        source_table = "qa_inspection" if index % 2 else "qa_nonconformance"
        row["source_id"] = uid(source_table, ((index - 1) % seed_count(source_table)) + 1)
    if name == "qa_customer_claim":
        row["claim_no"] = f"CLM-{date.today():%Y%m}-{index:04d}"
        row["title"] = ["到货设备外观损伤处理", "驱动器运行温升偏高", "备件交付数量差异"][(index - 1) % 3]
        row["source_type"] = "sales_delivery"
        row["source_id"] = uid("sales_delivery", ((index - 1) % seed_count("sales_delivery")) + 1)
        row["customer_id"] = uid("md_customer", ((index - 1) % seed_count("md_customer")) + 1)
        row["approved_amount"] = row["amount"] if row["status"] == "approved" else None
    if name == "sales_receivable":
        row["source_type"] = "sales_delivery"
        delivery_index = index
        order_index = SALES_DELIVERY_ORDER_INDEX[delivery_index - 1]
        row["source_id"] = uid("sales_delivery", delivery_index)
        row["customer_id"] = uid("md_customer", order_index)
        row["doc_no"] = f"AR-{date.today():%Y%m}-{index:04d}"
        row["total_amount"] = order_amount(order_index)
        row["reconciled_amount"] = Decimal("0") if index == 1 else (order_amount(order_index) / 2 if index == 2 else order_amount(order_index))
        row["status"] = ["open", "partial", "settled"][index - 1]
    if name == "purchase_payable":
        row["source_type"] = "purchase_receipt"
        receipt_index = index
        order_index = PURCHASE_RECEIPT_ORDER_INDEX[receipt_index - 1]
        amount = order_amount(order_index) * (Decimal("0.7") if order_index == 3 else Decimal("1"))
        row["source_id"] = uid("purchase_receipt", receipt_index)
        row["supplier_id"] = uid("md_supplier", order_index)
        row["doc_no"] = f"AP-{date.today():%Y%m}-{index:04d}"
        row["total_amount"] = amount
        row["reconciled_amount"] = Decimal("0") if index == 1 else (amount / 2 if index == 2 else amount)
        row["status"] = ["open", "partial", "settled"][index - 1]
    if name == "sales_return":
        row["source_delivery_id"] = uid("sales_delivery", 2)
        row["customer_id"] = uid("md_customer", SALES_DELIVERY_ORDER_INDEX[1])
        row["warehouse_id"] = uid("md_warehouse", ((SALES_DELIVERY_ORDER_INDEX[1] - 1) % seed_count("md_warehouse")) + 1)
        row["status"] = "completed"
        row["total_amount"] = order_amount(SALES_DELIVERY_ORDER_INDEX[1]) / Decimal("10")
    if name == "sales_return_item":
        row["return_id"] = uid("sales_return", 1)
        row["material_id"] = uid("md_material", SALES_DELIVERY_ORDER_INDEX[1])
        row["quantity"] = Decimal("1")
        row["unit_price"] = (order_amount(SALES_DELIVERY_ORDER_INDEX[1]) / Decimal("10")).quantize(Decimal("0.000001"))
        row["amount"] = order_amount(SALES_DELIVERY_ORDER_INDEX[1]) / Decimal("10")
    if name == "purchase_return":
        row["source_receipt_id"] = uid("purchase_receipt", 2)
        row["supplier_id"] = uid("md_supplier", PURCHASE_RECEIPT_ORDER_INDEX[1])
        row["warehouse_id"] = uid("md_warehouse", ((PURCHASE_RECEIPT_ORDER_INDEX[1] - 1) % seed_count("md_warehouse")) + 1)
        row["status"] = "completed"
        row["total_amount"] = order_amount(PURCHASE_RECEIPT_ORDER_INDEX[1]) / Decimal("10")
    if name == "purchase_return_item":
        row["return_id"] = uid("purchase_return", 1)
        row["material_id"] = uid("md_material", PURCHASE_RECEIPT_ORDER_INDEX[1])
        row["quantity"] = Decimal("1")
        row["unit_price"] = (order_amount(PURCHASE_RECEIPT_ORDER_INDEX[1]) / Decimal("10")).quantize(Decimal("0.000001"))
        row["amount"] = order_amount(PURCHASE_RECEIPT_ORDER_INDEX[1]) / Decimal("10")
    if name == "fin_receipt":
        receivable_index = index + 1
        order_index = SALES_DELIVERY_ORDER_INDEX[receivable_index - 1]
        receivable_amount = order_amount(order_index)
        row["doc_no"] = f"RCV-{date.today():%Y%m}-{index:04d}"
        row["customer_id"] = uid("md_customer", order_index)
        row["account_name"] = "宁波银行基本结算账户"
        row["amount"] = receivable_amount / 2 if index == 1 else receivable_amount
        row["status"] = "confirmed"
    if name == "fin_receipt_reconcile":
        receivable_index = index + 1
        row["receipt_id"] = uid("fin_receipt", index)
        row["receivable_id"] = uid("sales_receivable", receivable_index)
        order_index = SALES_DELIVERY_ORDER_INDEX[receivable_index - 1]
        row["amount"] = order_amount(order_index) / 2 if index == 1 else order_amount(order_index)
    if name == "fin_payment":
        payable_index = index + 1
        order_index = PURCHASE_RECEIPT_ORDER_INDEX[payable_index - 1]
        payable_amount = order_amount(order_index) * (Decimal("0.7") if order_index == 3 else Decimal("1"))
        row["doc_no"] = f"PAY-{date.today():%Y%m}-{index:04d}"
        row["supplier_id"] = uid("md_supplier", order_index)
        row["account_name"] = "宁波银行基本结算账户"
        row["amount"] = payable_amount / 2 if index == 1 else payable_amount
        row["status"] = "confirmed"
    if name == "fin_payment_reconcile":
        payable_index = index + 1
        row["payment_id"] = uid("fin_payment", index)
        row["payable_id"] = uid("purchase_payable", payable_index)
        order_index = PURCHASE_RECEIPT_ORDER_INDEX[payable_index - 1]
        payable_amount = order_amount(order_index) * (Decimal("0.7") if order_index == 3 else Decimal("1"))
        row["amount"] = payable_amount / 2 if index == 1 else payable_amount
    if name == "hr_performance_review":
        row["comments"] = "按计划完成重点客户交付协调，持续改善现场问题闭环效率"
    if name == "hr_employee_lifecycle":
        row["note"] = "依据组织岗位调整记录完成员工信息更新"
    if name == "mfg_plan_exception":
        row["details"] = {"impact": "关键工序负荷接近班次产能上限", "action": "调整排产日期并复核工作中心负荷"}
    if name == "mfg_demand_line":
        row["source_type"] = "sales_order"
        row["source_id"] = uid("sales_order", ((index - 1) % seed_count("sales_order")) + 1)
    if name == "fin_cash_forecast":
        row["source"] = "已审批客户订单回款预测" if index % 2 else "采购付款计划汇总"
    if name == "tms_shipment_event":
        row["shipment_id"] = uid("tms_shipment", ((index - 1) % seed_count("tms_shipment")) + 1)
    if name == "inv_stock":
        row["locked_quantity"] = Decimal("0")
        # Stocks for materials 1..3 stay intentionally below min_stock (80)
        # so the dashboard shows a handful of warnings; others stay healthy.
        material_index = ((index - 1) % seed_count("md_material")) + 1
        if material_index <= 3:
            row["quantity"] = Decimal("20")
        else:
            row["quantity"] = Decimal(str(120 + index * 2))
        row["available_quantity"] = row["quantity"]
    if name == "inv_stock_transaction":
        row["transaction_date"] = datetime.now()
        if index <= len(PURCHASE_RECEIPT_ORDER_INDEX):
            receipt_index = index
            order_index = PURCHASE_RECEIPT_ORDER_INDEX[receipt_index - 1]
            row["source_type"] = "purchase_receipt"
            row["source_id"] = uid("purchase_receipt", receipt_index)
            row["direction"] = "in"
            row["material_id"] = uid("md_material", order_index)
            row["warehouse_id"] = uid("md_warehouse", ((order_index - 1) % seed_count("md_warehouse")) + 1)
            row["quantity"] = Decimal("7") if order_index == 3 else Decimal("10")
        elif index <= len(PURCHASE_RECEIPT_ORDER_INDEX) + len(SALES_DELIVERY_ORDER_INDEX):
            delivery_index = index - len(PURCHASE_RECEIPT_ORDER_INDEX)
            order_index = SALES_DELIVERY_ORDER_INDEX[delivery_index - 1]
            row["source_type"] = "sales_delivery"
            row["source_id"] = uid("sales_delivery", delivery_index)
            row["direction"] = "out"
            row["material_id"] = uid("md_material", order_index)
            row["warehouse_id"] = uid("md_warehouse", ((order_index - 1) % seed_count("md_warehouse")) + 1)
            row["quantity"] = Decimal("10")
        elif index == 7:
            order_index = SALES_DELIVERY_ORDER_INDEX[1]
            row["source_type"] = "sales_return"
            row["source_id"] = uid("sales_return", 1)
            row["direction"] = "in"
            row["material_id"] = uid("md_material", order_index)
            row["warehouse_id"] = uid("md_warehouse", ((order_index - 1) % seed_count("md_warehouse")) + 1)
            row["quantity"] = Decimal("1")
        else:
            order_index = PURCHASE_RECEIPT_ORDER_INDEX[1]
            row["source_type"] = "purchase_return"
            row["source_id"] = uid("purchase_return", 1)
            row["direction"] = "out"
            row["material_id"] = uid("md_material", order_index)
            row["warehouse_id"] = uid("md_warehouse", ((order_index - 1) % seed_count("md_warehouse")) + 1)
            row["quantity"] = Decimal("1")
        unit_cost = order_amount(order_index) / Decimal("10")
        row["unit_cost"] = unit_cost
        row["amount"] = (row["quantity"] * unit_cost).quantize(Decimal("0.01"))
    if name == "inv_reservation":
        row["status"] = "released"
        row["released_quantity"] = row["quantity"]
    if name == "fin_voucher":
        if index <= 2:
            row["source_type"] = "receipt"
            row["source_id"] = uid("fin_receipt", index)
            row["status"] = "draft"
            order_index = SALES_DELIVERY_ORDER_INDEX[index]
            amount = order_amount(order_index) / (Decimal("2") if index == 1 else Decimal("1"))
        elif index <= 4:
            row["source_type"] = "payment"
            row["source_id"] = uid("fin_payment", index - 2)
            row["status"] = "draft"
            order_index = PURCHASE_RECEIPT_ORDER_INDEX[index - 2]
            amount = order_amount(order_index) / (Decimal("2") if index == 3 else Decimal("1"))
        elif index == 5:
            row["source_type"] = "expense"
            row["source_id"] = uid("fin_expense", 4)
            row["status"] = "reversed"
            amount = Decimal("3200.00")
        else:
            row["source_type"] = "manual"
            row["source_id"] = None
            row["status"] = "posted"
            amount = Decimal("3200.00")
        row["total_debit"] = amount
        row["total_credit"] = amount
        row["posted_at"] = datetime.now() if row["status"] in {"posted", "reversed"} else None
        row["reversed_from_id"] = uid("fin_voucher", 5) if index == 6 else None
        row["reversal_voucher_id"] = uid("fin_voucher", 6) if index == 5 else None
    if name == "fin_voucher_entry":
        line_no = 1 if index % 2 else 2
        voucher_index = (index + 1) // 2
        if voucher_index <= 2:
            order_index = SALES_DELIVERY_ORDER_INDEX[voucher_index]
            amount = order_amount(order_index) / (Decimal("2") if voucher_index == 1 else Decimal("1"))
            accounts = [("1002", "银行存款", 1), ("1122", "应收账款", 2)]
        elif voucher_index <= 4:
            payment_index = voucher_index - 2
            order_index = PURCHASE_RECEIPT_ORDER_INDEX[payment_index]
            amount = order_amount(order_index) / (Decimal("2") if payment_index == 1 else Decimal("1"))
            accounts = [("2202", "应付账款", 3), ("1002", "银行存款", 1)]
        elif voucher_index == 5:
            amount = Decimal("3200.00")
            accounts = [("6602", "管理费用", 5), ("1002", "银行存款", 1)]
        else:
            amount = Decimal("3200.00")
            accounts = [("1002", "银行存款", 1), ("6602", "管理费用", 5)]
        account_code, account_name, account_index = accounts[line_no - 1]
        row["id"] = uid("fin_voucher_entry", index)
        row["voucher_id"] = uid("fin_voucher", voucher_index)
        row["line_no"] = line_no
        row["account_id"] = uid("fin_account", account_index)
        row["account_code"] = account_code
        row["account_name"] = account_name
        row["debit_amount"] = amount if line_no == 1 else Decimal("0")
        row["credit_amount"] = Decimal("0") if line_no == 1 else amount
        row["dimensions_json"] = {}
    if name == "mfg_routing_operation":
        row["line_no"] = ((index - 1) // seed_count("mfg_routing")) + 1
        row["operation_name"] = "首道工序来料复核" if row["line_no"] == 1 else "关键尺寸加工与终检"
        row["quality_plan_id"] = uid("qa_plan", ((index - 1) % seed_count("qa_plan")) + 1)
        row["equipment_requirement"] = "三坐标测量设备" if row["line_no"] == 1 else "数控加工中心"
    if name == "svc_visit":
        row["case_id"] = uid("svc_case", index)
    if "display_name" in table.c:
        employee_names = REALISTIC_NAMES["hr_employee"]
        row["display_name"] = employee_names[(index - 1) % len(employee_names)]
    if "description" in table.c:
        row["description"] = "围绕华东区域订单交付、质量跟踪与回款协同的业务记录"
    if "title" in table.c:
        row["title"] = "客户交付与质量改进事项"
    if "note" in table.c:
        row["note"] = "已完成业务核对，等待下一节点处理"
    if "remark" in table.c:
        row["remark"] = "季度经营计划配套记录"
    if "email" in table.c:
        row["email"] = f"contact{index:02d}@chenghaimfg.cn"
    if "phone" in table.c:
        contact_phones = REALISTIC_FIELD_VALUES["md_customer"]["contact_phone"]
        row["phone"] = contact_phones[(index - 1) % len(contact_phones)]
    if "account_no" in table.c:
        row["account_no"] = f"622202260000{index:06d}"
    if "currency" in table.c:
        row["currency"] = "CNY"
    if "base_currency" in table.c:
        row["base_currency"] = "CNY"
    if "quote_currency" in table.c:
        row["quote_currency"] = "USD"
    if "source_file" in table.c:
        row["source_file"] = f"invoice_{index:02d}.pdf"
    if "file_name" in table.c:
        row["file_name"] = f"运营报表_{index:02d}.csv"
    if "file_key" in table.c:
        row["file_key"] = f"exports/operations/{index:02d}.csv"
    if "account_code" in table.c and name != "fin_voucher_entry":
        row["account_code"] = f"{6001 + (index % 20)}"
    if "account_name" in table.c and name != "fin_voucher_entry":
        row["account_name"] = "主营业务收入"
    if "asset_code" in table.c:
        row["asset_code"] = f"AST-{index:04d}"
    if "employee_no" in table.c:
        row["employee_no"] = f"EMP-{index:04d}"
    if "project_code" in table.c:
        row["project_code"] = f"PRJ-{index:04d}"
    if "project_name" in table.c:
        row["project_name"] = f"智能仓储升级项目 {index:02d}"
    if "object_key" in table.c:
        row["object_key"] = f"service_request_{index:02d}"
    if "metric_key" in table.c:
        row["metric_key"] = f"ops_metric_{index:02d}"
    if "alert_key" in table.c:
        row["alert_key"] = f"alert_{index:02d}"
    if "client_key" in table.c:
        row["client_key"] = f"client_{index:02d}"
    if "endpoint_url" in table.c:
        row["endpoint_url"] = "https://openapi.chenghaimfg.cn/erp/events"
    if "secret_hash" in table.c:
        row["secret_hash"] = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    if "signing_secret" in table.c:
        row["signing_secret"] = secrets.token_hex(32)
    if name == "sys_api_client":
        row["status"] = "disabled"
    if name == "ext_event_subscription":
        row["status"] = "disabled"
    # Resolve declared foreign keys to rows produced by this utility so related
    # list pages and document details can show their associated names.
    model_table = Base.metadata.tables.get(name, table)
    for foreign_key in model_table.foreign_keys:
        column = foreign_key.parent.name
        if name == "fin_voucher_entry" and column in {"voucher_id", "account_id"}:
            continue
        target_table = foreign_key.target_fullname.rsplit(".", 1)[0].rsplit(".", 1)[-1]
        if column in row and column != "parent_id" and target_table not in {"sys_user", "sys_role", "sys_menu", "sys_permission", "sys_org", "sys_department", "sys_org_membership"}:
            row[column] = uid(target_table, ((index - 1) % seed_count(target_table)) + 1)
    if name == "sales_delivery":
        order_index = SALES_DELIVERY_ORDER_INDEX[index - 1]
        row["order_id"] = uid("sales_order", order_index)
    elif name == "purchase_receipt":
        order_index = PURCHASE_RECEIPT_ORDER_INDEX[index - 1]
        row["order_id"] = uid("purchase_order", order_index)
    elif name == "sales_return":
        row["source_delivery_id"] = uid("sales_delivery", 2)
    elif name == "purchase_return":
        row["source_receipt_id"] = uid("purchase_receipt", 2)
    if name == "mfg_routing_operation":
        row["line_no"] = ((index - 1) // seed_count("mfg_routing")) + 1
    elif "line_no" in row and name != "fin_voucher_entry":
        # Repeatable foreign-key assignment groups rows by parent index. Use
        # the parent participating in a unique(parent, line_no) constraint so
        # multi-operation routings receive distinct line numbers.
        unique_parent = None
        for constraint in [*table.constraints, *table.indexes]:
            parent_columns = [column for column in constraint.columns if column.name != "line_no"]
            if ((isinstance(constraint, UniqueConstraint) or getattr(constraint, "unique", False))
                    and "line_no" in {column.name for column in constraint.columns}
                    and len(parent_columns) == 1):
                unique_parent = parent_columns[0].name
                break
        parent_table = None
        if unique_parent:
            for foreign_key in model_table.foreign_keys:
                if foreign_key.parent.name == unique_parent:
                    parent_table = foreign_key.target_fullname.rsplit(".", 1)[0].rsplit(".", 1)[-1]
                    break
        row["line_no"] = ((index - 1) // max(seed_count(parent_table), 1)) + 1 if parent_table else 1
    elif name == "fin_voucher_entry":
        row["line_no"] = 1 if index % 2 else 2

    # Replace generic filler with business-appropriate values on user-facing
    # fields. Numeric suffixes remain only in explicit codes/document numbers.
    field_values = REALISTIC_FIELD_VALUES.get(name, {})
    for field_name, values in field_values.items():
        if field_name not in row or not values:
            continue
        value = values[(index - 1) % len(values)]
        row[field_name] = Decimal(value) if field_name in {"rate", "original_value", "accumulated_depreciation"} else value

    if name == "fin_reconciliation_statement":
        party_table = "md_customer" if row.get("statement_type") == "ar" else "md_supplier"
        row["party_id"] = uid(party_table, ((index - 1) // 2) + 1)
    if name == "inv_reservation":
        row["source_type"] = "sales_order"
        row["source_id"] = uid("sales_order", index)
    if name == "org_intercompany_transaction":
        row["from_org_id"] = ORG
        row["to_org_id"] = uid("sys_org", 2 if index % 2 else 3)
        row["source_type"] = "sales_order"
        row["source_id"] = uid("sales_order", ((index - 1) % seed_count("sales_order")) + 1)
    if name == "tax_invoice":
        invoice_tax_rates = [Decimal("13"), Decimal("9"), Decimal("6"), Decimal("3"), Decimal("0"), Decimal("0")]
        tax_rate = invoice_tax_rates[(index - 1) % len(invoice_tax_rates)]
        row["amount"] = order_amount(index)
        row["tax_amount"] = (row["amount"] * tax_rate / (Decimal("100") + tax_rate)).quantize(Decimal("0.01")) if tax_rate else Decimal("0")
        row["source_type"] = "sales_order"
        row["source_id"] = uid("sales_order", ((index - 1) % seed_count("sales_order")) + 1)
        row["party_id"] = uid("md_customer", ((index - 1) % seed_count("md_customer")) + 1)
        row["tax_code"] = ["VAT-13", "VAT-09", "VAT-06", "VAT-03", "VAT-EXEMPT", "VAT-EXPORT"][(index - 1) % 6]
    return row


def perform_reset_and_seed(metadata: MetaData, connection, skip: set[str]) -> list[str]:
    clear_business_rows_and_rebuild_catalog(metadata, connection)
    ensure_preserved_user_context(metadata, connection)
    results: list[str] = []
    ordered = ordered_table_names(metadata, skip)
    enum_columns = {"status", "result", "disposition", "severity", "stage", "control_status", "capa_status", "rating", "from_status", "to_status", "event_type", "action_type", "task_type", "order_type", "inspection_type", "change_type", "object_type", "service_type", "invoice_type", "membership_type", "notification_type", "document_type", "visibility", "reset_cycle", "basis", "source_type", "statement_type", "match_type", "cost_type", "exception_type"}

    for name in ordered:
        table = metadata.tables[name]
        count = seed_count(name)
        for index in range(1, count + 1):
            row = table_rows(table, index)
            for key, value in row.items():
                if not isinstance(value, str) or key in enum_columns:
                    continue
                if any(term in value.casefold() for term in ("demo", "example", "示例", "测试", "演示")) or re.search(r"\btest\b", value, re.IGNORECASE):
                    raise RuntimeError(f"{name}[{index}] 含有不允许的占位文案")
            try:
                connection.execute(insert(table).values(row))
            except SQLAlchemyError as exc:
                raise RuntimeError(f"插入 {name}[{index}] 失败，整次重置将回滚：{type(exc).__name__}") from exc
        results.append(f"{name}:{count}")

    # Build the document center from actual business rows so every relation
    # follows a real source/target pair instead of synthetic polymorphic IDs.
    from app.services.document_service import sync_documents

    with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
        sync_documents(session, SimpleNamespace(org_id=ORG))
    document_count = connection.scalar(select(func.count()).select_from(metadata.tables["biz_document"])) or 0
    relation_count = connection.scalar(select(func.count()).select_from(metadata.tables["biz_document_relation"])) or 0
    document_table = metadata.tables["biz_document"]
    relation_table = metadata.tables["biz_document_relation"]
    document_keys = {
        (str(row.business_type), str(row.business_id))
        for row in connection.execute(select(document_table.c.business_type, document_table.c.business_id)).all()
    }
    for relation in connection.execute(select(relation_table)).mappings():
        source_key = (str(relation["from_type"]), str(relation["from_id"]))
        target_key = (str(relation["to_type"]), str(relation["to_id"]))
        if source_key not in document_keys or target_key not in document_keys:
            missing = source_key if source_key not in document_keys else target_key
            raise RuntimeError(f"业务单据关系端点 {missing[0]}:{missing[1]} 无对应单据，整次重置将回滚")
    results.extend([f"biz_document:{document_count}", f"biz_document_relation:{relation_count}"])

    # Check the SQLAlchemy model foreign-key graph too. The production schema
    # has several relations that were created without physical MySQL FKs.
    for name in ordered:
        child = metadata.tables[name]
        model_child = Base.metadata.tables.get(name, child)
        for foreign_key in model_child.foreign_keys:
            target_table, target_column_name = foreign_key.target_fullname.rsplit(".", 1)
            parent_name = target_table.rsplit(".", 1)[-1]
            if parent_name not in metadata.tables:
                continue
            parent = metadata.tables[parent_name]
            child_column = child.c.get(foreign_key.parent.name)
            parent_column = parent.c.get(target_column_name)
            if child_column is None or parent_column is None:
                continue
            orphan_count = connection.scalar(
                select(func.count()).select_from(child.outerjoin(parent, child_column == parent_column))
                .where(child_column.is_not(None), parent_column.is_(None))
            ) or 0
            if orphan_count:
                samples = connection.execute(
                    select(child_column).select_from(child.outerjoin(parent, child_column == parent_column))
                    .where(child_column.is_not(None), parent_column.is_(None)).limit(3)
                ).scalars().all()
                raise RuntimeError(f"{name}.{child_column.name} 有 {orphan_count} 条未匹配关联（{samples[:3]}），整次重置将回滚")
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--reset-and-seed", action="store_true")
    mode.add_argument("--dry-run-reset-and-seed", action="store_true")
    args = parser.parse_args()
    if engine.url.database != "erp" or engine.url.host not in {"mysql", "shop-mysql"}:
        raise RuntimeError("目标必须是 shop-mysql 容器中的 erp 数据库")

    metadata = MetaData()
    metadata.reflect(bind=engine)
    skip = {
        "sys_org", "sys_department", "sys_org_membership", "sys_user", "sys_role", "sys_menu", "sys_permission", "sys_user_role", "sys_role_menu", "sys_role_permission", "sys_user_data_scope",
        "sys_schema_migration", "sys_operation_log", "sys_login_log", "sys_backup_record", "sys_idempotency_record",
        "auth_captcha_challenge", "biz_attachment", "biz_export_job", "biz_document", "biz_document_relation",
    }
    # Runtime migrations leave physical snapshots with table names ending in
    # or containing `_backup`; keep the snapshots empty instead of treating
    # them as live business screens.
    skip.update(name for name in metadata.tables if "_backup" in name)
    connection = engine.connect()
    try:
        connection.exec_driver_sql("SET FOREIGN_KEY_CHECKS=0")
        connection.commit()
        transaction = connection.begin()
        try:
            results = perform_reset_and_seed(metadata, connection, skip)
            transaction.rollback() if args.dry_run_reset_and_seed else transaction.commit()
        except Exception:
            if transaction.is_active:
                transaction.rollback()
            raise
        finally:
            if connection.in_transaction():
                connection.rollback()
            connection.exec_driver_sql("SET FOREIGN_KEY_CHECKS=1")
            connection.commit()
    finally:
        connection.close()

    print("\n".join(results))
    print("结果：事务已回滚（仅预演）" if args.dry_run_reset_and_seed else "结果：重置与造数事务已提交")


if __name__ == "__main__":
    main()
