import { http } from "./http";

export type AdminResource = "departments" | "roles" | "users" | "menus";

export function listAdmin(resource: AdminResource) { return http.get(`/admin/${resource}`); }
export function createAdmin(resource: AdminResource, payload: Record<string, unknown>) { return http.post(`/admin/${resource}`, payload); }
export function updateAdminUser(id: string, payload: Record<string, unknown>) { return http.put(`/admin/users/${id}`, payload); }
export function changeAdminUserPassword(id: string, password: string) { return http.put(`/admin/users/${id}/password`, { password }); }
export function setAdminStatus(resource: AdminResource, id: string, status: "active" | "inactive") {
  return http.post(`/admin/${resource}/${id}/status`, { status });
}

export interface PermissionTreeNode {
  id: string;
  code: string;
  name: string;
  path?: string | null;
  parent_id?: string | null;
  children?: PermissionTreeNode[];
}

export interface FunctionPermission {
  id: string;
  code: string;
  name: string;
  menu_id: string;
  menu_name: string;
}

export interface PermissionCatalog {
  pages: PermissionTreeNode[];
  functions: FunctionPermission[];
}

export function getPermissionCatalog() { return http.get<{ code: number; data: PermissionCatalog }>("/admin/permissions/catalog"); }
export function getRoleAccess(roleId: string) { return http.get<{ code: number; data: { menu_ids: string[]; permission_ids: string[]; data_scope_type: "all" | "department" | "own" } }>(`/admin/roles/${roleId}/access`); }
export function updateRoleAccess(roleId: string, payload: { menu_ids: string[]; permission_ids: string[]; data_scope_type: "all" | "department" | "own" }) {
  return http.put(`/admin/roles/${roleId}/access`, payload);
}
export function updateUserRoles(userId: string, roleIds: string[]) {
  return http.put(`/admin/users/${userId}/roles`, { role_ids: roleIds });
}
