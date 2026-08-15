// @ts-expect-error The project does not currently include @types/node; Vitest provides this runtime module.
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

function source(relativePath: string) {
  return readFileSync(new URL(relativePath, import.meta.url), "utf8");
}

describe("平台四个独立工作台", () => {
  it("为每个菜单入口绑定唯一模块", () => {
    expect(source("../src/views/platform/GroupManagement.vue")).toContain('active-tab="group"');
    expect(source("../src/views/platform/ComplianceCenter.vue")).toContain('active-tab="compliance"');
    expect(source("../src/views/platform/LowCodeWorkbench.vue")).toContain('active-tab="low-code"');
    expect(source("../src/views/platform/MetricAssistant.vue")).toContain('active-tab="metrics"');
  });

  it("覆盖需求文档中的核心写操作与闭环动作", () => {
    const content = source("../src/views/platform/PlatformExpansion.vue");
    for (const token of [
      "createGroupMember",
      "createIntercompany",
      "createTaxCode",
      "createTaxInvoice",
      "transitionTaxInvoice",
      "createLowCode",
      "publishLowCode",
      "createMetric",
      "explainMetric",
      "scanAiAlerts",
      "resolveAiAlert",
    ]) {
      expect(content).toContain(token);
    }
  });

  it("统一设置四个工作台表格的表头和单元格居中", () => {
    const content = source("../src/views/platform/PlatformExpansion.vue");
    expect(content).toContain(":deep(.el-table th .cell)");
    expect(content).toContain(":deep(.el-table td .cell)");
    expect(content).toContain("text-align: center");
  });

  it("展示业务文案并提供成员编辑删除及低代码表单间距", () => {
    const content = source("../src/views/platform/PlatformExpansion.vue");
    for (const token of ["org_name", "membershipTypeLabels", "statusLabels", "invoiceTypeLabels", "invoiceStatusLabels", "updateGroupMember", "deleteGroupMember", "ElMessageBox.confirm"]) {
      expect(content).toContain(token);
    }
    expect(content).toContain("row-gap: 16px");
    expect(content).toContain(".form-grid .form-actions");
    expect(content).toContain("member-dialog-form");
    expect(content).toContain("margin-bottom: 12px");
    expect(content).toContain("width: 100%");
  });
});
