import { beforeEach, describe, expect, it, vi } from "vitest";

const { deleteMock, getMock, postMock } = vi.hoisted(() => ({
  deleteMock: vi.fn(),
  getMock: vi.fn(),
  postMock: vi.fn(),
}));

vi.mock("../src/api/http", () => ({
  http: { delete: deleteMock, get: getMock, post: postMock },
}));

import {
  addDocumentComment,
  deleteDocumentAttachment,
  getDocumentWorkspace,
  listDocuments,
  listNotifications,
  markAllNotificationsRead,
  runDocumentCommand,
} from "../src/api/documents";

describe("统一单据工作台 API", () => {
  beforeEach(() => vi.clearAllMocks());

  it("uses the page/filter contract and explicit commands", async () => {
    await listDocuments({ business_type: "sales_order", status: "submitted", page: 2, page_size: 20, sort: "-updated_at" });
    await getDocumentWorkspace("sales_order", "order-1");
    await runDocumentCommand("sales_order", "order-1", "approve");

    expect(getMock).toHaveBeenNthCalledWith(1, "/documents", { params: { business_type: "sales_order", status: "submitted", page: 2, page_size: 20, sort: "-updated_at" } });
    expect(getMock).toHaveBeenNthCalledWith(2, "/documents/sales_order/order-1");
    expect(postMock).toHaveBeenCalledWith("/documents/sales_order/order-1/commands", { command: "approve", payload: {} });
  });

  it("supports collaboration, notification and attachment lifecycle", async () => {
    await addDocumentComment("sales_order", "order-1", "请确认交期");
    await listNotifications({ unread_only: true });
    await markAllNotificationsRead();
    await deleteDocumentAttachment("attachment-1");

    expect(postMock).toHaveBeenNthCalledWith(1, "/documents/sales_order/order-1/comments", { content: "请确认交期" });
    expect(getMock).toHaveBeenCalledWith("/notifications", { params: { unread_only: true } });
    expect(postMock).toHaveBeenNthCalledWith(2, "/notifications/read-all");
    expect(deleteMock).toHaveBeenCalledWith("/documents/attachments/attachment-1");
  });

  it("clears an expired session when the unified body carries code 401", () => {
    const sources = import.meta.glob("../src/api/http.ts", { query: "?raw", import: "default", eager: true }) as Record<string, string>;
    const source = Object.values(sources)[0] || "";
    expect(source).toContain("response.data?.code === 401");
    expect(source).toContain('window.location.href = "/login"');
  });

  it("does not ship the default administrator password in the login form", () => {
    const sources = import.meta.glob("../src/views/Login.vue", { query: "?raw", import: "default", eager: true }) as Record<string, string>;
    const source = Object.values(sources)[0] || "";
    expect(source).toContain('const username = ref("")');
    expect(source).toContain('const password = ref("")');
    expect(source).not.toContain('const password = ref("Admin@123")');
  });
});
