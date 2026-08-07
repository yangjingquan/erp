<script setup lang="ts">
import { computed } from "vue";
import { usePermissionStore } from "../stores/permission";

const props = defineProps<{ permission: string }>();
const permissions = usePermissionStore();
const allowed = computed(() => permissions.hasPermission(props.permission));
</script>

<template>
  <el-button v-if="allowed"><slot /></el-button>
</template>
