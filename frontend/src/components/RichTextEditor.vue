<script setup lang="ts">
import { onMounted, ref, watch } from "vue";

const props = defineProps<{ modelValue: string; height?: string }>();
const emit = defineEmits<{ "update:modelValue": [value: string] }>();

const editor = ref<HTMLElement | null>(null);
const focused = ref(false);

const placeholders = [
  { label: "单据号", value: "{{ doc_no }}" },
  { label: "标题", value: "{{ title }}" },
  { label: "客户/供应商", value: "{{ party_name }}" },
  { label: "金额", value: "{{ amount }}" },
  { label: "单据日期", value: "{{ document_date }}" },
  { label: "状态", value: "{{ status }}" },
  { label: "备注", value: "{{ remark }}" },
];

function emitChange() {
  if (editor.value) emit("update:modelValue", editor.value.innerHTML);
}

function sync() {
  if (editor.value && !focused.value && editor.value.innerHTML !== (props.modelValue || "")) {
    editor.value.innerHTML = props.modelValue || "";
  }
}

function exec(command: string, value?: string) {
  editor.value?.focus();
  document.execCommand(command, false, value);
  emitChange();
}

function insertPlaceholder(value: string) {
  exec("insertText", value);
}

watch(() => props.modelValue, sync);
onMounted(sync);
</script>

<template>
  <div class="rte">
    <div class="rte-toolbar">
      <el-button-group>
        <el-button size="small" title="撤销" @click="exec('undo')">↺</el-button>
        <el-button size="small" title="重做" @click="exec('redo')">↻</el-button>
      </el-button-group>
      <el-button-group>
        <el-button size="small" title="标题1" @click="exec('formatBlock', 'H1')">H1</el-button>
        <el-button size="small" title="标题2" @click="exec('formatBlock', 'H2')">H2</el-button>
        <el-button size="small" title="标题3" @click="exec('formatBlock', 'H3')">H3</el-button>
        <el-button size="small" title="正文" @click="exec('formatBlock', 'P')">正文</el-button>
      </el-button-group>
      <el-button-group>
        <el-button size="small" title="加粗" @click="exec('bold')"><b>B</b></el-button>
        <el-button size="small" title="斜体" @click="exec('italic')"><i>I</i></el-button>
        <el-button size="small" title="下划线" @click="exec('underline')"><u>U</u></el-button>
        <el-button size="small" title="删除线" @click="exec('strikeThrough')"><s>S</s></el-button>
      </el-button-group>
      <el-button-group>
        <el-button size="small" title="无序列表" @click="exec('insertUnorderedList')">• 列表</el-button>
        <el-button size="small" title="有序列表" @click="exec('insertOrderedList')">1. 列表</el-button>
        <el-button size="small" title="引用" @click="exec('formatBlock', 'BLOCKQUOTE')">引用</el-button>
      </el-button-group>
      <el-button-group>
        <el-button size="small" title="左对齐" @click="exec('justifyLeft')">左</el-button>
        <el-button size="small" title="居中" @click="exec('justifyCenter')">中</el-button>
        <el-button size="small" title="右对齐" @click="exec('justifyRight')">右</el-button>
      </el-button-group>
      <el-button-group>
        <el-button size="small" title="字体颜色"><input type="color" class="rte-color" @input="exec('foreColor', ($event.target as HTMLInputElement).value)" /></el-button>
        <el-button size="small" title="清除格式" @click="exec('removeFormat')">清除格式</el-button>
      </el-button-group>
      <el-dropdown class="rte-field" @command="insertPlaceholder">
        <el-button size="small" type="primary" plain>插入字段</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item v-for="item in placeholders" :key="item.value" :command="item.value">{{ item.label }} · {{ item.value }}</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
    <div
      ref="editor"
      class="rte-editor"
      contenteditable="true"
      :style="{ minHeight: height || '260px' }"
      @focus="focused = true"
      @blur="focused = false; emitChange()"
      @input="emitChange"
    />
  </div>
</template>

<style scoped>
.rte { border: 1px solid var(--erp-border); border-radius: 8px; overflow: hidden; }
.rte-toolbar { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; padding: 8px; border-bottom: 1px solid var(--erp-border); background: var(--erp-panel-soft); }
.rte-toolbar :deep(.el-button) { margin: 0; }
.rte-field { margin-left: auto; }
.rte-color { width: 20px; height: 20px; padding: 0; border: 0; background: transparent; cursor: pointer; }
.rte-editor { padding: 12px; outline: none; overflow-y: auto; line-height: 1.7; background: var(--erp-panel-bg); }
.rte-editor:focus { background: #fff; }
.rte-editor :deep(h1) { font-size: 22px; }
.rte-editor :deep(h2) { font-size: 18px; }
.rte-editor :deep(h3) { font-size: 16px; }
.rte-editor :deep(blockquote) { margin: 8px 0; padding: 4px 12px; border-left: 3px solid var(--erp-primary); color: var(--erp-muted-text); }
.rte-editor :deep(ul), .rte-editor :deep(ol) { padding-left: 22px; }
</style>
