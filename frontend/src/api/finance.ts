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
