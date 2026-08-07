<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as echarts from "echarts";

import { useAppStore } from "../stores/app";
import { getDashboardPhase2 } from "../api/dashboard";
const phase2 = ref<Record<string, any>>({});
onMounted(async () => { try { phase2.value = (await getDashboardPhase2(new Date().toISOString().slice(0, 7))).data?.data ?? {}; } catch { /* dashboard remains usable when API is unavailable */ } });

const chart = ref<HTMLDivElement>();
const app = useAppStore();
let chartInstance: echarts.ECharts | null = null;

function renderChart() {
  if (!chart.value) return;
  chartInstance?.dispose();
  chartInstance = echarts.init(chart.value, app.theme === "dark" ? "dark" : undefined);
  chartInstance.setOption({
    tooltip: { trigger: "axis" },
    legend: { data: ["销售额", "采购额"] },
    xAxis: { type: "category", data: ["周一", "周二", "周三", "周四", "周五", "周六", "周日"] },
    yAxis: { type: "value" },
    series: [
      { name: "销售额", type: "line", smooth: true, data: [0, 0, 0, 0, 0, 0, 0] },
      { name: "采购额", type: "line", smooth: true, data: [0, 0, 0, 0, 0, 0, 0] },
    ],
  });
}

onMounted(() => {
  app.applyTheme();
  nextTick(renderChart);
});
watch(() => app.theme, renderChart);
onBeforeUnmount(() => chartInstance?.dispose());
</script>

<template>
  <section>
    <el-page-header content="经营看板" />
    <el-row :gutter="16" class="metrics">
      <el-col :span="6"><el-card><div class="metric-label">本月销售额</div><strong>¥ 0.00</strong></el-card></el-col>
      <el-col :span="6"><el-card><div class="metric-label">本月采购额</div><strong>¥ 0.00</strong></el-card></el-col>
      <el-col :span="6"><el-card><div class="metric-label">应收余额</div><strong>¥ 0.00</strong></el-card></el-col>
      <el-col :span="6"><el-card><div class="metric-label">库存预警</div><strong>0</strong></el-card></el-col>
    </el-row>
    <el-card class="chart-card"><div ref="chart" class="chart-placeholder" /></el-card>
  </section>
</template>

<style scoped>
.metrics { margin: 16px 0; }
.metric-label { color: var(--erp-muted-text); margin-bottom: 10px; }
strong { font-size: 24px; color: var(--erp-text); }
.chart-card { min-height: 300px; }
.chart-placeholder { min-height: 260px; display: grid; place-items: center; color: var(--erp-muted-text); }
</style>
