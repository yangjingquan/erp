<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { approveWorkflowTask, listMyWorkflowTasks, rejectWorkflowTask } from "../../api/workflow";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const loading = ref(false);
const actionLoading = ref<string | null>(null);

function unwrap(response: any): any {
  if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "审批任务接口返回失败");
  return response.data.data;
}

async function load() {
  loading.value = true;
  try {
    rows.value = unwrap(await listMyWorkflowTasks()) || [];
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "我的待办加载失败");
  } finally {
    loading.value = false;
  }
}

async function approve(row: Row) {
  try {
    const result = await ElMessageBox.prompt("请输入审批意见（可留空）", "审批通过", { inputValue: "" });
    actionLoading.value = String(row.task_id);
    unwrap(await approveWorkflowTask(String(row.task_id), result.value || ""));
    ElMessage.success("已通过审批");
    await load();
  } catch (error: any) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "审批失败");
  } finally {
    actionLoading.value = null;
  }
}

async function reject(row: Row) {
  try {
    const result = await ElMessageBox.prompt("请输入驳回原因", "驳回", { inputValue: "" });
    actionLoading.value = String(row.task_id);
    unwrap(await rejectWorkflowTask(String(row.task_id), result.value || ""));
    ElMessage.success("已驳回，单据退回草稿");
    await load();
  } catch (error: any) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "驳回失败");
  } finally {
    actionLoading.value = null;
  }
}

onMounted(load);
</script>

<template>
  <section class="page-stack">
    <header class="page-heading">
      <div>
        <small>WORKFLOW / MY TASKS</small>
        <h1>我的待办</h1>
        <p>审批流中指派给我的待审批任务。通过或驳回将同步驱动单据状态。</p>
      </div>
      <el-button :loading="loading" @click="load">刷新</el-button>
    </header>
    <el-card shadow="never">
      <el-table v-loading="loading" :data="rows" stripe>
        <el-table-column prop="document_label" label="单据" min-width="220" />
        <el-table-column prop="business_type" label="业务类型" width="140" />
        <el-table-column prop="node_name" label="审批节点" min-width="160" />
        <el-table-column prop="created_at" label="到达时间" width="180" />
        <el-table-column label="操作" width="180">
          <template #default="scope">
            <el-button link type="success" :loading="actionLoading === String(scope.row.task_id)" @click="approve(scope.row)">通过</el-button>
            <el-button link type="danger" :loading="actionLoading === String(scope.row.task_id)" @click="reject(scope.row)">驳回</el-button>
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无待办审批任务" /></template>
      </el-table>
    </el-card>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.page-heading { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; }
.page-heading small { color: var(--erp-muted-text); letter-spacing: .08em; }
.page-heading h1 { margin: 4px 0; }
.page-heading p { margin: 0; color: var(--erp-muted-text); }
</style>
