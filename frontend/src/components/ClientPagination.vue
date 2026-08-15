<script setup lang="ts">
defineProps<{ page: number; pageSize: number; total: number }>();
const emit = defineEmits<{
  "update:page": [value: number];
  "update:pageSize": [value: number];
}>();
</script>

<template>
  <div v-if="total > pageSize" class="client-pagination">
    <span>共 {{ total }} 条</span>
    <el-pagination
      background
      :current-page="page"
      :page-size="pageSize"
      :page-sizes="[10, 20, 50, 100]"
      layout="sizes, prev, pager, next"
      :total="total"
      @current-change="emit('update:page', $event)"
      @size-change="emit('update:pageSize', $event)"
    />
  </div>
</template>

<style scoped>
.client-pagination { display: flex; align-items: center; justify-content: flex-end; gap: 16px; margin-top: 14px; color: var(--erp-muted-text); font-size: 13px; }
</style>
