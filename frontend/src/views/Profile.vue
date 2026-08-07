<script setup lang="ts">
import { reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { useAuthStore } from "../stores/auth";
import { changePassword } from "../api/auth";

const auth = useAuthStore();
const saving = ref(false);
const form = reactive({ old_password: "", new_password: "", confirm_password: "" });
async function save() {
  if (!form.old_password || form.new_password.length < 8) { ElMessage.warning("新密码至少 8 位且必须填写旧密码"); return; }
  if (form.new_password !== form.confirm_password) { ElMessage.warning("两次输入的新密码不一致"); return; }
  saving.value = true;
  try { const response = await changePassword(form.old_password, form.new_password); if (response.data.code !== 0) throw new Error(response.data.msg); ElMessage.success("密码修改成功，请重新登录"); auth.logout(); window.location.href = "/login"; }
  catch (error) { ElMessage.error(error instanceof Error ? error.message : "密码修改失败"); }
  finally { saving.value = false; }
}
</script>
<template>
  <section class="page-stack"><el-page-header content="个人中心" /><el-card shadow="never"><el-descriptions :column="1" border><el-descriptions-item label="账号">{{ auth.user?.username }}</el-descriptions-item><el-descriptions-item label="姓名">{{ auth.user?.display_name }}</el-descriptions-item></el-descriptions><el-divider /><el-form label-width="110px" style="max-width: 520px"><el-form-item label="旧密码"><el-input v-model="form.old_password" type="password" show-password /></el-form-item><el-form-item label="新密码"><el-input v-model="form.new_password" type="password" show-password /></el-form-item><el-form-item label="确认新密码"><el-input v-model="form.confirm_password" type="password" show-password /></el-form-item><el-form-item><el-button type="primary" :loading="saving" @click="save">修改密码</el-button></el-form-item></el-form></el-card></section>
</template>
<style scoped>.page-stack { display: flex; flex-direction: column; gap: 16px; }</style>
