import { describe, expect, it } from "vitest";

import App from "../src/App.vue";

describe("frontend smoke", () => {
  it("exports the root application component", () => {
    expect(App).toBeTruthy();
  });
});
