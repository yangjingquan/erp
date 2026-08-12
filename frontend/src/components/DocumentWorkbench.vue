<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { ArrowLeft, Delete, Download, Link, Paperclip, Refresh, Upload } from "@element-plus/icons-vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  addDocumentComment,
  deleteDocumentAttachment,
  downloadDocumentAttachment,
  getDocumentWorkspace,
  runDocumentCommand,
  uploadDocumentAttachment,
} from "../api/documents";
import { formatLocalDateTime } from "../utils/time";
import StatusTag from "./StatusTag.vue";

type Row = Record<string, any>;
const props = defineProps<{ businessType: string; businessId: string }>();
const visible = defineModel<boolean>("visible", { default: false });
const emit = defineEmits<{ changed: []; navigate: [businessType: string, businessId: string] }>();
const loading = ref(false);
const actionLoading = ref("");
const errorMessage = ref("");
const workspace = ref<Row | null>(null);
const comment = ref("");
const currentType = ref("");
const currentId = ref("");
const history = ref<Array<{ type: string; id: string }>>([]);
const fileInput = ref<HTMLInputElement | null>(null);

const document = computed(() => workspace.value?.document || {});
const details = computed(() => workspace.value?.details || {});
const lineItems = computed(() => workspace.value?.display_items || details.value.items || details.value.entries || []);
const detailEntries = computed(() => workspace.value?.display_details || Object.entries(details.value).filter(([key]) => !["items", "entries", "reconciles", "is_deleted", "summary_json"].includes(key)).slice(0, 18).map(([label, value]) => ({ label, value })));

function unwrap(response: any): Row {
  if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "单据工作台接口返回失败");
  return response.data.data;
}

async function load() {
  if (!currentType.value || !currentId.value) return;
  loading.value = true;
  errorMessage.value = "";
  try {
    workspace.value = unwrap(await getDocumentWorkspace(currentType.value, currentId.value));
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "单据详情加载失败";
  } finally {
    loading.value = false;
  }
}

function openRelated(row: Row) {
  const target = row.document;
  if (!target?.business_type || !target?.business_id) return;
  history.value.push({ type: currentType.value, id: currentId.value });
  currentType.value = target.business_type;
  currentId.value = target.business_id;
  load();
}

function goBack() {
  const target = history.value.pop();
  if (!target) return;
  currentType.value = target.type;
  currentId.value = target.id;
  load();
}

async function runAction(action: Row) {
  try {
    await ElMessageBox.confirm(`确认执行“${action.label}”吗？`, "业务操作确认", { type: "warning" });
    actionLoading.value = action.command;
    unwrap(await runDocumentCommand(currentType.value, currentId.value, action.command));
    ElMessage.success(`${action.label}成功`);
    await load();
    emit("changed");
  } catch (error: any) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : `${action.label}失败`);
  } finally {
    actionLoading.value = "";
  }
}

async function submitComment() {
  const content = comment.value.trim();
  if (!content) return;
  try {
    unwrap(await addDocumentComment(currentType.value, currentId.value, content));
    comment.value = "";
    ElMessage.success("评论已发布");
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "评论发布失败");
  }
}

async function upload(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  try {
    unwrap(await uploadDocumentAttachment(currentType.value, currentId.value, file));
    ElMessage.success("附件上传成功");
    await load();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "附件上传失败");
  } finally {
    input.value = "";
  }
}

async function download(row: Row) {
  try {
    const response = await downloadDocumentAttachment(row.id);
    const url = URL.createObjectURL(response.data);
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = row.file_name;
    anchor.click();
    URL.revokeObjectURL(url);
  } catch {
    ElMessage.error("附件下载失败");
  }
}

async function removeAttachment(row: Row) {
  try {
    await ElMessageBox.confirm(`确认删除附件“${row.file_name}”吗？`, "删除附件", { type: "warning" });
    unwrap(await deleteDocumentAttachment(row.id));
    ElMessage.success("附件已删除");
    await load();
  } catch (error: any) {
    if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : "附件删除失败");
  }
}

function valueText(value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function relationLabel(value: string) {
  return ({ fulfills: "履约出库", creates_receivable: "形成应收", settled_by: "收付款核销", posts_to: "生成凭证", posts_inventory: "库存过账", receives: "采购收货", returns: "退货", inspected_by: "质量检验" } as Record<string, string>)[value] || value;
}

watch([visible, () => props.businessType, () => props.businessId], ([isVisible]) => {
  if (!isVisible) return;
  currentType.value = props.businessType;
  currentId.value = props.businessId;
  history.value = [];
  load();
}, { immediate: true });
</script>

<template>
  <el-drawer v-model="visible" size="min(960px, 96vw)" destroy-on-close class="document-drawer">
    <template #header>
      <div class="drawer-heading">
        <el-button v-if="history.length" :icon="ArrowLeft" text circle @click="goBack" />
        <div><small>{{ document.business_type || currentType }}</small><h2>{{ document.title || "单据详情" }}</h2></div>
        <StatusTag :status="document.status" :label="document.status_label" />
      </div>
    </template>
    <div v-loading="loading" class="workbench-body">
      <el-alert v-if="errorMessage" :title="errorMessage" type="error" show-icon><template #default><el-button link type="primary" @click="load">重新加载</el-button></template></el-alert>
      <main v-else-if="workspace" class="workbench-main">
        <el-tabs>
          <el-tab-pane label="业务概览">
            <el-descriptions :column="2" border class="detail-descriptions">
              <el-descriptions-item v-for="item in detailEntries" :key="item.label" :label="item.label">{{ valueText(item.value) }}</el-descriptions-item>
            </el-descriptions>
            <div v-if="lineItems.length" class="section-block"><h3>业务明细</h3><el-table :data="lineItems" stripe><el-table-column v-for="key in Object.keys(lineItems[0] || {}).slice(0, 8)" :key="key" :prop="key" :label="key" min-width="120" show-overflow-tooltip /></el-table></div>
          </el-tab-pane>
          <el-tab-pane :label="`关联单据 (${workspace.relations.length})`">
            <div v-if="workspace.relations.length" class="relation-list">
              <button v-for="relation in workspace.relations" :key="relation.id" type="button" class="relation-card" @click="openRelated(relation)"><el-icon><Link /></el-icon><span><small>{{ relation.direction === 'upstream' ? '来源' : '去向' }} · {{ relationLabel(relation.relation_type) }}</small><strong>{{ relation.document.title || relation.document.doc_no }}</strong><em>{{ relation.document.status_label || relation.document.status }}</em></span></button>
            </div>
            <el-empty v-else description="暂无上下游关联单据" />
          </el-tab-pane>
          <el-tab-pane :label="`附件 (${workspace.attachments.length})`">
            <div class="section-toolbar"><el-button type="primary" :icon="Upload" @click="fileInput?.click()">上传附件</el-button><input ref="fileInput" type="file" hidden @change="upload" /></div>
            <el-table :data="workspace.attachments"><el-table-column prop="file_name" label="文件名" min-width="220" /><el-table-column prop="size_bytes" label="大小（字节）" width="130" /><el-table-column label="上传时间" width="180"><template #default="scope">{{ formatLocalDateTime(scope.row.created_at) }}</template></el-table-column><el-table-column label="操作" width="130"><template #default="scope"><el-button link type="primary" :icon="Download" @click="download(scope.row)">下载</el-button><el-button link type="danger" :icon="Delete" @click="removeAttachment(scope.row)" /></template></el-table-column><template #empty><el-empty description="暂无附件" /></template></el-table>
          </el-tab-pane>
          <el-tab-pane :label="`评论 (${workspace.comments.length})`">
            <div class="comment-editor"><el-input v-model="comment" type="textarea" :rows="3" maxlength="2000" show-word-limit placeholder="补充业务说明或 @ 协同人" /><el-button type="primary" :disabled="!comment.trim()" @click="submitComment">发布评论</el-button></div>
            <div v-if="workspace.comments.length" class="comment-list"><article v-for="item in workspace.comments" :key="item.id"><span>{{ item.author_name.slice(0, 1) }}</span><div><header><strong>{{ item.author_name }}</strong><time>{{ formatLocalDateTime(item.created_at) }}</time></header><p>{{ item.content }}</p></div></article></div><el-empty v-else description="暂无评论" />
          </el-tab-pane>
          <el-tab-pane label="流程时间线">
            <el-timeline v-if="workspace.timeline.length"><el-timeline-item v-for="(item, index) in workspace.timeline" :key="index" :timestamp="formatLocalDateTime(item.time)" placement="top"><strong>{{ item.label }}</strong><p v-if="item.comment">{{ item.comment }}</p></el-timeline-item></el-timeline><el-empty v-else description="暂无流程记录" />
          </el-tab-pane>
        </el-tabs>
      </main>
      <aside v-if="workspace" class="action-rail">
        <div class="rail-card"><small>单据编号</small><strong>{{ document.doc_no }}</strong><small>金额</small><b>¥{{ document.amount }}</b><small>业务对象</small><span>{{ document.party_name || '-' }}</span><small>更新时间</small><span>{{ formatLocalDateTime(document.updated_at) }}</span></div>
        <div class="rail-card"><h3>可执行操作</h3><el-button v-for="action in document.available_actions" :key="action.command" :type="action.type" :loading="actionLoading === action.command" @click="runAction(action)">{{ action.label }}</el-button><el-empty v-if="!document.available_actions?.length" :image-size="48" description="当前无待执行操作" /><el-button :icon="Refresh" @click="load">刷新状态</el-button></div>
      </aside>
    </div>
  </el-drawer>
</template>

<style scoped>
.drawer-heading { display: flex; align-items: center; gap: 10px; color: var(--erp-text); }
.drawer-heading div { flex: 1; }.drawer-heading small { color: var(--erp-muted-text); text-transform: uppercase; }.drawer-heading h2 { margin: 3px 0 0; font-size: 18px; }
.workbench-body { display: grid; grid-template-columns: minmax(0, 1fr) 240px; gap: 18px; min-height: 520px; }
.workbench-main { min-width: 0; }.detail-descriptions :deep(.el-descriptions__label) { width: 120px; color: var(--erp-muted-text); }.detail-descriptions :deep(.el-descriptions__content) { word-break: break-all; }
.section-block { margin-top: 22px; }.section-block h3, .rail-card h3 { margin: 0 0 12px; font-size: 14px; }.section-toolbar { margin-bottom: 12px; }
.action-rail { display: flex; flex-direction: column; gap: 12px; }.rail-card { display: flex; flex-direction: column; gap: 9px; padding: 15px; border: 1px solid var(--erp-border); border-radius: var(--erp-radius); background: var(--erp-panel-soft); }.rail-card small { color: var(--erp-muted-text); }.rail-card b { color: var(--erp-primary-dark); font-size: 20px; }
.relation-list { display: grid; gap: 10px; }.relation-card { display: flex; gap: 12px; align-items: center; padding: 13px; border: 1px solid var(--erp-border); border-radius: 10px; background: var(--erp-panel-soft); color: var(--erp-text); text-align: left; cursor: pointer; }.relation-card:hover { border-color: var(--erp-primary); }.relation-card > span { display: grid; flex: 1; gap: 4px; }.relation-card small { color: var(--erp-muted-text); }.relation-card em { color: var(--erp-primary-dark); font-size: 12px; font-style: normal; }
.comment-editor { display: flex; align-items: flex-end; gap: 10px; }.comment-list { margin-top: 18px; }.comment-list article { display: flex; gap: 10px; padding: 14px 0; border-bottom: 1px solid var(--erp-border-soft); }.comment-list article > span { display: grid; place-items: center; width: 32px; height: 32px; border-radius: 50%; background: var(--erp-amber-bg); color: var(--erp-amber); }.comment-list article > div { flex: 1; }.comment-list header { display: flex; justify-content: space-between; }.comment-list time { color: var(--erp-subtle-text); font-size: 12px; }.comment-list p { margin: 7px 0 0; line-height: 1.6; }
@media (max-width: 760px) { .workbench-body { grid-template-columns: 1fr; }.action-rail { grid-row: 1; }.comment-editor { align-items: stretch; flex-direction: column; } }
</style>
