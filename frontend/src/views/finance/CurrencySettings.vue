<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { createCurrency, listCurrencies, listExchangeRates, upsertExchangeRate } from "../../api/finance";
import { localDateString } from "../../utils/time";

type Row = Record<string, any>;
const currencies = ref<Row[]>([]);
const rates = ref<Row[]>([]);
const loading = ref(false);
const saving = ref(false);
const dialog = ref<"currency" | "rate" | "">("");
const currencyForm = reactive({ code: "", name: "", symbol: "", decimal_places: 2, is_base: false });
const rateForm = reactive({ base_currency: "", quote_currency: "", rate_date: localDateString(), rate: 1, source: "manual" });

function unwrap(response: any) {
  if (response?.data?.code !== 0) throw new Error(response?.data?.msg || "接口返回失败");
  return response.data.data;
}
async function load() {
  loading.value = true;
  try {
    currencies.value = unwrap(await listCurrencies()) || [];
    rates.value = unwrap(await listExchangeRates()) || [];
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "多币种数据加载失败"); }
  finally { loading.value = false; }
}
function openCurrency() { Object.assign(currencyForm, { code: "", name: "", symbol: "", decimal_places: 2, is_base: currencies.value.length === 0 }); dialog.value = "currency"; }
function openRate() { Object.assign(rateForm, { base_currency: currencies.value.find((item) => item.is_base)?.code || currencies.value[0]?.code || "", quote_currency: currencies.value.find((item) => !item.is_base)?.code || "", rate_date: localDateString(), rate: 1, source: "manual" }); dialog.value = "rate"; }
async function save() {
  saving.value = true;
  try {
    if (dialog.value === "currency") unwrap(await createCurrency({ ...currencyForm }));
    if (dialog.value === "rate") unwrap(await upsertExchangeRate({ ...rateForm }));
    dialog.value = ""; ElMessage.success("保存成功"); await load();
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : "保存失败"); }
  finally { saving.value = false; }
}
onMounted(load);
</script>

<template>
  <section class="page-stack">
    <header class="page-heading"><div><small>MULTI-CURRENCY</small><h1>多币种与汇率</h1><p>维护组织币种档案、本位币和按日汇率，供财务换算使用。</p></div><el-button :loading="loading" @click="load">刷新</el-button></header>
    <el-card v-loading="loading" shadow="never">
      <el-tabs>
        <el-tab-pane label="币种档案"><div class="toolbar"><el-button type="primary" @click="openCurrency">新增币种</el-button></div><el-table :data="currencies" stripe><el-table-column prop="code" label="编码" width="110" /><el-table-column prop="name" label="名称" /><el-table-column prop="symbol" label="符号" width="90" /><el-table-column prop="decimal_places" label="小数位" width="90" /><el-table-column label="本位币" width="90"><template #default="scope">{{ scope.row.is_base ? '是' : '否' }}</template></el-table-column><el-table-column prop="status" label="状态" width="100" /><template #empty><el-empty description="暂无币种" /></template></el-table></el-tab-pane>
        <el-tab-pane label="汇率"><div class="toolbar"><el-button type="primary" :disabled="currencies.length < 2" @click="openRate">新增汇率</el-button></div><el-table :data="rates" stripe><el-table-column prop="rate_date" label="日期" width="130" /><el-table-column label="币种对" width="180"><template #default="scope">{{ scope.row.base_currency }} / {{ scope.row.quote_currency }}</template></el-table-column><el-table-column prop="rate" label="汇率" /><el-table-column prop="source" label="来源" /><template #empty><el-empty description="暂无汇率" /></template></el-table></el-tab-pane>
      </el-tabs>
    </el-card>
    <el-dialog :model-value="Boolean(dialog)" :title="dialog === 'currency' ? '新增币种' : '新增汇率'" width="520px" @update:model-value="(visible: boolean) => { if (!visible) dialog = '' }">
      <el-form v-if="dialog === 'currency'" label-width="90px"><el-form-item label="币种编码" required><el-input v-model="currencyForm.code" maxlength="8" placeholder="CNY" /></el-form-item><el-form-item label="名称" required><el-input v-model="currencyForm.name" placeholder="人民币" /></el-form-item><el-form-item label="符号"><el-input v-model="currencyForm.symbol" placeholder="¥" /></el-form-item><el-form-item label="小数位"><el-input-number v-model="currencyForm.decimal_places" :min="0" :max="6" /></el-form-item><el-form-item label="本位币"><el-switch v-model="currencyForm.is_base" /></el-form-item></el-form>
      <el-form v-else label-width="90px"><el-form-item label="基础币种" required><el-select v-model="rateForm.base_currency" filterable><el-option v-for="item in currencies" :key="item.code" :label="`${item.code} · ${item.name}`" :value="item.code" /></el-select></el-form-item><el-form-item label="目标币种" required><el-select v-model="rateForm.quote_currency" filterable><el-option v-for="item in currencies" :key="item.code" :label="`${item.code} · ${item.name}`" :value="item.code" /></el-select></el-form-item><el-form-item label="日期" required><el-date-picker v-model="rateForm.rate_date" value-format="YYYY-MM-DD" /></el-form-item><el-form-item label="汇率" required><el-input-number v-model="rateForm.rate" :min="0.00000001" :precision="8" /></el-form-item><el-form-item label="来源"><el-input v-model="rateForm.source" /></el-form-item></el-form>
      <template #footer><el-button @click="dialog = ''">取消</el-button><el-button type="primary" :loading="saving" @click="save">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<style scoped>.page-stack { display: flex; flex-direction: column; gap: 16px; }.page-heading { display: flex; justify-content: space-between; align-items: flex-end; }.page-heading small { color: var(--erp-muted-text); letter-spacing: .08em; }.page-heading h1 { margin: 4px 0; }.page-heading p { margin: 0; color: var(--erp-muted-text); }.toolbar { display: flex; justify-content: flex-end; margin-bottom: 12px; }</style>
