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

function hasRenderedUi(): boolean {
  const app = document.querySelector("#app");
  if (!app || app.children.length === 0) return false;
  // Accept login, shell layout, page content, or recovery card as "rendered".
  return Boolean(
    document.querySelector(
      ".login-page, .el-container, .page-stack, .app-failure, [data-erp-ready='1']",
    ),
  );
}

function startWhiteScreenMonitor() {
  // Avoid false positives during auth bootstrap, chunk download, and route transitions.
  const checkpoints = [2500, 4500, 7000];
  let index = 0;
  let cancelled = false;

  const cancel = () => {
    cancelled = true;
  };

  router.beforeEach(() => {
    // Route changes are transitional; do not treat empty outlet as white screen.
    document.documentElement.dataset.erpNavigating = "1";
  });
  router.afterEach(() => {
    window.setTimeout(() => {
      delete document.documentElement.dataset.erpNavigating;
      if (hasRenderedUi()) cancel();
    }, 0);
  });

  const tick = () => {
    if (cancelled) return;
    if (document.documentElement.dataset.erpNavigating === "1") {
      window.setTimeout(tick, 500);
      return;
    }
    if (hasRenderedUi()) {
      cancel();
      return;
    }
    index += 1;
    if (index < checkpoints.length) {
      window.setTimeout(tick, checkpoints[index] - checkpoints[index - 1]);
      return;
    }
    console.error("[ERP] 白屏监控：#app 未渲染页面");
    window.dispatchEvent(new CustomEvent("erp:white-screen"));
  };

  window.setTimeout(tick, checkpoints[0]);
}

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
  startWhiteScreenMonitor();
}

void bootstrap();
