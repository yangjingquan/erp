<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  createAdmin,
  getPermissionCatalog,
  getRoleAccess,
  listAdmin,
  setAdminStatus,
  updateAdmin,
  updateRoleAccess,
  updateUserRoles,
  type AdminResource,
  type FunctionPermission,
  type PermissionCatalog,
} from "../../api/admin";

type Row = Record<string, any>;
const active = ref<AdminResource>("departments");
const rows = ref<Row[]>([]);
const departmentRows = ref<Row[]>([]);
const roles = ref<Row[]>([]);
const loading = ref(false);
const saving = ref(false);
const dialogVisible = ref(false);
const editing = ref<Row | null>(null);
const form = reactive<Record<string, any>>({});
const permissionDialogVisible = ref(false);
const permissionLoading = ref(false);
const permissionSaving = ref(false);
const permissionCatalog = ref<PermissionCatalog>({ pages: [], functions: [] });
const selectedRole = ref<Row | null>(null);
const selectedPageIds = ref<string[]>([]);
const selectedFunctionIds = ref<string[]>([]);
const selectedDataScope = ref<"all" | "department" | "own">("department");
const pageTree = ref<any>();
const userRoleDialogVisible = ref(false);
const selectedUser = ref<Row | null>(null);
const selectedUserRoleIds = ref<string[]>([]);

const configs: Record<AdminResource, { title: string; columns: Array<{ prop: string; label: string }>; fields: Array<{ prop: string; label: string; type?: string; required?: boolean }> }> = {
  departments: { title: "部门", columns: [{ prop: "code", label: "编码" }, { prop: "name", label: "名称" }, { prop: "parent_id", label: "上级部门" }, { prop: "status", label: "状态" }], fields: [{ prop: "code", label: "部门编码", required: true }, { prop: "name", label: "部门名称", required: true }, { prop: "parent_id", label: "上级部门" }] },
  roles: { title: "角色", columns: [{ prop: "code", label: "编码" }, { prop: "name", label: "名称" }, { prop: "data_scope_type", label: "数据范围" }, { prop: "status", label: "状态" }], fields: [{ prop: "code", label: "角色编码", required: true }, { prop: "name", label: "角色名称", required: true }, { prop: "data_scope_type", label: "数据范围" }] },
  users: { title: "用户", columns: [{ prop: "username", label: "登录账号" }, { prop: "display_name", label: "姓名" }, { prop: "department_id", label: "部门ID" }, { prop: "status", label: "状态" }], fields: [{ prop: "username", label: "登录账号", required: true }, { prop: "display_name", label: "姓名", required: true }, { prop: "password", label: "初始密码", type: "password", required: true }, { prop: "department_id", label: "部门ID" }, { prop: "role_ids", label: "角色" }] },
  menus: { title: "菜单", columns: [{ prop: "code", label: "编码" }, { prop: "name", label: "名称" }, { prop: "path", label: "路由" }, { prop: "status", label: "状态" }], fields: [{ prop: "code", label: "菜单编码", required: true }, { prop: "name", label: "菜单名称", required: true }, { prop: "path", label: "路由路径" }, { prop: "component", label: "组件路径" }] },
};

const functionGroups = computed(() => {
  const groups = new Map<string, { name: string; items: FunctionPermission[] }>();
  permissionCatalog.value.functions.forEach((item) => {
    const group = groups.get(item.menu_id) || { name: item.menu_name, items: [] };
    group.items.push(item);
    groups.set(item.menu_id, group);
  });
  return [...groups.entries()].map(([menuId, group]) => ({ menuId, ...group }));
});

function config() { return configs[active.value]; }
function resetForm() { Object.keys(form).forEach((key) => delete form[key]); config().fields.forEach((field) => { form[field.prop] = field.prop === "role_ids" ? [] : field.prop === "data_scope_type" ? "department" : ""; }); }
function buildDepartmentTree(items: Row[]) {
  const nodes: Row[] = items.map((item) => ({ ...item, children: [] as Row[] }));
  const byId = new Map(nodes.map((item) => [item.id, item]));
  const roots: Row[] = [];
  nodes.forEach((node) => {
    const parent = node.parent_id ? byId.get(node.parent_id) : undefined;
    if (parent) parent.children.push(node);
    else roots.push(node);
  });
  return roots;
}
const departmentTree = computed(() => buildDepartmentTree(departmentRows.value));
const departmentTreeForForm = computed(() => {
  const excluded = new Set<string>();
  if (editing.value && active.value === "departments") {
    excluded.add(editing.value.id);
    let changed = true;
    while (changed) {
      changed = false;
      departmentRows.value.forEach((item) => {
        if (item.parent_id && excluded.has(item.parent_id) && !excluded.has(item.id)) {
          excluded.add(item.id);
          changed = true;
        }
      });
    }
  }
  return buildDepartmentTree(departmentRows.value.filter((item) => !excluded.has(item.id)));
});
function departmentName(id: string | null | undefined) { return departmentRows.value.find((item) => item.id === id)?.name || "-"; }
function cellValue(row: Row, prop: string) { return active.value === "departments" && prop === "parent_id" ? departmentName(row.parent_id) : row[prop]; }
async function load(resource = active.value) {
  loading.value = true;
  try {
    const response = await listAdmin(resource);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    rows.value = Array.isArray(response.data.data) ? response.data.data : [];
    if (resource === "departments") departmentRows.value = rows.value;
    if (resource === "roles") roles.value = rows.value;
  } catch (error) { rows.value = []; ElMessage.error(error instanceof Error ? error.message : "数据加载失败"); }
  finally { loading.value = false; }
}
function changeTab(value: string | number) { active.value = value as AdminResource; void load(active.value); }
function openCreate() { editing.value = null; resetForm(); dialogVisible.value = true; }
function openEdit(row: Row) {
  if (active.value !== "departments" && active.value !== "roles") return;
  editing.value = row;
  resetForm();
  config().fields.forEach((field) => { form[field.prop] = row[field.prop] ?? (field.prop === "data_scope_type" ? "department" : ""); });
  dialogVisible.value = true;
}
async function save() {
  const required = config().fields.filter((field) => field.required).find((field) => !String(form[field.prop] ?? "").trim());
  if (required) { ElMessage.warning(`请输入${required.label}`); return; }
  saving.value = true;
  try {
    const payload = { ...form };
    if (active.value === "departments") payload.parent_id = payload.parent_id || null;
    const response = editing.value ? await updateAdmin(active.value, editing.value.id, payload) : await createAdmin(active.value, payload);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success(`${editing.value ? "编辑" : "新增"}${config().title}成功`);
    dialogVisible.value = false;
    await load();
  }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : "保存失败"); }
  finally { saving.value = false; }
}
async function toggleStatus(row: Row) {
  const next = row.status === "active" ? "inactive" : "active";
  try { await ElMessageBox.confirm(`确认将“${row.name || row.display_name || row.username}”${next === "active" ? "启用" : "停用"}吗？`, "状态确认", { type: "warning" }); const response = await setAdminStatus(active.value, row.id, next); if (response.data.code !== 0) throw new Error(response.data.msg); await load(); }
  catch (error) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "状态更新失败"); }
}

async function openRoleAccess(row: Row) {
  selectedRole.value = row;
  permissionDialogVisible.value = true;
  permissionLoading.value = true;
  try {
    const [catalogResponse, accessResponse] = await Promise.all([getPermissionCatalog(), getRoleAccess(row.id)]);
    if (catalogResponse.data.code !== 0 || accessResponse.data.code !== 0) throw new Error("权限目录加载失败");
    permissionCatalog.value = catalogResponse.data.data;
    selectedPageIds.value = accessResponse.data.data.menu_ids;
    selectedFunctionIds.value = accessResponse.data.data.permission_ids;
    selectedDataScope.value = accessResponse.data.data.data_scope_type || "department";
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "权限加载失败"); }
  finally { permissionLoading.value = false; }
}
async function saveRoleAccess() {
  if (!selectedRole.value) return;
  permissionSaving.value = true;
  try {
    const menuIds = (pageTree.value?.getCheckedKeys(false) || []) as string[];
    const response = await updateRoleAccess(selectedRole.value.id, { menu_ids: menuIds, permission_ids: selectedFunctionIds.value, data_scope_type: selectedDataScope.value });
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success("角色权限已保存");
    permissionDialogVisible.value = false;
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "权限保存失败"); }
  finally { permissionSaving.value = false; }
}
function openUserRoles(row: Row) {
  selectedUser.value = row;
  selectedUserRoleIds.value = [...(row.role_ids || [])];
  userRoleDialogVisible.value = true;
}
async function saveUserRoles() {
  if (!selectedUser.value) return;
  permissionSaving.value = true;
  try {
    const response = await updateUserRoles(selectedUser.value.id, selectedUserRoleIds.value);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success("用户角色已保存");
    userRoleDialogVisible.value = false;
    await load("users");
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "用户角色保存失败"); }
  finally { permissionSaving.value = false; }
}
onMounted(async () => {
  await load();
  try {
    const response = await listAdmin("roles");
    if (response.data.code !== 0) throw new Error(response.data.msg);
    roles.value = Array.isArray(response.data.data) ? response.data.data : [];
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "角色列表加载失败");
  }
});
</script>

<template>
  <section class="page-stack">
    <el-page-header content="权限设置" />
    <el-card shadow="never">
      <el-tabs v-model="active" @tab-change="changeTab">
        <el-tab-pane v-for="(_, key) in configs" :key="key" :label="configs[key as AdminResource].title" :name="key" />
      </el-tabs>
      <el-space class="toolbar"><el-button type="primary" @click="openCreate">新增{{ config().title }}</el-button><el-button :loading="loading" @click="load()">刷新</el-button></el-space>
      <el-table v-loading="loading" :data="active === 'departments' ? departmentTree : rows" row-key="id" stripe :tree-props="{ children: 'children' }">
        <el-table-column v-for="column in config().columns" :key="column.prop" :prop="column.prop" :label="column.label" min-width="140"><template #default="scope">{{ cellValue(scope.row, column.prop) }}</template></el-table-column>
        <el-table-column v-if="active === 'roles'" label="权限配置" width="120"><template #default="scope"><el-button link type="primary" @click="openRoleAccess(scope.row)">配置权限</el-button></template></el-table-column>
        <el-table-column v-if="active === 'users'" label="角色配置" width="120"><template #default="scope"><el-button link type="primary" @click="openUserRoles(scope.row)">配置角色</el-button></template></el-table-column>
        <el-table-column label="操作" :width="active === 'departments' || active === 'roles' ? 180 : 100"><template #default="scope"><el-button v-if="active === 'departments' || active === 'roles'" link type="primary" @click="openEdit(scope.row)">修改</el-button><el-button v-if="scope.row.status" link type="warning" @click="toggleStatus(scope.row)">{{ scope.row.status === "active" ? "停用" : "启用" }}</el-button></template></el-table-column>
        <template #empty><el-empty description="暂无数据" /></template>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="`${editing ? '编辑' : '新增'}${config().title}`" width="560px">
      <el-form label-width="100px">
        <el-form-item v-for="field in config().fields" :key="field.prop" :label="field.label" :required="field.required">
          <el-select v-if="field.prop === 'role_ids'" v-model="form[field.prop]" multiple style="width: 100%"><el-option v-for="role in roles" :key="role.id" :label="role.name" :value="role.id" /></el-select>
          <el-tree-select v-else-if="field.prop === 'parent_id'" v-model="form[field.prop]" :data="departmentTreeForForm" node-key="id" :props="{ label: 'name', children: 'children' }" check-strictly clearable filterable default-expand-all style="width: 100%" placeholder="请选择上级部门" />
          <el-select v-else-if="field.prop === 'data_scope_type'" v-model="form[field.prop]" style="width: 100%"><el-option label="全部数据" value="all" /><el-option label="本部门数据" value="department" /><el-option label="本人数据" value="own" /></el-select>
          <el-input v-else v-model="form[field.prop]" :type="field.type === 'password' ? 'password' : 'text'" :show-password="field.type === 'password'" />
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="permissionDialogVisible" :title="`配置权限 · ${selectedRole?.name || ''}`" width="880px">
      <el-skeleton v-if="permissionLoading" :rows="8" animated />
      <el-tabs v-else>
        <el-tab-pane label="页面权限">
          <div class="scope-row"><span>数据范围</span><el-select v-model="selectedDataScope" size="small" style="width: 180px"><el-option label="全部数据" value="all" /><el-option label="本部门数据" value="department" /><el-option label="本人数据" value="own" /></el-select><span class="scope-tip">员工信息将按角色数据范围过滤</span></div>
          <p class="permission-hint">勾选后用户才能看到对应页面；父级模块会随子页面自动保留。</p>
          <el-tree ref="pageTree" node-key="id" show-checkbox default-expand-all :data="permissionCatalog.pages" :default-checked-keys="selectedPageIds" :props="{ label: 'name', children: 'children' }" class="permission-tree" />
        </el-tab-pane>
        <el-tab-pane label="功能权限">
          <p class="permission-hint">功能权限控制新增、编辑、删除、导出及业务操作按钮，和页面可见性分别保存。</p>
          <div class="function-groups">
            <div v-for="group in functionGroups" :key="group.menuId" class="function-group">
              <div class="function-group-title">{{ group.name }}</div>
              <el-checkbox-group v-model="selectedFunctionIds"><el-checkbox v-for="item in group.items" :key="item.id" :value="item.id">{{ item.name }}</el-checkbox></el-checkbox-group>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
      <template #footer><el-button @click="permissionDialogVisible = false">取消</el-button><el-button type="primary" :loading="permissionSaving" @click="saveRoleAccess">保存权限</el-button></template>
    </el-dialog>

    <el-dialog v-model="userRoleDialogVisible" :title="`配置角色 · ${selectedUser?.display_name || ''}`" width="520px">
      <el-form label-width="90px"><el-form-item label="角色"><el-select v-model="selectedUserRoleIds" multiple filterable style="width: 100%"><el-option v-for="role in roles" :key="role.id" :label="role.name" :value="role.id" /></el-select></el-form-item></el-form>
      <p class="permission-hint">用户最终权限由所选角色的页面权限和功能权限合并得到。</p>
      <template #footer><el-button @click="userRoleDialogVisible = false">取消</el-button><el-button type="primary" :loading="permissionSaving" @click="saveUserRoles">保存角色</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.toolbar { margin-bottom: 16px; }
.permission-hint { margin: 0 0 16px; color: var(--erp-muted-text); font-size: 13px; }
.scope-row { display: flex; align-items: center; gap: 10px; margin-bottom: 14px; color: var(--erp-text); font-size: 13px; font-weight: 700; }
.scope-tip { color: var(--erp-muted-text); font-weight: 400; }
.permission-tree { padding: 10px 16px; border: 1px solid var(--erp-border-soft); border-radius: 10px; background: var(--erp-panel-soft); }
.function-groups { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; max-height: 450px; overflow: auto; }
.function-group { padding: 14px 16px; border: 1px solid var(--erp-border-soft); border-radius: 10px; background: var(--erp-panel-soft); }
.function-group-title { margin-bottom: 10px; color: var(--erp-text); font-weight: 700; }
.function-group :deep(.el-checkbox) { margin-right: 18px; margin-bottom: 8px; }
@media (max-width: 720px) { .function-groups { grid-template-columns: 1fr; } }
</style>
