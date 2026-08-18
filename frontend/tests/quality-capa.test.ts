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
});
