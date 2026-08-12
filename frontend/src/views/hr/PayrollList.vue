<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { approvePayroll, calculatePayroll, listPayroll, payPayroll } from "../../api/hr";
import { localMonthString } from "../../utils/time";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const period = ref(localMonthString());
const loading = ref(false);
const saving = ref(false);
function validPeriod(value: string) { return /^\d{4}-(0[1-9]|1[0-2])$/.test(value); }
async function load() { loading.value = true; try { const response = await listPayroll(validPeriod(period.value) ? period.value : undefined); if (response.data.code !== 0) throw new Error(response.data.msg); rows.value = Array.isArray(response.data?.data) ? response.data.data : []; } catch (error) { ElMessage.error(error instanceof Error ? error.message : "薪资列表加载失败"); } finally { loading.value = false; } }
async function calculate() { if (!validPeriod(period.value)) { ElMessage.warning("薪资期间必须为 YYYY-MM，例如 2026-08"); return; } saving.value = true; try { const response = await calculatePayroll(period.value); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("薪资已计算"); await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "薪资计算失败"); } finally { saving.value = false; } }
async function approve(row: Row) { if (!row.id || row.status !== "calculated") return; saving.value = true; try { const response = await approvePayroll(row.id); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("薪资批次已审批"); await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "薪资审批失败"); } finally { saving.value = false; } }
async function pay(row: Row) { if (!row.id || row.status !== "approved") return; try { await ElMessageBox.confirm(`确认支付 ${row.period} 薪资 ${row.total_amount} 元吗？`, "支付确认", { type: "warning" }); saving.value = true; const response = await payPayroll(row.id); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("薪资已支付"); await load(); } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "薪资支付失败"); } finally { saving.value = false; } }
onMounted(load);
</script>

<template>
  <section class="page-stack"><el-page-header content="薪资管理" /><el-space><el-date-picker v-model="period" type="month" value-format="YYYY-MM" placeholder="选择薪资期间" clearable style="width: 180px" /><el-button type="primary" :loading="saving" @click="calculate">计算薪资</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space><el-alert title="薪资必须按 YYYY-MM 期间计算，并按“已计算 → 已审批 → 已支付”顺序操作。" type="info" show-icon /><el-table v-loading="loading" :data="rows" stripe width="100%" fit><el-table-column prop="period" label="薪资期间" width="140" /><el-table-column prop="total_amount" label="应付总额" min-width="160" /><el-table-column prop="status" label="状态" width="120" /><el-table-column label="操作" width="220"><template #default="scope"><el-button v-if="scope.row.status === 'calculated'" link type="success" :loading="saving" @click="approve(scope.row)">审批</el-button><el-button v-if="scope.row.status === 'approved'" link type="primary" :loading="saving" @click="pay(scope.row)">支付</el-button></template></el-table-column><template #empty><el-empty description="暂无薪资批次" /></template></el-table></section>
</template>

<style scoped>.page-stack { display: flex; flex-direction: column; gap: 16px; }</style>
