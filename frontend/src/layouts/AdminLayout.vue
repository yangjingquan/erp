<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import {
  Bell,
  Box,
  Collection,
  Connection,
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
import { usePermissionStore } from "../stores/permission";
import { globalSearch } from "../api/search";
import { listOrganizations } from "../api/auth";
import AppPageHeader from "../components/AppPageHeader.vue";
import NotificationCenter from "../components/NotificationCenter.vue";
import { pageHeaders } from "../config/pageHeaders";

const app = useAppStore();
const auth = useAuthStore();
const permissions = usePermissionStore();
const route = useRoute();
const router = useRouter();
const searchKeyword = ref("");
const searchResults = ref<Array<Record<string, any>>>([]);
const organizations = ref<Array<Record<string, any>>>([]);
const switchingOrganization = ref(false);
const compactViewport = ref(false);
const mobileMenuOpen = ref(false);
const sidebarCollapsed = computed(() => app.sidebarCollapsed && !compactViewport.value);
const activeMenu = computed(() => route.path);
const pageHeader = computed(() => pageHeaders[route.path]);
const openMenuKeys = computed(() => {
    const currentGroup = route.path.split("/")[1];
  const group = ["dashboard", "analytics"].includes(currentGroup) || route.path === "/platform/metrics" ? "insights" : currentGroup === "settings" || ["group", "compliance", "low-code"].includes(route.path.split("/")[2]) && currentGroup === "platform" ? "config" : ["plm"].includes(currentGroup) ? "production" : currentGroup === "srm" ? "purchase" : currentGroup === "projects" ? "cost" : currentGroup === "eam" ? "asset" : currentGroup;
  return ["insights", "master-data", "sales", "purchase", "inventory", "finance", "crm", "production", "cost", "quality", "hr", "operations", "asset", "system", "config"].includes(group) ? [group] : [];
});
function canPage(path: string) { return !auth.user || auth.user.is_superuser || permissions.hasPagePermission(path); }
function canAny(paths: string[]) { return paths.some((path) => canPage(path)); }

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

async function loadOrganizations() {
  try {
    const response = await listOrganizations();
    if (response.data.code === 0) organizations.value = Array.isArray(response.data.data) ? response.data.data : [];
  } catch {
    organizations.value = [];
  }
}

async function switchOrganization(orgId: string) {
  if (!orgId || orgId === auth.user?.org_id) return;
  switchingOrganization.value = true;
  try {
    await auth.switchOrganization(orgId);
    ElMessage.success("已切换组织");
    await router.replace(route.fullPath);
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "组织切换失败");
  } finally {
    switchingOrganization.value = false;
  }
}

function syncViewport() {
  compactViewport.value = window.innerWidth <= 900;
  if (!compactViewport.value) mobileMenuOpen.value = false;
}

function toggleNavigation() {
  if (compactViewport.value) {
    if (mobileMenuOpen.value) {
      closeMobileMenu();
    } else {
      mobileMenuOpen.value = true;
      void nextTick(() => document.querySelector<HTMLElement>(".sidebar .el-menu-item, .sidebar .el-sub-menu__title")?.focus());
    }
    return;
  }
  app.toggleSidebar();
}

function closeMobileMenu() {
  if (!mobileMenuOpen.value) return;
  mobileMenuOpen.value = false;
  if (compactViewport.value) void nextTick(() => document.querySelector<HTMLElement>(".menu-trigger")?.focus());
}

watch(() => route.path, closeMobileMenu);
watch(mobileMenuOpen, (open) => document.body.classList.toggle("navigation-open", open), { immediate: true });

onMounted(async () => {
  syncViewport();
  window.addEventListener("resize", syncViewport);
  await loadOrganizations();
});
onBeforeUnmount(() => {
  window.removeEventListener("resize", syncViewport);
  document.body.classList.remove("navigation-open");
});
</script>

<template>
  <el-container data-erp-ready="1" class="admin-layout" @keydown.esc="closeMobileMenu">
    <el-aside :width="sidebarCollapsed ? '68px' : '224px'" :class="['sidebar', { 'mobile-open': compactViewport && mobileMenuOpen }]" :aria-hidden="compactViewport && !mobileMenuOpen" :inert="compactViewport && !mobileMenuOpen">
      <div class="brand">
        <span class="brand-mark">ERP</span>
        <span v-if="!sidebarCollapsed">ERP 管理系统</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :default-openeds="openMenuKeys"
        :collapse="sidebarCollapsed"
        unique-opened
        router
      >
        <el-menu-item v-if="canPage('/workflow/tasks')" index="/workflow/tasks"><el-icon><Bell /></el-icon><span>我的待办</span></el-menu-item>
        <el-sub-menu v-if="canAny(['/dashboard', '/analytics/reports', '/platform/metrics'])" index="insights">
          <template #title><el-icon><DataAnalysis /></el-icon><span>经营分析</span></template>
          <el-menu-item v-if="canPage('/dashboard')" index="/dashboard">经营看板</el-menu-item>
          <el-menu-item v-if="canPage('/analytics/reports')" index="/analytics/reports">BI 报表中心</el-menu-item>
          <el-menu-item v-if="canPage('/platform/metrics')" index="/platform/metrics">指标与异常助手</el-menu-item>
        </el-sub-menu>
        <el-sub-menu v-if="canAny(['/operations/advanced', '/documents'])" index="operations">
          <template #title><el-icon><DataAnalysis /></el-icon><span>运营协同</span></template>
          <el-menu-item v-if="canPage('/operations/advanced')" index="/operations/advanced">运输与预测</el-menu-item>
          <el-menu-item v-if="canPage('/documents')" index="/documents">业务单据中心</el-menu-item>
        </el-sub-menu>
        <el-sub-menu v-if="canAny(['/master-data/materials', '/master-data/customers', '/master-data/suppliers', '/master-data/warehouses', '/master-data/units', '/master-data/tax-rates'])" index="master-data">
          <template #title><el-icon><Collection /></el-icon><span>基础资料</span></template>
          <el-menu-item v-if="canPage('/master-data/materials')" index="/master-data/materials">物料档案</el-menu-item>
          <el-menu-item v-if="canPage('/master-data/customers')" index="/master-data/customers">客户档案</el-menu-item>
          <el-menu-item v-if="canPage('/master-data/suppliers')" index="/master-data/suppliers">供应商档案</el-menu-item>
          <el-menu-item v-if="canPage('/master-data/warehouses')" index="/master-data/warehouses">仓库档案</el-menu-item>
          <el-menu-item v-if="canPage('/master-data/units')" index="/master-data/units">计量单位</el-menu-item>
          <el-menu-item v-if="canPage('/master-data/tax-rates')" index="/master-data/tax-rates">税率档案</el-menu-item>
        </el-sub-menu>
        <el-sub-menu v-if="canAny(['/sales/quotes', '/sales/orders', '/sales/returns'])" index="sales">
          <template #title><el-icon><Document /></el-icon><span>销售管理</span></template>
          <el-menu-item v-if="canPage('/sales/quotes')" index="/sales/quotes">销售报价</el-menu-item>
          <el-menu-item v-if="canPage('/sales/orders')" index="/sales/orders">销售订单</el-menu-item>
          <el-menu-item v-if="canPage('/sales/returns')" index="/sales/returns">销售退货</el-menu-item>
        </el-sub-menu>
        <el-sub-menu v-if="canAny(['/purchase/requests', '/purchase/orders', '/purchase/returns', '/srm/collaboration'])" index="purchase">
          <template #title><el-icon><ShoppingCart /></el-icon><span>采购管理</span></template>
          <el-menu-item v-if="canPage('/purchase/requests')" index="/purchase/requests">采购申请</el-menu-item>
          <el-menu-item v-if="canPage('/purchase/orders')" index="/purchase/orders">采购订单</el-menu-item>
          <el-menu-item v-if="canPage('/purchase/returns')" index="/purchase/returns">采购退货</el-menu-item>
          <el-menu-item v-if="canPage('/srm/collaboration')" index="/srm/collaboration">供应商协同</el-menu-item>
        </el-sub-menu>
        <el-sub-menu v-if="canAny(['/inventory/stock', '/inventory/transactions', '/inventory/transfers', '/inventory/counts', '/inventory/scan', '/inventory/locations', '/inventory/batches', '/inventory/control-center', '/inventory/wms-tasks'])" index="inventory">
          <template #title><el-icon><Box /></el-icon><span>库存管理</span></template>
          <el-menu-item v-if="canPage('/inventory/stock')" index="/inventory/stock">库存台账</el-menu-item>
          <el-menu-item v-if="canPage('/inventory/transactions')" index="/inventory/transactions">库存流水</el-menu-item>
          <el-menu-item v-if="canPage('/inventory/transfers')" index="/inventory/transfers">库存调拨</el-menu-item>
          <el-menu-item v-if="canPage('/inventory/counts')" index="/inventory/counts">库存盘点</el-menu-item>
          <el-menu-item v-if="canPage('/inventory/scan')" index="/inventory/scan">移动扫码</el-menu-item>
          <el-menu-item v-if="canPage('/inventory/locations')" index="/inventory/locations">仓位管理</el-menu-item>
          <el-menu-item v-if="canPage('/inventory/batches')" index="/inventory/batches">批次管理</el-menu-item>
          <el-menu-item v-if="canPage('/inventory/control-center')" index="/inventory/control-center">库存控制中心</el-menu-item>
          <el-menu-item v-if="canPage('/inventory/wms-tasks')" index="/inventory/wms-tasks">WMS 作业中心</el-menu-item>
        </el-sub-menu>
        <el-sub-menu v-if="canAny(['/finance/receivables', '/finance/payables', '/finance/expenses', '/finance/vouchers', '/finance/foundation', '/finance/currencies', '/finance/controls'])" index="finance">
          <template #title><el-icon><Wallet /></el-icon><span>财务管理</span></template>
          <el-menu-item v-if="canPage('/finance/receivables')" index="/finance/receivables">应收账款</el-menu-item>
          <el-menu-item v-if="canPage('/finance/payables')" index="/finance/payables">应付账款</el-menu-item>
          <el-menu-item v-if="canPage('/finance/expenses')" index="/finance/expenses">费用报销</el-menu-item>
          <el-menu-item v-if="canPage('/finance/vouchers')" index="/finance/vouchers">会计凭证</el-menu-item>
          <el-menu-item v-if="canPage('/finance/foundation')" index="/finance/foundation">总账基础</el-menu-item>
          <el-menu-item v-if="canPage('/finance/currencies')" index="/finance/currencies">多币种与汇率</el-menu-item>
          <el-menu-item v-if="canPage('/finance/controls')" index="/finance/controls">财务控制中心</el-menu-item>
        </el-sub-menu>
        <el-sub-menu v-if="canAny(['/crm/leads', '/crm/opportunities', '/crm/customer-360'])" index="crm">
          <template #title><el-icon><UserFilled /></el-icon><span>CRM 管理</span></template>
          <el-menu-item v-if="canPage('/crm/leads')" index="/crm/leads">线索管理</el-menu-item>
          <el-menu-item v-if="canPage('/crm/opportunities')" index="/crm/opportunities">商机管理</el-menu-item>
          <el-menu-item v-if="canPage('/crm/customer-360')" index="/crm/customer-360">客户 360</el-menu-item>
        </el-sub-menu>
        <el-sub-menu v-if="canAny(['/production/boms', '/production/mrp', '/production/planning', '/production/work-orders', '/production/resources', '/production/execution', '/plm/changes'])" index="production">
          <template #title><el-icon><Document /></el-icon><span>生产管理</span></template>
          <el-menu-item v-if="canPage('/production/boms')" index="/production/boms">BOM 管理</el-menu-item>
          <el-menu-item v-if="canPage('/production/mrp')" index="/production/mrp">MRP 运算</el-menu-item>
          <el-menu-item v-if="canPage('/production/planning')" index="/production/planning">生产计划</el-menu-item>
          <el-menu-item v-if="canPage('/production/work-orders')" index="/production/work-orders">生产工单</el-menu-item>
          <el-menu-item v-if="canPage('/production/resources')" index="/production/resources">工艺与产能</el-menu-item>
          <el-menu-item v-if="canPage('/production/execution')" index="/production/execution">生产执行控制台</el-menu-item>
          <el-menu-item v-if="canPage('/production/subcontract')" index="/production/subcontract">委外管理</el-menu-item>
          <el-menu-item v-if="canPage('/plm/changes')" index="/plm/changes">PLM 工程变更</el-menu-item>
        </el-sub-menu>
        <el-sub-menu v-if="canAny(['/cost/allocations', '/cost/period-close', '/projects/cost'])" index="cost">
          <template #title><el-icon><Wallet /></el-icon><span>成本管理</span></template>
          <el-menu-item v-if="canPage('/cost/allocations')" index="/cost/allocations">成本分摊</el-menu-item>
          <el-menu-item v-if="canPage('/cost/period-close')" index="/cost/period-close">期间结账</el-menu-item>
          <el-menu-item v-if="canPage('/projects/cost')" index="/projects/cost">项目与成本</el-menu-item>
        </el-sub-menu>
        <el-sub-menu v-if="canAny(['/quality/inspections', '/quality/nonconformances', '/quality/analytics'])" index="quality">
          <template #title><el-icon><Collection /></el-icon><span>质量管理</span></template>
          <el-menu-item v-if="canPage('/quality/inspections')" index="/quality/inspections">质量检验</el-menu-item>
          <el-menu-item v-if="canPage('/quality/nonconformances')" index="/quality/nonconformances">不合格与 CAPA</el-menu-item>
          <el-menu-item v-if="canPage('/quality/analytics')" index="/quality/analytics">质量分析与索赔</el-menu-item>
        </el-sub-menu>
        <el-sub-menu v-if="canAny(['/hr/employees', '/hr/payroll', '/hr/people-ops', '/hr/leave'])" index="hr">
          <template #title><el-icon><UserFilled /></el-icon><span>人事管理</span></template>
          <el-menu-item v-if="canPage('/hr/employees')" index="/hr/employees">员工档案</el-menu-item>
          <el-menu-item v-if="canPage('/hr/payroll')" index="/hr/payroll">薪资核算</el-menu-item>
          <el-menu-item v-if="canPage('/hr/people-ops')" index="/hr/people-ops">人事全生命周期</el-menu-item>
          <el-menu-item v-if="canPage('/hr/leave')" index="/hr/leave">请假管理</el-menu-item>
        </el-sub-menu>
        <el-sub-menu v-if="canAny(['/eam/service'])" index="asset">
          <template #title><el-icon><Connection /></el-icon><span>资产与服务</span></template>
          <el-menu-item v-if="canPage('/eam/service')" index="/eam/service">资产与售后服务</el-menu-item>
        </el-sub-menu>
        <el-sub-menu v-if="canAny(['/system/operation-logs', '/system/users', '/system/admin', '/system/backup'])" index="system">
          <template #title><el-icon><Setting /></el-icon><span>系统运维</span></template>
          <el-menu-item v-if="canPage('/system/operation-logs')" index="/system/operation-logs">操作日志</el-menu-item>
          <el-menu-item v-if="canPage('/system/users')" index="/system/users">用户管理</el-menu-item>
          <el-menu-item v-if="canPage('/system/admin')" index="/system/admin">权限设置</el-menu-item>
          <el-menu-item v-if="canPage('/system/backup')" index="/system/backup">备份恢复</el-menu-item>
        </el-sub-menu>
        <el-sub-menu v-if="canAny(['/settings/parameters', '/settings/workflow', '/settings/print-templates', '/settings/api-clients', '/settings/platform-events', '/platform/group', '/platform/compliance', '/platform/low-code'])" index="config">
          <template #title><el-icon><Setting /></el-icon><span>系统配置</span></template>
          <el-menu-item v-if="canPage('/settings/parameters')" index="/settings/parameters">全局参数</el-menu-item>
          <el-menu-item v-if="canPage('/settings/workflow')" index="/settings/workflow">审批流程</el-menu-item>
          <el-menu-item v-if="canPage('/settings/print-templates')" index="/settings/print-templates">打印模板</el-menu-item>
          <el-menu-item v-if="canPage('/settings/api-clients')" index="/settings/api-clients">API 客户端</el-menu-item>
          <el-menu-item v-if="canPage('/settings/platform-events')" index="/settings/platform-events">事件订阅</el-menu-item>
          <el-menu-item v-if="canPage('/platform/group')" index="/platform/group">集团与内部交易</el-menu-item>
          <el-menu-item v-if="canPage('/platform/compliance')" index="/platform/compliance">税务与发票</el-menu-item>
          <el-menu-item v-if="canPage('/platform/low-code')" index="/platform/low-code">低代码对象</el-menu-item>
        </el-sub-menu>
      </el-menu>
      <div class="sidebar-spacer" />
      <button class="sidebar-user" type="button" @click="router.push('/profile')">
        <span class="avatar">{{ (auth.user?.display_name || auth.user?.username || "用").slice(0, 1) }}</span>
        <span v-if="!sidebarCollapsed" class="user-copy"><strong>{{ auth.user?.display_name || auth.user?.username || "用户" }}</strong><small>运营管理员</small></span>
      </button>
    </el-aside>
    <button v-if="compactViewport && mobileMenuOpen" class="mobile-nav-backdrop" type="button" aria-label="关闭导航菜单" @click="closeMobileMenu" />
    <el-container>
      <el-header class="topbar">
        <el-button class="menu-trigger" text :aria-label="compactViewport ? '打开主导航' : '切换侧边栏'" :aria-expanded="compactViewport ? mobileMenuOpen : undefined" @click="toggleNavigation"><el-icon><Menu /></el-icon></el-button>
        <div class="topbar-fields" :class="{ 'has-org-switcher': organizations.length > 1 }">
          <el-autocomplete
            v-model="searchKeyword"
            class="global-search"
            :fetch-suggestions="fetchSearchSuggestions"
            placeholder="检索业务数据"
            clearable
            @keyup.enter="search"
            @select="selectResult"
          />
          <el-select v-if="organizations.length > 1" class="org-switcher" :model-value="auth.user?.org_id" :loading="switchingOrganization" @change="switchOrganization">
            <el-option v-for="item in organizations" :key="item.id" :label="item.name || item.code" :value="item.id" />
          </el-select>
        </div>
        <NotificationCenter />
        <el-button class="top-action theme-action" text aria-label="切换主题" @click="app.toggleTheme"><el-icon><Sunny /></el-icon>{{ app.theme === "light" ? "暖石" : "浅色" }}</el-button>
        <el-button class="top-action help-action" text><el-icon><QuestionFilled /></el-icon>帮助</el-button>
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
        <AppPageHeader v-if="pageHeader" v-bind="pageHeader" />
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.admin-layout { width: 100%; height: 100vh; height: 100dvh; overflow: hidden; background: var(--erp-page-bg); }
.admin-layout > :deep(.el-container) { min-width: 0; min-height: 0; height: 100%; overflow: hidden; }
.sidebar { display: flex; flex: 0 0 auto; flex-direction: column; min-height: 0; height: 100%; background: var(--erp-sidebar-bg); transition: width .2s; overflow-x: hidden; overflow-y: auto; overscroll-behavior: contain; -webkit-overflow-scrolling: touch; }
.brand { display: flex; align-items: center; gap: 10px; min-height: 80px; padding: 20px 18px; color: #fff; font-size: 16px; font-weight: 700; white-space: nowrap; }
.brand-mark { display: grid; place-items: center; flex: 0 0 35px; width: 35px; height: 35px; border-radius: 12px; background: var(--erp-primary); color: #fff; font-size: 10px; letter-spacing: .02em; }
.sidebar :deep(.el-menu) { flex: 0 0 auto; border-right: 0; background: transparent; padding: 0 12px; }
.sidebar :deep(.el-menu-item), .sidebar :deep(.el-sub-menu__title) { height: 40px; line-height: 40px; }
.sidebar :deep(.el-menu > .el-menu-item), .sidebar :deep(.el-menu > .el-sub-menu > .el-sub-menu__title) { font-size: 15px; font-weight: 600; }
.sidebar :deep(.el-menu-item), .sidebar :deep(.el-sub-menu__title) { margin: 3px 0; padding: 0 12px !important; border-radius: 10px; color: #c4bab0; }
.sidebar :deep(.el-menu-item:hover), .sidebar :deep(.el-sub-menu__title:hover) { color: #fff; background: rgba(255,255,255,.06); }
.sidebar :deep(.el-menu-item.is-active) { color: #fff; background: var(--erp-sidebar-active); box-shadow: inset 3px 0 var(--erp-primary); }
.sidebar :deep(.el-sub-menu.is-opened > .el-sub-menu__title) { color: #fff; background: rgba(255,255,255,.035); }
.sidebar :deep(.el-sub-menu .el-menu) { background: transparent; }
.sidebar :deep(.el-sub-menu .el-menu-item) { padding-left: 47px !important; color: #b4a79c; font-size: 15px; font-weight: 500; }
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
.topbar-fields { display: grid; flex: 1 1 auto; grid-template-columns: minmax(0, 1fr); align-items: center; gap: 12px; min-width: 0; margin-left: 14px; }
.topbar-fields.has-org-switcher { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.menu-trigger { color: var(--erp-muted-text); font-size: 20px; }
.user-menu { display: inline-flex; align-items: center; gap: 8px; cursor: pointer; color: var(--erp-text); white-space: nowrap; }
.top-action { color: var(--erp-muted-text); }
.top-action :deep(.el-icon) { margin-right: 4px; }
.global-search, .org-switcher { width: 100%; min-width: 0; }
.global-search :deep(.el-input__wrapper), .org-switcher :deep(.el-select__wrapper) { min-height: 34px; border-radius: 11px; padding: 1px 12px; }
.main-content { min-width: 0; min-height: 0; overflow-y: auto; overscroll-behavior-y: contain; -webkit-overflow-scrolling: touch; background: var(--erp-page-bg); }
.main-content :deep(.el-main) { padding: 0; }
.main-content > :deep(.el-main) { background: var(--erp-page-bg); }
@media (max-width: 900px) {
  .sidebar { position: fixed; inset: 0 auto 0 0; z-index: 3001; width: min(286px, calc(100vw - 48px)) !important; height: 100dvh; min-height: 100dvh; transform: translateX(-102%); transition: transform .24s cubic-bezier(.22, 1, .36, 1), box-shadow .24s ease; box-shadow: none; }
  .sidebar.mobile-open { transform: translateX(0); box-shadow: 12px 0 32px rgba(30, 22, 18, .22); }
  .mobile-nav-backdrop { position: fixed; inset: 0; z-index: 3000; padding: 0; border: 0; background: rgba(25, 20, 17, .46); touch-action: none; }
  .brand { min-height: 72px; padding: 18px 20px; }
  .sidebar-user { margin-inline: 20px; }
  .topbar { height: calc(60px + env(safe-area-inset-top)); flex: 0 0 calc(60px + env(safe-area-inset-top)); padding: env(safe-area-inset-top) 16px 0; }
  .topbar-fields { gap: 8px; margin-left: 4px; }
  .top-action { padding-inline: 6px; }
  .top-action :deep(.el-icon) { margin-right: 0; }
  .help-action { display: none; }
  .main-content { padding: 18px; overflow-x: hidden; }
}
@media (max-width: 640px) {
  .topbar { gap: 4px; height: calc(56px + env(safe-area-inset-top)); flex-basis: calc(56px + env(safe-area-inset-top)); padding: env(safe-area-inset-top) max(10px, env(safe-area-inset-left)) 0; }
  .menu-trigger { flex: 0 0 40px; width: 40px; height: 44px; padding: 0; }
  .topbar-fields { gap: 6px; margin-left: 0; }
  .topbar-fields.has-org-switcher { grid-template-columns: minmax(0, 1fr) minmax(96px, .55fr); }
  .theme-action { flex: 0 0 36px; width: 36px; height: 44px; padding: 0; font-size: 0; }
  .theme-action :deep(.el-icon) { margin: 0; font-size: 18px; }
  .user-menu > span:last-child { display: none; }
  .main-content { padding: 14px max(12px, env(safe-area-inset-right)) max(20px, env(safe-area-inset-bottom)) max(12px, env(safe-area-inset-left)); }
}
</style>
