# Key page dependency trees

The dependency trees below focus on UI-bearing local files. API modules and Pinia stores are listed when they affect visible state or labels; Element Plus, Vue, ECharts, Axios, and other node modules are omitted.

## `/dashboard` — 经营看板

Entry: `frontend/src/views/Dashboard.vue`

Dependencies:

- `frontend/src/views/Dashboard.vue`
  - `frontend/src/stores/app.ts`
  - `frontend/src/api/dashboard.ts`
- `frontend/src/layouts/AdminLayout.vue`
  - `frontend/src/stores/app.ts`
  - `frontend/src/stores/auth.ts`
  - `frontend/src/api/search.ts`
- `frontend/src/styles/theme.css`

Render: page header → four equal KPI cards → one large chart card with sales and purchase lines.

## `/master-data/materials` — 物料档案

Entry: `frontend/src/views/master-data/MaterialList.vue`

Dependencies:

- `frontend/src/views/master-data/MaterialList.vue`
  - `frontend/src/views/master-data/MasterDataPage.vue`
    - `frontend/src/api/master-data.ts`
    - `frontend/src/styles/theme.css`
- `frontend/src/layouts/AdminLayout.vue`
  - `frontend/src/stores/app.ts`
  - `frontend/src/stores/auth.ts`
  - `frontend/src/api/search.ts`

Render: page header → bordered toolbar card with search and actions → bordered striped table with material code/name/category/type/prices/safety stock/status → right-aligned pagination → modal create form.

## `/sales/orders` — 销售订单

Entry: `frontend/src/views/sales/SalesOrderList.vue`

Dependencies:

- `frontend/src/views/sales/SalesOrderList.vue`
  - `frontend/src/api/sales.ts`
  - `frontend/src/composables/useMasterOptions.ts`
    - `frontend/src/api/master-data.ts`
- `frontend/src/layouts/AdminLayout.vue`
  - `frontend/src/stores/app.ts`
  - `frontend/src/stores/auth.ts`
  - `frontend/src/api/search.ts`
- `frontend/src/styles/theme.css`

Render: page header → toolbar with primary new-order action and refresh → optional error alert → striped table with order no/customer/status/tax-inclusive amount/workflow actions → create-order dialog → order-detail descriptions dialog.

## `/master-data/customers` — representative sibling page

Entry: `frontend/src/views/master-data/CustomerList.vue`

Dependencies:

- `frontend/src/views/master-data/CustomerList.vue`
  - `frontend/src/views/master-data/MasterDataPage.vue`
    - `frontend/src/api/master-data.ts`
- `frontend/src/layouts/AdminLayout.vue`

## `/login` — authentication entry

Entry: `frontend/src/views/Login.vue`

Dependencies:

- `frontend/src/views/Login.vue`
  - `frontend/src/stores/auth.ts`

