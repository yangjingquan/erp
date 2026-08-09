<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { closeInspection, createInspection, listInspections, submitInspection } from "../../api/quality";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const loading = ref(false);
const saving = ref(false);
const createVisible = ref(false);
const resultVisible = ref(false);
const closeVisible = ref(false);
const selected = ref<Row | null>(null);
const createForm = reactive({ inspection_type: "incoming", source_type: "manual", source_id: "" });
const resultForm = reactive({ item: "appearance", value: "pass", passed: true });
const closeForm = reactive({ disposition: "accept" });

function listFrom(response: any) { if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "质量检验接口返回失败"); return Array.isArray(response?.data?.data) ? response.data.data : []; }
async function load() {
  loading.value = true;
  try { rows.value = listFrom(await listInspections()); }
  catch { ElMessage.error("检验列表加载失败"); }
  finally { loading.value = false; }
}
function openCreate() { createForm.inspection_type = "incoming"; createForm.source_type = "manual"; createForm.source_id = ""; createVisible.value = true; }
async function create() {
  if (!createForm.inspection_type || !createForm.source_type || !createForm.source_id.trim()) { ElMessage.warning("请填写检验类型、来源类型和来源单据"); return; }
  saving.value = true;
  try { const response = await createInspection({ ...createForm, source_id: createForm.source_id.trim() }); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("检验单已创建"); createVisible.value = false; await load(); }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : "检验单创建失败"); }
  finally { saving.value = false; }
}
function openResult(row: Row) { selected.value = row; resultForm.item = "appearance"; resultForm.value = "pass"; resultForm.passed = true; resultVisible.value = true; }
async function submitResult() {
  if (!selected.value?.id || !resultForm.item.trim() || !resultForm.value.trim()) { ElMessage.warning("请填写检验项目和结果"); return; }
  saving.value = true;
  try { const response = await submitInspection(selected.value.id, [{ ...resultForm, item: resultForm.item.trim(), value: resultForm.value.trim() }]); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("检验结果已提交"); resultVisible.value = false; await load(); }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : "检验结果提交失败"); }
  finally { saving.value = false; }
}
function openClose(row: Row) { selected.value = row; closeForm.disposition = row.result === "failed" ? "rework" : "accept"; closeVisible.value = true; }
async function close() {
  if (!selected.value?.id) return;
  try { await ElMessageBox.confirm("关闭后检验结果不可再修改，确认继续吗？", "关闭检验", { type: "warning" }); saving.value = true; const response = await closeInspection(selected.value.id, closeForm.disposition); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("检验已关闭"); closeVisible.value = false; await load(); }
  catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "检验关闭失败"); }
  finally { saving.value = false; }
}
onMounted(load);
</script>

<template>
  <section class="page-stack">
    <el-page-header content="质量检验" />
    <el-space><el-button type="primary" @click="openCreate">新建检验单</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-alert title="检验单必须先录入结构化结果，再选择处置结论关闭；不合格结果会自动生成不合格记录。" type="info" show-icon />
    <el-table v-loading="loading" :data="rows" stripe>
      <el-table-column prop="inspection_type" label="检验类型" width="130" /><el-table-column prop="source_type" label="来源类型" width="130" /><el-table-column prop="source_id" label="来源单据" min-width="180" /><el-table-column prop="result" label="结果" width="100" /><el-table-column prop="disposition" label="处置" width="100" /><el-table-column prop="status" label="状态" width="100" />
      <el-table-column label="操作" width="220"><template #default="scope"><el-button v-if="scope.row.status === 'draft'" link type="primary" @click="openResult(scope.row)">录入结果</el-button><el-button v-if="scope.row.status === 'submitted'" link type="success" @click="openClose(scope.row)">关闭检验</el-button></template></el-table-column>
      <template #empty><el-empty description="暂无检验单" /></template>
    </el-table>
    <el-dialog v-model="createVisible" title="新建检验单" width="520px"><el-form label-width="100px"><el-form-item label="检验类型" required><el-select v-model="createForm.inspection_type" style="width: 100%"><el-option label="来料检验" value="incoming" /><el-option label="过程检验" value="process" /><el-option label="成品检验" value="finished" /></el-select></el-form-item><el-form-item label="来源类型" required><el-input v-model="createForm.source_type" placeholder="如 purchase_receipt、work_order" /></el-form-item><el-form-item label="来源单据" required><el-input v-model="createForm.source_id" placeholder="填写来源单据 ID" /></el-form-item></el-form><template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="create">保存</el-button></template></el-dialog>
    <el-dialog v-model="resultVisible" title="录入检验结果" width="520px"><el-form label-width="100px"><el-form-item label="检验项目" required><el-input v-model="resultForm.item" placeholder="如 appearance、尺寸" /></el-form-item><el-form-item label="结果值" required><el-input v-model="resultForm.value" placeholder="如 pass、fail 或实测值" /></el-form-item><el-form-item label="是否通过"><el-switch v-model="resultForm.passed" active-text="通过" inactive-text="不通过" /></el-form-item></el-form><template #footer><el-button @click="resultVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitResult">提交结果</el-button></template></el-dialog>
    <el-dialog v-model="closeVisible" title="关闭检验" width="420px"><el-form label-width="100px"><el-form-item label="处置结论" required><el-select v-model="closeForm.disposition" style="width: 100%"><el-option label="接受" value="accept" /><el-option label="返工" value="rework" /><el-option label="报废" value="scrap" /></el-select></el-form-item></el-form><template #footer><el-button @click="closeVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="close">确认关闭</el-button></template></el-dialog>
  </section>
</template>

<style scoped>.page-stack { display: flex; flex-direction: column; gap: 16px; }</style>
