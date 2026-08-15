<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import {
  createScanToken,
  listScanTasks,
  processScan,
  type ScanProcessPayload,
  type ScanTask,
} from "../../api/inventory-advanced";
import { useMasterOptions } from "../../composables/useMasterOptions";

const scanToken = ref("");
const tasks = ref<ScanTask[]>([]);
const loading = ref(false);
const processing = ref(false);
const queued = ref<Array<{ token: string; payload: ScanProcessPayload }>>([]);
const online = ref(globalThis.navigator?.onLine ?? true);
const resultMessage = ref("");
const form = reactive<ScanProcessPayload>({
  scan_id: createScanId(),
  action: "receive",
  document_id: "",
  warehouse_id: "",
  location_id: "",
  batch_id: "",
  material_id: "",
  quantity: 1,
  actual_quantity: undefined,
  unit_cost: undefined,
});
const { warehouses, materials, loadOptions } = useMasterOptions();

function createScanId() {
  return globalThis.crypto?.randomUUID?.() ?? `scan-${Date.now()}`;
}

const QUEUE_KEY = "erp.scan.offline.queue";
function loadQueue() { try { queued.value = JSON.parse(globalThis.localStorage?.getItem(QUEUE_KEY) || "[]"); } catch { queued.value = []; } }
function persistQueue() { globalThis.localStorage?.setItem(QUEUE_KEY, JSON.stringify(queued.value)); }
function isNetworkError(error: any) { return !error?.response || error?.code === "ERR_NETWORK"; }

function tasksFrom(response: any): ScanTask[] {
  if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "扫描任务加载失败");
  const data = response?.data?.data;
  return Array.isArray(data) ? data : [];
}

function messageFrom(error: any, fallback: string) {
  return error?.response?.data?.msg || error?.response?.data?.message || error?.response?.data?.detail || (error instanceof Error ? error.message : fallback);
}

function applyTask(documentId: string) {
  const task = tasks.value.find((item) => item.document_id === documentId);
  if (!task) return;
  form.action = task.action;
  form.warehouse_id = task.warehouse_id;
}

async function load() {
  loading.value = true;
  try {
    const [tokenResponse, tasksResponse] = await Promise.all([createScanToken(), listScanTasks()]);
    if (tokenResponse?.data?.code !== 0) throw new Error(tokenResponse?.data?.msg || "扫描令牌创建失败");
    scanToken.value = tokenResponse?.data?.data?.token ?? tokenResponse?.data?.data ?? "";
    tasks.value = tasksFrom(tasksResponse);
    await flushQueue();
  } catch (error) {
    ElMessage.error(messageFrom(error, "扫码任务加载失败，请检查接口服务后重试"));
  } finally {
    loading.value = false;
  }
}

async function flushQueue() {
  if (!online.value || !scanToken.value || !queued.value.length) return;
  const remaining: typeof queued.value = [];
  for (const item of queued.value) {
    try { const response = await processScan(scanToken.value, item.payload); if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "离线扫码重试失败"); }
    catch { remaining.push({ token: scanToken.value, payload: item.payload }); }
  }
  queued.value = remaining;
  persistQueue();
  if (!remaining.length) ElMessage.success("离线扫码队列已全部重试");
}

async function submit() {
  const validQuantity = form.action === "count" ? form.actual_quantity : form.quantity;
  if (!form.scan_id || !form.document_id || !form.warehouse_id || !form.material_id || validQuantity === undefined || validQuantity <= 0 || (form.action === "receive" && !form.location_id)) {
    ElMessage.error("请填写扫描编号、单据、仓库、物料和有效数量");
    return;
  }
  if (!scanToken.value) {
    ElMessage.error("扫描令牌未就绪，请刷新后重试");
    return;
  }

  processing.value = true;
  resultMessage.value = "";
  try {
    const response = await processScan(scanToken.value, form);
    if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "扫码处理失败");
    const result = response?.data?.data;
    resultMessage.value = `扫描已处理：${result?.document_id || form.document_id}`;
    ElMessage.success(resultMessage.value);
    form.scan_id = createScanId();
    await load();
  } catch (error) {
    if (isNetworkError(error)) { queued.value.push({ token: scanToken.value, payload: { ...form } }); persistQueue(); ElMessage.warning("当前网络不可用，扫码已进入离线队列，恢复网络后自动重试"); form.scan_id = createScanId(); }
    else ElMessage.error(messageFrom(error, "扫码处理失败，请检查扫描数据后重试"));
  } finally {
    processing.value = false;
  }
}

onMounted(async () => { loadQueue(); const onOnline = () => { online.value = true; void load(); }; const onOffline = () => { online.value = false; }; globalThis.addEventListener("online", onOnline); globalThis.addEventListener("offline", onOffline); await Promise.all([load(), loadOptions(["warehouses", "materials"])]); });
</script>

<template>
  <section class="scan-page" v-loading="loading">
    <el-page-header content="移动扫码入库" />
    <el-alert
      v-if="resultMessage"
      class="result"
      :title="resultMessage"
      type="success"
      show-icon
      closable
      @close="resultMessage = ''"
    />
    <el-alert v-if="queued.length || !online" class="result" :title="!online ? `离线模式：${queued.length} 条扫码待重试` : `${queued.length} 条扫码等待重试`" type="warning" show-icon />

    <el-card class="scan-card" shadow="never">
      <template #header>扫描信息</template>
      <el-form label-position="top" @submit.prevent="submit">
        <div class="form-grid">
          <el-form-item label="扫描编号" required>
            <el-input v-model="form.scan_id" name="scan_id" autocomplete="off" />
          </el-form-item>
          <el-form-item label="操作" required>
            <el-select v-model="form.action" class="full-width">
              <el-option label="采购入库" value="receive" />
              <el-option label="生产发料" value="fill" />
              <el-option label="生产退料" value="return" />
              <el-option label="库存盘点" value="count" />
            </el-select>
          </el-form-item>
          <el-form-item label="扫描任务" required>
            <el-select v-model="form.document_id" class="full-width" filterable @change="applyTask">
              <el-option v-for="task in tasks" :key="`${task.action}:${task.document_id}`" :label="`${task.action} / ${task.document_no}`" :value="task.document_id" />
            </el-select>
          </el-form-item>
          <el-form-item label="仓库" required><el-select v-model="form.warehouse_id" filterable clearable class="full-width"><el-option v-for="option in warehouses" :key="option.value" v-bind="option" /></el-select></el-form-item>
          <el-form-item v-if="form.action === 'receive'" label="库位" required><el-input v-model="form.location_id" /></el-form-item>
          <el-form-item v-if="form.action === 'receive'" label="批次"><el-input v-model="form.batch_id" /></el-form-item>
          <el-form-item label="物料" required><el-select v-model="form.material_id" filterable clearable class="full-width"><el-option v-for="option in materials" :key="option.value" v-bind="option" /></el-select></el-form-item>
          <el-form-item :label="form.action === 'count' ? '实盘数量' : '数量'" required>
            <el-input-number
              v-if="form.action !== 'count'"
              v-model="form.quantity"
              :min="0.01"
              :step="0.01"
              :precision="2"
              class="full-width"
            />
            <el-input-number
              v-else
              v-model="form.actual_quantity"
              :min="0"
              :step="0.01"
              :precision="2"
              class="full-width"
            />
          </el-form-item>
        </div>
        <el-button native-type="submit" type="primary" :loading="processing" class="submit-button">提交扫码</el-button>
      </el-form>
    </el-card>
  </section>
</template>

<style scoped>
.scan-page { max-width: 860px; margin: 0 auto; padding: 12px; }
.scan-card, .result { margin-top: 16px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 16px; }
.full-width { width: 100%; }
.submit-button { width: 100%; min-height: 44px; }
@media (max-width: 640px) {
  .scan-page { padding: 8px; }
  .form-grid { grid-template-columns: 1fr; gap: 0; }
}
</style>
