<script setup lang="ts">
import MasterDataPage from "./MasterDataPage.vue";
const columns = [{ prop: "code", label: "税率编码" }, { prop: "name", label: "税率名称" }, { prop: "rate", label: "税率（%）" }, { prop: "status", label: "状态", width: 90 }];
const fields = [{ prop: "code", label: "税率编码", required: true }, { prop: "name", label: "税率名称", required: true }, { prop: "rate", label: "税率(%)", type: "number" as const, defaultValue: 13 }];
</script>
<template><MasterDataPage resource="tax-rates" title="税率档案" search-placeholder="输入税率编码或名称..." :columns="columns" :fields="fields" :summary-metrics="[{ label: '税率档案', key: 'total', tone: 'rust' }, { label: '启用税率', key: 'active', tone: 'green' }, { label: '已停用', key: 'inactive', tone: 'amber' }]" /></template>
