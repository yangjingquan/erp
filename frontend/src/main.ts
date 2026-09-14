import { createApp } from "vue";
import ElementPlus from "element-plus";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import "element-plus/dist/index.css";
import { createPinia, setActivePinia } from "pinia";
import { router } from "./router";
import App from "./App.vue";
import ClientPagination from "./components/ClientPagination.vue";
import { useAuthStore } from "./stores/auth";
import "./styles/theme.css";

const pinia = createPinia();
setActivePinia(pinia);

async function bootstrap() {
  const auth = useAuthStore(pinia);
  if (auth.token) {
    try {
      await auth.loadCurrentUser();
    } catch {
      auth.logout();
    }
  }
  const app = createApp(App);
  app.config.errorHandler = (error, _instance, info) => {
    console.error("[ERP] 页面运行异常", { error, info });
    window.dispatchEvent(new CustomEvent("erp:app-error", { detail: { message: "页面运行异常，请刷新重试" } }));
  };

  router.onError((error) => {
    console.error("[ERP] 页面资源加载失败", error);
    window.dispatchEvent(new CustomEvent("erp:resource-error", { detail: { message: "页面资源加载失败，请刷新重试" } }));
  });
  window.addEventListener("error", (event) => {
    const target = event.target as HTMLElement | null;
    if (target?.tagName === "SCRIPT" || target?.tagName === "LINK") {
      const resourceUrl = target instanceof HTMLScriptElement ? target.src : (target as HTMLLinkElement).href;
      console.error("[ERP] 静态资源加载失败", resourceUrl);
      window.dispatchEvent(new CustomEvent("erp:resource-error", { detail: { message: "页面资源加载失败，请刷新重试" } }));
    }
  }, true);

  app.use(pinia).use(router).use(ElementPlus, { locale: zhCn }).component("ClientPagination", ClientPagination).mount("#app");
  window.setTimeout(() => {
    if (!document.querySelector("#app")?.children.length) {
      console.error("[ERP] 白屏监控：#app 未渲染页面");
      window.dispatchEvent(new CustomEvent("erp:white-screen"));
    }
  }, 1500);
}

void bootstrap();
