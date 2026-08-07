import { createApp } from "vue";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import { createPinia } from "pinia";
import { router } from "./router";
import App from "./App.vue";
import "./styles/theme.css";

createApp(App).use(createPinia()).use(router).use(ElementPlus).mount("#app");
