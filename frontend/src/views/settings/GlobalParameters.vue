<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { listGlobalParameters, updateGlobalParameter, type GlobalParameter } from "../../api/config";
import { useClientPagination } from "../../composables/useClientPagination";

const rows = ref<GlobalParameter[]>([]);
const { pagedRows, page, pageSize, total, updatePageSize } = useClientPagination(rows);
const loading = ref(false);
const savingKey = ref("");
const errorMessage = ref("");

function responseRows(response: any): GlobalParameter[] {
  if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "全局参数接口返回失败");
  const data = response.data.data;
  return Array.isArray(data) ? data : [];
}

function isBoolean(row: GlobalParameter) {
  return row.value_type === "boolean";
}

function isTrue(row: GlobalParameter) {
  return ["true", "1", "是", "yes"].includes(String(row.parameter_value).toLowerCase());
}

function setBoolean(row: GlobalParameter, value: boolean | string | number) {
  row.parameter_value = value === true || value === "true" || value === 1 ? "true" : "false";
}

async function load() {
  loading.value = true;
  errorMessage.value = "";
  try {
    rows.value = responseRows(await listGlobalParameters());
  } catch (error) {
    rows.value = [];
    errorMessage.value = error instanceof Error ? error.message : "全局参数加载失败，请稍后重试";
    ElMessage.error(errorMessage.value);
  } finally {
    loading.value = false;
  }
}

async function saveRow(row: GlobalParameter) {
  savingKey.value = row.parameter_key;
  try {
    const response = await updateGlobalParameter(row.parameter_key, {
      parameter_value: String(row.parameter_value ?? ""),
      value_type: row.value_type || "string",
      description: row.description,
    });
    if (response.data.code !== 0) throw new Error(response.data.msg || "保存失败");
    ElMessage.success(`参数“${row.parameter_key}”已保存`);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "参数保存失败");
  } finally {
    savingKey.value = "";
  }
}

onMounted(load);
</script>

<template>
  <section class="page-stack">
    <el-page-header content="全局参数" />
    <el-alert title="参数修改会直接影响业务流程，请确认后保存。" type="info" show-icon />
    <el-space class="toolbar">
      <el-button :loading="loading" @click="load">刷新</el-button>
    </el-space>
    <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon closable @close="errorMessage = ''" />
    <el-table v-loading="loading" :data="pagedRows" border>
      <el-table-column prop="parameter_key" label="参数键" min-width="220" />
      <el-table-column label="参数名称" min-width="220">
        <template #default="scope">{{ scope.row.description || scope.row.parameter_key }}</template>
      </el-table-column>
      <el-table-column label="参数值" min-width="220">
        <template #default="scope">
          <el-switch
            v-if="isBoolean(scope.row)"
            :model-value="isTrue(scope.row)"
            active-text="是"
            inactive-text="否"
            @change="setBoolean(scope.row, $event)"
          />
          <el-input v-else v-model="scope.row.parameter_value" clearable />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="scope">
          <el-button type="primary" link :loading="savingKey === scope.row.parameter_key" @click="saveRow(scope.row)">保存</el-button>
        </template>
      </el-table-column>
      <template #empty><el-empty description="暂无全局参数" /></template>
    </el-table>
    <ClientPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @update:page-size="updatePageSize" />
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.toolbar { margin: 0; }
</style>
