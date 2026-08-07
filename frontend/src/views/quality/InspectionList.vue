<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { listInspections, submitInspection, closeInspection } from "../../api/quality";

const rows = ref<any[]>([]);
const inspectionId = ref("");
const loading = ref(false);
async function load() {
  loading.value = true;
  try { rows.value = (await listInspections()).data?.data ?? []; }
  catch { ElMessage.error("检验列表加载失败"); }
  finally { loading.value = false; }
}
async function submit() {
  try { await submitInspection(inspectionId.value, [{ item: "appearance", value: "pass", passed: true }]); ElMessage.success("检验已提交"); await load(); }
  catch { ElMessage.error("检验提交失败"); }
}
async function close() {
  try { await closeInspection(inspectionId.value, "accept"); ElMessage.success("检验已关闭"); await load(); }
  catch { ElMessage.error("检验关闭失败"); }
}
onMounted(load);
</script>

<template>
  <el-card v-loading="loading">
    <template #header>质量检验</template>
    <el-table :data="rows"><el-table-column prop="source_id" label="来源单据"/><el-table-column prop="result" label="结果"/><el-table-column prop="status" label="状态"/></el-table>
    <el-input v-model="inspectionId" placeholder="检验单 ID"/><el-button @click="submit">提交结果</el-button><el-button @click="close">关闭检验</el-button>
  </el-card>
</template>
