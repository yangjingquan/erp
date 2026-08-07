### Task 4: 委外订单、委外发料和收货应付来源

**Files:**
- Modify: `backend/app/models/production.py`
- Modify: `backend/app/schemas/production.py`
- Modify: `backend/app/services/production_service.py`
- Modify: `backend/app/api/production.py`
- Create: `backend/tests/test_subcontract_phase2.py`
- Modify: `backend/app/services/finance_service.py`

**Interfaces:**
- `create_subcontract_order(db, payload, context) -> MfgSubcontractOrder`
- `release_subcontract_order(db, order_id, context) -> MfgSubcontractOrder`
- `issue_subcontract_material(db, order_id, items, context) -> MfgMaterialIssue`
- `receive_subcontract_order(db, order_id, payload, context) -> MfgSubcontractReceipt`

- [ ] **Step 1: Write failing委外闭环测试**

```python
def test_subcontract_issue_then_receive_creates_inventory_and_payable_source():
    order = create_subcontract_order(quantity="10", processing_fee="120")
    release_subcontract_order(order.id)
    issue_subcontract_material(order.id, [{"material_id": "raw-1", "quantity": "10"}])
    receipt = receive_subcontract_order(order.id, {"good_quantity": "10", "unit_cost": "12"})
    assert receipt.status == "completed"
    assert count_transactions(source_type="subcontract_receipt", source_id=receipt.id) == 1
    assert find_payable(source_type="subcontract_receipt", source_id=receipt.id).amount == Decimal("120")
```

- [ ] **Step 2: Run the test and verify RED**

Run: `cd backend && pytest tests/test_subcontract_phase2.py -q`  
Expected: FAIL because subcontract models and transitions do not exist.

- [ ] **Step 3: Implement委外 state, material issue, receipt, and payable source**

Use `draft → released → partially_received/completed → cancelled`; validate supplier, material, quantity and processing fee. Repeated release, issue, receipt and payable generation return the existing result. Link issue/receipt/finance rows with `source_type` and `source_id`.

- [ ] **Step 4: Run targeted regression**

Run: `cd backend && pytest tests/test_subcontract_phase2.py tests/test_finance_flow.py -q`  
Expected:委外测试和一期财务测试通过。

---

