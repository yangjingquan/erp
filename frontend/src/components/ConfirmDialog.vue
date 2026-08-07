<script setup lang="ts">
import { ref } from "vue";

defineProps<{ title?: string; content?: string }>();
const emit = defineEmits<{ confirm: [] }>();
const visible = ref(false);

function open() { visible.value = true; }
function confirm() { visible.value = false; emit("confirm"); }
defineExpose({ open });
</script>

<template>
  <el-dialog v-model="visible" :title="title || '请确认操作'" width="380px">
    <p>{{ content || "该操作可能影响业务数据，是否继续？" }}</p>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="danger" @click="confirm">确认</el-button>
    </template>
  </el-dialog>
</template>
