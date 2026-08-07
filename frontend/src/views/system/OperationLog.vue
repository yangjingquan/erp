<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { listOperationLogs, type OperationLog as OperationLogRow } from "../../api/system";

const rows = ref<OperationLogRow[]>([]);
const loading = ref(false);
const errorMessage = ref("");

function responseRows(response: any): OperationLogRow[] {
  if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "操作日志接口返回失败");
  const data = response.data.data;
  return Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : [];
}

async function load() {
  loading.value = true;
  errorMessage.value = "";
  try {
    rows.value = responseRows(await listOperationLogs());
  } catch (error) {
    rows.value = [];
    errorMessage.value = error instanceof Error ? error.message : "操作日志加载失败，请稍后重试";
    ElMessage.error(errorMessage.value);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="page-stack">
    <el-page-header content="操作日志" />
    <el-space class="toolbar">
      <el-button :loading="loading" @click="load">刷新</el-button>
    </el-space>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''" />
    <el-table v-loading="loading" :data="rows" stripe>
      <el-table-column prop="created_at" label="时间" min-width="180" />
      <el-table-column prop="username" label="用户" width="140" />
      <el-table-column prop="action" label="动作" width="140" />
      <el-table-column prop="resource" label="资源" min-width="180" />
      <template #empty><el-empty description="暂无操作日志" /></template>
    </el-table>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.toolbar { margin: 0; }
</style>
