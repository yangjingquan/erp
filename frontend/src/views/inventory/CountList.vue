<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { completeInventoryCount, createInventoryCount, listInventoryCounts, type InventoryCountPayload } from "../../api/inventory";
import { useMasterOptions } from "../../composables/useMasterOptions";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const loading = ref(false);
const saving = ref(false);
const actionLoading = ref<string | null>(null);
const errorMessage = ref("");
const dialogVisible = ref(false);
const form = reactive<InventoryCountPayload>({ warehouse_id: "", items: [{ material_id: "", actual_quantity: 0 }] });
const { warehouses, materials, loadOptions } = useMasterOptions();

function listFrom(response: any): Row[] { if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "库存盘点接口返回失败"); const data = response?.data?.data; return Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : []; }
async function load() { loading.value = true; errorMessage.value = ""; try { rows.value = listFrom(await listInventoryCounts()); } catch (error) { errorMessage.value = "库存盘点加载失败，请检查接口服务后重试"; } finally { loading.value = false; } }
function openCreate() { form.warehouse_id = ""; form.items = [{ material_id: "", actual_quantity: 0 }]; dialogVisible.value = true; }
async function save() { if (!form.warehouse_id || !form.items[0]?.material_id || form.items[0].actual_quantity < 0) { ElMessage.warning("请填写仓库、物料和有效实盘数量"); return; } saving.value = true; try { const response = await createInventoryCount(form); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("盘点单已创建"); dialogVisible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "盘点单创建失败"); } finally { saving.value = false; } }
async function complete(row: Row) { const id = String(row.id || ""); if (!id) { ElMessage.error("盘点单缺少有效 ID，无法操作"); return; } try { await ElMessageBox.confirm(`确认完成盘点单“${row.doc_no || id}”吗？完成后会调整库存。`, "高危操作确认", { type: "warning" }); actionLoading.value = id; const response = await completeInventoryCount(id); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("盘点单已完成"); await load(); } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "盘点单完成失败"); } finally { actionLoading.value = null; } }
onMounted(async () => { await Promise.all([load(), loadOptions(["warehouses", "materials"])]); });
</script>

<template>
  <section>
    <el-page-header content="库存盘点" />
    <el-space class="toolbar"><el-button type="primary" @click="openCreate">新建盘点单</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''"><template #default><el-button link type="primary" @click="load">重新加载</el-button></template></el-alert>
    <el-table v-loading="loading" :data="rows" stripe width="100%" fit><el-table-column prop="doc_no" label="盘点单号" /><el-table-column prop="warehouse_id" label="仓库" /><el-table-column prop="status" label="状态" /><el-table-column prop="count_date" label="盘点日期" /><el-table-column label="操作"><template #default="scope"><el-button v-if="scope.row.status === 'draft'" link type="warning" :loading="actionLoading === scope.row.id" @click="complete(scope.row)">完成盘点</el-button></template></el-table-column></el-table>
    <el-dialog v-model="dialogVisible" title="新建盘点单" width="520px"><el-form label-width="100px"><el-form-item label="仓库" required><el-select v-model="form.warehouse_id" filterable clearable style="width: 100%"><el-option v-for="option in warehouses" :key="option.value" v-bind="option" /></el-select></el-form-item><el-form-item label="物料" required><el-select v-model="form.items[0].material_id" filterable clearable style="width: 100%"><el-option v-for="option in materials" :key="option.value" v-bind="option" /></el-select></el-form-item><el-form-item label="实盘数量" required><el-input-number v-model="form.items[0].actual_quantity" :min="0" /></el-form-item></el-form><template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template></el-dialog>
  </section>
</template>

<style scoped>.toolbar { margin: 16px 0; }</style>
