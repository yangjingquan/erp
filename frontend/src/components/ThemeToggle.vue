<script setup lang="ts">
import { useAppStore } from "../stores/app";

const app = useAppStore();
</script>

<template>
  <el-button text @click="app.toggleTheme">{{ app.theme === "light" ? "暗黑主题" : "浅色主题" }}</el-button>
</template>
