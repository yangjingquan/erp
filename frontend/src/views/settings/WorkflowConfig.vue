<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import {
  getWorkflowDefinition,
  loadWorkflowConfig,
  saveWorkflowConfig,
  saveWorkflowDefinition,
  type WorkflowNode,
} from "../../api/workflow";

const defaultNodes: WorkflowNode[] = [
  { key: "manager", name: "部门负责人审批", approver: "部门负责人" },
  { key: "finance", name: "财务审批", approver: "财务角色" },
];
const nodes = ref<WorkflowNode[]>([]);
const loading = ref(false);
const saving = ref(false);
const BUSINESS_TYPE = "sales_order";

async function load() {
  loading.value = true;
  try {
    const response = await getWorkflowDefinition(BUSINESS_TYPE);
    if (response.data.code === 0 && response.data.data?.nodes?.length) {
      nodes.value = response.data.data.nodes.map((node: WorkflowNode) => ({ ...node }));
      saveWorkflowConfig(nodes.value);
      return;
    }
  } catch {
    // Fall back to the local cache when the backend is temporarily unavailable.
  } finally {
    loading.value = false;
  }
  nodes.value = loadWorkflowConfig(defaultNodes.map((node) => ({ ...node })));
}

function addNode() {
  nodes.value.push({
    key: `node-${nodes.value.length + 1}`,
    name: "新审批节点",
    approver: "指定角色",
  });
}

function removeNode(index: number) {
  nodes.value.splice(index, 1);
}

async function saveWorkflow() {
  saveWorkflowConfig(nodes.value);
  saving.value = true;
  try {
    const response = await saveWorkflowDefinition(BUSINESS_TYPE, {
      name: "销售订单审批",
      status: "active",
      nodes: nodes.value,
    });
    if (response.data.code !== 0) throw new Error(response.data.msg || "审批流保存失败");
    ElMessage.success("审批流已保存到后端");
  } catch (error) {
    ElMessage.warning(error instanceof Error ? `${error.message}，已保存在当前浏览器` : "后端保存失败，已保存在当前浏览器");
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="page-stack">
    <el-page-header content="审批流配置" />
    <el-alert title="审批节点通过配置保存，单据业务服务不硬编码节点；后端不可用时保留浏览器本地缓存。" type="info" show-icon />
    <el-space class="toolbar">
      <el-button type="primary" @click="addNode">新增节点</el-button>
      <el-button type="success" :loading="saving" @click="saveWorkflow">保存流程</el-button>
      <el-button :loading="loading" @click="load">重新加载</el-button>
    </el-space>
    <el-table :data="nodes" row-key="key" border>
      <el-table-column prop="key" label="节点标识" width="180" />
      <el-table-column prop="name" label="节点名称" min-width="220">
        <template #default="scope"><el-input v-model="scope.row.name" /></template>
      </el-table-column>
      <el-table-column prop="approver" label="审批人来源" min-width="180">
        <template #default="scope">
          <el-select v-model="scope.row.approver" style="width: 100%">
            <el-option label="部门负责人" value="部门负责人" />
            <el-option label="财务角色" value="财务角色" />
            <el-option label="指定用户" value="指定用户" />
            <el-option label="指定角色" value="指定角色" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="scope">
          <el-button link type="danger" @click="removeNode(scope.$index)">删除</el-button>
        </template>
      </el-table-column>
      <template #empty><el-empty description="暂无审批节点" /></template>
    </el-table>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.toolbar { margin: 0; }
</style>
