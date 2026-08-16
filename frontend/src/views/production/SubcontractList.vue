<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  cancelSubcontractOrder,
  createSubcontractOrder,
  issueSubcontractMaterial,
  listSubcontractOrders,
  receiveSubcontractOrder,
  releaseSubcontractOrder,
} from "../../api/production";
import { useMasterOptions } from "../../composables/useMasterOptions";
import { useClientPagination } from "../../composables/useClientPagination";
import { localDateString } from "../../utils/time";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const loading = ref(false);
const saving = ref(false);
const actionLoading = ref<string | null>(null);
const createVisible = ref(false);
const issueVisible = ref(false);
const receiveVisible = ref(false);
const activeRow = ref<Row | null>(null);
const { pagedRows, page, pageSize, total, updatePageSize } = useClientPagination(rows);
const form = reactive({ supplier_id: "", material_id: "", warehouse_id: "", plan_date: localDateString(), quantity: 1, processing_fee: 0 });
const issueForm = reactive({ material_id: "", quantity: 1 });
const receiveForm = reactive({ good_quantity: 1, unit_cost: 0 });
const { suppliers, materials, warehouses, loadOptions } = useMasterOptions();
const statusLabels: Record<string, string> = { draft: "草稿", released: "已下达", partially_received: "部分收货", completed: "已完成", cancelled: "已取消" };
function statusTag(status: string) { return ({ draft: "info", released: "primary", partially_received: "warning", completed: "success", cancelled: "danger" } as Record<string, string>)[status] || "info"; }
function unwrap(response: any) { if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "委外接口返回失败"); return response.data.data; }
function labelOf(id: unknown, options: Array<{ value: string; label: string }>) { const value = String(id || ""); return options.find((o) => o.value === value)?.label || value || "-"; }
async function load() { loading.value = true; try { rows.value = unwrap(await listSubcontractOrders()) || []; } catch (error) { ElMessage.error(error instanceof Error ? error.message : "委外订单加载失败"); } finally { loading.value = false; } }
function openCreate() { Object.assign(form, { supplier_id: "", material_id: "", warehouse_id: "", plan_date: localDateString(), quantity: 1, processing_fee: 0 }); createVisible.value = true; }
async function saveCreate() { if (!form.supplier_id || !form.material_id || !form.warehouse_id || form.quantity <= 0 || form.processing_fee <= 0) { ElMessage.warning("请完整填写供应商、物料、仓库、数量和加工费"); return; } saving.value = true; try { unwrap(await createSubcontractOrder({ ...form })); ElMessage.success("委外订单已创建"); createVisible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "委外订单创建失败"); } finally { saving.value = false; } }
async function act(row: Row, action: string) { const id = String(row.id); try { const label = { release: "下达", cancel: "取消" }[action] || action; await ElMessageBox.confirm(`确认${label}委外订单“${row.doc_no}”吗？`, "操作确认", { type: "warning" }); actionLoading.value = id; unwrap(action === "release" ? await releaseSubcontractOrder(id) : await cancelSubcontractOrder(id)); ElMessage.success(`${label}成功`); await load(); } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : `${action}失败`); } finally { actionLoading.value = null; } }
function openIssue(row: Row) { activeRow.value = row; Object.assign(issueForm, { material_id: row.material_id, quantity: 1 }); issueVisible.value = true; }
async function saveIssue() { if (!issueForm.material_id || issueForm.quantity <= 0) { ElMessage.warning("请填写发料物料和数量"); return; } saving.value = true; try { unwrap(await issueSubcontractMaterial(String(activeRow.value?.id), [{ material_id: issueForm.material_id, quantity: issueForm.quantity }])); ElMessage.success("委外发料成功"); issueVisible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "委外发料失败"); } finally { saving.value = false; } }
function openReceive(row: Row) { activeRow.value = row; Object.assign(receiveForm, { good_quantity: Math.max(0.000001, Number(row.quantity) - Number(row.received_quantity)), unit_cost: Number(row.processing_fee) || 0 }); receiveVisible.value = true; }
async function saveReceive() { if (receiveForm.good_quantity <= 0 || receiveForm.unit_cost <= 0) { ElMessage.warning("请填写收货数量和单价"); return; } saving.value = true; try { unwrap(await receiveSubcontractOrder(String(activeRow.value?.id), { good_quantity: receiveForm.good_quantity, unit_cost: receiveForm.unit_cost, operation_key: `op-${Date.now()}-${Math.random().toString(16).slice(2, 8)}` })); ElMessage.success("委外收货成功"); receiveVisible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "委外收货失败"); } finally { saving.value = false; } }
onMounted(async () => { await Promise.all([load(), loadOptions(["suppliers", "materials", "warehouses"])]); });
</script>

<template>
  <section class="page-stack">
    <header class="page-heading">
      <div><small>PRODUCTION / SUBCONTRACT</small><h1>委外管理</h1><p>委外订单 创建→下达→发料→收货→生成应付与凭证 的完整闭环。</p></div>
      <el-space><el-button type="primary" @click="openCreate">新建委外订单</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    </header>
    <el-table v-loading="loading" :data="pagedRows" stripe>
      <el-table-column prop="doc_no" label="委外单号" width="200" />
      <el-table-column label="供应商" min-width="160"><template #default="scope">{{ labelOf(scope.row.supplier_id, suppliers) }}</template></el-table-column>
      <el-table-column label="物料" min-width="150"><template #default="scope">{{ labelOf(scope.row.material_id, materials) }}</template></el-table-column>
      <el-table-column label="仓库" min-width="140"><template #default="scope">{{ labelOf(scope.row.warehouse_id, warehouses) }}</template></el-table-column>
      <el-table-column prop="plan_date" label="计划日期" width="120" />
      <el-table-column prop="quantity" label="数量" width="100" />
      <el-table-column prop="received_quantity" label="已收" width="100" />
      <el-table-column prop="processing_fee" label="加工费" width="110" />
      <el-table-column label="状态" width="110"><template #default="scope"><el-tag :type="statusTag(scope.row.status)" effect="light">{{ statusLabels[scope.row.status] || scope.row.status }}</el-tag></template></el-table-column>
      <el-table-column label="操作" min-width="220">
        <template #default="scope">
          <el-button v-if="scope.row.status === 'draft'" link type="primary" :loading="actionLoading === scope.row.id" @click="act(scope.row, 'release')">下达</el-button>
          <el-button v-if="['draft', 'released'].includes(scope.row.status)" link type="danger" :loading="actionLoading === scope.row.id" @click="act(scope.row, 'cancel')">取消</el-button>
          <el-button v-if="['released', 'partially_received'].includes(scope.row.status)" link type="warning" @click="openIssue(scope.row)">发料</el-button>
          <el-button v-if="['released', 'partially_received'].includes(scope.row.status)" link type="success" @click="openReceive(scope.row)">收货</el-button>
        </template>
      </el-table-column>
      <template #empty><el-empty description="暂无委外订单" /></template>
    </el-table>
    <ClientPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @update:page-size="updatePageSize" />

    <el-dialog v-model="createVisible" title="新建委外订单" width="560px">
      <el-form label-width="90px">
        <el-form-item label="供应商" required><el-select v-model="form.supplier_id" filterable style="width: 100%"><el-option v-for="o in suppliers" :key="o.value" v-bind="o" /></el-select></el-form-item>
        <el-form-item label="物料" required><el-select v-model="form.material_id" filterable style="width: 100%"><el-option v-for="o in materials" :key="o.value" v-bind="o" /></el-select></el-form-item>
        <el-form-item label="仓库" required><el-select v-model="form.warehouse_id" filterable style="width: 100%"><el-option v-for="o in warehouses" :key="o.value" v-bind="o" /></el-select></el-form-item>
        <el-form-item label="计划日期" required><el-date-picker v-model="form.plan_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="数量" required><el-input-number v-model="form.quantity" :min="0.000001" :precision="6" /></el-form-item>
        <el-form-item label="加工费" required><el-input-number v-model="form.processing_fee" :min="0.01" :precision="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveCreate">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="issueVisible" title="委外发料" width="480px">
      <el-form label-width="90px">
        <el-form-item label="发料物料" required><el-select v-model="issueForm.material_id" filterable style="width: 100%"><el-option v-for="o in materials" :key="o.value" v-bind="o" /></el-select></el-form-item>
        <el-form-item label="发料数量" required><el-input-number v-model="issueForm.quantity" :min="0.000001" :precision="6" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="issueVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveIssue">发料</el-button></template>
    </el-dialog>

    <el-dialog v-model="receiveVisible" title="委外收货" width="480px">
      <el-form label-width="90px">
        <el-form-item label="收货数量" required><el-input-number v-model="receiveForm.good_quantity" :min="0.000001" :precision="6" /></el-form-item>
        <el-form-item label="收货单价" required><el-input-number v-model="receiveForm.unit_cost" :min="0.000001" :precision="6" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="receiveVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveReceive">收货</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.page-heading { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; }
.page-heading small { color: var(--erp-muted-text); letter-spacing: .08em; }
.page-heading h1 { margin: 4px 0; }
.page-heading p { margin: 0; color: var(--erp-muted-text); }
</style>
