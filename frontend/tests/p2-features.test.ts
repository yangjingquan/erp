import { describe, expect, it } from "vitest";

import { isKnownOrderStatus, orderStatusLabel, orderStatusTagType } from "../src/utils/orderStatus";

// @ts-expect-error Node types are not part of the production frontend dependency set.
import { readFileSync } from "node:fs";

function source(path: string) {
  return readFileSync(new URL(path, import.meta.url), "utf8");
}

describe("P2 业务订单状态展示", () => {
  it("keeps order statuses separate from master-data statuses", () => {
    expect(orderStatusLabel("active")).toBe("未知状态");
    expect(orderStatusTagType("active")).toBe("warning");
    expect(isKnownOrderStatus("approved")).toBe(true);
    expect(source("../src/views/sales/SalesOrderList.vue")).toContain("OrderStatusTag");
    expect(source("../src/views/purchase/PurchaseOrderList.vue")).toContain("OrderStatusTag");
  });

  it("warns when an unknown order status is rendered", () => {
    const component = source("../src/components/OrderStatusTag.vue");
    expect(component).toContain("未知订单状态");
    expect(component).toContain("console.warn");
  });

  it("provides a visible recovery path for runtime, resource, and white-screen failures", () => {
    const app = source("../src/App.vue");
    const main = source("../src/main.ts");
    expect(app).toContain("页面未能正常渲染");
    expect(app).toContain("重新加载");
    expect(app).toContain("返回首页");
    expect(main).toContain("erp:resource-error");
    expect(main).toContain("erp:white-screen");
    expect(main).toContain("app.config.errorHandler");
  });
});
