<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";

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
  "/production/boms": "BOM", "/production/mrp": "MRP", "/production/work-orders": "生产工单", "/quality/inspections": "质量检验", "/hr/employees": "员工管理", "/hr/payroll": "薪资核算", "/cost/allocations": "成本分摊", "/cost/period-close": "期间结账", "/settings/api-clients": "API 客户端",
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
    <el-aside :width="app.sidebarCollapsed ? '64px' : '228px'" class="sidebar">
      <div class="brand">{{ app.sidebarCollapsed ? "ERP" : "ERP 管理系统" }}</div>
      <el-menu
        :default-active="activeMenu"
        :default-openeds="openMenuKeys"
        :collapse="app.sidebarCollapsed"
        unique-opened
        router
        @select="activateMenu"
      >
        <el-menu-item index="/dashboard">经营看板</el-menu-item>
        <el-sub-menu index="master-data">
          <template #title>主数据</template>
          <el-menu-item index="/master-data/materials">物料档案</el-menu-item>
          <el-menu-item index="/master-data/customers">客户档案</el-menu-item>
          <el-menu-item index="/master-data/suppliers">供应商档案</el-menu-item>
          <el-menu-item index="/master-data/warehouses">仓库档案</el-menu-item>
          <el-menu-item index="/master-data/units">计量单位</el-menu-item>
          <el-menu-item index="/master-data/tax-rates">税率档案</el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="sales"><template #title>销售管理</template><el-menu-item index="/sales/quotes">销售报价</el-menu-item><el-menu-item index="/sales/orders">销售订单</el-menu-item><el-menu-item index="/sales/returns">销售退货</el-menu-item></el-sub-menu>
        <el-sub-menu index="purchase"><template #title>采购管理</template><el-menu-item index="/purchase/requests">采购申请</el-menu-item><el-menu-item index="/purchase/orders">采购订单</el-menu-item><el-menu-item index="/purchase/returns">采购退货</el-menu-item></el-sub-menu>
        <el-sub-menu index="inventory">
          <template #title>库存管理</template>
          <el-menu-item index="/inventory/stock">库存台账</el-menu-item>
          <el-menu-item index="/inventory/transactions">库存流水</el-menu-item>
          <el-menu-item index="/inventory/transfers">库存调拨</el-menu-item>
          <el-menu-item index="/inventory/counts">库存盘点</el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="finance">
          <template #title>财务管理</template>
          <el-menu-item index="/finance/receivables">应收账款</el-menu-item>
          <el-menu-item index="/finance/payables">应付账款</el-menu-item>
          <el-menu-item index="/finance/expenses">费用报销</el-menu-item>
          <el-menu-item index="/finance/vouchers">会计凭证</el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="crm"><template #title>CRM 管理</template><el-menu-item index="/crm/leads">线索管理</el-menu-item><el-menu-item index="/crm/opportunities">商机管理</el-menu-item></el-sub-menu>
        <el-sub-menu index="system">
          <template #title>系统运维</template>
          <el-menu-item index="/system/operation-logs">操作日志</el-menu-item>
          <el-menu-item index="/system/admin">权限与基础管理</el-menu-item>
          <el-menu-item index="/system/backup">备份恢复</el-menu-item>
          <el-menu-item index="/settings/parameters">全局参数</el-menu-item>
          <el-menu-item index="/settings/workflow">审批流程</el-menu-item>
          <el-menu-item index="/settings/print-templates">打印模板</el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="topbar">
        <el-button text @click="app.toggleSidebar">☰</el-button>
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
        <el-button text @click="app.toggleTheme">{{ app.theme === "light" ? "暗黑" : "浅色" }}</el-button>
        <el-dropdown>
          <span class="user-menu">{{ auth.user?.display_name || auth.user?.username || "用户" }}</span>
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
.admin-layout { min-height: 100vh; }
.sidebar { background: var(--erp-sidebar-bg); transition: width .2s; }
.brand { color: #fff; font-size: 17px; font-weight: 700; padding: 18px 16px; white-space: nowrap; }
.topbar { display: flex; align-items: center; border-bottom: 1px solid var(--erp-border); background: var(--erp-panel-bg); }
.spacer { flex: 1; }
.user-menu { cursor: pointer; color: var(--erp-text); }
.global-search { width: min(360px, 42vw); margin-left: 16px; }
.main-content { background: var(--erp-page-bg); }
.navigation-tabs { margin-bottom: 12px; }
</style>
