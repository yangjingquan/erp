<script setup lang="ts">
import { ref } from "vue";
import { ElMessage } from "element-plus";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();
const username = ref("admin");
const password = ref("Admin@123");
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
</script>

<template>
  <main class="login-page">
    <el-card class="login-card" shadow="always">
      <h1>ERP 管理系统</h1>
      <p class="subtitle">私有化企业经营管理平台</p>
      <el-form @submit.prevent="submit">
        <el-form-item>
          <el-input v-model="username" placeholder="用户名" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="password" type="password" show-password placeholder="密码" size="large" />
        </el-form-item>
        <el-button :loading="loading" type="primary" size="large" native-type="submit" class="submit">登录</el-button>
      </el-form>
    </el-card>
  </main>
</template>

<style scoped>
.login-page { min-height: 100vh; display: grid; place-items: center; background: linear-gradient(135deg, #e8f1ff, #f5f7fb); }
.login-card { width: min(410px, calc(100vw - 32px)); }
h1 { margin: 0; color: #1d4ed8; }
.subtitle { color: #64748b; }
.submit { width: 100%; }
</style>
