<script setup lang="ts">
import MasterDataPage from "./MasterDataPage.vue";

const columns = [
  { prop: "code", label: "客户编码", width: 150 },
  { prop: "name", label: "客户名称", width: 180 },
  { prop: "short_name", label: "简称" },
  { prop: "contact_name", label: "联系人" },
  { prop: "contact_phone", label: "联系电话" },
  { prop: "credit_limit", label: "信用额度" },
  { prop: "status", label: "状态", width: 90 },
];

const fields = [
  { prop: "code", label: "客户编码", required: true },
  { prop: "name", label: "客户名称", required: true },
  { prop: "short_name", label: "简称" },
  { prop: "contact_name", label: "联系人" },
  { prop: "contact_phone", label: "联系电话" },
  { prop: "address", label: "地址", type: "textarea" as const },
  { prop: "credit_limit", label: "信用额度", type: "number" as const },
];
</script>

<template>
  <MasterDataPage resource="customers" title="客户档案" :columns="columns" :fields="fields" />
</template>
