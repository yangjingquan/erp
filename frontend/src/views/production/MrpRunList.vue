<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { confirmMrpResult, createMps, listMps, runMrp } from "../../api/production";
import { useMasterOptions } from "../../composables/useMasterOptions";
import { useClientPagination } from "../../composables/useClientPagination";
import { localDateString } from "../../utils/time";

type Row = Record<string, any>;
const rows = ref<Row[]>([]); const loading = ref(false); const saving = ref(false); const actionLoading = ref<string | null>(null); const dialogVisible = ref(false); const resultRows = ref<Row[]>([]); const runVisible = ref(false);
const { pagedRows, page, pageSize, total, updatePageSize } = useClientPagination(rows);
const form = reactive({ material_id: "", warehouse_id: "", plan_date: localDateString(), plan_quantity: 1 });
const { materials, warehouses, loadOptions } = useMasterOptions();
const statusLabels: Record<string, string> = { draft: "草稿", planned: "已计划" };
const resultStatusLabels: Record<string, string> = { pending: "待确认", confirmed: "已确认" };
function statusLabel(status: string, labels = statusLabels) { return labels[status] || status || "未知"; }
function statusTagType(status: string) { return ({ draft: "info", planned: "success" } as Record<string, string>)[status] || "info"; }
function resultStatusTagType(status: string) { return ({ pending: "warning", confirmed: "success" } as Record<string, string>)[status] || "info"; }
function materialLabel(materialId: unknown) { const value = String(materialId || ""); return materials.value.find((option) => option.value === value)?.label || value || "-"; }
function listFrom(response: any) { if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "MPS 接口返回失败"); return Array.isArray(response?.data?.data) ? response.data.data : []; }
async function load() { loading.value = true; try { rows.value = listFrom(await listMps()); } catch { ElMessage.error("MPS 列表加载失败"); } finally { loading.value = false; } }
function openCreate() { form.material_id = ""; form.warehouse_id = ""; form.plan_date = localDateString(); form.plan_quantity = 1; dialogVisible.value = true; }
async function save() { if (!form.material_id || !form.plan_date || form.plan_quantity <= 0) { ElMessage.warning("请填写计划物料、日期和大于 0 的计划数量"); return; } saving.value = true; try { const response = await createMps({ ...form, warehouse_id: form.warehouse_id || null }); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("MPS 计划已创建"); dialogVisible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "MPS 创建失败"); } finally { saving.value = false; } }
async function execute(row: Row) { const id = String(row.id || ""); if (!id) return; try { await ElMessageBox.confirm(`确认对计划“${row.doc_no || id}”运行 MRP 吗？`, "操作确认", { type: "warning" }); actionLoading.value = id; const response = await runMrp(id); if (response.data.code !== 0) throw new Error(response.data.msg); resultRows.value = response.data.data?.results || []; runVisible.value = true; ElMessage.success("MRP 运算完成"); } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "MRP 运算失败"); } finally { actionLoading.value = null; } }
async function confirmResult(row: Row) { const id = String(row.id || ""); if (!id) return; try { await ElMessageBox.confirm("确认该净需求并生成采购申请吗？", "操作确认", { type: "warning" }); actionLoading.value = id; const response = await confirmMrpResult(id); if (response.data.code !== 0) throw new Error(response.data.msg); row.status = "confirmed"; row.source_document_ids = response.data.data?.source_document_ids || null; ElMessage.success("MRP 结果已确认，采购申请已生成"); } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "MRP 结果确认失败"); } finally { actionLoading.value = null; } }
onMounted(async () => { await Promise.all([load(), loadOptions(["materials", "warehouses"])]); });
</script>

<template>
  <section class="page-stack"><el-page-header content="MRP 运算" /><el-space><el-button type="primary" @click="openCreate">新建 MPS 计划</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space><el-alert title="运行 MRP 前请先在 BOM 管理中完成提交和审核。" type="info" show-icon />
    <el-table v-loading="loading" :data="pagedRows" stripe width="100%" fit :header-cell-style="{ textAlign: 'center' }" :cell-style="{ textAlign: 'center' }"><el-table-column prop="doc_no" label="计划单号" width="190" class-name="nowrap-column" /><el-table-column label="计划物料" min-width="180"><template #default="scope">{{ materialLabel(scope.row.material_id) }}</template></el-table-column><el-table-column prop="plan_date" label="计划日期" width="130" /><el-table-column prop="plan_quantity" label="计划数量" width="130" /><el-table-column label="状态" width="100"><template #default="scope"><el-tag class="status-tag" :type="statusTagType(scope.row.status)" effect="light">{{ statusLabel(scope.row.status) }}</el-tag></template></el-table-column><el-table-column label="操作" width="130"><template #default="scope"><el-button v-if="scope.row.status === 'draft'" link type="primary" :loading="actionLoading === scope.row.id" @click="execute(scope.row)">运行 MRP</el-button></template></el-table-column><template #empty><el-empty description="暂无 MPS 计划" /></template></el-table>
    <ClientPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @update:page-size="updatePageSize" />
    <el-dialog v-model="dialogVisible" title="新建 MPS 计划" width="520px"><el-form label-width="100px"><el-form-item label="计划物料" required><el-select v-model="form.material_id" filterable clearable style="width: 100%"><el-option v-for="option in materials" :key="option.value" v-bind="option" /></el-select></el-form-item><el-form-item label="计划仓库"><el-select v-model="form.warehouse_id" filterable clearable style="width: 100%"><el-option v-for="option in warehouses" :key="option.value" v-bind="option" /></el-select></el-form-item><el-form-item label="计划日期" required><el-date-picker v-model="form.plan_date" type="date" value-format="YYYY-MM-DD" /></el-form-item><el-form-item label="计划数量" required><el-input-number v-model="form.plan_quantity" :min="0.000001" :precision="6" /></el-form-item></el-form><template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template></el-dialog>
    <el-dialog v-model="runVisible" title="MRP 运算结果" width="820px"><el-table :data="resultRows" stripe :header-cell-style="{ textAlign: 'center' }" :cell-style="{ textAlign: 'center' }"><el-table-column label="物料" min-width="180"><template #default="scope">{{ materialLabel(scope.row.material_id) }}</template></el-table-column><el-table-column prop="gross_requirement" label="毛需求" /><el-table-column prop="available_stock" label="可用库存" /><el-table-column prop="open_supply_quantity" label="在途供应" /><el-table-column prop="net_requirement" label="净需求" /><el-table-column label="状态"><template #default="scope"><el-tag class="status-tag" :type="resultStatusTagType(scope.row.status)" effect="light">{{ statusLabel(scope.row.status, resultStatusLabels) }}</el-tag></template></el-table-column><el-table-column label="操作" width="110"><template #default="scope"><el-button v-if="scope.row.status === 'pending' && Number(scope.row.net_requirement) > 0" link type="primary" :loading="actionLoading === scope.row.id" @click="confirmResult(scope.row)">确认</el-button></template></el-table-column></el-table><template #footer><el-button @click="runVisible = false">关闭</el-button></template></el-dialog>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.nowrap-column :deep(.cell) { white-space: nowrap; }
.status-tag { border-width: 1px; }
.status-tag.el-tag--success { background: var(--erp-green-bg); border-color: var(--erp-green); color: var(--erp-green); }
.status-tag.el-tag--warning { background: var(--erp-amber-bg); border-color: var(--erp-amber); color: var(--erp-amber); }
.status-tag.el-tag--info { background: var(--erp-panel-soft); border-color: var(--erp-border); color: var(--erp-muted-text); }
</style>
