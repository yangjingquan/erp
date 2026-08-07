import { describe, expect, it } from "vitest";

const pageSources = import.meta.glob("../src/views/{sales,purchase,inventory,finance}/*.vue", {
  eager: true,
  import: "default",
  query: "?raw",
}) as Record<string, string>;

describe("一期业务页面加载契约", () => {
  it.each(Object.entries(pageSources))("%s does not use a static empty rows source", (relativePath, source) => {

    expect(source).not.toContain("const rows: Record<string, unknown>[] = []");
    expect(source).toContain("loading");
    expect(source).toContain("onMounted");
  });
});
