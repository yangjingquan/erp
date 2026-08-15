<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { approveExpense, createExpense, generateVoucher, listExpenses, settleExpense } from "../../api/finance";
import { useClientPagination } from "../../composables/useClientPagination";
import { statusLabel, tagTypeOf } from "../../utils/labels";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const filters = reactive({ doc_no: "", expense_type: "", status: "" });
const filteredRows = computed(() => rows.value.filter((row) => (!filters.doc_no || String(row.doc_no || "").includes(filters.doc_no)) && (!filters.expense_type || row.expense_type === filters.expense_type) && (!filters.status || row.status === filters.status)));
const { pagedRows, page, pageSize, total, updatePageSize } = useClientPagination(filteredRows);
const loading = ref(false);
const saving = ref(false);
const actionLoading = ref<string | null>(null);
const errorMessage = ref("");
const dialogVisible = ref(false);
const form = reactive({ expense_type: "", amount: 0, description: "" });
function listFrom(response: any): Row[] { if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "费用报销接口返回失败"); const data = response?.data?.data; return Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : []; }
async function load() { loading.value = true; errorMessage.value = ""; try { rows.value = listFrom(await listExpenses()); } catch (error) { errorMessage.value = "费用报销加载失败，请检查接口服务后重试"; } finally { loading.value = false; } }
function openCreate() { form.expense_type = ""; form.amount = 0; form.description = ""; dialogVisible.value = true; }
async function save() { if (!form.expense_type || form.amount <= 0) { ElMessage.warning("请填写费用类型和大于 0 的金额"); return; } saving.value = true; try { const response = await createExpense(form); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("报销单已创建"); dialogVisible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "报销单创建失败"); } finally { saving.value = false; } }
async function createVoucher(row: Row) { const id = String(row.id || ""); if (!id) { ElMessage.error("报销单缺少有效 ID，无法生成凭证"); return; } try { await ElMessageBox.confirm(`确认根据报销单“${row.doc_no || id}”生成凭证吗？`, "操作确认", { type: "warning" }); const response = await generateVoucher("expense", id); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("报销凭证已生成"); await load(); } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "报销凭证生成失败"); } }
async function changeStatus(row: Row, action: "approve" | "settle") { const id = String(row.id || ""); if (!id) { ElMessage.error("报销单缺少有效 ID，无法操作"); return; } const label = action === "approve" ? "审核报销单" : "结算报销单"; try { await ElMessageBox.confirm(`确认${label}“${row.doc_no || id}”吗？`, "操作确认", { type: "warning" }); actionLoading.value = id; const response = action === "approve" ? await approveExpense(id) : await settleExpense(id); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success(`${label}成功`); await load(); } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : `${label}失败`); } finally { actionLoading.value = null; } }
onMounted(load);
</script>

<template>
  <section>
    <el-page-header content="费用报销" />
    <el-space class="toolbar" wrap><el-input v-model="filters.doc_no" clearable placeholder="报销单号" style="width:180px" /><el-select v-model="filters.expense_type" clearable placeholder="费用类型" style="width:160px"><el-option label="办公费用" value="办公费用"/><el-option label="差旅费用" value="差旅费用"/><el-option label="交通费用" value="交通费用"/><el-option label="业务招待" value="业务招待"/><el-option label="其他费用" value="其他费用"/></el-select><el-select v-model="filters.status" clearable placeholder="状态" style="width:140px"><el-option label="草稿" value="draft"/><el-option label="已审核" value="approved"/><el-option label="已结算" value="settled"/></el-select><el-button type="primary" @click="openCreate">新建报销</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''"><template #default><el-button link type="primary" @click="load">重新加载</el-button></template></el-alert>
    <el-table v-loading="loading" :data="pagedRows" stripe width="100%" fit :header-cell-style="{ textAlign: 'center' }" :cell-style="{ textAlign: 'center' }"><el-table-column prop="doc_no" label="报销单号" /><el-table-column prop="expense_type" label="费用类型" /><el-table-column prop="amount" label="金额" /><el-table-column label="状态"><template #default="scope"><el-tag :type="tagTypeOf(scope.row.status)" effect="light">{{ statusLabel(scope.row.status) }}</el-tag></template></el-table-column><el-table-column label="操作" width="260"><template #default="scope"><el-button v-if="scope.row.status === 'draft'" link type="primary" :loading="actionLoading === scope.row.id" @click="changeStatus(scope.row, 'approve')">审核</el-button><el-button v-if="scope.row.status === 'approved'" link type="warning" :loading="actionLoading === scope.row.id" @click="changeStatus(scope.row, 'settle')">结算</el-button><el-button v-if="scope.row.status === 'settled' && !scope.row.voucher_generated" link type="primary" :loading="actionLoading === scope.row.id" @click="createVoucher(scope.row)">生成凭证</el-button></template></el-table-column></el-table>
    <ClientPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @update:page-size="updatePageSize" />
    <el-dialog v-model="dialogVisible" title="新建报销" width="480px"><el-form label-width="90px"><el-form-item label="费用类型" required><el-select v-model="form.expense_type" clearable placeholder="请选择费用类型" style="width: 100%"><el-option label="办公费用" value="办公费用"/><el-option label="差旅费用" value="差旅费用"/><el-option label="交通费用" value="交通费用"/><el-option label="业务招待" value="业务招待"/><el-option label="其他费用" value="其他费用"/></el-select></el-form-item><el-form-item label="金额" required><el-input-number v-model="form.amount" :min="0.01" :precision="2" /></el-form-item><el-form-item label="说明"><el-input v-model="form.description" type="textarea" /></el-form-item></el-form><template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template></el-dialog>
  </section>
</template>

<style scoped>.toolbar { margin: 16px 0; }</style>
