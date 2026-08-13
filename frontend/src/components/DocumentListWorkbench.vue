<script setup lang="ts">
import { computed } from "vue";
import { Refresh, Search } from "@element-plus/icons-vue";

type Summary = { total?: number; amount?: string; statuses?: Record<string, { count: number; amount: string }> };
const props = withDefaults(defineProps<{
  title: string;
  keyword: string;
  status: string;
  dateRange: string[];
  summary?: Summary;
  total?: number;
  page: number;
  pageSize: number;
  loading?: boolean;
}>(), { summary: () => ({}), total: 0, loading: false });
const emit = defineEmits<{
  "update:keyword": [value: string];
  "update:status": [value: string];
  "update:dateRange": [value: string[]];
  "update:page": [value: number];
  "update:pageSize": [value: number];
  search: [];
  reset: [];
  refresh: [];
}>();
const preferredStatuses = ["draft", "submitted", "approved", "released", "in_progress", "partial", "partially_received", "confirmed", "posted", "completed", "passed", "failed", "open", "settled", "reversed", "cancelled"];
const statusMetrics = computed(() => {
  const statuses = props.summary?.statuses || {};
  const populated = preferredStatuses.filter((key) => Number(statuses[key]?.count || 0) > 0);
  const remaining = preferredStatuses.filter((key) => !populated.includes(key));
  return [...populated, ...remaining].slice(0, 4).map((key) => ({ key, count: statuses[key]?.count || 0, amount: statuses[key]?.amount || "0.00" }));
});
const labels: Record<string, string> = {
  draft: "草稿", submitted: "待审核", approved: "已审核", released: "已下达", in_progress: "进行中",
  confirmed: "已确认", posted: "已记账", completed: "已完成", passed: "已通过", failed: "未通过",
  open: "待处理", partial: "部分完成", partially_received: "部分收货", settled: "已结清",
  reversed: "已冲销", cancelled: "已取消",
};
</script>

<template>
  <section class="list-workbench">
    <header class="page-heading"><div><h1>{{ title }}</h1><p>统一查看状态、责任对象和最新业务进展</p></div><slot name="actions" /></header>
    <div class="metric-grid">
      <button class="metric-card metric-card-primary" type="button" @click="emit('update:status', ''); emit('search')"><span>全部单据</span><strong>{{ summary?.total || 0 }}</strong><small>含税金额 ¥{{ summary?.amount || '0.00' }}</small></button>
      <button v-for="metric in statusMetrics.slice(0, 4)" :key="metric.key" class="metric-card" type="button" @click="emit('update:status', metric.key); emit('search')"><span>{{ labels[metric.key] || metric.key }}</span><strong>{{ metric.count }}</strong><small>金额 ¥{{ metric.amount }}</small></button>
    </div>
    <el-card class="filter-card" shadow="never">
      <div class="filter-row">
        <el-input :model-value="keyword" clearable placeholder="检索单号、客户名称" class="keyword-input" @update:model-value="emit('update:keyword', String($event))" @keyup.enter="emit('search')"><template #prefix><el-icon><Search /></el-icon></template></el-input>
        <el-select :model-value="status" clearable placeholder="全部状态" style="width: 150px" @update:model-value="emit('update:status', String($event || ''))"><el-option v-for="(label, key) in labels" :key="key" :label="label" :value="key" /></el-select>
        <el-date-picker :model-value="dateRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始日期" end-placeholder="结束日期" style="width: 260px" @update:model-value="emit('update:dateRange', ($event || []) as string[])" />
        <el-button type="primary" @click="emit('search')">查询</el-button>
        <el-button @click="emit('reset')">重置</el-button>
        <el-button :icon="Refresh" :loading="loading" circle title="刷新" @click="emit('refresh')" />
      </div>
    </el-card>
    <el-card class="table-card" shadow="never"><slot /></el-card>
    <footer class="list-footer"><span>共 {{ total }} 条</span><el-pagination background :current-page="page" :page-size="pageSize" :page-sizes="[10, 20, 50, 100]" layout="sizes, prev, pager, next" :total="total" @update:current-page="emit('update:page', $event)" @update:page-size="emit('update:pageSize', $event)" /></footer>
  </section>
</template>

<style scoped>
.list-workbench { display: flex; flex-direction: column; gap: 14px; }
.page-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.page-heading h1 { margin: 0; color: var(--erp-text); font-size: 22px; }.page-heading p { margin: 7px 0 0; color: var(--erp-muted-text); font-size: 12px; }
.metric-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.metric-card { display: flex; min-height: 106px; flex-direction: column; align-items: flex-start; padding: 17px; border: 1px solid var(--erp-border); border-radius: var(--erp-radius); background: var(--erp-panel-bg); color: var(--erp-muted-text); text-align: left; box-shadow: var(--erp-shadow); cursor: pointer; }
.metric-card:hover { border-color: var(--erp-primary); transform: translateY(-1px); }
.metric-card strong { margin: 8px 0 5px; color: var(--erp-text); font-size: 24px; }
.metric-card small { color: var(--erp-subtle-text); }
.metric-card-primary { background: linear-gradient(135deg, color-mix(in srgb, var(--erp-primary) 14%, var(--erp-panel-bg)), var(--erp-panel-bg)); }
.filter-card :deep(.el-card__body), .table-card :deep(.el-card__body) { padding: 14px 16px; }
.filter-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.keyword-input { width: min(320px, 100%); }
.table-card { min-width: 0; }
.list-footer { display: flex; align-items: center; justify-content: space-between; color: var(--erp-muted-text); }
@media (max-width: 1100px) { .metric-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 720px) { .metric-grid { grid-template-columns: 1fr; } .list-footer { align-items: flex-start; flex-direction: column; gap: 10px; } }
</style>
