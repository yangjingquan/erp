# Task 4 Report — 委外订单、委外发料和收货应付来源

## Status

Completed in `/Users/yangjingquan/Documents/ERP`. No Git operation, initialization, commit, or push was performed, per instruction.

## Delivered behavior

- Added subcontract order and receipt persistence with `draft → released → partially_received/completed` lifecycle and a terminal `cancelled` state before receipt.
- Added protected production API routes for creating, releasing, cancelling, issuing subcontract material, and receiving subcontract goods.
- Reused `post_stock_transaction` and `get_stock_unit_cost`; no duplicate inventory implementation was introduced.
- Reused finance payables by adding the idempotent `create_payable_from_subcontract_receipt` source adapter; payables preserve `source_type="subcontract_receipt"` and receipt ID.
- Preserved source tracing: subcontract orders, material issues, receipts, ledger transactions, and payables retain `source_type`/`source_id` relationships.
- Validated production permission and same-organization supplier, product material, issue material, warehouse, and source references.
- Added repeatable MySQL bootstrap tables, guarded Task 4 column upgrades, nullable legacy `mfg_material_issue.work_order_id` migration, and default number rules.

## Changed files

- `backend/app/models/production.py`
- `backend/app/models/inventory.py`
- `backend/app/models/__init__.py`
- `backend/app/schemas/production.py`
- `backend/app/api/production.py`
- `backend/app/services/production_service.py`
- `backend/app/services/finance_service.py`
- `backend/app/services/inventory_service.py`
- `backend/app/services/startup_check.py`
- `backend/tests/test_subcontract_phase2.py`
- `database/init.sql`

## TDD evidence

### RED

1. Initial command run from `backend/` used the instructed interpreter path incorrectly:

   ```text
   backend/.venv/bin/python -m pytest tests/test_subcontract_phase2.py -q
   zsh:1: no such file or directory: backend/.venv/bin/python
   ```

   The interpreter path is workspace-root relative, so the test command was rerun from the workspace root.

2. The new lifecycle, permission/org, and bootstrap tests were written before subcontract production code:

   ```text
   backend/.venv/bin/python -m pytest backend/tests/test_subcontract_phase2.py -q
   3 failed, 1 warning in 0.44s
   ```

   Expected failures were missing `/api/production/subcontract-orders` routes (404) and absent subcontract SQL tables/procedure.

3. The cancellation test was added before the cancellation route/service:

   ```text
   backend/.venv/bin/python -m pytest backend/tests/test_subcontract_phase2.py::test_subcontract_order_can_be_cancelled_before_receipt -q
   1 failed, 1 warning in 0.26s
   ```

   It failed because `/cancel` did not exist (404) and a post-cancellation issue was still accepted.

### GREEN

1. After the initial implementation:

   ```text
   backend/.venv/bin/python -m pytest backend/tests/test_subcontract_phase2.py -q
   3 passed, 1 warning in 0.44s
   ```

2. After the test-first cancellation implementation:

   ```text
   backend/.venv/bin/python -m pytest backend/tests/test_subcontract_phase2.py -q
   4 passed, 1 warning in 0.62s
   ```

The permission test was corrected to assert the project’s existing unified error payload (`{"code": 403}`) rather than HTTP status, matching existing production permission tests. This was test assertion alignment, not a production behavior change.

## Verification commands and results

```text
backend/.venv/bin/python -m pytest backend/tests/test_subcontract_phase2.py backend/tests/test_finance_flow.py backend/tests/test_inventory_ledger.py backend/tests/test_work_order_phase2.py backend/tests/test_production_planning_phase2.py -q
32 passed, 1 warning in 5.47s
```

```text
backend/.venv/bin/python -m pytest backend/tests -q
79 passed, 1 warning in 11.81s
```

```text
backend/.venv/bin/python -m compileall -q backend/app backend/tests
exit code 0; no output
```

All pytest runs emitted the pre-existing Starlette TestClient deprecation warning for `httpx`; no test failures or errors remained.

## Self-review

- The subcontract issue uses the established `MfgMaterialIssue` and `MfgMaterialIssueItem` records, with `subcontract_order_id` and source references, rather than duplicating material-movement data structures.
- Stock movements are posted only through the existing inventory ledger service and use distinct `subcontract_material_issue` and `subcontract_receipt` source types.
- Receipt payables are idempotent by receipt source and use only the subcontract processing-fee allocation; inventory receipt unit cost is not treated as an extra payable amount.
- Partial receipts prorate processing fees; the final receipt receives the residual to avoid rounding drift.
- Releasing, issuing the same subcontract order, receiving the same quantity/unit-cost payload, generating a payable, and cancelling an already-cancelled eligible order are idempotent.
- New write routes use the established `production:manage` dependency and responses use `ok(...)`, preserving the unified response envelope.
- No FIFO, CRM, quality, HR, frontend, or cost functionality was added.

## Concerns

- Cancellation is deliberately allowed only before any receipt (`draft` or `released`). Cancelling a partially received order would require explicit inventory/payable reversal documents and is outside Task 4’s minimal no-cost scope.
- Receipt idempotency is determined by order plus identical `good_quantity` and `unit_cost`, because the supplied interface contains no explicit idempotency key. A future API that needs two genuinely identical partial receipts should add a client operation key.
- The repeatable MySQL bootstrap includes `ALTER TABLE mfg_material_issue MODIFY COLUMN work_order_id ... NULL`; it is safe to re-run on MySQL but should be applied during a normal migration window for production lock management.

---

## Review-fix addendum — concurrency and receipt idempotency

### Review findings resolved

1. `issue_subcontract_material` now obtains the subcontract order row lock before looking up an existing issue. `mfg_material_issue.subcontract_order_id` is protected by `uk_mfg_material_issue_subcontract_order`; a duplicate-key race is recovered by re-querying and returning the existing issue before any second outbound ledger posting.
2. `receive_subcontract_order` now locks the order before lookup and identifies retries by `operation_key`, not quantity or unit cost. The operation-key lookup precedes the status transition check, so a retry remains successful after the order has reached `completed`.
3. `SubcontractReceiptCreate` now requires a nonblank `operation_key` (1–64 characters); `mfg_subcontract_receipt` stores it and has `uk_mfg_subcontract_receipt_operation` on `(org_id, subcontract_order_id, operation_key)`. Equal partial deliveries with different keys create separate receipts; same-key retries return the original receipt.
4. `PurchasePayable` now declares the already-established source uniqueness in the ORM test schema as well as MySQL. `create_payable_from_subcontract_receipt` wraps its insert in a savepoint and recovers the original payable after an `IntegrityError`.
5. MySQL bootstrap now creates the new constraints for fresh installs and safely upgrades existing installations: it backfills receipt operation keys from receipt IDs before making the key non-null and adding its unique index. The existing Task 3 schema assertion was updated because Task 4 intentionally changes `mfg_material_issue.work_order_id` to nullable.

### Additional changed files

- `backend/app/models/finance.py`
- `backend/tests/test_work_order_phase2.py`

### TDD RED/GREEN evidence for the review fixes

```text
backend/.venv/bin/python -m pytest backend/tests/test_subcontract_phase2.py -q
4 failed, 3 passed, 1 warning in 1.29s
```

The failures demonstrated the former payload-based receipt de-duplication, acceptance of an empty operation key, absent issue uniqueness, and absent bootstrap constraints.

```text
backend/.venv/bin/python -m pytest backend/tests/test_subcontract_phase2.py::test_subcontract_payable_recovers_from_a_stale_duplicate_lookup -q
1 failed, 1 warning in 0.39s
```

The deterministic stale-lookup simulation reached SQLite's source-unique `IntegrityError` before recovery was added to the subcontract payable adapter. A first attempt placed recovery in the purchase-receipt adapter; the stack trace identified the placement error, which was then corrected without changing purchase behavior.

```text
backend/.venv/bin/python -m pytest backend/tests/test_subcontract_phase2.py -q
8 passed, 1 warning in 1.45s
```

### Review-fix verification commands and results

```text
backend/.venv/bin/python -m pytest backend/tests/test_subcontract_phase2.py backend/tests/test_finance_flow.py backend/tests/test_inventory_ledger.py backend/tests/test_work_order_phase2.py backend/tests/test_production_planning_phase2.py -q
36 passed, 1 warning in 6.58s
```

```text
backend/.venv/bin/python -m pytest backend/tests -q
83 passed, 1 warning in 13.21s
```

```text
backend/.venv/bin/python -m compileall -q backend/app backend/tests
exit code 0; no output
```

### New regression coverage

- Equal partial receipts with distinct operation keys, same-key retry after completion, and final fee residual allocation (`50.01 + 50.00 = 100.01`).
- Nonblank operation-key validation and foreign-order rejection without inventory side effects.
- A deterministic SQLite stale-duplicate issue insertion proving the subcontract issue unique invariant, followed by an idempotent retry with only one outbound ledger row.
- A deterministic stale payable lookup that forces a unique-key collision and proves the subcontract payable adapter re-queries and returns the original source payable.

### Remaining operational note

The test suite uses SQLite and cannot validate MySQL's true concurrent row-lock scheduling. The protection is defense-in-depth: lock-first service ordering plus MySQL/ORM unique constraints and `IntegrityError` re-query recovery. The deterministic stale-read tests exercise the resulting uniqueness/recovery paths without requiring live MySQL.
