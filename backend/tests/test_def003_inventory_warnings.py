"""DEF-003: inventory warnings should be single-digit in demo fixtures."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "backend" / "tools" / "seed_realistic_data.py"


def _simulate_seed_warnings(n_materials: int = 40, n_stocks: int = 40) -> int:
    """Mirror calibrated seed rules without hitting the database."""
    min_stock = {}
    for index in range(1, n_materials + 1):
        min_stock[index] = Decimal("80") if index <= 3 else Decimal("0")

    warnings = 0
    for index in range(1, n_stocks + 1):
        material_index = (index % 40) + 1
        quantity = Decimal("20") if material_index <= 3 else Decimal(str(120 + index * 2))
        ms = min_stock[material_index]
        if ms > 0 and quantity < ms:
            warnings += 1
    return warnings


def test_demo_fixture_warning_count_is_single_digit():
    count = _simulate_seed_warnings()
    assert count < 10, f"expected single-digit warnings, got {count}"
    assert count >= 1, "sample low-stock SKUs should still produce some warnings"


def test_seed_source_calibrates_min_stock():
    text = SEED.read_text(encoding="utf-8")
    assert 'row["min_stock"] = Decimal("0")' in text
    assert 'row["min_stock"] = Decimal("80")' in text
    assert "material_index <= 3" in text


def test_warning_queries_require_min_stock_positive():
    inv = (ROOT / "backend/app/services/inventory_service.py").read_text(encoding="utf-8")
    dash = (ROOT / "backend/app/services/dashboard_service.py").read_text(encoding="utf-8")
    assert "MdMaterial.min_stock > 0" in inv
    assert "MdMaterial.min_stock > 0" in dash


def test_calibrate_migration_exists():
    mig = (ROOT / "backend/app/services/runtime_migrations.py").read_text(encoding="utf-8")
    assert "def calibrate_demo_min_stock" in mig
    assert "MAT-0001" in mig
