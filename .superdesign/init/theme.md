# Theme and visual baseline

## Compact token summary

- Framework/UI: Vue 3, Element Plus 2.9.8, ECharts 5.6.0.
- Font: browser/system default; no custom font declared.
- Light canvas: `--erp-page-bg #f4f7fb`, `--erp-panel-bg #ffffff`, `--erp-sidebar-bg #18253d`, `--erp-border #e5e7eb`, `--erp-text #1f2937`, `--erp-muted-text #64748b`.
- Dark canvas: `--erp-page-bg #0f172a`, `--erp-panel-bg #172033`, `--erp-sidebar-bg #090f1d`, `--erp-border #334155`, `--erp-text #e5e7eb`, `--erp-muted-text #94a3b8`.
- Layout: sidebar 228px expanded / 64px collapsed; top header is Element Plus `el-header`; main content uses page background.
- Common spacing: 12–16px page gaps; `el-card`, `el-table`, `el-dialog`, `el-button`, `el-input` use Element Plus defaults.
- Shape/shadow: Element Plus defaults; no custom radius/shadow tokens.
- Responsive: material toolbar wraps under 768px; sidebar is manually collapsible.

## Current visual language

The current application is a utilitarian enterprise CRUD shell: navy vertical navigation, white topbar, pale blue-gray workspace, small page header, cards with minimal borders, dense striped tables, and primary blue actions. Icons are mostly text glyphs or Element Plus defaults; the sidebar currently has no explicit icon system. Light/dark mode is controlled through `document.documentElement.dataset.theme`.

## Full source: `frontend/src/styles/theme.css`

```css
:root {
  --erp-page-bg: #f4f7fb;
  --erp-panel-bg: #ffffff;
  --erp-sidebar-bg: #18253d;
  --erp-border: #e5e7eb;
  --erp-text: #1f2937;
  --erp-muted-text: #64748b;
}

:root[data-theme="dark"] {
  --erp-page-bg: #0f172a;
  --erp-panel-bg: #172033;
  --erp-sidebar-bg: #090f1d;
  --erp-border: #334155;
  --erp-text: #e5e7eb;
  --erp-muted-text: #94a3b8;
}

body { margin: 0; color: var(--erp-text); background: var(--erp-page-bg); }
```

## Dependency entry

`frontend/src/main.ts` imports `element-plus/dist/index.css` globally and then imports `frontend/src/styles/theme.css`.

