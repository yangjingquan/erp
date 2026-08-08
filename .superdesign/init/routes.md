# Routes and page map

Router: `frontend/src/router/index.ts` using Vue Router 4 with `createWebHistory()` in browser and `createMemoryHistory()` on server.

All authenticated routes render inside `frontend/src/layouts/AdminLayout.vue`.

## Key design targets

| URL | Entry component | Current visual role |
|---|---|---|
| `/dashboard` | `frontend/src/views/Dashboard.vue` | 4 KPI cards and one sales/purchase line chart |
| `/master-data/materials` | `frontend/src/views/master-data/MaterialList.vue` → `MasterDataPage.vue` | Search/filter toolbar, master-data table, pagination, create dialog |
| `/sales/orders` | `frontend/src/views/sales/SalesOrderList.vue` | New-order action, table, workflow actions, create/detail dialogs |

Other route groups: master data (customers, suppliers, warehouses, units, tax rates), sales (quotes, returns), purchase (requests, orders, returns), inventory (stock, transactions, transfers, counts, scan, locations, batches), finance (receivables, payables, expenses, vouchers), CRM (leads, opportunities), production (BOM, MRP, work orders), quality, HR, cost, system, settings, and profile.

## Full router configuration

```ts
import { createMemoryHistory, createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "../stores/auth";
import AdminLayout from "../layouts/AdminLayout.vue";
import Dashboard from "../views/Dashboard.vue";
import Login from "../views/Login.vue";
import MaterialList from "../views/master-data/MaterialList.vue";

const history = typeof window === "undefined" ? createMemoryHistory() : createWebHistory();

export const router = createRouter({
  history,
  routes: [
    { path: "/login", name: "login", component: Login },
    { path: "/403", name: "forbidden", component: () => import("../views/Forbidden.vue") },
    {
      path: "/",
      component: AdminLayout,
      meta: { requiresAuth: true },
      children: [
        { path: "", redirect: "/dashboard" },
        { path: "dashboard", name: "dashboard", component: Dashboard, meta: { requiresAuth: true } },
        { path: "master-data/materials", name: "materials", component: MaterialList, meta: { requiresAuth: true } },
        { path: "master-data/customers", name: "customers", component: () => import("../views/master-data/CustomerList.vue"), meta: { requiresAuth: true } },
        { path: "master-data/suppliers", name: "suppliers", component: () => import("../views/master-data/SupplierList.vue"), meta: { requiresAuth: true } },
        { path: "master-data/warehouses", name: "warehouses", component: () => import("../views/master-data/WarehouseList.vue"), meta: { requiresAuth: true } },
        { path: "master-data/units", name: "units", component: () => import("../views/master-data/UnitList.vue"), meta: { requiresAuth: true } },
        { path: "master-data/tax-rates", name: "tax-rates", component: () => import("../views/master-data/TaxRateList.vue"), meta: { requiresAuth: true } },
        { path: "sales/orders", name: "sales-orders", component: () => import("../views/sales/SalesOrderList.vue"), meta: { requiresAuth: true } },
        { path: "sales/quotes", name: "sales-quotes", component: () => import("../views/sales/QuoteList.vue"), meta: { requiresAuth: true } },
        { path: "sales/returns", name: "sales-returns", component: () => import("../views/sales/ReturnList.vue"), meta: { requiresAuth: true } },
        { path: "purchase/orders", name: "purchase-orders", component: () => import("../views/purchase/PurchaseOrderList.vue"), meta: { requiresAuth: true } },
        { path: "purchase/requests", name: "purchase-requests", component: () => import("../views/purchase/RequestList.vue"), meta: { requiresAuth: true } },
        { path: "purchase/returns", name: "purchase-returns", component: () => import("../views/purchase/ReturnList.vue"), meta: { requiresAuth: true } },
        { path: "inventory/stock", name: "inventory-stock", component: () => import("../views/inventory/StockList.vue"), meta: { requiresAuth: true } },
        { path: "inventory/transactions", name: "inventory-transactions", component: () => import("../views/inventory/TransactionList.vue"), meta: { requiresAuth: true } },
        { path: "inventory/transfers", name: "inventory-transfers", component: () => import("../views/inventory/TransferList.vue"), meta: { requiresAuth: true } },
        { path: "inventory/counts", name: "inventory-counts", component: () => import("../views/inventory/CountList.vue"), meta: { requiresAuth: true } },
        { path: "finance/receivables", name: "finance-receivables", component: () => import("../views/finance/ReceivableList.vue"), meta: { requiresAuth: true } },
        { path: "finance/payables", name: "finance-payables", component: () => import("../views/finance/PayableList.vue"), meta: { requiresAuth: true } },
        { path: "finance/expenses", name: "finance-expenses", component: () => import("../views/finance/ExpenseList.vue"), meta: { requiresAuth: true } },
        { path: "finance/vouchers", name: "finance-vouchers", component: () => import("../views/finance/VoucherList.vue"), meta: { requiresAuth: true } },
        { path: "crm/leads", name: "crm-leads", component: () => import("../views/crm/LeadList.vue"), meta: { requiresAuth: true, permission: "crm:view" } },
        { path: "crm/opportunities", name: "crm-opportunities", component: () => import("../views/crm/OpportunityList.vue"), meta: { requiresAuth: true, permission: "crm:view" } },
        { path: "inventory/scan", name: "inventory-scan", component: () => import("../views/inventory-advanced/Scan.vue"), meta: { requiresAuth: true, permission: "inventory:manage" } },
        { path: "production/boms", name: "production-boms", component: () => import("../views/production/BomList.vue"), meta: { requiresAuth: true, permission: "production:view" } },
        { path: "production/mrp", name: "production-mrp", component: () => import("../views/production/MrpRunList.vue"), meta: { requiresAuth: true, permission: "production:view" } },
        { path: "production/work-orders", name: "production-work-orders", component: () => import("../views/production/WorkOrderList.vue"), meta: { requiresAuth: true, permission: "production:view" } },
        { path: "inventory/locations", name: "inventory-locations", component: () => import("../views/inventory-advanced/LocationList.vue"), meta: { requiresAuth: true, permission: "inventory:view" } },
        { path: "inventory/batches", name: "inventory-batches", component: () => import("../views/inventory-advanced/BatchList.vue"), meta: { requiresAuth: true, permission: "inventory:view" } },
        { path: "cost/allocations", name: "cost-allocations", component: () => import("../views/cost/AllocationList.vue"), meta: { requiresAuth: true, permission: "cost:view" } },
        { path: "cost/period-close", name: "cost-period-close", component: () => import("../views/cost/PeriodClose.vue"), meta: { requiresAuth: true, permission: "cost:close" } },
        { path: "quality/inspections", name: "quality-inspections", component: () => import("../views/quality/InspectionList.vue"), meta: { requiresAuth: true, permission: "quality:view" } },
        { path: "hr/employees", name: "hr-employees", component: () => import("../views/hr/EmployeeList.vue"), meta: { requiresAuth: true, permission: "hr:view" } },
        { path: "hr/payroll", name: "hr-payroll", component: () => import("../views/hr/PayrollList.vue"), meta: { requiresAuth: true, permission: "hr:salary:view" } },
        { path: "settings/api-clients", name: "api-clients", component: () => import("../views/settings/ApiClientList.vue"), meta: { requiresAuth: true, permission: "system:manage" } },
        { path: "settings/workflow", name: "workflow-settings", component: () => import("../views/settings/WorkflowConfig.vue"), meta: { requiresAuth: true } },
        { path: "system/operation-logs", name: "operation-logs", component: () => import("../views/system/OperationLog.vue"), meta: { requiresAuth: true } },
        { path: "system/admin", name: "system-admin", component: () => import("../views/system/AdminBasics.vue"), meta: { requiresAuth: true } },
        { path: "profile", name: "profile", component: () => import("../views/Profile.vue"), meta: { requiresAuth: true } },
        { path: "system/backup", name: "backup-restore", component: () => import("../views/system/BackupRestore.vue"), meta: { requiresAuth: true } },
        { path: "settings/parameters", name: "global-parameters", component: () => import("../views/settings/GlobalParameters.vue"), meta: { requiresAuth: true } },
        { path: "settings/print-templates", name: "print-templates", component: () => import("../views/settings/PrintTemplates.vue"), meta: { requiresAuth: true } },
      ],
    },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (to.meta.requiresAuth && !auth.isLoggedIn) return { name: "login", query: { redirect: to.fullPath } };
  if (to.name === "login" && auth.isLoggedIn) return { name: "dashboard" };
  return true;
});
```

