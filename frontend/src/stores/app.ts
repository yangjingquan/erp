import { defineStore } from "pinia";

const storage = typeof localStorage === "undefined" ? null : localStorage;

export const useAppStore = defineStore("app", {
  state: () => ({
    sidebarCollapsed: false,
    theme: (storage?.getItem("erp_theme") || "light") as "light" | "dark",
    openedNavigation: null as { path: string; title: string } | null,
  }),
  actions: {
    activateNavigation(path: string, title: string) {
      // 一级导航切换时只保留当前页面，避免旧导航页继续占用工作区。
      this.openedNavigation = { path, title };
    },
    closeNavigation() {
      this.openedNavigation = null;
    },
    toggleSidebar() {
      this.sidebarCollapsed = !this.sidebarCollapsed;
    },
    toggleTheme() {
      this.theme = this.theme === "light" ? "dark" : "light";
      storage?.setItem("erp_theme", this.theme);
      document.documentElement.dataset.theme = this.theme;
    },
    applyTheme() {
      document.documentElement.dataset.theme = this.theme;
    },
  },
});
