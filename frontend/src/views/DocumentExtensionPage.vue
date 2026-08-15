<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { completeSalesReturn, createSalesQuote, createSalesReturn, listSalesQuotes, listSalesReturns, quoteAction, submitSalesReturn } from "../api/sales";
import {
  createPurchaseRequest,
  createPurchaseReturn,
  deletePurchaseRequest,
  deletePurchaseReturn,
  listPurchaseRequests,
  listPurchaseReturns,
  requestAction,
  completePurchaseReturn,
  submitPurchaseReturn,
  updatePurchaseReturn,
  updatePurchaseRequest,
} from "../api/purchase";
import { useMasterOptions, type SelectOption } from "../composables/useMasterOptions";
import { useClientPagination } from "../composables/useClientPagination";
import { formatLocalDateTime, localDateString } from "../utils/time";
import { statusLabel as commonStatusLabel, tagTypeOf } from "../utils/labels";

type Kind = "quote" | "purchase-request" | "sales-return" | "purchase-return";

const props = defineProps<{ kind: Kind; title: string }>();
const rows = ref<any[]>([]);
const loading = ref(false);
const saving = ref(false);
const dialogVisible = ref(false);
const actionLoading = ref("");
const filters = reactive({ doc_no: "", customer_id: "", supplier_id: "", material_id: "", status: "" });
const editingId = ref("");
const form = reactive<any>({
  customer_id: "",
  supplier_id: "",
  warehouse_id: "",
  source_delivery_id: "",
  source_receipt_id: "",
  quote_date: localDateString(),
  request_date: localDateString(),
  return_date: localDateString(),
  valid_until: null,
  remark: "",
  items: [{ material_id: "", quantity: 1, unit_price: 0, estimated_price: 0 }],
});
const { customers, suppliers, materials, warehouses, loadOptions } = useMasterOptions();
const filteredRows = computed(() => rows.value.filter((row) => (!filters.doc_no || String(row.doc_no || "").includes(filters.doc_no)) && (!filters.customer_id || String(row.customer_id || "") === filters.customer_id) && (!filters.supplier_id || String(row.supplier_id || "") === filters.supplier_id) && (!filters.material_id || itemRows(row).some((item: any) => String(item.material_id) === filters.material_id)) && (!filters.status || row.status === filters.status)));
const { pagedRows, page, pageSize, total, updatePageSize } = useClientPagination(filteredRows);

const purchaseStatusLabels: Record<string, string> = {
  draft: "草稿",
  submitted: "已提交",
  approved: "已审核",
  rejected: "已驳回",
};

const isQuote = () => props.kind === "quote";
const isRequest = () => props.kind === "purchase-request";
const isSalesReturn = () => props.kind === "sales-return";
const isPurchaseReturn = () => props.kind === "purchase-return";
const isPurchaseKind = () => props.kind === "purchase-request" || props.kind === "purchase-return";

function listFn() {
  return isQuote() ? listSalesQuotes() : isRequest() ? listPurchaseRequests() : isSalesReturn() ? listSalesReturns() : listPurchaseReturns();
}

function listFrom(response: any) {
  if (response.data.code !== 0) throw new Error(response.data.msg);
  return Array.isArray(response.data.data) ? response.data.data : [];
}

function optionLabel(options: SelectOption[], id: unknown) {
  const value = String(id || "");
  return options.find((option) => option.value === value)?.label || value || "-";
}

function supplierLabel(id: unknown) {
  return optionLabel(suppliers.value, id);
}

function materialLabel(id: unknown) {
  return optionLabel(materials.value, id);
}

function statusLabel(status: string) {
  return purchaseStatusLabels[status] || commonStatusLabel(status);
}

function statusTagType(status: string) {
  return ({
    draft: "info",
    submitted: "warning",
    approved: "success",
    rejected: "danger",
  } as Record<string, string>)[status] || "info";
}

function itemRows(row: any) {
  return Array.isArray(row.items) ? row.items : [];
}

async function load() {
  loading.value = true;
  try {
    rows.value = listFrom(await listFn());
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : `${props.title}加载失败`);
  } finally {
    loading.value = false;
  }
}

function reset() {
  editingId.value = "";
  form.customer_id = "";
  form.supplier_id = "";
  form.warehouse_id = "";
  form.source_delivery_id = "";
  form.source_receipt_id = "";
  form.quote_date = localDateString();
  form.request_date = localDateString();
  form.return_date = localDateString();
  form.valid_until = null;
  form.remark = "";
  form.items = [{ material_id: "", quantity: 1, unit_price: 0, estimated_price: 0 }];
}

function openCreate() {
  reset();
  dialogVisible.value = true;
}

function openEdit(row: any) {
  reset();
  editingId.value = String(row.id);
  form.supplier_id = row.supplier_id || "";
  if (isRequest()) {
    form.request_date = row.request_date || form.request_date;
    form.remark = row.remark || "";
  } else if (isPurchaseReturn()) {
    form.warehouse_id = row.warehouse_id || "";
    form.source_receipt_id = row.source_receipt_id || "";
    form.return_date = row.return_date || form.return_date;
  }
  form.items = itemRows(row).length
    ? itemRows(row).map((item: any) => ({
      material_id: item.material_id || "",
      quantity: Number(item.quantity) || 0,
      estimated_price: Number(item.estimated_price) || 0,
      unit_price: Number(item.unit_price) || 0,
    }))
    : [{ material_id: "", quantity: 1, unit_price: 0, estimated_price: 0 }];
  dialogVisible.value = true;
}

function purchaseRequestPayload() {
  return {
    supplier_id: form.supplier_id || null,
    request_date: form.request_date,
    remark: form.remark || null,
    items: form.items.map((item: any) => ({
      material_id: item.material_id,
      quantity: item.quantity,
      estimated_price: item.estimated_price,
    })),
  };
}

function purchaseReturnPayload() {
  return {
    source_receipt_id: form.source_receipt_id || null,
    supplier_id: form.supplier_id,
    warehouse_id: form.warehouse_id,
    return_date: form.return_date,
    items: form.items.map((item: any) => ({
      material_id: item.material_id,
      quantity: item.quantity,
      unit_price: item.unit_price,
    })),
  };
}

async function save() {
  if ((isRequest() || isPurchaseReturn()) && !form.supplier_id) {
    ElMessage.warning("请选择供应商");
    return;
  }
  if (isPurchaseReturn() && !form.warehouse_id) {
    ElMessage.warning("请选择仓库");
    return;
  }
  if (!form.items.length || form.items.some((item: any) => !item.material_id || item.quantity <= 0)) {
    ElMessage.warning("请填写物料和有效数量");
    return;
  }
  saving.value = true;
  const editing = Boolean(editingId.value);
  try {
    let response: any;
    if (isQuote()) {
      response = await createSalesQuote({
        customer_id: form.customer_id,
        quote_date: form.quote_date,
        valid_until: form.valid_until,
        items: [{ material_id: form.items[0].material_id, quantity: form.items[0].quantity, unit_price: form.items[0].unit_price }],
      });
    } else if (isRequest()) {
      response = editing ? await updatePurchaseRequest(editingId.value, purchaseRequestPayload()) : await createPurchaseRequest(purchaseRequestPayload());
    } else if (isSalesReturn()) {
      response = await createSalesReturn({ ...form });
    } else if (isPurchaseReturn()) {
      response = editing ? await updatePurchaseReturn(editingId.value, purchaseReturnPayload()) : await createPurchaseReturn(purchaseReturnPayload());
    } else {
      response = await createPurchaseReturn({ ...form });
    }
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success(editing ? `${props.title}已修改` : `${props.title}已创建`);
    dialogVisible.value = false;
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "创建失败");
  } finally {
    saving.value = false;
  }
}

async function action(row: any, name: "submit" | "approve" | "reject") {
  try {
    await ElMessageBox.confirm(`确认操作单据“${row.doc_no}”吗？`, "操作确认", { type: "warning" });
    actionLoading.value = row.id;
    const response = props.kind === "quote" ? await quoteAction(row.id, name) : await requestAction(row.id, name);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    await load();
  } catch (error) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "操作失败");
  } finally {
    actionLoading.value = "";
  }
}

async function returnAction(row: any, name: "submit" | "complete") {
  try { await ElMessageBox.confirm(`确认${name === "submit" ? "提交" : "完成"}退货单“${row.doc_no}”？`, "操作确认", { type: "warning" }); actionLoading.value = row.id; const response = isSalesReturn() ? (name === "submit" ? await submitSalesReturn(row.id) : await completeSalesReturn(row.id)) : (name === "submit" ? await submitPurchaseReturn(row.id) : await completePurchaseReturn(row.id)); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("退货单状态已更新"); await load(); } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "退货操作失败"); } finally { actionLoading.value = ""; }
}

async function removeRequest(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除采购申请“${row.doc_no}”吗？删除后不可恢复。`, "删除确认", { type: "warning" });
    actionLoading.value = `delete:${row.id}`;
    const response = await deletePurchaseRequest(row.id);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success("采购申请已删除");
    await load();
  } catch (error) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "删除失败");
  } finally {
    actionLoading.value = "";
  }
}

async function removePurchaseReturn(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除采购退货单“${row.doc_no}”吗？删除后不可恢复。`, "删除确认", { type: "warning" });
    actionLoading.value = `delete:${row.id}`;
    const response = await deletePurchaseReturn(row.id);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success("采购退货单已删除");
    await load();
  } catch (error) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "删除失败");
  } finally {
    actionLoading.value = "";
  }
}

onMounted(async () => {
  await Promise.all([load(), loadOptions(["customers", "suppliers", "materials", "warehouses"])]);
});
</script>

<template>
  <section class="page-stack">
    <el-page-header :content="props.title" />
    <el-space wrap>
      <el-input v-model="filters.doc_no" clearable placeholder="单据号" style="width:180px" />
      <el-select v-if="isQuote() || isSalesReturn()" v-model="filters.customer_id" clearable filterable placeholder="客户" style="width:180px"><el-option v-for="option in customers" :key="option.value" v-bind="option" /></el-select>
      <el-select v-if="isRequest() || isPurchaseReturn()" v-model="filters.supplier_id" clearable filterable placeholder="供应商" style="width:180px"><el-option v-for="option in suppliers" :key="option.value" v-bind="option" /></el-select>
      <el-select v-if="isRequest() || isPurchaseReturn()" v-model="filters.material_id" clearable filterable placeholder="物料" style="width:180px"><el-option v-for="option in materials" :key="option.value" v-bind="option" /></el-select>
      <el-select v-model="filters.status" clearable placeholder="状态" style="width:140px"><el-option label="草稿" value="draft" /><el-option label="待审核" value="submitted" /><el-option label="已审核" value="approved" /><el-option label="已驳回" value="rejected" /><el-option label="已完成" value="completed" /></el-select>
      <el-button type="primary" @click="openCreate">新建{{ props.title }}</el-button>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </el-space>

    <el-table v-loading="loading" :data="pagedRows" stripe width="100%" fit :header-cell-style="{ textAlign: 'center' }" :cell-style="{ textAlign: 'center' }">
      <el-table-column prop="doc_no" label="单据号" min-width="180" />

      <template v-if="isRequest()">
        <el-table-column label="供应商" min-width="180">
          <template #default="scope">{{ supplierLabel(scope.row.supplier_id) }}</template>
        </el-table-column>
        <el-table-column label="物料" min-width="180">
          <template #default="scope">
            <div v-for="(item, index) in itemRows(scope.row)" :key="item.id || `${item.material_id}-${index}`">{{ materialLabel(item.material_id) }}</div>
          </template>
        </el-table-column>
        <el-table-column label="数量" width="120">
          <template #default="scope">
            <div v-for="(item, index) in itemRows(scope.row)" :key="item.id || `${item.material_id}-quantity-${index}`">{{ item.quantity }}</div>
          </template>
        </el-table-column>
        <el-table-column label="单价" width="120">
          <template #default="scope">
            <div v-for="(item, index) in itemRows(scope.row)" :key="item.id || `${item.material_id}-price-${index}`">{{ item.estimated_price }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="total_amount" label="金额" min-width="140" />
        <el-table-column label="状态" width="110">
          <template #default="scope">
            <el-tag class="request-status-tag" :type="statusTagType(scope.row.status)" effect="light">
              {{ statusLabel(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="180">
          <template #default="scope">{{ formatLocalDateTime(scope.row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="300">
          <template #default="scope">
            <el-button v-if="scope.row.status === 'draft'" link type="primary" @click="openEdit(scope.row)">修改</el-button>
            <el-button v-if="scope.row.status === 'draft'" link type="danger" :loading="actionLoading === `delete:${scope.row.id}`" @click="removeRequest(scope.row)">删除</el-button>
            <el-button v-if="scope.row.status === 'draft'" link :loading="actionLoading === scope.row.id" @click="action(scope.row, 'submit')">提交</el-button>
            <el-button v-if="scope.row.status === 'submitted'" link type="success" :loading="actionLoading === scope.row.id" @click="action(scope.row, 'approve')">审核</el-button>
            <el-button v-if="scope.row.status === 'submitted'" link type="danger" :loading="actionLoading === scope.row.id" @click="action(scope.row, 'reject')">驳回</el-button>
          </template>
        </el-table-column>
      </template>

      <template v-else>
        <template v-if="isPurchaseReturn()">
          <el-table-column label="供应商" min-width="180">
            <template #default="scope">{{ supplierLabel(scope.row.supplier_id) }}</template>
          </el-table-column>
          <el-table-column label="物料" min-width="180">
            <template #default="scope">
              <div v-for="(item, index) in itemRows(scope.row)" :key="item.id || `${item.material_id}-${index}`">{{ materialLabel(item.material_id) }}</div>
            </template>
          </el-table-column>
          <el-table-column label="数量" width="120">
            <template #default="scope">
              <div v-for="(item, index) in itemRows(scope.row)" :key="item.id || `${item.material_id}-quantity-${index}`">{{ item.quantity }}</div>
            </template>
          </el-table-column>
          <el-table-column label="单价" width="120">
            <template #default="scope">
              <div v-for="(item, index) in itemRows(scope.row)" :key="item.id || `${item.material_id}-price-${index}`">{{ item.unit_price }}</div>
            </template>
          </el-table-column>
          <el-table-column prop="total_amount" label="金额" min-width="140" />
          <el-table-column label="状态" width="110">
            <template #default="scope">
              <el-tag class="request-status-tag" :type="statusTagType(scope.row.status)" effect="light">
                {{ statusLabel(scope.row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" min-width="180">
            <template #default="scope">{{ formatLocalDateTime(scope.row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="220">
            <template #default="scope">
              <el-button v-if="scope.row.status === 'draft'" link type="primary" @click="openEdit(scope.row)">修改</el-button>
            <el-button v-if="scope.row.status === 'draft'" link type="danger" :loading="actionLoading === `delete:${scope.row.id}`" @click="removePurchaseReturn(scope.row)">删除</el-button>
              <el-button v-if="scope.row.status === 'draft'" link type="primary" @click="returnAction(scope.row, 'submit')">提交</el-button>
              <el-button v-if="scope.row.status === 'submitted'" link type="success" @click="returnAction(scope.row, 'complete')">完成</el-button>
            </template>
          </el-table-column>
        </template>
        <template v-else>
          <el-table-column label="状态" width="110">
            <template #default="scope"><el-tag class="request-status-tag" :type="tagTypeOf(scope.row.status)" effect="light">{{ statusLabel(scope.row.status) }}</el-tag></template>
          </el-table-column>
          <el-table-column v-if="isQuote() || isSalesReturn()" label="客户" min-width="180">
            <template #default="scope">{{ scope.row.customer_name || scope.row.customer_id || '-' }}</template>
          </el-table-column>
          <el-table-column prop="total_amount" label="金额" min-width="140" />
          <el-table-column label="操作" width="220" v-if="isQuote() || isSalesReturn()">
            <template #default="scope">
              <el-button v-if="isQuote() && scope.row.status === 'draft'" link @click="action(scope.row, 'submit')">提交</el-button>
              <el-button v-if="isQuote() && scope.row.status === 'submitted'" link type="success" @click="action(scope.row, 'approve')">审核</el-button>
              <el-button v-if="isQuote() && scope.row.status === 'submitted'" link type="danger" @click="action(scope.row, 'reject')">驳回</el-button>
              <el-button v-if="isSalesReturn() && scope.row.status === 'draft'" link type="primary" @click="returnAction(scope.row, 'submit')">提交</el-button>
              <el-button v-if="isSalesReturn() && scope.row.status === 'submitted'" link type="success" @click="returnAction(scope.row, 'complete')">完成</el-button>
            </template>
          </el-table-column>
        </template>
      </template>

      <template #empty><el-empty description="暂无单据" /></template>
    </el-table>

    <ClientPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @update:page-size="updatePageSize" />

    <el-dialog v-model="dialogVisible" :title="editingId ? `修改${props.title}` : `新建${props.title}`" width="560px">
      <el-form label-width="100px">
        <el-form-item v-if="isQuote() || isSalesReturn()" label="客户" required>
          <el-select v-model="form.customer_id" filterable clearable style="width: 100%">
            <el-option v-for="option in customers" :key="option.value" v-bind="option" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="isRequest() || props.kind === 'purchase-return'" label="供应商" required>
          <el-select v-model="form.supplier_id" filterable clearable style="width: 100%">
            <el-option v-for="option in suppliers" :key="option.value" v-bind="option" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="!isQuote() && !isRequest()" label="仓库" required>
          <el-select v-model="form.warehouse_id" filterable clearable style="width: 100%">
            <el-option v-for="option in warehouses" :key="option.value" v-bind="option" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="isPurchaseReturn()" label="退货日期" required>
          <el-date-picker v-model="form.return_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item v-if="isRequest()" label="申请日期" required>
          <el-date-picker v-model="form.request_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item v-if="isRequest()" label="备注">
          <el-input v-model="form.remark" type="textarea" />
        </el-form-item>
        <el-form-item v-if="isSalesReturn()" label="来源发货单">
          <el-input v-model="form.source_delivery_id" placeholder="可关联原发货单 ID" />
        </el-form-item>
        <el-form-item v-if="props.kind === 'purchase-return'" label="来源收货单">
          <el-input v-model="form.source_receipt_id" placeholder="可关联原收货单 ID" />
        </el-form-item>
        <el-form-item label="物料" required>
          <el-select v-model="form.items[0].material_id" filterable clearable style="width: 100%">
            <el-option v-for="option in materials" :key="option.value" v-bind="option" />
          </el-select>
        </el-form-item>
        <el-form-item label="数量" required><el-input-number v-model="form.items[0].quantity" :min="0.01" /></el-form-item>
        <el-form-item v-if="!isRequest()" label="单价"><el-input-number v-model="form.items[0].unit_price" :min="0" /></el-form-item>
        <el-form-item v-else label="预计单价"><el-input-number v-model="form.items[0].estimated_price" :min="0" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.request-status-tag { min-width: 64px; justify-content: center; }
</style>
