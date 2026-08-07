# SDD ledger — plan: docs/superpowers/plans/2026-08-02-erp-phase2-implementation-plan.md

Execution mode: subagent-driven development in the current workspace. Git worktree, commit, and diff-package steps are unavailable because this workspace has no writable Git metadata; task review uses file snapshots and test evidence instead.

## Pre-flight

- Plan conflict scan: clean.
- Current backend baseline: unavailable until Python dependencies are installed (`ModuleNotFoundError: fastapi`).
- Current frontend baseline: 34 tests passing.

## Task status

- Task 1: complete — foundation, repeatable SQL seeds, audit fields, idempotent event writes, and concurrent event claims reviewed and approved. Live MySQL locking remains unverified because Docker access is denied.
- Task 2: complete — BOM/MPS/MRP behavior, repeatable BOM schema upgrade, production permissions, organization-reference validation, and coverage reviewed and approved.
- Task 3: complete — work-order lifecycle, ledger-backed issue/return/completion, service-level report validation, source validation, and repeatable SQL schema reviewed and approved.
- Task 4: complete — subcontract lifecycle, ledger/payable source linkage, explicit receipt operation keys, database uniqueness, and concurrency recovery reviewed and approved.
- Task 5: complete — locations, batches, FIFO layers, slow-moving snapshots, shared warehouse scope, soft-delete conflicts, and deterministic rule selection reviewed and approved.
- Task 6: complete — scanner token, durable scan idempotency, receive/fill/return/count actions, scoped task list, validated API payloads and responsive H5 page. Focused scanner tests pass.
- Task 7: implementation complete — Decimal cost allocations, project entries, period close/reopen guards, APIs and tests.
- Task 8: implementation complete — CRM leads, conversion idempotency, opportunities, follow-ups, APIs, pages and tests.
- Task 9: implementation complete — inspection plans, lifecycle, nonconformity and disposition handling, APIs, page and tests.
- Task 10: implementation complete — employees, attendance, Decimal payroll workflow, APIs, pages and tests.
- Task 11: implementation complete — API clients/scopes, outbox query endpoint, phase-2 dashboard metadata and frontend client/dashboard assets.
- Task 12: implementation complete — phase-2 routes, permissions metadata, shared API modules/views and full integration validation.
