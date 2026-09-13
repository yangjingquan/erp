<script setup lang="ts">
import { ref } from "vue";
import { ElMessage } from "element-plus";
import { ArrowRight, ChatDotRound, CircleCheck, Collection, Lock, Operation, User } from "@element-plus/icons-vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "../stores/auth";
import { register as registerUser } from "../api/auth";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();
const username = ref("");
const password = ref("");
const confirmPassword = ref("");
const mode = ref<"login" | "register">("login");
const loading = ref(false);

async function submit() {
  loading.value = true;
  try {
    await auth.login(username.value, password.value);
    await router.push(String(route.query.redirect || "/dashboard"));
  } catch {
    ElMessage.error("登录失败，请检查账号密码");
  } finally {
    loading.value = false;
  }
}

function switchMode(next: "login" | "register") {
  mode.value = next;
  password.value = "";
  confirmPassword.value = "";
}

function apiError(error: unknown, fallback: string) {
  const response = (error as { response?: { data?: { msg?: string } } })?.response?.data;
  return response?.msg || fallback;
}

async function submitRegister() {
  const account = username.value.trim();
  if (account.length < 3) { ElMessage.warning("账号至少 3 位"); return; }
  if (password.value.length < 8) { ElMessage.warning("密码至少 8 位"); return; }
  if (password.value !== confirmPassword.value) { ElMessage.warning("密码和确认密码不一致"); return; }
  loading.value = true;
  try {
    await registerUser(account, password.value);
    ElMessage.success("注册成功，请使用新账号登录");
    username.value = account;
    confirmPassword.value = "";
    mode.value = "login";
  } catch (error) { ElMessage.error(apiError(error, "注册失败，请稍后重试")); }
  finally { loading.value = false; }
}
</script>

<template>
  <main class="login-page">
    <section class="login-story" aria-label="ERP 平台介绍">
      <div class="story-inner">
        <div class="story-brand"><span class="brand-mark">ERP</span><strong>ERP 管理系统</strong></div>
        <div class="story-copy">
          <span class="story-label">企业经营工作台</span>
          <h1>从一张清晰的经营视图开始工作。</h1>
          <p>统一主数据、订单、库存与财务流程，让团队快速找到下一步。</p>
        </div>
        <div class="feature-list" aria-label="平台能力">
          <div class="feature-row"><span class="feature-icon"><el-icon><Collection /></el-icon></span><div><strong>统一主数据</strong><p>物料、客户、供应商与仓库保持一致</p></div></div>
          <div class="feature-row"><span class="feature-icon"><el-icon><Operation /></el-icon></span><div><strong>协同业务流程</strong><p>从销售订单到出库，节点清晰可追踪</p></div></div>
          <div class="feature-row"><span class="feature-icon"><el-icon><CircleCheck /></el-icon></span><div><strong>安全可控</strong><p>权限隔离与全链路审计，守住经营数据</p></div></div>
        </div>
        <div class="story-footer">© 2026 ERP 管理系统 · 企业经营管理平台</div>
      </div>
    </section>

    <section class="login-panel">
      <div class="login-box">
        <div class="mobile-brand story-brand"><span class="brand-mark">ERP</span><strong>ERP 管理系统</strong></div>
        <div class="login-title">
          <span class="title-mark" aria-hidden="true"></span>
          <h2>登录工作台</h2>
        </div>
        <p class="welcome-copy">登录你的企业工作台，继续处理今天的经营任务。</p>
        <div class="login-tabs" role="tablist" aria-label="账号操作"><button class="login-tab" :class="{ 'is-active': mode === 'login' }" type="button" role="tab" :aria-selected="mode === 'login'" @click="switchMode('login')">账号登录</button><button class="login-tab" :class="{ 'is-active': mode === 'register' }" type="button" role="tab" :aria-selected="mode === 'register'" @click="switchMode('register')">注册账号</button></div>
        <el-form v-if="mode === 'login'" class="login-form" label-position="top" @submit.prevent="submit">
          <el-form-item label="账号"><el-input v-model="username" placeholder="请输入账号" size="large" autocomplete="username"><template #prefix><el-icon><User /></el-icon></template></el-input></el-form-item>
          <el-form-item label="密码"><el-input v-model="password" type="password" show-password placeholder="请输入密码" size="large" autocomplete="current-password"><template #prefix><el-icon><Lock /></el-icon></template></el-input></el-form-item>
          <div class="form-helper"><span class="remember-note"><span class="checkbox-mark" aria-hidden="true" />记住本次登录</span><button class="forgot-link" type="button" @click="ElMessage.info('请联系系统管理员重置密码')">忘记密码？</button></div>
          <el-button :loading="loading" type="primary" size="large" native-type="submit" class="submit"><span>登录工作台</span><el-icon><ArrowRight /></el-icon></el-button>
        </el-form>
        <el-form v-else class="login-form" label-position="top" @submit.prevent="submitRegister">
          <el-form-item label="账号"><el-input v-model="username" placeholder="请输入注册账号" size="large" autocomplete="username"><template #prefix><el-icon><User /></el-icon></template></el-input></el-form-item>
          <el-form-item label="密码"><el-input v-model="password" type="password" show-password placeholder="至少 8 位密码" size="large" autocomplete="new-password"><template #prefix><el-icon><Lock /></el-icon></template></el-input></el-form-item>
          <el-form-item label="确认密码"><el-input v-model="confirmPassword" type="password" show-password placeholder="请再次输入密码" size="large" autocomplete="new-password"><template #prefix><el-icon><Lock /></el-icon></template></el-input></el-form-item>
          <el-button :loading="loading" type="primary" size="large" native-type="submit" class="submit"><span>注册账号</span><el-icon><ArrowRight /></el-icon></el-button>
        </el-form>
        <div class="security-note"><el-icon><CircleCheck /></el-icon><span>当前连接受企业安全策略保护。首次登录或更换设备时，可能需要管理员确认。</span></div>
        <div class="support-row"><div><strong>需要帮助?</strong><span>请联系企业系统管理员</span></div><button type="button" @click="ElMessage.info('请联系企业系统管理员')"><el-icon><ChatDotRound /></el-icon>获取支持</button></div>
        <div class="login-meta">隐私政策 · 使用条款 · 版本 1.0.0</div>
      </div>
    </section>
  </main>
</template>

<style scoped>
.login-page { min-height: 100dvh; display: grid; grid-template-columns: minmax(0, 1fr) minmax(470px, .92fr); background: #f3f1ed; overflow: hidden; }
.login-story { min-height: 100dvh; background: #2b2927; color: #f5ede6; }
.story-inner { display: flex; flex-direction: column; min-height: 100dvh; padding: 42px clamp(42px, 7vw, 116px) 28px; }
.story-brand { display: flex; align-items: center; gap: 10px; color: #fff; font-size: 15px; }
.story-brand strong { font-weight: 700; letter-spacing: .01em; }
.brand-mark { display: grid; place-items: center; width: 34px; height: 34px; border-radius: 10px; background: var(--erp-primary); color: #fff; font-size: 10px; font-weight: 700; }
.story-copy { margin: auto 0 38px; max-width: 490px; }
.story-label { display: block; margin-bottom: 14px; color: #d08a6b; font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.story-copy h1 { max-width: 460px; margin: 0 0 16px; color: #fffaf5; font-size: clamp(27px, 2.5vw, 36px); font-weight: 680; line-height: 1.3; letter-spacing: -.025em; }
.story-copy p { max-width: 420px; margin: 0; color: #b8aea7; font-size: 14px; line-height: 1.75; }
.feature-list { display: grid; gap: 0; max-width: 520px; border-top: 1px solid rgba(255,255,255,.14); }
.feature-row { display: flex; align-items: center; gap: 14px; padding: 17px 0; border-bottom: 1px solid rgba(255,255,255,.14); }
.feature-icon { display: grid; flex: 0 0 auto; place-items: center; width: 30px; height: 30px; color: #d08a6b; }
.feature-row strong { display: block; color: #f4eae2; font-size: 13px; font-weight: 700; }
.feature-row p { margin: 4px 0 0; color: #9f958d; font-size: 11px; line-height: 1.5; }
.story-footer { margin-top: auto; color: #8f837b; font-size: 11px; }
.login-panel { display: grid; place-items: center; min-height: 100dvh; padding: 48px clamp(28px, 7vw, 112px); background: #f8f7f4; }
.login-box { width: min(100%, 430px); padding: 38px 40px 32px; border: 1px solid #e4e0da; border-radius: 18px; background: #fff; }
.mobile-brand { display: none; }
.login-title { display: flex; align-items: center; gap: 12px; }
.title-mark { width: 5px; height: 28px; border-radius: 5px; background: var(--erp-primary); }
.login-box h2 { margin: 0; color: #332f2b; font-size: 28px; font-weight: 700; line-height: 1.25; letter-spacing: -.025em; }
.welcome-copy { margin: 10px 0 26px; color: #8c837b; font-size: 13px; line-height: 1.65; }
.login-tabs { display: flex; gap: 22px; height: 39px; border-bottom: 1px solid #e7e2dc; }
.login-tab { position: relative; padding: 0 0 12px; border: 0; background: transparent; color: #9a9189; font-size: 13px; cursor: pointer; }
.login-tab:focus-visible, .forgot-link:focus-visible, .support-row button:focus-visible { outline: 2px solid rgba(198,109,75,.55); outline-offset: 4px; }
.login-tab.is-active { color: var(--erp-primary-dark); font-weight: 700; }.login-tab.is-active::after { position: absolute; right: 0; bottom: -1px; left: 0; height: 2px; border-radius: 2px; background: var(--erp-primary); content: ""; }
.login-form { margin-top: 23px; }.login-form :deep(.el-form-item) { display: block; margin-bottom: 18px; }.login-form :deep(.el-form-item__label) { height: auto; margin-bottom: 8px; color: #665d56; font-size: 12px; font-weight: 700; line-height: 1; }.login-form :deep(.el-form-item__content) { min-width: 0; }.login-form :deep(.el-input__wrapper) { min-height: 44px; border-radius: 9px; background: #fcfbf9; box-shadow: 0 0 0 1px #ded8d1 inset; }.login-form :deep(.el-input__wrapper.is-focus) { box-shadow: 0 0 0 1px var(--erp-primary) inset, 0 0 0 3px rgba(198,109,75,.12); }.login-form :deep(.el-input__inner) { color: #4a4039; font-size: 13px; }.login-form :deep(.el-input__inner::placeholder) { color: #b2aaa2; }.login-form :deep(.el-input__prefix) { color: #a69c93; }.login-form :deep(.el-input__suffix) { color: #a69c93; }
.form-helper { display: flex; align-items: center; justify-content: space-between; margin: -1px 0 20px; color: #988e85; font-size: 11px; }.remember-note { display: inline-flex; align-items: center; gap: 6px; }.checkbox-mark { display: inline-block; width: 14px; height: 14px; border: 1px solid #d8d0c8; border-radius: 4px; background: #fff; }.forgot-link, .support-row button { padding: 0; border: 0; background: transparent; color: var(--erp-primary-dark); cursor: pointer; font-size: 11px; }
.submit { display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; min-height: 44px; border: 0; border-radius: 9px; background: var(--erp-primary); box-shadow: 0 8px 16px rgba(198,109,75,.2); font-size: 13px; font-weight: 700; }.submit:hover { background: #b95f42; }
.security-note { display: flex; align-items: flex-start; gap: 7px; margin-top: 19px; padding: 12px; border-radius: 9px; background: #faf2df; color: #927546; font-size: 11px; line-height: 1.55; }.security-note .el-icon { flex: 0 0 auto; margin-top: 1px; }
.support-row { display: flex; align-items: center; justify-content: space-between; margin-top: 21px; padding-top: 17px; border-top: 1px solid #eee9e3; }.support-row div { display: flex; flex-direction: column; gap: 4px; }.support-row strong { color: #756961; font-size: 11px; }.support-row span { color: #aaa097; font-size: 11px; }.support-row button { display: inline-flex; align-items: center; gap: 5px; }.login-meta { margin-top: 25px; color: #b0a8a0; font-size: 10px; text-align: center; }
@media (max-width: 1020px) { .login-page { grid-template-columns: minmax(0, 1fr) minmax(440px, .9fr); }.story-inner { padding-inline: 56px; }.story-copy h1 { font-size: 30px; } }
@media (max-width: 720px) { .login-page { display: block; }.login-story { display: none; }.login-panel { min-height: 100dvh; padding: 24px 18px; }.login-box { width: min(100%, 430px); padding: 27px 22px 24px; border-radius: 16px; }.mobile-brand { display: flex; margin-bottom: 34px; color: #3d3732; }.mobile-brand .brand-mark { color: #fff; }.login-box h2 { font-size: 26px; }.welcome-copy { margin-bottom: 24px; }.login-form { margin-top: 21px; }.login-meta { margin-top: 22px; } }
</style>
