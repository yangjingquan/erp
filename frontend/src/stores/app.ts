import { defineStore } from "pinia";

const storage = typeof localStorage === "undefined" ? null : localStorage;

export const useAppStore = defineStore("app", {
  state: () => ({
    sidebarCollapsed: false,
    theme: (storage?.getItem("erp_theme") || "light") as "light" | "dark",
  }),
  actions: {
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
