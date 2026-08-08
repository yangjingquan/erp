<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { convertLead, createLead, listLeads, transitionLead } from "../../api/crm";

type Row = Record<string, any>;
const rows = ref<Row[]>([]); const loading = ref(false); const saving = ref(false); const visible = ref(false); const form = reactive({ name: "", phone: "", email: "", source: "" });
async function load() { loading.value = true; try { rows.value = (await listLeads()).data?.data ?? []; } catch { ElMessage.error("线索加载失败"); } finally { loading.value = false; } }
function openCreate() { form.name = ""; form.phone = ""; form.email = ""; form.source = ""; visible.value = true; }
async function create() { if (!form.name.trim()) { ElMessage.warning("请填写线索名称"); return; } saving.value = true; try { const response = await createLead({ ...form, name: form.name.trim() }); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("线索已创建"); visible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "线索创建失败"); } finally { saving.value = false; } }
async function transition(row: Row, status: string) { try { const response = await transitionLead(row.id, status); if (response.data.code !== 0) throw new Error(response.data.msg); await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "线索状态更新失败"); } }
async function convert(id: string) { try { await convertLead(id); ElMessage.success("线索已转化"); await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "线索转化失败"); } }
onMounted(load);
</script>

<template><section class="page-stack"><el-page-header content="CRM 线索" /><el-space><el-button type="primary" @click="openCreate">新建线索</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space><el-table v-loading="loading" :data="rows" stripe><el-table-column prop="name" label="名称" min-width="180" /><el-table-column prop="phone" label="电话" width="150" /><el-table-column prop="source" label="来源" width="140" /><el-table-column prop="status" label="状态" width="120" /><el-table-column label="操作" width="260"><template #default="scope"><el-button v-if="scope.row.status === 'new'" link type="primary" @click="transition(scope.row, 'contacted')">标记已联系</el-button><el-button v-if="scope.row.status === 'contacted'" link type="primary" @click="transition(scope.row, 'qualified')">标记合格</el-button><el-button v-if="scope.row.status === 'qualified'" link type="success" @click="convert(scope.row.id)">转化</el-button><el-button v-if="!['converted', 'lost'].includes(scope.row.status)" link type="danger" @click="transition(scope.row, 'lost')">放弃</el-button></template></el-table-column><template #empty><el-empty description="暂无线索" /></template></el-table><el-dialog v-model="visible" title="新建线索" width="520px"><el-form label-width="80px"><el-form-item label="名称" required><el-input v-model="form.name" /></el-form-item><el-form-item label="电话"><el-input v-model="form.phone" /></el-form-item><el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item><el-form-item label="来源"><el-input v-model="form.source" /></el-form-item></el-form><template #footer><el-button @click="visible = false">取消</el-button><el-button type="primary" :loading="saving" @click="create">保存</el-button></template></el-dialog></section></template>

<style scoped>.page-stack { display: flex; flex-direction: column; gap: 16px; }</style>
