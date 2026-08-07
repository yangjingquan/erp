<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { createReceipt, listReceivables } from "../../api/finance";
import { useMasterOptions } from "../../composables/useMasterOptions";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const loading = ref(false);
const saving = ref(false);
const errorMessage = ref("");
const dialogVisible = ref(false);
const form = reactive({ customer_id: "", amount: 0 });
const { customers, loadOptions } = useMasterOptions();
function listFrom(response: any): Row[] { const data = response?.data?.data; return Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : []; }
async function load() { loading.value = true; errorMessage.value = ""; try { rows.value = listFrom(await listReceivables()); } catch (error) { errorMessage.value = "应收账款加载失败，请检查接口服务后重试"; } finally { loading.value = false; } }
function openCreate() { form.customer_id = ""; form.amount = 0; dialogVisible.value = true; }
async function save() { if (!form.customer_id || form.amount <= 0) { ElMessage.warning("请填写客户和大于 0 的收款金额"); return; } saving.value = true; try { await createReceipt(form); ElMessage.success("收款单已创建"); dialogVisible.value = false; await load(); } catch (error) { ElMessage.error("收款单创建失败"); } finally { saving.value = false; } }
onMounted(async () => { await Promise.all([load(), loadOptions(["customers"])]); });
</script>

<template>
  <section>
    <el-page-header content="应收账款" />
    <el-space class="toolbar"><el-button type="primary" @click="openCreate">登记收款</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''"><template #default><el-button link type="primary" @click="load">重新加载</el-button></template></el-alert>
    <el-table v-loading="loading" :data="rows" stripe><el-table-column prop="doc_no" label="应收单号" /><el-table-column label="客户"><template #default="scope">{{ scope.row.customer_name || scope.row.customer_id }}</template></el-table-column><el-table-column prop="total_amount" label="应收金额" /><el-table-column prop="reconciled_amount" label="已核销" /><el-table-column prop="status" label="状态" /></el-table>
    <el-dialog v-model="dialogVisible" title="登记收款" width="440px"><el-form label-width="90px"><el-form-item label="客户" required><el-select v-model="form.customer_id" filterable clearable style="width: 100%"><el-option v-for="option in customers" :key="option.value" v-bind="option" /></el-select></el-form-item><el-form-item label="收款金额" required><el-input-number v-model="form.amount" :min="0.01" :precision="2" /></el-form-item></el-form><template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template></el-dialog>
  </section>
</template>

<style scoped>.toolbar { margin: 16px 0; }</style>
