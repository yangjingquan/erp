<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { approveBom, createBom, disableBom, getBomTree, importBoms, listBoms, submitBom, updateBom } from "../../api/production";
import { useMasterOptions } from "../../composables/useMasterOptions";
import { useClientPagination } from "../../composables/useClientPagination";
import { localDateString } from "../../utils/time";

type Row = Record<string, any>;
const rows = ref<Row[]>([]);
const { pagedRows, page, pageSize, total, updatePageSize } = useClientPagination(rows);
const loading = ref(false);
const saving = ref(false);
const actionLoading = ref<string | null>(null);
const dialogVisible = ref(false);
const importVisible = ref(false);
const treeVisible = ref(false);
const editingId = ref("");
const tree = ref<Row | null>(null);
const importText = ref("[]");
const form = reactive({ material_id: "", bom_version: "1.0", effective_from: localDateString(), effective_to: "", items: [{ material_id: "", quantity: 1, scrap_rate: 0, issue_operation_id: "", is_phantom: false }] });
const { materials, loadOptions } = useMasterOptions();
const statusLabels: Record<string, string> = { draft: "草稿", submitted: "已提交", approved: "已审核", disabled: "已停用" };
function statusLabel(status: string) { return statusLabels[status] || status || "未知"; }
function statusTagType(status: string) { return ({ draft: "info", submitted: "warning", approved: "success", disabled: "info" } as Record<string, string>)[status] || "info"; }
function materialLabel(materialId: unknown) { const value = String(materialId || ""); return materials.value.find((option) => option.value === value)?.label || value || "-"; }
function unwrap(response: any) { if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "BOM 接口返回失败"); return response.data.data; }
async function load() { loading.value = true; try { rows.value = (unwrap(await listBoms()) || []) as Row[]; } catch (error) { ElMessage.error(error instanceof Error ? error.message : "BOM 列表加载失败"); } finally { loading.value = false; } }
function reset() { Object.assign(form, { material_id: "", bom_version: "1.0", effective_from: localDateString(), effective_to: "" }); form.items = [{ material_id: "", quantity: 1, scrap_rate: 0, issue_operation_id: "", is_phantom: false }]; }
function openCreate() { reset(); editingId.value = ""; dialogVisible.value = true; }
function edit(row: Row) { Object.assign(form, { material_id: row.material_id, bom_version: row.bom_version, effective_from: row.effective_from, effective_to: row.effective_to || "" }); form.items = (row.items || []).map((item: Row) => ({ material_id: item.material_id, quantity: Number(item.quantity), scrap_rate: Number(item.scrap_rate || 0), issue_operation_id: item.issue_operation_id || "", is_phantom: Boolean(item.is_phantom) })); editingId.value = String(row.id); dialogVisible.value = true; }
function copy(row: Row) { edit(row); editingId.value = ""; form.bom_version = `${row.bom_version}-copy`; }
async function openTree(row: Row) { try { tree.value = unwrap(await getBomTree(String(row.id))); treeVisible.value = true; } catch (error) { ElMessage.error(error instanceof Error ? error.message : "BOM 树加载失败"); } }
function addItem() { form.items.push({ material_id: "", quantity: 1, scrap_rate: 0, issue_operation_id: "", is_phantom: false }); }
function removeItem(index: number) { if (form.items.length > 1) form.items.splice(index, 1); }
async function save() { if (!form.material_id || form.items.some((item) => !item.material_id || item.quantity <= 0) || !form.effective_from) { ElMessage.warning("请填写成品、至少一条有效组件、数量和生效日期"); return; } saving.value = true; try { unwrap(editingId.value ? await updateBom(editingId.value, { ...form, effective_to: form.effective_to || null }) : await createBom({ ...form, effective_to: form.effective_to || null })); ElMessage.success(editingId.value ? "BOM 已更新" : "BOM 已创建"); dialogVisible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "BOM 保存失败"); } finally { saving.value = false; } }
async function doImport() { try { const payload = JSON.parse(importText.value); if (!Array.isArray(payload) || !payload.length) throw new Error("请输入 BOM 数组"); unwrap(await importBoms(payload)); ElMessage.success("BOM 批量导入完成"); importVisible.value = false; await load(); } catch (error) { ElMessage.error(error instanceof Error ? error.message : "BOM 导入失败"); } }
async function action(row: Row, kind: "submit" | "approve" | "disable") { const id = String(row.id || ""); if (!id) return; const labels = { submit: "提交 BOM", approve: "审核 BOM", disable: "停用 BOM" }; try { await ElMessageBox.confirm(`确认${labels[kind]}“${row.bom_version || id}”吗？`, "操作确认", { type: "warning" }); actionLoading.value = id; unwrap(kind === "submit" ? await submitBom(id) : kind === "approve" ? await approveBom(id) : await disableBom(id)); ElMessage.success(`${labels[kind]}成功`); await load(); } catch (error: any) { if (error !== "cancel" && error !== "close") ElMessage.error(error instanceof Error ? error.message : `${labels[kind]}失败`); } finally { actionLoading.value = null; } }
onMounted(async () => { await Promise.all([load(), loadOptions(["materials"])]); });
</script>

<template>
  <section class="page-stack">
    <el-page-header content="BOM 管理" />
    <el-space><el-button type="primary" @click="openCreate">新建 BOM</el-button><el-button @click="importVisible = true">批量导入</el-button><el-button :loading="loading" @click="load">刷新</el-button></el-space>
    <el-alert title="支持多层组件、损耗率、虚拟件、BOM 树查看和草稿编辑；只有审核通过的 BOM 才能参与 MRP 和生产工单。" type="info" show-icon />
    <el-table v-loading="loading" :data="pagedRows" stripe width="100%" fit :header-cell-style="{ textAlign: 'center' }" :cell-style="{ textAlign: 'center' }">
      <el-table-column prop="bom_version" label="版本" width="100" />
      <el-table-column label="成品物料" min-width="180"><template #default="scope">{{ materialLabel(scope.row.material_id) }}</template></el-table-column>
      <el-table-column prop="effective_from" label="生效日期" width="130" /><el-table-column label="失效日期" width="130"><template #default="scope">{{ scope.row.effective_to || "长期有效" }}</template></el-table-column>
      <el-table-column label="状态" width="110"><template #default="scope"><el-tag class="status-tag" :type="statusTagType(scope.row.status)">{{ statusLabel(scope.row.status) }}</el-tag></template></el-table-column>
      <el-table-column label="组件数" width="90"><template #default="scope">{{ scope.row.items?.length || 0 }}</template></el-table-column>
      <el-table-column label="操作" min-width="300"><template #default="scope"><el-button link type="primary" @click="openTree(scope.row)">查看树</el-button><el-button v-if="scope.row.status === 'draft'" link type="primary" @click="edit(scope.row)">编辑</el-button><el-button link @click="copy(scope.row)">复制</el-button><el-button v-if="scope.row.status === 'draft'" link type="warning" :loading="actionLoading === scope.row.id" @click="action(scope.row, 'submit')">提交</el-button><el-button v-if="scope.row.status === 'submitted'" link type="success" :loading="actionLoading === scope.row.id" @click="action(scope.row, 'approve')">审核</el-button><el-button v-if="scope.row.status === 'approved'" link type="warning" :loading="actionLoading === scope.row.id" @click="action(scope.row, 'disable')">停用</el-button></template></el-table-column>
      <template #empty><el-empty description="暂无 BOM" /></template>
    </el-table>
    <ClientPagination v-model:page="page" v-model:page-size="pageSize" :total="total" @update:page-size="updatePageSize" />
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑 BOM' : '新建 BOM'" width="960px"><el-form label-width="100px"><el-form-item label="成品物料" required><el-select v-model="form.material_id" filterable clearable style="width: 100%"><el-option v-for="option in materials" :key="option.value" v-bind="option" /></el-select></el-form-item><el-form-item label="BOM 版本" required><el-input v-model="form.bom_version" /></el-form-item><el-form-item label="生效日期" required><el-date-picker v-model="form.effective_from" type="date" value-format="YYYY-MM-DD" /></el-form-item><el-form-item label="失效日期"><el-date-picker v-model="form.effective_to" type="date" value-format="YYYY-MM-DD" /></el-form-item><el-divider content-position="left">多层组件明细</el-divider><div class="bom-lines"><div v-for="(item, index) in form.items" :key="index" class="bom-line"><span class="line-no">{{ index + 1 }}</span><el-select v-model="item.material_id" filterable clearable placeholder="组件物料"><el-option v-for="option in materials" :key="option.value" v-bind="option" /></el-select><el-input-number v-model="item.quantity" :min="0.000001" :precision="6" controls-position="right" /><el-input-number v-model="item.scrap_rate" :min="0" :max="0.9999" :precision="4" controls-position="right" placeholder="损耗率" /><el-input v-model="item.issue_operation_id" placeholder="绑定工序 ID（可选）" /><el-checkbox v-model="item.is_phantom">虚拟件</el-checkbox><el-button link type="danger" :disabled="form.items.length === 1" @click="removeItem(index)">删除</el-button></div><el-button plain @click="addItem">+ 添加组件行</el-button></div></el-form><template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存 BOM</el-button></template></el-dialog>
    <el-dialog v-model="importVisible" title="批量导入 BOM" width="720px"><el-alert title="JSON 数组格式：[{ material_id, bom_version, effective_from, items: [{ material_id, quantity, scrap_rate, is_phantom }] }]" type="info" show-icon /><el-input v-model="importText" type="textarea" :rows="12" /><template #footer><el-button @click="importVisible = false">取消</el-button><el-button type="primary" @click="doImport">导入</el-button></template></el-dialog>
    <el-drawer v-model="treeVisible" title="BOM 多层结构" size="520px"><el-tree v-if="tree" :data="[tree]" node-key="id" default-expand-all><template #default="scope"><span>{{ materialLabel(scope.data.material_id) }} × {{ scope.data.quantity || 1 }}<small v-if="scope.data.scrap_rate">（损耗 {{ scope.data.scrap_rate }}）</small></span></template></el-tree><el-empty v-else description="暂无结构" /></el-drawer>
  </section>
</template>

<style scoped>
.page-stack { display: flex; flex-direction: column; gap: 16px; }
.bom-lines { display: flex; flex-direction: column; gap: 10px; width: 100%; }
.bom-line { display: grid; grid-template-columns: 32px 1.5fr 130px 120px 1fr auto auto; gap: 8px; align-items: center; }
.line-no { color: var(--erp-muted-text); text-align: center; }
.status-tag { border-width: 1px; }
@media (max-width: 900px) { .bom-line { grid-template-columns: 28px 1fr 1fr; } }
</style>
