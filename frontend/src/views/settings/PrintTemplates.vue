<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { createPrintTemplate, listPrintTemplates, type PrintTemplate } from "../../api/config";

const rows = ref<PrintTemplate[]>([]);
const loading = ref(false);
const saving = ref(false);
const dialogVisible = ref(false);
const form = reactive<Omit<PrintTemplate, "id">>({ business_type: "sales_order", name: "", template_html: "<h1>{{ doc_no }}</h1>", status: "active" });

async function load() {
  loading.value = true;
  try {
    const response = await listPrintTemplates();
    if (response.data.code !== 0) throw new Error(response.data.msg || "打印模板加载失败");
    rows.value = Array.isArray(response.data.data) ? response.data.data : [];
  } catch (error) {
    rows.value = [];
    ElMessage.error(error instanceof Error ? error.message : "打印模板加载失败");
  } finally { loading.value = false; }
}

function openCreate() {
  form.business_type = "sales_order";
  form.name = "";
  form.template_html = "<h1>{{ doc_no }}</h1>";
  form.status = "active";
  dialogVisible.value = true;
}

async function save() {
  if (!form.name.trim() || !form.template_html.trim()) { ElMessage.warning("模板名称和内容不能为空"); return; }
  saving.value = true;
  try {
    const response = await createPrintTemplate({ ...form });
    if (response.data.code !== 0) throw new Error(response.data.msg || "打印模板保存失败");
    ElMessage.success("打印模板已保存");
    dialogVisible.value = false;
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "打印模板保存失败");
  } finally { saving.value = false; }
}

onMounted(load);
</script>

<template>
  <section>
    <el-page-header content="打印模板" />
    <el-space class="toolbar"><el-button type="primary" @click="openCreate">新增模板</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-table v-loading="loading" :data="rows" border>
      <el-table-column prop="business_type" label="业务类型" />
      <el-table-column prop="name" label="模板名称" />
      <el-table-column prop="status" label="状态" />
      <template #empty><el-empty description="暂无打印模板" /></template>
    </el-table>
    <el-dialog v-model="dialogVisible" title="新增打印模板" width="620px">
      <el-form label-width="100px">
        <el-form-item label="业务类型" required><el-select v-model="form.business_type" style="width: 100%"><el-option label="销售报价" value="sales_quote"/><el-option label="销售订单" value="sales_order"/><el-option label="采购订单" value="purchase_order"/><el-option label="采购入库" value="purchase_receipt"/><el-option label="生产工单" value="mfg_work_order"/></el-select></el-form-item>
        <el-form-item label="模板名称" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="模板内容" required><el-input v-model="form.template_html" type="textarea" :rows="8" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.toolbar { margin: 16px 0; }
</style>
