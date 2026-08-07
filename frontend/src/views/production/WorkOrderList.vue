<script setup lang="ts">
import { onMounted, ref } from "vue";
import { listWorkOrders } from "../../api/production";

const rows = ref<any[]>([]);
onMounted(async () => {
  const response = await listWorkOrders();
  rows.value = response.data?.data ?? [];
});
</script>

<template>
  <el-card>
    <template #header>工单</template>
    <el-table :data="rows">
      <el-table-column prop="doc_no" label="工单" />
      <el-table-column prop="status" label="状态" />
    </el-table>
  </el-card>
</template>
