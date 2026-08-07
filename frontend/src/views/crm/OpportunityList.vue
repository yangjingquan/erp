<script setup lang="ts">
import { onMounted, ref } from "vue"; import { ElMessage } from "element-plus"; import { listOpportunities, addFollowUp } from "../../api/crm";
const rows=ref<any[]>([]); const loading=ref(false); async function load(){loading.value=true;try{rows.value=(await listOpportunities()).data?.data??[]}catch{ElMessage.error("商机加载失败")}finally{loading.value=false}} async function follow(id:string){try{await addFollowUp(id,{content:"跟进记录",occurred_at:new Date().toISOString()});ElMessage.success("已记录跟进")}catch{ElMessage.error("跟进失败")}} onMounted(load);
</script>
<template><el-card v-loading="loading"><template #header>CRM 商机</template><el-table :data="rows"><el-table-column prop="name" label="商机"/><el-table-column prop="status" label="阶段"/><el-table-column label="操作"><template #default="scope"><el-button @click="follow(scope.row.id)">添加跟进</el-button></template></el-table-column></el-table></el-card></template>
