<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import {
  Box,
  Collection,
  DataAnalysis,
  Document,
  Menu,
  QuestionFilled,
  Setting,
  ShoppingCart,
  Sunny,
  UserFilled,
  Wallet,
} from "@element-plus/icons-vue";

import { useAppStore } from "../stores/app";
import { useAuthStore } from "../stores/auth";
import { globalSearch } from "../api/search";

const app = useAppStore();
const auth = useAuthStore();
const route = useRoute();
const router = useRouter();
const searchKeyword = ref("");
const searchResults = ref<Array<Record<string, any>>>([]);
const activeMenu = computed(() => route.path);
const openMenuKeys = computed(() => {
  const group = route.path.split("/")[1] === "settings" ? "system" : route.path.split("/")[1];
  return ["master-data", "sales", "purchase", "inventory", "finance", "crm", "system"].includes(group) ? [group] : [];
});
const pageTitles: Record<string, string> = {
  "/dashboard": "经营看板", "/master-data/materials": "物料档案", "/master-data/customers": "客户档案", "/master-data/suppliers": "供应商档案", "/master-data/warehouses": "仓库档案", "/master-data/units": "计量单位", "/master-data/tax-rates": "税率档案",
  "/sales/quotes": "销售报价", "/sales/orders": "销售订单", "/sales/returns": "销售退货", "/purchase/requests": "采购申请", "/purchase/orders": "采购订单", "/purchase/returns": "采购退货",
  "/inventory/stock": "库存台账", "/inventory/transactions": "库存流水", "/inventory/transfers": "库存调拨", "/inventory/counts": "库存盘点", "/inventory/scan": "移动扫码",
  "/finance/receivables": "应收账款", "/finance/payables": "应付账款", "/finance/expenses": "费用报销", "/finance/vouchers": "会计凭证", "/crm/leads": "线索管理", "/crm/opportunities": "商机管理",
  "/production/boms": "BOM", "/production/mrp": "MRP", "/production/work-orders": "生产工单", "/quality/inspections": "质量检验", "/hr/employees": "员工管理", "/hr/payroll": "薪资核算", "/cost/allocations": "成本分摊", "/cost/period-close": "期间结账", "/settings/api-clients": "API 客户端", "/settings/parameters": "全局参数", "/settings/workflow": "审批流程", "/settings/print-templates": "打印模板", "/system/operation-logs": "操作日志", "/system/admin": "权限与基础管理", "/system/backup": "备份恢复", "/profile": "个人中心",
};

function navigationTitle(path: string) { return pageTitles[path] || "导航页面"; }
function activateMenu(path: string) { app.activateNavigation(path, navigationTitle(path)); }
function closeNavigation() { app.closeNavigation(); void router.push("/dashboard"); }

watch(() => route.path, (path) => {
  if (path !== "/login" && (!app.openedNavigation || app.openedNavigation.path !== path)) activateMenu(path);
}, { immediate: true });

function logout() {
  auth.logout();
  router.push("/login");
}

async function search() {
  const keyword = searchKeyword.value.trim();
  if (!keyword) { searchResults.value = []; return; }
  try {
    const response = await globalSearch(keyword);
    if (response.data.code !== 0) throw new Error(response.data.msg || "检索失败");
    searchResults.value = Array.isArray(response.data.data) ? response.data.data : [];
    if (!searchResults.value.length) ElMessage.info("未找到匹配业务数据");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "全局检索失败");
  }
}

function resultLabel(result: Record<string, any>) {
  return result.name || result.code || result.doc_no || result.id;
}

function selectResult(result: Record<string, any>) {
  const paths: Record<string, string> = {
    material: "/master-data/materials",
    customer: "/master-data/customers",
    supplier: "/master-data/suppliers",
    sales_order: "/sales/orders",
    purchase_order: "/purchase/orders",
  };
  const path = paths[result.resource];
  if (path) router.push(path);
}

async function fetchSearchSuggestions(_query: string, callback: (results: Array<Record<string, any>>) => void) {
  await search();
  callback(searchResults.value.map((item) => ({ ...item, value: resultLabel(item) })));
}
</script>

<template>
  <el-container class="admin-layout">
    <el-aside :width="app.sidebarCollapsed ? '68px' : '224px'" class="sidebar">
      <div class="brand">
        <span class="brand-mark">ERP</span>
        <span v-if="!app.sidebarCollapsed">ERP 管理系统</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :default-openeds="openMenuKeys"
        :collapse="app.sidebarCollapsed"
        unique-opened
        router
        @select="activateMenu"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataAnalysis /></el-icon><template #title>经营看板</template>
        </el-menu-item>
        <el-sub-menu index="master-data">
          <template #title><el-icon><Collection /></el-icon><span>主数据</span></template>
          <el-menu-item index="/master-data/materials">物料档案</el-menu-item>
          <el-menu-item index="/master-data/customers">客户档案</el-menu-item>
          <el-menu-item index="/master-data/suppliers">供应商档案</el-menu-item>
          <el-menu-item index="/master-data/warehouses">仓库档案</el-menu-item>
          <el-menu-item index="/master-data/units">计量单位</el-menu-item>
          <el-menu-item index="/master-data/tax-rates">税率档案</el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="sales">
          <template #title><el-icon><Document /></el-icon><span>销售管理</span></template>
          <el-menu-item index="/sales/quotes">销售报价</el-menu-item>
          <el-menu-item index="/sales/orders">销售订单</el-menu-item>
          <el-menu-item index="/sales/returns">销售退货</el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="purchase">
          <template #title><el-icon><ShoppingCart /></el-icon><span>采购管理</span></template>
          <el-menu-item index="/purchase/requests">采购申请</el-menu-item>
          <el-menu-item index="/purchase/orders">采购订单</el-menu-item>
          <el-menu-item index="/purchase/returns">采购退货</el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="inventory">
          <template #title><el-icon><Box /></el-icon><span>库存管理</span></template>
          <el-menu-item index="/inventory/stock">库存台账</el-menu-item>
          <el-menu-item index="/inventory/transactions">库存流水</el-menu-item>
          <el-menu-item index="/inventory/transfers">库存调拨</el-menu-item>
          <el-menu-item index="/inventory/counts">库存盘点</el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="finance">
          <template #title><el-icon><Wallet /></el-icon><span>财务管理</span></template>
          <el-menu-item index="/finance/receivables">应收账款</el-menu-item>
          <el-menu-item index="/finance/payables">应付账款</el-menu-item>
          <el-menu-item index="/finance/expenses">费用报销</el-menu-item>
          <el-menu-item index="/finance/vouchers">会计凭证</el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="crm">
          <template #title><el-icon><UserFilled /></el-icon><span>CRM 管理</span></template>
          <el-menu-item index="/crm/leads">线索管理</el-menu-item>
          <el-menu-item index="/crm/opportunities">商机管理</el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="system">
          <template #title><el-icon><Setting /></el-icon><span>系统运维</span></template>
          <el-menu-item index="/system/operation-logs">操作日志</el-menu-item>
          <el-menu-item index="/system/admin">权限与基础管理</el-menu-item>
          <el-menu-item index="/system/backup">备份恢复</el-menu-item>
          <el-menu-item index="/settings/parameters">全局参数</el-menu-item>
          <el-menu-item index="/settings/workflow">审批流程</el-menu-item>
          <el-menu-item index="/settings/print-templates">打印模板</el-menu-item>
        </el-sub-menu>
      </el-menu>
      <div class="sidebar-spacer" />
      <button class="sidebar-user" type="button" @click="router.push('/profile')">
        <span class="avatar">{{ (auth.user?.display_name || auth.user?.username || "用").slice(0, 1) }}</span>
        <span v-if="!app.sidebarCollapsed" class="user-copy"><strong>{{ auth.user?.display_name || auth.user?.username || "用户" }}</strong><small>运营管理员</small></span>
      </button>
    </el-aside>
    <el-container>
      <el-header class="topbar">
        <el-button class="menu-trigger" text @click="app.toggleSidebar"><el-icon><Menu /></el-icon></el-button>
        <el-autocomplete
          v-model="searchKeyword"
          class="global-search"
          :fetch-suggestions="fetchSearchSuggestions"
          placeholder="全局检索编码、名称、单据号"
          clearable
          @keyup.enter="search"
          @select="selectResult"
        />
        <span class="spacer" />
        <el-button class="top-action" text @click="app.toggleTheme"><el-icon><Sunny /></el-icon>{{ app.theme === "light" ? "暖石" : "浅色" }}</el-button>
        <el-button class="top-action" text><el-icon><QuestionFilled /></el-icon>帮助</el-button>
        <el-dropdown>
          <span class="user-menu"><span class="avatar avatar-small">{{ (auth.user?.display_name || auth.user?.username || "用").slice(0, 1) }}</span><span>{{ auth.user?.display_name || auth.user?.username || "用户" }}</span></span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="router.push('/profile')">个人中心</el-dropdown-item>
              <el-dropdown-item @click="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main class="main-content">
        <div v-if="app.openedNavigation" class="navigation-tabs">
          <el-tabs :model-value="app.openedNavigation.path" type="card" @tab-click="router.push(app.openedNavigation?.path || '/dashboard')" @tab-remove="closeNavigation">
            <el-tab-pane :name="app.openedNavigation.path" :label="app.openedNavigation.title" closable />
          </el-tabs>
        </div>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.admin-layout { min-height: 100vh; background: var(--erp-page-bg); }
.sidebar { display: flex; flex-direction: column; background: var(--erp-sidebar-bg); transition: width .2s; overflow: hidden; }
.brand { display: flex; align-items: center; gap: 10px; min-height: 80px; padding: 20px 18px; color: #fff; font-size: 16px; font-weight: 700; white-space: nowrap; }
.brand-mark { display: grid; place-items: center; flex: 0 0 35px; width: 35px; height: 35px; border-radius: 12px; background: var(--erp-primary); color: #fff; font-size: 10px; letter-spacing: .02em; }
.sidebar :deep(.el-menu) { flex: 0 0 auto; border-right: 0; background: transparent; padding: 0 12px; }
.sidebar :deep(.el-menu-item), .sidebar :deep(.el-sub-menu__title) { height: 40px; line-height: 40px; }
.sidebar :deep(.el-menu-item), .sidebar :deep(.el-sub-menu__title) { margin: 3px 0; padding: 0 12px !important; border-radius: 10px; color: #c4bab0; }
.sidebar :deep(.el-menu-item:hover), .sidebar :deep(.el-sub-menu__title:hover) { color: #fff; background: rgba(255,255,255,.06); }
.sidebar :deep(.el-menu-item.is-active) { color: #fff; background: var(--erp-sidebar-active); box-shadow: inset 3px 0 var(--erp-primary); }
.sidebar :deep(.el-sub-menu.is-opened > .el-sub-menu__title) { color: #fff; background: rgba(255,255,255,.035); }
.sidebar :deep(.el-sub-menu .el-menu) { background: transparent; }
.sidebar :deep(.el-sub-menu .el-menu-item) { padding-left: 47px !important; color: #b4a79c; }
.sidebar :deep(.el-sub-menu .el-menu-item.is-active) { color: #fff; background: var(--erp-sidebar-active); }
.sidebar :deep(.el-icon) { color: currentColor; margin-right: 9px; font-size: 17px; }
.sidebar :deep(.el-sub-menu__icon-arrow) { right: 12px; color: #8d8177; }
.sidebar-spacer { flex: 1; min-height: 10px; }
.sidebar-user { display: flex; align-items: center; gap: 9px; margin: 12px 18px 19px; padding: 17px 0 0; border: 0; border-top: 1px solid rgba(255,255,255,.11); background: transparent; text-align: left; color: #fff; cursor: pointer; }
.user-copy { display: flex; flex-direction: column; min-width: 0; }
.user-copy strong { font-size: 12px; font-weight: 600; }
.user-copy small { margin-top: 3px; color: #b4a79c; font-size: 10px; }
.avatar { display: grid; place-items: center; flex: 0 0 31px; width: 31px; height: 31px; border-radius: 50%; background: #e0ac8f; color: #573122; font-size: 11px; font-weight: 700; }
.avatar-small { width: 29px; height: 29px; }
.topbar { display: flex; align-items: center; height: 66px; border-bottom: 1px solid var(--erp-border); background: var(--erp-panel-bg); }
.spacer { flex: 1; }
.menu-trigger { color: var(--erp-muted-text); font-size: 20px; }
.user-menu { display: inline-flex; align-items: center; gap: 8px; cursor: pointer; color: var(--erp-text); }
.top-action { color: var(--erp-muted-text); }
.top-action :deep(.el-icon) { margin-right: 4px; }
.global-search { width: min(400px, 42vw); margin-left: 14px; }
.global-search :deep(.el-input__wrapper) { border-radius: 11px; padding: 1px 12px; }
.main-content { min-width: 0; background: var(--erp-page-bg); }
.main-content :deep(.el-main) { padding: 0; }
.navigation-tabs { margin: 12px 27px 0; }
.navigation-tabs :deep(.el-tabs__header) { margin: 0; }
.navigation-tabs :deep(.el-tabs__item) { color: var(--erp-muted-text); }
.navigation-tabs :deep(.el-tabs__item.is-active) { color: var(--erp-primary-dark); }
.main-content > :deep(.el-main) { background: var(--erp-page-bg); }
@media (max-width: 820px) {
  .sidebar { width: 68px !important; }
  .brand { padding-inline: 16px; }
  .sidebar-user { margin-inline: 18px; }
  .global-search { width: min(260px, 42vw); }
  .top-action { padding-inline: 6px; }
  .top-action :deep(.el-icon) { margin-right: 0; }
  .top-action:not(:has(.el-icon)) { display: none; }
}
</style>
