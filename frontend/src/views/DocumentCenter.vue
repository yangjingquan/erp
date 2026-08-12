<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import DocumentWorkbench from "../components/DocumentWorkbench.vue";

const route = useRoute();
const router = useRouter();
const visible = ref(true);
function closed(value: boolean) {
  if (!value) window.history.length > 1 ? router.back() : router.replace("/dashboard");
}
</script>

<template><section><DocumentWorkbench :visible="visible" :business-type="String(route.params.businessType)" :business-id="String(route.params.businessId)" @update:visible="closed" /></section></template>
