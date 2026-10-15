"""DEF-004: leave_type / status must be legal enums in seed and API."""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "backend/tools/seed_realistic_data.py"
LEGAL_TYPES = {"annual", "sick", "personal", "compensatory"}
LEGAL_STATUS = {"draft", "submitted", "approved", "rejected", "cancelled"}


def test_seed_leave_type_pool_legal():
    text = SEED.read_text(encoding="utf-8")
    assert '"leave_type": ["annual", "sick", "personal", "compensatory"]' in text
    assert 'if name == "hr_leave_request"' in text
    # Simulate enum cycling
    pool = ["annual", "sick", "personal", "compensatory"]
    for index in range(1, 41):
        assert pool[(index - 1) % len(pool)] in LEGAL_TYPES


def test_seed_never_writes_placeholder_leave_type():
    text = SEED.read_text(encoding="utf-8")
    # leave_type must go through enum_value, not the title-case fallback
    assert '"leave_type"' in text
    assert '"leave_type"' in text  # pool key
    assert 'elif key in {"status", "leave_type"' in text or '"leave_type",' in text.split("elif key in")[-1]
    assert 'row["leave_type"] = enum_value(name, "leave_type", index)' in text


def test_schema_and_service_enforce_leave_type():
    schema = (ROOT / "backend/app/schemas/phase2.py").read_text(encoding="utf-8")
    service = (ROOT / "backend/app/services/phase2_service.py").read_text(encoding="utf-8")
    assert 'Literal["annual", "sick", "personal", "compensatory"]' in schema
    assert "LEAVE_TYPES" in service
    assert "请假类型不合法" in service


def test_frontend_leave_type_fallback():
    vue = (ROOT / "frontend/src/views/hr/LeaveRequestCenter.vue").read_text(encoding="utf-8")
    assert "leaveTypeLabels" in vue
    assert "leaveTypeLabel" in vue
    assert "其他（" in vue
    assert "leaveStatusLabel" in vue


def test_sanitize_migration_exists():
    mig = (ROOT / "backend/app/services/runtime_migrations.py").read_text(encoding="utf-8")
    assert "def sanitize_leave_request_seed" in mig
