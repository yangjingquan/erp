<script setup lang="ts">
import MasterDataPage from "./MasterDataPage.vue";
const columns = [{ prop: "code", label: "单位编码" }, { prop: "name", label: "单位名称" }, { prop: "precision_scale", label: "精度（小数位）" }, { prop: "status", label: "状态", width: 90 }, { prop: "remark", label: "备注" }];
const fields = [{ prop: "code", label: "单位编码", required: true }, { prop: "name", label: "单位名称", required: true }, { prop: "precision_scale", label: "小数精度", type: "number" as const, defaultValue: 2 }];
</script>
<template><MasterDataPage resource="units" title="计量单位" search-placeholder="检索单位编码、名称..." :columns="columns" :fields="fields" :summary-metrics="[{ label: '单位总数', key: 'total', tone: 'rust' }, { label: '启用单位', key: 'active', tone: 'green' }, { label: '已停用', key: 'inactive', tone: 'amber' }]" /></template>
