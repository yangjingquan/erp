# Shared UI components

## Component library

- Framework: Vue 3 with `<script setup lang="ts">`
- Component library: Element Plus 2.x, globally registered from `frontend/src/main.ts`
- Styling: Element Plus default CSS plus a small CSS-variable layer in `frontend/src/styles/theme.css`; page-specific styles are mostly scoped CSS in Vue SFCs.
- There is no local Button/Input/Card/Table primitive layer. Shared local components below are small workflow helpers.

## ConfirmDialog

- Source: `frontend/src/components/ConfirmDialog.vue`
- Description: Reusable confirmation dialog exposing an `open()` method and emitting `confirm`.

```vue
<script setup lang="ts">
import { ref } from "vue";

defineProps<{ title?: string; content?: string }>();
const emit = defineEmits<{ confirm: [] }>();
const visible = ref(false);

function open() { visible.value = true; }
function confirm() { visible.value = false; emit("confirm"); }
defineExpose({ open });
</script>

<template>
  <el-dialog v-model="visible" :title="title || '请确认操作'" width="380px">
    <p>{{ content || "该操作可能影响业务数据，是否继续？" }}</p>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="danger" @click="confirm">确认</el-button>
    </template>
  </el-dialog>
</template>
```

## PermissionButton

- Source: `frontend/src/components/PermissionButton.vue`
- Description: Shows an Element Plus button only when the current permission store allows the requested permission.

```vue
<script setup lang="ts">
import { computed } from "vue";
import { usePermissionStore } from "../stores/permission";

const props = defineProps<{ permission: string }>();
const permissions = usePermissionStore();
const allowed = computed(() => permissions.hasPermission(props.permission));
</script>

<template>
  <el-button v-if="allowed"><slot /></el-button>
</template>
```

## ThemeToggle

- Source: `frontend/src/components/ThemeToggle.vue`
- Description: Text action that switches the Pinia-managed light/dark theme.

```vue
<script setup lang="ts">
import { useAppStore } from "../stores/app";

const app = useAppStore();
</script>

<template>
  <el-button text @click="app.toggleTheme">{{ app.theme === "light" ? "暗黑主题" : "浅色主题" }}</el-button>
</template>
```

