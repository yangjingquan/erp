<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { listInventoryTransactions } from "../../api/inventory";
import { useClientPagination } from "../../composables/useClientPagination";
import { directionLabels, labelOf, sourceTypeLabels } from "../../utils/labels";

type Row = Record<string, any>;
const transactionSourceTypeLabels: Record<string, string> = {
  ...sourceTypeLabels,
  count: "库存盘点",
  scan: "移动扫码",
  subcontract_receipt: "委外入库",
  subcontract_material_issue: "委外领料",
  mfg_subcontract_order: "委外工单",
  mfg_material_issue: "生产领料",
  mfg_material_return: "生产退料",
  mfg_completion: "生产完工",
  mfg_work_order_cost: "生产工单成本",
  active: "系统生成",
};
const transactionDirectionLabels: Record<string, string> = { ...directionLabels, active: "入库" };
const rows = ref<Row[]>([]);
const filters = reactive({ source_type: "", source_id: "", direction: "" });
const filteredRows = computed(() => rows.value.filter((row) => (!filters.source_type || row.source_type === filters.source_type) && (!filters.source_id || String(row.source_id || "").includes(filters.source_id)) && (!filters.direction || row.direction === filters.direction)));
const { pagedRows, page, pageSize, total, updatePageSize } = useClientPagination(filteredRows);
const loading = ref(false);
const errorMessage = ref("");

function listFrom(response: any): Row[] {
  if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "库存流水接口返回失败");
  const data = response?.data?.data;
  return Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : [];
}

async function load() {
  loading.value = true;
  errorMessage.value = "";
  try { rows.value = listFrom(await listInventoryTransactions()); }
  catch (error) { errorMessage.value = "库存流水加载失败，请检查接口服务后重试"; }
  finally { loading.value = false; }
}

onMounted(load);
</script>

<template>
  <section>
    <el-page-header content="库存流水" />
    <el-space class="toolbar" wrap><el-select v-model="filters.source_type" clearable placeholder="来源类型" style="width:170px"><el-option v-for="(label, key) in transactionSourceTypeLabels" :key="key" :label="label" :value="key" /></el-select><el-input v-model="filters.source_id" clearable placeholder="来源单据" style="width:200px" /><el-select v-model="filters.direction" clearable placeholder="方向" style="width:130px"><el-option label="入库" value="in" /><el-option label="出库" value="out" /></el-select><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''"><template #default><el-button link type="primary" @click="load">重新加载</el-button></template></el-alert>
    <el-table v-loading="loading" :data="pagedRows" stripe width="100%" fit><el-table-column label="来源类型"><template #default="scope">{{ labelOf(transactionSourceTypeLabels, scope.row.source_type) }}</template></el-table-column><el-table-column prop="source_id" label="来源单据" /><el-table-column label="方向"><template #default="scope">{{ labelOf(transactionDirectionLabels, scope.row.direction) }}</template></el-table-column><el-table-column prop="quantity" label="数量" /><el-table-column prop="amount" label="金额" /></el-table>
    <ClientPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @update:page-size="updatePageSize" />
  </section>
</template>

<style scoped>.toolbar { margin: 16px 0; }</style>
