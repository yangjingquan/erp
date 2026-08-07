<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { createAdmin, listAdmin, setAdminStatus, type AdminResource } from "../../api/admin";

type Row = Record<string, any>;
const active = ref<AdminResource>("departments");
const rows = ref<Row[]>([]);
const roles = ref<Row[]>([]);
const loading = ref(false);
const saving = ref(false);
const dialogVisible = ref(false);
const form = reactive<Record<string, any>>({});
const configs: Record<AdminResource, { title: string; columns: Array<{ prop: string; label: string }>; fields: Array<{ prop: string; label: string; type?: string; required?: boolean }> }> = {
  departments: { title: "部门", columns: [{ prop: "code", label: "编码" }, { prop: "name", label: "名称" }, { prop: "status", label: "状态" }], fields: [{ prop: "code", label: "部门编码", required: true }, { prop: "name", label: "部门名称", required: true }, { prop: "parent_id", label: "上级部门ID" }] },
  roles: { title: "角色", columns: [{ prop: "code", label: "编码" }, { prop: "name", label: "名称" }, { prop: "data_scope_type", label: "数据范围" }, { prop: "status", label: "状态" }], fields: [{ prop: "code", label: "角色编码", required: true }, { prop: "name", label: "角色名称", required: true }, { prop: "data_scope_type", label: "数据范围" }] },
  users: { title: "用户", columns: [{ prop: "username", label: "登录账号" }, { prop: "display_name", label: "姓名" }, { prop: "department_id", label: "部门ID" }, { prop: "status", label: "状态" }], fields: [{ prop: "username", label: "登录账号", required: true }, { prop: "display_name", label: "姓名", required: true }, { prop: "password", label: "初始密码", type: "password", required: true }, { prop: "department_id", label: "部门ID" }, { prop: "role_ids", label: "角色" }] },
  menus: { title: "菜单", columns: [{ prop: "code", label: "编码" }, { prop: "name", label: "名称" }, { prop: "path", label: "路由" }, { prop: "status", label: "状态" }], fields: [{ prop: "code", label: "菜单编码", required: true }, { prop: "name", label: "菜单名称", required: true }, { prop: "path", label: "路由路径" }, { prop: "component", label: "组件路径" }] },
};

function config() { return configs[active.value]; }
function resetForm() { Object.keys(form).forEach((key) => delete form[key]); config().fields.forEach((field) => { form[field.prop] = field.prop === "role_ids" ? [] : ""; }); }
async function load(resource = active.value) {
  loading.value = true;
  try {
    const response = await listAdmin(resource);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    rows.value = Array.isArray(response.data.data) ? response.data.data : [];
    if (resource === "roles") roles.value = rows.value;
  } catch (error) { rows.value = []; ElMessage.error(error instanceof Error ? error.message : "数据加载失败"); }
  finally { loading.value = false; }
}
function changeTab(value: string | number) { active.value = value as AdminResource; void load(active.value); }
function openCreate() { resetForm(); dialogVisible.value = true; }
async function save() {
  const required = config().fields.filter((field) => field.required).find((field) => !String(form[field.prop] ?? "").trim());
  if (required) { ElMessage.warning(`请输入${required.label}`); return; }
  saving.value = true;
  try { const response = await createAdmin(active.value, { ...form }); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success(`新增${config().title}成功`); dialogVisible.value = false; await load(); }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : "保存失败"); }
  finally { saving.value = false; }
}
async function toggleStatus(row: Row) {
  const next = row.status === "active" ? "inactive" : "active";
  try { await ElMessageBox.confirm(`确认将“${row.name || row.display_name || row.username}”${next === "active" ? "启用" : "停用"}吗？`, "状态确认", { type: "warning" }); const response = await setAdminStatus(active.value, row.id, next); if (response.data.code !== 0) throw new Error(response.data.msg); await load(); }
  catch (error) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "状态更新失败"); }
}
onMounted(() => { void load(); void listAdmin("roles").then((response) => { roles.value = Array.isArray(response.data.data) ? response.data.data : []; }); });
</script>

<template>
  <section class="page-stack">
    <el-page-header content="权限与基础管理" />
    <el-card shadow="never">
      <el-tabs v-model="active" @tab-change="changeTab">
        <el-tab-pane v-for="(_, key) in configs" :key="key" :label="configs[key as AdminResource].title" :name="key" />
      </el-tabs>
      <el-space class="toolbar"><el-button type="primary" @click="openCreate">新增{{ config().title }}</el-button><el-button :loading="loading" @click="load()">刷新</el-button></el-space>
      <el-table v-loading="loading" :data="rows" stripe>
        <el-table-column v-for="column in config().columns" :key="column.prop" :prop="column.prop" :label="column.label" min-width="140" />
        <el-table-column label="操作" width="100"><template #default="scope"><el-button v-if="scope.row.status" link type="warning" @click="toggleStatus(scope.row)">{{ scope.row.status === "active" ? "停用" : "启用" }}</el-button></template></el-table-column>
        <template #empty><el-empty description="暂无数据" /></template>
      </el-table>
    </el-card>
    <el-dialog v-model="dialogVisible" :title="`新增${config().title}`" width="560px">
      <el-form label-width="100px">
        <el-form-item v-for="field in config().fields" :key="field.prop" :label="field.label" :required="field.required">
          <el-select v-if="field.prop === 'role_ids'" v-model="form[field.prop]" multiple style="width: 100%"><el-option v-for="role in roles" :key="role.id" :label="role.name" :value="role.id" /></el-select>
          <el-input v-else v-model="form[field.prop]" :type="field.type === 'password' ? 'password' : 'text'" :show-password="field.type === 'password'" />
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>.page-stack { display: flex; flex-direction: column; gap: 16px; }.toolbar { margin-bottom: 16px; }</style>
