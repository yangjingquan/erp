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
    pagePaths: new Set<string>(),
  }),
  actions: {
    loadMenus(menus: MenuItem[], permissions: string[] = []) {
      this.menuTree = menus;
      this.buttonPermissions = new Set(permissions);
      const paths = new Set<string>();
      const visit = (items: MenuItem[]) => items.forEach((item) => {
        if (item.path) paths.add(item.path);
        if (item.children?.length) visit(item.children);
      });
      visit(menus);
      this.pagePaths = paths;
    },
    hasPermission(permission: string) {
      return this.buttonPermissions.has("*") || this.buttonPermissions.has(permission);
    },
    hasPagePermission(path: string) {
      return this.buttonPermissions.has("*") || this.pagePaths.has(path);
    },
  },
});
