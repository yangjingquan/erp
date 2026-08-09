import { beforeEach, describe, expect, it, vi } from "vitest";

const { getMock, postMock, putMock } = vi.hoisted(() => ({
  getMock: vi.fn(),
  postMock: vi.fn(),
  putMock: vi.fn(),
}));

vi.mock("../src/api/http", () => ({
  http: {
    get: getMock,
    post: postMock,
    put: putMock,
  },
}));

import { listOperationLogs } from "../src/api/system";
import { createPrintTemplate, listGlobalParameters, listPrintTemplates, updateGlobalParameter } from "../src/api/config";
import { createBackup, restoreBackup, validateRestore } from "../src/api/backup";
import { getWorkflowDefinition, saveWorkflowDefinition } from "../src/api/workflow";
import { updateAdmin } from "../src/api/admin";

describe("系统设置 API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads operation logs from the system endpoint", async () => {
    await listOperationLogs();

    expect(getMock).toHaveBeenCalledWith("/system/operation-logs");
  });

  it("loads and updates global parameters using the parameter key", async () => {
    const payload = { parameter_value: "true", value_type: "boolean", description: "允许负库存" };

    await listGlobalParameters();
    await updateGlobalParameter("inventory.allow_negative", payload);

    expect(getMock).toHaveBeenCalledWith("/config/parameters");
    expect(putMock).toHaveBeenCalledWith("/config/parameters/inventory.allow_negative", payload);
  });

  it("uses the backup and restore endpoints with path and confirmation word", async () => {
    await createBackup();
    await validateRestore("/tmp/erp.sql", "RESTORE ERP");
    await restoreBackup("/tmp/erp.sql", "RESTORE ERP");

    expect(postMock).toHaveBeenNthCalledWith(1, "/system/backup");
    expect(postMock).toHaveBeenNthCalledWith(2, "/system/restore/validate", undefined, {
      params: { path: "/tmp/erp.sql", confirmation_token: "RESTORE ERP" },
    });
    expect(postMock).toHaveBeenNthCalledWith(3, "/system/restore", undefined, {
      params: { path: "/tmp/erp.sql", confirmation_token: "RESTORE ERP" },
    });
  });

  it("persists workflow definitions through the backend", async () => {
    const payload = { name: "销售审批", status: "active", nodes: [] };

    await getWorkflowDefinition("sales_order");
    await saveWorkflowDefinition("sales_order", payload);

    expect(getMock).toHaveBeenCalledWith("/workflow/definitions/sales_order");
    expect(putMock).toHaveBeenCalledWith("/workflow/definitions/sales_order", payload);
  });

  it("uses the print template list and create endpoints", async () => {
    const payload = { business_type: "sales_order", name: "订单", template_html: "<h1>{{ doc_no }}</h1>", status: "active" };

    await listPrintTemplates();
    await createPrintTemplate(payload);

    expect(getMock).toHaveBeenCalledWith("/config/print-templates");
    expect(postMock).toHaveBeenCalledWith("/config/print-templates", payload);
  });

  it("uses the department and role update endpoint", async () => {
    const payload = { code: "sales-new", name: "销售一部", parent_id: null };

    await updateAdmin("departments", "department-1", payload);

    expect(putMock).toHaveBeenCalledWith("/admin/departments/department-1", payload);
  });
});
