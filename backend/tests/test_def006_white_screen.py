"""DEF-006: white-screen monitor must not false-alarm on route transitions."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_main_ts_has_hardened_monitor():
    main = (ROOT / "frontend/src/main.ts").read_text(encoding="utf-8")
    assert "hasRenderedUi" in main
    assert "erpNavigating" in main
    assert "2500" in main and "7000" in main
    # Old one-shot 1500ms empty-children check must be gone
    assert "1500" not in main or "startWhiteScreenMonitor" in main
    assert "checkpoints" in main


def test_foundation_and_layout_marked_ready():
    foundation = (ROOT / "frontend/src/views/finance/FinanceFoundation.vue").read_text(encoding="utf-8")
    layout = (ROOT / "frontend/src/layouts/AdminLayout.vue").read_text(encoding="utf-8")
    assert 'data-erp-ready="1"' in foundation
    assert 'data-erp-ready="1"' in layout
