<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { listLeads, convertLead } from "../../api/crm";
const rows = ref<any[]>([]); const loading = ref(false);
async function load() { loading.value = true; try { rows.value = (await listLeads()).data?.data ?? []; } catch { ElMessage.error("线索加载失败"); } finally { loading.value = false; } }
async function convert(id: string) { try { await convertLead(id); ElMessage.success("线索已转化"); await load(); } catch { ElMessage.error("线索转化失败"); } }
onMounted(load);
</script>
<template><el-card v-loading="loading"><template #header>CRM 线索</template><el-table :data="rows"><el-table-column prop="name" label="名称"/><el-table-column prop="status" label="状态"/><el-table-column label="操作"><template #default="scope"><el-button @click="convert(scope.row.id)">转化</el-button></template></el-table-column></el-table></el-card></template>
