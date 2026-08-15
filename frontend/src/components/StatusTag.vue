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
  active: { label: "启用", type: "success" }, inactive: { label: "停用", type: "info" },
  pending: { label: "待处理", type: "warning" }, in_progress: { label: "进行中", type: "warning" },
  released: { label: "已发布", type: "success" }, effective: { label: "已生效", type: "success" },
  obsolete: { label: "已作废", type: "danger" }, new: { label: "新建", type: "info" },
  contacted: { label: "已联系", type: "primary" }, qualified: { label: "已合格", type: "success" },
  converted: { label: "已转化", type: "success" }, lost: { label: "已丢失", type: "danger" },
  won: { label: "赢单", type: "success" }, proposal: { label: "商谈中", type: "warning" },
  ready: { label: "待执行", type: "info" }, assigned: { label: "已分配", type: "primary" },
  resolved: { label: "已解决", type: "success" }, quoted: { label: "已报价", type: "primary" },
  accepted: { label: "已接受", type: "success" }, issued: { label: "已开具", type: "success" },
  red_issued: { label: "已红冲", type: "danger" }, voided: { label: "已作废", type: "danger" },
};
const display = computed(() => statusMap[props.status || ""] || { label: props.label || props.status || "-", type: "info" as const });
</script>

<template><el-tag :type="display.type" effect="light" round>{{ display.label }}</el-tag></template>
