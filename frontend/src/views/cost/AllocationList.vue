<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { createAllocation, listAllocations, postAllocation } from "../../api/cost";
import { localDateString } from "../../utils/time";
import { useClientPagination } from "../../composables/useClientPagination";
import { allocationBasisLabels, statusLabel, tagTypeOf } from "../../utils/labels";

type Item = { project_id: string; quantity: number; amount: number; hours: number };
type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const loading = ref(false);
const saving = ref(false);
const actionLoading = ref<string | null>(null);
const { pagedRows, page, pageSize, total, updatePageSize } = useClientPagination(rows);
const dialogVisible = ref(false);
const form = reactive({ allocation_date: localDateString(), amount: 0, basis: "quantity", source_type: "expense", source_id: "", idempotency_key: "", items: [{ project_id: "", quantity: 1, amount: 0, hours: 0 }] as Item[] });

function listFrom(response: any): Row[] { if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "成本分摊接口返回失败"); const data = response?.data?.data; return Array.isArray(data) ? data : []; }
async function load() { loading.value = true; try { rows.value = listFrom(await listAllocations()); } catch { ElMessage.error("成本分摊列表加载失败"); } finally { loading.value = false; } }
function reset() { form.allocation_date = localDateString(); form.amount = 0; form.basis = "quantity"; form.source_type = "expense"; form.source_id = ""; form.idempotency_key = `allocation-${Date.now()}`; form.items = [{ project_id: "", quantity: 1, amount: 0, hours: 0 }]; }
function openCreate() { reset(); dialogVisible.value = true; }
function addItem() { form.items.push({ project_id: "", quantity: 0, amount: 0, hours: 0 }); }
function removeItem(index: number) { if (form.items.length > 1) form.items.splice(index, 1); }
function basisValue(item: Item) { return Number(item[form.basis as "quantity" | "amount" | "hours"] || 0); }
async function save() {
  if (!form.allocation_date || form.amount <= 0 || form.items.some((item) => !item.project_id.trim() || basisValue(item) <= 0)) { ElMessage.warning("请填写日期、分摊金额，以及每行项目和大于 0 的分摊基数"); return; }
  saving.value = true;
  try { const response = await createAllocation({ ...form, items: form.items }); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("成本分摊已创建"); dialogVisible.value = false; await load(); }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : "成本分摊创建失败"); }
  finally { saving.value = false; }
}
async function post(row: Row) {
  const id = String(row.id || ""); if (!id) return;
  try { await ElMessageBox.confirm(`确认过账分摊单“${id}”吗？`, "操作确认", { type: "warning" }); actionLoading.value = id; const response = await postAllocation(id); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("成本分摊已过账"); await load(); }
  catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "成本分摊过账失败"); }
  finally { actionLoading.value = null; }
}
onMounted(load);
</script>

<template>
  <section class="page-stack">
    <el-page-header content="成本分摊" />
    <el-space><el-button type="primary" @click="openCreate">新建分摊</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-alert title="分摊保存前必须填写项目和对应分摊基数，避免提交空明细导致后端拒绝。" type="info" show-icon />
    <el-table v-loading="loading" :data="pagedRows" stripe>
      <el-table-column prop="allocation_date" label="分摊日期" min-width="130" />
      <el-table-column prop="period" label="期间" width="100" />
      <el-table-column prop="amount" label="分摊金额" width="130" />
      <el-table-column label="分摊依据" width="120"><template #default="scope">{{ allocationBasisLabels[scope.row.basis] || scope.row.basis || '-' }}</template></el-table-column>
      <el-table-column label="状态" width="110"><template #default="scope"><el-tag :type="tagTypeOf(scope.row.status)" effect="light">{{ statusLabel(scope.row.status) }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="120"><template #default="scope"><el-button v-if="scope.row.status === 'draft'" link type="primary" :loading="actionLoading === scope.row.id" @click="post(scope.row)">过账</el-button></template></el-table-column>
      <template #empty><el-empty description="暂无成本分摊记录" /></template>
    </el-table>
    <ClientPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @update:page-size="updatePageSize" />
    <el-dialog v-model="dialogVisible" title="新建成本分摊" width="760px">
      <el-form label-width="96px">
        <el-form-item label="分摊日期" required><el-date-picker v-model="form.allocation_date" type="date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="分摊金额" required><el-input-number v-model="form.amount" :min="0.01" :precision="2" /></el-form-item>
        <el-form-item label="分摊依据" required><el-select v-model="form.basis" style="width: 220px"><el-option label="数量" value="quantity" /><el-option label="金额" value="amount" /><el-option label="工时" value="hours" /></el-select></el-form-item>
        <el-form-item label="来源单据"><el-input v-model="form.source_id" placeholder="可选，例如费用单 ID" /></el-form-item>
        <el-form-item label="分摊明细" required>
          <div class="items-editor">
            <div v-for="(item, index) in form.items" :key="index" class="item-row"><el-input v-model="item.project_id" placeholder="项目 ID" /><el-input-number v-model="item.quantity" :min="0" :precision="2" placeholder="数量" /><el-input-number v-model="item.amount" :min="0" :precision="2" placeholder="金额" /><el-input-number v-model="item.hours" :min="0" :precision="2" placeholder="工时" /><el-button link type="danger" :disabled="form.items.length === 1" @click="removeItem(index)">删除</el-button></div>
            <el-button link type="primary" @click="addItem">新增分摊行</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.items-editor { display: flex; flex-direction: column; gap: 10px; width: 100%; }.item-row { display: grid; grid-template-columns: minmax(150px, 1fr) repeat(3, 130px) 52px; align-items: center; gap: 8px; }.item-row :deep(.el-input-number) { width: 100%; }
@media (max-width: 760px) { .item-row { grid-template-columns: 1fr 1fr; }.item-row .el-button { justify-self: start; } }
</style>
