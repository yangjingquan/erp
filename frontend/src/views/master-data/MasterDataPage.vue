<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import type { FormInstance, FormRules } from "element-plus";
import { Download, EditPen, FolderOpened, Plus, Refresh, Search, View } from "@element-plus/icons-vue";

import {
  createMasterData,
  exportMasterData,
  getMasterDataErrorMessage,
  importMasterData,
  listMasterData,
  setMasterDataStatus,
  updateMasterData,
  type MasterResource,
} from "../../api/master-data";

export interface MasterColumn { prop: string; label: string; width?: number; labelMap?: Record<string, string>; }
export interface MasterFilter { prop: string; label: string; placeholder?: string; options?: Array<{ label: string; value: string }>; }
export interface MasterFormField { prop: string; label: string; type?: "text" | "number" | "textarea" | "select"; required?: boolean; defaultValue?: string | number; min?: number; max?: number; options?: Array<{ label: string; value: string }>; }
export interface SummaryMetric { label: string; key: "total" | "active" | "inactive"; tone?: "rust" | "green" | "amber"; }

const props = withDefaults(defineProps<{
  resource: MasterResource;
  title: string;
  columns: MasterColumn[];
  fields: MasterFormField[];
  searchPlaceholder?: string;
  summaryMetrics?: SummaryMetric[];
  filters?: MasterFilter[];
}>(), {
  searchPlaceholder: "编码、名称或关键字",
  summaryMetrics: () => [
    { label: "档案总数", key: "total", tone: "rust" },
    { label: "启用中", key: "active", tone: "green" },
    { label: "已停用", key: "inactive", tone: "amber" },
  ],
});

const rows = ref<Record<string, unknown>[]>([]);
const loading = ref(false);
const submitting = ref(false);
const importing = ref(false);
const keyword = ref("");
const filterValues = reactive<Record<string, string>>({});
const currentPage = ref(1);
const pageSize = ref(10);
const dialogVisible = ref(false);
const detailVisible = ref(false);
const selectedRow = ref<Record<string, unknown> | null>(null);
const editingId = ref("");
const totalRows = ref(0);
const summary = ref({ total: 0, active: 0, inactive: 0 });
const formRef = ref<FormInstance>();
const fileInput = ref<HTMLInputElement>();
const form = reactive<Record<string, unknown>>({});

const summaryValues = computed(() => summary.value);
const formRules = computed<FormRules>(() => Object.fromEntries(props.fields.filter((field) => field.required).map((field) => [field.prop, [{ required: true, message: `请输入${field.label}`, trigger: "blur" }]])));
const dialogTitle = computed(() => `${editingId.value ? "编辑" : "新增"}${props.title}`);

function ensureResponseSuccess(response: { data: { code: number; msg: string } }) { if (response.data.code !== 0) throw new Error(response.data.msg); }

function resetForm(source?: Record<string, unknown>) {
  Object.keys(form).forEach((key) => delete form[key]);
  props.fields.forEach((field) => {
    const value = source?.[field.prop] ?? field.defaultValue ?? (field.type === "number" ? 0 : "");
    form[field.prop] = field.type === "number" && value !== "" && value !== null ? Number(value) : value;
  });
}

async function load() {
  loading.value = true;
  try {
    const response = await listMasterData(props.resource, { keyword: keyword.value.trim() || undefined, ...filterValues, page: currentPage.value, pageSize: pageSize.value });
    ensureResponseSuccess(response);
    const data = response.data.data;
    if (Array.isArray(data)) {
      rows.value = data;
      totalRows.value = data.length;
      summary.value = { total: data.length, active: data.filter((row) => row.status !== "inactive").length, inactive: data.filter((row) => row.status === "inactive").length };
    } else {
      rows.value = Array.isArray(data?.items) ? data.items : [];
      totalRows.value = Number(data?.total ?? rows.value.length);
      summary.value = { total: totalRows.value, active: Number(data?.active ?? rows.value.filter((row) => row.status !== "inactive").length), inactive: Number(data?.inactive ?? 0) };
    }
    if (currentPage.value > 1 && rows.value.length === 0) { currentPage.value = 1; await load(); }
  } catch (error) {
    ElMessage.error(getMasterDataErrorMessage(error, `${props.title}加载失败`));
    rows.value = [];
  } finally { loading.value = false; }
}

function search() { currentPage.value = 1; void load(); }
function resetFilters() { keyword.value = ""; Object.keys(filterValues).forEach((key) => { filterValues[key] = ""; }); search(); }
function openCreate() { editingId.value = ""; resetForm(); dialogVisible.value = true; void nextTick(() => formRef.value?.clearValidate()); }
function closeCreate() { if (!submitting.value) dialogVisible.value = false; }
function openDetail(row: Record<string, unknown>) { selectedRow.value = row; detailVisible.value = true; }
function openEdit(row: Record<string, unknown>) { editingId.value = String(row.id); resetForm(row); dialogVisible.value = true; void nextTick(() => formRef.value?.clearValidate()); }

async function submitCreate() {
  if (!formRef.value) return;
  const valid = await formRef.value.validate().catch(() => false);
  if (!valid) return;
  submitting.value = true;
  try {
    const response = editingId.value ? await updateMasterData(props.resource, editingId.value, { ...form }) : await createMasterData(props.resource, { ...form });
    ensureResponseSuccess(response);
    ElMessage.success(editingId.value ? "保存成功" : "新增成功");
    dialogVisible.value = false;
    await load();
  } catch (error) { ElMessage.error(getMasterDataErrorMessage(error, "新增失败，请检查编码或名称是否重复")); }
  finally { submitting.value = false; }
}

async function toggleStatus(row: Record<string, unknown>) {
  const id = String(row.id || "");
  if (!id) return;
  const next = row.status === "inactive" ? "active" : "inactive";
  try {
    await ElMessageBox.confirm(`确认${next === "active" ? "启用" : "停用"}${props.title}“${row.name || row.code}”吗？`, "状态确认", { type: "warning" });
    const response = await setMasterDataStatus(props.resource, id, next);
    ensureResponseSuccess(response);
    ElMessage.success("状态已更新");
    await load();
  } catch (error: any) {
    if (error !== "cancel" && error !== "close") ElMessage.error(getMasterDataErrorMessage(error, "状态更新失败"));
  }
}

function chooseImportFile() { fileInput.value?.click(); }
async function handleImport(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  importing.value = true;
  try {
    const response = await importMasterData(props.resource, file);
    ensureResponseSuccess(response);
    const result = response.data.data as { created_count?: number; skipped_count?: number; errors?: Array<{ message?: string }> };
    const errors = result?.errors ?? [];
    const summary = `新增${result?.created_count ?? 0}条，跳过${result?.skipped_count ?? 0}条`;
    errors.length ? ElMessage.warning(`${summary}，${errors.length}条数据有误：${errors[0]?.message ?? "请检查导入文件"}`) : ElMessage.success(`导入完成，${summary}`);
    await load();
  } catch (error) { ElMessage.error(getMasterDataErrorMessage(error, "导入失败，请使用系统导出的Excel模板")); }
  finally { importing.value = false; input.value = ""; }
}

async function handleExport() {
  try {
    const response = await exportMasterData(props.resource);
    const url = URL.createObjectURL(new Blob([response.data]));
    const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${props.resource}.xlsx`; anchor.click(); URL.revokeObjectURL(url);
    ElMessage.success("导出成功");
  } catch (error) { ElMessage.error(getMasterDataErrorMessage(error, "导出失败")); }
}

function formatCell(row: Record<string, unknown>, column: MasterColumn) {
  if (column.prop === "status") return row.status === "inactive" ? "停用" : "启用";
  if (column.prop === "material_type") return ({ goods: "商品", raw_material: "原材料", semi_finished: "半成品", finished: "成品" } as Record<string, string>)[String(row[column.prop])] ?? row[column.prop];
  if (column.labelMap) return column.labelMap[String(row[column.prop])] ?? row[column.prop];
  const value = row[column.prop];
  return value === null || value === undefined || value === "" ? "-" : String(value);
}
function isActiveStatus(row: Record<string, unknown>, column: MasterColumn) { return column.prop === "status" && row.status !== "inactive"; }
function handlePageSizeChange() { currentPage.value = 1; void load(); }

onMounted(load);
</script>

<template>
  <section class="master-page">
    <div class="page-heading"><div><div class="breadcrumb">基础资料 <span>/</span> {{ props.title }}</div><h1>{{ props.title }}</h1></div><div class="page-note">最后更新：实时数据</div></div>

    <div class="summary-grid">
      <el-card v-for="metric in props.summaryMetrics" :key="metric.label" class="summary-card" shadow="never">
        <div class="summary-label"><span>{{ metric.label }}</span><span :class="['summary-dot', metric.tone || 'rust']" /></div>
        <strong>{{ summaryValues[metric.key] }}</strong>
        <small>{{ metric.key === 'total' ? '当前组织范围' : '档案状态' }}</small>
      </el-card>
    </div>

    <el-card class="toolbar-card" shadow="never">
      <div class="toolbar">
        <div class="search-row"><el-input v-model="keyword" :placeholder="props.searchPlaceholder" clearable class="search-input" @keyup.enter="search" @clear="search"><template #prefix><el-icon><Search /></el-icon></template></el-input><template v-if="props.filters?.length"><el-input v-for="filter in props.filters.filter((item) => !item.options)" :key="filter.prop" v-model="filterValues[filter.prop]" clearable :placeholder="filter.placeholder || filter.label" /><el-select v-for="filter in props.filters.filter((item) => item.options)" :key="filter.prop" v-model="filterValues[filter.prop]" clearable :placeholder="filter.placeholder || filter.label"><el-option v-for="option in filter.options" :key="option.value" v-bind="option" /></el-select></template><el-button class="search-button" @click="search"><el-icon><Search /></el-icon>查询</el-button></div>
        <div class="toolbar-actions"><el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新增{{ props.title.replace('档案', '') }}</el-button><el-button :loading="importing" @click="chooseImportFile"><el-icon><FolderOpened /></el-icon>导入</el-button><el-button @click="handleExport"><el-icon><Download /></el-icon>导出</el-button><el-button :loading="loading" @click="load"><el-icon><Refresh /></el-icon>刷新</el-button><input ref="fileInput" type="file" accept=".xlsx,.xls" hidden @change="handleImport" /></div>
      </div>
    </el-card>

    <el-card class="table-card" shadow="never">
      <div class="table-caption"><div><strong>{{ props.title }}</strong><span>共 {{ totalRows }} 条记录</span></div><span class="caption-tip">支持编码、名称和关键字模糊搜索</span></div>
      <el-table v-loading="loading" :data="rows" row-key="id" class="master-table" width="100%" fit>
        <el-table-column v-for="column in props.columns" :key="column.prop" :prop="column.prop" :label="column.label" :width="column.width" min-width="100" show-overflow-tooltip>
          <template #default="{ row }"><el-tag v-if="isActiveStatus(row, column)" class="status-tag" type="success">{{ formatCell(row, column) }}</el-tag><el-tag v-else-if="column.prop === 'status'" class="status-tag" type="info">{{ formatCell(row, column) }}</el-tag><span v-else>{{ formatCell(row, column) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="220" class-name="operation-column">
          <template #default="{ row }"><el-button link class="row-action" @click="openDetail(row)"><el-icon><View /></el-icon>查看</el-button><el-button link class="row-action" @click="openEdit(row)"><el-icon><EditPen /></el-icon>编辑</el-button><el-button link class="row-action" @click="toggleStatus(row)">{{ row.status === "inactive" ? "启用" : "停用" }}</el-button></template>
        </el-table-column>
        <template #empty><el-empty description="暂无数据，试试调整筛选条件" /></template>
      </el-table>
      <div v-if="totalRows > 0" class="pagination-wrap"><span>显示 {{ (currentPage - 1) * pageSize + 1 }} - {{ Math.min(currentPage * pageSize, totalRows) }} / 共 {{ totalRows }} 条</span><el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :page-sizes="[10, 20, 50]" layout="sizes, prev, pager, next" :total="totalRows" @size-change="handlePageSizeChange" @current-change="load" /></div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="620px" @close="closeCreate">
      <el-form ref="formRef" :model="form" :rules="formRules" label-position="top" class="master-form">
        <el-form-item v-for="field in props.fields" :key="field.prop" :label="field.label" :prop="field.prop"><el-select v-if="field.type === 'select'" v-model="form[field.prop]" class="full-width"><el-option v-for="option in field.options ?? []" :key="option.value" :label="option.label" :value="option.value" /></el-select><el-input-number v-else-if="field.type === 'number'" v-model="form[field.prop] as number" :min="field.min ?? 0" :max="field.max" :controls="false" class="full-width" /><el-input v-else v-model="form[field.prop] as string" :type="field.type === 'textarea' ? 'textarea' : 'text'" :rows="field.type === 'textarea' ? 3 : undefined" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="closeCreate">取消</el-button><el-button type="primary" :loading="submitting" @click="submitCreate">保存{{ props.title.replace('档案', '') }}</el-button></template>
    </el-dialog>

    <el-drawer v-model="detailVisible" :title="`${props.title}详情`" size="430px"><div v-if="selectedRow" class="detail-panel"><div class="detail-intro"><span class="detail-code">{{ selectedRow.code || '-' }}</span><el-tag v-if="selectedRow.status !== 'inactive'" type="success">启用</el-tag><el-tag v-else type="info">停用</el-tag></div><div v-for="field in props.fields" :key="field.prop" class="detail-row"><span>{{ field.label }}</span><strong>{{ selectedRow[field.prop] ?? '-' }}</strong></div></div></el-drawer>
  </section>
</template>

<style scoped>
.master-page { min-width: 0; }
.page-heading { display: flex; align-items: end; justify-content: space-between; margin-bottom: 18px; }
.breadcrumb { color: var(--erp-muted-text); font-size: 11px; }
.breadcrumb span { margin: 0 5px; color: var(--erp-border); }
h1 { margin: 6px 0 0; color: var(--erp-text); font-size: 25px; line-height: 1.2; }
.page-note { color: var(--erp-subtle-text); font-size: 11px; }
.summary-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 15px; margin-bottom: 15px; }
.summary-card { min-height: 108px; padding: 16px 17px; }
.summary-card :deep(.el-card__body) { padding: 0; }
.summary-label { display: flex; align-items: center; justify-content: space-between; color: var(--erp-muted-text); font-size: 12px; }
.summary-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--erp-primary); }
.summary-dot.green { background: var(--erp-green); }.summary-dot.amber { background: var(--erp-amber); }
.summary-card strong { display: block; margin: 14px 0 5px; color: var(--erp-text); font-size: 25px; line-height: 1; }
.summary-card small { color: var(--erp-subtle-text); font-size: 11px; }
.toolbar-card, .table-card { margin-bottom: 15px; }
.toolbar-card :deep(.el-card__body) { padding: 16px 17px; }
.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 15px; flex-wrap: wrap; }
.search-row { display: flex; flex: 1; min-width: 290px; max-width: 760px; gap: 8px; }
.search-row :deep(.el-select) { width: 150px; }
.search-input { min-width: 0; flex: 1; }.search-input :deep(.el-input__wrapper) { border-radius: 8px; }
.search-button { color: var(--erp-primary-dark); border-color: var(--erp-border); background: var(--erp-panel-bg); }
.toolbar-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.table-card :deep(.el-card__body) { padding: 0; }
.table-caption { display: flex; align-items: center; justify-content: space-between; padding: 16px 17px; border-bottom: 1px solid var(--erp-border-soft); }
.table-caption > div { display: flex; align-items: center; gap: 12px; }.table-caption strong { color: #493d35; font-size: 15px; }.table-caption span { color: var(--erp-subtle-text); font-size: 11px; }.caption-tip { color: var(--erp-subtle-text); }
.master-table :deep(.el-table__header th) { background: var(--erp-panel-soft); }.master-table :deep(.el-table__cell) { padding: 13px 8px; }.master-table :deep(.el-table__row) { background: var(--erp-panel-bg); }
.status-tag { border: 0; border-radius: 999px; }.status-tag.el-tag--success { background: var(--erp-green-bg); color: var(--erp-green); }.status-tag.el-tag--info { background: #f2e6dc; color: #a45b40; }
.operation-column :deep(.cell), .row-action { white-space: nowrap; }.row-action { color: var(--erp-primary-dark); }.row-action + .row-action { margin-left: 4px; }.row-action :deep(.el-icon) { margin-right: 2px; }
.pagination-wrap { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 17px; border-top: 1px solid var(--erp-border-soft); color: var(--erp-muted-text); font-size: 11px; }.pagination-wrap :deep(.el-pagination) { padding: 0; }
.master-form { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: 18px; }.master-form :deep(.el-form-item:last-child) { grid-column: 1 / -1; }.full-width { width: 100%; }
.detail-panel { padding: 4px 2px; }.detail-intro { display: flex; align-items: center; justify-content: space-between; padding-bottom: 18px; border-bottom: 1px solid var(--erp-border-soft); }.detail-code { color: var(--erp-primary-dark); font-size: 18px; font-weight: 700; }.detail-row { display: flex; justify-content: space-between; gap: 20px; padding: 15px 0; border-bottom: 1px solid var(--erp-border-soft); }.detail-row span { color: var(--erp-muted-text); }.detail-row strong { max-width: 240px; color: var(--erp-text); font-weight: 600; text-align: right; word-break: break-word; }
@media (max-width: 760px) { .summary-grid { grid-template-columns: 1fr; }.page-heading { align-items: flex-start; flex-direction: column; gap: 8px; }.toolbar-actions { width: 100%; }.pagination-wrap { align-items: flex-start; flex-direction: column; }.master-form { grid-template-columns: 1fr; }.master-form :deep(.el-form-item:last-child) { grid-column: auto; } }
</style>
