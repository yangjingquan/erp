<script setup lang="ts">
import { ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import { closePeriod } from "../../api/cost";

const period = ref("");

async function close() {
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(period.value)) {
    ElMessage.warning("结账期间必须为 YYYY-MM，例如 2026-08");
    return;
  }
  try {
    await ElMessageBox.confirm(`确认关闭 ${period.value} 期间吗？`, "确认结账", { type: "warning" });
    const response = await closePeriod(period.value);
    if (response.data.code !== 0) throw new Error(response.data.msg);
    ElMessage.success("结账成功");
  } catch (error: any) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "结账失败");
  }
}
</script>

<template>
  <section class="page-stack">
    <el-page-header content="期间结账" />
    <el-card shadow="never">
      <el-space>
        <el-input v-model="period" placeholder="YYYY-MM" clearable style="width: 180px" />
        <el-button type="primary" @click="close">结账</el-button>
      </el-space>
    </el-card>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
</style>
