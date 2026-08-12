from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


settings = get_settings()
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=280,
    future=True,
)


@event.listens_for(engine, "connect")
def set_database_session_timezone(dbapi_connection, _connection_record) -> None:
    """Keep MySQL CURRENT_TIMESTAMP aligned with the ERP business timezone."""
    if engine.dialect.name != "mysql":
        return
    with dbapi_connection.cursor() as cursor:
        cursor.execute("SET time_zone = %s", (settings.database_time_zone,))


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
