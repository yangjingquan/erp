### Task 3: 生产工单、领料、退料、报工和完工入库

**Files:**
- Modify: `backend/app/models/production.py`
- Modify: `backend/app/schemas/production.py`
- Create: `backend/app/services/production_service.py`
- Modify: `backend/app/api/production.py`
- Create: `backend/tests/test_work_order_phase2.py`
- Modify: `backend/app/services/inventory_service.py`
- Modify: `backend/app/models/inventory.py`

**Interfaces:**
- `create_work_order(db, payload, context) -> MfgWorkOrder`
- `release_work_order(db, work_order_id, context) -> MfgWorkOrder`
- `issue_material(db, work_order_id, items, context) -> MfgMaterialIssue`
- `return_material(db, issue_id, items, context) -> MfgMaterialReturn`
- `report_work(db, work_order_id, payload, context) -> MfgReport`
- `complete_work_order(db, work_order_id, context) -> MfgWorkOrder`

- [ ] **Step 1: Write failing end-to-end production tests**

```python
def test_work_order_issue_report_complete_updates_inventory_and_is_traceable(client_and_session):
    work_order = create_released_work_order(quantity="5")
    issue = issue_material(work_order.id, [{"material_id": "component-1", "quantity": "10"}])
    report = report_work(work_order.id, {"good_quantity": "5", "scrap_quantity": "0", "hours": "3"})
    completed = complete_work_order(work_order.id)
    assert completed.status == "completed"
    assert count_transactions(source_type="mfg_material_issue", source_id=issue.id) == 1
    assert count_transactions(source_type="mfg_completion", source_id=completed.id) == 1

def test_work_order_rejects_issue_over_bom_quantity_and_double_completion():
    response = issue_material("wo-1", [{"material_id": "component-1", "quantity": "11"}])
    assert response.status_code == 400
    assert complete_work_order("completed-wo").status_code == 400
```

- [ ] **Step 2: Run the tests to verify RED**

Run: `cd backend && pytest tests/test_work_order_phase2.py -q`  
Expected: FAIL because production document services and inventory source extensions do not exist.

- [ ] **Step 3: Implement the work-order state machine and source snapshots**

Implement `draft → released → in_progress → completed` and cancellation from `released`/`in_progress`. Snapshot the approved BOM and plan quantity at creation. Track planned, issued, returned, reported-good, reported-scrap and completed quantities; reject quantity overflow and operations outside the allowed status. Use `post_stock_transaction` for every issue, return and completion and add audit logs.

- [ ] **Step 4: Implement report and completion actions**

Require `good_quantity + scrap_quantity` to be positive and no greater than the work-order quantity. Completion requires released/in-progress status, creates an in-flow transaction for the finished material and emits `work_order.completed` exactly once. Return the existing completion result when the action is retried.

- [ ] **Step 5: Run production flow and existing inventory tests**

Run: `cd backend && pytest tests/test_work_order_phase2.py tests/test_inventory_ledger.py -q`  
Expected: all phase-2 production tests and all一期库存回归 tests pass.

---

