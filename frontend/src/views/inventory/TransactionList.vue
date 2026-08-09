<script setup lang="ts">
import { onMounted, ref } from "vue";
import { listInventoryTransactions } from "../../api/inventory";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
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
    <el-button class="toolbar" :loading="loading" @click="load">刷新</el-button>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''"><template #default><el-button link type="primary" @click="load">重新加载</el-button></template></el-alert>
    <el-table v-loading="loading" :data="rows" stripe width="100%" fit><el-table-column prop="source_type" label="来源类型" /><el-table-column prop="source_id" label="来源单据" /><el-table-column prop="direction" label="方向" /><el-table-column prop="quantity" label="数量" /><el-table-column prop="amount" label="金额" /></el-table>
  </section>
</template>

<style scoped>.toolbar { margin: 16px 0; }</style>
