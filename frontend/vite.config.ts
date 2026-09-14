import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  if (mode === "production") {
    const apiBaseUrl = env.VITE_API_BASE_URL?.trim();
    if (!apiBaseUrl) throw new Error("生产构建必须设置 VITE_API_BASE_URL");
    let parsed: URL;
    try { parsed = new URL(apiBaseUrl); } catch { throw new Error("VITE_API_BASE_URL 必须是完整 URL"); }
    if (!/^https?:$/.test(parsed.protocol)) throw new Error("VITE_API_BASE_URL 仅支持 http 或 https");
    if (/^(localhost|127(?:\.\d{1,3}){3})$/i.test(parsed.hostname)) throw new Error("生产构建禁止使用 localhost 或 127.0.0.1 API 地址");
  }

  return {
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
  };
});
