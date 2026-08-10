<script setup lang="ts">
import { onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { createLocation, deleteLocation, listLocations, updateLocation } from "../../api/inventory-advanced";
import { useMasterOptions } from "../../composables/useMasterOptions";

const rows = ref<any[]>([]);
const loading = ref(false);
const saving = ref(false);
const actionLoading = ref<string | null>(null);
const visible = ref(false);
const editingId = ref<string | null>(null);
const selectedWarehouseId = ref("");
const createForm = reactive({ warehouse_id: "", code: "", name: "", status: "active" });
const { warehouses, loadOptions } = useMasterOptions();

const statusLabels: Record<string, string> = { active: "启用", inactive: "停用" };

function statusLabel(status: string) { return statusLabels[status] || status || "未知"; }
function statusTagType(status: string) { return status === "active" ? "success" : "info"; }

function warehouseName(warehouseId: string | null | undefined) {
  return warehouses.value.find((item) => item.value === warehouseId)?.label || warehouseId || "-";
}

async function load() {
  loading.value = true;
  try {
    const response = await listLocations(selectedWarehouseId.value || undefined);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    rows.value = response.data.data || [];
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "库位加载失败");
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingId.value = null;
  createForm.warehouse_id = selectedWarehouseId.value;
  createForm.code = "";
  createForm.name = "";
  createForm.status = "active";
  visible.value = true;
}

function openEdit(row: any) {
  editingId.value = String(row.id);
  createForm.warehouse_id = row.warehouse_id || selectedWarehouseId.value;
  createForm.code = row.code || "";
  createForm.name = row.name || "";
  createForm.status = row.status || "active";
  visible.value = true;
}

async function save() {
  if (!createForm.warehouse_id || !createForm.code.trim() || !createForm.name.trim()) {
    ElMessage.warning("请选择仓库并填写库位编码和名称");
    return;
  }
  saving.value = true;
  try {
    const warehouseId = createForm.warehouse_id;
    const payload = { code: createForm.code.trim(), name: createForm.name.trim(), status: createForm.status };
    const response = editingId.value ? await updateLocation(editingId.value, payload) : await createLocation(warehouseId, payload);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success(editingId.value ? "库位已修改" : "库位已创建");
    visible.value = false;
    selectedWarehouseId.value = warehouseId;
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "库位创建失败");
  } finally {
    saving.value = false;
  }
}

async function remove(row: any) {
  const id = String(row.id || "");
  if (!id) { ElMessage.error("库位缺少有效 ID，无法删除"); return; }
  try {
    await ElMessageBox.confirm(`确认删除库位“${row.name || row.code || id}”吗？删除后不可恢复。`, "删除确认", { type: "warning" });
    actionLoading.value = id;
    const response = await deleteLocation(id);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success("库位已删除");
    await load();
  } catch (error: any) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "库位删除失败");
  } finally { actionLoading.value = null; }
}

async function toggleStatus(row: any) {
  const id = String(row.id || "");
  if (!id) { ElMessage.error("库位缺少有效 ID，无法切换状态"); return; }
  const nextStatus = row.status === "active" ? "inactive" : "active";
  actionLoading.value = id;
  try {
    const response = await updateLocation(id, { code: row.code, name: row.name, status: nextStatus });
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success(nextStatus === "active" ? "库位已启用" : "库位已停用");
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "库位状态修改失败");
  } finally { actionLoading.value = null; }
}

watch(selectedWarehouseId, () => { void load(); });
onMounted(async () => {
  await loadOptions(["warehouses"]);
  await load();
});
</script>
<template>
  <section class="page-stack">
    <el-page-header content="库位管理" />
    <el-space>
      <el-select v-model="selectedWarehouseId" filterable clearable placeholder="请选择仓库" style="width: 220px">
        <el-option v-for="item in warehouses" :key="item.value" v-bind="item" />
      </el-select>
      <el-button type="primary" @click="openCreate">新增库位</el-button>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </el-space>
    <el-table v-loading="loading" :data="rows" stripe :header-cell-style="{ textAlign: 'center' }" :cell-style="{ textAlign: 'center' }">
      <el-table-column prop="code" label="库位编码" min-width="180" />
      <el-table-column prop="name" label="库位名称" min-width="220" />
      <el-table-column label="库区" min-width="180"><template #default="scope">{{ warehouseName(scope.row.warehouse_id) }}</template></el-table-column>
      <el-table-column label="状态" width="120"><template #default="scope"><el-tag class="status-tag" :type="statusTagType(scope.row.status)" effect="light">{{ statusLabel(scope.row.status) }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="240"><template #default="scope"><el-button link type="primary" @click="openEdit(scope.row)">修改</el-button><el-button link :type="scope.row.status === 'active' ? 'warning' : 'success'" :loading="actionLoading === scope.row.id" @click="toggleStatus(scope.row)">{{ scope.row.status === "active" ? "停用" : "启用" }}</el-button><el-button link type="danger" :loading="actionLoading === scope.row.id" @click="remove(scope.row)">删除</el-button></template></el-table-column>
      <template #empty><el-empty description="暂无库位" /></template>
    </el-table>
    <el-dialog v-model="visible" :title="editingId ? '修改库位' : '新增库位'" width="460px">
      <el-form label-width="90px">
        <el-form-item label="仓库" required>
          <el-select v-model="createForm.warehouse_id" filterable placeholder="请选择所属仓库" style="width: 100%" :disabled="Boolean(editingId)">
            <el-option v-for="item in warehouses" :key="item.value" v-bind="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="编码" required><el-input v-model="createForm.code" /></el-form-item>
        <el-form-item label="名称" required><el-input v-model="createForm.name" /></el-form-item>
        <el-form-item label="状态"><el-select v-model="createForm.status" style="width: 100%"><el-option label="启用" value="active" /><el-option label="停用" value="inactive" /></el-select></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>
<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.status-tag { border-width: 1px; }
</style>
