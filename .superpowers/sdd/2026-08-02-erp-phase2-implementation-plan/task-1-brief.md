### Task 1: 二期基础设施、模型注册和可重复数据库初始化

**Files:**
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/startup_check.py`
- Modify: `database/init.sql`
- Create: `backend/app/models/platform.py`
- Create: `backend/app/services/event_service.py`
- Create: `backend/app/services/phase2_parameter_service.py`
- Create: `backend/tests/test_phase2_foundation.py`

**Interfaces:**
- `emit_event(db: Session, event_type: str, aggregate_type: str, aggregate_id: str, payload: dict) -> ExtEventOutbox`
- `claim_pending_events(db: Session, limit: int = 50) -> list[ExtEventOutbox]`
- `get_phase2_parameter(db: Session, org_id: str, key: str, default: str) -> str`
- `check_schema(db: Session)` must include at least `mfg_bom`, `mfg_work_order`, `inv_location`, `inv_cost_layer`, `cost_period_close`, `crm_lead`, `qa_inspection`, `hr_employee`, and `ext_event_outbox` in the required table set.

- [ ] **Step 1: Write the failing foundation tests**

```python
def test_phase2_tables_are_required_by_schema_contract():
    status = schema_status_from_tables({"sys_user", "sales_order"})
    assert "mfg_bom" in status.missing_tables
    assert "crm_lead" in status.missing_tables

def test_emit_event_is_idempotent_for_same_aggregate_and_type(client_and_session):
    _, session = client_and_session
    first = emit_event(session, "work_order.completed", "mfg_work_order", "wo-1", {"quantity": "2"})
    second = emit_event(session, "work_order.completed", "mfg_work_order", "wo-1", {"quantity": "2"})
    assert first.id == second.id
    assert session.query(ExtEventOutbox).count() == 1
```

- [ ] **Step 2: Run the tests and verify the expected failure**

Run: `cd backend && pytest tests/test_phase2_foundation.py -q`  
Expected: FAIL because the phase-2 model, event service, and schema table requirements do not exist.

- [ ] **Step 3: Implement the minimum foundation**

Register every phase-2 model module before tests call `Base.metadata.create_all`; add an `ExtEventOutbox` model with a unique constraint on `(event_type, aggregate_type, aggregate_id)`. Implement `emit_event` using an existing row lookup followed by insert, `claim_pending_events` using `pending` status and retry timestamp, and parameter lookup with the documented default. Extend `database/init.sql` with the event table, phase-2 module seeds, menu rows, number rules and parameter rows using `CREATE TABLE IF NOT EXISTS` and `ON DUPLICATE KEY UPDATE`.

- [ ] **Step 4: Run the targeted tests and schema compilation**

Run: `cd backend && pytest tests/test_phase2_foundation.py -q && python -m compileall -q app`  
Expected: all foundation tests pass and compilation exits 0.

- [ ] **Step 5: Verify SQL contract without claiming MySQL success**

Run: `rg -n "CREATE TABLE IF NOT EXISTS (mfg_|inv_(zone|location|batch|cost_layer)|cost_|crm_|qa_|hr_|ext_event_outbox)" database/init.sql`  
Expected: every planned phase-2 table appears. If Docker/MySQL is unavailable, record that as an environment limitation for the final report.

---

