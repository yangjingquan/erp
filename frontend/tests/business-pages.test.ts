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

    expect(salesOrder).toContain('<el-table-column label="操作" width="260" fixed="right">');
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
    expect(inspection).toContain(":header-cell-style=\"{ textAlign: 'center' }\"");
    expect(inspection).toContain(":cell-style=\"{ textAlign: 'center' }\"");
    expect(inspection).toContain("inspectionTypeLabels");
    expect(inspection).toContain("sourceDocumentLabel");
    expect(inspection).toContain("不合格");
    expect(inspection).toContain("已关闭");
    expect(inspection).toContain("处理 NCR/CAPA");
    expect(inspection).toContain("/quality/nonconformances");
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

  it("keeps payable reconciliation labels and terminology separate from receivables", () => {
    const payable = pageSources["../src/views/finance/PayableList.vue"];

    expect(payable).toContain("付款记录");
    expect(payable).toContain(":header-cell-style=\"{ textAlign: 'center' }\"");
    expect(payable).toContain(":cell-style=\"{ textAlign: 'center' }\"");
    expect(payable).toContain("reconciledLabel");
    expect(payable).toContain("statusLabel");
    expect(payable).toContain("该供应商暂无可核销的应付账款");
    expect(payable).not.toContain("该客户暂无可核销的应收账款");
  });

  it("keeps receivable reconciliation labels tied to customer receivables", () => {
    const receivable = pageSources["../src/views/finance/ReceivableList.vue"];

    expect(receivable).toContain("收款记录");
    expect(receivable).toContain(":header-cell-style=\"{ textAlign: 'center' }\"");
    expect(receivable).toContain(":cell-style=\"{ textAlign: 'center' }\"");
    expect(receivable).toContain("reconciledLabel");
    expect(receivable).toContain("statusLabel");
    expect(receivable).toContain("该客户暂无可核销的应收账款");
  });

  it("centers expense tables and hides voucher generation after creation", () => {
    const expense = pageSources["../src/views/finance/ExpenseList.vue"];

    expect(expense).toContain(":header-cell-style=\"{ textAlign: 'center' }\"");
    expect(expense).toContain(":cell-style=\"{ textAlign: 'center' }\"");
    expect(expense).toContain("!scope.row.voucher_generated");
    expect(expense).toContain("await load();");
  });

  it("centers BOM tables and renders translated status tags", () => {
    const bom = pageSources["../src/views/production/BomList.vue"];

    expect(bom).toContain(":header-cell-style=\"{ textAlign: 'center' }\"");
    expect(bom).toContain(":cell-style=\"{ textAlign: 'center' }\"");
    expect(bom).toContain("statusLabels");
    expect(bom).toContain("statusTagType");
    expect(bom).toContain("materialLabel");
    expect(bom).toContain('label="生效日期"');
    expect(bom).toContain('label="失效日期"');
    expect(bom).toContain("长期有效");
    expect(bom).toContain("已审核");
    expect(bom).toContain("border-width: 1px");
  });

  it("centers MRP and work-order tables and renders translated status tags", () => {
    const mrp = pageSources["../src/views/production/MrpRunList.vue"];
    const workOrder = pageSources["../src/views/production/WorkOrderList.vue"];

    for (const page of [mrp, workOrder]) {
      expect(page).toContain(":header-cell-style=\"{ textAlign: 'center' }\"");
      expect(page).toContain(":cell-style=\"{ textAlign: 'center' }\"");
      expect(page).toContain("statusLabels");
      expect(page).toContain("statusTagType");
      expect(page).toContain("materialLabel");
      expect(page).toContain("border-width: 1px");
    }
    expect(mrp).toContain("已计划");
    expect(mrp).toContain("已确认");
    expect(workOrder).toContain("进行中");
    expect(workOrder).toContain("已完成");
  });

  it("shows period reopening only with its dedicated permission", () => {
    const periodClose = import.meta.glob("../src/views/cost/PeriodClose.vue", { eager: true, import: "default", query: "?raw" })["../src/views/cost/PeriodClose.vue"] as string;

    expect(periodClose).toContain("reopenPeriod");
    expect(periodClose).toContain("cost:period:reopen");
    expect(periodClose).toContain("v-if=\"canReopen\"");
    expect(periodClose).toContain("确认重开");
  });

  it("centers employee and user management tables", () => {
    const employee = import.meta.glob("../src/views/hr/EmployeeList.vue", { eager: true, import: "default", query: "?raw" })["../src/views/hr/EmployeeList.vue"] as string;
    const user = import.meta.glob("../src/views/system/UserManagement.vue", { eager: true, import: "default", query: "?raw" })["../src/views/system/UserManagement.vue"] as string;

    for (const page of [employee, user]) {
      expect(page).toContain(":header-cell-style=\"{ textAlign: 'center' }\"");
      expect(page).toContain(":cell-style=\"{ textAlign: 'center' }\"");
    }
  });
});
