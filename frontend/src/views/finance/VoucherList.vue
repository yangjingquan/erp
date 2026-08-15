<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { createManualVoucher, listAccountingDimensions, listFinanceAccounts, listVouchers, postVoucher, reverseVoucher } from "../../api/finance";
import DocumentWorkbench from "../../components/DocumentWorkbench.vue";
import { useClientPagination } from "../../composables/useClientPagination";
import { localDateString } from "../../utils/time";
import { statusLabel, tagTypeOf } from "../../utils/labels";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const filters = reactive({ voucher_no: "", voucher_date: "", status: "" });
const filteredRows = computed(() => rows.value.filter((row) => (!filters.voucher_no || String(row.voucher_no || "").includes(filters.voucher_no)) && (!filters.voucher_date || String(row.voucher_date || "").startsWith(filters.voucher_date)) && (!filters.status || row.status === filters.status)));
const { pagedRows, page, pageSize, total, updatePageSize } = useClientPagination(filteredRows);
const loading = ref(false);
const actionLoading = ref<string | null>(null);
const errorMessage = ref("");
const detailVisible = ref(false);
const selected = ref<Row | null>(null);
const manualVisible = ref(false);
const saving = ref(false);
const accounts = ref<Row[]>([]);
const dimensions = ref<Row[]>([]);
const voucherForm = reactive({
  voucher_date: localDateString(),
  entries: [] as Array<{ account_code: string; summary: string; debit_amount: number; credit_amount: number; dimensions: Record<string, string> }>,
});
const totals = computed(() => voucherForm.entries.reduce((result, item) => ({ debit: result.debit + Number(item.debit_amount || 0), credit: result.credit + Number(item.credit_amount || 0) }), { debit: 0, credit: 0 }));
const balanced = computed(() => {
  const requiredDimensions = dimensions.value.filter((item) => item.required);
  return totals.value.debit > 0
    && Math.abs(totals.value.debit - totals.value.credit) < 0.005
    && voucherForm.entries.every((item) => item.account_code
      && ((item.debit_amount > 0) !== (item.credit_amount > 0))
      && requiredDimensions.every((dimension) => String(item.dimensions[dimension.code] || "").trim()));
});
function listFrom(response: any): Row[] { if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "会计凭证接口返回失败"); const data = response?.data?.data; return Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : []; }
async function load() { loading.value = true; errorMessage.value = ""; try { rows.value = listFrom(await listVouchers()); } catch (error) { errorMessage.value = "会计凭证加载失败，请检查接口服务后重试"; } finally { loading.value = false; } }
function blankEntry() { return { account_code: "", summary: "", debit_amount: 0, credit_amount: 0, dimensions: {} as Record<string, string> }; }
async function openManualVoucher() {
  try {
    const [accountResponse, dimensionResponse] = await Promise.all([listFinanceAccounts({ page: 1, page_size: 200 }), listAccountingDimensions()]);
    accounts.value = listFrom(accountResponse).filter((item) => item.status === "active" && item.allow_posting);
    dimensions.value = listFrom(dimensionResponse).filter((item) => item.status === "active");
    voucherForm.voucher_date = localDateString();
    voucherForm.entries = [blankEntry(), blankEntry()];
    manualVisible.value = true;
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "会计科目加载失败"); }
}
function changeAmount(entry: Row, side: "debit" | "credit") { if (side === "debit" && Number(entry.debit_amount) > 0) entry.credit_amount = 0; if (side === "credit" && Number(entry.credit_amount) > 0) entry.debit_amount = 0; }
async function saveManualVoucher() {
  if (!balanced.value) { ElMessage.warning("请补全凭证明细，并确保借贷相等且每行只填写一方金额"); return; }
  saving.value = true;
  try {
    const response = await createManualVoucher({ voucher_date: voucherForm.voucher_date, entries: voucherForm.entries });
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success("手工凭证已创建，请复核后记账"); manualVisible.value = false; await load();
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "手工凭证创建失败"); }
  finally { saving.value = false; }
}
async function changeStatus(row: Row, action: "post" | "reverse") { try { await ElMessageBox.confirm(`确认${action === "post" ? "记账" : "冲销"}凭证“${row.voucher_no}”吗？`, "会计凭证操作", { type: "warning" }); actionLoading.value = String(row.id); const response = action === "post" ? await postVoucher(String(row.id)) : await reverseVoucher(String(row.id)); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success(action === "post" ? "凭证已记账" : "凭证已冲销"); await load(); } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "凭证操作失败"); } finally { actionLoading.value = null; } }
function openDetail(row: Row) { selected.value = row; detailVisible.value = true; }
onMounted(load);
</script>

<template>
  <section>
    <el-page-header content="会计凭证" />
    <el-space class="toolbar" wrap><el-input v-model="filters.voucher_no" clearable placeholder="凭证号" style="width:180px" /><el-date-picker v-model="filters.voucher_date" type="date" value-format="YYYY-MM-DD" placeholder="凭证日期" /><el-select v-model="filters.status" clearable placeholder="状态" style="width:140px"><el-option label="草稿" value="draft"/><el-option label="已过账" value="posted"/><el-option label="已冲销" value="reversed"/></el-select><el-button type="primary" @click="openManualVoucher">新增手工凭证</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''"><template #default><el-button link type="primary" @click="load">重新加载</el-button></template></el-alert>
    <el-table v-loading="loading" :data="pagedRows" stripe width="100%" fit><el-table-column label="凭证号"><template #default="scope"><el-button link type="primary" @click="openDetail(scope.row)">{{ scope.row.voucher_no }}</el-button></template></el-table-column><el-table-column prop="voucher_date" label="日期" /><el-table-column prop="total_debit" label="借方合计" /><el-table-column prop="total_credit" label="贷方合计" /><el-table-column label="状态"><template #default="scope"><el-tag :type="tagTypeOf(scope.row.status)" effect="light">{{ statusLabel(scope.row.status) }}</el-tag></template></el-table-column><el-table-column label="操作" width="220"><template #default="scope"><el-button v-if="scope.row.status === 'draft'" link type="success" :loading="actionLoading === scope.row.id" @click="changeStatus(scope.row, 'post')">记账</el-button><el-button v-if="scope.row.status === 'posted'" link type="danger" :loading="actionLoading === scope.row.id" @click="changeStatus(scope.row, 'reverse')">冲销</el-button><el-button link @click="openDetail(scope.row)">详情</el-button></template></el-table-column></el-table>
    <ClientPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @update:page-size="updatePageSize" />
    <DocumentWorkbench v-if="selected" v-model:visible="detailVisible" business-type="fin_voucher" :business-id="String(selected.id)" @changed="load" />
    <el-dialog v-model="manualVisible" title="新增手工凭证" width="1120px" destroy-on-close>
      <el-form label-width="90px"><el-form-item label="凭证日期" required><el-date-picker v-model="voucherForm.voucher_date" type="date" value-format="YYYY-MM-DD" /></el-form-item></el-form>
      <el-table :data="voucherForm.entries" border>
        <el-table-column label="会计科目" min-width="220"><template #default="scope"><el-select v-model="scope.row.account_code" filterable style="width: 100%"><el-option v-for="item in accounts" :key="item.id" :label="`${item.code} · ${item.name}`" :value="item.code" /></el-select></template></el-table-column>
        <el-table-column label="摘要" min-width="220"><template #default="scope"><el-input v-model="scope.row.summary" maxlength="255" /></template></el-table-column>
        <el-table-column label="核算维度" min-width="210"><template #default="scope"><div v-if="dimensions.length" class="dimension-list"><el-input v-for="dimension in dimensions" :key="dimension.id" v-model="scope.row.dimensions[dimension.code]" :placeholder="`${dimension.name}${dimension.required ? '（必填）' : ''}`" clearable /></div><span v-else>-</span></template></el-table-column>
        <el-table-column label="借方金额" width="170"><template #default="scope"><el-input-number v-model="scope.row.debit_amount" :min="0" :precision="2" :controls="false" style="width: 100%" @change="changeAmount(scope.row, 'debit')" /></template></el-table-column>
        <el-table-column label="贷方金额" width="170"><template #default="scope"><el-input-number v-model="scope.row.credit_amount" :min="0" :precision="2" :controls="false" style="width: 100%" @change="changeAmount(scope.row, 'credit')" /></template></el-table-column>
        <el-table-column label="操作" width="80"><template #default="scope"><el-button link type="danger" :disabled="voucherForm.entries.length <= 2" @click="voucherForm.entries.splice(scope.$index, 1)">删除</el-button></template></el-table-column>
      </el-table>
      <div class="voucher-summary"><el-button link type="primary" @click="voucherForm.entries.push(blankEntry())">添加明细</el-button><span>借方合计：¥{{ totals.debit.toFixed(2) }}</span><span>贷方合计：¥{{ totals.credit.toFixed(2) }}</span><el-tag :type="balanced ? 'success' : 'danger'">{{ balanced ? '借贷平衡' : '借贷不平衡' }}</el-tag></div>
      <template #footer><el-button @click="manualVisible = false">取消</el-button><el-button type="primary" :loading="saving" :disabled="!balanced" @click="saveManualVoucher">创建凭证</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>.toolbar { margin: 16px 0; }.voucher-summary { display: flex; justify-content: flex-end; align-items: center; gap: 18px; margin-top: 14px; }.dimension-list { display: grid; gap: 6px; }</style>
