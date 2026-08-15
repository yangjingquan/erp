<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";
import { listInventoryStock, listInventoryWarnings } from "../../api/inventory";
import { useMasterOptions } from "../../composables/useMasterOptions";
import { useClientPagination } from "../../composables/useClientPagination";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const warningRows = ref<Row[]>([]);
const warningFilters = reactive({ warehouse_id: "", material_id: "" });
const balanceFilters = reactive({ warehouse_id: "", material_id: "" });
const filteredWarnings = computed(() => warningRows.value.filter((row) => (!warningFilters.warehouse_id || String(row.warehouse_id) === warningFilters.warehouse_id) && (!warningFilters.material_id || String(row.material_id) === warningFilters.material_id)));
const filteredRows = computed(() => rows.value.filter((row) => (!balanceFilters.warehouse_id || String(row.warehouse_id) === balanceFilters.warehouse_id) && (!balanceFilters.material_id || String(row.material_id) === balanceFilters.material_id)));
const { pagedRows: pagedWarningRows, page: warningPage, pageSize: warningPageSize, total: warningTotal, updatePageSize: updateWarningPageSize } = useClientPagination(filteredWarnings);
const { pagedRows: pagedBalanceRows, page: balancePage, pageSize: balancePageSize, total: balanceTotal, updatePageSize: updateBalancePageSize } = useClientPagination(filteredRows);
const loading = ref(false);
const errorMessage = ref("");
const { warehouses, materials, loadOptions } = useMasterOptions();

watch(() => [warningFilters.warehouse_id, warningFilters.material_id], () => { warningPage.value = 1; });
watch(() => [balanceFilters.warehouse_id, balanceFilters.material_id], () => { balancePage.value = 1; });

function optionLabel(options: Array<{ label: string; value: string }>, id: unknown) {
  const value = String(id || "");
  return options.find((option) => option.value === value)?.label || value || "-";
}

function warehouseLabel(id: unknown) { return optionLabel(warehouses.value, id); }
function materialLabel(id: unknown) { return optionLabel(materials.value, id); }

function listFrom(response: any): Row[] {
  if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "库存接口返回失败");
  const data = response?.data?.data;
  return Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : [];
}

async function load() {
  loading.value = true;
  errorMessage.value = "";
  const [stockResult, warningResult] = await Promise.allSettled([listInventoryStock(), listInventoryWarnings()]);
  if (stockResult.status === "fulfilled") rows.value = listFrom(stockResult.value);
  else errorMessage.value = "库存台账加载失败，请检查接口服务后重试";
  if (warningResult.status === "fulfilled") warningRows.value = listFrom(warningResult.value);
  else if (!errorMessage.value) errorMessage.value = "库存预警加载失败，请检查接口服务后重试";
  loading.value = false;
}

onMounted(async () => { await Promise.all([load(), loadOptions(["warehouses", "materials"])]); });
</script>

<template>
  <section>
    <el-page-header content="库存台账" />
    <el-space class="toolbar" wrap><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''"><template #default><el-button link type="primary" @click="load">重新加载</el-button></template></el-alert>
    <el-card shadow="never" class="warning-table"><template #header><div class="card-header"><span>库存预警</span><span v-if="warningTotal" class="warning-text">当前有 {{ warningTotal }} 条库存低于安全库存</span></div></template><el-space class="section-toolbar" wrap><el-select v-model="warningFilters.warehouse_id" clearable filterable placeholder="仓库" style="width:200px"><el-option v-for="item in warehouses" :key="item.value" v-bind="item" /></el-select><el-select v-model="warningFilters.material_id" clearable filterable placeholder="物料" style="width:220px"><el-option v-for="item in materials" :key="item.value" v-bind="item" /></el-select></el-space><el-table v-loading="loading" :data="pagedWarningRows" stripe width="100%" fit :header-cell-style="{ textAlign: 'center' }" :cell-style="{ textAlign: 'center' }"><el-table-column label="仓库"><template #default="scope">{{ warehouseLabel(scope.row.warehouse_id) }}</template></el-table-column><el-table-column label="物料"><template #default="scope">{{ materialLabel(scope.row.material_id) }}</template></el-table-column><el-table-column prop="current_quantity" label="当前库存" /><el-table-column prop="min_quantity" label="安全库存" /><template #empty><el-empty description="暂无库存预警" /></template></el-table><ClientPagination v-model:page="warningPage" v-model:page-size="warningPageSize" :total="warningTotal" @update:page-size="updateWarningPageSize" /></el-card>
    <el-card shadow="never"><template #header>库存余额</template><el-space class="section-toolbar" wrap><el-select v-model="balanceFilters.warehouse_id" clearable filterable placeholder="仓库" style="width:200px"><el-option v-for="item in warehouses" :key="item.value" v-bind="item" /></el-select><el-select v-model="balanceFilters.material_id" clearable filterable placeholder="物料" style="width:220px"><el-option v-for="item in materials" :key="item.value" v-bind="item" /></el-select></el-space><el-table v-loading="loading" :data="pagedBalanceRows" stripe width="100%" fit :header-cell-style="{ textAlign: 'center' }" :cell-style="{ textAlign: 'center' }"><el-table-column label="仓库"><template #default="scope">{{ warehouseLabel(scope.row.warehouse_id) }}</template></el-table-column><el-table-column label="物料"><template #default="scope">{{ materialLabel(scope.row.material_id) }}</template></el-table-column><el-table-column prop="quantity" label="库存数量" /><el-table-column prop="available_quantity" label="可用数量" /><template #empty><el-empty description="暂无库存余额" /></template></el-table></el-card>
    <ClientPagination v-model:page="balancePage" v-model:page-size="balancePageSize" :total="balanceTotal" @update:page-size="updateBalancePageSize" />
  </section>
</template>

<style scoped>
.toolbar { margin: 16px 0; }
.warning-table { margin: 16px 0; }
.section-toolbar { margin-bottom: 16px; }
.card-header { display: flex; align-items: center; gap: 16px; }
.warning-text { color: #f56c6c; font-size: 13px; }
</style>
