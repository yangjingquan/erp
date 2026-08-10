import { describe, expect, it } from "vitest";

const pageSources = import.meta.glob("../src/views/{sales,purchase,inventory,finance,quality,production}/*.vue", {
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

  it("keeps the highlighted quality and MRP identifiers on one line", () => {
    const inspection = pageSources["../src/views/quality/InspectionList.vue"];
    const mrp = pageSources["../src/views/production/MrpRunList.vue"];

    expect(inspection).toContain('label="来源类型" width="180" class-name="nowrap-column"');
    expect(mrp).toContain('label="计划单号" width="190" class-name="nowrap-column"');
    expect(inspection).toContain("white-space: nowrap");
    expect(mrp).toContain("white-space: nowrap");
  });

  it("reloads locations after creating one from the warehouse selector", () => {
    const location = import.meta.glob("../src/views/inventory-advanced/LocationList.vue", { eager: true, import: "default", query: "?raw" })["../src/views/inventory-advanced/LocationList.vue"] as string;

    expect(location).toContain('selectedWarehouseId.value = warehouseId;');
    expect(location).toContain('selectedWarehouseId.value = warehouseId;\n    await load();');
  });

  it("loads all locations without a warehouse filter and displays the selected warehouse", () => {
    const location = import.meta.glob("../src/views/inventory-advanced/LocationList.vue", { eager: true, import: "default", query: "?raw" })["../src/views/inventory-advanced/LocationList.vue"] as string;

    expect(location).toContain("listLocations(selectedWarehouseId.value || undefined)");
    expect(location).toContain("warehouseName");
    expect(location).toContain("await load();");
    expect(location).toContain('label="库区"');
  });
});
