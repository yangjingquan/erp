<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { createPayment, listPayments, listPayables, reconcilePayment } from "../../api/finance";
import { useMasterOptions } from "../../composables/useMasterOptions";
import { useClientPagination } from "../../composables/useClientPagination";
import { labelOf, reconciliationRecordStatusLabels, reconciliationStatusLabels } from "../../utils/labels";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const paymentRows = ref<Row[]>([]);
const filters = reactive({ docNo: "", supplier: "", status: "" });
const filteredRows = computed(() => rows.value.filter((row) => (!filters.docNo || String(row.doc_no || "").toLowerCase().includes(filters.docNo.toLowerCase())) && (!filters.supplier || String(row.supplier_name || row.supplier_id || "").toLowerCase().includes(filters.supplier.toLowerCase())) && (!filters.status || row.status === filters.status)));
const filteredPaymentRows = computed(() => paymentRows.value.filter((row) => (!filters.docNo || String(row.doc_no || "").toLowerCase().includes(filters.docNo.toLowerCase())) && (!filters.supplier || String(row.supplier_name || row.supplier_id || "").toLowerCase().includes(filters.supplier.toLowerCase())) && (!filters.status || row.status === filters.status)));
const { pagedRows: payableRows, page: payablePage, pageSize: payablePageSize, total: payableTotal, updatePageSize: updatePayablePageSize } = useClientPagination(filteredRows);
const { pagedRows: paymentRowsPage, page: paymentPage, pageSize: paymentPageSize, total: paymentTotal, updatePageSize: updatePaymentPageSize } = useClientPagination(filteredPaymentRows);
const loading = ref(false);
const saving = ref(false);
const reconciling = ref(false);
const errorMessage = ref("");
const dialogVisible = ref(false);
const reconcileDialogVisible = ref(false);
const reconcilePaymentRow = ref<Row | null>(null);
const form = reactive({ supplier_id: "", amount: 0 });
const reconcileForm = reactive({ payable_id: "", amount: 0 });
const { suppliers, loadOptions } = useMasterOptions();
function listFrom(response: any, fallbackMessage: string): Row[] { if (response?.data?.code !== 0) throw new Error(response?.data?.msg || fallbackMessage); const data = response?.data?.data; return Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : []; }
function supplierLabel(supplierId: unknown) { const value = String(supplierId || ""); return suppliers.value.find((option) => option.value === value)?.label || value || "-"; }
function numeric(value: unknown) { const result = Number(value); return Number.isFinite(result) ? result : 0; }
function paymentRemaining(row: Row | null) { return Math.max(0, numeric(row?.amount) - numeric(row?.reconciled_amount)); }
function payableRemaining(row: Row | null) { return Math.max(0, numeric(row?.total_amount) - numeric(row?.reconciled_amount)); }
function availablePayables(payment: Row | null) { if (!payment?.supplier_id) return []; return rows.value.filter((row) => String(row.supplier_id) === String(payment.supplier_id) && payableRemaining(row) > 0); }
const selectedPayable = computed(() => rows.value.find((row) => String(row.id) === reconcileForm.payable_id) || null);
const reconcileMaxAmount = computed(() => Math.min(paymentRemaining(reconcilePaymentRow.value), payableRemaining(selectedPayable.value)));
function statusTagType(status: string) { return ({ open: "info", partial: "warning", settled: "success" } as Record<string, string>)[status] || "info"; }
function paymentStatusTagType(status: string) { return ({ draft: "info", confirmed: "success", partial: "warning", settled: "success" } as Record<string, string>)[status] || "info"; }
function reconciledLabel(row: Row) { const amount = numeric(row.reconciled_amount); return amount <= 0 ? "未核销" : amount >= numeric(row.total_amount || row.amount) ? "已核销" : "部分核销"; }
function reconciledTagType(row: Row) { const label = reconciledLabel(row); return label === "已核销" ? "success" : label === "部分核销" ? "warning" : "info"; }
function paymentReconciledLabel(row: Row) { return reconciledLabel({ ...row, total_amount: row.amount }); }
function paymentReconciledTagType(row: Row) { return reconciledTagType({ ...row, total_amount: row.amount }); }
async function load() { loading.value = true; errorMessage.value = ""; try { const [payablesResponse, paymentsResponse] = await Promise.all([listPayables(), listPayments()]); rows.value = listFrom(payablesResponse, "应付账款接口返回失败"); paymentRows.value = listFrom(paymentsResponse, "付款记录接口返回失败"); } catch (error) { errorMessage.value = "应付账款或付款记录加载失败，请检查接口服务后重试"; } finally { loading.value = false; } }
function openCreate() { form.supplier_id = ""; form.amount = 0; dialogVisible.value = true; }
function openReconcile(row: Row) { const options = availablePayables(row); if (!options.length) { ElMessage.info("该供应商暂无可核销的应付账款"); return; } reconcilePaymentRow.value = row; reconcileForm.payable_id = String(options[0].id); reconcileForm.amount = Math.min(paymentRemaining(row), payableRemaining(options[0])); reconcileDialogVisible.value = true; }
function selectPayable(payableId: string) { reconcileForm.payable_id = payableId; reconcileForm.amount = Math.min(paymentRemaining(reconcilePaymentRow.value), payableRemaining(selectedPayable.value)); }
async function save() { if (!form.supplier_id || form.amount <= 0) { ElMessage.warning("请填写供应商和大于 0 的付款金额"); return; } saving.value = true; try { const response = await createPayment(form); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("付款单已创建"); dialogVisible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "付款单创建失败"); } finally { saving.value = false; } }
async function saveReconcile() { if (!reconcilePaymentRow.value?.id || !reconcileForm.payable_id || reconcileForm.amount <= 0 || reconcileForm.amount > reconcileMaxAmount.value) { ElMessage.warning("请选择应付账款并填写不超过可核销余额的金额"); return; } reconciling.value = true; try { const response = await reconcilePayment(String(reconcilePaymentRow.value.id), { payable_id: reconcileForm.payable_id, amount: reconcileForm.amount }); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("付款核销成功"); reconcileDialogVisible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "付款核销失败"); } finally { reconciling.value = false; } }
onMounted(async () => { await Promise.all([load(), loadOptions(["suppliers"])]); });
</script>

<template>
  <section>
    <el-page-header content="应付账款" />
    <el-space class="toolbar"><el-input v-model="filters.docNo" placeholder="按单号筛选" clearable style="width: 180px" /><el-input v-model="filters.supplier" placeholder="按供应商筛选" clearable style="width: 180px" /><el-select v-model="filters.status" placeholder="按状态筛选" clearable style="width: 150px"><el-option label="未核销" value="open" /><el-option label="部分核销" value="partial" /><el-option label="已核销" value="settled" /></el-select><el-button type="primary" @click="openCreate">登记付款</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''"><template #default><el-button link type="primary" @click="load">重新加载</el-button></template></el-alert>
    <el-table v-loading="loading" :data="payableRows" stripe width="100%" fit :header-cell-style="{ textAlign: 'center' }" :cell-style="{ textAlign: 'center' }"><el-table-column prop="doc_no" label="应付单号" /><el-table-column label="供应商"><template #default="scope">{{ scope.row.supplier_name || supplierLabel(scope.row.supplier_id) }}</template></el-table-column><el-table-column prop="total_amount" label="应付金额" /><el-table-column label="已核销"><template #default="scope"><el-tag class="status-tag" :type="reconciledTagType(scope.row)" effect="light">{{ reconciledLabel(scope.row) }}</el-tag></template></el-table-column><el-table-column label="状态"><template #default="scope"><el-tag class="status-tag" :type="statusTagType(scope.row.status)" effect="light">{{ labelOf(reconciliationStatusLabels, scope.row.status) }}</el-tag></template></el-table-column></el-table>
    <ClientPagination v-model:page="payablePage" v-model:page-size="payablePageSize" :total="payableTotal" @update:page-size="updatePayablePageSize" />
    <el-divider content-position="left">付款记录</el-divider>
    <el-table v-loading="loading" :data="paymentRowsPage" stripe width="100%" fit :header-cell-style="{ textAlign: 'center' }" :cell-style="{ textAlign: 'center' }"><el-table-column prop="doc_no" label="付款单号" /><el-table-column label="供应商"><template #default="scope">{{ supplierLabel(scope.row.supplier_id) }}</template></el-table-column><el-table-column prop="amount" label="付款金额" /><el-table-column prop="payment_date" label="付款日期" /><el-table-column label="已核销"><template #default="scope"><el-tag class="status-tag" :type="paymentReconciledTagType(scope.row)" effect="light">{{ paymentReconciledLabel(scope.row) }}</el-tag></template></el-table-column><el-table-column label="状态"><template #default="scope"><el-tag class="status-tag" :type="paymentStatusTagType(scope.row.status)" effect="light">{{ labelOf(reconciliationRecordStatusLabels, scope.row.status) }}</el-tag></template></el-table-column><el-table-column label="操作" width="100"><template #default="scope"><el-button v-if="paymentRemaining(scope.row) > 0" link type="primary" @click="openReconcile(scope.row)">核销</el-button><span v-else>已完成</span></template></el-table-column></el-table>
    <ClientPagination v-model:page="paymentPage" v-model:page-size="paymentPageSize" :total="paymentTotal" @update:page-size="updatePaymentPageSize" />
    <el-dialog v-model="dialogVisible" title="登记付款" width="440px"><el-form label-width="90px"><el-form-item label="供应商" required><el-select v-model="form.supplier_id" filterable clearable style="width: 100%"><el-option v-for="option in suppliers" :key="option.value" v-bind="option" /></el-select></el-form-item><el-form-item label="付款金额" required><el-input-number v-model="form.amount" :min="0.01" :precision="2" /></el-form-item></el-form><template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template></el-dialog>
    <el-dialog v-model="reconcileDialogVisible" title="付款核销" width="500px"><el-form label-width="90px"><el-form-item label="付款单号"><span>{{ reconcilePaymentRow?.doc_no }}</span></el-form-item><el-form-item label="供应商"><span>{{ supplierLabel(reconcilePaymentRow?.supplier_id) }}</span></el-form-item><el-form-item label="应付账款" required><el-select :model-value="reconcileForm.payable_id" filterable style="width: 100%" @update:model-value="selectPayable"><el-option v-for="option in availablePayables(reconcilePaymentRow)" :key="option.id" :label="`${option.doc_no}（剩余 ${payableRemaining(option).toFixed(2)}）`" :value="String(option.id)" /></el-select></el-form-item><el-form-item label="核销金额" required><el-input-number v-model="reconcileForm.amount" :min="0.01" :max="reconcileMaxAmount" :precision="2" /><span class="amount-hint">最多可核销 {{ reconcileMaxAmount.toFixed(2) }}</span></el-form-item></el-form><template #footer><el-button @click="reconcileDialogVisible = false">取消</el-button><el-button type="primary" :loading="reconciling" @click="saveReconcile">确认核销</el-button></template></el-dialog>
  </section>
</template>

<style scoped>
.toolbar { margin: 16px 0; }
.amount-hint { margin-left: 12px; color: var(--el-text-color-secondary); }
.reconciled-cell { display: inline-flex; align-items: center; justify-content: center; gap: 8px; }
.status-tag { border-width: 1px; }
.status-tag.el-tag--success { background: var(--erp-green-bg); border-color: var(--erp-green); color: var(--erp-green); }
.status-tag.el-tag--warning { background: var(--erp-amber-bg); border-color: var(--erp-amber); color: var(--erp-amber); }
.status-tag.el-tag--info { background: var(--erp-panel-soft); border-color: var(--erp-border); color: var(--erp-muted-text); }
</style>
