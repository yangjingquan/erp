// @ts-expect-error The project does not currently include @types/node; Vitest provides this runtime module.
import { readFileSync } from "node:fs";

import { beforeEach, describe, expect, it, vi } from "vitest";

const { getMock, postMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
}));

vi.mock("../src/api/http", () => ({
  http: {
    get: getMock,
    post: postMock,
  },
}));

import { listMasterData } from "../src/api/master-data";

describe("master data api", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("passes search and pagination parameters to the list endpoint", async () => {
    getMock.mockResolvedValue({ data: { code: 0, msg: "ok", data: [] } });

    await listMasterData("materials", {
      keyword: "螺丝",
      page: 2,
      pageSize: 20,
    });

    expect(getMock).toHaveBeenCalledWith("/master/materials", {
      params: { keyword: "螺丝", page: 2, page_size: 20 },
    });
  });

  it("normalizes decimal strings before binding edit values to number controls", () => {
    const source = readFileSync(new URL("../src/views/master-data/MasterDataPage.vue", import.meta.url), "utf8");
    expect(source).toContain('field.type === "number" && value !== "" && value !== null ? Number(value) : value');
  });
});
