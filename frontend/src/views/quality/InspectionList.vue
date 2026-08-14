<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { useRouter } from "vue-router";
import { listPurchaseReceipts } from "../../api/purchase";
import { listWorkOrders } from "../../api/production";
import { closeInspection, createDefect, createInspection, createInspectionFromPlan, createQualityPlan, listDefects, listInspections, listQualityPlans, submitInspection } from "../../api/quality";

type Row = Record<string, any>;
const router = useRouter();
const rows = ref<Row[]>([]);
const loading = ref(false);
const saving = ref(false);
const createVisible = ref(false);
const resultVisible = ref(false);
const closeVisible = ref(false);
const planVisible = ref(false);
const defectVisible = ref(false);
const sourceLoading = ref(false);
const selected = ref<Row | null>(null);
const sourceDocuments = ref<Array<{ label: string; value: string }>>([]);
const sourceDocumentNames = ref<Record<string, string>>({});
const createForm = reactive({ inspection_type: "incoming", source_type: "purchase_receipt", source_id: "" });
const resultItems = ref<Array<{ item: string; value: string; passed: boolean | null }>>([]);
const closeForm = reactive({ disposition: "accept" });
const plans = ref<Row[]>([]);
const planForm = reactive({ name: "", items: "appearance\n尺寸" });
const defects = ref<Row[]>([]);
const defectForm = reactive({ code: "", name: "", severity: "major" });
const fromPlanForm = reactive({ plan_id: "", sample_size: 1 });

function listFrom(response: any, fallbackMessage = "质量检验接口返回失败") { if (response?.data?.code !== 0) throw new Error(response?.data?.msg || fallbackMessage); return Array.isArray(response?.data?.data) ? response.data.data : []; }
const inspectionTypeLabels: Record<string, string> = { incoming: "来料检验", process: "过程检验", finished: "成品检验" };
const sourceTypeLabels: Record<string, string> = { purchase_receipt: "采购入库单", mfg_work_order: "生产工单" };
const resultLabels: Record<string, string> = { passed: "合格", failed: "不合格" };
const dispositionLabels: Record<string, string> = { accept: "接受", rework: "返工", scrap: "报废", return_to_supplier: "退回供应商" };
const statusLabels: Record<string, string> = { draft: "草稿", submitted: "已提交", closed: "已关闭" };
function labelOf(value: unknown, labels: Record<string, string>) { const key = String(value || ""); return labels[key] || key || "-"; }
function sourceTypeForInspection(inspectionType: string) { return inspectionType === "incoming" ? "purchase_receipt" : "mfg_work_order"; }
function sourceTypeLabel(sourceType: string) { return labelOf(sourceType, sourceTypeLabels); }
function inspectionTypeLabel(inspectionType: string) { return labelOf(inspectionType, inspectionTypeLabels); }
function resultLabel(result: string) { return result ? labelOf(result, resultLabels) : "待检验"; }
function dispositionLabel(disposition: string) { return disposition ? labelOf(disposition, dispositionLabels) : "待处置"; }
function statusLabel(status: string) { return labelOf(status, statusLabels); }
function statusTagType(status: string) { return ({ draft: "info", submitted: "warning", closed: "success" } as Record<string, string>)[status] || "info"; }
function resultTagType(result: string) { return result === "passed" ? "success" : result === "failed" ? "danger" : "info"; }
function sourceDocumentKey(sourceType: unknown, sourceId: unknown) { return `${String(sourceType || "")}:${String(sourceId || "")}`; }
function sourceDocumentLabel(row: Row) { return sourceDocumentNames.value[sourceDocumentKey(row.source_type, row.source_id)] || row.source_id || "-"; }
function sourceStatusLabel(status: string) { return ({ draft: "草稿", released: "已下达", in_progress: "生产中", completed: "已完成" } as Record<string, string>)[status] || status || "未知"; }
async function loadSourceNames() {
  try {
    const [purchaseResponse, workOrderResponse] = await Promise.all([listPurchaseReceipts(), listWorkOrders()]);
    const map: Record<string, string> = {};
    for (const row of listFrom(purchaseResponse, "采购入库单加载失败")) map[sourceDocumentKey("purchase_receipt", row.id)] = row.doc_no || String(row.id);
    for (const row of listFrom(workOrderResponse, "生产工单加载失败")) map[sourceDocumentKey("mfg_work_order", row.id)] = row.doc_no || String(row.id);
    sourceDocumentNames.value = map;
  } catch (error) {
    sourceDocumentNames.value = {};
    ElMessage.warning(error instanceof Error ? error.message : "来源单据名称加载失败，将显示单据 ID");
  }
}
async function loadSourceDocuments() {
  sourceLoading.value = true;
  sourceDocuments.value = [];
  try {
    const response = createForm.source_type === "purchase_receipt" ? await listPurchaseReceipts() : await listWorkOrders();
    sourceDocuments.value = listFrom(response, "来源单据加载失败")
      .filter((row: Row) => row.status !== "cancelled")
      .map((row: Row) => ({ label: `${row.doc_no || row.id}（${sourceStatusLabel(row.status)}）`, value: String(row.id) }));
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "来源单据加载失败");
  } finally {
    sourceLoading.value = false;
  }
}
async function load() {
  loading.value = true;
  try { rows.value = listFrom(await listInspections()); plans.value = listFrom(await listQualityPlans()); defects.value = listFrom(await listDefects()); }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : "检验列表加载失败"); }
  finally { loading.value = false; }
}
async function savePlan() { const items = planForm.items.split(/\n|,/).map((item) => item.trim()).filter(Boolean).map((item) => ({ item, value: "待检" })); if (!planForm.name.trim() || !items.length) return ElMessage.warning("请填写计划名称和检验项目"); try { const response = await createQualityPlan({ name: planForm.name.trim(), items }); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("检验计划已创建"); planVisible.value = false; planForm.name = ""; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "检验计划创建失败"); } }
async function saveDefect() { if (!defectForm.code.trim() || !defectForm.name.trim()) return ElMessage.warning("请填写缺陷编码和名称"); try { const response = await createDefect({ ...defectForm, code: defectForm.code.trim(), name: defectForm.name.trim() }); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("缺陷字典已创建"); defectVisible.value = false; defectForm.code = ""; defectForm.name = ""; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "缺陷字典创建失败"); } }
async function createFromPlan() { if (!fromPlanForm.plan_id || !createForm.source_id) return ElMessage.warning("请选择检验计划和来源单据"); saving.value = true; try { const response = await createInspectionFromPlan({ ...createForm, ...fromPlanForm }); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("按检验计划创建成功"); createVisible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "按计划创建失败"); } finally { saving.value = false; } }
function openCreate() { createForm.inspection_type = "incoming"; createForm.source_type = "purchase_receipt"; createForm.source_id = ""; fromPlanForm.plan_id = ""; fromPlanForm.sample_size = 1; createVisible.value = true; void loadSourceDocuments(); }
function changeInspectionType(inspectionType: string) { createForm.source_type = sourceTypeForInspection(inspectionType); createForm.source_id = ""; void loadSourceDocuments(); }
async function create() {
  if (!createForm.inspection_type || !createForm.source_type || !createForm.source_id) { ElMessage.warning("请选择检验类型和来源单据"); return; }
  saving.value = true;
  try { const response = await createInspection(createForm); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("检验单已创建"); createVisible.value = false; await load(); }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : "检验单创建失败"); }
  finally { saving.value = false; }
}
function openResult(row: Row) {
  selected.value = row;
  const existing = Array.isArray(row.results) ? row.results : [];
  resultItems.value = existing.length
    ? existing.map((item: Row) => ({ item: String(item.item || ""), value: String(item.value || ""), passed: typeof item.passed === "boolean" ? item.passed : null }))
    : [{ item: "appearance", value: "", passed: null }];
  resultVisible.value = true;
}
async function submitResult() {
  if (!selected.value?.id || !resultItems.value.length || resultItems.value.some((item) => !item.item.trim() || !item.value.trim() || item.passed === null)) {
    ElMessage.warning("请完成全部检验项目，并明确每项是否通过");
    return;
  }
  saving.value = true;
  try { const response = await submitInspection(selected.value.id, resultItems.value.map((item) => ({ ...item, item: item.item.trim(), value: item.value.trim() }))); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("检验结果已提交"); resultVisible.value = false; await load(); }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : "检验结果提交失败"); }
  finally { saving.value = false; }
}
function openClose(row: Row) { selected.value = row; closeForm.disposition = row.result === "failed" ? "rework" : "accept"; closeVisible.value = true; }
function openNonconformance() { void router.push("/quality/nonconformances"); }
async function close() {
  if (!selected.value?.id) return;
  try { await ElMessageBox.confirm("关闭后检验结果不可再修改，确认继续吗？", "关闭检验", { type: "warning" }); saving.value = true; const response = await closeInspection(selected.value.id, closeForm.disposition); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("检验已关闭"); closeVisible.value = false; await load(); }
  catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "检验关闭失败"); }
  finally { saving.value = false; }
}
onMounted(async () => { await Promise.all([load(), loadSourceNames()]); });
</script>

<template>
  <section class="page-stack">
    <el-page-header content="质量检验" />
    <el-space><el-button type="primary" @click="openCreate">新建检验单</el-button><el-button @click="planVisible = true">维护检验计划</el-button><el-button @click="defectVisible = true">维护缺陷字典</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-alert title="检验单必须先录入结构化结果，再选择处置结论关闭；不合格结果会自动生成不合格记录。" type="info" show-icon />
    <el-table v-loading="loading" :data="rows" stripe width="100%" fit :header-cell-style="{ textAlign: 'center' }" :cell-style="{ textAlign: 'center' }">
      <el-table-column label="检验类型" width="130"><template #default="scope">{{ inspectionTypeLabel(scope.row.inspection_type) }}</template></el-table-column><el-table-column label="来源类型" width="180" class-name="nowrap-column"><template #default="scope">{{ sourceTypeLabel(scope.row.source_type) }}</template></el-table-column><el-table-column label="来源单据" min-width="180"><template #default="scope">{{ sourceDocumentLabel(scope.row) }}</template></el-table-column><el-table-column label="结果" width="100"><template #default="scope"><el-tag class="status-tag" :type="resultTagType(scope.row.result)" effect="light">{{ resultLabel(scope.row.result) }}</el-tag></template></el-table-column><el-table-column label="处置" width="100"><template #default="scope">{{ dispositionLabel(scope.row.disposition) }}</template></el-table-column><el-table-column label="状态" width="100"><template #default="scope"><el-tag class="status-tag" :type="statusTagType(scope.row.status)" effect="light">{{ statusLabel(scope.row.status) }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="220"><template #default="scope"><el-button v-if="scope.row.status === 'draft'" link type="primary" @click="openResult(scope.row)">录入结果</el-button><el-button v-if="scope.row.status === 'submitted' && scope.row.result !== 'failed'" link type="success" @click="openClose(scope.row)">关闭检验</el-button><el-button v-if="scope.row.status === 'submitted' && scope.row.result === 'failed'" link type="warning" @click="openNonconformance">处理 NCR/CAPA</el-button></template></el-table-column>
      <template #empty><el-empty description="暂无检验单" /></template>
    </el-table>
    <el-dialog v-model="createVisible" title="新建检验单" width="560px"><el-form label-width="100px"><el-form-item label="检验类型" required><el-select v-model="createForm.inspection_type" style="width: 100%" @change="changeInspectionType"><el-option label="来料检验" value="incoming" /><el-option label="过程检验" value="process" /><el-option label="成品检验" value="finished" /></el-select></el-form-item><el-form-item label="来源类型"><el-input :model-value="sourceTypeLabel(createForm.source_type)" readonly /></el-form-item><el-form-item label="来源单据" required><el-select v-model="createForm.source_id" filterable clearable :loading="sourceLoading" :placeholder="`请选择${sourceTypeLabel(createForm.source_type)}`" style="width: 100%"><el-option v-for="option in sourceDocuments" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item><el-form-item label="检验计划"><el-select v-model="fromPlanForm.plan_id" clearable style="width: 100%"><el-option v-for="plan in plans" :key="plan.id" :label="plan.name" :value="plan.id" /></el-select></el-form-item><el-form-item v-if="fromPlanForm.plan_id" label="抽样数量"><el-input-number v-model="fromPlanForm.sample_size" :min="1" /></el-form-item></el-form><template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="fromPlanForm.plan_id ? createFromPlan() : create()">保存</el-button></template></el-dialog>
    <el-dialog v-model="planVisible" title="维护检验计划" width="520px"><el-form label-width="100px"><el-form-item label="计划名称"><el-input v-model="planForm.name" /></el-form-item><el-form-item label="检验项目"><el-input v-model="planForm.items" type="textarea" :rows="5" placeholder="每行一个项目" /></el-form-item></el-form><template #footer><el-button @click="planVisible = false">取消</el-button><el-button type="primary" @click="savePlan">保存计划</el-button></template></el-dialog>
    <el-dialog v-model="defectVisible" title="维护缺陷字典" width="520px"><el-form label-width="100px"><el-form-item label="缺陷编码"><el-input v-model="defectForm.code" /></el-form-item><el-form-item label="缺陷名称"><el-input v-model="defectForm.name" /></el-form-item><el-form-item label="严重程度"><el-select v-model="defectForm.severity" style="width: 100%"><el-option label="轻微" value="minor" /><el-option label="主要" value="major" /><el-option label="严重" value="critical" /></el-select></el-form-item></el-form><el-divider /><el-table :data="defects" size="small"><el-table-column prop="code" label="编码" /><el-table-column prop="name" label="名称" /><el-table-column prop="severity" label="严重程度" /></el-table><template #footer><el-button @click="defectVisible = false">取消</el-button><el-button type="primary" @click="saveDefect">新增缺陷</el-button></template></el-dialog>
    <el-dialog v-model="resultVisible" title="录入检验结果" width="620px"><el-alert title="按检验计划创建的检验单必须完成全部项目后才能提交。" type="info" show-icon /><div class="result-items"><div v-for="item in resultItems" :key="item.item" class="result-item"><div class="result-item-name">{{ item.item || "未命名项目" }}</div><el-input v-model="item.value" placeholder="填写实测值或 pass/fail" /><el-switch v-model="item.passed" :active-value="true" :inactive-value="false" active-text="通过" inactive-text="不通过" /></div></div><template #footer><el-button @click="resultVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitResult">提交结果</el-button></template></el-dialog>
    <el-dialog v-model="closeVisible" title="关闭检验" width="420px"><el-form label-width="100px"><el-form-item label="处置结论" required><el-select v-model="closeForm.disposition" style="width: 100%"><el-option label="接受" value="accept" /><el-option label="返工" value="rework" /><el-option label="报废" value="scrap" /><el-option label="退回供应商" value="return_to_supplier" /></el-select></el-form-item></el-form><template #footer><el-button @click="closeVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="close">确认关闭</el-button></template></el-dialog>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.nowrap-column :deep(.cell) { white-space: nowrap; }
.status-tag { border-width: 1px; }
.status-tag.el-tag--success { background: var(--erp-green-bg); border-color: var(--erp-green); color: var(--erp-green); }
.status-tag.el-tag--warning { background: var(--erp-amber-bg); border-color: var(--erp-amber); color: var(--erp-amber); }
.status-tag.el-tag--info { background: var(--erp-panel-soft); border-color: var(--erp-border); color: var(--erp-muted-text); }
.status-tag.el-tag--danger { background: var(--erp-danger-bg, #f8e4dc); border-color: var(--erp-danger); color: var(--erp-danger); }
.result-items { display: flex; flex-direction: column; gap: 12px; margin-top: 16px; }
.result-item { display: grid; grid-template-columns: 120px minmax(0, 1fr) 130px; align-items: center; gap: 12px; }
.result-item-name { font-weight: 600; }
@media (max-width: 640px) { .result-item { grid-template-columns: 1fr; } }
</style>
