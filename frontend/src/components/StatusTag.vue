<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ status?: string; label?: string }>();
const statusMap: Record<string, { label: string; type: "primary" | "success" | "warning" | "danger" | "info" }> = {
  draft: { label: "草稿", type: "info" },
  submitted: { label: "待审核", type: "warning" }, pending_review: { label: "待审核", type: "warning" },
  approved: { label: "已审核", type: "success" },
  completed: { label: "已完成", type: "success" },
  open: { label: "待处理", type: "warning" },
  partial: { label: "部分核销", type: "primary" },
  settled: { label: "已结清", type: "success" },
  confirmed: { label: "已确认", type: "primary" },
  posted: { label: "已过账", type: "success" },
  rejected: { label: "已驳回", type: "danger" },
  cancelled: { label: "已取消", type: "info" },
  closed: { label: "已关闭", type: "info" }, reopened: { label: "已重开", type: "warning" },
  active: { label: "启用", type: "success" }, inactive: { label: "停用", type: "info" },
  pending: { label: "待处理", type: "warning" }, in_progress: { label: "进行中", type: "warning" },
  released: { label: "已发布", type: "success" }, effective: { label: "已生效", type: "success" },
  obsolete: { label: "已作废", type: "danger" }, disabled: { label: "已停用", type: "info" },
  new: { label: "新建", type: "info" },
  contacted: { label: "已联系", type: "primary" }, qualified: { label: "已合格", type: "success" },
  converted: { label: "已转化", type: "success" }, lost: { label: "已丢失", type: "danger" },
  won: { label: "赢单", type: "success" }, proposal: { label: "商谈中", type: "warning" },
  ready: { label: "待执行", type: "info" }, assigned: { label: "已分配", type: "primary" },
  resolved: { label: "已解决", type: "success" }, quoted: { label: "已报价", type: "primary" },
  accepted: { label: "已接受", type: "success" }, issued: { label: "已开具", type: "success" },
  red_issued: { label: "已红冲", type: "danger" }, voided: { label: "已作废", type: "danger" },
  partially_received: { label: "部分入库", type: "warning" }, partially_delivered: { label: "部分出库", type: "warning" },
  maintenance: { label: "保养中", type: "warning" }, retired: { label: "已报废", type: "info" },
  reserved: { label: "预留中", type: "primary" }, released_reservation: { label: "已释放", type: "info" },
  ignored: { label: "已忽略", type: "info" }, passed: { label: "已通过", type: "success" },
  failed: { label: "未通过", type: "danger" }, planned: { label: "已计划", type: "primary" },
  dispatched: { label: "已发运", type: "primary" }, in_transit: { label: "运输中", type: "warning" },
  delivered: { label: "已签收", type: "success" }, matched: { label: "已匹配", type: "success" },
  difference: { label: "存在差异", type: "warning" }, suggested: { label: "待确认", type: "warning" },
  unmatched: { label: "未匹配", type: "info" }, processing: { label: "处理中", type: "warning" },
  dead_letter: { label: "进入死信队列", type: "danger" },
  published: { label: "已发布", type: "success" }, calculated: { label: "已计算", type: "primary" },
  paid: { label: "已支付", type: "success" }, interview: { label: "面试中", type: "warning" },
  hired: { label: "已录用", type: "success" }, root_cause: { label: "原因分析", type: "warning" },
  containment: { label: "临时遏制", type: "warning" }, retest: { label: "待复验", type: "primary" },
  investigating: { label: "调查中", type: "warning" },
  in_workflow: { label: "审批中", type: "warning" }, exception: { label: "异常", type: "danger" },
};
const display = computed(() => ({
  label: props.label || statusMap[props.status || ""]?.label || (props.status ? "其他状态" : "-"),
  type: statusMap[props.status || ""]?.type || "info" as const,
}));
</script>

<template><el-tag :type="display.type" effect="plain" round>{{ display.label }}</el-tag></template>
