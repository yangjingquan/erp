# Extractable Superdesign components

## AdminLayout

- Source: `frontend/src/layouts/AdminLayout.vue`
- Category: `layout`
- Description: Full authenticated ERP shell with expandable left navigation, global search, theme control, user menu, navigation tab, and router content.
- Extractable props: `activeItem` (string, default `/dashboard`), `sidebarCollapsed` (boolean, default false), `userName` (string, default `用户`).
- Hardcoded: ERP 管理系统 brand text, Chinese module labels, menu hierarchy, search placeholder, theme labels, and all current Element Plus layout styling.

## ConfirmDialog

- Source: `frontend/src/components/ConfirmDialog.vue`
- Category: `basic`
- Description: Confirmation dialog for potentially destructive business actions.
- Extractable props: `title` (string, default `请确认操作`), `content` (string, default `该操作可能影响业务数据，是否继续？`).
- Hardcoded: Element Plus dialog/button styling and Chinese action labels.

## PermissionButton

- Source: `frontend/src/components/PermissionButton.vue`
- Category: `basic`
- Description: Permission-gated action button wrapper.
- Extractable props: `permission` (string, default `system:view`).
- Hardcoded: Element Plus button styling; slot content remains page-provided.

## ThemeToggle

- Source: `frontend/src/components/ThemeToggle.vue`
- Category: `basic`
- Description: Light/dark theme switch action.
- Extractable props: none; state is read from the Pinia app store.
- Hardcoded: Chinese theme labels and text-button treatment.

