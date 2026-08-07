from typing import Any


def ok(data: Any = None, msg: str = "操作成功") -> dict[str, Any]:
    return {"code": 0, "msg": msg, "data": data}


def fail(code: int, msg: str, data: Any = None) -> dict[str, Any]:
    return {"code": code, "msg": msg, "data": data}
