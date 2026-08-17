<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  createAlternateMaterial,
  createWorkOrderException,
  createWorkOrderSchedule,
  listAlternateMaterials,
  listWorkCenters,
  listWorkOrderExceptions,
  listWorkOrderSchedules,
  listWorkOrders,
  resolveWorkOrderException,
} from "../../api/production";
import { useMasterOptions } from "../../composables/useMasterOptions";
import { statusLabel } from "../../utils/labels";

type Row = Record<string, any>;
const workOrders = ref<Row[]>([]);
const workCenters = ref<Row[]>([]);
const schedules = ref<Row[]>([]);
const alternates = ref<Row[]>([]);
const exceptions = ref<Row[]>([]);
const selectedWorkOrderId = ref("");
const loading = ref(false);
const saving = ref(false);
const scheduleForm = reactive({ operation_id: "", work_center_id: "", schedule_date: new Date().toISOString().slice(0, 10), scheduled_hours: 1, override_capacity: false });
const alternateForm = reactive({ material_id: "", alternate_material_id: "", conversion_rate: 1, reason: "" });
const exceptionForm = reactive({ exception_type: "", description: "" });
const { materials, loadOptions } = useMasterOptions();
const orderMaterials = computed(() => selectedOrder()?.materials || []);
const orderOperations = computed(() => selectedOrder()?.routing_snapshot?.operations || []);

function materialLabel(id: unknown) { const value = String(id || ""); return materials.value.find((item) => item.value === value)?.label || value || "-"; }
function centerLabel(id: unknown) { const value = String(id || ""); const center = workCenters.value.find((item) => String(item.id) === value); return center ? `${center.code} · ${center.name}` : value || "-"; }
function operationLabel(id: unknown) { const value = String(id || ""); const operation = orderOperations.value.find((item: Row) => String(item.id) === value); return operation ? `${operation.line_no}. ${operation.operation_name}` : value || "未指定"; }
function workOrderLabel(row: Row) { return `${row.doc_no} · ${materialLabel(row.material_id)} · ${statusLabel(row.status)}`; }
function changeOperation(operationId: string) { scheduleForm.operation_id = operationId; const operation = orderOperations.value.find((item: Row) => String(item.id) === String(operationId)); if (operation?.work_center_id) scheduleForm.work_center_id = String(operation.work_center_id); }
function changeWorkOrder() { scheduleForm.operation_id = ""; scheduleForm.work_center_id = ""; alternateForm.material_id = ""; alternateForm.alternate_material_id = ""; loadDetail(); }

function unwrap(response: any) {
  if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "生产执行接口失败");
  return response.data.data;
}
function selectedOrder() { return workOrders.value.find((item) => String(item.id) === selectedWorkOrderId.value); }
async function loadDetail() {
  if (!selectedWorkOrderId.value) { schedules.value = []; alternates.value = []; exceptions.value = []; return; }
  const [scheduleResponse, alternateResponse, exceptionResponse] = await Promise.all([
    listWorkOrderSchedules(selectedWorkOrderId.value),
    listAlternateMaterials(selectedWorkOrderId.value),
    listWorkOrderExceptions(selectedWorkOrderId.value),
  ]);
  schedules.value = unwrap(scheduleResponse)?.items || [];
  alternates.value = unwrap(alternateResponse) || [];
  exceptions.value = unwrap(exceptionResponse) || [];
  const orderMaterials = selectedOrder()?.materials || [];
  if (!alternateForm.material_id && orderMaterials.length) alternateForm.material_id = String(orderMaterials[0].material_id);
}
async function load() {
  loading.value = true;
  try {
    const [orderResponse, centerResponse] = await Promise.all([listWorkOrders(), listWorkCenters()]);
    workOrders.value = unwrap(orderResponse) || [];
    workCenters.value = unwrap(centerResponse) || [];
    if (!selectedWorkOrderId.value && workOrders.value.length) selectedWorkOrderId.value = String(workOrders.value[0].id);
    await loadDetail();
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "生产执行数据加载失败"); }
  finally { loading.value = false; }
}
async function saveSchedule() {
  if (!selectedWorkOrderId.value || !scheduleForm.work_center_id || scheduleForm.scheduled_hours <= 0) { ElMessage.warning("请选择工单、工作中心并填写计划工时"); return; }
  saving.value = true;
  try { unwrap(await createWorkOrderSchedule(selectedWorkOrderId.value, scheduleForm)); ElMessage.success("工单排程已保存"); await loadDetail(); }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : "工单排程保存失败"); }
  finally { saving.value = false; }
}
async function saveAlternate() {
  if (!selectedWorkOrderId.value || !alternateForm.material_id || !alternateForm.alternate_material_id || alternateForm.conversion_rate <= 0) { ElMessage.warning("请填写主料、替代料和转换率"); return; }
  saving.value = true;
  try { unwrap(await createAlternateMaterial(selectedWorkOrderId.value, alternateForm)); ElMessage.success("替代料已保存"); await loadDetail(); }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : "替代料保存失败"); }
  finally { saving.value = false; }
}
async function saveException() {
  if (!selectedWorkOrderId.value || !exceptionForm.exception_type.trim() || !exceptionForm.description.trim()) { ElMessage.warning("请填写异常类型和描述"); return; }
  saving.value = true;
  try { unwrap(await createWorkOrderException(selectedWorkOrderId.value, exceptionForm)); exceptionForm.exception_type = ""; exceptionForm.description = ""; ElMessage.success("生产异常已上报"); await loadDetail(); }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : "生产异常上报失败"); }
  finally { saving.value = false; }
}
async function resolveException(row: Row) {
  try {
    const result = await ElMessageBox.prompt("请输入处理结果", "关闭生产异常", { inputPlaceholder: "例如：已更换设备并完成试产" });
    unwrap(await resolveWorkOrderException(String(row.id), { resolution: result.value })); ElMessage.success("生产异常已关闭"); await loadDetail();
  } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "生产异常关闭失败"); }
}
onMounted(async () => { await Promise.all([loadOptions(["materials"]), load()]); });
</script>

<template>
  <section class="page-stack">
    <header class="page-heading"><div><small>SHOPFLOOR EXECUTION</small><h1>生产执行控制台</h1><p>统一管理工单排程、替代料和车间异常，支持现场执行闭环。</p></div><el-button :loading="loading" @click="load">刷新</el-button></header>
    <el-card shadow="never"><div class="toolbar"><el-select v-model="selectedWorkOrderId" placeholder="请选择生产工单" clearable filterable style="width: 420px" @change="changeWorkOrder"><el-option v-for="item in workOrders" :key="String(item.id)" :label="workOrderLabel(item)" :value="String(item.id)" /></el-select><el-tag v-if="selectedOrder()" type="info">计划数量：{{ selectedOrder()?.quantity }}</el-tag></div><el-alert v-if="!workOrders.length && !loading" title="当前没有可执行工单，请先在生产工单页面创建或下达工单。" type="info" :closable="false" /></el-card>
    <el-card shadow="never"><template #header>工单排程</template><div class="form-grid"><el-select :model-value="scheduleForm.operation_id" placeholder="工序（可选）" clearable filterable @update:model-value="changeOperation"><el-option v-for="item in orderOperations" :key="String(item.id)" :label="`${item.line_no}. ${item.operation_name}`" :value="String(item.id)" /></el-select><el-select v-model="scheduleForm.work_center_id" placeholder="工作中心" filterable><el-option v-for="item in workCenters" :key="String(item.id)" :label="centerLabel(item.id)" :value="String(item.id)" /></el-select><el-date-picker v-model="scheduleForm.schedule_date" value-format="YYYY-MM-DD" type="date" placeholder="排程日期" /><el-input-number v-model="scheduleForm.scheduled_hours" :min="0.01" :precision="2" /><el-switch v-model="scheduleForm.override_capacity" active-text="允许超产能" /><el-button type="primary" :loading="saving" :disabled="!selectedWorkOrderId" @click="saveSchedule">保存排程</el-button></div><el-table :data="schedules" stripe><el-table-column prop="schedule_date" label="日期" /><el-table-column label="工序"><template #default="scope">{{ operationLabel(scope.row.operation_id) }}</template></el-table-column><el-table-column label="工作中心"><template #default="scope">{{ centerLabel(scope.row.work_center_id) }}</template></el-table-column><el-table-column prop="scheduled_hours" label="计划工时" /><el-table-column prop="actual_hours" label="实际工时" /><el-table-column label="状态"><template #default="scope">{{ statusLabel(scope.row.status) }}</template></el-table-column></el-table></el-card>
    <el-card shadow="never"><template #header>替代料</template><div class="form-grid"><el-select v-model="alternateForm.material_id" placeholder="主料" filterable><el-option v-for="item in orderMaterials" :key="String(item.material_id)" :label="materialLabel(item.material_id)" :value="String(item.material_id)" /></el-select><el-select v-model="alternateForm.alternate_material_id" placeholder="替代料" filterable><el-option v-for="item in materials" :key="item.value" v-bind="item" /></el-select><el-input-number v-model="alternateForm.conversion_rate" :min="0.000001" :precision="6" /><el-input v-model="alternateForm.reason" placeholder="替代原因" /><el-button type="primary" :loading="saving" :disabled="!selectedWorkOrderId" @click="saveAlternate">保存替代料</el-button></div><el-table :data="alternates" stripe><el-table-column label="主料"><template #default="scope">{{ materialLabel(scope.row.material_id) }}</template></el-table-column><el-table-column label="替代料"><template #default="scope">{{ materialLabel(scope.row.alternate_material_id) }}</template></el-table-column><el-table-column prop="conversion_rate" label="转换率" /><el-table-column label="状态"><template #default="scope">{{ statusLabel(scope.row.status) }}</template></el-table-column><el-table-column prop="reason" label="原因" /></el-table></el-card>
    <el-card shadow="never"><template #header>车间异常</template><div class="form-grid"><el-input v-model="exceptionForm.exception_type" placeholder="异常类型，例如设备停机" /><el-input v-model="exceptionForm.description" placeholder="异常描述" /><el-button type="warning" :loading="saving" :disabled="!selectedWorkOrderId" @click="saveException">上报异常</el-button></div><el-table :data="exceptions" stripe><el-table-column prop="exception_type" label="类型" /><el-table-column prop="description" label="描述" /><el-table-column label="状态"><template #default="scope">{{ statusLabel(scope.row.status) }}</template></el-table-column><el-table-column prop="occurred_at" label="发生时间" /><el-table-column label="操作" width="100"><template #default="scope"><el-button v-if="scope.row.status === 'open'" link type="success" @click="resolveException(scope.row)">关闭</el-button></template></el-table-column></el-table></el-card>
  </section>
</template>

<style scoped>.page-stack{display:flex;flex-direction:column;gap:16px}.page-heading{display:flex;justify-content:space-between;align-items:flex-end}.page-heading small{color:var(--erp-muted-text);letter-spacing:.08em}.page-heading h1{margin:4px 0}.page-heading p{margin:0;color:var(--erp-muted-text)}.toolbar,.form-grid{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.form-grid{margin-bottom:14px}.form-grid>*{min-width:150px}</style>
