import { describe, expect, it } from "vitest";

// @ts-expect-error Node types are not part of the production frontend dependency set.
import { readFileSync } from "node:fs";

function source(path: string) {
  return readFileSync(new URL(path, import.meta.url), "utf8");
}

describe("导航和关联字段交互", () => {
  it("keeps only one first-level navigation group open", () => {
    const layout = source("../src/layouts/AdminLayout.vue");
    const store = source("../src/stores/app.ts");
    expect(layout).toContain("activateNavigation");
    expect(layout).toContain("@select=\"activateMenu\"");
    expect(layout).toContain(":default-openeds=\"openMenuKeys\"");
    expect(layout).toContain("unique-opened");
    expect(store).toContain("openedNavigation");
    expect(store).toContain("this.openedNavigation = { path, title }");
  });

  it("uses master-data options instead of typing common IDs", () => {
    const sales = source("../src/views/sales/SalesOrderList.vue");
    const purchase = source("../src/views/purchase/PurchaseOrderList.vue");
    const transfer = source("../src/views/inventory/TransferList.vue");
    expect(sales).toContain("<el-select v-model=\"form.customer_id\"");
    expect(sales).toContain("<el-select v-model=\"form.items[0].material_id\"");
    expect(purchase).toContain("<el-select v-model=\"form.supplier_id\"");
    expect(transfer).toContain("<el-select v-model=\"form.from_warehouse_id\"");
  });
});
