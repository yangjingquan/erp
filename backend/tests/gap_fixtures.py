"""Shared in-memory SQLite fixtures for GAP-xx functional tests."""
from __future__ import annotations

import importlib
import pkgutil
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
import app.models as _models

for _m in pkgutil.iter_modules(_models.__path__):
    importlib.import_module(f"app.models.{_m.name}")

from app.models.master_data import MdCustomer, MdMaterial, MdSupplier, MdWarehouse  # noqa: E402
from app.models.system import SysUser  # noqa: E402
from app.services.auth_service import UserContext  # noqa: E402

ORG = "org-test"


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def ctx(db):
    user = SysUser(org_id=ORG, username="tester", display_name="测试员", password_hash="x", status="active", is_superuser=True)
    db.add(user)
    from app.models.configuration import CfgNumberRule
    for key in ("purchase_order", "purchase_receipt", "sales_order", "sales_delivery", "sales_return", "purchase_return", "sales_quote", "purchase_request"):
        db.add(CfgNumberRule(org_id=ORG, rule_key=key, prefix=key[:2].upper() + "-", date_format="%Y%m%d", sequence_length=4))
    db.flush()
    return UserContext(user=user, permissions={"*"})


@pytest.fixture()
def md(db, ctx):
    wh = MdWarehouse(org_id=ORG, code="WH1", name="测试仓")
    mat = MdMaterial(org_id=ORG, code="M1", name="测试物料", standard_cost=Decimal("8"))
    sup = MdSupplier(org_id=ORG, code="S1", name="测试供应商甲")
    cus = MdCustomer(org_id=ORG, code="C1", name="测试客户乙")
    db.add_all([wh, mat, sup, cus])
    db.commit()
    return SimpleNamespace(wh=wh, mat=mat, sup=sup, cus=cus)
