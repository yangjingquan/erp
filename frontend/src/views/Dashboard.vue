<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import * as echarts from "echarts";
import { Bell, CircleCheck, DataAnalysis, TopRight, Wallet } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

import { getDashboardOverview } from "../api/dashboard";
import { useAppStore } from "../stores/app";

const router = useRouter();
const app = useAppStore();
const period = ref(new Date().toISOString().slice(0, 7));
const loading = ref(false);
const overview = ref({ sales_total: 1286430, purchase_total: 698240, inventory_warning_count: 12, receivable_total: 426800 });
const chart = ref<HTMLDivElement>();
let chartInstance: echarts.ECharts | null = null;

const periodLabel = computed(() => {
  const [year, month] = period.value.split("-");
  return `${year}年${month}月`;
});

const metrics = computed(() => [
  { label: "本月销售额", value: formatCurrency(overview.value.sales_total), trend: "↑ 12.8%", note: "较上月", tone: "rust", icon: TopRight },
  { label: "本月采购额", value: formatCurrency(overview.value.purchase_total), trend: "↑ 4.6%", note: "较上月", tone: "green", icon: TopRight },
  { label: "应收余额", value: formatCurrency(overview.value.receivable_total), trend: "↓ 6.2%", note: "较上月", tone: "neutral", icon: Wallet },
  { label: "库存预警", value: String(overview.value.inventory_warning_count), trend: "4 项高风险", note: "需处理", tone: "danger", icon: Bell },
]);

function formatCurrency(value: number | string) {
  const amount = Number(value || 0);
  return `¥ ${amount.toLocaleString("zh-CN", { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

async function loadOverview() {
  loading.value = true;
  try {
    const response = await getDashboardOverview();
    if (response.data.code !== 0) throw new Error(response.data.msg);
    const data = response.data.data as Record<string, unknown>;
    overview.value = {
      ...overview.value,
      sales_total: Number(data.sales_total ?? overview.value.sales_total),
      purchase_total: Number(data.purchase_total ?? overview.value.purchase_total),
      inventory_warning_count: Number(data.inventory_warning_count ?? overview.value.inventory_warning_count),
    };
  } catch {
    // The dashboard keeps its designed preview state when the API is not available.
  } finally {
    loading.value = false;
  }
}

function renderChart() {
  if (!chart.value) return;
  chartInstance?.dispose();
  chartInstance = echarts.init(chart.value);
  chartInstance.setOption({
    animationDuration: 500,
    color: ["#c66d4b", "#ead2c5"],
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, valueFormatter: (value: number) => formatCurrency(value) },
    legend: { right: 0, top: 0, itemWidth: 10, itemHeight: 10, textStyle: { color: "#8e8276", fontSize: 11 }, data: ["销售额", "采购额"] },
    grid: { left: 6, right: 4, top: 34, bottom: 10, containLabel: true },
    xAxis: { type: "category", data: ["08/01", "08/02", "08/03", "08/04", "08/05", "08/06", "08/07"], axisTick: { show: false }, axisLine: { lineStyle: { color: "#e8dfd5" } }, axisLabel: { color: "#a2988e", fontSize: 11 } },
    yAxis: { type: "value", splitNumber: 3, axisLabel: { color: "#a2988e", fontSize: 10, formatter: (value: number) => `${Math.round(value / 10000)}万` }, splitLine: { lineStyle: { color: "#f0e8df", type: "dashed" } } },
    series: [
      { name: "销售额", type: "bar", barWidth: 12, barGap: "25%", data: [42000, 56000, 49000, 72000, 64000, 83000, 76000], itemStyle: { borderRadius: [6, 6, 0, 0] } },
      { name: "采购额", type: "bar", barWidth: 12, data: [26000, 35000, 31000, 46000, 41000, 54000, 48000], itemStyle: { borderRadius: [6, 6, 0, 0] } },
    ],
  });
}

function go(path: string) { void router.push(path); }
function showAllTasks() { ElMessage.info("待处理事项已按优先级展示"); }

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
        <div class="eyebrow">OPERATING PULSE · AUGUST 2026</div>
        <h1>经营看板</h1>
      </div>
      <div class="period-picker"><span>查看</span><el-select v-model="period" size="default" @change="loadOverview"><el-option :label="periodLabel" :value="period" /></el-select></div>
    </div>

    <div v-loading="loading" class="dashboard-grid">
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
        <div class="card-heading"><span>今天要处理的事</span><el-button link class="text-link" @click="showAllTasks">查看全部 →</el-button></div>
        <button class="todo-item" type="button" @click="go('/sales/orders')"><span class="todo-index">1</span><span class="todo-body"><strong>销售订单待审核</strong><small>销售管理 · 4 条待处理</small></span><b>4</b></button>
        <button class="todo-item" type="button" @click="go('/inventory/stock')"><span class="todo-index">2</span><span class="todo-body"><strong>库存低于安全线</strong><small>库存管理 · 12 项预警</small></span><b>12</b></button>
        <button class="todo-item" type="button" @click="go('/finance/receivables')"><span class="todo-index">3</span><span class="todo-body"><strong>应收账款逾期</strong><small>财务管理 · 3 笔逾期</small></span><b>3</b></button>
      </el-card>

      <el-card class="module-card" shadow="never">
        <div class="module-header"><div><button class="module-title" type="button" @click="go('/master-data/materials')">物料档案</button><small>管理物料、价格与安全库存</small></div><el-button type="primary" size="small" @click="go('/master-data/materials')">新增物料</el-button></div>
        <div class="module-body"><div class="mini-toolbar"><el-input size="small" placeholder="搜索编码或名称" /><el-select size="small" placeholder="分类"><el-option label="全部分类" value="all" /></el-select><el-button size="small" @click="go('/master-data/materials')">导出</el-button></div><table class="preview-table"><thead><tr><th>物料编码</th><th>物料名称</th><th>类型</th><th>安全库存</th><th>状态</th></tr></thead><tbody><tr><td>MAT-2024-001</td><td>铝合金外壳</td><td>原材料</td><td>500</td><td><span class="status-tag green">启用</span></td></tr><tr><td>MAT-2024-018</td><td>控制面板组件</td><td>半成品</td><td>120</td><td><span class="status-tag green">启用</span></td></tr><tr><td>MAT-2024-032</td><td>工业连接器</td><td>商品</td><td>80</td><td><span class="status-tag">启用</span></td></tr></tbody></table></div>
      </el-card>

      <el-card class="module-card" shadow="never">
        <div class="module-header"><div><button class="module-title" type="button" @click="go('/sales/orders')">销售订单</button><small>从草稿到出库的工作流</small></div><el-button type="primary" size="small" @click="go('/sales/orders')">新建订单</el-button></div>
        <div class="module-body"><div class="mini-toolbar"><el-input size="small" placeholder="搜索订单或客户" /><el-select size="small" placeholder="状态"><el-option label="全部状态" value="all" /></el-select><el-button size="small" @click="go('/sales/orders')">刷新</el-button></div><table class="preview-table"><thead><tr><th>订单号</th><th>客户</th><th>含税金额</th><th>状态</th><th>操作</th></tr></thead><tbody><tr><td>SO-20260807-08</td><td>华东精工</td><td>¥86,400</td><td><span class="status-tag amber">待审核</span></td><td><button class="table-link" type="button" @click="go('/sales/orders')">审核</button></td></tr><tr><td>SO-20260806-14</td><td>启明科技</td><td>¥52,800</td><td><span class="status-tag green">已审核</span></td><td><button class="table-link" type="button" @click="go('/sales/orders')">出库</button></td></tr><tr><td>SO-20260805-21</td><td>南方机电</td><td>¥31,200</td><td><span class="status-tag">草稿</span></td><td><button class="table-link" type="button" @click="go('/sales/orders')">提交</button></td></tr></tbody></table></div>
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
@media (max-width: 620px) { .dashboard-heading { align-items: flex-start; flex-direction: column; gap: 14px; } .metric-card { grid-column: span 12; } .mini-toolbar { flex-wrap: wrap; } .mini-toolbar :deep(.el-input) { flex-basis: 100%; } }
</style>
