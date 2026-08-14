import { describe, expect, it } from "vitest";

// @ts-expect-error Node types are not part of the production frontend dependency set.
import { readFileSync } from "node:fs";

function source(path: string) {
  return readFileSync(new URL(path, import.meta.url), "utf8");
}

describe("P1 库存控制与质量闭环页面", () => {
  it("provides reservation validation, status filtering, and traceability filters", () => {
    const page = source("../src/views/inventory-advanced/ControlCenter.vue");
    const api = source("../src/api/inventory-advanced.ts");
    expect(page).toContain("请填写来源单据、物料、仓库和有效数量");
    expect(page).toContain("reservationStatus");
    expect(page).toContain("traceFilters");
    expect(page).toContain('class="control-form"');
    expect(page).toContain("align-items: flex-end");
    expect(page).toContain("暂无可用物料或仓库");
    expect(page).toContain("暂无批次追溯事件");
    expect(api).toContain("/inventory/advanced/reservations");
    expect(api).toContain("/inventory/advanced/trace");
  });

  it("submits every inspection-plan item and exposes the NCR/CAPA handoff", () => {
    const page = source("../src/views/quality/InspectionList.vue");
    const api = source("../src/api/quality.ts");
    expect(page).toContain("resultItems");
    expect(page).toContain("请完成全部检验项目，并明确每项是否通过");
    expect(page).toContain("按检验计划创建的检验单必须完成全部项目后才能提交");
    expect(page).toContain("处理 NCR/CAPA");
    expect(api).toContain("/quality/inspections/from-plan");
    expect(api).toContain("/quality/nonconformances");
  });
});
