<script setup lang="ts">
import MasterDataPage from "./MasterDataPage.vue";
const columns = [{ prop: "code", label: "单位编码" }, { prop: "name", label: "单位名称" }, { prop: "precision_scale", label: "精度" }];
const fields = [{ prop: "code", label: "单位编码", required: true }, { prop: "name", label: "单位名称", required: true }, { prop: "precision_scale", label: "小数精度", type: "number" as const, defaultValue: 2 }];
</script>
<template><MasterDataPage resource="units" title="计量单位" :columns="columns" :fields="fields" /></template>
