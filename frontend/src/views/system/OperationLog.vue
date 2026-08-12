<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { listOperationLogs, type OperationLog as OperationLogRow } from "../../api/system";
import { formatLocalDateTime } from "../../utils/time";

const rows = ref<OperationLogRow[]>([]);
const currentPage = ref(1);
const pageSize = ref(20);
const totalRows = ref(0);
const loading = ref(false);
const errorMessage = ref("");

function responsePage(response: any) {
  if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "操作日志接口返回失败");
  const data = response.data.data;
  if (Array.isArray(data)) return { items: data, total: data.length };
  return {
    items: Array.isArray(data?.items) ? data.items : [],
    total: Number(data?.total || 0),
  };
}

async function load(page = currentPage.value) {
  currentPage.value = page;
  loading.value = true;
  errorMessage.value = "";
  try {
    const result = responsePage(await listOperationLogs(currentPage.value, pageSize.value));
    rows.value = result.items;
    totalRows.value = result.total;
  } catch (error) {
    rows.value = [];
    totalRows.value = 0;
    errorMessage.value = error instanceof Error ? error.message : "操作日志加载失败，请稍后重试";
    ElMessage.error(errorMessage.value);
  } finally {
    loading.value = false;
  }
}

function handlePageSizeChange(size: number) {
  pageSize.value = size;
  currentPage.value = 1;
  void load(1);
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
    <el-table v-loading="loading" :data="rows" stripe width="100%" fit>
      <el-table-column label="时间" min-width="180"><template #default="scope">{{ formatLocalDateTime(scope.row.created_at) }}</template></el-table-column>
      <el-table-column prop="username" label="用户" width="140" />
      <el-table-column prop="action" label="动作" width="140" />
      <el-table-column prop="resource" label="资源" min-width="180" />
      <template #empty><el-empty description="暂无操作日志" /></template>
    </el-table>
    <div v-if="totalRows > 0" class="pagination-wrap">
      <span>显示 {{ (currentPage - 1) * pageSize + 1 }} - {{ Math.min(currentPage * pageSize, totalRows) }} / 共 {{ totalRows }} 条</span>
      <el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :page-sizes="[10, 20, 50]" layout="sizes, prev, pager, next" :total="totalRows" @size-change="handlePageSizeChange" @current-change="load" />
    </div>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.toolbar { margin: 0; }
.pagination-wrap { display: flex; align-items: center; justify-content: space-between; gap: 12px; color: var(--erp-muted-text); font-size: 12px; }
.pagination-wrap :deep(.el-pagination) { padding: 0; }
@media (max-width: 720px) { .pagination-wrap { align-items: flex-start; flex-direction: column; } }
</style>
