# Task 4 fix review snapshot
## Report
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
## Models
    required_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    issued_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    returned_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    line_no: Mapped[int] = mapped_column(nullable=False, default=1)
    work_order: Mapped[MfgWorkOrder] = relationship(back_populates="materials")


class MfgSubcontractOrder(AuditMixin, UUIDModel):
    __tablename__ = "mfg_subcontract_order"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    supplier_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    processing_fee: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    issues: Mapped[list["MfgMaterialIssue"]] = relationship(back_populates="subcontract_order")
    receipts: Mapped[list["MfgSubcontractReceipt"]] = relationship(
        back_populates="subcontract_order", order_by="MfgSubcontractReceipt.created_at"
    )


class MfgMaterialIssue(AuditMixin, UUIDModel):
    __tablename__ = "mfg_material_issue"
    __table_args__ = (UniqueConstraint("subcontract_order_id", name="uk_mfg_material_issue_subcontract_order"),)

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    work_order_id: Mapped[str | None] = mapped_column(ForeignKey("mfg_work_order.id"), nullable=True)
    subcontract_order_id: Mapped[str | None] = mapped_column(ForeignKey("mfg_subcontract_order.id"), nullable=True)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    work_order: Mapped[MfgWorkOrder | None] = relationship(back_populates="issues")
    subcontract_order: Mapped[MfgSubcontractOrder | None] = relationship(back_populates="issues")
    items: Mapped[list["MfgMaterialIssueItem"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan", order_by="MfgMaterialIssueItem.line_no"
    )


class MfgMaterialIssueItem(AuditMixin, UUIDModel):
    __tablename__ = "mfg_material_issue_item"

    issue_id: Mapped[str] = mapped_column(ForeignKey("mfg_material_issue.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    returned_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=0, nullable=False)
    line_no: Mapped[int] = mapped_column(nullable=False, default=1)
    issue: Mapped[MfgMaterialIssue] = relationship(back_populates="items")


class MfgSubcontractReceipt(AuditMixin, UUIDModel):
    __tablename__ = "mfg_subcontract_receipt"
    __table_args__ = (
        UniqueConstraint("org_id", "subcontract_order_id", "operation_key", name="uk_mfg_subcontract_receipt_operation"),
    )

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    doc_no: Mapped[str] = mapped_column(String(64), nullable=False)
    subcontract_order_id: Mapped[str] = mapped_column(ForeignKey("mfg_subcontract_order.id"), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    good_quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    processing_fee_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    operation_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    subcontract_order: Mapped[MfgSubcontractOrder] = relationship(back_populates="receipts")


class MfgMaterialReturn(AuditMixin, UUIDModel):
    __tablename__ = "mfg_material_return"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    work_order_id: Mapped[str] = mapped_column(ForeignKey("mfg_work_order.id"), nullable=False)
    issue_id: Mapped[str] = mapped_column(ForeignKey("mfg_material_issue.id"), nullable=False)
    warehouse_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    items: Mapped[list["MfgMaterialReturnItem"]] = relationship(
        back_populates="material_return", cascade="all, delete-orphan", order_by="MfgMaterialReturnItem.line_no"
    )


class MfgMaterialReturnItem(AuditMixin, UUIDModel):
    __tablename__ = "mfg_material_return_item"

    return_id: Mapped[str] = mapped_column(ForeignKey("mfg_material_return.id"), nullable=False)
    material_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
## Schemas

class MaterialMovementItem(BaseModel):
    material_id: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)


class MaterialIssueCreate(BaseModel):
    items: list[MaterialMovementItem] = Field(min_length=1)


class MaterialReturnCreate(BaseModel):
    items: list[MaterialMovementItem] = Field(min_length=1)


class WorkReportCreate(BaseModel):
    good_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    scrap_quantity: Decimal = Field(default=Decimal("0"), ge=0)
    hours: Decimal = Field(default=Decimal("0"), ge=0)


class SubcontractReceiptCreate(BaseModel):
    good_quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(gt=0)
    operation_key: str = Field(min_length=1, max_length=64)
## Production service
    material_ids = [item.material_id for item in items]
    if len(material_ids) != len(set(material_ids)):
        raise AppError("物料明细不能重复", code=400)


def _require_supplier(db: Session, supplier_id: str, context: UserContext) -> None:
    supplier = db.scalar(
        select(MdSupplier).where(
            MdSupplier.id == supplier_id,
            MdSupplier.org_id == context.org_id,
            MdSupplier.is_deleted.is_(False),
        )
    )
    if supplier is None:
        raise AppError("供应商不存在或不属于当前组织", code=404)


def _find_subcontract_issue(db: Session, order_id: str, context: UserContext) -> MfgMaterialIssue | None:
    return db.scalar(
        select(MfgMaterialIssue)
        .options(selectinload(MfgMaterialIssue.items))
        .where(
            MfgMaterialIssue.subcontract_order_id == order_id,
            MfgMaterialIssue.org_id == context.org_id,
            MfgMaterialIssue.is_deleted.is_(False),
        )
    )


def _find_subcontract_receipt(
    db: Session, order_id: str, operation_key: str, context: UserContext
) -> MfgSubcontractReceipt | None:
    return db.scalar(
        select(MfgSubcontractReceipt).where(
            MfgSubcontractReceipt.subcontract_order_id == order_id,
            MfgSubcontractReceipt.org_id == context.org_id,
            MfgSubcontractReceipt.operation_key == operation_key,
            MfgSubcontractReceipt.is_deleted.is_(False),
        )
    )


def create_work_order(db: Session, payload, context: UserContext) -> MfgWorkOrder:
    _require_material(db, payload.material_id, context)
    _require_warehouse(db, payload.warehouse_id, context)
    _validate_source(payload, db, context)
    bom = _approved_bom_for_material(db, context.org_id, payload.material_id, payload.plan_date)
    if bom is None:
        raise AppError("成品缺少有效的已审核 BOM 版本", code=400)
    quantity = _quantity(payload.quantity)
    snapshot_items = [
        {"material_id": item.material_id, "quantity": _snapshot_quantity(item.quantity)}
        for item in bom.items
        if not item.is_deleted
    ]
    row = MfgWorkOrder(
        org_id=context.org_id,
        doc_no=next_doc_no(db, "mfg_work_order", context.org_id, payload.plan_date),
        material_id=payload.material_id,
        warehouse_id=payload.warehouse_id,
        bom_id=bom.id,
        plan_date=payload.plan_date,
        quantity=quantity,
        status="draft",
        bom_snapshot={
            "bom_id": bom.id,
            "bom_version": bom.bom_version,
            "plan_quantity": _snapshot_quantity(quantity),
            "items": snapshot_items,
        },
        source_type=payload.source_type,
        source_id=payload.source_id,
        created_by=context.id,
        updated_by=context.id,
    )
    row.materials = [
        MfgWorkOrderMaterial(
            material_id=item.material_id,
            required_quantity=_quantity(quantity * _quantity(item.quantity)),
            line_no=index,
        )
        for index, item in enumerate(bom.items, start=1)
        if not item.is_deleted
    ]
    db.add(row)
    db.flush()
    write_operation_log(db, user=context.user, action="create", resource="mfg_work_order", target_id=row.id)
    return row


def create_subcontract_order(db: Session, payload, context: UserContext) -> MfgSubcontractOrder:
    _require_supplier(db, payload.supplier_id, context)
    _require_material(db, payload.material_id, context)
    _require_warehouse(db, payload.warehouse_id, context)
    _validate_source(payload, db, context)
    quantity = _quantity(payload.quantity)
    processing_fee = Decimal(payload.processing_fee).quantize(MONEY_SCALE, rounding=ROUND_HALF_UP)
    if quantity <= 0 or processing_fee <= 0:
        raise AppError("委外数量和加工费必须大于零", code=400)
    row = MfgSubcontractOrder(
        org_id=context.org_id,
        doc_no=next_doc_no(db, "mfg_subcontract_order", context.org_id, payload.plan_date),
        supplier_id=payload.supplier_id,
        material_id=payload.material_id,
        warehouse_id=payload.warehouse_id,
        plan_date=payload.plan_date,
        quantity=quantity,
        processing_fee=processing_fee,
        status="draft",
        source_type=payload.source_type,
        source_id=payload.source_id,
        created_by=context.id,
        updated_by=context.id,
    )
    db.add(row)
    db.flush()
    write_operation_log(db, user=context.user, action="create", resource="mfg_subcontract_order", target_id=row.id)
    return row


def release_subcontract_order(db: Session, order_id: str, context: UserContext) -> MfgSubcontractOrder:
    row = _get_subcontract_order(db, order_id, context, lock=True)
    if row.status in {"released", "partially_received", "completed"}:
        return row
    if row.status != "draft":
        raise AppError(f"委外订单状态 {row.status} 不允许下达", code=400)
    row.status = "released"
    row.updated_by = context.id
    write_operation_log(db, user=context.user, action="release", resource="mfg_subcontract_order", target_id=row.id)
    db.flush()
    return row


def cancel_subcontract_order(db: Session, order_id: str, context: UserContext) -> MfgSubcontractOrder:
    row = _get_subcontract_order(db, order_id, context, lock=True)
    if row.status == "cancelled":
        return row
    if row.status not in {"draft", "released"}:
        raise AppError(f"委外订单状态 {row.status} 不允许取消", code=400)
    row.status = "cancelled"
    row.updated_by = context.id
    write_operation_log(db, user=context.user, action="cancel", resource="mfg_subcontract_order", target_id=row.id)
    db.flush()
    return row


def issue_subcontract_material(db: Session, order_id: str, items, context: UserContext) -> MfgMaterialIssue:
    row = _get_subcontract_order(db, order_id, context, lock=True)
    existing = _find_subcontract_issue(db, row.id, context)
    if existing is not None:
        return existing
    if row.status not in {"released", "partially_received"}:
        raise AppError(f"委外订单状态 {row.status} 不允许发料", code=400)
    _ensure_distinct_items(items)
    quantities = {item.material_id: _quantity(item.quantity) for item in items}
    for material_id, quantity in quantities.items():
        _require_material(db, material_id, context)
        if quantity <= 0:
            raise AppError("委外发料数量必须大于零", code=400)
    issue = MfgMaterialIssue(
        org_id=context.org_id,
        subcontract_order_id=row.id,
        warehouse_id=row.warehouse_id,
        source_type="mfg_subcontract_order",
        source_id=row.id,
        created_by=context.id,
    )
    try:
        with db.begin_nested():
            db.add(issue)
            db.flush()
    except IntegrityError:
        existing = _find_subcontract_issue(db, row.id, context)
        if existing is None:
            raise
        return existing
    for index, item in enumerate(items, start=1):
        quantity = quantities[item.material_id]
        unit_cost = get_stock_unit_cost(db, context, row.warehouse_id, item.material_id)
        issue.items.append(
            MfgMaterialIssueItem(
                material_id=item.material_id,
                quantity=quantity,
                unit_cost=unit_cost,
                line_no=index,
            )
        )
        post_stock_transaction(
            db,
            context,
            source_type=SUBCONTRACT_MATERIAL_ISSUE_SOURCE,
            source_id=issue.id,
            warehouse_id=row.warehouse_id,
            material_id=item.material_id,
            quantity=quantity,
            direction="out",
            unit_cost=unit_cost,
        )
    row.updated_by = context.id
    write_operation_log(
        db, user=context.user, action="issue", resource="mfg_subcontract_order", target_id=row.id, detail={"issue_id": issue.id}
    )
    db.flush()
    return issue


def receive_subcontract_order(db: Session, order_id: str, payload, context: UserContext) -> MfgSubcontractReceipt:
    good_quantity = _quantity(payload.good_quantity)
    unit_cost = _quantity(payload.unit_cost)
    row = _get_subcontract_order(db, order_id, context, lock=True)
    existing = _find_subcontract_receipt(db, row.id, payload.operation_key, context)
    if existing is not None:
        return existing
    if row.status not in {"released", "partially_received"}:
        raise AppError(f"委外订单状态 {row.status} 不允许收货", code=400)
    if good_quantity <= 0 or unit_cost <= 0:
        raise AppError("委外收货数量和单价必须大于零", code=400)
    if _quantity(row.received_quantity + good_quantity) > _quantity(row.quantity):
        raise AppError("委外收货数量超过订单数量", code=400)
    allocated_fee = (Decimal(row.processing_fee) * good_quantity / Decimal(row.quantity)).quantize(
        MONEY_SCALE, rounding=ROUND_HALF_UP
    )
    if _quantity(row.received_quantity + good_quantity) == _quantity(row.quantity):
        allocated_fee = Decimal(row.processing_fee) - sum(
            db.scalars(
                select(MfgSubcontractReceipt.processing_fee_amount).where(
                    MfgSubcontractReceipt.subcontract_order_id == row.id,
                    MfgSubcontractReceipt.org_id == context.org_id,
                    MfgSubcontractReceipt.is_deleted.is_(False),
                )
            )
        )
    receipt = MfgSubcontractReceipt(
        org_id=context.org_id,
        doc_no=next_doc_no(db, "mfg_subcontract_receipt", context.org_id, row.plan_date),
        subcontract_order_id=row.id,
        warehouse_id=row.warehouse_id,
        material_id=row.material_id,
        good_quantity=good_quantity,
        unit_cost=unit_cost,
        processing_fee_amount=allocated_fee,
        operation_key=payload.operation_key,
        status="completed",
        source_type="mfg_subcontract_order",
        source_id=row.id,
        created_by=context.id,
    )
    try:
        with db.begin_nested():
            db.add(receipt)
            db.flush()
    except IntegrityError:
        existing = _find_subcontract_receipt(db, row.id, payload.operation_key, context)
        if existing is None:
            raise
        return existing
    post_stock_transaction(
        db,
        context,
        source_type=SUBCONTRACT_RECEIPT_SOURCE,
        source_id=receipt.id,
        warehouse_id=row.warehouse_id,
        material_id=row.material_id,
        quantity=good_quantity,
        direction="in",
        unit_cost=unit_cost,
    )
    row.received_quantity = _quantity(row.received_quantity + good_quantity)
    row.status = "completed" if row.received_quantity == _quantity(row.quantity) else "partially_received"
    row.updated_by = context.id
    create_payable_from_subcontract_receipt(db, receipt.id, context)
    write_operation_log(
        db, user=context.user, action="receive", resource="mfg_subcontract_order", target_id=row.id, detail={"receipt_id": receipt.id}
    )
    db.flush()
    return receipt
## Finance service
    existing = db.scalar(select(PurchasePayable).where(PurchasePayable.source_type == "purchase_receipt", PurchasePayable.source_id == receipt.id))
    if existing:
        return existing
    payable = PurchasePayable(
        org_id=context.org_id,
        doc_no=f"AP-{receipt.doc_no}",
        supplier_id=receipt.supplier_id,
        source_type="purchase_receipt",
        source_id=receipt.id,
        total_amount=receipt.total_amount,
        status="open",
    )
    db.add(payable)
    db.flush()
    return payable


def create_payable_from_subcontract_receipt(
    db: Session, receipt_id: str, context: UserContext
) -> PurchasePayable:
    receipt = db.get(MfgSubcontractReceipt, receipt_id)
    if receipt is None or receipt.org_id != context.org_id:
        raise AppError("委外收货单不存在", code=404)
    existing = db.scalar(
        select(PurchasePayable).where(
            PurchasePayable.org_id == context.org_id,
            PurchasePayable.source_type == "subcontract_receipt",
            PurchasePayable.source_id == receipt.id,
        )
    )
    if existing:
        return existing
    payable = PurchasePayable(
        org_id=context.org_id,
        doc_no=f"AP-{receipt.doc_no}",
        supplier_id=receipt.subcontract_order.supplier_id,
        source_type="subcontract_receipt",
        source_id=receipt.id,
        total_amount=receipt.processing_fee_amount,
        status="open",
    )
    try:
        with db.begin_nested():
            db.add(payable)
            db.flush()
    except IntegrityError:
        existing = db.scalar(
            select(PurchasePayable).where(
                PurchasePayable.org_id == context.org_id,
                PurchasePayable.source_type == "subcontract_receipt",
                PurchasePayable.source_id == receipt.id,
            )
        )
        if existing is None:
            raise
        return existing
## Tests
    client, session = client_and_session
    seed_subcontract_data(session)
    order = client.post("/api/production/subcontract-orders", json=order_payload(), headers=headers()).json()["data"]
    client.post(f"/api/production/subcontract-orders/{order['id']}/release", headers=headers())

    cancelled = client.post(f"/api/production/subcontract-orders/{order['id']}/cancel", headers=headers())
    issue_after_cancel = client.post(
        f"/api/production/subcontract-orders/{order['id']}/issue",
        json={"items": [{"material_id": "subcontract-raw-1", "quantity": "1"}]},
        headers=headers(),
    )

    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert issue_after_cancel.json()["code"] == 400


def test_subcontract_receipt_operation_key_allows_equal_partials_and_preserves_fee_residual(client_and_session):
    """Payload equality must not collapse two physical equal deliveries, while a retry must not duplicate stock or payables."""
    client, session = client_and_session
    seed_subcontract_data(session)
    order = client.post(
        "/api/production/subcontract-orders",
        json=order_payload(processing_fee="100.01"),
        headers=headers(),
    ).json()["data"]
    client.post(f"/api/production/subcontract-orders/{order['id']}/release", headers=headers())

    first = client.post(
        f"/api/production/subcontract-orders/{order['id']}/receipts",
        json={"good_quantity": "5", "unit_cost": "12", "operation_key": "partial-receipt-1"},
        headers=headers(),
    )
    second = client.post(
        f"/api/production/subcontract-orders/{order['id']}/receipts",
        json={"good_quantity": "5", "unit_cost": "12", "operation_key": "partial-receipt-2"},
        headers=headers(),
    )
    retried_first = client.post(
        f"/api/production/subcontract-orders/{order['id']}/receipts",
        json={"good_quantity": "5", "unit_cost": "12", "operation_key": "partial-receipt-1"},
        headers=headers(),
    )

    first_receipt = first.json()["data"]
    second_receipt = second.json()["data"]
    assert first_receipt["id"] != second_receipt["id"]
    assert first_receipt["processing_fee_amount"] == "50.01"
    assert second_receipt["processing_fee_amount"] == "50.00"
    assert retried_first.json()["data"]["id"] == first_receipt["id"]
    assert session.query(InvStockTransaction).filter_by(source_type="subcontract_receipt").count() == 2
    payables = session.query(PurchasePayable).filter_by(source_type="subcontract_receipt").all()
    assert {payable.total_amount for payable in payables} == {Decimal("50.01"), Decimal("50.00")}


def test_subcontract_receipt_requires_nonblank_operation_key_and_hides_foreign_order(client_and_session):
    """An empty idempotency key or foreign order must not create a receipt side effect."""
    client, session = client_and_session
    seed_subcontract_data(session)
    order = client.post("/api/production/subcontract-orders", json=order_payload(), headers=headers()).json()["data"]
    client.post(f"/api/production/subcontract-orders/{order['id']}/release", headers=headers())

    invalid_key = client.post(
        f"/api/production/subcontract-orders/{order['id']}/receipts",
        json={"good_quantity": "1", "unit_cost": "12", "operation_key": ""},
        headers=headers(),
    )
    foreign_order = client.post(
        "/api/production/subcontract-orders/foreign-order/receipts",
        json={"good_quantity": "1", "unit_cost": "12", "operation_key": "foreign-order-receipt"},
        headers=headers(),
    )

    assert invalid_key.json()["code"] == 422
    assert foreign_order.json()["code"] == 404
    assert session.query(InvStockTransaction).filter_by(source_type="subcontract_receipt").count() == 0


def test_subcontract_issue_unique_invariant_rejects_a_stale_duplicate(client_and_session):
    """Without the database invariant, two stale requests can both post outbound subcontract stock."""
    client, session = client_and_session
    seed_subcontract_data(session)
    order = client.post("/api/production/subcontract-orders", json=order_payload(), headers=headers()).json()["data"]
    client.post(f"/api/production/subcontract-orders/{order['id']}/release", headers=headers())
    issue = client.post(
        f"/api/production/subcontract-orders/{order['id']}/issue",
        json={"items": [{"material_id": "subcontract-raw-1", "quantity": "1"}]},
        headers=headers(),
    ).json()["data"]

    session.add(
        MfgMaterialIssue(
            org_id="org-1",
            subcontract_order_id=order["id"],
            warehouse_id="subcontract-warehouse-1",
            source_type="mfg_subcontract_order",
            source_id=order["id"],
            created_by="user-1",
        )
    )
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()

    retried_issue = client.post(
        f"/api/production/subcontract-orders/{order['id']}/issue",
        json={"items": [{"material_id": "subcontract-raw-1", "quantity": "1"}]},
        headers=headers(),
    )
    assert retried_issue.json()["data"]["id"] == issue["id"]
    assert session.query(InvStockTransaction).filter_by(source_type="subcontract_material_issue").count() == 1


def test_subcontract_payable_recovers_from_a_stale_duplicate_lookup(client_and_session, monkeypatch):
    """A stale payable lookup must recover the source-unique payable instead of creating a second liability."""
    client, session = client_and_session
    seed_subcontract_data(session)
    order = client.post("/api/production/subcontract-orders", json=order_payload(), headers=headers()).json()["data"]
    client.post(f"/api/production/subcontract-orders/{order['id']}/release", headers=headers())
    receipt = client.post(
        f"/api/production/subcontract-orders/{order['id']}/receipts",
        json={"good_quantity": "10", "unit_cost": "12", "operation_key": "payable-recovery-receipt"},
        headers=headers(),
    ).json()["data"]
    payable = session.query(PurchasePayable).filter_by(source_type="subcontract_receipt", source_id=receipt["id"]).one()
    real_scalar = session.scalar
    lookup_count = 0

    def stale_first_lookup(*args, **kwargs):
        nonlocal lookup_count
        lookup_count += 1
        if lookup_count == 1:
            return None
        return real_scalar(*args, **kwargs)

    monkeypatch.setattr(session, "scalar", stale_first_lookup)
    recovered = create_payable_from_subcontract_receipt(
        session,
        receipt["id"],
        UserContext(user=session.get(SysUser, "user-1"), permissions={"*"}),
    )

    assert recovered.id == payable.id
    assert session.query(PurchasePayable).filter_by(source_type="subcontract_receipt", source_id=receipt["id"]).count() == 1


def test_sql_contains_repeatable_subcontract_schema_bootstrap():
    """Removing subcontract tables or guarded upgrades breaks existing MySQL installations on re-run."""
    sql = (Path(__file__).parents[2] / "database" / "init.sql").read_text(encoding="utf-8").lower()

    for table in ("mfg_subcontract_order", "mfg_subcontract_receipt"):
        table_sql = sql.split(f"create table if not exists {table}", 1)[1].split("engine=", 1)[0]
        assert "is_deleted tinyint(1) not null default 0" in table_sql
        assert "created_at datetime(6) not null default current_timestamp(6)" in table_sql
        assert "updated_at datetime(6) not null default current_timestamp(6) on update current_timestamp(6)" in table_sql
        assert "version int not null default 1" in table_sql
    assert "create procedure phase2_add_task4_column" in sql
    assert "call phase2_add_task4_column('mfg_material_issue', 'subcontract_order_id'" in sql
    assert "uk_mfg_material_issue_subcontract_order" in sql
    assert "uk_mfg_subcontract_receipt_operation" in sql
    assert "operation_key varchar(64) not null" in sql
## SQL
  required_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  issued_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  returned_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  line_no INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_work_order_material_order (work_order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_material_issue (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  work_order_id CHAR(36) NULL,
  subcontract_order_id CHAR(36) NULL,
  warehouse_id CHAR(36) NOT NULL,
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  created_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_material_issue_order (work_order_id),
  KEY idx_mfg_material_issue_org (org_id),
  UNIQUE KEY uk_mfg_material_issue_subcontract_order (subcontract_order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_material_issue_item (
  id CHAR(36) PRIMARY KEY,
  issue_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  quantity DECIMAL(18,6) NOT NULL,
  returned_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  unit_cost DECIMAL(18,6) NOT NULL DEFAULT 0,
  line_no INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_material_issue_item_issue (issue_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_material_return (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  work_order_id CHAR(36) NOT NULL,
  issue_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  created_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_material_return_order (work_order_id),
  KEY idx_mfg_material_return_issue (issue_id),
  KEY idx_mfg_material_return_org (org_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_material_return_item (
  id CHAR(36) PRIMARY KEY,
  return_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  quantity DECIMAL(18,6) NOT NULL,
  unit_cost DECIMAL(18,6) NOT NULL DEFAULT 0,
  line_no INT NOT NULL DEFAULT 1,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_material_return_item_return (return_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_work_report (
  id CHAR(36) PRIMARY KEY,
  work_order_id CHAR(36) NOT NULL,
  good_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  scrap_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  hours DECIMAL(18,6) NOT NULL DEFAULT 0,
  report_time DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  created_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  KEY idx_mfg_work_report_order (work_order_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_subcontract_order (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  supplier_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  plan_date DATE NOT NULL,
  quantity DECIMAL(18,6) NOT NULL,
  received_quantity DECIMAL(18,6) NOT NULL DEFAULT 0,
  processing_fee DECIMAL(18,2) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'draft',
  source_type VARCHAR(64) NULL,
  source_id CHAR(36) NULL,
  created_by CHAR(36) NULL,
  updated_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_mfg_subcontract_order_doc_no (org_id, doc_no),
  KEY idx_mfg_subcontract_order_supplier (org_id, supplier_id),
  KEY idx_mfg_subcontract_order_material (org_id, material_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS mfg_subcontract_receipt (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  doc_no VARCHAR(64) NOT NULL,
  subcontract_order_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  material_id CHAR(36) NOT NULL,
  good_quantity DECIMAL(18,6) NOT NULL,
  unit_cost DECIMAL(18,6) NOT NULL,
  processing_fee_amount DECIMAL(18,2) NOT NULL,
  operation_key VARCHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'completed',
  source_type VARCHAR(64) NOT NULL,
  source_id CHAR(36) NOT NULL,
  created_by CHAR(36) NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
  version INT NOT NULL DEFAULT 1,
  UNIQUE KEY uk_mfg_subcontract_receipt_doc_no (org_id, doc_no),
  UNIQUE KEY uk_mfg_subcontract_receipt_operation (org_id, subcontract_order_id, operation_key),
  KEY idx_mfg_subcontract_receipt_order (subcontract_order_id),
  KEY idx_mfg_subcontract_receipt_source (org_id, source_type, source_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Upgrade the Task 1 work-order stub and any partial Task 3 schema when this
-- script is re-run. CREATE TABLE IF NOT EXISTS does not add columns.
DROP PROCEDURE IF EXISTS phase2_add_task3_column;
DELIMITER //
CREATE PROCEDURE phase2_add_task3_column(
  IN table_name_input VARCHAR(64),
  IN column_name_input VARCHAR(64),

CALL phase2_rename_task3_column('mfg_work_report', 'reported_quantity', 'good_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_report', 'good_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_report', 'scrap_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_report', 'hours', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task3_column('mfg_work_report', 'report_time', 'DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)');
CALL phase2_add_task3_column('mfg_work_report', 'created_by', 'CHAR(36) NULL');

UPDATE mfg_work_order
SET bom_snapshot = JSON_OBJECT()
WHERE bom_snapshot IS NULL;
ALTER TABLE `mfg_work_order` MODIFY COLUMN `bom_snapshot` JSON NOT NULL;
DROP PROCEDURE IF EXISTS phase2_add_task3_column;
DROP PROCEDURE IF EXISTS phase2_rename_task3_column;

-- Upgrade Task 4 subcontract fields safely when this script is re-run against
-- an existing Phase 2 database. The prior material issue table only accepted
-- work-order issues, so its work_order_id must become optional.
DROP PROCEDURE IF EXISTS phase2_add_task4_column;
DELIMITER //
CREATE PROCEDURE phase2_add_task4_column(
  IN table_name_input VARCHAR(64),
  IN column_name_input VARCHAR(64),
  IN column_definition TEXT
)
BEGIN
  DECLARE column_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO column_exists
  FROM information_schema.columns
  WHERE table_schema = DATABASE()
    AND table_name = table_name_input
    AND column_name = column_name_input;
  IF column_exists = 0 THEN
    SET @phase2_task4_sql = CONCAT(
      'ALTER TABLE `', table_name_input, '` ADD COLUMN `', column_name_input, '` ', column_definition
    );
    PREPARE phase2_task4_statement FROM @phase2_task4_sql;
    EXECUTE phase2_task4_statement;
    DEALLOCATE PREPARE phase2_task4_statement;
  END IF;
END//
DELIMITER ;

DROP PROCEDURE IF EXISTS phase2_add_task4_index;
DELIMITER //
CREATE PROCEDURE phase2_add_task4_index(
  IN table_name_input VARCHAR(64),
  IN index_name_input VARCHAR(64),
  IN index_definition TEXT
)
BEGIN
  DECLARE index_exists INT DEFAULT 0;
  SELECT COUNT(*) INTO index_exists
  FROM information_schema.statistics
  WHERE table_schema = DATABASE()
    AND table_name = table_name_input
    AND index_name = index_name_input;
  IF index_exists = 0 THEN
    SET @phase2_task4_index_sql = CONCAT(
      'ALTER TABLE `', table_name_input, '` ADD ', index_definition
    );
    PREPARE phase2_task4_index_statement FROM @phase2_task4_index_sql;
    EXECUTE phase2_task4_index_statement;
    DEALLOCATE PREPARE phase2_task4_index_statement;
  END IF;
END//
DELIMITER ;

CALL phase2_add_task4_column('mfg_material_issue', 'subcontract_order_id', 'CHAR(36) NULL');
CALL phase2_add_task4_column('mfg_material_issue', 'source_type', 'VARCHAR(64) NULL');
CALL phase2_add_task4_column('mfg_material_issue', 'source_id', 'CHAR(36) NULL');
ALTER TABLE `mfg_material_issue` MODIFY COLUMN `work_order_id` CHAR(36) NULL;
CALL phase2_add_task4_column('mfg_subcontract_order', 'received_quantity', 'DECIMAL(18,6) NOT NULL DEFAULT 0');
CALL phase2_add_task4_column('mfg_subcontract_order', 'processing_fee', 'DECIMAL(18,2) NOT NULL DEFAULT 0');
CALL phase2_add_task4_column('mfg_subcontract_order', 'source_type', 'VARCHAR(64) NULL');
CALL phase2_add_task4_column('mfg_subcontract_order', 'source_id', 'CHAR(36) NULL');
CALL phase2_add_task4_column('mfg_subcontract_order', 'created_by', 'CHAR(36) NULL');
CALL phase2_add_task4_column('mfg_subcontract_order', 'updated_by', 'CHAR(36) NULL');
CALL phase2_add_task4_column('mfg_subcontract_receipt', 'processing_fee_amount', 'DECIMAL(18,2) NOT NULL DEFAULT 0');
CALL phase2_add_task4_column('mfg_subcontract_receipt', 'operation_key', 'VARCHAR(64) NULL');
CALL phase2_add_task4_column('mfg_subcontract_receipt', 'source_type', 'VARCHAR(64) NOT NULL DEFAULT ''''');
CALL phase2_add_task4_column('mfg_subcontract_receipt', 'source_id', 'CHAR(36) NOT NULL DEFAULT ''''');
CALL phase2_add_task4_column('mfg_subcontract_receipt', 'created_by', 'CHAR(36) NULL');
UPDATE mfg_subcontract_receipt
SET operation_key = id
WHERE operation_key IS NULL OR operation_key = '';
ALTER TABLE `mfg_subcontract_receipt` MODIFY COLUMN `operation_key` VARCHAR(64) NOT NULL;
CALL phase2_add_task4_index('mfg_material_issue', 'uk_mfg_material_issue_subcontract_order', 'UNIQUE KEY uk_mfg_material_issue_subcontract_order (subcontract_order_id)');
CALL phase2_add_task4_index('mfg_subcontract_receipt', 'uk_mfg_subcontract_receipt_operation', 'UNIQUE KEY uk_mfg_subcontract_receipt_operation (org_id, subcontract_order_id, operation_key)');
DROP PROCEDURE IF EXISTS phase2_add_task4_column;
DROP PROCEDURE IF EXISTS phase2_add_task4_index;

CREATE TABLE IF NOT EXISTS inv_zone (
  id CHAR(36) PRIMARY KEY,
  org_id CHAR(36) NOT NULL,
  warehouse_id CHAR(36) NOT NULL,
  code VARCHAR(64) NOT NULL,
  name VARCHAR(128) NOT NULL,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
