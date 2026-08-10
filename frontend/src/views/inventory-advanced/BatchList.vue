<script setup lang="ts">
import { onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { createBatch, deleteBatch, listBatches, updateBatch } from "../../api/inventory-advanced";
import { useMasterOptions } from "../../composables/useMasterOptions";
const rows = ref<any[]>([]); const loading = ref(false); const saving = ref(false); const actionLoading = ref<string | null>(null); const visible = ref(false); const editingId = ref<string | null>(null); const form = reactive({ material_id: "", batch_no: "", production_date: "", expiry_date: "", status: "active" });
const { materials, loadOptions } = useMasterOptions();
const statusLabels: Record<string, string> = { active: "启用", inactive: "停用" };
function materialLabel(id: unknown) { const value = String(id || ""); return materials.value.find((option) => option.value === value)?.label || value || "-"; }
function statusLabel(status: string) { return statusLabels[status] || status || "未知"; }
function statusTagType(status: string) { return status === "active" ? "success" : "info"; }
async function load() { loading.value = true; try { const response = await listBatches(form.material_id || undefined); if (response.data.code !== 0) throw new Error(response.data.msg); rows.value = response.data.data || []; } catch (error) { ElMessage.error(error instanceof Error ? error.message : "批次加载失败"); } finally { loading.value = false; } }
function openCreate() { editingId.value = null; form.batch_no = ""; form.production_date = ""; form.expiry_date = ""; form.status = "active"; visible.value = true; }
function openEdit(row: any) { editingId.value = String(row.id); form.material_id = row.material_id || form.material_id; form.batch_no = row.batch_no || ""; form.production_date = row.production_date || ""; form.expiry_date = row.expiry_date || ""; form.status = row.status || "active"; visible.value = true; }
async function save() { if (!form.material_id || !form.batch_no.trim()) { ElMessage.warning("请选择物料并填写批次号"); return; } saving.value = true; try { const payload = { batch_no: form.batch_no.trim(), production_date: form.production_date || null, expiry_date: form.expiry_date || null, status: form.status }; const response = editingId.value ? await updateBatch(editingId.value, payload) : await createBatch(form.material_id, payload); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success(editingId.value ? "批次已修改" : "批次已创建"); visible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "批次保存失败"); } finally { saving.value = false; } }
async function remove(row: any) { const id = String(row.id || ""); if (!id) { ElMessage.error("批次缺少有效 ID，无法删除"); return; } try { await ElMessageBox.confirm(`确认删除批次“${row.batch_no || id}”吗？删除后不可恢复。`, "删除确认", { type: "warning" }); actionLoading.value = id; const response = await deleteBatch(id); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("批次已删除"); await load(); } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "批次删除失败"); } finally { actionLoading.value = null; } }
async function toggleStatus(row: any) { const id = String(row.id || ""); if (!id) { ElMessage.error("批次缺少有效 ID，无法切换状态"); return; } const nextStatus = row.status === "active" ? "inactive" : "active"; actionLoading.value = id; try { const response = await updateBatch(id, { batch_no: row.batch_no, production_date: row.production_date || null, expiry_date: row.expiry_date || null, status: nextStatus }); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success(nextStatus === "active" ? "批次已启用" : "批次已停用"); await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "批次状态修改失败"); } finally { actionLoading.value = null; } }
watch(() => form.material_id, load); onMounted(() => Promise.all([load(), loadOptions(["materials"])]));
</script>
<template>
  <section class="page-stack">
    <el-page-header content="批次管理" />
    <el-space><el-select v-model="form.material_id" filterable clearable placeholder="全部物料" style="width: 250px"><el-option v-for="item in materials" :key="item.value" v-bind="item" /></el-select><el-button type="primary" @click="openCreate">新增批次</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-table v-loading="loading" :data="rows" stripe :header-cell-style="{ textAlign: 'center' }" :cell-style="{ textAlign: 'center' }">
      <el-table-column prop="batch_no" label="批次号" min-width="200" />
      <el-table-column label="物料" min-width="220"><template #default="scope">{{ materialLabel(scope.row.material_id) }}</template></el-table-column>
      <el-table-column prop="production_date" label="生产日期" width="140" />
      <el-table-column prop="expiry_date" label="失效日期" width="140" />
      <el-table-column label="状态" width="110"><template #default="scope"><el-tag class="status-tag" :type="statusTagType(scope.row.status)" effect="light">{{ statusLabel(scope.row.status) }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="240"><template #default="scope"><el-button link type="primary" @click="openEdit(scope.row)">修改</el-button><el-button link :type="scope.row.status === 'active' ? 'warning' : 'success'" :loading="actionLoading === scope.row.id" @click="toggleStatus(scope.row)">{{ scope.row.status === "active" ? "停用" : "启用" }}</el-button><el-button link type="danger" :loading="actionLoading === scope.row.id" @click="remove(scope.row)">删除</el-button></template></el-table-column>
      <template #empty><el-empty description="暂无批次" /></template>
    </el-table>
    <el-dialog v-model="visible" :title="editingId ? '修改批次' : '新增批次'" width="500px"><el-form label-width="90px"><el-form-item label="物料" required><el-select v-model="form.material_id" filterable style="width: 100%" :disabled="Boolean(editingId)"><el-option v-for="item in materials" :key="item.value" v-bind="item" /></el-select></el-form-item><el-form-item label="批次号" required><el-input v-model="form.batch_no" /></el-form-item><el-form-item label="生产日期"><el-date-picker v-model="form.production_date" type="date" value-format="YYYY-MM-DD" /></el-form-item><el-form-item label="失效日期"><el-date-picker v-model="form.expiry_date" type="date" value-format="YYYY-MM-DD" /></el-form-item><el-form-item label="状态"><el-select v-model="form.status" style="width: 100%"><el-option label="启用" value="active" /><el-option label="停用" value="inactive" /></el-select></el-form-item></el-form><template #footer><el-button @click="visible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template></el-dialog>
  </section>
</template>
<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.status-tag { border-width: 1px; }
</style>
