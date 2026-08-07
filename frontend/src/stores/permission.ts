import { defineStore } from "pinia";

export interface MenuItem {
  code: string;
  name: string;
  path?: string;
  children?: MenuItem[];
}

export const usePermissionStore = defineStore("permission", {
  state: () => ({
    menuTree: [] as MenuItem[],
    buttonPermissions: new Set<string>(),
  }),
  actions: {
    loadMenus(menus: MenuItem[], permissions: string[] = []) {
      this.menuTree = menus;
      this.buttonPermissions = new Set(permissions);
    },
    hasPermission(permission: string) {
      return this.buttonPermissions.has("*") || this.buttonPermissions.has(permission);
    },
  },
});
