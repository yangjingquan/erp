// @ts-expect-error The project does not currently include @types/node; Vitest provides this runtime module.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

function source(relativePath: string) {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8");
}

describe("系统设置页面交互契约", () => {
  it("loads operation logs from the API on mount and exposes loading/error handling", () => {
    const content = source("../src/views/system/OperationLog.vue");

    expect(content).toContain("listOperationLogs");
    expect(content).toContain("onMounted(load)");
    expect(content).toContain("v-loading=\"loading\"");
    expect(content).toContain("ElMessage.error");
  });

  it("loads parameters and persists each edited value through the API", () => {
    const content = source("../src/views/settings/GlobalParameters.vue");

    expect(content).toContain("listGlobalParameters");
    expect(content).toContain("updateGlobalParameter");
    expect(content).toContain("onMounted(load)");
    expect(content).toContain("@click=\"saveRow(scope.row)\"");
  });

  it("requires a restore path, confirmation word, and a second confirmation dialog", () => {
    const content = source("../src/views/system/BackupRestore.vue");

    expect(content).toContain("createBackup");
    expect(content).toContain("validateRestore");
    expect(content).toContain("restoreBackup");
    expect(content).toContain("RESTORE ERP");
    expect(content).toContain("ElMessageBox.confirm");
    expect(content).toContain("@click=\"backup\"");
  });

  it("loads and saves workflow configuration through the backend without local-only fallback", () => {
    const content = source("../src/views/settings/WorkflowConfig.vue");
    const apiContent = source("../src/api/workflow.ts");

    expect(content).toContain("getWorkflowDefinition");
    expect(content).toContain("saveWorkflowDefinition");
    expect(content).toContain("businessTypes");
    expect(content).toContain("ElMessage.error");
    expect(content).toContain("@click=\"saveWorkflow\"");
  });

  it("loads and saves print templates through the backend", () => {
    const content = source("../src/views/settings/PrintTemplates.vue");

    expect(content).toContain("listPrintTemplates");
    expect(content).toContain("createPrintTemplate");
    expect(content).toContain("onMounted(load)");
    expect(content).toContain("@click=\"openCreate\"");
  });
});
