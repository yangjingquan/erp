<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { createReceipt, listReceipts, listReceivables, reconcileReceipt } from "../../api/finance";
import { useMasterOptions } from "../../composables/useMasterOptions";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const receiptRows = ref<Row[]>([]);
const loading = ref(false);
const saving = ref(false);
const errorMessage = ref("");
const dialogVisible = ref(false);
const reconcileDialogVisible = ref(false);
const reconciling = ref(false);
const reconcileReceiptRow = ref<Row | null>(null);
const form = reactive({ customer_id: "", amount: 0 });
const reconcileForm = reactive({ receivable_id: "", amount: 0 });
const { customers, loadOptions } = useMasterOptions();
function listFrom(response: any, fallbackMessage: string): Row[] { if (response?.data?.code !== 0) throw new Error(response?.data?.msg || fallbackMessage); const data = response?.data?.data; return Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : []; }
function customerLabel(customerId: string) { return customers.value.find((option) => option.value === String(customerId))?.label || customerId; }
function numeric(value: unknown) { const result = Number(value); return Number.isFinite(result) ? result : 0; }
function receiptRemaining(row: Row | null) { return Math.max(0, numeric(row?.amount) - numeric(row?.reconciled_amount)); }
function receivableRemaining(row: Row | null) { return Math.max(0, numeric(row?.total_amount) - numeric(row?.reconciled_amount)); }
function availableReceivables(receipt: Row | null) { if (!receipt?.customer_id) return []; return rows.value.filter((row) => String(row.customer_id) === String(receipt.customer_id) && receivableRemaining(row) > 0); }
const selectedReceivable = computed(() => rows.value.find((row) => String(row.id) === reconcileForm.receivable_id) || null);
const reconcileMaxAmount = computed(() => Math.min(receiptRemaining(reconcileReceiptRow.value), receivableRemaining(selectedReceivable.value)));
async function load() { loading.value = true; errorMessage.value = ""; try { const [receivablesResponse, receiptsResponse] = await Promise.all([listReceivables(), listReceipts()]); rows.value = listFrom(receivablesResponse, "应收账款接口返回失败"); receiptRows.value = listFrom(receiptsResponse, "收款记录接口返回失败"); } catch (error) { errorMessage.value = "应收账款或收款记录加载失败，请检查接口服务后重试"; } finally { loading.value = false; } }
function openCreate() { form.customer_id = ""; form.amount = 0; dialogVisible.value = true; }
function openReconcile(row: Row) { const options = availableReceivables(row); if (!options.length) { ElMessage.info("该客户暂无可核销的应收账款"); return; } reconcileReceiptRow.value = row; reconcileForm.receivable_id = String(options[0].id); reconcileForm.amount = Math.min(receiptRemaining(row), receivableRemaining(options[0])); reconcileDialogVisible.value = true; }
function selectReceivable(receivableId: string) { reconcileForm.receivable_id = receivableId; reconcileForm.amount = Math.min(receiptRemaining(reconcileReceiptRow.value), receivableRemaining(selectedReceivable.value)); }
async function save() { if (!form.customer_id || form.amount <= 0) { ElMessage.warning("请填写客户和大于 0 的收款金额"); return; } saving.value = true; try { const response = await createReceipt(form); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("收款单已创建"); dialogVisible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "收款单创建失败"); } finally { saving.value = false; } }
async function saveReconcile() { if (!reconcileReceiptRow.value?.id || !reconcileForm.receivable_id || reconcileForm.amount <= 0 || reconcileForm.amount > reconcileMaxAmount.value) { ElMessage.warning("请选择应收账款并填写不超过可核销余额的金额"); return; } reconciling.value = true; try { const response = await reconcileReceipt(String(reconcileReceiptRow.value.id), { receivable_id: reconcileForm.receivable_id, amount: reconcileForm.amount }); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("收款核销成功"); reconcileDialogVisible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "收款核销失败"); } finally { reconciling.value = false; } }
onMounted(async () => { await Promise.all([load(), loadOptions(["customers"])]); });
</script>

<template>
  <section>
    <el-page-header content="应收账款" />
    <el-space class="toolbar"><el-button type="primary" @click="openCreate">登记收款</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''"><template #default><el-button link type="primary" @click="load">重新加载</el-button></template></el-alert>
    <el-table v-loading="loading" :data="rows" stripe width="100%" fit><el-table-column prop="doc_no" label="应收单号" /><el-table-column label="客户"><template #default="scope">{{ scope.row.customer_name || scope.row.customer_id }}</template></el-table-column><el-table-column prop="total_amount" label="应收金额" /><el-table-column prop="reconciled_amount" label="已核销" /><el-table-column prop="status" label="状态" /></el-table>
    <el-divider content-position="left">收款记录</el-divider>
    <el-table v-loading="loading" :data="receiptRows" stripe width="100%" fit><el-table-column prop="doc_no" label="收款单号" /><el-table-column label="客户"><template #default="scope">{{ customerLabel(scope.row.customer_id) }}</template></el-table-column><el-table-column prop="amount" label="收款金额" /><el-table-column prop="receipt_date" label="收款日期" /><el-table-column prop="reconciled_amount" label="已核销" /><el-table-column prop="status" label="状态" /><el-table-column label="操作" width="100"><template #default="scope"><el-button v-if="receiptRemaining(scope.row) > 0" link type="primary" @click="openReconcile(scope.row)">核销</el-button><span v-else>已完成</span></template></el-table-column></el-table>
    <el-dialog v-model="dialogVisible" title="登记收款" width="440px"><el-form label-width="90px"><el-form-item label="客户" required><el-select v-model="form.customer_id" filterable clearable style="width: 100%"><el-option v-for="option in customers" :key="option.value" v-bind="option" /></el-select></el-form-item><el-form-item label="收款金额" required><el-input-number v-model="form.amount" :min="0.01" :precision="2" /></el-form-item></el-form><template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template></el-dialog>
    <el-dialog v-model="reconcileDialogVisible" title="收款核销" width="500px"><el-form label-width="90px"><el-form-item label="收款单号"><span>{{ reconcileReceiptRow?.doc_no }}</span></el-form-item><el-form-item label="客户"><span>{{ customerLabel(reconcileReceiptRow?.customer_id) }}</span></el-form-item><el-form-item label="应收账款" required><el-select :model-value="reconcileForm.receivable_id" filterable style="width: 100%" @update:model-value="selectReceivable"><el-option v-for="option in availableReceivables(reconcileReceiptRow)" :key="option.id" :label="`${option.doc_no}（剩余 ${receivableRemaining(option).toFixed(2)}）`" :value="String(option.id)" /></el-select></el-form-item><el-form-item label="核销金额" required><el-input-number v-model="reconcileForm.amount" :min="0.01" :max="reconcileMaxAmount" :precision="2" /><span class="amount-hint">最多可核销 {{ reconcileMaxAmount.toFixed(2) }}</span></el-form-item></el-form><template #footer><el-button @click="reconcileDialogVisible = false">取消</el-button><el-button type="primary" :loading="reconciling" @click="saveReconcile">确认核销</el-button></template></el-dialog>
  </section>
</template>

<style scoped>.toolbar { margin: 16px 0; } .amount-hint { margin-left: 12px; color: var(--el-text-color-secondary); }</style>
