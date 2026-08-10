<script setup lang="ts">
import { computed, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { closePeriod, reopenPeriod } from "../../api/cost";
import { usePermissionStore } from "../../stores/permission";

const period = ref("");
const actionLoading = ref<"close" | "reopen" | null>(null);
const permissions = usePermissionStore();
const canReopen = computed(() => permissions.hasPermission("cost:period:reopen"));

function validPeriod() {
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(period.value)) {
    ElMessage.warning("操作期间必须为 YYYY-MM，例如 2026-08");
    return false;
  }
  return true;
}

async function close() {
  if (!validPeriod()) return;
  try {
    await ElMessageBox.confirm(`确认关闭 ${period.value} 期间吗？`, "确认结账", { type: "warning" });
    actionLoading.value = "close";
    const response = await closePeriod(period.value);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success("结账成功");
  } catch (error: any) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "结账失败");
  } finally {
    actionLoading.value = null;
  }
}

async function reopen() {
  if (!validPeriod()) return;
  try {
    await ElMessageBox.confirm(`确认重开 ${period.value} 期间吗？重开后可继续录入该期间业务。`, "确认重开", { type: "warning" });
    actionLoading.value = "reopen";
    const response = await reopenPeriod(period.value);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success("会计期间已重开");
  } catch (error: any) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "重开失败");
  } finally {
    actionLoading.value = null;
  }
}
</script>

<template>
  <section class="page-stack">
    <el-page-header content="期间结账" />
    <el-card shadow="never">
      <el-space>
        <el-date-picker v-model="period" type="month" value-format="YYYY-MM" placeholder="选择结账期间" clearable style="width: 180px" />
        <el-button type="primary" :loading="actionLoading === 'close'" :disabled="Boolean(actionLoading)" @click="close">结账</el-button>
        <el-button v-if="canReopen" type="warning" :loading="actionLoading === 'reopen'" :disabled="Boolean(actionLoading)" @click="reopen">重开</el-button>
      </el-space>
      <el-alert class="permission-hint" title="重开会计期间需要 cost:period:reopen 权限。" type="info" :closable="false" />
    </el-card>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.permission-hint { margin-top: 16px; }
</style>
