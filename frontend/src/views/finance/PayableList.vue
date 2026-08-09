<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { createPayment, listPayables } from "../../api/finance";
import { useMasterOptions } from "../../composables/useMasterOptions";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const loading = ref(false);
const saving = ref(false);
const errorMessage = ref("");
const dialogVisible = ref(false);
const form = reactive({ supplier_id: "", amount: 0 });
const { suppliers, loadOptions } = useMasterOptions();
function listFrom(response: any): Row[] { if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "应付账款接口返回失败"); const data = response?.data?.data; return Array.isArray(data) ? data : Array.isArray(data?.items) ? data.items : []; }
async function load() { loading.value = true; errorMessage.value = ""; try { rows.value = listFrom(await listPayables()); } catch (error) { errorMessage.value = "应付账款加载失败，请检查接口服务后重试"; } finally { loading.value = false; } }
function openCreate() { form.supplier_id = ""; form.amount = 0; dialogVisible.value = true; }
async function save() { if (!form.supplier_id || form.amount <= 0) { ElMessage.warning("请填写供应商和大于 0 的付款金额"); return; } saving.value = true; try { const response = await createPayment(form); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("付款单已创建"); dialogVisible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "付款单创建失败"); } finally { saving.value = false; } }
onMounted(async () => { await Promise.all([load(), loadOptions(["suppliers"])]); });
</script>

<template>
  <section>
    <el-page-header content="应付账款" />
    <el-space class="toolbar"><el-button type="primary" @click="openCreate">登记付款</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''"><template #default><el-button link type="primary" @click="load">重新加载</el-button></template></el-alert>
    <el-table v-loading="loading" :data="rows" stripe><el-table-column prop="doc_no" label="应付单号" /><el-table-column label="供应商"><template #default="scope">{{ scope.row.supplier_name || scope.row.supplier_id }}</template></el-table-column><el-table-column prop="total_amount" label="应付金额" /><el-table-column prop="reconciled_amount" label="已核销" /><el-table-column prop="status" label="状态" /></el-table>
    <el-dialog v-model="dialogVisible" title="登记付款" width="440px"><el-form label-width="90px"><el-form-item label="供应商" required><el-select v-model="form.supplier_id" filterable clearable style="width: 100%"><el-option v-for="option in suppliers" :key="option.value" v-bind="option" /></el-select></el-form-item><el-form-item label="付款金额" required><el-input-number v-model="form.amount" :min="0.01" :precision="2" /></el-form-item></el-form><template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template></el-dialog>
  </section>
</template>

<style scoped>.toolbar { margin: 16px 0; }</style>
