import { describe, expect, it } from "vitest";
// @ts-expect-error The project does not currently include @types/node; Vitest provides this runtime module.
import { readFileSync } from "node:fs";
// @ts-expect-error The project does not currently include @types/node; Vitest provides this runtime module.
import { resolve } from "node:path";

describe("phase 2 mobile scan page contract", () => {
  it("uses the scan API, carries scan_id, and presents processing errors", () => {
    // @ts-expect-error The project does not currently include @types/node; Vitest provides this runtime global.
    const source = readFileSync(resolve(process.cwd(), "src/views/inventory-advanced/Scan.vue"), "utf8");

    expect(source).toContain("createScanToken");
    expect(source).toContain("processScan");
    expect(source).toContain("scan_id");
    expect(source).toContain("ElMessage.error");
  });
});
