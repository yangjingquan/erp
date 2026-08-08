import { createApp } from "vue";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import { createPinia, setActivePinia } from "pinia";
import { router } from "./router";
import App from "./App.vue";
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
  createApp(App).use(pinia).use(router).use(ElementPlus).mount("#app");
}

void bootstrap();
