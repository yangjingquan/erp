<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { createSalesOrder, deleteSalesOrder, updateSalesOrder, type SalesOrderPayload } from "../../api/sales";
import { getDocumentWorkspace, listDocuments, runDocumentCommand } from "../../api/documents";
import DocumentListWorkbench from "../../components/DocumentListWorkbench.vue";
import DocumentWorkbench from "../../components/DocumentWorkbench.vue";
import StatusTag from "../../components/StatusTag.vue";
import { useMasterOptions } from "../../composables/useMasterOptions";
import { formatLocalDateTime, localDateString } from "../../utils/time";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const summary = ref<Row>({});
const total = ref(0);
const page = ref(1);
const pageSize = ref(20);
const keyword = ref("");
const status = ref("");
const dateRange = ref<string[]>([]);
const loading = ref(false);
const saving = ref(false);
const actionLoading = ref<string | null>(null);
const errorMessage = ref("");
const dialogVisible = ref(false);
const detailVisible = ref(false);
const selected = ref<Row | null>(null);
const editingId = ref("");
const form = reactive<SalesOrderPayload>({ customer_id: "", order_date: localDateString(), expected_date: null, remark: "", items: [{ material_id: "", quantity: 1, unit_price: 0, warehouse_id: "", tax_rate: 0 }] });
const { customers, materials, warehouses, loadOptions } = useMasterOptions();

function unwrap(response: any): Row {
  if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "销售订单接口返回失败");
  return response.data.data;
}

async function load() {
  loading.value = true;
  errorMessage.value = "";
  try {
    const data = unwrap(await listDocuments({ business_type: "sales_order", status: status.value || undefined, keyword: keyword.value.trim() || undefined, date_from: dateRange.value[0], date_to: dateRange.value[1], page: page.value, page_size: pageSize.value, sort: "-updated_at" }));
    rows.value = data.items || [];
    total.value = Number(data.total || 0);
    summary.value = data.summary || {};
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "销售订单加载失败，请检查接口服务后重试";
  } finally {
    loading.value = false;
  }
}

function resetForm() { form.customer_id = ""; form.order_date = localDateString(); form.expected_date = null; form.remark = ""; form.items = [{ material_id: "", quantity: 1, unit_price: 0, warehouse_id: "", tax_rate: 0 }]; }
function openCreate() { selected.value = null; editingId.value = ""; resetForm(); dialogVisible.value = true; }
async function openEdit(row: Row) {
  try {
    const data = unwrap(await getDocumentWorkspace("sales_order", String(row.business_id)));
    const source = data.details || {};
    const item = source.items?.[0];
    editingId.value = String(row.business_id);
    form.customer_id = source.customer_id || "";
    form.order_date = source.order_date || localDateString();
    form.expected_date = source.expected_date || null;
    form.remark = source.remark || "";
    form.items = [{ material_id: item?.material_id || "", quantity: Number(item?.quantity || 1), unit_price: Number(item?.unit_price || 0), warehouse_id: item?.warehouse_id || "", tax_rate: Number(item?.tax_rate || 0) }];
    dialogVisible.value = true;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "加载订单失败");
  }
}
function openDetail(row: Row) { selected.value = row; detailVisible.value = true; }
function search() { page.value = 1; load(); }
function resetFilters() { keyword.value = ""; status.value = ""; dateRange.value = []; page.value = 1; load(); }

async function copyToForm(row: Row) {
  try {
    const data = unwrap(await getDocumentWorkspace("sales_order", String(row.business_id)));
    const source = data.details || {};
    const item = source.items?.[0];
    form.customer_id = source.customer_id || "";
    form.order_date = source.order_date || localDateString();
    form.expected_date = source.expected_date || null;
    form.remark = source.remark || `复制自 ${source.doc_no || "订单"}`;
    form.items = [{ material_id: item?.material_id || "", quantity: Number(item?.quantity || 1), unit_price: Number(item?.unit_price || 0), warehouse_id: item?.warehouse_id || "", tax_rate: Number(item?.tax_rate || 0) }];
    dialogVisible.value = true;
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "复制订单失败");
  }
}

async function save() {
  if (!form.customer_id || !form.items[0]?.material_id || !form.items[0]?.warehouse_id || form.items[0].quantity <= 0) { ElMessage.warning("请填写客户、物料、仓库和有效数量"); return; }
  saving.value = true;
  try {
    const response = editingId.value ? await updateSalesOrder(editingId.value, form) : await createSalesOrder(form);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success(editingId.value ? "销售订单已修改" : "销售订单已创建"); dialogVisible.value = false; await load();
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "销售订单保存失败"); }
  finally { saving.value = false; }
}

async function removeOrder(row: Row) {
  const id = String(row.business_id || "");
  try {
    await ElMessageBox.confirm(`确认删除销售订单“${row.doc_no || id}”吗？删除后不可恢复。`, "删除确认", { type: "warning" });
    actionLoading.value = id;
    unwrap(await deleteSalesOrder(id));
    ElMessage.success("销售订单已删除"); await load();
  } catch (error: any) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "删除失败");
  } finally { actionLoading.value = null; }
}

async function confirmAction(row: Row, action: Row) {
  const id = String(row.business_id || "");
  if (!id) { ElMessage.error("订单缺少有效 ID，无法操作"); return; }
  try {
    await ElMessageBox.confirm(`确认${action.label}“${row.doc_no || id}”吗？`, "业务操作确认", { type: "warning" });
    actionLoading.value = id;
    unwrap(await runDocumentCommand("sales_order", id, action.command));
    ElMessage.success(`${action.label}成功`); await load();
  } catch (error: any) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : `${action.label}失败`);
  } finally { actionLoading.value = null; }
}

onMounted(async () => { await Promise.all([load(), loadOptions(["customers", "materials", "warehouses"])]); });
</script>

<template>
  <DocumentListWorkbench v-model:keyword="keyword" v-model:status="status" v-model:date-range="dateRange" v-model:page="page" v-model:page-size="pageSize" title="销售订单" :summary="summary" :total="total" :loading="loading" @search="search" @reset="resetFilters" @refresh="load" @update:page="load" @update:page-size="search">
    <template #actions><el-button type="primary" @click="openCreate">新建订单</el-button></template>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''">
      <template #default><el-button link type="primary" @click="load">重新加载</el-button></template>
    </el-alert>
    <el-table v-loading="loading" :data="rows" stripe width="100%" fit>
      <el-table-column label="订单号" min-width="160"><template #default="scope"><el-button link type="primary" @click="openDetail(scope.row)">{{ scope.row.doc_no }}</el-button></template></el-table-column>
      <el-table-column prop="party_name" label="客户" min-width="180" show-overflow-tooltip />
      <el-table-column label="状态" width="100"><template #default="scope"><StatusTag :status="scope.row.status" :label="scope.row.status_label" /></template></el-table-column>
      <el-table-column prop="document_date" label="订单日期" width="115" />
      <el-table-column label="含税金额" width="130" align="right"><template #default="scope">¥{{ scope.row.amount }}</template></el-table-column>
      <el-table-column label="更新时间" width="165"><template #default="scope">{{ formatLocalDateTime(scope.row.updated_at) }}</template></el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="scope">
          <el-button link type="primary" @click="openDetail(scope.row)">查看</el-button>
          <el-button v-if="scope.row.status === 'draft'" link @click="openEdit(scope.row)">修改</el-button>
          <el-button v-if="scope.row.status === 'draft'" link type="danger" :loading="actionLoading === scope.row.business_id" @click="removeOrder(scope.row)">删除</el-button>
          <el-button link @click="copyToForm(scope.row)">复制填充</el-button>
          <el-button v-for="action in scope.row.available_actions" :key="action.command" link :type="action.type" :loading="actionLoading === scope.row.business_id" @click="confirmAction(scope.row, action)">{{ action.label }}</el-button>
        </template>
      </el-table-column>
      <template #empty><el-empty description="当前筛选范围内暂无销售订单，可调整筛选或新建订单" /></template>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingId ? '修改销售订单' : '新建销售订单'" width="560px">
      <el-form label-width="92px" @submit.prevent="save">
        <el-form-item label="客户" required><el-select v-model="form.customer_id" filterable clearable placeholder="请选择客户" style="width: 100%"><el-option v-for="option in customers" :key="option.value" v-bind="option" /></el-select></el-form-item>
        <el-form-item label="订单日期" required><el-date-picker v-model="form.order_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="预计交期"><el-date-picker v-model="form.expected_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="物料" required><el-select v-model="form.items[0].material_id" filterable clearable placeholder="请选择物料" style="width: 100%"><el-option v-for="option in materials" :key="option.value" v-bind="option" /></el-select></el-form-item>
        <el-form-item label="仓库" required><el-select v-model="form.items[0].warehouse_id" filterable clearable placeholder="请选择仓库" style="width: 100%"><el-option v-for="option in warehouses" :key="option.value" v-bind="option" /></el-select></el-form-item>
        <el-form-item label="数量" required><el-input-number v-model="form.items[0].quantity" :min="0.01" /></el-form-item>
        <el-form-item label="含税单价" required><el-input-number v-model="form.items[0].unit_price" :min="0" :precision="2" /></el-form-item>
        <el-form-item label="备注"><el-input v-model="form.remark" type="textarea" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>

    <DocumentWorkbench v-if="selected" v-model:visible="detailVisible" business-type="sales_order" :business-id="String(selected.business_id)" @changed="load" />
  </DocumentListWorkbench>
</template>
