<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { createReportDefinition, exportReportRun, getReportRun, listReportDefinitions, listReportRuns, runReport } from "../../api/analytics";
import { localMonthString } from "../../utils/time";
import { useClientPagination } from "../../composables/useClientPagination";
import { labelOf, reportTypeLabels, statusLabel, tagTypeOf } from "../../utils/labels";

type Row = Record<string, any>;
function reportTypeLabel(value: unknown) { const key = String(value || ""); return reportTypeLabels[key] || (key.startsWith("Biz Report Run") ? "经营管理 KPI" : key || "-"); }
function normalizeRun(row: Row) { const key = String(row.report_key || ""); return key.startsWith("Biz Report Run") ? { ...row, report_key: "management_kpi", report_type_label: reportTypeLabel(key) } : row; }
const definitions = ref<Row[]>([]);
const runs = ref<Row[]>([]);
const loading = ref(false);
const saving = ref(false);
const selectedRun = ref<Row | null>(null);
const dialogVisible = ref(false);
const period = ref(localMonthString());
const form = reactive({ report_key: "management_kpi", name: "", description: "" });
const { pagedRows: definitionRows, page: definitionPage, pageSize: definitionPageSize, total: definitionTotal, updatePageSize: updateDefinitionPageSize } = useClientPagination(definitions);
const { pagedRows: runListRows, page: runListPage, pageSize: runListPageSize, total: runListTotal, updatePageSize: updateRunListPageSize } = useClientPagination(runs);

const runRows = computed(() => {
  const result = selectedRun.value?.result || {};
  const rows: Array<{ section: string; metric: string; value: string }> = [];
  Object.entries(result).forEach(([section, value]) => {
    if (value && typeof value === "object" && !Array.isArray(value)) {
      Object.entries(value as Row).forEach(([metric, item]) => rows.push({ section: labelOf({ sales: "销售", inventory: "库存", receivables: "应收", production: "生产", quality: "质量", crm: "CRM", finance: "财务", project: "项目" }, section), metric: labelOf({ fulfillment_rate: "履约率", inventory_value: "库存价值", overdue_receivable: "逾期应收", production_completion_rate: "生产完成率", failed_inspections: "不合格检验" }, metric), value: typeof item === "object" ? JSON.stringify(item) : String(item ?? "") }));
    } else rows.push({ section: "", metric: labelOf({ fulfillment_rate: "履约率", inventory_value: "库存价值", overdue_receivable: "逾期应收", production_completion_rate: "生产完成率", failed_inspections: "不合格检验" }, section), value: String(value ?? "") });
  });
  return rows;
});

function unwrap(response: any) {
  if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "接口返回失败");
  return response.data.data;
}
async function load() {
  loading.value = true;
  try {
    const [definitionsResponse, runsResponse] = await Promise.all([listReportDefinitions(), listReportRuns()]);
    definitions.value = unwrap(definitionsResponse) || [];
    runs.value = unwrap(runsResponse) || [];
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "报表中心加载失败"); }
  finally { loading.value = false; }
}
function openCreate() { Object.assign(form, { report_key: "management_kpi", name: "", description: "" }); dialogVisible.value = true; }
async function saveDefinition() {
  if (!form.name.trim()) { ElMessage.warning("请填写报表名称"); return; }
  saving.value = true;
  try { unwrap(await createReportDefinition({ ...form, name: form.name.trim(), description: form.description.trim(), parameters: { period: "YYYY-MM" } })); dialogVisible.value = false; ElMessage.success("报表定义已保存"); await load(); }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : "报表定义保存失败"); }
  finally { saving.value = false; }
}
async function execute(definition: Row) {
  saving.value = true;
  try { const result = unwrap(await runReport(String(definition.id), { period: period.value })); selectedRun.value = normalizeRun(result); ElMessage.success("报表已生成"); await load(); }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : "报表执行失败"); }
  finally { saving.value = false; }
}
async function exportRun(row: Row) {
  try {
    const response = await exportReportRun(String(row.id));
    const blob = new Blob([response.data], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob); const link = document.createElement("a");
    link.href = url; link.download = row.report_key + "-" + String(row.id).slice(0, 8) + ".csv"; link.click(); URL.revokeObjectURL(url);
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "报表导出失败"); }
}
async function showRun(row: Row) {
  try { selectedRun.value = normalizeRun(unwrap(await getReportRun(String(row.id)))); }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : "报表运行记录加载失败"); }
}
async function explainBuiltin() { await ElMessageBox.alert("内置报表用于保证指标口径一致，当前版本支持修改展示名称，不支持删除。", "说明", { type: "info" }); }
onMounted(load);
</script>

<template>
  <section class="page-stack">
    <header class="page-heading"><div><small>BI REPORTING FOUNDATION</small><h1>BI 报表中心</h1><p>统一指标口径，按当前组织生成经营与运营报表，并保留可追溯运行记录。</p></div><el-space><el-date-picker v-model="period" type="month" value-format="YYYY-MM" /><el-button type="primary" @click="dialogVisible = true">配置报表名称</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space></header>
    <el-card v-loading="loading" shadow="never"><el-table :data="definitionRows" stripe><el-table-column prop="name" label="报表名称" min-width="180" /><el-table-column label="报表类型" width="180"><template #default="scope">{{ reportTypeLabels[scope.row.report_key] || scope.row.report_key }}</template></el-table-column><el-table-column prop="description" label="说明" min-width="320" /><el-table-column label="来源" width="100"><template #default="scope">{{ scope.row.is_builtin ? "系统内置" : "组织配置" }}</template></el-table-column><el-table-column label="操作" width="120"><template #default="scope"><el-button link type="primary" :loading="saving" @click="execute(scope.row)">运行</el-button></template></el-table-column><template #empty><el-empty description="暂无报表定义" /></template></el-table><ClientPagination v-model:page="definitionPage" v-model:page-size="definitionPageSize" :total="definitionTotal" @update:page-size="updateDefinitionPageSize" /></el-card>
    <el-card shadow="never"><template #header><div class="card-header"><span>运行记录</span><el-tag type="info">按当前组织隔离</el-tag></div></template><el-table :data="runListRows" stripe><el-table-column label="报表类型" width="180"><template #default="scope">{{ reportTypeLabels[scope.row.report_key] || scope.row.report_key }}</template></el-table-column><el-table-column label="期间" width="120"><template #default="scope">{{ scope.row.parameters?.period || "-" }}</template></el-table-column><el-table-column label="状态" width="100"><template #default="scope"><el-tag :type="tagTypeOf(scope.row.status)" effect="light">{{ statusLabel(scope.row.status) }}</el-tag></template></el-table-column><el-table-column prop="created_at" label="生成时间" min-width="220" /><el-table-column label="操作" width="180"><template #default="scope"><el-button link type="primary" @click="showRun(scope.row)">查看</el-button><el-button link type="success" @click="exportRun(scope.row)">导出 CSV</el-button></template></el-table-column><template #empty><el-empty description="暂无运行记录" /></template></el-table><ClientPagination v-model:page="runListPage" v-model:page-size="runListPageSize" :total="runListTotal" @update:page-size="updateRunListPageSize" /></el-card>
    <el-drawer :model-value="Boolean(selectedRun)" title="报表结果" size="620px" @update:model-value="(visible: boolean) => { if (!visible) selectedRun = null }"><el-descriptions v-if="selectedRun" :column="2" border><el-descriptions-item label="类型">{{ reportTypeLabels[selectedRun.report_key] || selectedRun.report_key }}</el-descriptions-item><el-descriptions-item label="期间">{{ selectedRun.parameters?.period || "-" }}</el-descriptions-item></el-descriptions><el-table v-if="selectedRun" :data="runRows" stripe class="result-table"><el-table-column prop="section" label="分组" width="130" /><el-table-column prop="metric" label="指标" width="220" /><el-table-column prop="value" label="值" min-width="180" /></el-table></el-drawer>
    <el-dialog v-model="dialogVisible" title="配置报表名称" width="520px"><el-form label-width="100px"><el-form-item label="报表类型"><el-select v-model="form.report_key"><el-option label="经营管理 KPI" value="management_kpi" /><el-option label="运营模块 KPI" value="operations_kpi" /></el-select></el-form-item><el-form-item label="展示名称" required><el-input v-model="form.name" placeholder="例如：月度经营复盘" /></el-form-item><el-form-item label="说明"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item></el-form><template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveDefinition">保存</el-button></template></el-dialog>
    <el-button class="builtin-help" text @click="explainBuiltin">内置报表说明</el-button>
  </section>
</template>

<style scoped>.page-stack { display:flex; flex-direction:column; gap:16px; }.page-heading { display:flex; justify-content:space-between; align-items:flex-end; }.page-heading small { color:var(--erp-muted-text); letter-spacing:.08em; }.page-heading h1 { margin:4px 0; }.page-heading p { margin:0; color:var(--erp-muted-text); }.card-header { display:flex; justify-content:space-between; align-items:center; }.result-table { margin-top:16px; }.builtin-help { align-self:flex-start; }</style>
