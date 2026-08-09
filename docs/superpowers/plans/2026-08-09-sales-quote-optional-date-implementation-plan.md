# Sales Quote Optional Date Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task with verification checkpoints.

**Goal:** Ensure creating a sales quote never sends an empty string for the optional `valid_until` date and never sends unrelated fields from the shared document form.

**Architecture:** Keep the backend contract strict (`date | None`) and make the frontend boundary responsible for constructing a sales-quote-specific payload. The API wrapper will defensively normalize blank `valid_until` values to `null` and whitelist quote item fields; the page reset will restore the form's nullable state.

**Tech Stack:** Vue 3, TypeScript, Axios wrapper, Vitest, Vite.

## Global Constraints

- Preserve the backend `valid_until: date | None` contract; do not make the backend accept `""`.
- Do not change purchase request, sales return, or purchase return payload behavior.
- Keep existing success/error handling and required material/quantity validation unchanged.

---

### Task 1: Add a regression test for the sales quote API payload

**Files:**
- Modify: `frontend/tests/business-api.test.ts`
- Reference: `frontend/src/api/sales.ts`

**Interfaces:**
- Consumes: `createSalesQuote(payload)` from `src/api/sales.ts`.
- Produces: A failing contract test proving blank `valid_until` becomes `null` and unrelated fields are removed.

- [ ] **Step 1: Extend the existing sales API test imports**

Add `createSalesQuote` to the import from `../src/api/sales`.

- [ ] **Step 2: Write the failing test**

Add this test inside the existing `describe("一期业务 API 路由", ...)` block:

```ts
  it("normalizes an empty quote validity date and whitelists quote fields", async () => {
    const payload = {
      customer_id: "customer-1",
      quote_date: "2026-08-09",
      valid_until: "",
      supplier_id: "",
      warehouse_id: "",
      items: [{ material_id: "material-1", quantity: 2, unit_price: 3, estimated_price: 0 }],
    };

    await createSalesQuote(payload);

    expect(postMock).toHaveBeenCalledWith("/sales/quotes", {
      customer_id: "customer-1",
      quote_date: "2026-08-09",
      valid_until: null,
      items: [{ material_id: "material-1", quantity: 2, unit_price: 3 }],
    });
  });
```

- [ ] **Step 3: Run the focused test and verify it fails**

Run: `npm test -- --run frontend/tests/business-api.test.ts` from the repository root, or `npm test -- --run tests/business-api.test.ts` from `frontend/`.

Expected: FAIL because the current `createSalesQuote` forwards the original payload unchanged.

- [ ] **Step 4: Commit the test**

```bash
git add frontend/tests/business-api.test.ts
git commit -m "test: cover sales quote optional date payload"
```

### Task 2: Normalize and whitelist sales quote requests

**Files:**
- Modify: `frontend/src/api/sales.ts:1-40`
- Modify: `frontend/src/views/DocumentExtensionPage.vue:11,17,19-23`

**Interfaces:**
- Consumes: Shared document form values from `DocumentExtensionPage.vue`.
- Produces: `POST /sales/quotes` payload with `{ customer_id, quote_date, valid_until: string | null, items }` only.

- [ ] **Step 1: Implement defensive normalization in `createSalesQuote`**

Define a sales quote payload type with `customer_id`, required `quote_date`, optional `valid_until`, and item fields `material_id`, `quantity`, and `unit_price`. In `createSalesQuote`, compute `valid_until` as `payload.valid_until?.trim() || null`, then post a new object containing only the allowed top-level fields. Map each item to the three allowed item fields so `estimated_price` and other shared-form properties cannot leak through.

- [ ] **Step 2: Make the page construct a quote-specific payload**

In the `isQuote()` branch of `save()`, pass only:

```ts
{
  customer_id: form.customer_id,
  quote_date: form.quote_date,
  valid_until: form.valid_until,
  items: [{
    material_id: form.items[0].material_id,
    quantity: form.items[0].quantity,
    unit_price: form.items[0].unit_price,
  }],
}
```

Leave the other document-type branches unchanged.

- [ ] **Step 3: Restore nullable state in `reset()`**

After resetting the date fields, explicitly set `form.valid_until = null`. This keeps the reactive form aligned with the API payload even before the defensive wrapper runs.

- [ ] **Step 4: Run the focused regression test**

Run: `npm test -- --run tests/business-api.test.ts` from `frontend/`.

Expected: PASS, including the new sales quote payload test.

- [ ] **Step 5: Run typecheck and frontend build**

Run: `npm run typecheck` and `npm run build` from `frontend/`.

Expected: both commands exit successfully with no TypeScript or Vite errors.

- [ ] **Step 6: Inspect the final diff and commit the implementation**

Run: `git diff --check && git diff -- frontend/src/api/sales.ts frontend/src/views/DocumentExtensionPage.vue frontend/tests/business-api.test.ts`.

Expected: only the quote payload normalization, quote-specific form mapping, reset null assignment, and regression test are present.

```bash
git add frontend/src/api/sales.ts frontend/src/views/DocumentExtensionPage.vue frontend/tests/business-api.test.ts
git commit -m "fix: normalize sales quote optional date"
```
