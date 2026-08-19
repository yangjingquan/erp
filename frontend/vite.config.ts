import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  build: {
    chunkSizeWarningLimit: 800,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("@element-plus/icons-vue")) return "element-icons";
          if (id.includes("element-plus")) return "element-plus";
          if (id.includes("echarts") || id.includes("zrender")) return "charts";
          if (id.includes("vue") || id.includes("pinia") || id.includes("vue-router")) return "vue-core";
          if (id.includes("axios")) return "http";
          return "vendor";
        },
      },
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5176,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8085",
        changeOrigin: true,
      },
    },
  },
});
