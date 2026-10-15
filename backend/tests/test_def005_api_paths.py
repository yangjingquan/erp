"""DEF-005: frontend uses canonical paths; wrong list paths cleaned / aliased."""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
FE_API = ROOT / "frontend" / "src" / "api"


def test_frontend_uses_canonical_paths():
    production = (FE_API / "production.ts").read_text(encoding="utf-8")
    phase2 = (FE_API / "phase2.ts").read_text(encoding="utf-8")
    assert 'http.get("/production/plan-runs")' in production
    assert 'http.get("/production/mps")' in production
    assert 'http.get("/phase2/hr/leave-requests")' in phase2
    # Frontend must not call the misleading list path as primary
    assert 'http.get("/production/mrp-runs")' not in production
    assert 'http.get("/hr/leave-requests")' not in phase2
    assert 'http.get("/hr/leave-requests")' not in (FE_API / "hr.ts").read_text(encoding="utf-8")


def test_no_wrong_paths_in_frontend_src():
    bad = []
    for path in (ROOT / "frontend" / "src").rglob("*"):
        if path.suffix not in {".ts", ".vue", ".js"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(r'["`]/production/mrp-runs["`\']', text):
            # detail with id is ok on backend only; frontend should not list via mrp-runs
            if "mrp-runs/" not in text and "plan-runs" not in text:
                bad.append(str(path))
        if re.search(r'["`]/hr/leave-requests', text) and "phase2/hr/leave-requests" not in text:
            bad.append(str(path))
    assert bad == [], f"wrong paths remain: {bad}"


def test_backend_aliases_exist():
    prod = (ROOT / "backend/app/api/production.py").read_text(encoding="utf-8")
    hr = (ROOT / "backend/app/api/hr.py").read_text(encoding="utf-8")
    assert '@router.get("/mrp-runs")' in prod
    assert "alias_of" in prod
    assert '@router.get("/leave-requests")' in hr
    assert "phase2/hr/leave-requests" in hr
