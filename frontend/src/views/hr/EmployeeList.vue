<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { createEmployee, listEmployees } from "../../api/hr";

const rows = ref<any[]>([]);
const employeeNo = ref("");
const name = ref("");
const loading = ref(false);

async function load() {
  loading.value = true;
  try { rows.value = (await listEmployees()).data?.data ?? []; }
  catch { ElMessage.error("员工列表加载失败"); }
  finally { loading.value = false; }
}
async function save() {
  try { await createEmployee({ employee_no: employeeNo.value, name: name.value, base_salary: 0, allowance: 0 }); ElMessage.success("员工已保存"); await load(); }
  catch { ElMessage.error("员工保存失败"); }
}
onMounted(load);
</script>

<template>
  <el-card v-loading="loading">
    <template #header>员工</template>
    <el-table :data="rows"><el-table-column prop="employee_no" label="工号"/><el-table-column prop="name" label="姓名"/><el-table-column prop="status" label="状态"/></el-table>
    <el-input v-model="employeeNo" placeholder="工号"/><el-input v-model="name" placeholder="姓名"/><el-button @click="save">保存</el-button>
  </el-card>
</template>
