<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { completeInventoryCount, createInventoryCount, deleteInventoryCount, listInventoryCounts, updateInventoryCount, type InventoryCountPayload } from "../../api/inventory";
import { useMasterOptions } from "../../composables/useMasterOptions";
import { useClientPagination } from "../../composables/useClientPagination";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const filters = reactive({ doc_no: "", material_id: "", warehouse_id: "", status: "", count_date: "" });
const filteredRows = computed(() => rows.value.filter((row) => (!filters.doc_no || String(row.doc_no || "").includes(filters.doc_no)) && (!filters.material_id || itemRows(row).some((item: any) => String(item.material_id) === filters.material_id)) && (!filters.warehouse_id || String(row.warehouse_id) === filters.warehouse_id) && (!filters.status || row.status === filters.status) && (!filters.count_date || String(row.count_date || "").startsWith(filters.count_date))));
const { pagedRows, page, pageSize, total, updatePageSize } = useClientPagination(filteredRows);
const loading = ref(false);
const saving = ref(false);
const actionLoading = ref<string | null>(null);
const errorMessage = ref("");
const dialogVisible = ref(false);
const editingId = ref<string | null>(null);
const form = reactive<InventoryCountPayload>({ warehouse_id: "", items: [{ material_id: "", actual_quantity: 0 }] });
const { warehouses, materials, loadOptions } = useMasterOptions();

const statusLabels: Record<string, string> = { draft: "草稿", completed: "已完成" };
function statusLabel(status: string) { return statusLabels[status] || status || "未知"; }
function statusTagType(status: string) { return status === "completed" ? "success" : "warning"; }
function warehouseLabel(id: unknown) { const value = String(id || ""); return warehouses.value.find((option) => option.value === value)?.label || value || "-"; }
function materialLabel(id: unknown) { const value = String(id || ""); return materials.value.find((option) => option.value === value)?.label || value || "-"; }
function itemRows(row: Row) { return Array.isArray(row.items) ? row.items : []; }
function materialNames(row: Row) { return itemRows(row).map((item) => materialLabel(item.material_id)).join("、") || "-"; }

function listFrom(response: any): Row[] { if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "库存盘点接口返回失败"); const data = response?.data?.data; return Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : []; }
async function load() { loading.value = true; errorMessage.value = ""; try { rows.value = listFrom(await listInventoryCounts()); } catch (error) { errorMessage.value = "库存盘点加载失败，请检查接口服务后重试"; } finally { loading.value = false; } }
function openCreate() { editingId.value = null; form.warehouse_id = ""; form.items = [{ material_id: "", actual_quantity: 0 }]; dialogVisible.value = true; }
function openEdit(row: Row) { const item = itemRows(row)[0]; editingId.value = String(row.id); form.warehouse_id = row.warehouse_id || ""; form.items = [{ material_id: item?.material_id || "", actual_quantity: Number(item?.actual_quantity || 0) }]; dialogVisible.value = true; }
async function save() { if (!form.warehouse_id || !form.items[0]?.material_id || form.items[0].actual_quantity < 0) { ElMessage.warning("请填写仓库、物料和有效实盘数量"); return; } saving.value = true; const editing = Boolean(editingId.value); try { const response = editing ? await updateInventoryCount(editingId.value as string, form) : await createInventoryCount(form); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success(editing ? "盘点单已修改" : "盘点单已创建"); dialogVisible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "盘点单保存失败"); } finally { saving.value = false; } }
async function remove(row: Row) { const id = String(row.id || ""); if (!id) { ElMessage.error("盘点单缺少有效 ID，无法删除"); return; } try { await ElMessageBox.confirm(`确认删除盘点单“${row.doc_no || id}”吗？删除后不可恢复。`, "删除确认", { type: "warning" }); actionLoading.value = `delete:${id}`; const response = await deleteInventoryCount(id); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("盘点单已删除"); await load(); } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "盘点单删除失败"); } finally { actionLoading.value = null; } }
async function complete(row: Row) { const id = String(row.id || ""); if (!id) { ElMessage.error("盘点单缺少有效 ID，无法操作"); return; } try { await ElMessageBox.confirm(`确认完成盘点单“${row.doc_no || id}”吗？完成后会调整库存。`, "高危操作确认", { type: "warning" }); actionLoading.value = id; const response = await completeInventoryCount(id); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("盘点单已完成"); await load(); } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "盘点单完成失败"); } finally { actionLoading.value = null; } }
onMounted(async () => { await Promise.all([load(), loadOptions(["warehouses", "materials"])]); });
</script>

<template>
  <section>
    <el-page-header content="库存盘点" />
    <el-space class="toolbar" wrap><el-input v-model="filters.doc_no" clearable placeholder="盘点单号" style="width:180px" /><el-select v-model="filters.material_id" clearable filterable placeholder="物料" style="width:200px"><el-option v-for="item in materials" :key="item.value" v-bind="item" /></el-select><el-select v-model="filters.warehouse_id" clearable filterable placeholder="仓库" style="width:180px"><el-option v-for="item in warehouses" :key="item.value" v-bind="item" /></el-select><el-select v-model="filters.status" clearable placeholder="状态" style="width:130px"><el-option label="草稿" value="draft" /><el-option label="已完成" value="completed" /></el-select><el-date-picker v-model="filters.count_date" type="date" value-format="YYYY-MM-DD" placeholder="盘点日期" /><el-button type="primary" @click="openCreate">新建盘点单</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''"><template #default><el-button link type="primary" @click="load">重新加载</el-button></template></el-alert>
    <el-table v-loading="loading" :data="pagedRows" stripe width="100%" fit :header-cell-style="{ textAlign: 'center' }" :cell-style="{ textAlign: 'center' }"><el-table-column prop="doc_no" label="盘点单号" /><el-table-column label="物料"><template #default="scope">{{ materialNames(scope.row) }}</template></el-table-column><el-table-column label="仓库"><template #default="scope">{{ warehouseLabel(scope.row.warehouse_id) }}</template></el-table-column><el-table-column label="状态"><template #default="scope"><el-tag class="status-tag" :type="statusTagType(scope.row.status)" effect="light">{{ statusLabel(scope.row.status) }}</el-tag></template></el-table-column><el-table-column prop="count_date" label="盘点日期" /><el-table-column label="操作" width="250"><template #default="scope"><el-button v-if="scope.row.status === 'draft'" link type="primary" @click="openEdit(scope.row)">修改</el-button><el-button v-if="scope.row.status === 'draft'" link type="danger" :loading="actionLoading === `delete:${scope.row.id}`" @click="remove(scope.row)">删除</el-button><el-button v-if="scope.row.status === 'draft'" link type="warning" :loading="actionLoading === scope.row.id" @click="complete(scope.row)">完成盘点</el-button></template></el-table-column></el-table>
    <ClientPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @update:page-size="updatePageSize" />
    <el-dialog v-model="dialogVisible" :title="editingId ? '修改盘点单' : '新建盘点单'" width="520px"><el-form label-width="100px"><el-form-item label="仓库" required><el-select v-model="form.warehouse_id" filterable clearable style="width: 100%"><el-option v-for="option in warehouses" :key="option.value" v-bind="option" /></el-select></el-form-item><el-form-item label="物料" required><el-select v-model="form.items[0].material_id" filterable clearable style="width: 100%"><el-option v-for="option in materials" :key="option.value" v-bind="option" /></el-select></el-form-item><el-form-item label="实盘数量" required><el-input-number v-model="form.items[0].actual_quantity" :min="0" /></el-form-item></el-form><template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template></el-dialog>
  </section>
</template>

<style scoped>
.toolbar { margin: 16px 0; }
.status-tag { border-width: 1px; }
</style>
