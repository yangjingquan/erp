import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError
from app.core.response import fail

logger = logging.getLogger("erp.api")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content=fail(exc.code, exc.msg, exc.data, trace_id=getattr(request.state, "request_id", ""), extended=True),
            headers={"X-Request-ID": getattr(request.state, "request_id", "")},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content=fail(422, "请求参数校验失败", exc.errors(), trace_id=getattr(request.state, "request_id", ""), field_errors=exc.errors(), extended=True),
            headers={"X-Request-ID": getattr(request.state, "request_id", "")},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request, exc: Exception
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "")
        logger.exception("Unhandled request error request_id=%s", request_id)
        return JSONResponse(
            status_code=200,
            content=fail(500, "系统内部错误", {"request_id": request_id}, trace_id=request_id, extended=True),
            headers={"X-Request-ID": request_id},
        )
