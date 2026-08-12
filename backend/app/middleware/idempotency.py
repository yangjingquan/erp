import hashlib
import json
from datetime import datetime, timedelta

from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.dependencies import get_db
from app.core.security import decode_token
from app.core.time import local_now
from app.models.collaboration import SysIdempotencyRecord
from app.models.system import SysUser


WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _now() -> datetime:
    return local_now()


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        key = request.headers.get("Idempotency-Key", "").strip()
        if request.method not in WRITE_METHODS or not key or not request.url.path.startswith("/api/"):
            return await call_next(request)
        if len(key) > 128:
            return JSONResponse(status_code=200, content={"code": 400, "msg": "Idempotency-Key 不能超过 128 个字符", "data": None})
        try:
            token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            user_id = str(decode_token(token).get("sub") or "")
        except Exception:
            return await call_next(request)
        if not user_id:
            return await call_next(request)

        body = await request.body()
        request_hash = hashlib.sha256(body).hexdigest()
        dependency = request.app.dependency_overrides.get(get_db, get_db)
        generator = dependency()
        db = next(generator)
        def close_generator() -> None:
            close = getattr(generator, "close", None)
            if close:
                close()
        record = None
        try:
            record = db.scalar(select(SysIdempotencyRecord).where(
                SysIdempotencyRecord.user_id == user_id,
                SysIdempotencyRecord.idempotency_key == key,
                SysIdempotencyRecord.method == request.method,
                SysIdempotencyRecord.path == request.url.path,
            ))
            if record is not None:
                if record.request_hash != request_hash:
                    close_generator()
                    return JSONResponse(status_code=200, content={"code": 409, "msg": "同一 Idempotency-Key 不能用于不同请求", "data": None})
                if record.response_status == -1:
                    close_generator()
                    return JSONResponse(status_code=200, content={"code": 409, "msg": "相同请求正在处理中，请稍后重试", "data": None})
                replay = JSONResponse(status_code=record.response_status, content=record.response_json, headers={"Idempotency-Replayed": "true"})
                close_generator()
                return replay
            user = db.get(SysUser, user_id)
            record = SysIdempotencyRecord(
                org_id=user.org_id if user else None,
                user_id=user_id,
                idempotency_key=key,
                method=request.method,
                path=request.url.path,
                request_hash=request_hash,
                response_status=-1,
                response_json={},
                created_at=_now(),
                expires_at=_now() + timedelta(hours=24),
            )
            db.add(record)
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            close_generator()
            return await call_next(request)

        try:
            response = await call_next(request)
            response_body = b"".join([chunk async for chunk in response.body_iterator])
            response_headers = dict(response.headers)
            try:
                response_json = json.loads(response_body or b"null")
            except (TypeError, json.JSONDecodeError):
                response_json = {"code": 500, "msg": "幂等响应不是 JSON", "data": None}
            record = db.get(SysIdempotencyRecord, record.id)
            record.response_status = response.status_code
            record.response_json = response_json
            db.commit()
            return Response(content=response_body, status_code=response.status_code, headers=response_headers, media_type=response.media_type)
        except Exception:
            if record is not None:
                current = db.get(SysIdempotencyRecord, record.id)
                if current is not None:
                    db.delete(current)
                    db.commit()
            raise
        finally:
            close_generator()
