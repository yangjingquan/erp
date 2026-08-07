### Task 5: 库位、批次、FIFO 成本层、呆滞库存和多仓隔离

**Files:**
- Create: `backend/app/models/inventory_advanced.py`
- Create: `backend/app/schemas/inventory_advanced.py`
- Create: `backend/app/services/inventory_advanced_service.py`
- Create: `backend/app/api/inventory_advanced.py`
- Create: `backend/tests/test_inventory_advanced_phase2.py`
- Modify: `backend/app/services/inventory_service.py`
- Modify: `backend/app/models/inventory.py`
- Modify: `backend/app/main.py`
- Modify: `database/init.sql`

**Interfaces:**
- `create_location(db, warehouse_id, zone_id, payload, context) -> InvLocation`
- `create_batch(db, material_id, payload, context) -> InvBatch`
- `post_fifo_inbound(db, source_type, source_id, warehouse_id, location_id, material_id, batch_id, quantity, unit_cost, context) -> list[InvCostLayer]`
- `post_fifo_outbound(db, source_type, source_id, warehouse_id, location_id, material_id, batch_id, quantity, context) -> list[dict]`
- `list_slow_moving(db, context, as_of) -> list[dict]`
- `assert_warehouse_access(context, warehouse_id) -> None`

- [ ] **Step 1: Write failing FIFO and isolation tests**

```python
def test_fifo_outbound_consumes_oldest_layers_and_records_source_layer():
    post_fifo_inbound("receipt", "r1", "wh-1", "loc-1", "m-1", "b-1", "3", "10")
    post_fifo_inbound("receipt", "r2", "wh-1", "loc-1", "m-1", "b-2", "4", "12")
    consumed = post_fifo_outbound("delivery", "d1", "wh-1", "loc-1", "m-1", None, "5")
    assert [(row["quantity"], row["unit_cost"]) for row in consumed] == [("3", "10"), ("2", "12")]

def test_user_cannot_read_or_move_stock_in_unassigned_warehouse():
    assert stock_request("wh-2", user="dept-user").status_code == 403
```

- [ ] **Step 2: Run tests to verify RED**

Run: `cd backend && pytest tests/test_inventory_advanced_phase2.py -q`  
Expected: FAIL because location, batch, cost-layer and warehouse access services are absent.

- [ ] **Step 3: Implement location, batch, stock extension, and FIFO layer allocation**

Add unique `(warehouse_id, code)` location validation, batch expiry/status, and cost layers with `remaining_quantity`. Extend inventory transaction serialization with location, batch and consumed layer IDs. Inbound creates one layer; outbound locks available layers, consumes in `created_at` order, rejects insufficient quantity and emits immutable consumption rows.

- [ ] **Step 4: Implement slow-moving snapshots and warehouse access checks**

Add rules by organization/material/warehouse and compute days since last inbound/outbound without mutating stock. Apply `assert_warehouse_access` to all advanced inventory list and write endpoints, including production and scan calls.

- [ ] **Step 5: Run FIFO,一期库存 and compile tests**

Run: `cd backend && pytest tests/test_inventory_advanced_phase2.py tests/test_inventory_ledger.py -q && python -m compileall -q app`  
Expected: FIFO ordering, insufficient stock, batch/location trace, slow-moving thresholds, multi-warehouse isolation and一期库存 tests pass.

---

