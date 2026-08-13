<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  closeFiscalPeriod,
  createAccountingDimension,
  createAsset,
  createBankAccount,
  createFiscalPeriod,
  createFinanceAccount,
  listAccountingDimensions,
  listAssets,
  listBankAccounts,
  listFinanceAccounts,
  listFiscalPeriods,
  reopenFiscalPeriod,
  runAssetDepreciation,
} from "../../api/finance";
import { localDateString, localMonthString } from "../../utils/time";

type Row = Record<string, unknown>;
const activeTab = ref("accounts");
const loading = ref(false);
const saving = ref(false);
const errorMessage = ref("");
const accounts = ref<Row[]>([]);
const dimensions = ref<Row[]>([]);
const periods = ref<Row[]>([]);
const banks = ref<Row[]>([]);
const assets = ref<Row[]>([]);
const dialog = ref("");
const form = reactive<Record<string, any>>({});
const activeAccounts = computed(() => accounts.value.filter((item) => item.status === "active" && item.allow_posting));
const dialogTitle = computed(() => ({ account: "新增会计科目", dimension: "新增核算维度", bank: "新增银行账户", asset: "新增固定资产" } as Record<string, string>)[dialog.value] || "");

function unwrap(response: any): any {
  if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "财务基础接口返回失败");
  return response.data.data;
}

async function load() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const [accountData, dimensionData, periodData, bankData, assetData] = await Promise.all([
      listFinanceAccounts({ page: 1, page_size: 200 }), listAccountingDimensions(), listFiscalPeriods(), listBankAccounts(), listAssets(),
    ]);
    accounts.value = unwrap(accountData).items || [];
    dimensions.value = unwrap(dimensionData) || [];
    periods.value = unwrap(periodData) || [];
    banks.value = unwrap(bankData) || [];
    assets.value = unwrap(assetData) || [];
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "财务基础数据加载失败";
  } finally { loading.value = false; }
}

function open(kind: string) {
  Object.keys(form).forEach((key) => delete form[key]);
  if (kind === "account") Object.assign(form, { code: "", name: "", account_type: "asset", balance_direction: "debit", parent_id: null, allow_posting: true });
  if (kind === "dimension") Object.assign(form, { code: "", name: "", dimension_type: "department", required: false });
  if (kind === "bank") Object.assign(form, { name: "", bank_name: "", account_no: "", currency: "CNY", ledger_account_id: "" });
  if (kind === "asset") Object.assign(form, { asset_code: "", asset_name: "", category: "", purchase_date: localDateString(), original_value: 0, useful_life_months: 60, residual_rate: 0, depreciation_account_code: "1602", expense_account_code: "6602" });
  dialog.value = kind;
}

async function save() {
  saving.value = true;
  try {
    if (dialog.value === "account") unwrap(await createFinanceAccount({ ...form }));
    if (dialog.value === "dimension") unwrap(await createAccountingDimension({ ...form }));
    if (dialog.value === "bank") unwrap(await createBankAccount({ ...form }));
    if (dialog.value === "asset") unwrap(await createAsset({ ...form }));
    ElMessage.success("保存成功"); dialog.value = ""; await load();
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "保存失败"); }
  finally { saving.value = false; }
}

async function changePeriod(row: Row, action: "close" | "reopen") {
  const period = String(row.period);
  try {
    await ElMessageBox.confirm(`确认${action === "close" ? "结账" : "重开"}会计期间 ${period} 吗？`, "会计期间操作", { type: "warning" });
    unwrap(action === "close" ? await closeFiscalPeriod(period) : await reopenFiscalPeriod(period));
    ElMessage.success(action === "close" ? "期间已结账" : "期间已重开"); await load();
  } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "期间操作失败"); }
}

async function addPeriod() {
  try {
    const result = await ElMessageBox.prompt("请输入会计期间（YYYY-MM）", "新增会计期间", { inputValue: localMonthString(), inputPattern: /^\d{4}-(0[1-9]|1[0-2])$/, inputErrorMessage: "期间格式不正确" });
    const [year, month] = result.value.split("-").map(Number);
    const lastDay = new Date(year, month, 0).getDate();
    unwrap(await createFiscalPeriod({ period: result.value, start_date: `${result.value}-01`, end_date: `${result.value}-${String(lastDay).padStart(2, "0")}` }));
    ElMessage.success("会计期间已创建"); await load();
  } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "会计期间创建失败"); }
}

async function depreciate(row: Row) {
  try {
    const result = await ElMessageBox.prompt("请输入计提期间（YYYY-MM）", "计提折旧", { inputValue: localMonthString(), inputPattern: /^\d{4}-(0[1-9]|1[0-2])$/, inputErrorMessage: "期间格式不正确" });
    unwrap(await runAssetDepreciation(String(row.id), result.value));
    ElMessage.success("折旧已计提并自动记账"); await load();
  } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "折旧计提失败"); }
}

onMounted(load);
</script>

<template>
  <section class="page-stack">
    <header class="page-heading"><div><small>GENERAL LEDGER FOUNDATION</small><h1>总账基础</h1><p>统一维护科目、核算维度、期间、银行账户与固定资产。</p></div><el-button :loading="loading" @click="load">刷新</el-button></header>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''" />
    <el-card v-loading="loading" shadow="never">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="会计科目" name="accounts"><div class="toolbar"><el-button type="primary" @click="open('account')">新增科目</el-button></div><el-table :data="accounts" stripe><el-table-column prop="code" label="科目编码" /><el-table-column prop="name" label="科目名称" /><el-table-column prop="account_type" label="科目类型" /><el-table-column prop="balance_direction" label="余额方向" /><el-table-column prop="allow_posting" label="允许记账"><template #default="scope">{{ scope.row.allow_posting ? '是' : '否' }}</template></el-table-column><el-table-column prop="status" label="状态" /></el-table></el-tab-pane>
        <el-tab-pane label="核算维度" name="dimensions"><div class="toolbar"><el-button type="primary" @click="open('dimension')">新增维度</el-button></div><el-table :data="dimensions" stripe><el-table-column prop="code" label="维度编码" /><el-table-column prop="name" label="名称" /><el-table-column prop="dimension_type" label="类型" /><el-table-column label="必填"><template #default="scope">{{ scope.row.required ? '是' : '否' }}</template></el-table-column><el-table-column prop="status" label="状态" /></el-table></el-tab-pane>
        <el-tab-pane label="会计期间" name="periods"><div class="toolbar"><el-button type="primary" @click="addPeriod">新增期间</el-button></div><el-table :data="periods" stripe><el-table-column prop="period" label="期间" /><el-table-column prop="start_date" label="开始日期" /><el-table-column prop="end_date" label="结束日期" /><el-table-column prop="status" label="状态" /><el-table-column label="操作"><template #default="scope"><el-button v-if="scope.row.status === 'open'" link type="warning" @click="changePeriod(scope.row, 'close')">结账</el-button><el-button v-else link type="primary" @click="changePeriod(scope.row, 'reopen')">重开</el-button></template></el-table-column></el-table></el-tab-pane>
        <el-tab-pane label="银行账户" name="banks"><div class="toolbar"><el-button type="primary" @click="open('bank')">新增银行账户</el-button></div><el-table :data="banks" stripe><el-table-column prop="name" label="账户名称" /><el-table-column prop="bank_name" label="开户银行" /><el-table-column prop="account_no_masked" label="银行账号" /><el-table-column prop="currency" label="币种" /><el-table-column prop="status" label="状态" /></el-table></el-tab-pane>
        <el-tab-pane label="固定资产" name="assets"><div class="toolbar"><el-button type="primary" @click="open('asset')">新增资产</el-button></div><el-table :data="assets" stripe><el-table-column prop="asset_code" label="资产编码" /><el-table-column prop="asset_name" label="资产名称" /><el-table-column prop="original_value" label="原值" /><el-table-column prop="accumulated_depreciation" label="累计折旧" /><el-table-column prop="net_value" label="净值" /><el-table-column prop="last_depreciation_period" label="最近计提期间" /><el-table-column label="操作"><template #default="scope"><el-button link type="primary" @click="depreciate(scope.row)">计提折旧</el-button></template></el-table-column></el-table></el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog :model-value="Boolean(dialog)" :title="dialogTitle" width="600px" @update:model-value="(visible: boolean) => { if (!visible) dialog = '' }">
      <el-form label-width="110px">
        <template v-if="dialog === 'account'"><el-form-item label="科目编码" required><el-input v-model="form.code" /></el-form-item><el-form-item label="科目名称" required><el-input v-model="form.name" /></el-form-item><el-form-item label="科目类型"><el-select v-model="form.account_type"><el-option v-for="item in ['asset','liability','equity','cost','revenue','expense']" :key="item" :label="item" :value="item" /></el-select></el-form-item><el-form-item label="余额方向"><el-radio-group v-model="form.balance_direction"><el-radio value="debit">借</el-radio><el-radio value="credit">贷</el-radio></el-radio-group></el-form-item><el-form-item label="允许记账"><el-switch v-model="form.allow_posting" /></el-form-item></template>
        <template v-if="dialog === 'dimension'"><el-form-item label="维度编码" required><el-input v-model="form.code" /></el-form-item><el-form-item label="维度名称" required><el-input v-model="form.name" /></el-form-item><el-form-item label="维度类型"><el-select v-model="form.dimension_type"><el-option v-for="item in ['department','customer','supplier','employee','project','custom']" :key="item" :label="item" :value="item" /></el-select></el-form-item><el-form-item label="凭证必填"><el-switch v-model="form.required" /></el-form-item></template>
        <template v-if="dialog === 'bank'"><el-form-item label="账户名称" required><el-input v-model="form.name" /></el-form-item><el-form-item label="开户银行" required><el-input v-model="form.bank_name" /></el-form-item><el-form-item label="银行账号" required><el-input v-model="form.account_no" /></el-form-item><el-form-item label="币种"><el-input v-model="form.currency" /></el-form-item><el-form-item label="会计科目" required><el-select v-model="form.ledger_account_id" filterable><el-option v-for="item in activeAccounts" :key="String(item.id)" :label="`${item.code} · ${item.name}`" :value="item.id" /></el-select></el-form-item></template>
        <template v-if="dialog === 'asset'"><el-form-item label="资产编码" required><el-input v-model="form.asset_code" /></el-form-item><el-form-item label="资产名称" required><el-input v-model="form.asset_name" /></el-form-item><el-form-item label="类别"><el-input v-model="form.category" /></el-form-item><el-form-item label="购置日期"><el-date-picker v-model="form.purchase_date" value-format="YYYY-MM-DD" /></el-form-item><el-form-item label="资产原值"><el-input-number v-model="form.original_value" :min="0.01" :precision="2" /></el-form-item><el-form-item label="使用月数"><el-input-number v-model="form.useful_life_months" :min="1" /></el-form-item><el-form-item label="残值率"><el-input-number v-model="form.residual_rate" :min="0" :max="0.99" :step="0.01" :precision="4" /></el-form-item></template>
      </el-form><template #footer><el-button @click="dialog = ''">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }.page-heading { display: flex; justify-content: space-between; align-items: flex-end; }.page-heading small { color: var(--erp-muted-text); letter-spacing: .08em; }.page-heading h1 { margin: 4px 0; }.page-heading p { margin: 0; color: var(--erp-muted-text); }.toolbar { display: flex; justify-content: flex-end; margin-bottom: 12px; }
</style>
