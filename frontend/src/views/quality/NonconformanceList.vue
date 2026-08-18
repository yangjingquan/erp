<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { listAdmin } from "../../api/admin";
import { listPurchaseOrders, listPurchaseReceipts } from "../../api/purchase";
import { listWorkOrders } from "../../api/production";
import {
  closeNonconformance,
  completeCapaAction,
  createCapaAction,
  listNonconformances,
  updateNonconformanceInvestigation,
  type QualityCapaAction,
  type QualityCapaCreatePayload,
  type QualityInvestigationPayload,
  type QualityNonconformance,
} from "../../api/quality";
import { usePermissionStore } from "../../stores/permission";
import { useClientPagination } from "../../composables/useClientPagination";
import { useMasterOptions } from "../../composables/useMasterOptions";
import { localDateString } from "../../utils/time";

interface UserOption {
  label: string;
  value: string;
}

interface AdminUserRow {
  id: string;
  username: string;
  display_name: string;
  status: string;
}

const permissions = usePermissionStore();
const canManage = computed(() => permissions.hasPermission("quality:manage"));
const rows = ref<QualityNonconformance[]>([]);
const { pagedRows, page, pageSize, total, updatePageSize } = useClientPagination(rows);
const users = ref<UserOption[]>([]);
const loading = ref(false);
const saving = ref(false);
const selected = ref<QualityNonconformance | null>(null);
const selectedAction = ref<QualityCapaAction | null>(null);
const investigationVisible = ref(false);
const actionVisible = ref(false);
const completionVisible = ref(false);
const closeVisible = ref(false);
const sourceDocumentNames = ref<Record<string, string>>({});
const { suppliers, loadOptions } = useMasterOptions();

const investigationForm = reactive<QualityInvestigationPayload>({
  severity: "major",
  disposition: "rework",
  owner_id: "",
  due_date: localDateString(),
  root_cause: "",
});
const actionForm = reactive<QualityCapaCreatePayload>({
  action_type: "corrective",
  description: "",
  owner_id: "",
  due_date: localDateString(),
});
const completionForm = reactive({ completion_evidence: "" });
const closeForm = reactive({ closure_evidence: "" });

const statusLabels: Record<string, string> = { open: "待调查", investigating: "整改中", closed: "已关闭" };
const severityLabels: Record<string, string> = { minor: "一般", major: "重大", critical: "严重" };
const dispositionLabels: Record<string, string> = { rework: "返工", accept: "让步接收", scrap: "报废", return_to_supplier: "退回供应商" };
const actionTypeLabels: Record<string, string> = { corrective: "纠正措施", preventive: "预防措施" };
const inspectionTypeLabels: Record<string, string> = {
  incoming: "来料检验",
  process: "过程检验",
  finished: "成品检验",
  final: "成品检验",
  active: "启用",
};

function statusTagType(status: string) {
  return ({ open: "danger", investigating: "warning", closed: "success" } as Record<string, string>)[status] || "info";
}

function severityTagType(severity: string) {
  return ({ minor: "info", major: "warning", critical: "danger" } as Record<string, string>)[severity] || "info";
}

function ownerName(ownerId?: string | null) {
  return users.value.find((option) => option.value === ownerId)?.label || ownerId || "待分配";
}

function sourceDocumentKey(sourceType: unknown, sourceId: unknown) {
  return `${String(sourceType || "")}:${String(sourceId || "")}`;
}

function sourceDocumentLabel(row: QualityNonconformance) {
  if (row.supplier_quality_id) return `供应商质量：${supplierLabel(row.supplier_id)}${row.supplier_period ? ` · ${row.supplier_period}` : ""}`;
  const sourceId = String(row.source_id || "");
  return row.source_document_name
    || sourceDocumentNames.value[sourceDocumentKey(row.source_type, sourceId)]
    || sourceDocumentNames.value[sourceId]
    || "-";
}

function supplierLabel(supplierId?: string | null) {
  return suppliers.value.find((option) => option.value === supplierId)?.label?.replace(/（[^（）]*）$/, "") || supplierId || "-";
}

async function loadSourceNames() {
  try {
    const [purchaseOrderResponse, purchaseReceiptResponse, workOrderResponse] = await Promise.all([
      listPurchaseOrders(),
      listPurchaseReceipts(),
      listWorkOrders(),
    ]);
    const map: Record<string, string> = {};
    const responses = [
      { response: purchaseOrderResponse, sourceTypes: ["purchase_order"] },
      { response: purchaseReceiptResponse, sourceTypes: ["purchase_receipt"] },
      { response: workOrderResponse, sourceTypes: ["mfg_work_order", "work_order"] },
    ];
    for (const { response, sourceTypes } of responses) {
      if (response.data.code !== 0) throw new Error(response.data.msg || "来源单据加载失败");
      for (const row of (response.data.data || []) as Array<Record<string, unknown>>) {
        const title = String(row.doc_no || row.order_no || "");
        if (!title) continue;
        for (const sourceType of sourceTypes) map[sourceDocumentKey(sourceType, row.id)] = title;
        // Some historical records carry an outdated or generic source_type.
        // Keep an ID-only index so the document number can still be resolved.
        if (row.id) map[String(row.id)] = title;
        if (row.doc_no) map[String(row.doc_no)] = title;
      }
    }
    sourceDocumentNames.value = map;
  } catch (error) {
    sourceDocumentNames.value = {};
    ElMessage.warning(error instanceof Error ? error.message : "来源单据名称加载失败");
  }
}

async function load() {
  loading.value = true;
  try {
    const [ncrResponse, usersResponse] = await Promise.all([
      listNonconformances(),
      listAdmin("users"),
    ]);
    if (ncrResponse.data.code !== 0) throw new Error(ncrResponse.data.msg || "不合格记录加载失败");
    rows.value = ncrResponse.data.data;
    const userEnvelope = usersResponse.data as { code: number; msg?: string; data?: AdminUserRow[] };
    if (userEnvelope.code !== 0) throw new Error(userEnvelope.msg || "责任人加载失败");
    users.value = (userEnvelope.data || [])
      .filter((user) => user.status === "active")
      .map((user) => ({ label: `${user.display_name}（${user.username}）`, value: user.id }));
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "质量闭环数据加载失败");
  } finally {
    loading.value = false;
  }
}

function openInvestigation(row: QualityNonconformance) {
  selected.value = row;
  investigationForm.severity = row.severity || "major";
  investigationForm.disposition = row.disposition || "rework";
  investigationForm.owner_id = row.owner_id || "";
  investigationForm.due_date = row.due_date || localDateString();
  investigationForm.root_cause = row.root_cause || "";
  investigationVisible.value = true;
}

async function saveInvestigation() {
  if (!selected.value || !investigationForm.owner_id || !investigationForm.due_date || investigationForm.root_cause.trim().length < 2) {
    ElMessage.warning("请填写责任人、整改期限和根因分析");
    return;
  }
  saving.value = true;
  try {
    const response = await updateNonconformanceInvestigation(selected.value.id, {
      ...investigationForm,
      root_cause: investigationForm.root_cause.trim(),
    });
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success("调查结论已保存");
    investigationVisible.value = false;
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "调查结论保存失败");
  } finally {
    saving.value = false;
  }
}

function openAction(row: QualityNonconformance, actionType: QualityCapaAction["action_type"] = "corrective") {
  selected.value = row;
  actionForm.action_type = actionType;
  actionForm.description = "";
  actionForm.owner_id = row.owner_id || "";
  actionForm.due_date = row.due_date || localDateString();
  actionVisible.value = true;
}

async function saveAction() {
  if (!selected.value || !actionForm.owner_id || !actionForm.due_date || actionForm.description.trim().length < 2) {
    ElMessage.warning("请填写措施内容、责任人和完成期限");
    return;
  }
  saving.value = true;
  try {
    const response = await createCapaAction(selected.value.id, {
      ...actionForm,
      description: actionForm.description.trim(),
    });
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success("CAPA 措施已创建");
    actionVisible.value = false;
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "CAPA 措施创建失败");
  } finally {
    saving.value = false;
  }
}

function openCompletion(action: QualityCapaAction) {
  selectedAction.value = action;
  completionForm.completion_evidence = "";
  completionVisible.value = true;
}

async function saveCompletion() {
  if (!selectedAction.value || completionForm.completion_evidence.trim().length < 2) {
    ElMessage.warning("请填写完成证据");
    return;
  }
  saving.value = true;
  try {
    const response = await completeCapaAction(selectedAction.value.id, completionForm.completion_evidence.trim());
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success("措施已完成并留存证据");
    completionVisible.value = false;
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "措施完成失败");
  } finally {
    saving.value = false;
  }
}

function openClose(row: QualityNonconformance) {
  selected.value = row;
  closeForm.closure_evidence = "";
  closeVisible.value = true;
}

async function saveClose() {
  if (!selected.value || closeForm.closure_evidence.trim().length < 2) {
    ElMessage.warning("请填写关闭验证证据");
    return;
  }
  try {
    await ElMessageBox.confirm("关闭后将同步关闭对应检验单或供应商质量 CAPA，确认继续吗？", "关闭 NCR", { type: "warning" });
    saving.value = true;
    const response = await closeNonconformance(selected.value.id, closeForm.closure_evidence.trim());
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success("NCR/CAPA 已闭环");
    closeVisible.value = false;
    await load();
  } catch (error) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "NCR 关闭失败");
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  await Promise.all([load(), loadSourceNames(), loadOptions(["suppliers"])]);
});
</script>

<template>
  <section class="page-stack">
    <el-page-header content="不合格与 CAPA" />
    <div class="toolbar">
      <div><strong>质量整改闭环</strong><span>不合格调查 → 根因分析 → 纠正/预防措施 → 证据验证 → 关闭</span></div>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </div>
    <el-alert title="不合格检验会自动生成 NCR；供应商质量低于阈值时会自动触发期间级 CAPA，必须同时完成纠正和预防措施并留存证据才能关闭。" type="info" show-icon />

    <el-table v-loading="loading" :data="pagedRows" row-key="id" stripe width="100%" fit :header-cell-style="{ textAlign: 'center' }" :cell-style="{ textAlign: 'center' }">
      <el-table-column type="expand" width="48">
        <template #default="scope">
          <div class="detail-grid">
            <div><span>问题描述</span><strong>{{ scope.row.description }}</strong></div>
            <div><span>根因分析</span><strong>{{ scope.row.root_cause || "待调查" }}</strong></div>
            <div><span>关闭证据</span><strong>{{ scope.row.closure_evidence || "待验证" }}</strong></div>
          </div>
          <div class="action-header"><strong>CAPA 措施</strong><el-space v-if="canManage && scope.row.status !== 'closed'"><el-button size="small" @click="openAction(scope.row, 'corrective')">新增纠正措施</el-button><el-button size="small" @click="openAction(scope.row, 'preventive')">新增预防措施</el-button></el-space></div>
          <el-table :data="scope.row.actions" size="small" border>
            <el-table-column label="类型" width="110"><template #default="actionScope">{{ actionTypeLabels[actionScope.row.action_type] }}</template></el-table-column>
            <el-table-column prop="description" label="措施内容" min-width="220" />
            <el-table-column label="责任人" width="160"><template #default="actionScope">{{ ownerName(actionScope.row.owner_id) }}</template></el-table-column>
            <el-table-column prop="due_date" label="期限" width="110" />
            <el-table-column label="状态" width="100"><template #default="actionScope"><el-tag :type="actionScope.row.status === 'completed' ? 'success' : actionScope.row.overdue ? 'danger' : 'warning'">{{ actionScope.row.status === "completed" ? "已完成" : actionScope.row.overdue ? "已逾期" : "进行中" }}</el-tag></template></el-table-column>
            <el-table-column prop="completion_evidence" label="完成证据" min-width="180" />
            <el-table-column v-if="canManage" label="操作" width="100"><template #default="actionScope"><el-button v-if="actionScope.row.status !== 'completed'" link type="success" @click="openCompletion(actionScope.row)">提交证据</el-button></template></el-table-column>
            <template #empty><el-empty description="尚未制定 CAPA 措施" :image-size="48" /></template>
          </el-table>
        </template>
      </el-table-column>
      <el-table-column label="检验类型" width="110"><template #default="scope">{{ inspectionTypeLabels[scope.row.inspection_type] || scope.row.inspection_type || "-" }}</template></el-table-column>
      <el-table-column label="来源单据" min-width="170"><template #default="scope">{{ sourceDocumentLabel(scope.row) }}</template></el-table-column>
      <el-table-column label="严重度" width="100"><template #default="scope"><el-tag :type="severityTagType(scope.row.severity)">{{ severityLabels[scope.row.severity] }}</el-tag></template></el-table-column>
      <el-table-column label="责任人" width="170"><template #default="scope">{{ ownerName(scope.row.owner_id) }}</template></el-table-column>
      <el-table-column label="整改期限" width="120"><template #default="scope"><span :class="{ overdue: scope.row.overdue }">{{ scope.row.due_date || "待设定" }}</span></template></el-table-column>
      <el-table-column label="处置" width="120"><template #default="scope">{{ dispositionLabels[scope.row.disposition] || "待确定" }}</template></el-table-column>
      <el-table-column label="状态" width="110"><template #default="scope"><el-tag :type="statusTagType(scope.row.status)">{{ scope.row.overdue ? "已逾期" : statusLabels[scope.row.status] }}</el-tag></template></el-table-column>
      <el-table-column v-if="canManage" label="操作" width="230"><template #default="scope"><el-button v-if="scope.row.status !== 'closed'" link type="primary" @click="openInvestigation(scope.row)">调查</el-button><el-button v-if="scope.row.status === 'investigating'" link type="warning" @click="openAction(scope.row)">制定措施</el-button><el-button v-if="scope.row.status === 'investigating'" link type="success" @click="openClose(scope.row)">验证关闭</el-button></template></el-table-column>
      <template #empty><el-empty description="暂无不合格记录" /></template>
    </el-table>
    <ClientPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @update:page-size="updatePageSize" />

    <el-dialog v-model="investigationVisible" title="不合格调查" width="620px"><el-form label-width="100px"><el-form-item label="严重度" required><el-select v-model="investigationForm.severity" style="width: 100%"><el-option label="一般" value="minor" /><el-option label="重大" value="major" /><el-option label="严重" value="critical" /></el-select></el-form-item><el-form-item label="处置结论" required><el-select v-model="investigationForm.disposition" style="width: 100%"><el-option label="返工" value="rework" /><el-option label="让步接收" value="accept" /><el-option label="报废" value="scrap" /><el-option label="退回供应商" value="return_to_supplier" /></el-select></el-form-item><el-form-item label="责任人" required><el-select v-model="investigationForm.owner_id" filterable style="width: 100%"><el-option v-for="user in users" :key="user.value" v-bind="user" /></el-select></el-form-item><el-form-item label="整改期限" required><el-date-picker v-model="investigationForm.due_date" type="date" value-format="YYYY-MM-DD" /></el-form-item><el-form-item label="根因分析" required><el-input v-model="investigationForm.root_cause" type="textarea" :rows="4" maxlength="1000" show-word-limit /></el-form-item></el-form><template #footer><el-button @click="investigationVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveInvestigation">保存调查</el-button></template></el-dialog>
    <el-dialog v-model="actionVisible" title="新增 CAPA 措施" width="620px"><el-form label-width="100px"><el-form-item label="措施类型" required><el-radio-group v-model="actionForm.action_type"><el-radio-button value="corrective">纠正措施</el-radio-button><el-radio-button value="preventive">预防措施</el-radio-button></el-radio-group></el-form-item><el-form-item label="措施内容" required><el-input v-model="actionForm.description" type="textarea" :rows="3" maxlength="500" show-word-limit /></el-form-item><el-form-item label="责任人" required><el-select v-model="actionForm.owner_id" filterable style="width: 100%"><el-option v-for="user in users" :key="user.value" v-bind="user" /></el-select></el-form-item><el-form-item label="完成期限" required><el-date-picker v-model="actionForm.due_date" type="date" value-format="YYYY-MM-DD" /></el-form-item></el-form><template #footer><el-button @click="actionVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveAction">创建措施</el-button></template></el-dialog>
    <el-dialog v-model="completionVisible" title="提交措施完成证据" width="560px"><el-input v-model="completionForm.completion_evidence" type="textarea" :rows="4" maxlength="1000" show-word-limit placeholder="填写复验结果、附件编号、照片或培训记录等证据" /><template #footer><el-button @click="completionVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveCompletion">确认完成</el-button></template></el-dialog>
    <el-dialog v-model="closeVisible" title="验证并关闭 NCR" width="560px"><el-alert title="系统会校验纠正、预防措施均已完成并留存证据。" type="warning" show-icon /><el-input v-model="closeForm.closure_evidence" class="closure-input" type="textarea" :rows="4" maxlength="1000" show-word-limit placeholder="填写最终复验、效果验证和归档证据" /><template #footer><el-button @click="closeVisible = false">取消</el-button><el-button type="success" :loading="saving" @click="saveClose">验证关闭</el-button></template></el-dialog>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.toolbar div { display: flex; flex-direction: column; gap: 4px; }
.toolbar span, .detail-grid span { color: var(--erp-muted-text); font-size: 13px; }
.detail-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; margin: 4px 24px 18px; text-align: left; }
.detail-grid div { display: flex; flex-direction: column; gap: 6px; }
.detail-grid strong { line-height: 1.6; }
.action-header { display: flex; align-items: center; justify-content: space-between; margin: 0 24px 10px; }
.overdue { color: var(--erp-danger); font-weight: 700; }
.closure-input { margin-top: 14px; }
@media (max-width: 900px) { .detail-grid { grid-template-columns: 1fr; } .toolbar { align-items: flex-start; } }
</style>
