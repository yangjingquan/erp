<script setup lang="ts">
import { ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { createBackup, restoreBackup, validateRestore } from "../../api/backup";

const REQUIRED_CONFIRMATION = "RESTORE ERP";
const backupPath = ref("");
const confirmationWord = ref("");
const backupResult = ref("");
const backingUp = ref(false);
const restoring = ref(false);

function responseData(response: any) {
  if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "接口返回失败");
  return response.data.data || {};
}

async function backup() {
  backingUp.value = true;
  try {
    const result = responseData(await createBackup());
    backupPath.value = String(result.path || "");
    backupResult.value = backupPath.value ? `备份完成：${backupPath.value}` : "数据库备份已完成";
    ElMessage.success(backupResult.value);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "数据库备份失败");
  } finally {
    backingUp.value = false;
  }
}

async function restore() {
  const path = backupPath.value.trim();
  const word = confirmationWord.value.trim();
  if (!path) {
    ElMessage.warning("请输入备份文件路径");
    return;
  }
  if (word !== REQUIRED_CONFIRMATION) {
    ElMessage.warning(`请输入确认词 ${REQUIRED_CONFIRMATION}`);
    return;
  }

  try {
    await ElMessageBox.confirm(
      `即将使用“${path}”覆盖当前数据库。此操作不可逆，确认继续吗？`,
      "高危操作二次确认",
      { type: "warning", confirmButtonText: "确认恢复", cancelButtonText: "取消" },
    );
    restoring.value = true;
    await validateRestore(path, word);
    responseData(await restoreBackup(path, word));
    ElMessage.success("数据库恢复完成");
  } catch (error) {
    if (error === "cancel" || error === "close") return;
    ElMessage.error(error instanceof Error ? error.message : "数据库恢复失败");
  } finally {
    restoring.value = false;
  }
}
</script>

<template>
  <section class="page-stack">
    <el-page-header content="备份与恢复" />
    <el-alert title="恢复数据库前请确认备份文件和目标环境，操作不可逆。" type="warning" show-icon />
    <el-card shadow="never">
      <el-form label-width="150px" @submit.prevent="restore">
        <el-form-item label="备份文件路径" required>
          <el-input v-model="backupPath" placeholder="例如：var/backups/erp-admin.sql" clearable />
        </el-form-item>
        <el-form-item label="恢复确认词" required>
          <el-input v-model="confirmationWord" :placeholder="`请输入 ${REQUIRED_CONFIRMATION}`" clearable />
        </el-form-item>
        <el-form-item>
          <span class="hint">必须输入确认词 {{ REQUIRED_CONFIRMATION }}，并通过二次确认弹窗。</span>
        </el-form-item>
      </el-form>
      <el-alert v-if="backupResult" :title="backupResult" type="success" show-icon />
      <el-space class="toolbar">
        <el-button type="primary" :loading="backingUp" @click="backup">立即备份</el-button>
        <el-button type="danger" :loading="restoring" @click="restore">恢复备份</el-button>
      </el-space>
    </el-card>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.toolbar { margin-top: 18px; }
.hint { color: var(--erp-muted-text); }
</style>
