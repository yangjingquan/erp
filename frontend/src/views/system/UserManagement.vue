<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  changeAdminUserPassword,
  createAdmin,
  listAdmin,
  setAdminStatus,
  updateAdminUser,
  updateUserRoles,
} from "../../api/admin";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const roles = ref<Row[]>([]);
const departments = ref<Row[]>([]);
const loading = ref(false);
const saving = ref(false);
const dialogVisible = ref(false);
const passwordDialogVisible = ref(false);
const roleDialogVisible = ref(false);
const editing = ref<Row | null>(null);
const passwordUser = ref<Row | null>(null);
const roleUser = ref<Row | null>(null);
const password = ref("");
const confirmPassword = ref("");
const selectedRoleIds = ref<string[]>([]);
const form = reactive({ username: "", display_name: "", password: "", department_id: "", email: "", phone: "", status: "active", role_ids: [] as string[] });

const departmentName = computed(() => (id: string | null | undefined) => departments.value.find((item) => item.id === id)?.name || "未分配");
const roleNames = computed(() => (ids: string[] = []) => roles.value.filter((item) => ids.includes(item.id)).map((item) => item.name).join("、") || "未配置角色");

async function load() {
  loading.value = true;
  try {
    const [userResponse, roleResponse, departmentResponse] = await Promise.all([listAdmin("users"), listAdmin("roles"), listAdmin("departments")]);
    rows.value = Array.isArray(userResponse.data?.data) ? userResponse.data.data : [];
    roles.value = Array.isArray(roleResponse.data?.data) ? roleResponse.data.data : [];
    departments.value = Array.isArray(departmentResponse.data?.data) ? departmentResponse.data.data : [];
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "用户列表加载失败"); }
  finally { loading.value = false; }
}

function resetForm() { Object.assign(form, { username: "", display_name: "", password: "", department_id: "", email: "", phone: "", status: "active", role_ids: [] }); }
function openCreate() { editing.value = null; resetForm(); dialogVisible.value = true; }
function openEdit(row: Row) { editing.value = row; Object.assign(form, { username: row.username, display_name: row.display_name, password: "", department_id: row.department_id || "", email: row.email || "", phone: row.phone || "", status: row.status || "active", role_ids: [...(row.role_ids || [])] }); dialogVisible.value = true; }

async function save() {
  if (!form.display_name.trim()) { ElMessage.warning("请输入用户名称"); return; }
  if (!editing.value && !form.username.trim()) { ElMessage.warning("请输入登录账号"); return; }
  if (!editing.value && form.password.length < 8) { ElMessage.warning("初始密码至少 8 位"); return; }
  saving.value = true;
  try {
    const response = editing.value
      ? await updateAdminUser(editing.value.id, { display_name: form.display_name, department_id: form.department_id || null, email: form.email || null, phone: form.phone || null, status: form.status })
      : await createAdmin("users", { username: form.username, display_name: form.display_name, password: form.password, department_id: form.department_id || null, email: form.email || null, phone: form.phone || null, role_ids: form.role_ids });
    if (response.data.code !== 0) throw new Error(response.data.msg);
    if (!editing.value && form.role_ids.length && response.data.data?.id) await updateUserRoles(response.data.data.id, form.role_ids);
    ElMessage.success(editing.value ? "用户信息已更新" : "用户创建成功"); dialogVisible.value = false; await load();
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "用户保存失败"); }
  finally { saving.value = false; }
}

async function toggleStatus(row: Row) {
  const next = row.status === "active" ? "inactive" : "active";
  try { await ElMessageBox.confirm(`确认将“${row.display_name || row.username}”${next === "active" ? "启用" : "停用"}吗？`, "状态确认", { type: "warning" }); const response = await setAdminStatus("users", row.id, next); if (response.data.code !== 0) throw new Error(response.data.msg); await load(); }
  catch (error) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "状态更新失败"); }
}

function openPassword(row: Row) { passwordUser.value = row; password.value = ""; confirmPassword.value = ""; passwordDialogVisible.value = true; }
async function savePassword() {
  if (password.value.length < 8) { ElMessage.warning("密码至少 8 位"); return; }
  if (password.value !== confirmPassword.value) { ElMessage.warning("两次输入的密码不一致"); return; }
  if (!passwordUser.value) return;
  saving.value = true;
  try { const response = await changeAdminUserPassword(passwordUser.value.id, password.value); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("用户密码已更新"); passwordDialogVisible.value = false; }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : "密码修改失败"); }
  finally { saving.value = false; }
}

function openRoles(row: Row) { roleUser.value = row; selectedRoleIds.value = [...(row.role_ids || [])]; roleDialogVisible.value = true; }
async function saveRoles() {
  if (!roleUser.value) return;
  saving.value = true;
  try { const response = await updateUserRoles(roleUser.value.id, selectedRoleIds.value); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("用户角色已保存"); roleDialogVisible.value = false; await load(); }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : "角色保存失败"); }
  finally { saving.value = false; }
}

onMounted(load);
</script>

<template>
  <section class="page-stack">
    <el-page-header content="用户管理" />
    <el-card shadow="never">
      <div class="toolbar"><div><strong>登录用户</strong><span>维护可登录系统的用户账号、角色和数据范围</span></div><div><el-button type="primary" @click="openCreate">新增用户</el-button><el-button :loading="loading" @click="load">刷新</el-button></div></div>
      <el-table v-loading="loading" :data="rows" stripe>
        <el-table-column prop="username" label="登录账号" min-width="150" />
        <el-table-column prop="display_name" label="用户名称" min-width="130" />
        <el-table-column label="所属部门" min-width="140"><template #default="scope">{{ departmentName(scope.row.department_id) }}</template></el-table-column>
        <el-table-column label="角色" min-width="180"><template #default="scope">{{ roleNames(scope.row.role_ids) }}</template></el-table-column>
        <el-table-column prop="phone" label="手机号" min-width="130" />
        <el-table-column prop="status" label="状态" width="100"><template #default="scope"><el-tag :type="scope.row.status === 'active' ? 'success' : 'info'">{{ scope.row.status === "active" ? "启用" : "停用" }}</el-tag></template></el-table-column>
        <el-table-column label="操作" width="300"><template #default="scope"><el-button link type="primary" @click="openEdit(scope.row)">设置用户信息</el-button><el-button link type="primary" @click="openRoles(scope.row)">配置角色</el-button><el-button link type="warning" @click="openPassword(scope.row)">修改密码</el-button><el-button link type="info" @click="toggleStatus(scope.row)">{{ scope.row.status === "active" ? "停用" : "启用" }}</el-button></template></el-table-column>
        <template #empty><el-empty description="暂无登录用户" /></template>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editing ? '设置用户信息' : '新增用户'" width="620px">
      <el-form label-width="100px">
        <el-form-item label="登录账号" required><el-input v-model="form.username" :disabled="Boolean(editing)" placeholder="请输入唯一登录账号" autocomplete="username" /></el-form-item>
        <el-form-item label="用户名称" required><el-input v-model="form.display_name" placeholder="请输入用户名称" /></el-form-item>
        <el-form-item v-if="!editing" label="初始密码" required><el-input v-model="form.password" type="password" show-password placeholder="至少 8 位" autocomplete="new-password" /></el-form-item>
        <el-form-item label="所属部门"><el-select v-model="form.department_id" clearable style="width: 100%"><el-option v-for="item in departments" :key="item.id" :label="item.name" :value="item.id" /></el-select></el-form-item>
        <el-form-item label="角色"><el-select v-model="form.role_ids" multiple filterable style="width: 100%"><el-option v-for="role in roles" :key="role.id" :label="role.name" :value="role.id" /></el-select></el-form-item>
        <el-form-item label="邮箱"><el-input v-model="form.email" /></el-form-item>
        <el-form-item label="手机号"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item v-if="editing" label="状态"><el-select v-model="form.status" style="width: 100%"><el-option label="启用" value="active" /><el-option label="停用" value="inactive" /></el-select></el-form-item>
      </el-form>
      <p class="dialog-note">页面权限、功能权限和数据范围由用户所绑定的角色统一继承，可在“权限与基础管理”的角色权限中配置。</p>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="roleDialogVisible" :title="`配置角色 · ${roleUser?.display_name || ''}`" width="520px">
      <el-select v-model="selectedRoleIds" multiple filterable style="width: 100%"><el-option v-for="role in roles" :key="role.id" :label="role.name" :value="role.id" /></el-select>
      <p class="dialog-note">角色同时决定页面权限、功能权限和数据范围。具体权限请在“权限与基础管理”的角色配置中维护。</p>
      <template #footer><el-button @click="roleDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveRoles">保存角色</el-button></template>
    </el-dialog>

    <el-dialog v-model="passwordDialogVisible" title="修改用户密码" width="480px">
      <p class="dialog-note">正在修改：{{ passwordUser?.display_name }}（{{ passwordUser?.username }}）</p>
      <el-form label-width="90px"><el-form-item label="新密码" required><el-input v-model="password" type="password" show-password autocomplete="new-password" /></el-form-item><el-form-item label="确认密码" required><el-input v-model="confirmPassword" type="password" show-password autocomplete="new-password" /></el-form-item></el-form>
      <template #footer><el-button @click="passwordDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="savePassword">保存密码</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.toolbar div:first-child { display: flex; flex-direction: column; gap: 5px; }
.toolbar span, .dialog-note { color: var(--erp-muted-text); font-size: 13px; }
.dialog-note { margin: 16px 0 0; line-height: 1.6; }
@media (max-width: 800px) { .toolbar { align-items: stretch; flex-direction: column; } .toolbar > div:last-child { display: flex; } .toolbar > div:last-child .el-button { flex: 1; } }
</style>
