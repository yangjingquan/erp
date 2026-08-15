<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { listAdmin } from "../../api/admin";
import { listOrganizations } from "../../api/auth";
import {
  createGroupMember, createIntercompany, createLowCode, createMetric,
  createTaxCode, createTaxInvoice, deleteGroupMember, explainMetric, listAiAlerts,
  listGroupMembers, listIntercompany, listLowCode, listMetrics,
  listTaxCodes, listTaxInvoices, publishLowCode, resolveAiAlert,
  scanAiAlerts, transitionTaxInvoice, updateGroupMember,
} from "../../api/phase2";
import { useMasterOptions, type SelectOption } from "../../composables/useMasterOptions";

type PlatformTab = "group" | "compliance" | "low-code" | "metrics";
type Row = Record<string, any>;
const props = withDefaults(defineProps<{ activeTab?: PlatformTab }>(), { activeTab: "group" });
const loading = ref(false);
const memberDialog = ref(false);
const editingMemberId = ref<string | null>(null);
const metricDetail = ref<Row | null>(null);
const intercompany = ref<Row[]>([]);
const members = ref<Row[]>([]);
const invoices = ref<Row[]>([]);
const taxCodes = ref<Row[]>([]);
const lowCode = ref<Row[]>([]);
const metrics = ref<Row[]>([]);
const alerts = ref<Row[]>([]);
const users = ref<SelectOption[]>([]);
const organizations = ref<SelectOption[]>([]);
const { customers, suppliers, loadOptions } = useMasterOptions();

const groupForm = reactive({ from_org_id: "", to_org_id: "", source_type: "manual", source_id: "", amount: 0, currency: "CNY" });
const memberForm = reactive({ user_id: "", org_id: "", membership_type: "member", status: "active" });
const taxCodeForm = reactive({ code: "", name: "", rate: 0 });
const invoiceForm = reactive({ invoice_type: "output", source_type: "sales_order", source_id: "", party_id: "", amount: 0, tax_amount: 0, tax_code: "" });
const lowForm = reactive({ object_key: "", name: "", schema: '{"fields":[]}', workflow: '{"steps":[]}' });
const metricForm = reactive({ metric_key: "", name: "", formula: "", target: null as number | null });
const memberFormTitle = computed(() => editingMemberId.value ? "编辑组织成员" : "添加组织成员");
const membershipTypeLabels: Record<string, string> = { member: "普通成员", admin: "管理员", viewer: "只读成员" };
const statusLabels: Record<string, string> = { active: "正常", inactive: "停用" };
const invoiceTypeLabels: Record<string, string> = { output: "销项发票", input: "进项发票", credit: "红字发票" };
const invoiceStatusLabels: Record<string, string> = { draft: "草稿", submitted: "已提交", issued: "已开具", red_issued: "已红冲", rejected: "已驳回", cancelled: "已取消" };

const pageMeta = computed(() => ({
  group: { eyebrow: "GROUP", title: "集团与内部交易", description: "管理组织成员、组织间交易与跨组织业务关系。" },
  compliance: { eyebrow: "COMPLIANCE", title: "税务与电子发票", description: "维护税码、发票池、业务原单关系和合规状态流转。" },
  "low-code": { eyebrow: "LOW-CODE", title: "低代码对象", description: "配置对象字段与工作流，支持发布前校验和版本发布。" },
  metrics: { eyebrow: "METRICS / AI", title: "指标与异常助手", description: "沉淀指标口径、证据解释并扫描和闭环业务异常。" },
}[props.activeTab]));
const partyOptions = computed(() => props.activeTab === "compliance" && invoiceForm.invoice_type === "input" ? suppliers.value : customers.value);
const organizationOptions = computed(() => organizations.value);

function unwrap(response: any) {
  if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "接口返回失败");
  return response.data.data;
}
function rowsOf(response: any): Row[] {
  const data = unwrap(response);
  return Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : [];
}
function optionRows(rows: Row[], labelKeys: string[]): SelectOption[] {
  return rows.map((row) => ({ value: String(row.id), label: labelKeys.map((key) => row[key]).find(Boolean) || String(row.id) }));
}
function parseJson(value: string, label: string) {
  const result = JSON.parse(value);
  if (!result || Array.isArray(result) || typeof result !== "object") throw new Error(label + "必须是 JSON 对象");
  return result;
}

async function loadGroup() {
  const [transactionResponse, memberResponse, userResponse, organizationResponse] = await Promise.all([listIntercompany(), listGroupMembers(), listAdmin("users"), listOrganizations()]);
  intercompany.value = rowsOf(transactionResponse);
  members.value = rowsOf(memberResponse);
  users.value = optionRows(rowsOf(userResponse), ["display_name", "username", "name"]);
  organizations.value = optionRows(rowsOf(organizationResponse), ["name", "code"]);
}
async function loadCompliance() {
  const [taxCodeResponse, invoiceResponse] = await Promise.all([listTaxCodes(), listTaxInvoices()]);
  taxCodes.value = rowsOf(taxCodeResponse);
  invoices.value = rowsOf(invoiceResponse);
  await loadOptions(["customers", "suppliers"]);
}
async function loadLowCode() { lowCode.value = rowsOf(await listLowCode()); }
async function loadMetrics() {
  const [metricResponse, alertResponse] = await Promise.all([listMetrics(), listAiAlerts()]);
  metrics.value = rowsOf(metricResponse);
  alerts.value = rowsOf(alertResponse);
}
async function load() {
  loading.value = true;
  try {
    if (props.activeTab === "group") await loadGroup();
    if (props.activeTab === "compliance") await loadCompliance();
    if (props.activeTab === "low-code") await loadLowCode();
    if (props.activeTab === "metrics") await loadMetrics();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "页面数据加载失败");
  } finally { loading.value = false; }
}
async function saveGroup() {
  try {
    if (!groupForm.from_org_id || !groupForm.to_org_id || !groupForm.source_id || groupForm.amount <= 0) throw new Error("请完整填写组织、来源单据和金额");
    unwrap(await createIntercompany({ ...groupForm }));
    ElMessage.success("内部交易已登记");
    await load();
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "内部交易保存失败"); }
}
async function saveMember() {
  try {
    if (!memberForm.user_id || !memberForm.org_id) throw new Error("请选择用户和组织");
    const isEditing = Boolean(editingMemberId.value);
    const payload = editingMemberId.value
      ? { ...memberForm }
      : { user_id: memberForm.user_id, org_id: memberForm.org_id, membership_type: memberForm.membership_type };
    if (editingMemberId.value) {
      unwrap(await updateGroupMember(editingMemberId.value, payload));
    } else {
      unwrap(await createGroupMember(payload));
    }
    memberDialog.value = false;
    editingMemberId.value = null;
    ElMessage.success(isEditing ? "组织成员已更新" : "组织成员已添加");
    await load();
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "成员保存失败"); }
}

function openMemberEditor(row?: Row) {
  editingMemberId.value = row?.id || null;
  Object.assign(memberForm, {
    user_id: row?.user_id || "",
    org_id: row?.org_id || "",
    membership_type: row?.membership_type || "member",
    status: row?.status || "active",
  });
  memberDialog.value = true;
}

async function removeMember(row: Row) {
  try {
    await ElMessageBox.confirm("删除后该成员将从当前组织中移除，是否继续？", "确认删除", { type: "warning" });
    unwrap(await deleteGroupMember(row.id));
    ElMessage.success("组织成员已删除");
    await load();
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(error instanceof Error ? error.message : "成员删除失败");
  }
}
async function saveTaxCode() {
  try {
    if (!taxCodeForm.code || !taxCodeForm.name || taxCodeForm.rate < 0) throw new Error("请完整填写税码、名称和税率");
    unwrap(await createTaxCode({ ...taxCodeForm }));
    Object.assign(taxCodeForm, { code: "", name: "", rate: 0 });
    ElMessage.success("税码已保存");
    await load();
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "税码保存失败"); }
}
async function saveInvoice() {
  try {
    if (!invoiceForm.source_id || !invoiceForm.party_id || invoiceForm.amount <= 0) throw new Error("请完整填写来源单据、往来方和金额");
    unwrap(await createTaxInvoice({ ...invoiceForm }));
    Object.assign(invoiceForm, { source_id: "", party_id: "", amount: 0, tax_amount: 0, tax_code: "" });
    ElMessage.success("发票已加入发票池");
    await load();
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "发票保存失败"); }
}
const invoiceTransitions: Record<string, string[]> = { draft: ["submitted", "cancelled"], submitted: ["issued", "rejected"], issued: ["red_issued"] };
async function transitionInvoice(row: Row, status: string) {
  try {
    unwrap(await transitionTaxInvoice(row.id, status));
    ElMessage.success("发票状态已更新");
    await load();
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "发票状态更新失败"); }
}
async function saveLowCode() {
  try {
    if (!lowForm.object_key || !lowForm.name) throw new Error("请填写对象编码和名称");
    unwrap(await createLowCode({ object_key: lowForm.object_key, name: lowForm.name, schema: parseJson(lowForm.schema, "字段配置"), workflow: parseJson(lowForm.workflow, "工作流配置") }));
    ElMessage.success("低代码对象已保存");
    await load();
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "低代码对象保存失败"); }
}
async function publish(row: Row) {
  try {
    unwrap(await publishLowCode(row.id));
    ElMessage.success("低代码对象已发布");
    await load();
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "低代码发布失败"); }
}
async function saveMetric() {
  try {
    if (!metricForm.metric_key || !metricForm.name || !metricForm.formula) throw new Error("请完整填写指标编码、名称和公式");
    unwrap(await createMetric({ ...metricForm }));
    ElMessage.success("指标口径已保存");
    await load();
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "指标保存失败"); }
}
async function explain(row: Row) {
  try { metricDetail.value = unwrap(await explainMetric(row.metric_key)); }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : "指标解释失败"); }
}
async function scan() {
  try {
    alerts.value = rowsOf(await scanAiAlerts());
    ElMessage.success("异常扫描完成");
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "异常扫描失败"); }
}
async function resolve(row: Row) {
  try {
    unwrap(await resolveAiAlert(row.id, "已由工作台处理"));
    ElMessage.success("异常已闭环");
    await load();
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "异常关闭失败"); }
}
onMounted(load);
</script>

<template>
  <section class="page-stack">
    <header class="page-heading">
      <div>
        <small>{{ pageMeta.eyebrow }}</small>
        <h1>{{ pageMeta.title }}</h1>
        <p>{{ pageMeta.description }}</p>
      </div>
      <el-space>
        <el-button v-if="props.activeTab === 'metrics'" type="warning" @click="scan">扫描异常</el-button>
        <el-button :loading="loading" @click="load">刷新</el-button>
      </el-space>
    </header>

    <template v-if="props.activeTab === 'group'">
      <el-card shadow="never">
        <template #header><div class="card-header"><span>组织成员与权限</span><el-button type="primary" @click="openMemberEditor()">添加成员</el-button></div></template>
        <el-empty v-if="!loading && !members.length" description="暂无组织成员" />
        <el-table v-else :data="members" stripe>
          <el-table-column prop="user_name" label="成员" />
          <el-table-column label="组织"><template #default="{ row }">{{ row.org_name || row.org_id }}</template></el-table-column>
          <el-table-column label="成员类型"><template #default="{ row }">{{ membershipTypeLabels[row.membership_type] || row.membership_type }}</template></el-table-column>
          <el-table-column label="状态"><template #default="{ row }">{{ statusLabels[row.status] || row.status }}</template></el-table-column>
          <el-table-column label="操作" width="150"><template #default="{ row }"><el-button link type="primary" @click="openMemberEditor(row)">编辑</el-button><el-button link type="danger" @click="removeMember(row)">删除</el-button></template></el-table-column>
        </el-table>
      </el-card>
      <el-card shadow="never">
        <template #header>内部交易登记</template>
        <el-form :model="groupForm" inline>
          <el-form-item label="转出组织"><el-select v-model="groupForm.from_org_id" filterable placeholder="请选择"><el-option v-for="item in organizationOptions" :key="item.value" v-bind="item" /></el-select></el-form-item>
          <el-form-item label="转入组织"><el-select v-model="groupForm.to_org_id" filterable placeholder="请选择"><el-option v-for="item in organizationOptions" :key="item.value" v-bind="item" /></el-select></el-form-item>
          <el-form-item label="来源单据"><el-input v-model="groupForm.source_id" placeholder="业务原单 ID" /></el-form-item>
          <el-form-item label="金额"><el-input-number v-model="groupForm.amount" :min="0.01" /></el-form-item>
          <el-form-item class="form-actions"><el-button type="primary" @click="saveGroup">登记交易</el-button></el-form-item>
        </el-form>
        <el-empty v-if="!loading && !intercompany.length" description="暂无内部交易" />
        <el-table v-else :data="intercompany" stripe><el-table-column prop="transaction_no" label="交易号" /><el-table-column prop="from_org_id" label="转出组织" /><el-table-column prop="to_org_id" label="转入组织" /><el-table-column prop="amount" label="金额" /><el-table-column prop="currency" label="币种" /><el-table-column prop="status" label="状态" /></el-table>
      </el-card>
    </template>

    <template v-else-if="props.activeTab === 'compliance'">
      <el-alert title="发票状态只能按草稿→提交→开具→红冲的合法路径流转，电子发票服务接入前不伪造已开票结果。" type="info" show-icon />
      <el-card shadow="never">
        <template #header>税码主数据</template>
        <el-form :model="taxCodeForm" inline><el-form-item label="税码"><el-input v-model="taxCodeForm.code" placeholder="VAT-13" /></el-form-item><el-form-item label="名称"><el-input v-model="taxCodeForm.name" /></el-form-item><el-form-item label="税率"><el-input-number v-model="taxCodeForm.rate" :min="0" :max="100" :precision="2" /></el-form-item><el-form-item class="form-actions"><el-button type="primary" @click="saveTaxCode">保存税码</el-button></el-form-item></el-form>
        <el-empty v-if="!loading && !taxCodes.length" description="暂无税码" />
        <el-table v-else :data="taxCodes" stripe><el-table-column prop="code" label="税码" /><el-table-column prop="name" label="名称" /><el-table-column prop="rate" label="税率" /><el-table-column prop="status" label="状态" /></el-table>
      </el-card>
      <el-card shadow="never">
        <template #header>发票池</template>
        <el-form :model="invoiceForm" inline><el-form-item label="类型"><el-select v-model="invoiceForm.invoice_type"><el-option label="销项" value="output" /><el-option label="进项" value="input" /><el-option label="红字" value="credit" /></el-select></el-form-item><el-form-item label="来源类型"><el-input v-model="invoiceForm.source_type" /></el-form-item><el-form-item label="来源单据"><el-input v-model="invoiceForm.source_id" /></el-form-item><el-form-item label="往来方"><el-select v-model="invoiceForm.party_id" filterable placeholder="请选择"><el-option v-for="item in partyOptions" :key="item.value" v-bind="item" /></el-select></el-form-item><el-form-item label="金额"><el-input-number v-model="invoiceForm.amount" :min="0.01" /></el-form-item><el-form-item label="税额"><el-input-number v-model="invoiceForm.tax_amount" :min="0" /></el-form-item><el-form-item label="税码"><el-input v-model="invoiceForm.tax_code" /></el-form-item><el-form-item class="form-actions"><el-button type="primary" @click="saveInvoice">加入发票池</el-button></el-form-item></el-form>
        <el-empty v-if="!loading && !invoices.length" description="暂无发票" />
        <el-table v-else :data="invoices" stripe><el-table-column prop="invoice_no" label="发票号" /><el-table-column label="类型"><template #default="{ row }">{{ invoiceTypeLabels[row.invoice_type] || row.invoice_type }}</template></el-table-column><el-table-column prop="amount" label="金额" /><el-table-column prop="tax_amount" label="税额" /><el-table-column label="状态"><template #default="{ row }">{{ invoiceStatusLabels[row.status] || row.status }}</template></el-table-column><el-table-column label="操作" min-width="180"><template #default="{ row }"><el-button v-for="status in invoiceTransitions[row.status] || []" :key="status" link type="primary" @click="transitionInvoice(row, status)">{{ status === "submitted" ? "提交" : status === "issued" ? "开具" : status === "red_issued" ? "红冲" : status === "rejected" ? "驳回" : "取消" }}</el-button></template></el-table-column></el-table>
      </el-card>
    </template>

    <template v-else-if="props.activeTab === 'low-code'">
      <el-card shadow="never">
        <template #header>对象与工作流配置</template>
        <el-form :model="lowForm" label-width="100px" class="form-grid"><el-form-item label="对象编码"><el-input v-model="lowForm.object_key" /></el-form-item><el-form-item label="对象名称"><el-input v-model="lowForm.name" /></el-form-item><el-form-item label="字段 JSON"><el-input v-model="lowForm.schema" type="textarea" :rows="5" /></el-form-item><el-form-item label="工作流 JSON"><el-input v-model="lowForm.workflow" type="textarea" :rows="5" /></el-form-item><el-form-item class="form-actions"><el-button type="primary" @click="saveLowCode">保存对象</el-button></el-form-item></el-form>
      </el-card>
      <el-card shadow="never"><template #header>对象发布</template><el-empty v-if="!loading && !lowCode.length" description="暂无低代码对象" /><el-table v-else :data="lowCode" stripe><el-table-column prop="object_key" label="对象" /><el-table-column prop="name" label="名称" /><el-table-column prop="status" label="状态" /><el-table-column prop="version" label="版本" /><el-table-column label="操作"><template #default="{ row }"><el-button v-if="row.status !== 'published'" link type="primary" @click="publish(row)">发布</el-button><span v-else class="muted">已发布</span></template></el-table-column></el-table></el-card>
    </template>

    <template v-else>
      <el-card shadow="never"><template #header>指标口径</template><el-form :model="metricForm" inline><el-form-item label="指标编码"><el-input v-model="metricForm.metric_key" /></el-form-item><el-form-item label="名称"><el-input v-model="metricForm.name" /></el-form-item><el-form-item label="公式"><el-input v-model="metricForm.formula" /></el-form-item><el-form-item label="目标"><el-input-number v-model="metricForm.target" /></el-form-item><el-form-item class="form-actions"><el-button type="primary" @click="saveMetric">保存口径</el-button></el-form-item></el-form><el-empty v-if="!loading && !metrics.length" description="暂无指标口径" /><el-table v-else :data="metrics" stripe><el-table-column prop="metric_key" label="编码" /><el-table-column prop="name" label="名称" /><el-table-column prop="formula" label="公式" /><el-table-column prop="target" label="目标" /><el-table-column label="操作"><template #default="{ row }"><el-button link type="primary" @click="explain(row)">查看证据</el-button></template></el-table-column></el-table></el-card>
      <el-card shadow="never"><template #header>异常助手</template><el-empty v-if="!loading && !alerts.length" description="暂无异常" /><el-table v-else :data="alerts" stripe><el-table-column prop="title" label="异常" /><el-table-column prop="severity" label="严重度" /><el-table-column prop="recommended_action" label="建议动作" /><el-table-column prop="status" label="状态" /><el-table-column label="操作"><template #default="{ row }"><el-button v-if="row.status === 'open'" link type="success" @click="resolve(row)">标记已处理</el-button></template></el-table-column></el-table></el-card>
    </template>

    <el-dialog v-model="memberDialog" :title="memberFormTitle" width="420px"><el-form :model="memberForm" label-width="90px" class="member-dialog-form"><el-form-item label="用户"><el-select v-model="memberForm.user_id" filterable placeholder="请选择" :disabled="Boolean(editingMemberId)"><el-option v-for="item in users" :key="item.value" v-bind="item" /></el-select></el-form-item><el-form-item label="组织"><el-select v-model="memberForm.org_id" filterable placeholder="请选择"><el-option v-for="item in organizationOptions" :key="item.value" v-bind="item" /></el-select></el-form-item><el-form-item label="成员类型"><el-select v-model="memberForm.membership_type"><el-option label="普通成员" value="member" /><el-option label="管理员" value="admin" /><el-option label="只读成员" value="viewer" /></el-select></el-form-item><el-form-item v-if="editingMemberId" label="状态"><el-select v-model="memberForm.status"><el-option label="正常" value="active" /><el-option label="停用" value="inactive" /></el-select></el-form-item></el-form><template #footer><el-button @click="memberDialog = false">取消</el-button><el-button type="primary" @click="saveMember">保存</el-button></template></el-dialog>
    <el-drawer :model-value="Boolean(metricDetail)" title="指标证据" size="520px" @update:model-value="(value: boolean) => { if (!value) metricDetail = null; }"><el-descriptions v-if="metricDetail" :column="1" border><el-descriptions-item label="指标">{{ metricDetail.metric?.name }}</el-descriptions-item><el-descriptions-item label="公式">{{ metricDetail.metric?.formula }}</el-descriptions-item><el-descriptions-item label="质量">{{ metricDetail.quality }}</el-descriptions-item><el-descriptions-item label="证据">{{ metricDetail.evidence?.[0]?.message || "暂无证据" }}</el-descriptions-item></el-descriptions></el-drawer>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.page-heading { display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; }
.page-heading small { color: var(--erp-muted-text); letter-spacing: .08em; }
.page-heading h1 { margin: 4px 0; }
.page-heading p { margin: 0; color: var(--erp-muted-text); }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.form-grid { display: grid; grid-template-columns: minmax(0, 760px); row-gap: 16px; max-width: 860px; }
.form-grid .el-form-item { width: 100%; }
.form-grid .form-actions { margin-left: 100px; width: auto; }
.muted { color: var(--erp-muted-text); }
.el-form { flex-wrap: wrap; align-items: center; }
.el-form-item { margin-bottom: 0; }
.form-actions { margin-left: 4px; }
.member-dialog-form { display: block; }
.member-dialog-form .el-form-item { width: 100%; margin-bottom: 12px; }
.member-dialog-form .el-form-item:last-child { margin-bottom: 0; }
:deep(.member-dialog-form .el-select),
:deep(.member-dialog-form .el-input) { width: 100%; }
:deep(.el-table th .cell),
:deep(.el-table td .cell) { text-align: center; }
</style>
