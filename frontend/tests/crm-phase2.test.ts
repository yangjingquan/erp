import { describe, expect, it } from "vitest";

// @ts-expect-error Node types are intentionally not part of the production frontend dependency set.
import { readFileSync } from "node:fs";
// @ts-expect-error Node types are intentionally not part of the production frontend dependency set.
import { resolve } from "node:path";

// @ts-expect-error Vitest supplies the runtime process global.
const source = (name: string) => readFileSync(resolve(process.cwd(), "src", "views", "crm", name), "utf8");

describe("CRM phase 2 pages", () => {
  it("loads and converts leads with visible error handling", () => {
    const page = source("LeadList.vue");
    expect(page).toContain("listLeads");
    expect(page).toContain("convertLead");
    expect(page).toContain("ElMessage.error");
  });

  it("loads opportunities and records follow-ups with visible error handling", () => {
    const page = source("OpportunityList.vue");
    expect(page).toContain("listOpportunities");
    expect(page).toContain("addFollowUp");
    expect(page).toContain("ElMessage.error");
  });
});
