import { describe, expect, it } from "vitest";

// @ts-expect-error Node types are not part of the production frontend dependency set.
import { readFileSync } from "node:fs";

function source(path: string) {
  return readFileSync(new URL(path, import.meta.url), "utf8");
}

describe("P0 财务、生产成本与统一单据页面", () => {
  it("exposes the general-ledger foundation and voucher lifecycle", () => {
    const page = source("../src/views/finance/FinanceFoundation.vue");
    const voucher = source("../src/views/finance/VoucherList.vue");
    const api = source("../src/api/finance.ts");

    expect(page).toContain("会计科目");
    expect(page).toContain("会计期间");
    expect(page).toContain("固定资产");
    expect(page).toContain("runAssetDepreciation");
    expect(voucher).toContain("createManualVoucher");
    expect(voucher).toContain("postVoucher");
    expect(voucher).toContain("reverseVoucher");
    expect(api).toContain("/finance/periods/${period}/close");
  });

  it("shows actual work-order costs and configurable conversion rates", () => {
    const orders = source("../src/views/production/WorkOrderList.vue");
    const resources = source("../src/views/production/ProductionResources.vue");
    const api = source("../src/api/production.ts");

    expect(orders).toContain("实际单位成本");
    expect(orders).toContain("生产实际成本");
    expect(resources).toContain("人工费率/时");
    expect(resources).toContain("制造费率/时");
    expect(api).toContain("/production/work-orders/${id}/cost");
  });

  it("provides shared filters, saved views, bulk actions, and background exports", () => {
    const page = source("../src/views/UnifiedDocumentCenter.vue");
    const api = source("../src/api/documents.ts");
    const list = source("../src/components/DocumentListWorkbench.vue");

    expect(page).toContain("保存当前视图");
    expect(page).toContain("runBulkDocumentCommand");
    expect(page).toContain("后台导出");
    expect(api).toContain("/documents/bulk-commands");
    expect(api).toContain("/documents/exports");
    expect(list).toContain("released: \"已下达\"");
  });

  it("requires a real warehouse selection before creating a WMS task", () => {
    const page = source("../src/views/inventory-advanced/WmsTaskCenter.vue");
    expect(page).toContain('listMasterData("warehouses")');
    expect(page).toContain('placeholder="请选择仓库"');
    expect(page).toContain('ElMessage.warning("请先选择仓库")');
    expect(page).toContain(':disabled="!form.warehouse_id"');
  });

  it("exposes executable controls for the four P0 workstreams", () => {
    const wms = source("../src/views/inventory-advanced/WmsTaskCenter.vue");
    const production = source("../src/views/production/ExecutionControl.vue");
    const finance = source("../src/views/finance/FinanceControls.vue");
    const platform = source("../src/views/settings/PlatformEvents.vue");
    expect(wms).toContain("createPickWave");
    expect(production).toContain("createWorkOrderSchedule");
    expect(production).toContain("createAlternateMaterial");
    expect(production).toContain("createWorkOrderException");
    expect(finance).toContain("createBudget");
    expect(finance).toContain("createCashForecast");
    expect(finance).toContain("createReconciliationStatement");
    expect(platform).toContain("processDueEvents");
  });
});
