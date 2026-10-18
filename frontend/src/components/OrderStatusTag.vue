<script setup lang="ts">
import { computed, watch } from "vue";

import { isKnownOrderStatus, orderStatusLabel, orderStatusTagType } from "../utils/orderStatus";

const props = defineProps<{ status?: unknown }>();
const warnedStatuses = new Set<string>();

watch(() => props.status, (value) => {
  const key = String(value ?? "");
  if (key && !isKnownOrderStatus(key) && !warnedStatuses.has(key)) {
    warnedStatuses.add(key);
    console.warn(`[ERP] 未知订单状态: ${key}`);
  }
}, { immediate: true });

const display = computed(() => ({
  label: orderStatusLabel(props.status),
  type: orderStatusTagType(props.status),
}));
</script>

<template><el-tag :type="display.type" effect="plain" round>{{ display.label }}</el-tag></template>
