<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  approvePurchaseOrder,
  createPurchaseOrder,
  createPurchaseReceipt,
  deletePurchaseOrder,
  listPurchaseOrders,
  submitPurchaseOrder,
  updatePurchaseOrder,
  type PurchaseOrderPayload,
} from "../../api/purchase";
import { useMasterOptions } from "../../composables/useMasterOptions";
import { useClientPagination } from "../../composables/useClientPagination";
import { formatLocalDateTime, localDateString } from "../../utils/time";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const { pagedRows, page, pageSize, total, updatePageSize } = useClientPagination(rows);
const loading = ref(false);
const saving = ref(false);
const actionLoading = ref<string | null>(null);
const errorMessage = ref("");
const dialogVisible = ref(false);
const detailVisible = ref(false);
const selected = ref<Row | null>(null);
const editingId = ref<string | null>(null);
const form = reactive<PurchaseOrderPayload>({
  supplier_id: "",
  order_date: localDateString(),
  expected_date: null,
  items: [{ material_id: "", quantity: 1, unit_price: 0, warehouse_id: null, tax_rate: 0 }],
});
const { suppliers, materials, loadOptions } = useMasterOptions();

const statusLabels: Record<string, string> = {
  draft: "草稿",
  submitted: "已提交",
  approved: "已审核",
  rejected: "已驳回",
  cancelled: "已取消",
};

function listFrom(response: any): Row[] {
  if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "采购订单接口返回失败");
  const data = response?.data?.data;
  return Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : [];
}

function supplierLabel(id: unknown) {
  const value = String(id || "");
  return suppliers.value.find((option) => option.value === value)?.label || value || "-";
}

function materialLabel(id: unknown) {
  const value = String(id || "");
  return materials.value.find((option) => option.value === value)?.label || value || "-";
}

function itemRows(row: Row) {
  return Array.isArray(row.items) ? row.items : [];
}

function statusLabel(status: string) {
  return statusLabels[status] || status || "-";
}

function statusTagType(status: string) {
  return ({ draft: "info", submitted: "warning", approved: "success", rejected: "danger", cancelled: "danger" } as Record<string, string>)[status] || "info";
}

async function load() {
  loading.value = true;
  errorMessage.value = "";
  try {
    rows.value = listFrom(await listPurchaseOrders());
  } catch (error) {
    errorMessage.value = "采购订单加载失败，请检查接口服务后重试";
  } finally {
    loading.value = false;
  }
}

function resetForm() {
  editingId.value = null;
  form.supplier_id = "";
  form.order_date = localDateString();
  form.expected_date = null;
  form.items = [{ material_id: "", quantity: 1, unit_price: 0, warehouse_id: null, tax_rate: 0 }];
}

function openCreate() { resetForm(); dialogVisible.value = true; }
function openDetail(row: Row) { selected.value = row; detailVisible.value = true; }
function openEdit(row: Row) { copyToForm(row); editingId.value = String(row.id); dialogVisible.value = true; }
function copyToForm(row: Row) {
  editingId.value = null;
  const item = row.items?.[0];
  form.supplier_id = row.supplier_id || "";
  form.order_date = row.order_date || localDateString();
  form.expected_date = row.expected_date || null;
  form.items = [{ material_id: item?.material_id || "", quantity: Number(item?.quantity || 1), unit_price: Number(item?.unit_price || 0), warehouse_id: item?.warehouse_id || null, tax_rate: Number(item?.tax_rate || 0) }];
  dialogVisible.value = true;
}

async function save() {
  if (!form.supplier_id || !form.items[0]?.material_id || form.items[0].quantity <= 0) {
    ElMessage.warning("请填写供应商、物料和有效数量");
    return;
  }
  saving.value = true;
  const editing = Boolean(editingId.value);
  try {
    const response = editing ? await updatePurchaseOrder(editingId.value as string, form) : await createPurchaseOrder(form);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success(editing ? "采购订单已修改" : "采购订单已创建");
    dialogVisible.value = false;
    await load();
  } catch (error) {
    ElMessage.error("采购订单创建失败");
  } finally {
    saving.value = false;
  }
}

async function removeOrder(row: Row) {
  const id = String(row.id || "");
  if (!id) { ElMessage.error("订单缺少有效 ID，无法删除"); return; }
  try {
    await ElMessageBox.confirm(`确认删除采购订单“${row.doc_no || id}”吗？删除后不可恢复。`, "删除确认", { type: "warning" });
    actionLoading.value = id;
    const response = await deletePurchaseOrder(id);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success("采购订单已删除");
    await load();
  } catch (error: any) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "采购订单删除失败");
  } finally { actionLoading.value = null; }
}

async function confirmAction(row: Row, action: "submit" | "approve" | "receipt") {
  const id = String(row.id || "");
  if (!id) { ElMessage.error("订单缺少有效 ID，无法操作"); return; }
  const labels = { submit: "提交审核", approve: "审核订单", receipt: "创建入库单" };
  try {
    await ElMessageBox.confirm(`确认${labels[action]}“${row.doc_no || id}”吗？`, "操作确认", { type: "warning" });
    actionLoading.value = id;
    const response = action === "submit" ? await submitPurchaseOrder(id) : action === "approve" ? await approvePurchaseOrder(id) : await createPurchaseReceipt(id);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success(`${labels[action]}成功`);
    await load();
  } catch (error: any) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : `${labels[action]}失败`);
  } finally { actionLoading.value = null; }
}

onMounted(async () => { await Promise.all([load(), loadOptions(["suppliers", "materials"])]); });
</script>

<template>
  <section>
    <el-page-header content="采购订单" />
    <el-space class="toolbar"><el-button type="primary" @click="openCreate">新建订单</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''"><template #default><el-button link type="primary" @click="load">重新加载</el-button></template></el-alert>
    <el-table v-loading="loading" :data="pagedRows" stripe width="100%" fit :header-cell-style="{ textAlign: 'center' }" :cell-style="{ textAlign: 'center' }">
      <el-table-column prop="doc_no" label="订单号" /><el-table-column label="供应商"><template #default="scope">{{ supplierLabel(scope.row.supplier_id) }}</template></el-table-column><el-table-column label="物料"><template #default="scope"><div v-for="(item, index) in itemRows(scope.row)" :key="item.id || `${item.material_id}-${index}`">{{ materialLabel(item.material_id) }}</div></template></el-table-column><el-table-column label="数量"><template #default="scope"><div v-for="(item, index) in itemRows(scope.row)" :key="item.id || `${item.material_id}-quantity-${index}`">{{ item.quantity }}</div></template></el-table-column><el-table-column label="单价"><template #default="scope"><div v-for="(item, index) in itemRows(scope.row)" :key="item.id || `${item.material_id}-price-${index}`">{{ item.unit_price }}</div></template></el-table-column><el-table-column prop="total_amount" label="含税金额" /><el-table-column label="状态"><template #default="scope"><el-tag :type="statusTagType(scope.row.status)" effect="light">{{ statusLabel(scope.row.status) }}</el-tag></template></el-table-column><el-table-column label="创建时间"><template #default="scope">{{ formatLocalDateTime(scope.row.created_at) }}</template></el-table-column>
      <el-table-column label="操作" width="300"><template #default="scope">
        <el-button link type="primary" @click="openDetail(scope.row)">查看</el-button><el-button link @click="copyToForm(scope.row)">复制填充</el-button>
        <el-button v-if="scope.row.status === 'draft'" link type="primary" @click="openEdit(scope.row)">修改</el-button>
        <el-button v-if="scope.row.status === 'draft'" link type="danger" :loading="actionLoading === scope.row.id" @click="removeOrder(scope.row)">删除</el-button>
        <el-button v-if="scope.row.status === 'draft'" link type="primary" :loading="actionLoading === scope.row.id" @click="confirmAction(scope.row, 'submit')">提交</el-button>
        <el-button v-if="scope.row.status === 'submitted'" link type="success" :loading="actionLoading === scope.row.id" @click="confirmAction(scope.row, 'approve')">审核</el-button>
        <el-button v-if="scope.row.status === 'approved'" link type="warning" :loading="actionLoading === scope.row.id" @click="confirmAction(scope.row, 'receipt')">生成入库</el-button>
      </template></el-table-column>
    </el-table>
    <ClientPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @update:page-size="updatePageSize" />
    <el-dialog v-model="dialogVisible" :title="editingId ? '修改采购订单' : '新建采购订单'" width="560px">
      <el-form label-width="92px"><el-form-item label="供应商" required><el-select v-model="form.supplier_id" filterable clearable placeholder="请选择供应商" style="width: 100%"><el-option v-for="option in suppliers" :key="option.value" v-bind="option" /></el-select></el-form-item><el-form-item label="订单日期" required><el-date-picker v-model="form.order_date" type="date" value-format="YYYY-MM-DD" /></el-form-item><el-form-item label="预计到货"><el-date-picker v-model="form.expected_date" type="date" value-format="YYYY-MM-DD" /></el-form-item><el-form-item label="物料" required><el-select v-model="form.items[0].material_id" filterable clearable placeholder="请选择物料" style="width: 100%"><el-option v-for="option in materials" :key="option.value" v-bind="option" /></el-select></el-form-item><el-form-item label="数量" required><el-input-number v-model="form.items[0].quantity" :min="0.01" /></el-form-item><el-form-item label="含税单价" required><el-input-number v-model="form.items[0].unit_price" :min="0" :precision="2" /></el-form-item></el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>
    <el-dialog v-model="detailVisible" title="采购订单详情" width="680px"><el-descriptions v-if="selected" :column="2" border><el-descriptions-item label="订单号">{{ selected.doc_no }}</el-descriptions-item><el-descriptions-item label="状态">{{ selected.status }}</el-descriptions-item><el-descriptions-item label="供应商">{{ selected.supplier_name || selected.supplier_id }}</el-descriptions-item><el-descriptions-item label="金额">{{ selected.total_amount }}</el-descriptions-item></el-descriptions></el-dialog>
  </section>
</template>

<style scoped>.toolbar { margin: 16px 0; }</style>
