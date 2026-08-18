import { describe, expect, it } from "vitest";

// @ts-expect-error Node types are intentionally not part of the production frontend dependency set.
import { readFileSync } from "node:fs";
// @ts-expect-error Node types are intentionally not part of the production frontend dependency set.
import { resolve } from "node:path";

describe("quality NCR/CAPA page", () => {
  it("supports investigation, corrective and preventive actions, evidence, and closure", () => {
    // @ts-expect-error Vitest provides the process runtime global.
    const source = readFileSync(resolve(process.cwd(), "src/views/quality/NonconformanceList.vue"), "utf8");

    expect(source).toContain("listNonconformances");
    expect(source).toContain("updateNonconformanceInvestigation");
    expect(source).toContain("createCapaAction");
    expect(source).toContain("completeCapaAction");
    expect(source).toContain("closeNonconformance");
    expect(source).toContain("纠正措施");
    expect(source).toContain("预防措施");
    expect(source).toContain("完成证据");
    expect(source).toContain("quality:manage");
    expect(source).toContain("source_document_name");
    expect(source).not.toContain("|| sourceId || \"-\"");
  });

  it("supports supplier quality aggregation, review, scoring and CAPA linkage", () => {
    // @ts-expect-error Vitest provides the process runtime global.
    const source = readFileSync(resolve(process.cwd(), "src/views/quality/QualityAnalyticsCenter.vue"), "utf8");

    expect(source).toContain("汇总采购检验");
    expect(source).toContain("listSupplierQualitySources");
    expect(source).toContain("approveSupplierQuality");
    expect(source).toContain("rejectSupplierQuality");
    expect(source).toContain("质量得分");
    expect(source).toContain("capaStatusLabel");
    expect(source).toContain("采购检验自动汇总");
  });

  it("uses a month picker and localized quality-cost types", () => {
    // @ts-expect-error Vitest provides the process runtime global.
    const source = readFileSync(resolve(process.cwd(), "src/views/quality/QualityAnalyticsCenter.vue"), "utf8");

    expect(source).toContain('type="month"');
    expect(source).toContain('value-format="YYYY-MM"');
    expect(source).toContain("qualityCostTypeLabel");
    expect(source).toContain("内部失败成本");
    expect(source).toContain("外部失败成本");
    expect(source).toContain("qualityCostSourceTypeLabels");
    expect(source).toContain("source_label");
  });

  it("localizes customer claim statuses and styles the claim table", () => {
    // @ts-expect-error Vitest provides the process runtime global.
    const source = readFileSync(resolve(process.cwd(), "src/views/quality/QualityAnalyticsCenter.vue"), "utf8");

    expect(source).toContain('class="customer-claim-table"');
    expect(source).toContain('class="customer-claim-status"');
    expect(source).toContain("statusLabel(scope.row.status)");
    expect(source).toContain("border");
    expect(source).toContain("listCustomerClaimSources");
    expect(source).toContain("transitionCustomerClaim");
    expect(source).toContain("流程：待处理 → 调查中 → 待审核 → 已审核/已驳回 → 已关闭");

    // @ts-expect-error Vitest provides the process runtime global.
    const labels = readFileSync(resolve(process.cwd(), "src/utils/labels.ts"), "utf8");
    expect(labels).toContain('investigating: "调查中"');
    expect(labels).toContain('pending_review: "待审核"');
  });
});
