<script setup lang="ts">
import MasterDataPage from "./MasterDataPage.vue";

const columns = [
  { prop: "code", label: "供应商编码", width: 150 },
  { prop: "name", label: "供应商名称", width: 180 },
  { prop: "short_name", label: "简称" },
  { prop: "contact_name", label: "联系人" },
  { prop: "contact_phone", label: "联系电话" },
  { prop: "credit_days", label: "账期（天）" },
  { prop: "status", label: "状态", width: 90 },
];

const fields = [
  { prop: "code", label: "供应商编码", required: true },
  { prop: "name", label: "供应商名称", required: true },
  { prop: "short_name", label: "简称" },
  { prop: "contact_name", label: "联系人" },
  { prop: "contact_phone", label: "联系电话" },
  { prop: "address", label: "地址", type: "textarea" as const },
  { prop: "credit_days", label: "账期（天）", type: "number" as const },
];
</script>

<template>
  <MasterDataPage resource="suppliers" title="供应商档案" search-placeholder="搜索编码、名称、联系人..." :columns="columns" :fields="fields" :summary-metrics="[{ label: '供应商总数', key: 'total', tone: 'rust' }, { label: '启用供应商', key: 'active', tone: 'green' }, { label: '已停用', key: 'inactive', tone: 'amber' }]" />
</template>
