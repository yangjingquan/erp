<script setup lang="ts">
import MasterDataPage from "./MasterDataPage.vue";

const columns = [
  { prop: "code", label: "仓库编码", width: 150 },
  { prop: "name", label: "仓库名称", width: 180 },
  { prop: "address", label: "地址" },
  { prop: "status", label: "状态", width: 90 },
];

const fields = [
  { prop: "code", label: "仓库编码", required: true },
  { prop: "name", label: "仓库名称", required: true },
  { prop: "address", label: "地址", type: "textarea" as const },
];
</script>

<template>
  <MasterDataPage resource="warehouses" title="仓库档案" search-placeholder="搜索仓库编码、名称、地址..." :columns="columns" :fields="fields" :summary-metrics="[{ label: '仓库总数', key: 'total', tone: 'rust' }, { label: '启用中', key: 'active', tone: 'green' }, { label: '已停用', key: 'inactive', tone: 'amber' }]" />
</template>
