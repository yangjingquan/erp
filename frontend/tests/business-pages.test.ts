import { describe, expect, it } from "vitest";

const pageSources = import.meta.glob("../src/views/{sales,purchase,inventory,finance}/*.vue", {
  eager: true,
  import: "default",
  query: "?raw",
}) as Record<string, string>;

describe("一期业务页面加载契约", () => {
  it.each(Object.entries(pageSources))("%s does not use a static empty rows source", (relativePath, source) => {

    expect(source).not.toContain("const rows: Record<string, unknown>[] = []");
    expect(source).toContain("loading");
    expect(source).toContain("onMounted");
  });

  it("列表操作列使用固定宽度，避免 fit 按 min-width 放大造成右侧空白", () => {
    const salesOrder = pageSources["../src/views/sales/SalesOrderList.vue"];
    const purchaseOrder = pageSources["../src/views/purchase/PurchaseOrderList.vue"];
    const expense = pageSources["../src/views/finance/ExpenseList.vue"];

    expect(salesOrder).toContain('<el-table-column label="操作" width="300">');
    expect(purchaseOrder).toContain('<el-table-column label="操作" width="300">');
    expect(expense).toContain('<el-table-column label="操作" width="260">');
  });
});
