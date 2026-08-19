<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { BarChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import { init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { Bell, CircleCheck, TopRight, Wallet } from "@element-plus/icons-vue";

import { getDashboardOverview, getReportCenter } from "../api/dashboard";
import { useAppStore } from "../stores/app";
import { localMonthString } from "../utils/time";
import { statusLabel } from "../utils/labels";

const router = useRouter();
const app = useAppStore();
use([BarChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);
const period = ref(localMonthString());
const loading = ref(false);
const errorMessage = ref("");
type DashboardOverview = {
  period: string;
  sales_total: number | string;
  purchase_total: number | string;
  receivable_total: number | string;
  inventory_warning_count: number;
  sales_change: number;
  purchase_change: number;
  trend: Array<{ label: string; sales: number | string; purchase: number | string }>;
  tasks: Array<{ key: string; label: string; description: string; count: number; path: string }>;
  materials: Array<{ id: string; code: string; name: string; material_type: string; min_stock: number | string; status: string }>;
  sales_orders: Array<{ id: string; doc_no: string; customer_id: string; customer_name: string; total_amount: number | string; status: string }>;
};
function emptyOverview(): DashboardOverview { return { period: period.value, sales_total: 0, purchase_total: 0, receivable_total: 0, inventory_warning_count: 0, sales_change: 0, purchase_change: 0, trend: [], tasks: [], materials: [], sales_orders: [] }; }
const overview = ref<DashboardOverview>(emptyOverview());
const report = ref<Record<string, any>>({ metrics: {} });
const chart = ref<HTMLDivElement>();
let chartInstance: ECharts | null = null;

const periodOptions = computed(() => Array.from({ length: 12 }, (_, index) => {
  const dateValue = new Date();
  dateValue.setDate(1);
  dateValue.setMonth(dateValue.getMonth() - index);
  return localMonthString(dateValue);
}));

const periodLabel = computed(() => {
  const [year, month] = period.value.split("-");
  return `${year}年${month}月`;
});

const metrics = computed(() => [
  { label: "本期销售额", value: formatCurrency(overview.value.sales_total), trend: changeText(overview.value.sales_change), note: "较上期", tone: "rust", icon: TopRight },
  { label: "本期采购额", value: formatCurrency(overview.value.purchase_total), trend: changeText(overview.value.purchase_change), note: "较上期", tone: "green", icon: TopRight },
  { label: "应收余额", value: formatCurrency(overview.value.receivable_total), trend: "实时余额", note: "未结清", tone: "neutral", icon: Wallet },
  { label: "库存预警", value: String(overview.value.inventory_warning_count), trend: overview.value.inventory_warning_count ? `${overview.value.inventory_warning_count} 项` : "暂无预警", note: "需处理", tone: "danger", icon: Bell },
]);

function formatCurrency(value: number | string) {
  const amount = Number(value || 0);
  return `¥ ${amount.toLocaleString("zh-CN", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

function changeText(value: number) { return value === 0 ? "暂无环比" : `${value > 0 ? "↑" : "↓"} ${Math.abs(value)}%`; }

async function loadOverview() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const [response, reportResponse] = await Promise.all([getDashboardOverview(period.value), getReportCenter(period.value)]);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    overview.value = { ...emptyOverview(), ...(response.data.data as DashboardOverview) };
    if (reportResponse.data.code === 0) report.value = reportResponse.data.data || { metrics: {} };
  } catch (error) {
    overview.value = emptyOverview();
    errorMessage.value = error instanceof Error ? error.message : "经营看板加载失败，请稍后重试";
  } finally {
    loading.value = false;
  }
}

function renderChart() {
  if (!chart.value) return;
  chartInstance?.dispose();
  chartInstance = init(chart.value);
  chartInstance.setOption({
    animationDuration: 500,
    color: ["#c66d4b", "#ead2c5"],
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (value: number) => formatCurrency(value) },
    legend: { right: 0, top: 0, itemWidth: 10, itemHeight: 10, textStyle: { color: "#8e8276", fontSize: 11 }, data: ["销售额", "采购额"] },
    grid: { left: 6, right: 4, top: 34, bottom: 10, containLabel: true },
    xAxis: { type: "category", data: overview.value.trend.map((item) => item.label), axisTick: { show: false }, axisLine: { lineStyle: { color: "#e8dfd5" } }, axisLabel: { color: "#a2988e", fontSize: 11 } },
    yAxis: { type: "value", splitNumber: 3, axisLabel: { color: "#a2988e", fontSize: 10, formatter: (value: number) => `${Math.round(value / 10000)}万` }, splitLine: { lineStyle: { color: "#f0e8df", type: "dashed" } } },
    series: [
      { name: "销售额", type: "bar", barWidth: 12, barGap: "25%", data: overview.value.trend.map((item) => Number(item.sales)), itemStyle: { borderRadius: [6, 6, 0, 0] } },
      { name: "采购额", type: "bar", barWidth: 12, data: overview.value.trend.map((item) => Number(item.purchase)), itemStyle: { borderRadius: [6, 6, 0, 0] } },
    ],
  });
}

function go(path: string) { void router.push(path); }

onMounted(async () => {
  await loadOverview();
  await nextTick();
  renderChart();
  window.addEventListener("resize", handleResize);
});
watch(() => app.theme, () => nextTick(renderChart));
onBeforeUnmount(() => { chartInstance?.dispose(); window.removeEventListener("resize", handleResize); });
function handleResize() { chartInstance?.resize(); }
</script>

<template>
  <section class="dashboard-page">
    <div class="dashboard-heading">
      <div>
        <div class="eyebrow">OPERATING PULSE · {{ periodLabel }}</div>
        <h1>经营看板</h1>
      </div>
      <div class="period-picker"><span>查看</span><el-select v-model="period" size="default" @change="loadOverview"><el-option v-for="item in periodOptions" :key="item" :label="item" :value="item" /></el-select></div>
    </div>

    <div v-loading="loading" class="dashboard-grid">
      <el-alert v-if="errorMessage" class="dashboard-error" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''" />
      <el-card v-for="metric in metrics" :key="metric.label" class="metric-card" shadow="never">
        <div class="metric-top"><span>{{ metric.label }}</span><el-icon :class="`metric-icon ${metric.tone}`"><component :is="metric.icon" /></el-icon></div>
        <div class="metric-value">{{ metric.value }}<small v-if="metric.label === '库存预警'"> 项</small></div>
        <div :class="['metric-trend', metric.tone === 'danger' ? 'is-danger' : '']"><span>{{ metric.trend }}</span><em>{{ metric.note }}</em></div>
      </el-card>

      <el-card class="chart-card" shadow="never">
        <div class="card-heading"><span>销售与采购的节奏</span><small>近 7 日</small></div>
        <div ref="chart" class="chart" />
      </el-card>

      <el-card class="todo-card" shadow="never">
        <div class="card-heading"><span>待处理事项</span></div>
        <button v-for="(task, index) in overview.tasks" :key="task.key" class="todo-item" type="button" @click="go(task.path)"><span class="todo-index">{{ index + 1 }}</span><span class="todo-body"><strong>{{ task.label }}</strong><small>{{ task.description }} · {{ task.count }} 条待处理</small></span><b>{{ task.count }}</b></button>
        <el-empty v-if="!overview.tasks.length" description="暂无待处理事项" :image-size="56" />
      </el-card>

      <el-card class="module-card report-card" shadow="never"><div class="module-header"><div><span class="module-title">报表中心</span><small>经营指标定义统一、可直接导出</small></div><el-button size="small" @click="loadOverview">刷新指标</el-button></div><div class="report-grid"><div><small>履约率</small><strong>{{ report.metrics?.fulfillment_rate || 0 }}%</strong></div><div><small>库存价值</small><strong>{{ formatCurrency(report.metrics?.inventory_value || 0) }}</strong></div><div><small>逾期应收</small><strong>{{ formatCurrency(report.metrics?.overdue_receivable || 0) }}</strong></div><div><small>生产完成率</small><strong>{{ report.metrics?.production_completion_rate || 0 }}%</strong></div><div><small>不合格检验</small><strong>{{ report.metrics?.failed_inspections || 0 }}</strong></div></div></el-card>

      <el-card class="module-card" shadow="never">
        <div class="module-header"><div><button class="module-title" type="button" @click="go('/master-data/materials')">物料档案</button><small>管理物料、价格与安全库存</small></div><el-button type="primary" size="small" @click="go('/master-data/materials')">新增物料</el-button></div>
        <div class="module-body"><div class="mini-toolbar"><el-button size="small" @click="go('/master-data/materials')">打开物料档案</el-button></div><table class="preview-table"><thead><tr><th>物料编码</th><th>物料名称</th><th>类型</th><th>安全库存</th><th>状态</th></tr></thead><tbody><tr v-for="row in overview.materials" :key="row.id"><td>{{ row.code }}</td><td>{{ row.name }}</td><td>{{ row.material_type }}</td><td>{{ row.min_stock }}</td><td><span :class="['status-tag', row.status === 'active' ? 'green' : '']">{{ row.status === 'active' ? '启用' : '停用' }}</span></td></tr></tbody></table><el-empty v-if="!overview.materials.length" description="暂无物料" :image-size="56" /></div>
      </el-card>

      <el-card class="module-card" shadow="never">
        <div class="module-header"><div><button class="module-title" type="button" @click="go('/sales/orders')">销售订单</button><small>从草稿到出库的工作流</small></div><el-button type="primary" size="small" @click="go('/sales/orders')">新建订单</el-button></div>
        <div class="module-body"><div class="mini-toolbar"><el-button size="small" @click="go('/sales/orders')">打开销售订单</el-button></div><table class="preview-table"><thead><tr><th>订单号</th><th>客户</th><th>含税金额</th><th>状态</th><th>操作</th></tr></thead><tbody><tr v-for="row in overview.sales_orders" :key="row.id"><td>{{ row.doc_no }}</td><td>{{ row.customer_name || row.customer_id }}</td><td>{{ formatCurrency(row.total_amount) }}</td><td><span :class="['status-tag', row.status === 'approved' ? 'green' : 'amber']">{{ statusLabel(row.status) }}</span></td><td><button class="table-link" type="button" @click="go(`/documents/sales_order/${row.id}`)">查看</button></td></tr></tbody></table><el-empty v-if="!overview.sales_orders.length" description="暂无本期订单" :image-size="56" /></div>
      </el-card>
    </div>

    <div class="dashboard-foot"><el-icon><CircleCheck /></el-icon>方向 C · 暖石运营 <span>/</span> 在保持 ERP 专业度的前提下，建立更有品牌识别度的运营体验</div>
  </section>
</template>

<style scoped>
.dashboard-page { min-width: 0; }
.dashboard-heading { display: flex; align-items: end; justify-content: space-between; margin-bottom: 20px; }
.eyebrow { color: var(--erp-muted-text); font-size: 11px; letter-spacing: .09em; }
h1 { margin: 4px 0 0; color: var(--erp-text); font-size: 26px; line-height: 1.2; }
.period-picker { display: flex; align-items: center; gap: 9px; color: var(--erp-muted-text); }
.period-picker :deep(.el-select) { width: 130px; }
.period-picker :deep(.el-select__wrapper) { border-radius: 9px; }
.dashboard-grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 15px; }
.dashboard-error { grid-column: span 12; }
.metric-card { grid-column: span 3; min-height: 120px; padding: 17px; }
.metric-card :deep(.el-card__body) { padding: 0; }
.metric-top, .card-heading, .module-header, .metric-trend { display: flex; align-items: center; justify-content: space-between; }
.metric-top { color: var(--erp-muted-text); font-size: 12px; }
.metric-icon { font-size: 17px; }
.metric-icon.rust { color: var(--erp-primary); }
.metric-icon.green { color: var(--erp-green); }
.metric-icon.neutral { color: var(--erp-muted-text); }
.metric-icon.danger { color: var(--erp-danger); }
.metric-value { margin: 13px 0 6px; color: var(--erp-text); font-size: 25px; font-weight: 760; line-height: 1; }
.metric-value small { color: var(--erp-muted-text); font-size: 13px; font-weight: 500; }
.metric-trend { justify-content: flex-start; gap: 6px; color: var(--erp-green); font-size: 11px; }
.metric-trend em { color: var(--erp-subtle-text); font-style: normal; }
.metric-trend.is-danger { color: var(--erp-danger); }
.chart-card, .todo-card { min-height: 278px; }
.chart-card { grid-column: span 8; padding: 17px; }
.todo-card { grid-column: span 4; padding: 17px; }
.chart-card :deep(.el-card__body), .todo-card :deep(.el-card__body) { padding: 0; }
.card-heading { margin-bottom: 12px; color: #493d35; font-size: 15px; font-weight: 700; }
.card-heading small { color: var(--erp-subtle-text); font-size: 11px; font-weight: 400; }
.text-link { color: var(--erp-primary-dark); font-size: 11px; }
.chart { width: 100%; height: 220px; }
.todo-item { display: flex; align-items: center; width: 100%; gap: 10px; padding: 13px 0; border: 0; border-bottom: 1px solid var(--erp-border-soft); background: transparent; text-align: left; color: inherit; cursor: pointer; }
.todo-item:last-child { border-bottom: 0; }
.todo-item:hover .todo-body strong, .table-link:hover, .module-title:hover { color: var(--erp-primary-dark); }
.todo-index { display: grid; place-items: center; flex: 0 0 21px; width: 21px; height: 21px; border-radius: 50%; background: #f6e7de; color: var(--erp-primary-dark); font-size: 11px; }
.todo-body { display: flex; flex: 1; flex-direction: column; gap: 3px; }
.todo-body strong { color: #54483e; font-size: 13px; font-weight: 600; }
.todo-body small { color: var(--erp-subtle-text); font-size: 11px; }
.todo-item b { color: #493d35; font-size: 15px; }
.module-card { grid-column: span 6; min-height: 286px; overflow: hidden; }
.report-card { grid-column: span 12; min-height: 150px; }
.report-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; padding: 16px 17px; }
.report-grid > div { padding: 12px; border: 1px solid var(--erp-border-soft); border-radius: 10px; background: var(--erp-panel-soft); }
.report-grid small { display: block; color: var(--erp-muted-text); font-size: 11px; }
.report-grid strong { display: block; margin-top: 8px; color: var(--erp-text); font-size: 18px; }
.module-card :deep(.el-card__body) { padding: 0; }
.module-header { align-items: center; padding: 16px 17px; border-bottom: 1px solid var(--erp-border-soft); }
.module-header > div { display: flex; flex-direction: column; gap: 4px; }
.module-title { padding: 0; border: 0; background: transparent; color: #493d35; font-size: 16px; font-weight: 720; cursor: pointer; text-align: left; }
.module-header small { color: var(--erp-subtle-text); font-size: 11px; }
.module-body { padding: 14px 17px; }
.mini-toolbar { display: flex; gap: 7px; margin-bottom: 10px; }
.mini-toolbar :deep(.el-input), .mini-toolbar :deep(.el-select) { min-width: 0; flex: 1; }
.mini-toolbar :deep(.el-select) { max-width: 96px; }
.preview-table { width: 100%; border-collapse: collapse; color: #5a4f46; font-size: 11px; }
.preview-table th { padding: 8px 6px; border-bottom: 1px solid #e7ddd2; color: var(--erp-muted-text); font-weight: 500; text-align: left; }
.preview-table td { padding: 11px 6px; border-bottom: 1px solid var(--erp-border-soft); white-space: nowrap; }
.preview-table tr:last-child td { border-bottom: 0; }
.status-tag { display: inline-flex; padding: 4px 8px; border-radius: 999px; background: #f2e6dc; color: #a45b40; font-size: 10px; }
.status-tag.green { background: var(--erp-green-bg); color: var(--erp-green); }
.status-tag.amber { background: var(--erp-amber-bg); color: var(--erp-amber); }
.table-link { padding: 0; border: 0; background: transparent; color: var(--erp-primary-dark); cursor: pointer; font-size: 11px; }
.dashboard-foot { display: flex; align-items: center; gap: 7px; padding-top: 16px; color: var(--erp-subtle-text); font-size: 11px; }
.dashboard-foot .el-icon { color: var(--erp-green); }
.dashboard-foot span { color: var(--erp-border); }
@media (max-width: 1100px) { .metric-card { grid-column: span 6; } .chart-card, .todo-card { grid-column: span 12; } .module-card { grid-column: span 12; } }
@media (max-width: 620px) { .dashboard-heading { align-items: flex-start; flex-direction: column; gap: 14px; } .metric-card { grid-column: span 12; } .mini-toolbar { flex-wrap: wrap; } .mini-toolbar :deep(.el-input) { flex-basis: 100%; } .report-grid { grid-template-columns: repeat(2, 1fr); } }
</style>
