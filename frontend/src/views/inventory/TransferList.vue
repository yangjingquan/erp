<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { approveInventoryTransfer, completeInventoryTransfer, createInventoryTransfer, listInventoryTransfers, type InventoryTransferPayload } from "../../api/inventory";
import { useMasterOptions } from "../../composables/useMasterOptions";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const loading = ref(false);
const saving = ref(false);
const actionLoading = ref<string | null>(null);
const errorMessage = ref("");
const dialogVisible = ref(false);
const form = reactive<InventoryTransferPayload>({ from_warehouse_id: "", to_warehouse_id: "", items: [{ material_id: "", quantity: 1, unit_cost: 0 }] });
const { warehouses, materials, loadOptions } = useMasterOptions();

function listFrom(response: any): Row[] { if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "库存调拨接口返回失败"); const data = response?.data?.data; return Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : []; }
async function load() {
  loading.value = true; errorMessage.value = "";
  try { rows.value = listFrom(await listInventoryTransfers()); }
  catch (error) { errorMessage.value = "库存调拨加载失败，请检查接口服务后重试"; }
  finally { loading.value = false; }
}
function openCreate() { form.from_warehouse_id = ""; form.to_warehouse_id = ""; form.items = [{ material_id: "", quantity: 1, unit_cost: 0 }]; dialogVisible.value = true; }
async function save() {
  if (!form.from_warehouse_id || !form.to_warehouse_id || !form.items[0]?.material_id || form.items[0].quantity <= 0) { ElMessage.warning("请填写调出/调入仓库、物料和有效数量"); return; }
  saving.value = true;
  try { const response = await createInventoryTransfer(form); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("调拨单已创建"); dialogVisible.value = false; await load(); }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : "调拨单创建失败"); }
  finally { saving.value = false; }
}
async function confirmAction(row: Row, action: "approve" | "complete") {
  const id = String(row.id || ""); if (!id) { ElMessage.error("调拨单缺少有效 ID，无法操作"); return; }
  const label = action === "approve" ? "审核调拨单" : "完成调拨单";
  try { await ElMessageBox.confirm(`确认${label}“${row.doc_no || id}”吗？`, "操作确认", { type: "warning" }); actionLoading.value = id; const response = action === "approve" ? await approveInventoryTransfer(id) : await completeInventoryTransfer(id); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success(`${label}成功`); await load(); }
  catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : `${label}失败`); }
  finally { actionLoading.value = null; }
}
onMounted(async () => { await Promise.all([load(), loadOptions(["warehouses", "materials"])]); });
</script>

<template>
  <section>
    <el-page-header content="库存调拨" />
    <el-space class="toolbar"><el-button type="primary" @click="openCreate">新建调拨单</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''"><template #default><el-button link type="primary" @click="load">重新加载</el-button></template></el-alert>
    <el-table v-loading="loading" :data="rows" stripe><el-table-column prop="doc_no" label="调拨单号" /><el-table-column prop="from_warehouse_id" label="调出仓库" /><el-table-column prop="to_warehouse_id" label="调入仓库" /><el-table-column prop="status" label="状态" /><el-table-column label="操作" min-width="180"><template #default="scope"><el-button v-if="scope.row.status === 'draft'" link type="primary" :loading="actionLoading === scope.row.id" @click="confirmAction(scope.row, 'approve')">审核</el-button><el-button v-if="scope.row.status === 'approved'" link type="warning" :loading="actionLoading === scope.row.id" @click="confirmAction(scope.row, 'complete')">完成</el-button></template></el-table-column></el-table>
    <el-dialog v-model="dialogVisible" title="新建调拨单" width="520px"><el-form label-width="100px"><el-form-item label="调出仓库" required><el-select v-model="form.from_warehouse_id" filterable clearable style="width: 100%"><el-option v-for="option in warehouses" :key="option.value" v-bind="option" /></el-select></el-form-item><el-form-item label="调入仓库" required><el-select v-model="form.to_warehouse_id" filterable clearable style="width: 100%"><el-option v-for="option in warehouses" :key="option.value" v-bind="option" /></el-select></el-form-item><el-form-item label="物料" required><el-select v-model="form.items[0].material_id" filterable clearable style="width: 100%"><el-option v-for="option in materials" :key="option.value" v-bind="option" /></el-select></el-form-item><el-form-item label="数量" required><el-input-number v-model="form.items[0].quantity" :min="0.01" /></el-form-item><el-form-item label="单位成本"><el-input-number v-model="form.items[0].unit_cost" :min="0" :precision="2" /></el-form-item></el-form><template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template></el-dialog>
  </section>
</template>

<style scoped>.toolbar { margin: 16px 0; }</style>
