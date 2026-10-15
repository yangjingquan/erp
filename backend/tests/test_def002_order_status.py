"""DEF-002: status=active must not render as 未知状态; seeds must not write active on docs."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ORDER_STATUS_TS = ROOT / "frontend" / "src" / "utils" / "orderStatus.ts"
SEED = ROOT / "backend" / "tools" / "seed_realistic_data.py"
ORDER_STATUS_TAG = ROOT / "frontend" / "src" / "components" / "OrderStatusTag.vue"


def _load_order_status_labels() -> dict[str, str]:
    text = ORDER_STATUS_TS.read_text(encoding="utf-8")
    block = re.search(r"orderStatusLabels:\s*Record<string,\s*string>\s*=\s*\{([^}]+)\}", text, re.S)
    assert block, "orderStatusLabels block missing"
    labels = dict(re.findall(r'(\w+)\s*:\s*"([^"]+)"', block.group(1)))
    return labels


def getOrderStatusLabel(value: str) -> str:
    labels = _load_order_status_labels()
    return labels.get(value, "未知状态")


def test_get_order_status_label_active_not_unknown():
    label = getOrderStatusLabel("active")
    assert label != "未知状态"
    assert label == "生效"


def test_order_status_ts_exports_alias_and_active():
    text = ORDER_STATUS_TS.read_text(encoding="utf-8")
    assert "active: \"生效\"" in text
    assert "function getOrderStatusLabel" in text
    assert "active: \"success\"" in text


def test_order_status_tag_only_warns_unknown():
    # active is now known, so console.warn path uses isKnownOrderStatus
    text = ORDER_STATUS_TAG.read_text(encoding="utf-8")
    assert "isKnownOrderStatus" in text
    assert "console.warn" in text  # still warns for truly unknown


def test_seed_document_tables_never_use_active():
    # Import enum_value from seed module without connecting to DB heavily
    import importlib.util
    import sys

    # Minimal load: exec only STATUS_POOLS / enum_value parts by importing after stubbing DB
    sys.path.insert(0, str(ROOT / "backend"))
    # Avoid engine connect: seed imports engine at module level. Read pools via regex + exec snippet.
    text = SEED.read_text(encoding="utf-8")
    assert "DOCUMENT_WORKFLOW_TABLES" in text
    assert "sales_order" in text
    # Evaluate STATUS_POOLS for document tables
    ns: dict = {}
    pools_match = re.search(r"STATUS_POOLS:\s*dict\[str,\s*dict\[str,\s*list\[str\]\]\]\s*=\s*(\{.*?\n\})", text, re.S)
    assert pools_match
    # Safer: check each listed order table pool does not contain active
    for table in ("sales_quote", "sales_order", "purchase_order", "purchase_request", "hr_leave_request"):
        m = re.search(rf'"{table}":\s*\{{[\s\S]*?"status":\s*\[([^\]]+)\]', text)
        assert m, f"missing STATUS_POOLS for {table}"
        pool = [s.strip().strip('"') for s in m.group(1).split(",")]
        assert "active" not in pool, f"{table} pool still has active: {pool}"


def test_remap_function_exists():
    mig = (ROOT / "backend" / "app" / "services" / "runtime_migrations.py").read_text(encoding="utf-8")
    assert "def remap_document_active_status" in mig
    assert "WHERE status = 'active'" in mig
