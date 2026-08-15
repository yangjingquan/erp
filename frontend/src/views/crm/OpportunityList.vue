<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { addFollowUp, createOpportunity, listOpportunities, transitionOpportunity } from "../../api/crm";
import { useClientPagination } from "../../composables/useClientPagination";
import { localDateTimeString } from "../../utils/time";

type Row = Record<string, any>;
const rows = ref<Row[]>([]); const loading = ref(false); const saving = ref(false); const visible = ref(false); const form = reactive({ name: "", customer_id: "" });
const { pagedRows, page, pageSize, total, updatePageSize } = useClientPagination(rows);
async function load() { loading.value = true; try { const response = await listOpportunities(); if (response.data.code !== 0) throw new Error(response.data.msg); rows.value = Array.isArray(response.data.data) ? response.data.data : []; } catch (error) { rows.value = []; ElMessage.error(error instanceof Error ? error.message : "商机加载失败"); } finally { loading.value = false; } }
function openCreate() { form.name = ""; form.customer_id = ""; visible.value = true; }
async function create() { if (!form.name.trim()) { ElMessage.warning("请填写商机名称"); return; } saving.value = true; try { const response = await createOpportunity({ ...form, name: form.name.trim(), customer_id: form.customer_id.trim() || null }); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("商机已创建"); visible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "商机创建失败"); } finally { saving.value = false; } }
async function move(row: Row, stage: string) { try { const response = await transitionOpportunity(row.id, stage); if (response.data.code !== 0) throw new Error(response.data.msg); await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "商机阶段更新失败"); } }
async function follow(id: string) { try { const response = await addFollowUp(id, { content: "跟进记录", occurred_at: localDateTimeString() }); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("已记录跟进"); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "跟进失败"); } }
onMounted(load);
</script>

<template><section class="page-stack"><el-page-header content="CRM 商机" /><el-space><el-button type="primary" @click="openCreate">新建商机</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space><el-table v-loading="loading" :data="pagedRows" stripe><el-table-column prop="name" label="商机" min-width="220" /><el-table-column prop="customer_id" label="客户" min-width="180" /><el-table-column prop="stage" label="阶段" width="130" /><el-table-column label="操作" width="300"><template #default="scope"><el-button link type="primary" @click="follow(scope.row.id)">添加跟进</el-button><el-button v-if="scope.row.stage !== 'won'" link @click="move(scope.row, 'proposal')">推进商谈</el-button><el-button v-if="scope.row.stage !== 'won'" link type="success" @click="move(scope.row, 'won')">赢单</el-button></template></el-table-column><template #empty><el-empty description="暂无商机" /></template></el-table><ClientPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @update:page-size="updatePageSize" /><el-dialog v-model="visible" title="新建商机" width="480px"><el-form label-width="80px"><el-form-item label="商机名称" required><el-input v-model="form.name" /></el-form-item><el-form-item label="客户 ID"><el-input v-model="form.customer_id" /></el-form-item></el-form><template #footer><el-button @click="visible = false">取消</el-button><el-button type="primary" :loading="saving" @click="create">保存</el-button></template></el-dialog></section></template>

<style scoped>.page-stack { display: flex; flex-direction: column; gap: 16px; }</style>
