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
const username = ref("admin");
const password = ref("Admin@123");
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
      <span class="decor-ring decor-ring-top" aria-hidden="true" />
      <span class="decor-ring decor-ring-bottom" aria-hidden="true" />
      <div class="story-inner">
        <div class="story-brand"><span class="brand-mark">ERP</span><strong>ERP 管理系统</strong></div>
        <div class="story-copy">
          <div class="story-eyebrow">PRIVATE OPERATIONS PLATFORM</div>
          <h1>把经营数据，变成每天<br />可执行的动作。</h1>
          <p>统一主数据、订单、库存与财务流程，让团队从一张清晰的经营视图开始今天的工作。</p>
        </div>
        <div class="feature-grid">
          <article class="feature-card"><el-icon><Collection /></el-icon><strong>统一主数据</strong><p>物料、客户、供应商与仓库信息保持一致。</p></article>
          <article class="feature-card"><el-icon><Operation /></el-icon><strong>协同业务流程</strong><p>从销售订单到出库，节点清晰可追踪。</p></article>
          <article class="feature-card"><el-icon><CircleCheck /></el-icon><strong>安全可控</strong><p>私有化部署、权限隔离与全链路审计。</p></article>
        </div>
        <div class="story-footer">© 2026 ERP 管理系统 · 企业经营管理平台</div>
      </div>
    </section>

    <section class="login-panel">
      <div class="login-box">
        <div class="welcome-eyebrow">WELCOME BACK / SIGN IN</div>
        <h2>欢迎回来</h2>
        <p class="welcome-copy">登录你的企业工作台，继续处理今天的经营任务。</p>
        <div class="login-tabs" role="tablist" aria-label="账号操作"><button class="login-tab" :class="{ 'is-active': mode === 'login' }" type="button" role="tab" :aria-selected="mode === 'login'" @click="switchMode('login')">账号登录</button><button class="login-tab" :class="{ 'is-active': mode === 'register' }" type="button" role="tab" :aria-selected="mode === 'register'" @click="switchMode('register')">注册账号</button></div>
        <el-form v-if="mode === 'login'" class="login-form" label-position="left" label-width="44px" @submit.prevent="submit">
          <el-form-item label="账号"><el-input v-model="username" placeholder="请输入账号" size="large" autocomplete="username"><template #prefix><el-icon><User /></el-icon></template></el-input></el-form-item>
          <el-form-item label="密码"><el-input v-model="password" type="password" show-password placeholder="请输入密码" size="large" autocomplete="current-password"><template #prefix><el-icon><Lock /></el-icon></template></el-input></el-form-item>
          <div class="form-helper"><span class="remember-note"><span class="checkbox-mark" aria-hidden="true" />记住本次登录</span><button class="forgot-link" type="button" @click="ElMessage.info('请联系系统管理员重置密码')">忘记密码?</button></div>
          <el-button :loading="loading" type="primary" size="large" native-type="submit" class="submit"><span>登录工作台</span><el-icon><ArrowRight /></el-icon></el-button>
        </el-form>
        <el-form v-else class="login-form" label-position="left" label-width="58px" @submit.prevent="submitRegister">
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
.login-page { min-height: 100dvh; display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(430px, .95fr); background: var(--erp-page-bg); overflow: hidden; }
.login-story { position: relative; min-height: 100dvh; overflow: hidden; background: #292726; color: #f5ede6; }
.story-inner { position: relative; z-index: 1; display: flex; flex-direction: column; min-height: 100dvh; padding: 45px clamp(42px, 7vw, 144px) 28px; }
.story-brand { display: flex; align-items: center; gap: 10px; color: #fff; font-size: 16px; }
.story-brand strong { font-weight: 700; letter-spacing: .01em; }
.brand-mark { display: grid; place-items: center; width: 35px; height: 35px; border-radius: 11px; background: var(--erp-primary); color: #fff; font-size: 10px; font-weight: 700; }
.story-copy { margin: auto 0 54px; max-width: 600px; }
.story-eyebrow, .welcome-eyebrow { color: #bc8874; font-size: 11px; font-weight: 700; letter-spacing: .16em; }
.story-copy h1 { margin: 16px 0 18px; color: #fffaf5; font-size: clamp(40px, 4.1vw, 62px); font-weight: 760; line-height: 1.13; letter-spacing: -.045em; }
.story-copy p { max-width: 560px; margin: 0; color: #b8aea7; font-size: 15px; line-height: 1.8; }
.feature-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; max-width: 600px; }
.feature-card { min-height: 102px; padding: 15px 13px; border: 1px solid rgba(255,255,255,.13); border-radius: 10px; background: rgba(255,255,255,.025); }
.feature-card .el-icon { margin-bottom: 11px; color: #d08a6b; font-size: 17px; }
.feature-card strong { display: block; color: #f4eae2; font-size: 13px; }
.feature-card p { margin: 7px 0 0; color: #a99d94; font-size: 11px; line-height: 1.55; }
.story-footer { margin-top: auto; color: #8f837b; font-size: 11px; }
.decor-ring { position: absolute; display: block; border: 1px solid rgba(198,109,75,.16); border-radius: 50%; pointer-events: none; }
.decor-ring-top { width: 430px; height: 430px; top: -190px; right: -90px; }.decor-ring-bottom { width: 300px; height: 300px; bottom: -160px; left: -170px; }
.login-panel { display: grid; place-items: center; min-height: 100dvh; padding: 48px clamp(32px, 8vw, 150px); background: #fffaf4; }
.login-box { width: min(100%, 410px); }
.welcome-eyebrow { color: #b5a79b; }
.login-box h2 { margin: 13px 0 8px; color: #3b342f; font-size: 31px; line-height: 1.2; letter-spacing: -.035em; }
.welcome-copy { margin: 0 0 27px; color: #a49a90; font-size: 13px; line-height: 1.6; }
.login-tabs { display: flex; gap: 21px; height: 37px; border-bottom: 1px solid #e7ddd2; }
.login-tab { position: relative; padding: 0 0 12px; border: 0; background: transparent; color: #a49a90; font-size: 13px; cursor: default; }
.login-tab.is-active { color: var(--erp-primary-dark); font-weight: 700; }.login-tab.is-active::after { position: absolute; right: 0; bottom: -1px; left: 0; height: 2px; border-radius: 2px; background: var(--erp-primary); content: ""; }
.login-form { margin-top: 20px; }.login-form :deep(.el-form-item) { align-items: center; margin-bottom: 16px; }.login-form :deep(.el-form-item__label) { display: flex; align-items: center; height: 41px; margin-bottom: 0; color: #776b62; font-size: 12px; font-weight: 600; line-height: 1; }.login-form :deep(.el-form-item__content) { min-width: 0; }.login-form :deep(.el-input__wrapper) { min-height: 41px; border-radius: 9px; background: #fffdf9; box-shadow: 0 0 0 1px #e4d9ce inset; }.login-form :deep(.el-input__wrapper.is-focus) { box-shadow: 0 0 0 1px var(--erp-primary) inset, 0 0 0 3px rgba(198,109,75,.1); }.login-form :deep(.el-input__inner) { color: #4a4039; font-size: 13px; }.login-form :deep(.el-input__inner::placeholder) { color: #b9ada2; }.login-form :deep(.el-input__prefix) { color: #b1a59b; }.login-form :deep(.el-input__suffix) { color: #b1a59b; }
.form-helper { display: flex; align-items: center; justify-content: space-between; margin: -1px 0 19px 44px; color: #a59a90; font-size: 11px; }.remember-note { display: inline-flex; align-items: center; gap: 6px; }.checkbox-mark { display: inline-block; width: 14px; height: 14px; border: 1px solid #ded3c8; border-radius: 4px; background: #fffdf9; }.forgot-link, .support-row button { padding: 0; border: 0; background: transparent; color: var(--erp-primary-dark); cursor: pointer; font-size: 11px; }
.submit { display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; min-height: 41px; border: 0; border-radius: 9px; background: var(--erp-primary); box-shadow: 0 8px 16px rgba(198,109,75,.2); font-size: 13px; font-weight: 700; }.submit:hover { background: #b95f42; }
.security-note { display: flex; align-items: flex-start; gap: 7px; margin-top: 18px; padding: 13px 12px; border-radius: 9px; background: #f8eed4; color: #a8874c; font-size: 11px; line-height: 1.5; }.security-note .el-icon { flex: 0 0 auto; margin-top: 1px; }
.support-row { display: flex; align-items: center; justify-content: space-between; margin-top: 22px; padding-top: 16px; border-top: 1px solid #eee5dc; }.support-row div { display: flex; flex-direction: column; gap: 4px; }.support-row strong { color: #756961; font-size: 11px; }.support-row span { color: #aaa097; font-size: 11px; }.support-row button { display: inline-flex; align-items: center; gap: 5px; }.login-meta { margin-top: 30px; color: #b8ada4; font-size: 10px; text-align: center; }
@media (max-width: 920px) { .login-page { grid-template-columns: minmax(0, 1fr) minmax(390px, .85fr); }.story-inner { padding-inline: 56px; }.story-copy h1 { font-size: 40px; } }
@media (max-width: 1400px) and (min-width: 721px) { .story-inner { padding-inline: 56px; } }
@media (max-width: 720px) { .login-page { display: block; }.login-story { display: none; }.login-panel { min-height: 100dvh; padding: 32px 22px; }.login-box { width: min(100%, 410px); }.login-box h2 { font-size: 26px; } }
</style>
