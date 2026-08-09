<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { generateVoucher, listVouchers } from "../../api/finance";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const loading = ref(false);
const actionLoading = ref<string | null>(null);
const errorMessage = ref("");
function listFrom(response: any): Row[] { if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "会计凭证接口返回失败"); const data = response?.data?.data; return Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : []; }
async function load() { loading.value = true; errorMessage.value = ""; try { rows.value = listFrom(await listVouchers()); } catch (error) { errorMessage.value = "会计凭证加载失败，请检查接口服务后重试"; } finally { loading.value = false; } }
async function create(row: Row) { const sourceType = String(row.source_type || ""); const sourceId = String(row.source_id || ""); if (!sourceType || !sourceId) { ElMessage.error("凭证来源信息不完整，无法生成"); return; } try { await ElMessageBox.confirm(`确认根据来源单据“${sourceId}”生成凭证吗？`, "操作确认", { type: "warning" }); actionLoading.value = sourceId; const response = await generateVoucher(sourceType, sourceId); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("凭证已生成"); await load(); } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "凭证生成失败"); } finally { actionLoading.value = null; } }
onMounted(load);
</script>

<template>
  <section>
    <el-page-header content="会计凭证" />
    <el-button class="toolbar" :loading="loading" @click="load">刷新</el-button>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''"><template #default><el-button link type="primary" @click="load">重新加载</el-button></template></el-alert>
    <el-table v-loading="loading" :data="rows" stripe><el-table-column prop="voucher_no" label="凭证号" /><el-table-column prop="voucher_date" label="日期" /><el-table-column prop="total_debit" label="借方合计" /><el-table-column prop="total_credit" label="贷方合计" /><el-table-column prop="status" label="状态" /><el-table-column label="操作"><template #default="scope"><el-button v-if="!scope.row.voucher_no" link type="primary" :loading="actionLoading === scope.row.source_id" @click="create(scope.row)">生成凭证</el-button></template></el-table-column></el-table>
  </section>
</template>

<style scoped>.toolbar { margin: 16px 0; }</style>
