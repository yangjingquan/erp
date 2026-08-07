from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db
from app.core.database import Base
from app.core.security import hash_password
from app.main import app
from app.models.system import SysUser


@pytest.fixture
def client_and_session() -> Generator[tuple[TestClient, Session], None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            SysUser(
                id="user-1",
                org_id="org-1",
                department_id="dept-1",
                username="alice",
                display_name="Alice",
                password_hash=hash_password("Password@123"),
                is_superuser=False,
            )
        )
        session.commit()

        def override_get_db():
            yield session

        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as client:
            yield client, session
        app.dependency_overrides.clear()
