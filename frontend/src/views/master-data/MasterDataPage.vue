<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import type { FormInstance, FormRules } from "element-plus";

import {
  createMasterData,
  exportMasterData,
  getMasterDataErrorMessage,
  importMasterData,
  listMasterData,
  type MasterResource,
} from "../../api/master-data";

export interface MasterColumn {
  prop: string;
  label: string;
  width?: number;
}

export interface MasterFormField {
  prop: string;
  label: string;
  type?: "text" | "number" | "textarea" | "select";
  required?: boolean;
  defaultValue?: string | number;
  options?: Array<{ label: string; value: string }>;
}

const props = withDefaults(
  defineProps<{
    resource: MasterResource;
    title: string;
    columns: MasterColumn[];
    fields: MasterFormField[];
    searchPlaceholder?: string;
  }>(),
  { searchPlaceholder: "编码、名称或关键字" },
);

const rows = ref<Record<string, unknown>[]>([]);
const loading = ref(false);
const submitting = ref(false);
const importing = ref(false);
const keyword = ref("");
const currentPage = ref(1);
const pageSize = ref(10);
const dialogVisible = ref(false);
const formRef = ref<FormInstance>();
const fileInput = ref<HTMLInputElement>();
const form = reactive<Record<string, unknown>>({});

const filteredRows = computed(() => {
  const query = keyword.value.trim().toLocaleLowerCase();
  if (!query) return rows.value;
  return rows.value.filter((row) =>
    Object.values(row).some((value) => String(value ?? "").toLocaleLowerCase().includes(query)),
  );
});

const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value;
  return filteredRows.value.slice(start, start + pageSize.value);
});

const formRules = computed<FormRules>(() => {
  const rules: FormRules = {};
  props.fields.forEach((field) => {
    if (field.required) {
      rules[field.prop] = [{ required: true, message: `请输入${field.label}`, trigger: "blur" }];
    }
  });
  return rules;
});

function ensureResponseSuccess(response: { data: { code: number; msg: string } }) {
  if (response.data.code !== 0) throw new Error(response.data.msg);
}

function resetForm() {
  Object.keys(form).forEach((key) => delete form[key]);
  props.fields.forEach((field) => {
    form[field.prop] = field.defaultValue ?? (field.type === "number" ? 0 : "");
  });
}

async function load() {
  loading.value = true;
  try {
    const response = await listMasterData(props.resource, {
      keyword: keyword.value.trim() || undefined,
      page: currentPage.value,
      pageSize: pageSize.value,
    });
    ensureResponseSuccess(response);
    const data = response.data.data;
    rows.value = Array.isArray(data) ? data : [];
    if (currentPage.value > 1 && pagedRows.value.length === 0 && rows.value.length > 0) {
      currentPage.value = 1;
    }
  } catch (error) {
    ElMessage.error(getMasterDataErrorMessage(error, `${props.title}加载失败`));
    rows.value = [];
  } finally {
    loading.value = false;
  }
}

function search() {
  currentPage.value = 1;
}

function openCreate() {
  resetForm();
  dialogVisible.value = true;
  void nextTick(() => formRef.value?.clearValidate());
}

function closeCreate() {
  if (!submitting.value) dialogVisible.value = false;
}

async function submitCreate() {
  if (!formRef.value) return;
  const valid = await formRef.value.validate().catch(() => false);
  if (!valid) return;

  submitting.value = true;
  try {
    const response = await createMasterData(props.resource, { ...form });
    ensureResponseSuccess(response);
    ElMessage.success("新增成功");
    dialogVisible.value = false;
    await load();
  } catch (error) {
    ElMessage.error(getMasterDataErrorMessage(error, "新增失败，请检查编码或名称是否重复"));
  } finally {
    submitting.value = false;
  }
}

function chooseImportFile() {
  fileInput.value?.click();
}

async function handleImport(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;

  importing.value = true;
  try {
    const response = await importMasterData(props.resource, file);
    ensureResponseSuccess(response);
    const result = response.data.data as {
      created_count?: number;
      skipped_count?: number;
      errors?: Array<{ row?: number; message?: string }>;
    };
    const errors = result?.errors ?? [];
    const summary = `新增${result?.created_count ?? 0}条，跳过${result?.skipped_count ?? 0}条`;
    if (errors.length > 0) {
      ElMessage.warning(`${summary}，${errors.length}条数据有误：${errors[0]?.message ?? "请检查导入文件"}`);
    } else {
      ElMessage.success(`导入完成，${summary}`);
    }
    await load();
  } catch (error) {
    ElMessage.error(getMasterDataErrorMessage(error, "导入失败，请使用系统导出的Excel模板"));
  } finally {
    importing.value = false;
    input.value = "";
  }
}

async function handleExport() {
  try {
    const response = await exportMasterData(props.resource);
    const blob = new Blob([response.data]);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${props.resource}.xlsx`;
    anchor.click();
    URL.revokeObjectURL(url);
    ElMessage.success("导出成功");
  } catch (error) {
    ElMessage.error(getMasterDataErrorMessage(error, "导出失败"));
  }
}

function formatCell(row: Record<string, unknown>, column: MasterColumn) {
  const value = row[column.prop];
  if (column.prop === "status") return value === "active" ? "启用" : value || "停用";
  return value === null || value === undefined || value === "" ? "-" : String(value);
}

function isActiveStatus(row: Record<string, unknown>, column: MasterColumn) {
  return column.prop === "status" && row[column.prop] === "active";
}

function handlePageSizeChange() {
  currentPage.value = 1;
}

onMounted(load);
</script>

<template>
  <section class="master-page">
    <el-page-header :content="props.title" />

    <el-card class="toolbar-card" shadow="never">
      <div class="toolbar">
        <el-input
          v-model="keyword"
          :placeholder="props.searchPlaceholder"
          clearable
          class="search-input"
          @keyup.enter="search"
          @clear="search"
        >
          <template #append><el-button @click="search">搜索</el-button></template>
        </el-input>
        <div class="toolbar-actions">
          <el-button type="primary" @click="openCreate">新增</el-button>
          <el-button :loading="importing" @click="chooseImportFile">导入</el-button>
          <el-button @click="handleExport">导出</el-button>
          <el-button :loading="loading" @click="load">刷新</el-button>
          <input ref="fileInput" type="file" accept=".xlsx,.xls" hidden @change="handleImport" />
        </div>
      </div>
    </el-card>

    <el-card class="table-card" shadow="never">
      <el-table v-loading="loading" :data="pagedRows" stripe row-key="id">
        <el-table-column
          v-for="column in props.columns"
          :key="column.prop"
          :prop="column.prop"
          :label="column.label"
          :width="column.width"
          show-overflow-tooltip
        >
          <template #default="{ row }">
            <el-tag v-if="isActiveStatus(row, column)" type="success">{{ formatCell(row, column) }}</el-tag>
            <span v-else>{{ formatCell(row, column) }}</span>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty description="暂无数据" />
        </template>
      </el-table>
      <div v-if="filteredRows.length > 0" class="pagination-wrap">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          :total="filteredRows.length"
          @size-change="handlePageSizeChange"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="`新增${props.title}`" width="620px" @close="closeCreate">
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="100px">
        <el-form-item v-for="field in props.fields" :key="field.prop" :label="field.label" :prop="field.prop">
          <el-select v-if="field.type === 'select'" v-model="form[field.prop]" style="width: 100%">
            <el-option
              v-for="option in field.options ?? []"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <el-input-number
            v-else-if="field.type === 'number'"
            v-model="form[field.prop] as number"
            :min="0"
            :controls="false"
            style="width: 100%"
          />
          <el-input
            v-else
            v-model="form[field.prop] as string"
            :type="field.type === 'textarea' ? 'textarea' : 'text'"
            :rows="field.type === 'textarea' ? 3 : undefined"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closeCreate">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitCreate">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.master-page { display: flex; flex-direction: column; gap: 16px; }
.toolbar-card, .table-card { border-color: var(--erp-border); background: var(--erp-panel-bg); }
.toolbar { display: flex; align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.search-input { max-width: 440px; }
.toolbar-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.pagination-wrap { display: flex; justify-content: flex-end; padding-top: 16px; }
@media (max-width: 768px) {
  .search-input { max-width: none; width: 100%; }
  .toolbar-actions { width: 100%; }
}
</style>
