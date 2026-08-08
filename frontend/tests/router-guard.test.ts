import { beforeEach, describe, expect, it } from "vitest";
import { createPinia, setActivePinia } from "pinia";

import { useAuthStore } from "../src/stores/auth";
import { router } from "../src/router";

describe("route guard", () => {
  beforeEach(async () => {
    setActivePinia(createPinia());
    await router.push("/login");
  });

  it("redirects unauthenticated users to login", async () => {
    await router.push("/dashboard");

    expect(router.currentRoute.value.path).toBe("/login");
  });

  it("allows authenticated users to reach dashboard", async () => {
    const auth = useAuthStore();
    auth.token = "test-token";

    await router.push("/dashboard");

    expect(router.currentRoute.value.path).toBe("/dashboard");
  });

  it("registers the一期 business and operations routes", () => {
    const paths = router.getRoutes().map((route) => route.path);

    expect(paths).toEqual(expect.arrayContaining([
      "/sales/orders",
      "/sales/quotes",
      "/sales/returns",
      "/purchase/orders",
      "/purchase/requests",
      "/purchase/returns",
      "/inventory/stock",
      "/inventory/transactions",
      "/inventory/transfers",
      "/inventory/counts",
      "/finance/receivables",
      "/finance/payables",
      "/finance/expenses",
      "/finance/vouchers",
      "/settings/workflow",
      "/system/operation-logs",
      "/system/users",
      "/system/admin",
      "/master-data/units",
      "/master-data/tax-rates",
      "/profile",
    ]));
  });
});
