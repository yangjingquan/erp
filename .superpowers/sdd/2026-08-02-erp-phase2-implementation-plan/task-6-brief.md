### Task 6: 移动 H5 扫码和盘点增强

**Files:**
- Modify: `backend/app/models/inventory_advanced.py`
- Modify: `backend/app/schemas/inventory_advanced.py`
- Modify: `backend/app/services/inventory_advanced_service.py`
- Modify: `backend/app/api/inventory_advanced.py`
- Create: `backend/tests/test_scan_phase2.py`
- Create: `frontend/src/api/inventory-advanced.ts`
- Create: `frontend/src/views/inventory-advanced/Scan.vue`
- Create: `frontend/tests/phase2-scan-page.test.ts`

**Interfaces:**
- `create_scan_token(db, context) -> str`
- `process_scan(db, token, scan_id, action, document_id, payload) -> dict`
- `list_scan_tasks(db, context) -> list[dict]`

- [ ] **Step 1: Write failing idempotent scan tests and page contract**

```python
def test_same_scan_id_returns_same_result_without_duplicate_transaction():
    token = create_scan_token(admin_context)
    first = process_scan(token, "scan-1", "receive", "receipt-1", {"quantity": "2"})
    second = process_scan(token, "scan-1", "receive", "receipt-1", {"quantity": "2"})
    assert first == second
    assert transaction_count(source_type="scan", source_id="scan-1") == 1
```

Frontend test reads `Scan.vue` and asserts it contains `createScanToken`, `processScan`, `scan_id`, and an error message path.

- [ ] **Step 2: Run tests to verify RED**

Run: `cd backend && pytest tests/test_scan_phase2.py -q`; then `cd ../frontend && npm test -- phase2-scan-page.test.ts`  
Expected: both fail because scan API/client/page do not exist.

- [ ] **Step 3: Implement short-lived scan token and action validation**

Bind token to user, organization, warehouse scope and expiration from `scan.token.ttl` parameter. Validate `scan_id` uniqueness, action-specific document status, batch/location and quantity, then call the same inventory service used by desktop APIs. Store and return the original result for retries; reject expired token, wrong warehouse and duplicate document completion.

- [ ] **Step 4: Implement responsive scan page and API client**

Add API functions for token creation, task listing and processing; add a mobile-friendly page with action select, document ID, batch/location, quantity, `scan_id`, loading state and `ElMessage.error`. Do not add a native app dependency.

- [ ] **Step 5: Run targeted tests and frontend typecheck**

Run: `cd backend && pytest tests/test_scan_phase2.py -q && cd ../frontend && npm test -- phase2-scan-page.test.ts && npm run typecheck`  
Expected: all pass.

---

