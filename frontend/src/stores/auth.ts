import { defineStore } from "pinia";

import { http } from "../api/http";
import { usePermissionStore, type MenuItem } from "./permission";

const storage = typeof localStorage === "undefined" ? null : localStorage;

export interface CurrentUser {
  id: string;
  username: string;
  display_name: string;
  org_id: string;
  department_id?: string | null;
  is_superuser: boolean;
  permissions?: string[];
  menus?: MenuItem[];
  data_scope_type?: "all" | "department" | "own";
}

export const useAuthStore = defineStore("auth", {
  state: () => ({
    token: storage?.getItem("erp_access_token") as string | null,
    refreshToken: storage?.getItem("erp_refresh_token") as string | null,
    user: null as CurrentUser | null,
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.token),
  },
  actions: {
    setTokens(accessToken: string, refreshToken?: string) {
      this.token = accessToken;
      storage?.setItem("erp_access_token", accessToken);
      if (refreshToken) {
        this.refreshToken = refreshToken;
        storage?.setItem("erp_refresh_token", refreshToken);
      }
    },
    async login(username: string, password: string) {
      const response = await http.post("/auth/login", { username, password });
      const data = response.data.data;
      this.setTokens(data.access_token, data.refresh_token);
      this.user = data.user;
      usePermissionStore().loadMenus(data.user.menus ?? [], data.user.permissions ?? []);
      return data.user as CurrentUser;
    },
    async loadCurrentUser() {
      if (!this.token) return null;
      const response = await http.get("/auth/me");
      this.user = response.data.data;
      usePermissionStore().loadMenus(this.user?.menus ?? [], this.user?.permissions ?? []);
      return this.user;
    },
    logout() {
      this.token = null;
      this.refreshToken = null;
      this.user = null;
      usePermissionStore().$reset();
      storage?.removeItem("erp_access_token");
      storage?.removeItem("erp_refresh_token");
    },
  },
});
