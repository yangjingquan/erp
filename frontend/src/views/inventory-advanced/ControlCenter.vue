<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { createReservation, listReservations, listTraceEvents, releaseReservation } from "../../api/inventory-advanced";
import { useMasterOptions } from "../../composables/useMasterOptions";
import { useClientPagination } from "../../composables/useClientPagination";
import { labelOf, sourceTypeLabels, statusLabel, tagTypeOf } from "../../utils/labels";

type Row = Record<string, any>;
const tab = ref("reservations");
const loading = ref(false);
const saving = ref(false);
const reservationVisible = ref(false);
const reservations = ref<Row[]>([]);
const trace = ref<Row[]>([]);
const reservationFilters = reactive({ search: "", warehouse_id: "", source_type: "", status: "" });
const traceFilters = reactive({ material_id: "", batch_id: "" });
const form = reactive({ source_type: "sales_order", source_id: "", material_id: "", warehouse_id: "", quantity: 1, note: "" });
const { materials, warehouses, loadOptions } = useMasterOptions();
const filteredReservations = computed(() => {
  const search = reservationFilters.search.trim().toLowerCase();
  return reservations.value.filter((row) => {
    const materialText = label(materials.value, row.material_id).toLowerCase();
    const sourceId = String(row.source_id ?? "").toLowerCase();
    const materialId = String(row.material_id ?? "").toLowerCase();
    return (!search || sourceId.includes(search) || materialText.includes(search) || materialId.includes(search))
      && (!reservationFilters.warehouse_id || String(row.warehouse_id) === reservationFilters.warehouse_id)
      && (!reservationFilters.source_type || String(row.source_type) === reservationFilters.source_type)
      && (!reservationFilters.status || String(row.status) === reservationFilters.status);
  });
});
const { pagedRows: reservationRows, page: reservationPage, pageSize: reservationPageSize, total: reservationTotal, updatePageSize: updateReservationPageSize } = useClientPagination(filteredReservations);
const { pagedRows: traceRows, page: tracePage, pageSize: tracePageSize, total: traceTotal, updatePageSize: updateTracePageSize } = useClientPagination(trace);
const reservationSourceTypeOptions = [
  { value: "sales_order", label: sourceTypeLabels.sales_order },
  { value: "work_order", label: sourceTypeLabels.work_order },
  { value: "purchase_request", label: sourceTypeLabels.purchase_request },
];
const reservationSourceTypeLabels: Record<string, string> = {
  ...Object.fromEntries(reservationSourceTypeOptions.map((item) => [item.value, item.label])),
  active: "系统生成",
};

function data(response: any) {
  if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "接口请求失败");
  const value = response.data.data;
  return Array.isArray(value) ? value : Array.isArray(value?.items) ? value.items : [];
}

function label(options: any[], id: any) { return options.find((item) => item.value === id)?.label || id || "-"; }

async function load() {
  loading.value = true;
  try {
    reservations.value = data(await listReservations(reservationFilters.status || undefined));
    trace.value = data(await listTraceEvents({ material_id: traceFilters.material_id || undefined, batch_id: traceFilters.batch_id || undefined }));
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "库存控制台加载失败");
  } finally {
    loading.value = false;
  }
}

function openReservation() {
  Object.assign(form, { source_type: "sales_order", source_id: "", material_id: "", warehouse_id: "", quantity: 1, note: "" });
  reservationVisible.value = true;
}

async function reserve() {
  if (!form.source_id.trim() || !form.material_id || !form.warehouse_id || Number(form.quantity) <= 0) {
    return ElMessage.warning("请填写来源单据、物料、仓库和有效数量");
  }
  saving.value = true;
  try {
    const response = await createReservation({ ...form, source_id: form.source_id.trim() });
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success("库存已预留");
    reservationVisible.value = false;
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "库存预留失败");
  } finally {
    saving.value = false;
  }
}

async function release(row: Row) {
  await ElMessageBox.confirm("确认释放该库存预留？", "操作确认", { type: "warning" });
  try {
    const response = await releaseReservation(row.id);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success("预留已释放");
    await load();
  } catch (error: any) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "释放失败");
  }
}

onMounted(async () => {
  try {
    await loadOptions(["materials", "warehouses"]);
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "库存控制台基础数据加载失败");
  }
});
</script>

<template>
  <section class="page-stack">
    <el-page-header content="库存控制中心" />
    <el-alert title="预留会锁定可用库存；批次追溯展示已接入 FIFO 入库/出库事件。" type="info" show-icon />
    <el-alert v-if="!materials.length || !warehouses.length" title="暂无可用物料或仓库，当前不能创建库存预留。请先维护主数据。" type="warning" show-icon />
    <el-tabs v-model="tab" type="border-card">
      <el-tab-pane label="库存预留" name="reservations">
        <div class="reservation-toolbar">
          <div class="reservation-filter">
            <el-input v-model="reservationFilters.search" clearable placeholder="来源单据/物料" style="width: 230px" />
            <el-select v-model="reservationFilters.warehouse_id" clearable placeholder="仓库" style="width: 170px">
              <el-option v-for="item in warehouses" :key="item.value" v-bind="item" />
            </el-select>
            <el-select v-model="reservationFilters.source_type" clearable placeholder="来源" style="width: 150px">
              <el-option v-for="item in reservationSourceTypeOptions" :key="item.value" v-bind="item" />
            </el-select>
            <el-select v-model="reservationFilters.status" clearable placeholder="状态" style="width: 120px" @change="load">
              <el-option label="预留中" value="reserved" />
              <el-option label="已释放" value="released" />
            </el-select>
          </div>
          <el-space class="toolbar-actions">
            <el-button type="primary" :disabled="!materials.length || !warehouses.length" @click="openReservation">新建预留</el-button>
            <el-button :loading="loading" @click="load">刷新</el-button>
          </el-space>
        </div>
        <el-table v-loading="loading" :data="reservationRows" stripe>
          <el-table-column prop="source_id" label="来源单据" min-width="180" />
          <el-table-column label="物料" min-width="160"><template #default="scope">{{ label(materials, scope.row.material_id) }}</template></el-table-column>
          <el-table-column label="仓库" min-width="140"><template #default="scope">{{ label(warehouses, scope.row.warehouse_id) }}</template></el-table-column>
          <el-table-column prop="quantity" label="预留总量" width="110" />
          <el-table-column prop="reserved_quantity" label="剩余预留" width="110" />
          <el-table-column label="来源" width="140"><template #default="scope">{{ labelOf(reservationSourceTypeLabels, scope.row.source_type) }}</template></el-table-column>
          <el-table-column label="状态" width="100"><template #default="scope"><el-tag class="status-tag" :type="tagTypeOf(scope.row.status)" effect="light">{{ statusLabel(scope.row.status) }}</el-tag></template></el-table-column>
          <el-table-column label="操作" width="100"><template #default="scope"><el-button v-if="scope.row.status !== 'released'" link type="danger" @click="release(scope.row)">释放</el-button></template></el-table-column>
          <template #empty><el-empty description="暂无库存预留记录" /></template>
        </el-table>
        <ClientPagination v-model:page="reservationPage" v-model:page-size="reservationPageSize" :total="reservationTotal" @update:page-size="updateReservationPageSize" />
      </el-tab-pane>
      <el-tab-pane label="批次追溯" name="trace">
        <el-form inline class="control-form">
          <el-form-item label="物料"><el-select v-model="traceFilters.material_id" filterable clearable style="width: 200px"><el-option v-for="item in materials" :key="item.value" v-bind="item" /></el-select></el-form-item>
          <el-form-item label="批次 ID"><el-input v-model="traceFilters.batch_id" clearable placeholder="可选批次 ID" /></el-form-item>
          <el-button type="primary" @click="load">查询追溯</el-button>
          <el-button @click="traceFilters.material_id = ''; traceFilters.batch_id = ''; load()">重置</el-button>
        </el-form>
        <el-table :data="traceRows" stripe>
          <el-table-column prop="event_time" label="日期" width="120" />
          <el-table-column prop="direction" label="方向" width="90" />
          <el-table-column label="来源类型" width="150"><template #default="scope">{{ labelOf(reservationSourceTypeLabels, scope.row.source_type) }}</template></el-table-column>
          <el-table-column prop="source_id" label="来源单据" min-width="180" />
          <el-table-column label="物料" min-width="160"><template #default="scope">{{ label(materials, scope.row.material_id) }}</template></el-table-column>
          <el-table-column prop="batch_id" label="批次" min-width="150" />
          <el-table-column prop="quantity" label="数量" width="120" />
          <template #empty><el-empty description="暂无批次追溯事件" /></template>
        </el-table>
        <ClientPagination v-model:page="tracePage" v-model:page-size="tracePageSize" :total="traceTotal" @update:page-size="updateTracePageSize" />
      </el-tab-pane>
    </el-tabs>
    <el-dialog v-model="reservationVisible" title="新建库存预留" width="560px">
      <el-form label-width="90px">
        <el-form-item label="来源类型" required><el-select v-model="form.source_type" style="width: 100%"><el-option v-for="item in reservationSourceTypeOptions" :key="item.value" v-bind="item" /></el-select></el-form-item>
        <el-form-item label="来源单据" required><el-input v-model="form.source_id" placeholder="单据 ID" /></el-form-item>
        <el-form-item label="物料" required><el-select v-model="form.material_id" filterable clearable style="width: 100%"><el-option v-for="item in materials" :key="item.value" v-bind="item" /></el-select></el-form-item>
        <el-form-item label="仓库" required><el-select v-model="form.warehouse_id" filterable clearable style="width: 100%"><el-option v-for="item in warehouses" :key="item.value" v-bind="item" /></el-select></el-form-item>
        <el-form-item label="数量" required><el-input-number v-model="form.quantity" :min="0.000001" :precision="6" style="width: 100%" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="reservationVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="reserve">预留</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.reservation-toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.reservation-filter { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.toolbar-actions { margin-left: auto; }
.control-form { display: flex; flex-wrap: wrap; align-items: flex-end; column-gap: 12px; }
.control-form :deep(.el-form-item) { margin-right: 0; }
.control-form :deep(.el-button) { margin-bottom: 18px; }
.status-tag { border-width: 1px; }
</style>
