### Task 2: BOM、MPS 和 MRP 净需求计算

**Files:**
- Create: `backend/app/models/production.py`
- Create: `backend/app/schemas/production.py`
- Create: `backend/app/services/planning_service.py`
- Create: `backend/app/api/production.py`
- Create: `backend/tests/test_production_planning_phase2.py`
- Modify: `backend/app/main.py`
- Modify: `database/init.sql`

**Interfaces:**
- `create_bom(db, payload, context) -> MfgBom`
- `submit_bom(db, bom_id, context) -> MfgBom`
- `approve_bom(db, bom_id, context) -> MfgBom`
- `create_mps(db, payload, context) -> MfgMps`
- `run_mrp(db, mps_id, context) -> MfgMrpRun`
- `confirm_mrp_result(db, result_id, context) -> dict`

- [ ] **Step 1: Write failing tests for BOM lifecycle and MRP math**

```python
def test_approved_bom_mrp_uses_stock_and_open_orders(client_and_session):
    # finished F requires 2x component C; stock=3, open purchase=1, plan=5
    result = run_mrp_for_fixture(plan_quantity=5, bom_quantity=2, stock=3, open_purchase=1)
    assert result.net_requirement == Decimal("6")
    assert result.source_snapshot["available_stock"] == "3"

def test_bom_cannot_be_approved_with_duplicate_component_or_invalid_effective_range(client_and_session):
    response = create_invalid_bom_payload()
    assert response.status_code == 400
    assert "BOM" in response.json()["msg"]
```

- [ ] **Step 2: Run the tests to verify RED**

Run: `cd backend && pytest tests/test_production_planning_phase2.py -q`  
Expected: FAIL because production models, API, and planning service are absent.

- [ ] **Step 3: Implement BOM models, validation, and state transitions**

Create BOM headers/items/versions and MPS/MRP headers/results with UUID, org, audit, status and source fields. Validate component quantities, duplicate component rows, effective dates, circular BOM references and required approved version. Implement `draft → submitted → approved → disabled`; reject modification/deletion when referenced by MRP or work order. Add protected routes for create, submit, approve, list and detail.

- [ ] **Step 4: Implement deterministic MRP calculation**

Snapshot plan quantity, BOM version, stock, open sales/purchase quantities and safety stock. Recursively explode the BOM, calculate `gross_requirement - available_stock - open_supply + safety_stock`, quantize quantities to six decimals, and store every result with the run ID. A second run creates a new run; confirming the same result twice returns the original source document IDs.

- [ ] **Step 5: Run targeted tests and compile**

Run: `cd backend && pytest tests/test_production_planning_phase2.py -q && python -m compileall -q app`  
Expected: BOM lifecycle, MRP net requirement, duplicate confirmation, permission and invalid-input tests pass.

---

