from app.core.response import fail, ok


def test_ok_uses_unified_response_contract():
    assert ok({"id": "1"}, "完成") == {
        "code": 0,
        "msg": "完成",
        "data": {"id": "1"},
    }


def test_fail_uses_unified_response_contract():
    assert fail(403, "无权访问") == {
        "code": 403,
        "msg": "无权访问",
        "data": None,
    }
