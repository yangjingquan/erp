from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.database import get_db
from app.core.response import ok
from app.services.auth_service import UserContext
from app.services.search_service import global_search

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
def search(q: str = Query(min_length=1), context: UserContext = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(global_search(db, context, q))
