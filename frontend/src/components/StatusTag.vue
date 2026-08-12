<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ status?: string; label?: string }>();
const statusMap: Record<string, { label: string; type: "primary" | "success" | "warning" | "danger" | "info" }> = {
  draft: { label: "草稿", type: "info" },
  submitted: { label: "待审核", type: "warning" },
  approved: { label: "已审核", type: "success" },
  completed: { label: "已完成", type: "success" },
  open: { label: "待核销", type: "warning" },
  partial: { label: "部分核销", type: "primary" },
  settled: { label: "已结清", type: "success" },
  confirmed: { label: "已确认", type: "primary" },
  posted: { label: "已过账", type: "success" },
  rejected: { label: "已驳回", type: "danger" },
  cancelled: { label: "已取消", type: "info" },
};
const display = computed(() => statusMap[props.status || ""] || { label: props.label || props.status || "-", type: "info" as const });
</script>

<template><el-tag :type="display.type" effect="light" round>{{ label || display.label }}</el-tag></template>
