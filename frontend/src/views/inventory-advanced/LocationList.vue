<script setup lang="ts">
import { onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { createLocation, listLocations } from "../../api/inventory-advanced";
import { useMasterOptions } from "../../composables/useMasterOptions";

const rows = ref<any[]>([]);
const loading = ref(false);
const saving = ref(false);
const visible = ref(false);
const selectedWarehouseId = ref("");
const createForm = reactive({ warehouse_id: "", code: "", name: "" });
const { warehouses, loadOptions } = useMasterOptions();

async function load() {
  if (!selectedWarehouseId.value) {
    rows.value = [];
    return;
  }
  loading.value = true;
  try {
    const response = await listLocations(selectedWarehouseId.value);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    rows.value = response.data.data || [];
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "库位加载失败");
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  createForm.warehouse_id = selectedWarehouseId.value;
  createForm.code = "";
  createForm.name = "";
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
    const response = await createLocation(warehouseId, {
      code: createForm.code.trim(),
      name: createForm.name.trim(),
    });
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success("库位已创建");
    visible.value = false;
    if (selectedWarehouseId.value === warehouseId) {
      await load();
    } else {
      selectedWarehouseId.value = warehouseId;
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "库位创建失败");
  } finally {
    saving.value = false;
  }
}

watch(selectedWarehouseId, load);
onMounted(() => loadOptions(["warehouses"]));
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
    <el-table v-loading="loading" :data="rows" stripe>
      <el-table-column prop="code" label="库位编码" min-width="180" />
      <el-table-column prop="name" label="库位名称" min-width="220" />
      <el-table-column prop="zone_id" label="库区" min-width="180" />
      <el-table-column prop="status" label="状态" width="120" />
      <template #empty><el-empty description="请选择仓库或暂无库位" /></template>
    </el-table>
    <el-dialog v-model="visible" title="新增库位" width="460px">
      <el-form label-width="90px">
        <el-form-item label="仓库" required>
          <el-select v-model="createForm.warehouse_id" filterable placeholder="请选择所属仓库" style="width: 100%">
            <el-option v-for="item in warehouses" :key="item.value" v-bind="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="编码" required><el-input v-model="createForm.code" /></el-form-item>
        <el-form-item label="名称" required><el-input v-model="createForm.name" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>
<style scoped>.page-stack { display: flex; flex-direction: column; gap: 16px; }</style>
