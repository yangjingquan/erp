<script setup lang="ts">
import MasterDataPage from "./MasterDataPage.vue";
const columns = [{ prop: "code", label: "税率编码" }, { prop: "name", label: "税率名称" }, { prop: "rate", label: "税率" }];
const fields = [{ prop: "code", label: "税率编码", required: true }, { prop: "name", label: "税率名称", required: true }, { prop: "rate", label: "税率(%)", type: "number" as const, defaultValue: 13 }];
</script>
<template><MasterDataPage resource="tax-rates" title="税率档案" :columns="columns" :fields="fields" /></template>
