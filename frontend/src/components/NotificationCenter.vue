<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { Bell } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { useRouter } from "vue-router";

import { listNotifications, markAllNotificationsRead, markNotificationRead } from "../api/documents";
import { formatLocalDateTime } from "../utils/time";

type NotificationRow = Record<string, any>;
const router = useRouter();
const rows = ref<NotificationRow[]>([]);
const unread = ref(0);
const loading = ref(false);
let timer: ReturnType<typeof setInterval> | undefined;

async function load(silent = false) {
  if (!silent) loading.value = true;
  try {
    const response = await listNotifications({ page: 1, page_size: 20 });
    if (response.data.code !== 0) throw new Error(response.data.msg);
    rows.value = response.data.data?.items || [];
    unread.value = Number(response.data.data?.unread || 0);
  } catch (error) {
    if (!silent) ElMessage.error(error instanceof Error ? error.message : "通知加载失败");
  } finally {
    loading.value = false;
  }
}

async function open(row: NotificationRow) {
  if (!row.read_at) await markNotificationRead(String(row.id));
  await load(true);
  if (row.action_url) router.push(String(row.action_url));
}

async function readAll() {
  const response = await markAllNotificationsRead();
  if (response.data.code !== 0) { ElMessage.error(response.data.msg); return; }
  await load(true);
}

onMounted(() => { load(true); timer = setInterval(() => load(true), 60000); });
onUnmounted(() => { if (timer) clearInterval(timer); });
</script>

<template>
  <el-popover placement="bottom-end" :width="360" trigger="click" @show="load(true)">
    <template #reference><el-badge :value="unread" :hidden="!unread" :max="99"><el-button class="notification-trigger" text circle aria-label="通知中心"><el-icon><Bell /></el-icon></el-button></el-badge></template>
    <div class="notification-head"><strong>通知中心</strong><el-button v-if="unread" link type="primary" @click="readAll">全部已读</el-button></div>
    <div v-loading="loading" class="notification-list">
      <button v-for="row in rows" :key="row.id" type="button" :class="['notification-item', { unread: !row.read_at }]" @click="open(row)"><span /><div><strong>{{ row.title }}</strong><p>{{ row.content }}</p><time>{{ formatLocalDateTime(row.created_at) }}</time></div></button>
      <el-empty v-if="!rows.length" :image-size="56" description="暂无通知" />
    </div>
  </el-popover>
</template>

<style scoped>
.notification-trigger { color: var(--erp-muted-text); font-size: 18px; }.notification-head { display: flex; justify-content: space-between; padding: 2px 2px 10px; border-bottom: 1px solid var(--erp-border-soft); }.notification-list { max-height: 420px; overflow: auto; }.notification-item { display: flex; width: 100%; gap: 9px; padding: 12px 2px; border: 0; border-bottom: 1px solid var(--erp-border-soft); background: transparent; color: var(--erp-text); text-align: left; cursor: pointer; }.notification-item:hover { background: var(--erp-panel-soft); }.notification-item > span { flex: 0 0 7px; width: 7px; height: 7px; margin-top: 5px; border-radius: 50%; background: transparent; }.notification-item.unread > span { background: var(--erp-primary); }.notification-item > div { min-width: 0; }.notification-item strong { font-size: 13px; }.notification-item p { margin: 5px 0; color: var(--erp-muted-text); font-size: 12px; line-height: 1.5; }.notification-item time { color: var(--erp-subtle-text); font-size: 11px; }
</style>
