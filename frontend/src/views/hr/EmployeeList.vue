<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";

import { listAdmin } from "../../api/admin";
import { changeEmployeePassword, createEmployee, listEmployees, updateEmployee } from "../../api/hr";
import { useAuthStore } from "../../stores/auth";
import { usePermissionStore } from "../../stores/permission";
import { useClientPagination } from "../../composables/useClientPagination";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const { pagedRows, page, pageSize, total, updatePageSize } = useClientPagination(rows);
const departments = ref<Row[]>([]);
const loading = ref(false);
const saving = ref(false);
const dialogVisible = ref(false);
const passwordDialogVisible = ref(false);
const editing = ref<Row | null>(null);
const passwordEmployee = ref<Row | null>(null);
const password = ref("");
const confirmPassword = ref("");
const form = reactive({ employee_no: "", name: "", department_id: "", status: "active", base_salary: 0, allowance: 0, account_username: "", account_password: "" });
const auth = useAuthStore();
const permissions = usePermissionStore();
const canManage = () => Boolean(auth.user?.is_superuser || permissions.hasPermission("hr:employee:manage"));

function resetForm() { Object.assign(form, { employee_no: "", name: "", department_id: "", status: "active", base_salary: 0, allowance: 0, account_username: "", account_password: "" }); }
async function load() { loading.value = true; try { const response = await listEmployees(); if (response.data.code !== 0) throw new Error(response.data.msg); rows.value = Array.isArray(response.data?.data) ? response.data.data : []; } catch (error) { rows.value = []; ElMessage.error(error instanceof Error ? error.message : "员工列表加载失败"); } finally { loading.value = false; } }
function openCreate() { editing.value = null; resetForm(); dialogVisible.value = true; }
function openEdit(row: Row) { editing.value = row; Object.assign(form, { employee_no: row.employee_no, name: row.name, department_id: row.department_id || "", status: row.status || "active", base_salary: Number(row.base_salary || 0), allowance: Number(row.allowance || 0), account_username: "", account_password: "" }); dialogVisible.value = true; }
async function save() {
  if (!form.employee_no.trim() || !form.name.trim()) { ElMessage.warning("请填写工号和姓名"); return; }
  if (!editing.value && form.account_username && !form.account_password) { ElMessage.warning("请输入账号初始密码"); return; }
  saving.value = true;
  try {
    const response = editing.value ? await updateEmployee(editing.value.id, { name: form.name, department_id: form.department_id || null, status: form.status, base_salary: form.base_salary, allowance: form.allowance }) : await createEmployee({ ...form, department_id: form.department_id || null, account_username: form.account_username || null, account_password: form.account_password || null });
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success(editing.value ? "员工信息已更新" : "员工已创建"); dialogVisible.value = false; await load();
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "员工保存失败"); } finally { saving.value = false; }
}
function openPassword(row: Row) { passwordEmployee.value = row; password.value = ""; confirmPassword.value = ""; passwordDialogVisible.value = true; }
async function savePassword() {
  if (password.value.length < 8) { ElMessage.warning("密码至少 8 位"); return; }
  if (password.value !== confirmPassword.value) { ElMessage.warning("两次输入的密码不一致"); return; }
  if (!passwordEmployee.value?.user_id) { ElMessage.warning("该员工尚未绑定登录账号"); return; }
  saving.value = true;
  try { const response = await changeEmployeePassword(passwordEmployee.value.id, password.value); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("账号密码已更新"); passwordDialogVisible.value = false; } catch (error) { ElMessage.error(error instanceof Error ? error.message : "密码修改失败"); } finally { saving.value = false; }
}
onMounted(async () => {
  await Promise.all([
    load(),
    listAdmin("departments").then((response) => {
      if (response.data.code !== 0) throw new Error(response.data.msg);
      departments.value = Array.isArray(response.data.data) ? response.data.data : [];
    }).catch((error) => ElMessage.error(error instanceof Error ? error.message : "部门列表加载失败")),
  ]);
});
</script>

<template>
  <section class="page-stack">
    <el-page-header content="人事员工档案" />
    <el-card shadow="never">
      <div class="toolbar"><div><strong>员工信息</strong><span>维护员工资料与系统登录账号</span></div><div><el-button v-if="canManage()" type="primary" @click="openCreate">新增员工</el-button><el-button :loading="loading" @click="load">刷新</el-button></div></div>
      <el-table v-loading="loading" :data="pagedRows" stripe width="100%" fit :header-cell-style="{ textAlign: 'center' }" :cell-style="{ textAlign: 'center' }">
        <el-table-column prop="employee_no" label="工号" min-width="120" />
        <el-table-column prop="name" label="姓名" min-width="120" />
        <el-table-column label="部门" min-width="140"><template #default="scope">{{ departments.find((item) => item.id === scope.row.department_id)?.name || "-" }}</template></el-table-column>
        <el-table-column label="登录账号" min-width="150"><template #default="scope">{{ scope.row.account_username || "未绑定" }}</template></el-table-column>
        <el-table-column prop="status" label="状态" width="100"><template #default="scope"><el-tag :type="scope.row.status === 'active' ? 'success' : 'info'">{{ scope.row.status === "active" ? "在职" : "停用" }}</el-tag></template></el-table-column>
        <el-table-column v-if="canManage()" label="操作" width="220"><template #default="scope"><el-button link type="primary" @click="openEdit(scope.row)">设置员工信息</el-button><el-button link type="warning" @click="openPassword(scope.row)">修改密码</el-button></template></el-table-column>
        <template #empty><el-empty description="暂无员工" /></template>
      </el-table>
      <ClientPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @update:page-size="updatePageSize" />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editing ? '设置员工信息' : '新增员工'" width="620px">
      <el-form label-width="100px">
        <el-form-item label="工号" required><el-input v-model="form.employee_no" :disabled="Boolean(editing)" placeholder="请输入工号" /></el-form-item>
        <el-form-item label="姓名" required><el-input v-model="form.name" placeholder="请输入姓名" /></el-form-item>
        <el-form-item label="所属部门"><el-select v-model="form.department_id" clearable style="width: 100%"><el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
        <el-form-item label="状态"><el-select v-model="form.status" style="width: 100%"><el-option label="在职" value="active" /><el-option label="停用" value="inactive" /></el-select></el-form-item>
        <el-form-item label="基本工资"><el-input-number v-model="form.base_salary" :min="0" :precision="2" /></el-form-item>
        <el-form-item label="津贴"><el-input-number v-model="form.allowance" :min="0" :precision="2" /></el-form-item>
        <template v-if="!editing"><el-divider content-position="left">登录账号（可选）</el-divider><el-form-item label="登录账号"><el-input v-model="form.account_username" placeholder="不填写则暂不绑定账号" autocomplete="username" /></el-form-item><el-form-item label="初始密码"><el-input v-model="form.account_password" type="password" show-password placeholder="至少 8 位" autocomplete="new-password" /></el-form-item></template>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="passwordDialogVisible" title="修改员工账号密码" width="480px">
      <p class="dialog-note">正在修改：{{ passwordEmployee?.name }}（{{ passwordEmployee?.account_username }}）</p>
      <el-form label-width="90px"><el-form-item label="新密码" required><el-input v-model="password" type="password" show-password autocomplete="new-password" /></el-form-item><el-form-item label="确认密码" required><el-input v-model="confirmPassword" type="password" show-password autocomplete="new-password" /></el-form-item></el-form>
      <template #footer><el-button @click="passwordDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="savePassword">保存密码</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.toolbar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.toolbar div:first-child { display: flex; flex-direction: column; gap: 5px; }.toolbar span, .dialog-note { color: var(--erp-muted-text); font-size: 13px; }.dialog-note { margin: 0 0 18px; }
</style>
