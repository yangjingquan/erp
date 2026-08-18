import { describe, expect, it } from "vitest";

// @ts-expect-error Node types are intentionally not part of the production frontend dependency set.
import { readFileSync } from "node:fs";
// @ts-expect-error Node types are intentionally not part of the production frontend dependency set.
import { resolve } from "node:path";

describe("EAM service list display", () => {
  it("renders readable asset, service type, customer, and priority values", () => {
    // @ts-expect-error Vitest supplies the runtime process global.
    const source = readFileSync(resolve(process.cwd(), "src/views/eam/AssetServiceCenter.vue"), "utf8");

    expect(source).toContain("useMasterOptions");
    expect(source).toContain('repair: "维修"');
    expect(source).toContain('maintenance: "保养"');
    expect(source).toContain('inspection: "点检"');
    expect(source).toContain('low: "低"');
    expect(source).toContain('normal: "普通"');
    expect(source).toContain('high: "高"');
    expect(source).toContain('urgent: "紧急"');
    expect(source).toContain("assetLabel(scope.row.asset_id)");
    expect(source).toContain("customerLabel(scope.row.customer_id)");
  });

  it("exposes asset maintenance, work-order closure, SLA, visits, and evidence workbench", () => {
    // @ts-expect-error Vitest supplies the runtime process global.
    const source = readFileSync(resolve(process.cwd(), "src/views/eam/AssetServiceCenter.vue"), "utf8");

    expect(source).toContain("generateMaintenanceWorkOrder");
    expect(source).toContain("updateAssetWorkOrder");
    expect(source).toContain("updateServiceCase");
    expect(source).toContain("createServiceVisit");
    expect(source).toContain("completeVisit");
    expect(source).toContain("DocumentWorkbench");
    expect(source).toContain("SLA到期");
    expect(source).toContain("customer_feedback");
  });
});
