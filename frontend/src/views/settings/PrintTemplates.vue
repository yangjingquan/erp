<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { createPrintTemplate, deletePrintTemplate, listPrintTemplates, updatePrintTemplate, type PrintTemplate } from "../../api/config";
import { useClientPagination } from "../../composables/useClientPagination";
import RichTextEditor from "../../components/RichTextEditor.vue";

const rows = ref<PrintTemplate[]>([]);
const { pagedRows, page, pageSize, total, updatePageSize } = useClientPagination(rows);
const loading = ref(false);
const saving = ref(false);
const actionLoading = ref("");
const dialogVisible = ref(false);
const editingId = ref("");
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
  editingId.value = "";
  form.business_type = "sales_order";
  form.name = "";
  form.template_html = "<h1>{{ doc_no }}</h1>";
  form.status = "active";
  dialogVisible.value = true;
}

function openEdit(row: PrintTemplate) {
  editingId.value = String(row.id || "");
  form.business_type = row.business_type;
  form.name = row.name;
  form.template_html = row.template_html;
  form.status = row.status || "active";
  dialogVisible.value = true;
}

async function save() {
  if (!form.name.trim() || !form.template_html.trim()) { ElMessage.warning("模板名称和内容不能为空"); return; }
  saving.value = true;
  try {
    const response = editingId.value ? await updatePrintTemplate(editingId.value, { ...form }) : await createPrintTemplate({ ...form });
    if (response.data.code !== 0) throw new Error(response.data.msg || "打印模板保存失败");
    ElMessage.success(editingId.value ? "打印模板已更新" : "打印模板已保存");
    dialogVisible.value = false;
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "打印模板保存失败");
  } finally { saving.value = false; }
}

async function removeTemplate(row: PrintTemplate) {
  const id = String(row.id || "");
  try {
    await ElMessageBox.confirm(`确认删除打印模板“${row.name}”吗？删除后不可恢复。`, "删除确认", { type: "warning" });
    actionLoading.value = id;
    const response = await deletePrintTemplate(id);
    if (response.data.code !== 0) throw new Error(response.data.msg || "打印模板删除失败");
    ElMessage.success("打印模板已删除");
    await load();
  } catch (error: any) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "打印模板删除失败");
  } finally { actionLoading.value = ""; }
}

onMounted(load);
</script>

<template>
  <section>
    <el-page-header content="打印模板" />
    <el-space class="toolbar"><el-button type="primary" @click="openCreate">新增模板</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-table v-loading="loading" :data="pagedRows" border>
      <el-table-column prop="business_type" label="业务类型" />
      <el-table-column prop="name" label="模板名称" />
      <el-table-column label="状态" width="100"><template #default="scope"><el-tag :type="scope.row.status === 'active' ? 'success' : 'info'" effect="light">{{ scope.row.status === 'active' ? '启用' : '停用' }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="scope">
          <el-button link type="primary" @click="openEdit(scope.row)">修改</el-button>
          <el-button link type="danger" :loading="actionLoading === scope.row.id" @click="removeTemplate(scope.row)">删除</el-button>
        </template>
      </el-table-column>
      <template #empty><el-empty description="暂无打印模板" /></template>
    </el-table>
    <ClientPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @update:page-size="updatePageSize" />
    <el-dialog v-model="dialogVisible" :title="editingId ? '修改打印模板' : '新增打印模板'" width="860px">
      <el-form label-width="100px">
        <el-form-item label="业务类型" required><el-select v-model="form.business_type" style="width: 100%"><el-option label="销售报价" value="sales_quote"/><el-option label="销售订单" value="sales_order"/><el-option label="销售出库" value="sales_delivery"/><el-option label="销售退货" value="sales_return"/><el-option label="采购订单" value="purchase_order"/><el-option label="采购入库" value="purchase_receipt"/><el-option label="采购退货" value="purchase_return"/><el-option label="生产工单" value="mfg_work_order"/><el-option label="会计凭证" value="fin_voucher"/></el-select></el-form-item>
        <el-form-item label="模板名称" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="模板内容" required><RichTextEditor v-model="form.template_html" /></el-form-item>
        <el-form-item label="状态"><el-switch v-model="form.status" active-value="active" inactive-value="inactive" active-text="启用" inactive-text="停用" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.toolbar { margin: 16px 0; }
</style>
