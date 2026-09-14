<script setup lang="ts">
import { onErrorCaptured, onMounted, onUnmounted, ref } from "vue";

type Failure = { title: string; message: string };
const failure = ref<Failure | null>(null);

function showFailure(event: Event) {
  const detail = (event as CustomEvent<Failure>).detail;
  failure.value = {
    title: event.type === "erp:white-screen" ? "页面未能正常渲染" : "页面加载异常",
    message: detail?.message || "系统遇到临时问题，请刷新后重试。",
  };
}

function reload() { window.location.reload(); }
function goDashboard() { window.location.assign("/dashboard"); }

onErrorCaptured((error, _instance, info) => {
  console.error("[ERP] 组件渲染异常", { error, info });
  failure.value = { title: "页面运行异常", message: "系统遇到临时问题，请刷新后重试。" };
  return false;
});

onMounted(() => {
  ["erp:app-error", "erp:resource-error", "erp:white-screen"].forEach((type) => window.addEventListener(type, showFailure));
});
onUnmounted(() => {
  ["erp:app-error", "erp:resource-error", "erp:white-screen"].forEach((type) => window.removeEventListener(type, showFailure));
});
</script>

<template>
  <section v-if="failure" class="app-failure" role="alert">
    <div class="app-failure-card">
      <div class="app-failure-code">ERP / RECOVERY</div>
      <h1>{{ failure.title }}</h1>
      <p>{{ failure.message }}</p>
      <div class="app-failure-actions">
        <button type="button" @click="reload">重新加载</button>
        <button type="button" class="secondary" @click="goDashboard">返回首页</button>
      </div>
    </div>
  </section>
  <router-view v-else />
</template>

<style scoped>
.app-failure { min-height: 100vh; display: grid; place-items: center; padding: 24px; background: #f4f7fb; color: #172033; }
.app-failure-card { width: min(460px, 100%); padding: 36px; border: 1px solid #dbe3ef; border-radius: 18px; background: #fff; box-shadow: 0 18px 50px rgb(24 44 78 / 12%); text-align: center; }
.app-failure-code { color: #64748b; font-size: 12px; font-weight: 700; letter-spacing: .16em; }
h1 { margin: 14px 0 10px; font-size: 24px; }
p { margin: 0; color: #64748b; line-height: 1.7; }
.app-failure-actions { display: flex; justify-content: center; gap: 10px; margin-top: 24px; }
button { padding: 9px 16px; border: 0; border-radius: 8px; background: #2563eb; color: #fff; cursor: pointer; }
button.secondary { background: #e8eef7; color: #28415f; }
</style>
