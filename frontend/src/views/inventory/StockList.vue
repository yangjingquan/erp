<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { listInventoryStock, listInventoryWarnings } from "../../api/inventory";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const warningRows = ref<Row[]>([]);
const loading = ref(false);
const errorMessage = ref("");

function listFrom(response: any): Row[] {
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

onMounted(load);
</script>

<template>
  <section>
    <el-page-header content="库存台账" />
    <el-space class="toolbar"><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''"><template #default><el-button link type="primary" @click="load">重新加载</el-button></template></el-alert>
    <el-alert v-if="warningRows.length" :title="`当前有 ${warningRows.length} 条库存低于安全库存`" type="warning" show-icon />
    <el-table v-if="warningRows.length" :data="warningRows" stripe class="warning-table"><el-table-column prop="warehouse_id" label="仓库" /><el-table-column prop="material_id" label="物料" /><el-table-column prop="current_quantity" label="当前库存" /><el-table-column prop="min_quantity" label="安全库存" /></el-table>
    <el-table v-loading="loading" :data="rows" stripe><el-table-column prop="warehouse_id" label="仓库" /><el-table-column prop="material_id" label="物料" /><el-table-column prop="quantity" label="库存数量" /><el-table-column prop="available_quantity" label="可用数量" /></el-table>
  </section>
</template>

<style scoped>
.toolbar { margin: 16px 0; }
.warning-table { margin: 16px 0; }
</style>
