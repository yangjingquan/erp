# ERP redesign design brief

## Product context

This is a private enterprise ERP for operations teams. The core information architecture is already implemented in Vue 3 + Element Plus and must remain recognizable: an authenticated shell, left navigation, global search, module pages, dense data tables, workflow status actions, and light/dark theme support.

## Four design targets in this round

1. Left navigation: the complete module hierarchy with current-page state, collapse affordance, global search entry, and user/theme utilities.
2. 经营看板: month-level sales, purchasing, receivables, inventory risk, and sales/purchase trend visualization.
3. 物料档案: searchable material master data with code, name, category, type, prices, safety stock, status, import/export, pagination, and create flow.
4. 销售订单: order list with customer/status/amount, workflow actions for draft/submitted/approved orders, create order flow, and detail view.

## Existing source-of-truth baseline

- Vue 3 `<script setup lang="ts">`; Element Plus 2.9.8 primitives; ECharts for charts.
- Current canvas tokens: page `#f4f7fb`, panels `#ffffff`, sidebar `#18253d`, border `#e5e7eb`, text `#1f2937`, muted `#64748b`; dark theme equivalents are in `.superdesign/init/theme.md`.
- Current shell dimensions: 228px expanded sidebar / 64px collapsed; white topbar; main content on pale blue-gray background.
- No custom font or icon set currently exists. Use a restrained enterprise sans fallback and a coherent line-icon family in the redesign; do not use decorative serif, novelty fonts, neon gradients, or marketing-landing-page patterns.

## Three comparison directions

All three directions preserve the same Chinese labels, four target modules, business data hierarchy, table density, workflow semantics, and responsive behavior. The branches are intentionally distinct but remain appropriate for long daily ERP sessions.

### Direction A — 清晰蓝图 / Clear Blueprint

Calm blue enterprise workspace. White panels, very light blue-gray canvas, navy sidebar, blue primary actions, crisp 1px borders, moderate 10px radii, compact but breathable tables, and subtle status colors. Best for broad adoption and low training cost.

### Direction B — 数据工作台 / Data Workbench

High-density operations console. Charcoal sidebar and topbar accents, warm-white workspace, teal primary actions, stronger column grouping, compact KPI strip, more visible filters, table-first layout, and sharper 6px radii. Best for power users who spend most of the day in lists and workflows.

### Direction C — 暖石运营 / Warmstone Operations

Human-centered industrial system. Warm gray canvas, ivory cards, deep ink navigation, terracotta primary action, olive/amber status accents, softer 12px radii, layered section headers, and a more editorial KPI/dashboard hierarchy without sacrificing data density. Best for a company wanting a more distinctive brand character.

## Hard constraints for every generated page

- Keep the actual ERP information architecture and the four requested modules visible together in the comparison set.
- Keep controls functional-looking: search, filter, import/export, refresh, new order, status actions, pagination, create dialog, and detail dialog.
- Use realistic Chinese sample content and values; never show a generic SaaS landing page or unrelated marketing imagery.
- Use only a restrained enterprise sans stack; do not introduce display/serif fonts.
- Use accessible contrast, clear focus/hover states, keyboard-friendly controls, and status labels that do not rely on color alone.
- Use one consistent line-icon family per direction; no emoji glyphs for primary navigation.
- Preserve the ability to map the designs back to Vue + Element Plus, even if the composition is more custom than the current default theme.

