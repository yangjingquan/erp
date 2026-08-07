# Task 1 Report: Phase-2 foundation, model registration, and repeatable initialization

## Scope delivered

Implemented the Task 1 foundation only:

- Registered the phase-2 platform model during application startup so SQLite test fixtures include it before `Base.metadata.create_all`.
- Added the `ExtEventOutbox` model and its `(event_type, aggregate_type, aggregate_id)` uniqueness contract.
- Added idempotent event emission, due pending-event claiming, and organization-scoped phase-2 parameter lookup with a caller-supplied default.
- Extended startup schema validation with the phase-2 production, inventory/cost, CRM, quality, HR, and outbox table contract.
- Extended `database/init.sql` with inert phase-2 table foundations, outbox uniqueness, repeatable menu/module/number-rule/parameter seeds.

No later-domain workflows, API routes, or business rules were added.

## Changed files

- `backend/app/models/__init__.py` — imports `ExtEventOutbox` to register the platform model.
- `backend/app/models/platform.py` — new outbox model and uniqueness constraint.
- `backend/app/main.py` — imports the model package before application startup.
- `backend/app/services/event_service.py` — new idempotent emit and pending-event claim service.
- `backend/app/services/phase2_parameter_service.py` — new parameter lookup with default fallback.
- `backend/app/services/startup_check.py` — adds the phase-2 required-table schema contract.
- `backend/tests/test_phase2_foundation.py` — new integration-style SQLite foundation tests.
- `database/init.sql` — phase-2 table names, outbox uniqueness, and repeatable phase-2 seed data.

## TDD evidence

### RED

Required command, run from `backend` before implementation:

```text
$ pytest tests/test_phase2_foundation.py -q
ImportError while loading conftest ...
E   ModuleNotFoundError: No module named 'fastapi'
```

The bare shell interpreter is not the project environment, so it cannot load the pre-existing FastAPI fixture. The project virtual environment then demonstrated the intended feature-level RED state before production code existed:

```text
$ ./.venv/bin/python -m pytest tests/test_phase2_foundation.py -q
ERROR collecting tests/test_phase2_foundation.py
E   ModuleNotFoundError: No module named 'app.models.platform'
1 error in 0.08s
```

The failing tests target these production breaks: absent phase-2 schema requirements, a missing outbox model/service, duplicate aggregate-event rows, claiming deferred events, and absent parameter defaulting.

### GREEN

```text
$ ./.venv/bin/python -m pytest tests/test_phase2_foundation.py -q && ./.venv/bin/python -m compileall -q app
....                                                                     [100%]
4 passed, 1 warning in 0.60s
```

`compileall` produced no output and exited 0. The sole warning is pre-existing FastAPI/TestClient deprecation output from the installed dependency stack.

Additional compatibility verification:

```text
$ ./.venv/bin/python -m pytest -q
........................................................                 [100%]
56 passed, 1 warning in 8.42s
```

## SQL contract verification

```text
$ rg -n "CREATE TABLE IF NOT EXISTS (mfg_|inv_(zone|location|batch|cost_layer)|cost_|crm_|qa_|hr_|ext_event_outbox)" database/init.sql
915:CREATE TABLE IF NOT EXISTS ext_event_outbox (
929:CREATE TABLE IF NOT EXISTS mfg_bom (
938:CREATE TABLE IF NOT EXISTS mfg_bom_item (
947:CREATE TABLE IF NOT EXISTS mfg_routing (
955:CREATE TABLE IF NOT EXISTS mfg_routing_operation (
963:CREATE TABLE IF NOT EXISTS mfg_work_order (
973:CREATE TABLE IF NOT EXISTS mfg_work_order_material (
982:CREATE TABLE IF NOT EXISTS mfg_work_report (
990:CREATE TABLE IF NOT EXISTS inv_zone (
999:CREATE TABLE IF NOT EXISTS inv_location (
1009:CREATE TABLE IF NOT EXISTS inv_batch (
1019:CREATE TABLE IF NOT EXISTS inv_cost_layer (
1031:CREATE TABLE IF NOT EXISTS cost_period_close (
1040:CREATE TABLE IF NOT EXISTS cost_allocation_rule (
1049:CREATE TABLE IF NOT EXISTS crm_lead (
1059:CREATE TABLE IF NOT EXISTS crm_opportunity (
1069:CREATE TABLE IF NOT EXISTS crm_contact (
1078:CREATE TABLE IF NOT EXISTS crm_activity (
1088:CREATE TABLE IF NOT EXISTS qa_inspection (
1099:CREATE TABLE IF NOT EXISTS qa_inspection_item (
1107:CREATE TABLE IF NOT EXISTS qa_nonconformance (
1116:CREATE TABLE IF NOT EXISTS hr_employee (
1126:CREATE TABLE IF NOT EXISTS hr_attendance (
1135:CREATE TABLE IF NOT EXISTS hr_leave_request (
1146:CREATE TABLE IF NOT EXISTS hr_payroll_run (
```

## Self-review

- The SQLAlchemy and MySQL outbox definitions both enforce the same aggregate-event uniqueness invariant.
- `emit_event` first looks up an existing row and flushes only a newly created one, so repeated calls in one transaction return the original event.
- `claim_pending_events` selects only `pending` rows whose retry time is absent or due, transitions selected rows to `processing`, and flushes so a subsequent claim will not return them.
- Parameter lookup is constrained by both organization and key, returning the documented caller default for a missing row or null stored value.
- The phase-2 SQL tables are foundation schemas only; no later production, inventory, cost, CRM, quality, or HR behavior was introduced.
- Existing test fixtures remain SQLite-compatible; the complete backend test suite passes in the committed project virtual environment.

## Concerns and environment limitations

- MySQL/Docker initialization was not executed. `docker version --format '{{.Server.Version}}'` could not access the local Docker socket: `permission denied while trying to connect to the docker API at unix:///Users/yangjingquan/.docker/run/docker.sock`. The SQL name contract was verified statically, but MySQL execution remains an environment-limited follow-up.
- The shell's bare `pytest` lacks FastAPI because its virtual environment is not activated. All verification used `backend/.venv/bin/python -m pytest`, which contains the project dependencies.
- No commit was created because this workspace has no usable Git metadata (`fatal: not a git repository`).

## Review-fix addendum

### Findings addressed

- Added `is_deleted`, `created_at`, `updated_at`, and integer `version` columns to every mutable table introduced for the phase-2 foundation: the outbox plus production, inventory/cost, CRM, quality, and HR tables. `mfg_bom` now uses `bom_version` for its business revision so `version` can consistently carry the audit version.
- Updated `ExtEventOutbox` to inherit the established `AuditMixin`, preserving SQLite fixture compatibility and aligning its owned ORM fields with the SQL audit convention. It also owns the new nullable `claim_token` field.
- Made `emit_event` concurrency-idempotent: after the initial lookup, insertion happens inside a SQLAlchemy savepoint. A duplicate-key `IntegrityError` rolls back only that savepoint, re-queries the unique aggregate-event row, and returns it.
- Made `claim_pending_events` an atomic conditional claim compatible with SQLite and MySQL. It selects candidates, then updates only rows that are still due, pending, and not deleted while assigning a fresh claim token. It returns only rows bearing that token, so a competing worker whose conditional update loses the race returns no shared rows. This avoids relying on MySQL-only `SKIP LOCKED` while retaining atomic database update semantics.

### Changed files for this fix

- `backend/app/models/platform.py`
- `backend/app/services/event_service.py`
- `backend/tests/test_phase2_foundation.py`
- `database/init.sql`
- `.superpowers/sdd/2026-08-02-erp-phase2-implementation-plan/task-1-report.md`

### TDD RED evidence

```text
$ ./.venv/bin/python -m pytest tests/test_phase2_foundation.py -q
..FFFF.                                                                  [100%]
FAILED test_emit_event_recovers_from_a_stale_lookup_duplicate
  sqlalchemy.exc.IntegrityError: UNIQUE constraint failed: ext_event_outbox.event_type, ext_event_outbox.aggregate_type, ext_event_outbox.aggregate_id
FAILED test_claim_pending_events_returns_only_due_pending_events
  AttributeError: 'ExtEventOutbox' object has no attribute 'claim_token'
FAILED test_outbox_uses_the_established_audit_and_soft_delete_fields
  AttributeError: 'ExtEventOutbox' object has no attribute 'is_deleted'
FAILED test_phase2_sql_tables_include_audit_and_soft_delete_columns
  AssertionError: ext_event_outbox
4 failed, 3 passed, 1 warning in 1.10s
```

The stale-lookup test deliberately bypasses only the first lookup because the shared SQLite in-memory fixture cannot produce two independent concurrent transactions reliably; the duplicate insert and its unique-constraint error are real database operations.

### GREEN verification

```text
$ ./.venv/bin/python -m pytest tests/test_phase2_foundation.py -q
.......                                                                  [100%]
7 passed, 1 warning in 0.97s

$ ./.venv/bin/python -m compileall -q app
exit 0 (no output)
```

The existing FastAPI/TestClient dependency deprecation warning remains unchanged. A full compatibility run performed before this final SQL punctuation correction also passed: `59 passed, 1 warning in 8.78s`.

### Remaining concerns

- MySQL/Docker remains unavailable in this workspace (Docker socket permission was denied in the earlier verification), so the MySQL execution and real multi-connection concurrency behavior are not run here. The claim implementation deliberately uses a conditional `UPDATE` plus token rather than MySQL-only row locking, and is covered by SQLite-compatible tests.
- `CREATE TABLE IF NOT EXISTS` is repeatable for a fresh initialization, but it does not alter an already-created legacy `ext_event_outbox` table. An existing deployment created before this task needs a schema migration for its new audit and `claim_token` columns; this task was constrained to `database/init.sql` and does not add a migration system.

## Review-fix round 2

### Finding addressed

The duplicate-key recovery query in `emit_event` is now a locking/current read:

```python
select(ExtEventOutbox).where(...).with_for_update()
```

It runs only after the nested savepoint has rolled back a duplicate-key `IntegrityError`. In MySQL InnoDB, this avoids reusing a `REPEATABLE READ` consistent-read snapshot and observes the committed winning row before returning it. SQLite remains compatible because SQLAlchemy's SQLite dialect accepts the statement and omits unsupported row-lock syntax.

### Regression test and RED evidence

The existing stale-lookup duplicate test now asserts that the recovery query requests a lock. It still uses a real SQLite uniqueness violation; only the initial lookup is made stale because the shared in-memory fixture cannot provide independent InnoDB-style snapshots.

```text
$ ./.venv/bin/python -m pytest tests/test_phase2_foundation.py -q
..F....                                                                  [100%]
FAILED test_emit_event_recovers_from_a_stale_lookup_duplicate
  assert None is not None
  where None = <Select>._for_update_arg
1 failed, 6 passed, 1 warning in 1.10s
```

### GREEN verification

```text
$ ./.venv/bin/python -m pytest tests/test_phase2_foundation.py -q
.......                                                                  [100%]
7 passed, 1 warning in 0.97s

$ ./.venv/bin/python -m compileall -q app
exit 0 (no output)
```

### Changed files

- `backend/app/services/event_service.py`
- `backend/tests/test_phase2_foundation.py`
- `.superpowers/sdd/2026-08-02-erp-phase2-implementation-plan/task-1-report.md`

### Remaining concern

MySQL/Docker is unavailable in this workspace, so the InnoDB `REPEATABLE READ` behavior is protected by the locking-read contract test but has not been exercised against a live MySQL server.
