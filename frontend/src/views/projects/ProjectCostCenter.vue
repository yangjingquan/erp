<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { createProject, createProjectEntry, createProjectMilestone, createWbs, getProjectDashboard, listProjectEntries, listProjectMilestones, listProjectWbs, listProjects } from "../../api/phase2";
import { useClientPagination } from "../../composables/useClientPagination";
import { sourceTypeLabels, statusLabel } from "../../utils/labels";

type Row = Record<string, any>;
const rows = ref<Row[]>([]); const entries = ref<Row[]>([]); const wbs = ref<Row[]>([]); const milestones = ref<Row[]>([]); const dashboard = ref<Row | null>(null);
const loading = ref(false); const visible = ref(false); const entryVisible = ref(false); const selected = ref<Row | null>(null);
const { pagedRows, page, pageSize, total, updatePageSize } = useClientPagination(rows);
const form = reactive({ project_code: "", name: "", customer_id: "", budget_amount: 0, start_date: "", end_date: "" });
const entry = reactive({ project_id: "", wbs_id: "", entry_date: "", category: "expense", source_type: "manual", source_id: "", amount: 0 });
const wbsForm = reactive({ code: "", name: "", planned_amount: 0 }); const milestoneForm = reactive({ name: "", due_date: "", wbs_id: "" });
function unwrap(response: any) { if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "接口返回失败"); return response.data.data; }
const categoryLabels: Record<string, string> = { purchase: "采购", labor: "人工", inventory: "库存", revenue: "收入", expense: "费用" };
const categoryOptions = Object.entries(categoryLabels).map(([value, label]) => ({ value, label }));
function categoryLabel(value: unknown) { return categoryLabels[String(value)] || String(value || "-"); }
async function load() { loading.value = true; try { rows.value = (unwrap(await listProjects()) || []).map((item: Row) => ({ ...item, status: statusLabel(item.status) })); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "项目加载失败"); } finally { loading.value = false; } }
function openCreate() { Object.assign(form, { project_code: "", name: "", customer_id: "", budget_amount: 0, start_date: "", end_date: "" }); visible.value = true; }
async function save() { if (!form.project_code.trim() || !form.name.trim()) return ElMessage.warning("请填写项目编码和名称"); try { unwrap(await createProject({ ...form })); ElMessage.success("项目已创建"); visible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "项目创建失败"); } }
async function openEntries(row: Row) { selected.value = row; entry.project_id = row.id; try { [entries.value, wbs.value, milestones.value, dashboard.value] = await Promise.all([listProjectEntries(row.id).then(unwrap), listProjectWbs(row.id).then(unwrap), listProjectMilestones(row.id).then(unwrap), getProjectDashboard(row.id).then(unwrap)]); entries.value = entries.value.map((item) => ({ ...item, category: categoryLabel(item.category), source_type: sourceTypeLabels[item.source_type] || item.source_type })); milestones.value = milestones.value.map((item) => ({ ...item, status: statusLabel(item.status) })); entryVisible.value = true; } catch (error) { ElMessage.error(error instanceof Error ? error.message : "项目成本加载失败"); } }
async function saveWbs() { if (!selected.value || !wbsForm.code || !wbsForm.name) return ElMessage.warning("请填写 WBS 编码和名称"); try { unwrap(await createWbs({ project_id: selected.value.id, ...wbsForm })); ElMessage.success("WBS 已创建"); Object.assign(wbsForm, { code: "", name: "", planned_amount: 0 }); await openEntries(selected.value); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "WBS 创建失败"); } }
async function saveMilestone() { if (!selected.value || !milestoneForm.name || !milestoneForm.due_date) return ElMessage.warning("请填写里程碑名称和日期"); try { unwrap(await createProjectMilestone({ project_id: selected.value.id, ...milestoneForm })); ElMessage.success("里程碑已创建"); Object.assign(milestoneForm, { name: "", due_date: "", wbs_id: "" }); await openEntries(selected.value); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "里程碑创建失败"); } }
async function saveEntry() { if (!entry.entry_date || !entry.source_id.trim() || entry.amount <= 0) return ElMessage.warning("请填写日期、来源单据和金额"); try { unwrap(await createProjectEntry({ ...entry })); ElMessage.success("项目成本已归集"); await openEntries(selected.value!); await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "项目成本归集失败"); } }
onMounted(load);
</script>

<template>
  <section class="page-stack">
    <header class="page-heading"><div><small>PROJECT / COST CONTROL</small><h1>项目与成本控制中心</h1><p>以项目/WBS 为主线归集采购、工时、库存、收入和费用，显示预算、实际和利润风险。</p></div><el-space><el-button type="primary" @click="openCreate">新建项目</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space></header>
    <el-card shadow="never"><el-table v-loading="loading" :data="pagedRows" stripe><el-table-column prop="project_code" label="项目编码" width="150" /><el-table-column prop="name" label="项目名称" min-width="220" /><el-table-column prop="budget_amount" label="预算" /><el-table-column prop="actual_amount" label="实际" /><el-table-column prop="variance" label="预算余额" /><el-table-column prop="status" label="状态" /><el-table-column label="操作" width="120"><template #default="scope"><el-button link type="primary" @click="openEntries(scope.row)">成本驾驶舱</el-button></template></el-table-column><template #empty><el-empty description="暂无项目" /></template></el-table><ClientPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @update:page-size="updatePageSize" /></el-card>
    <el-dialog v-model="visible" title="新建项目" width="560px"><el-form label-width="90px"><el-form-item label="项目编码" required><el-input v-model="form.project_code" /></el-form-item><el-form-item label="项目名称" required><el-input v-model="form.name" /></el-form-item><el-form-item label="客户 ID"><el-input v-model="form.customer_id" /></el-form-item><el-form-item label="预算金额"><el-input-number v-model="form.budget_amount" :min="0" :precision="2" /></el-form-item><el-form-item label="起止日期"><el-date-picker v-model="form.start_date" value-format="YYYY-MM-DD" /><el-date-picker v-model="form.end_date" value-format="YYYY-MM-DD" /></el-form-item></el-form><template #footer><el-button @click="visible = false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template></el-dialog>
    <el-drawer v-model="entryVisible" title="项目成本驾驶舱" size="900px">
      <el-alert v-if="dashboard" :title="`收入 ${dashboard.revenue || 0} · 成本 ${dashboard.cost || 0} · 利润 ${dashboard.profit || 0} · 利润率 ${dashboard.margin || 0}%`" type="info" show-icon />
      <el-tabs>
        <el-tab-pane label="成本明细"><el-table :data="entries" stripe><el-table-column prop="entry_date" label="日期" /><el-table-column prop="category" label="类别" /><el-table-column prop="source_type" label="来源" /><el-table-column prop="source_id" label="来源单据" /><el-table-column prop="amount" label="金额" /></el-table><el-divider /><el-form label-width="80px"><el-form-item label="归集日期"><el-date-picker v-model="entry.entry_date" value-format="YYYY-MM-DD" /></el-form-item><el-form-item label="类别"><el-select v-model="entry.category"><el-option v-for="item in categoryOptions" :key="item.value" :value="item.value" :label="item.label" /></el-select></el-form-item><el-form-item label="来源单据"><el-input v-model="entry.source_id" /></el-form-item><el-form-item label="金额"><el-input-number v-model="entry.amount" :min="0.01" /></el-form-item><el-button type="primary" @click="saveEntry">归集成本</el-button></el-form></el-tab-pane>
        <el-tab-pane label="WBS"><el-form inline class="cockpit-form wbs-form"><el-form-item label="编码"><el-input v-model="wbsForm.code" /></el-form-item><el-form-item label="名称"><el-input v-model="wbsForm.name" /></el-form-item><el-form-item label="计划金额"><el-input-number v-model="wbsForm.planned_amount" :min="0" /></el-form-item><el-button type="primary" @click="saveWbs">新增 WBS</el-button></el-form><el-table :data="wbs" stripe><el-table-column prop="code" label="编码" /><el-table-column prop="name" label="名称" /><el-table-column prop="planned_amount" label="计划金额" /><el-table-column prop="actual_amount" label="实际金额" /></el-table></el-tab-pane>
        <el-tab-pane label="里程碑"><el-form inline class="cockpit-form milestone-form"><el-form-item label="名称"><el-input v-model="milestoneForm.name" /></el-form-item><el-form-item label="截止日期"><el-date-picker v-model="milestoneForm.due_date" value-format="YYYY-MM-DD" /></el-form-item><el-form-item label="WBS"><el-input v-model="milestoneForm.wbs_id" placeholder="可选" /></el-form-item><el-button type="primary" @click="saveMilestone">新增里程碑</el-button></el-form><el-table :data="milestones" stripe><el-table-column prop="name" label="里程碑" /><el-table-column prop="due_date" label="截止日期" /><el-table-column prop="status" label="状态" /><el-table-column prop="completion_rate" label="完成率" /></el-table></el-tab-pane>
      </el-tabs>
    </el-drawer>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.page-heading { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; }
.page-heading small { color: var(--erp-muted-text); letter-spacing: .08em; }
.page-heading h1 { margin: 4px 0; }
.page-heading p { margin: 0; color: var(--erp-muted-text); }
.cockpit-form { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; }
.cockpit-form :deep(.el-form-item) { margin: 0; }
.wbs-form { flex-wrap: nowrap; }
.wbs-form :deep(.el-form-item) { flex: 1 1 0; min-width: 0; }
.wbs-form :deep(.el-form-item__content) { min-width: 0; }
.wbs-form :deep(.el-input), .wbs-form :deep(.el-input-number) { width: 100%; }
.wbs-form :deep(.el-button) { flex: 0 0 auto; }
.milestone-form { margin-bottom: 16px; }
</style>
