<script setup lang="ts">
import MasterDataPage from "./MasterDataPage.vue";

const columns = [
  { prop: "code", label: "物料编码", width: 150 },
  { prop: "name", label: "物料名称", width: 180 },
  { prop: "category", label: "分类" },
  { prop: "material_type", label: "类型" },
  { prop: "sale_price", label: "销售价" },
  { prop: "purchase_price", label: "采购价" },
  { prop: "min_stock", label: "安全库存" },
  { prop: "status", label: "状态", width: 90 },
];

const fields = [
  { prop: "code", label: "物料编码", required: true },
  { prop: "name", label: "物料名称", required: true },
  { prop: "category", label: "分类" },
  {
    prop: "material_type",
    label: "物料类型",
    type: "select" as const,
    defaultValue: "goods",
    options: [
      { label: "商品", value: "goods" },
      { label: "原材料", value: "raw_material" },
      { label: "半成品", value: "semi_finished" },
      { label: "成品", value: "finished" },
    ],
  },
  { prop: "standard_cost", label: "标准成本", type: "number" as const },
  { prop: "sale_price", label: "销售价", type: "number" as const },
  { prop: "purchase_price", label: "采购价", type: "number" as const },
  { prop: "min_stock", label: "最低库存", type: "number" as const },
  { prop: "max_stock", label: "最高库存", type: "number" as const },
  { prop: "specification", label: "规格说明", type: "textarea" as const },
];
</script>

<template>
  <MasterDataPage resource="materials" title="物料档案" :columns="columns" :fields="fields" />
</template>
