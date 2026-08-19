<script setup lang="ts">
defineProps<{
  eyebrow: string;
  title: string;
  description?: string;
}>();
</script>

<template>
  <header class="app-page-header">
    <div class="app-page-header__eyebrow">{{ eyebrow }}</div>
    <h1>{{ title }}</h1>
    <p v-if="description">{{ description }}</p>
  </header>
</template>

<style scoped>
.app-page-header { margin: 2px 0 22px; }
.app-page-header__eyebrow { color: var(--erp-muted-text); font-size: 12px; font-weight: 650; letter-spacing: .12em; line-height: 1.35; }
h1 { margin: 8px 0 0; color: var(--erp-text); font-size: 32px; font-weight: 760; letter-spacing: -.02em; line-height: 1.2; }
p { margin: 9px 0 0; color: var(--erp-muted-text); font-size: 16px; line-height: 1.5; }
@media (max-width: 640px) { h1 { font-size: 26px; } p { font-size: 14px; } }
</style>
