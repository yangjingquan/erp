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
});
