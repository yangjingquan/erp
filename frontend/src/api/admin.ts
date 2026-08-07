import { http } from "./http";

export type AdminResource = "departments" | "roles" | "users" | "menus";

export function listAdmin(resource: AdminResource) { return http.get(`/admin/${resource}`); }
export function createAdmin(resource: AdminResource, payload: Record<string, unknown>) { return http.post(`/admin/${resource}`, payload); }
export function setAdminStatus(resource: AdminResource, id: string, status: "active" | "inactive") {
  return http.post(`/admin/${resource}/${id}/status`, { status });
}
