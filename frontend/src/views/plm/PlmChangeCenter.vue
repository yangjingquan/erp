<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { createChangeRequest, listChangeRequests, transitionChangeRequest } from "../../api/phase2";

type Row = Record<string, any>;
const rows = ref<Row[]>([]); const loading = ref(false); const saving = ref(false); const visible = ref(false);
const form = reactive({ title: "", change_type: "engineering", description: "", due_date: "", impact_snapshot: [] as Array<{ object_type: string; object_id: string; impact: string }> });
function unwrap(response: any) { if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "接口返回失败"); return response.data.data; }
async function load() { loading.value = true; try { rows.value = unwrap(await listChangeRequests()) || []; } catch (error) { ElMessage.error(error instanceof Error ? error.message : "工程变更加载失败"); } finally { loading.value = false; } }
function openCreate() { Object.assign(form, { title: "", change_type: "engineering", description: "", due_date: "", impact_snapshot: [] }); form.impact_snapshot.push({ object_type: "bom", object_id: "", impact: "" }); visible.value = true; }
function addImpact() { form.impact_snapshot.push({ object_type: "bom", object_id: "", impact: "" }); }
async function save() { if (!form.title.trim() || !form.description.trim() || form.impact_snapshot.some((item) => !item.object_type || !item.object_id.trim() || !item.impact.trim())) { ElMessage.warning("请填写变更标题、说明和完整影响单据"); return; } saving.value = true; try { unwrap(await createChangeRequest({ ...form, title: form.title.trim(), description: form.description.trim(), impact_snapshot: form.impact_snapshot })); ElMessage.success("工程变更申请已创建"); visible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "工程变更创建失败"); } finally { saving.value = false; } }
async function transition(row: Row, status: string) { try { await ElMessageBox.confirm(`确认将 ${row.change_no} 流转为${status}吗？`, "状态确认", { type: "warning" }); unwrap(await transitionChangeRequest(String(row.id), status)); ElMessage.success("变更状态已更新"); await load(); } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "变更状态更新失败"); } }
onMounted(load);
</script>
<template>
  <section class="page-stack">
    <header class="page-heading">
      <div><small>PLM / ENGINEERING CHANGE</small><h1>PLM 工程变更中心</h1><p>维护产品版本、ECR/ECN、影响评估、审批和生效快照，防止错版生产。</p></div>
      <el-space><el-button type="primary" @click="openCreate">新建变更申请</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    </header>
    <el-alert title="变更生效后会保存 ECN、影响对象和操作人，可从统一单据继续追溯。" type="info" show-icon />
    <el-card shadow="never">
      <el-table v-loading="loading" :data="rows" stripe>
        <el-table-column prop="change_no" label="申请号" width="170" /><el-table-column prop="title" label="标题" min-width="220" /><el-table-column prop="change_type" label="类型" width="120" /><el-table-column prop="status" label="状态" width="120" /><el-table-column prop="due_date" label="期限" width="120" />
        <el-table-column label="影响对象" min-width="220"><template #default="scope">{{ (scope.row.impact_snapshot || []).map((item: Row) => `${item.object_type}:${item.object_id}`).join("、") || "待评估" }}</template></el-table-column>
        <el-table-column label="操作" width="250"><template #default="scope"><el-button v-if="scope.row.status === 'draft'" link type="primary" @click="transition(scope.row, 'submitted')">提交评估</el-button><el-button v-if="scope.row.status === 'submitted'" link type="success" @click="transition(scope.row, 'approved')">批准</el-button><el-button v-if="scope.row.status === 'approved'" link type="warning" @click="transition(scope.row, 'effective')">生效</el-button></template></el-table-column>
        <template #empty><el-empty description="暂无工程变更" /></template>
      </el-table>
    </el-card>
    <el-dialog v-model="visible" title="新建工程变更申请" width="720px">
      <el-form label-width="100px">
        <el-form-item label="变更标题" required><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="变更类型"><el-select v-model="form.change_type"><el-option label="工程变更" value="engineering" /><el-option label="质量变更" value="quality" /><el-option label="供应商变更" value="supplier" /><el-option label="生产变更" value="production" /></el-select></el-form-item>
        <el-form-item label="变更说明" required><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="截止日期"><el-date-picker v-model="form.due_date" value-format="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="影响对象" required><div class="impact-list"><div v-for="(item, index) in form.impact_snapshot" :key="index" class="impact-row"><el-select v-model="item.object_type"><el-option label="BOM" value="bom" /><el-option label="工艺" value="routing" /><el-option label="采购" value="purchase" /><el-option label="工单" value="work_order" /></el-select><el-input v-model="item.object_id" placeholder="对象 ID / 单据号" /><el-input v-model="item.impact" placeholder="影响说明" /></div><el-button link type="primary" @click="addImpact">新增影响对象</el-button></div></el-form-item>
      </el-form>
      <template #footer><el-button @click="visible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>
  </section>
</template>
<style scoped>.page-stack{display:flex;flex-direction:column;gap:16px}.page-heading{display:flex;justify-content:space-between;align-items:flex-end}.page-heading small{color:var(--erp-muted-text);letter-spacing:.08em}.page-heading h1{margin:4px 0}.page-heading p{margin:0;color:var(--erp-muted-text)}.impact-list{display:flex;flex-direction:column;gap:8px;width:100%}.impact-row{display:grid;grid-template-columns:130px 1fr 1fr;gap:8px}</style>
