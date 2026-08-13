<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";

import DocumentListWorkbench from "../components/DocumentListWorkbench.vue";
import DocumentWorkbench from "../components/DocumentWorkbench.vue";
import StatusTag from "../components/StatusTag.vue";
import {
  createSavedDocumentView, deleteSavedDocumentView, downloadDocumentExport, listDocumentExports,
  listDocuments, listSavedDocumentViews, runBulkDocumentCommand, runDocumentCommand, startDocumentExport,
} from "../api/documents";
import { formatLocalDateTime } from "../utils/time";

type Row = Record<string, any>;
const route = useRoute(); const router = useRouter();
const rows = ref<Row[]>([]); const views = ref<Row[]>([]); const exports = ref<Row[]>([]); const selectedRows = ref<Row[]>([]);
const summary = ref<Row>({}); const total = ref(0); const page = ref(Number(route.query.page || 1)); const pageSize = ref(20);
const businessType = ref(String(route.query.business_type || "")); const keyword = ref(String(route.query.keyword || "")); const status = ref(String(route.query.status || ""));
const dateRange = ref<string[]>([String(route.query.date_from || ""), String(route.query.date_to || "")].filter(Boolean));
const loading = ref(false); const actionLoading = ref(""); const errorMessage = ref(""); const detailVisible = ref(false); const selected = ref<Row | null>(null); const exportDrawer = ref(false);
let exportTimer: ReturnType<typeof setInterval> | null = null;
const typeOptions = [
  ["sales_order", "销售订单"], ["sales_delivery", "销售出库"], ["purchase_order", "采购订单"], ["purchase_receipt", "采购入库"],
  ["inv_transfer", "库存调拨"], ["inv_count", "库存盘点"], ["mfg_work_order", "生产工单"], ["qa_inspection", "质量检验"],
  ["sales_receivable", "应收账款"], ["purchase_payable", "应付账款"], ["fin_voucher", "会计凭证"],
] as const;
const title = computed(() => typeOptions.find(([value]) => value === businessType.value)?.[1] || "业务单据中心");
const bulkActions = computed(() => {
  if (!selectedRows.value.length || !businessType.value) return [];
  const actionMaps: Map<string, Row>[] = selectedRows.value.map((row) => new Map<string, Row>((row.available_actions || []).map((item: Row) => [String(item.command), item])));
  return [...actionMaps[0].values()].filter((item) => actionMaps.every((map) => map.has(String(item.command))));
});

function unwrap(response: any): any { if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "统一单据接口返回失败"); return response.data.data; }
function currentFilters() { return { status: status.value || undefined, keyword: keyword.value.trim() || undefined, date_from: dateRange.value[0] || undefined, date_to: dateRange.value[1] || undefined, sort: "-updated_at" }; }
async function syncQuery() { await router.replace({ query: { business_type: businessType.value || undefined, ...currentFilters(), page: page.value > 1 ? page.value : undefined } }); }
async function load() { loading.value = true; errorMessage.value = ""; try { const data = unwrap(await listDocuments({ business_type: businessType.value || undefined, ...currentFilters(), page: page.value, page_size: pageSize.value })); rows.value = data.items || []; total.value = Number(data.total || 0); summary.value = data.summary || {}; selectedRows.value = []; await syncQuery(); } catch (error) { errorMessage.value = error instanceof Error ? error.message : "业务单据加载失败"; } finally { loading.value = false; } }
async function loadViews() { try { views.value = unwrap(await listSavedDocumentViews()) || []; } catch { views.value = []; } }
function search() { page.value = 1; void load(); }
function reset() { businessType.value = ""; keyword.value = ""; status.value = ""; dateRange.value = []; page.value = 1; void load(); }
function changeBusinessType() { status.value = ""; search(); }
function openDetail(row: Row) { selected.value = row; detailVisible.value = true; }
async function runAction(row: Row, action: Row) { try { await ElMessageBox.confirm(`确认${action.label}“${row.doc_no}”吗？`, "业务操作确认", { type: "warning" }); actionLoading.value = String(row.business_id); unwrap(await runDocumentCommand(row.business_type, row.business_id, action.command)); ElMessage.success(`${action.label}成功`); await load(); } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "业务操作失败"); } finally { actionLoading.value = ""; } }
async function runBulk(action: Row) { if (!businessType.value || !selectedRows.value.length) return; try { await ElMessageBox.confirm(`确认对 ${selectedRows.value.length} 张单据执行“${action.label}”吗？`, "批量业务操作", { type: "warning" }); const result = unwrap(await runBulkDocumentCommand(businessType.value, selectedRows.value.map((row) => String(row.business_id)), action.command)); if (result.failed) ElMessage.warning(`批量操作完成：成功 ${result.succeeded}，失败 ${result.failed}`); else ElMessage.success(`已成功处理 ${result.succeeded} 张单据`); await load(); } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "批量操作失败"); } }
async function saveView() { try { const result = await ElMessageBox.prompt("请输入视图名称", "保存当前视图", { inputPattern: /\S+/, inputErrorMessage: "视图名称不能为空" }); unwrap(await createSavedDocumentView({ name: result.value.trim(), business_type: businessType.value || undefined, filters: currentFilters() })); ElMessage.success("视图已保存"); await loadViews(); } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "保存视图失败"); } }
function applyView(view: Row) { businessType.value = view.business_type || ""; status.value = view.filters?.status || ""; keyword.value = view.filters?.keyword || ""; dateRange.value = [view.filters?.date_from, view.filters?.date_to].filter(Boolean); search(); }
async function removeView(view: Row) { try { unwrap(await deleteSavedDocumentView(String(view.id))); ElMessage.success("视图已删除"); await loadViews(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "删除视图失败"); } }
async function startExport() { try { unwrap(await startDocumentExport({ business_type: businessType.value || undefined, filters: currentFilters() })); ElMessage.success("导出任务已提交"); exportDrawer.value = true; await loadExports(); startExportPolling(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "提交导出失败"); } }
async function loadExports() { try { exports.value = unwrap(await listDocumentExports()) || []; if (!exports.value.some((item) => ["pending", "processing"].includes(item.status))) stopExportPolling(); } catch { /* drawer retains the latest valid snapshot */ } }
function startExportPolling() { if (!exportTimer) exportTimer = setInterval(loadExports, 2000); }
function stopExportPolling() { if (exportTimer) clearInterval(exportTimer); exportTimer = null; }
function exportStatusLabel(value: string) { return ({ pending: "等待中", processing: "导出中", completed: "已完成", failed: "失败" } as Record<string, string>)[value] || value; }
async function downloadExport(row: Row) { try { const response = await downloadDocumentExport(String(row.id)); const url = URL.createObjectURL(response.data); const anchor = document.createElement("a"); anchor.href = url; anchor.download = row.file_name || "ERP业务单据.csv"; anchor.click(); URL.revokeObjectURL(url); } catch { ElMessage.error("导出文件下载失败"); } }
onMounted(async () => { await Promise.all([load(), loadViews()]); });
onBeforeUnmount(stopExportPolling);
</script>

<template>
  <DocumentListWorkbench v-model:keyword="keyword" v-model:status="status" v-model:date-range="dateRange" v-model:page="page" v-model:page-size="pageSize" :title="title" :summary="summary" :total="total" :loading="loading" @search="search" @reset="reset" @refresh="load" @update:page="load" @update:page-size="search">
    <template #actions><el-space wrap><el-select v-model="businessType" clearable placeholder="全部业务类型" style="width: 180px" @change="changeBusinessType"><el-option v-for="item in typeOptions" :key="item[0]" :label="item[1]" :value="item[0]" /></el-select><el-dropdown v-if="views.length" @command="applyView"><el-button>我的视图</el-button><template #dropdown><el-dropdown-menu><el-dropdown-item v-for="view in views" :key="view.id" :command="view"><span>{{ view.name }}</span><el-button v-if="view.is_owner" link type="danger" @click.stop="removeView(view)">删除</el-button></el-dropdown-item></el-dropdown-menu></template></el-dropdown><el-button @click="saveView">保存当前视图</el-button><el-button @click="startExport">后台导出</el-button><el-button @click="exportDrawer = true; loadExports()">导出任务</el-button></el-space></template>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''" />
    <div v-if="selectedRows.length" class="bulk-toolbar"><span>已选 {{ selectedRows.length }} 项</span><el-button v-for="action in bulkActions" :key="action.command" :type="action.type" @click="runBulk(action)">批量{{ action.label }}</el-button><span v-if="!bulkActions.length">所选单据没有共同的可执行操作</span></div>
    <el-table v-loading="loading" :data="rows" stripe @selection-change="selectedRows = $event"><el-table-column type="selection" width="46" /><el-table-column label="单据编号" min-width="170"><template #default="scope"><el-button link type="primary" @click="openDetail(scope.row)">{{ scope.row.doc_no }}</el-button></template></el-table-column><el-table-column prop="title" label="业务单据" min-width="220" show-overflow-tooltip /><el-table-column prop="party_name" label="业务对象" min-width="180" show-overflow-tooltip /><el-table-column label="状态" width="110"><template #default="scope"><StatusTag :status="scope.row.status" :label="scope.row.status_label" /></template></el-table-column><el-table-column prop="document_date" label="单据日期" width="120" /><el-table-column prop="amount" label="金额" width="130" align="right" /><el-table-column label="更新时间" width="170"><template #default="scope">{{ formatLocalDateTime(scope.row.updated_at) }}</template></el-table-column><el-table-column label="操作" width="260" fixed="right"><template #default="scope"><el-button link @click="openDetail(scope.row)">详情</el-button><el-button v-for="action in scope.row.available_actions" :key="action.command" link :type="action.type" :loading="actionLoading === scope.row.business_id" @click="runAction(scope.row, action)">{{ action.label }}</el-button></template></el-table-column><template #empty><el-empty description="当前筛选范围内暂无业务单据" /></template></el-table>
    <DocumentWorkbench v-if="selected" v-model:visible="detailVisible" :business-type="selected.business_type" :business-id="String(selected.business_id)" @changed="load" />
    <el-drawer v-model="exportDrawer" title="后台导出任务" size="520px" @open="loadExports"><el-table :data="exports"><el-table-column prop="file_name" label="文件" min-width="180" /><el-table-column prop="row_count" label="行数" width="80" /><el-table-column label="状态" width="100"><template #default="scope">{{ exportStatusLabel(scope.row.status) }}</template></el-table-column><el-table-column label="操作" width="90"><template #default="scope"><el-button v-if="scope.row.status === 'completed'" link type="primary" @click="downloadExport(scope.row)">下载</el-button></template></el-table-column><template #empty><el-empty description="暂无导出任务" /></template></el-table></el-drawer>
  </DocumentListWorkbench>
</template>

<style scoped>.bulk-toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; padding: 10px 12px; border-radius: 8px; background: var(--erp-panel-soft); color: var(--erp-muted-text); }</style>
