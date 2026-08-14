import { http } from "./http";

export function listReceivables(params?: Record<string, unknown>) {
  return http.get("/finance/receivables", { params });
}

export function listPayables(params?: Record<string, unknown>) {
  return http.get("/finance/payables", { params });
}

export function listReceipts(params?: Record<string, unknown>) {
  return http.get("/finance/receipts", { params });
}

export function listPayments(params?: Record<string, unknown>) {
  return http.get("/finance/payments", { params });
}

export function listExpenses(params?: Record<string, unknown>) {
  return http.get("/finance/expenses", { params });
}

export function listVouchers(params?: Record<string, unknown>) {
  return http.get("/finance/vouchers", { params });
}

export const listFinanceAccounts = (params?: { page?: number; page_size?: number }) => http.get("/finance/accounts", { params });
export const createFinanceAccount = (payload: unknown) => http.post("/finance/accounts", payload);
export const listAccountingDimensions = () => http.get("/finance/dimensions");
export const createAccountingDimension = (payload: unknown) => http.post("/finance/dimensions", payload);
export const listFiscalPeriods = () => http.get("/finance/periods");
export const createFiscalPeriod = (payload: unknown) => http.post("/finance/periods", payload);
export const closeFiscalPeriod = (period: string) => http.post(`/finance/periods/${period}/close`);
export const reopenFiscalPeriod = (period: string) => http.post(`/finance/periods/${period}/reopen`);
export const listBankAccounts = () => http.get("/finance/bank-accounts");
export const createBankAccount = (payload: unknown) => http.post("/finance/bank-accounts", payload);
export const listAssets = () => http.get("/finance/assets");
export const createAsset = (payload: unknown) => http.post("/finance/assets", payload);
export const runAssetDepreciation = (assetId: string, period: string) => http.post(`/finance/assets/${assetId}/depreciation`, { period });
export const createManualVoucher = (payload: unknown) => http.post("/finance/vouchers", payload);
export const postVoucher = (voucherId: string) => http.post(`/finance/vouchers/${voucherId}/post`);
export const reverseVoucher = (voucherId: string) => http.post(`/finance/vouchers/${voucherId}/reverse`);
export const listCurrencies = () => http.get("/finance/currencies");
export const createCurrency = (payload: unknown) => http.post("/finance/currencies", payload);
export const listExchangeRates = (currency?: string) => http.get("/finance/exchange-rates", { params: currency ? { currency } : undefined });
export const upsertExchangeRate = (payload: unknown) => http.post("/finance/exchange-rates", payload);
export const convertCurrency = (params: Record<string, unknown>) => http.get("/finance/currency-convert", { params });
export const getAgingReport = (type: "ar" | "ap", asOf?: string) => http.get(`/finance/aging/${type}`, { params: asOf ? { as_of: asOf } : undefined });
export const listBudgets = (period?: string) => http.get("/finance/budgets", { params: period ? { period } : undefined });
export const createBudget = (payload: unknown) => http.post("/finance/budgets", payload);
export const approveBudget = (id: string) => http.post(`/finance/budgets/${id}/approve`);
export const listCashForecasts = (params?: Record<string, unknown>) => http.get("/finance/cash-forecasts", { params });
export const createCashForecast = (payload: unknown) => http.post("/finance/cash-forecasts", payload);
export const listReconciliationStatements = (statementType?: string) => http.get("/finance/reconciliation-statements", { params: statementType ? { statement_type: statementType } : undefined });
export const createReconciliationStatement = (payload: unknown) => http.post("/finance/reconciliation-statements", payload);
export const listBankStatements = () => http.get("/finance/bank-statements");
export const createBankStatement = (payload: unknown) => http.post("/finance/bank-statements", payload);
export const autoMatchBankStatement = (id: string) => http.post(`/finance/bank-statements/${id}/auto-match`);
export const matchBankStatementLine = (id: string, payload: unknown) => http.post(`/finance/bank-statement-lines/${id}/match`, payload);
export const getCloseChecklist = (period: string) => http.get(`/finance/periods/${period}/close-checklist`);
export const updateCloseChecklist = (id: string, payload: unknown) => http.post(`/finance/close-checklist/${id}`, payload);

export function createReceipt(payload: { customer_id: string; amount: number }) {
  return http.post("/finance/receipts", payload);
}

export function createPayment(payload: { supplier_id: string; amount: number }) {
  return http.post("/finance/payments", payload);
}

export function createExpense(payload: { expense_type: string; amount: number; description?: string }) {
  return http.post("/finance/expenses", payload);
}

export function approveExpense(expenseId: string) {
  return http.post(`/finance/expenses/${expenseId}/approve`);
}

export function settleExpense(expenseId: string) {
  return http.post(`/finance/expenses/${expenseId}/settle`);
}

export function generateVoucher(sourceType: string, sourceId: string) {
  return http.post(`/finance/vouchers/${sourceType}/${sourceId}`);
}

export function reconcileReceipt(receiptId: string, payload: { receivable_id: string; amount: number }) {
  return http.post(`/finance/receipts/${receiptId}/reconcile`, payload);
}

export function reconcilePayment(paymentId: string, payload: { payable_id: string; amount: number }) {
  return http.post(`/finance/payments/${paymentId}/reconcile`, payload);
}
