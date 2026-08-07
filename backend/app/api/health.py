from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.response import ok
from app.services.startup_check import check_schema

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        schema = check_schema(db)
        database = {
            "connected": True,
            "initialized": schema.initialized,
            "missing_tables": schema.missing_tables,
        }
        msg = "服务正常" if schema.initialized else schema.guidance
    except SQLAlchemyError as exc:
        database = {
            "connected": False,
            "initialized": False,
            "error": exc.__class__.__name__,
        }
        msg = "服务正常，数据库暂不可用"
    return ok({"service": "up", "database": database}, msg)
