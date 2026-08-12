from typing import Any


def ok(data: Any = None, msg: str = "操作成功") -> dict[str, Any]:
    return {"code": 0, "msg": msg, "data": data}


def fail(
    code: int,
    msg: str,
    data: Any = None,
    *,
    trace_id: str | None = None,
    field_errors: Any = None,
    extended: bool = False,
) -> dict[str, Any]:
    result = {"code": code, "msg": msg, "data": data}
    if extended:
        result.update(
            message=msg,
            field_errors=field_errors if field_errors is not None else [],
            trace_id=trace_id or "",
        )
    return result
