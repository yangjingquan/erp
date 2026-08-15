from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.auth import sys_role_menu, sys_role_permission
from app.models.base import new_uuid
from app.models.system import SysMenu, SysPermission, SysRole


ROOT_CATALOG = [
    ("dashboard:view", "经营看板", "/dashboard", 1),
    ("master:view", "基础资料", "/master-data", 10),
    ("sales:view", "销售管理", "/sales", 20),
    ("purchase:view", "采购管理", "/purchase", 30),
    ("inventory:view", "库存管理", "/inventory", 40),
    ("finance:view", "财务管理", "/finance", 50),
    ("crm:view", "CRM 管理", "/crm", 60),
    ("production:view", "生产管理", "/production", 35),
    ("cost:view", "成本管理", "/cost", 45),
    ("quality:view", "质量管理", "/quality", 55),
    ("hr:view", "人事管理", "/hr", 65),
    ("operations:view", "运营协同", "/operations", 70),
    ("system:view", "系统运维", "/system", 90),
    ("config:view", "系统配置", "/settings", 95),
]

PAGE_CATALOG = [
    ("master:view", "物料档案", "/master-data/materials", 1),
    ("master:view", "客户档案", "/master-data/customers", 2),
    ("master:view", "供应商档案", "/master-data/suppliers", 3),
    ("master:view", "仓库档案", "/master-data/warehouses", 4),
    ("master:view", "计量单位", "/master-data/units", 5),
    ("master:view", "税率档案", "/master-data/tax-rates", 6),
    ("sales:view", "销售报价", "/sales/quotes", 1),
    ("sales:view", "销售订单", "/sales/orders", 2),
    ("sales:view", "销售退货", "/sales/returns", 3),
    ("purchase:view", "采购申请", "/purchase/requests", 1),
    ("purchase:view", "采购订单", "/purchase/orders", 2),
    ("purchase:view", "采购退货", "/purchase/returns", 3),
    ("inventory:view", "库存台账", "/inventory/stock", 1),
    ("inventory:view", "库存流水", "/inventory/transactions", 2),
    ("inventory:view", "库存调拨", "/inventory/transfers", 3),
    ("inventory:view", "库存盘点", "/inventory/counts", 4),
    ("finance:view", "应收账款", "/finance/receivables", 1),
    ("finance:view", "应付账款", "/finance/payables", 2),
    ("finance:view", "费用报销", "/finance/expenses", 3),
    ("finance:view", "会计凭证", "/finance/vouchers", 4),
    ("crm:view", "线索管理", "/crm/leads", 1),
    ("crm:view", "商机管理", "/crm/opportunities", 2),
    ("inventory:view", "移动扫码", "/inventory/scan", 5),
    ("inventory:view", "仓位管理", "/inventory/locations", 6),
    ("inventory:view", "批次管理", "/inventory/batches", 7),
    ("inventory:view", "库存控制中心", "/inventory/control-center", 8),
    ("inventory:view", "WMS 作业中心", "/inventory/wms-tasks", 8),
    ("system:view", "操作日志", "/system/operation-logs", 1),
    ("system:view", "用户管理", "/system/users", 2),
    ("system:view", "权限设置", "/system/admin", 3),
    ("system:view", "备份恢复", "/system/backup", 4),
    ("config:view", "全局参数", "/settings/parameters", 1),
    ("config:view", "审批流程", "/settings/workflow", 2),
    ("config:view", "打印模板", "/settings/print-templates", 3),
    ("production:view", "BOM", "/production/boms", 1),
    ("production:view", "MRP", "/production/mrp", 2),
    ("production:view", "生产工单", "/production/work-orders", 3),
    ("production:view", "工艺与产能", "/production/resources", 4),
    ("production:view", "生产执行控制台", "/production/execution", 5),
    ("finance:view", "财务控制中心", "/finance/controls", 8),
    ("cost:view", "成本分摊", "/cost/allocations", 1),
    ("cost:view", "期间结账", "/cost/period-close", 2),
    ("quality:view", "质量检验", "/quality/inspections", 1),
    ("quality:view", "不合格与 CAPA", "/quality/nonconformances", 2),
    ("quality:view", "质量分析与索赔", "/quality/analytics", 3),
    ("hr:view", "人事员工档案", "/hr/employees", 1),
    ("hr:view", "薪资核算", "/hr/payroll", 2),
    ("hr:view", "人事全生命周期", "/hr/people-ops", 3),
    ("operations:view", "运输、OCR 与预算预测", "/operations/advanced", 1),
    ("config:view", "API 客户端", "/settings/api-clients", 4),
    ("production:view", "PLM 工程变更", "/plm/changes", 6),
    ("purchase:view", "供应商协同", "/srm/collaboration", 4),
    ("cost:view", "项目与成本", "/projects/cost", 3),
    ("production:view", "资产与维修", "/eam/service", 7),
    ("crm:view", "客户 360", "/crm/customer-360", 3),
    ("config:view", "集团与内部交易", "/platform/group", 6),
    ("config:view", "税务与电子发票", "/platform/compliance", 7),
    ("config:view", "低代码对象", "/platform/low-code", 8),
    ("dashboard:view", "指标与异常助手", "/platform/metrics", 9),
]

LEGACY_FUNCTIONS = {
    "master:view": [("master:manage", "基础资料业务操作")],
    "system:view": [("system:manage", "系统管理")],
    "system:admin": [
        ("system:user:manage", "用户管理"),
        ("system:role:manage", "角色管理"),
        ("system:department:manage", "部门管理"),
        ("system:menu:manage", "菜单管理"),
    ],
    "production:view": [("production:view", "查看生产计划"), ("production:manage", "生产计划管理")],
    "sales:view": [("sales:manage", "销售业务操作")],
    "purchase:view": [("purchase:manage", "采购业务操作")],
    "inventory:view": [("inventory:view", "查看库存"), ("inventory:manage", "库存管理")],
    "finance:view": [("finance:manage", "财务业务操作")],
    "crm:view": [("crm:view", "查看 CRM"), ("crm:manage", "CRM 业务操作")],
    "cost:view": [("cost:view", "查看成本"), ("cost:manage", "成本业务操作"), ("cost:close", "期间结账"), ("cost:period:reopen", "重开会计期间")],
    "quality:view": [("quality:view", "查看质量检验"), ("quality:manage", "质量业务操作")],
    "hr:view": [("hr:view", "查看人事"), ("hr:salary:view", "查看薪资"), ("hr:salary:manage", "薪资业务操作"), ("hr:employee:manage", "员工信息管理")],
    "operations:view": [("operations:manage", "运营业务操作")],
    "config:view": [("config:manage", "系统配置操作"), ("workflow:manage", "审批流程配置"), ("workflow:approve", "审批任务处理")],
}


def _page_code(path: str) -> str:
    return f"page:{path.strip('/').replace('/', ':')}:view"


def ensure_permission_catalog(db: Session) -> None:
    roots: dict[str, SysMenu] = {}
    # Several legacy permissions belong to a module rather than a single page.
    # Keep one canonical row per code while the catalog is being upgraded so
    # existing MySQL installations do not receive duplicate inserts when a
    # module has multiple pages.
    known_permission_codes = set(db.scalars(select(SysPermission.code)).all())
    for code, name, path, sort_order in ROOT_CATALOG:
        row = db.scalar(select(SysMenu).where(SysMenu.code == code))
        if row is None:
            row = SysMenu(
                id=new_uuid(), code=code, name=name, path=path,
                component=name, menu_type="menu", sort_order=sort_order,
            )
            db.add(row)
            db.flush()
        else:
            row.name = name
            row.path = path
            row.sort_order = sort_order
        roots[code] = row

    for parent_code, name, path, sort_order in PAGE_CATALOG:
        code = _page_code(path)
        row = db.scalar(select(SysMenu).where(SysMenu.code == code))
        if row is None:
            row = SysMenu(
                id=new_uuid(), parent_id=roots[parent_code].id, code=code,
                name=name, path=path, component=name, menu_type="menu",
                sort_order=sort_order,
            )
            db.add(row)
            db.flush()
            # Preserve the old module-level access model for roles that already
            # had the parent module selected before page-level permissions were
            # introduced. Administrators can narrow it immediately afterwards.
            existing_role_ids = db.scalars(
                select(sys_role_menu.c.role_id).where(sys_role_menu.c.menu_id == roots[parent_code].id)
            ).all()
            for role_id in existing_role_ids:
                db.execute(sys_role_menu.insert().values(role_id=role_id, menu_id=row.id))
        else:
            row.parent_id = roots[parent_code].id
            row.path = path
            row.name = name
            row.sort_order = sort_order
        # When a page is re-parented (for example from the legacy system root
        # to the new configuration root), preserve existing role visibility by
        # ensuring the new parent is also selected for roles that already have
        # this page.
        page_role_ids = db.scalars(
            select(sys_role_menu.c.role_id).where(sys_role_menu.c.menu_id == row.id)
        ).all()
        for role_id in page_role_ids:
            has_parent = db.scalar(
                select(sys_role_menu.c.role_id).where(
                    sys_role_menu.c.role_id == role_id,
                    sys_role_menu.c.menu_id == roots[parent_code].id,
                )
            )
            if has_parent is None:
                db.execute(sys_role_menu.insert().values(role_id=role_id, menu_id=roots[parent_code].id))
        function_defs = [
            (f"{code}:create", "新增"),
            (f"{code}:edit", "编辑"),
            (f"{code}:delete", "删除"),
            (f"{code}:export", "导出"),
        ] + LEGACY_FUNCTIONS.get(parent_code, [])
        if path == "/system/users":
            function_defs.append(("system:user:manage", "用户管理"))
        if path == "/system/admin":
            function_defs += LEGACY_FUNCTIONS["system:admin"]
        for permission_code, permission_name in function_defs:
            if permission_code in known_permission_codes:
                continue
            db.add(SysPermission(
                id=new_uuid(), menu_id=row.id, code=permission_code,
                name=permission_name, permission_type="button",
            ))
            known_permission_codes.add(permission_code)

    # Existing installations may only have the old root permissions. Keep
    # those codes available and place them on their matching root menu.
    for menu_code, functions in LEGACY_FUNCTIONS.items():
        menu = db.scalar(select(SysMenu).where(SysMenu.code == menu_code))
        if menu is None:
            continue
        for permission_code, permission_name in functions:
            if permission_code in known_permission_codes:
                continue
            db.add(SysPermission(
                id=new_uuid(), menu_id=menu.id, code=permission_code,
                name=permission_name, permission_type="button",
            ))
            known_permission_codes.add(permission_code)
    db.flush()


def _tree(rows: list[SysMenu]) -> list[dict]:
    nodes = {
        row.id: {"id": row.id, "code": row.code, "name": row.name, "path": row.path, "parent_id": row.parent_id, "children": []}
        for row in rows
    }
    roots: list[dict] = []
    for node in nodes.values():
        parent = nodes.get(node["parent_id"])
        (parent["children"] if parent else roots).append(node)
    return roots


def get_permission_catalog(db: Session) -> dict:
    ensure_permission_catalog(db)
    db.commit()
    menus = db.scalars(select(SysMenu).where(SysMenu.status == "active").order_by(SysMenu.sort_order, SysMenu.code)).all()
    functions = db.execute(
        select(SysPermission, SysMenu.code, SysMenu.name)
        .join(SysMenu, SysMenu.id == SysPermission.menu_id)
        .where(SysMenu.status == "active")
        .order_by(SysMenu.sort_order, SysPermission.code)
    ).all()
    return {
        "pages": _tree(menus),
        "functions": [
            {"id": permission.id, "code": permission.code, "name": permission.name, "menu_id": menu_code, "menu_name": menu_name}
            for permission, menu_code, menu_name in functions
        ],
    }


def get_role_access(db: Session, role_id: str, context) -> dict:
    role = db.scalar(select(SysRole).where(SysRole.id == role_id, SysRole.org_id == context.org_id, SysRole.is_deleted.is_(False)))
    if role is None:
        raise AppError("角色不存在", code=404)
    return {
        "menu_ids": list(db.scalars(select(sys_role_menu.c.menu_id).where(sys_role_menu.c.role_id == role_id)).all()),
        "permission_ids": list(db.scalars(select(sys_role_permission.c.permission_id).where(sys_role_permission.c.role_id == role_id)).all()),
        "data_scope_type": role.data_scope_type,
    }


def save_role_access(db: Session, role_id: str, menu_ids: list[str], permission_ids: list[str], context, data_scope_type: str | None = None) -> dict:
    role = db.scalar(select(SysRole).where(SysRole.id == role_id, SysRole.org_id == context.org_id, SysRole.is_deleted.is_(False)))
    if role is None:
        raise AppError("角色不存在", code=404)
    if data_scope_type is not None:
        if data_scope_type not in {"all", "department", "own"}:
            raise AppError("数据范围无效", code=400)
        role.data_scope_type = data_scope_type
    ensure_permission_catalog(db)
    menu_rows = db.scalars(select(SysMenu).where(SysMenu.id.in_(menu_ids))).all() if menu_ids else []
    permission_rows = db.scalars(select(SysPermission).where(SysPermission.id.in_(permission_ids))).all() if permission_ids else []
    if len(menu_rows) != len(set(menu_ids)) or len(permission_rows) != len(set(permission_ids)):
        raise AppError("权限目录中存在无效项", code=400)
    selected_menu_ids = set(menu_ids)
    by_id = {row.id: row for row in menu_rows}
    for row in menu_rows:
        parent_id = row.parent_id
        while parent_id and parent_id not in selected_menu_ids:
            selected_menu_ids.add(parent_id)
            parent_id = by_id.get(parent_id).parent_id if by_id.get(parent_id) else db.scalar(select(SysMenu.parent_id).where(SysMenu.id == parent_id))
    db.execute(delete(sys_role_menu).where(sys_role_menu.c.role_id == role_id))
    db.execute(delete(sys_role_permission).where(sys_role_permission.c.role_id == role_id))
    for menu_id in selected_menu_ids:
        db.execute(sys_role_menu.insert().values(role_id=role_id, menu_id=menu_id))
    for permission_id in set(permission_ids):
        db.execute(sys_role_permission.insert().values(role_id=role_id, permission_id=permission_id))
    db.commit()
    return get_role_access(db, role_id, context)
