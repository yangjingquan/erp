import { http } from "./http";

export type PurchaseOrderPayload = {
  supplier_id: string;
  order_date?: string;
  expected_date?: string | null;
  items: Array<{
    material_id: string;
    quantity: number;
    unit_price: number;
    warehouse_id?: string | null;
    tax_rate?: number;
  }>;
};

export function listPurchaseOrders(params?: Record<string, unknown>) {
  return http.get("/purchase/orders", { params });
}

export function createPurchaseOrder(payload: PurchaseOrderPayload) {
  return http.post("/purchase/orders", payload);
}

export function updatePurchaseOrder(orderId: string, payload: PurchaseOrderPayload) {
  return http.put(`/purchase/orders/${orderId}`, payload);
}

export function deletePurchaseOrder(orderId: string) {
  return http.delete(`/purchase/orders/${orderId}`);
}

export function submitPurchaseOrder(orderId: string) {
  return http.post(`/purchase/orders/${orderId}/submit`);
}

export function approvePurchaseOrder(orderId: string) {
  return http.post(`/purchase/orders/${orderId}/approve`);
}

export function createPurchaseReceipt(orderId: string) {
  return http.post(`/purchase/orders/${orderId}/create-receipt`);
}

export function listPurchaseReceipts() {
  return http.get("/purchase/receipts");
}

export function listPurchaseRequests() { return http.get("/purchase/requests"); }
export function createPurchaseRequest(payload: Record<string, unknown>) { return http.post("/purchase/requests", payload); }
export function updatePurchaseRequest(id: string, payload: Record<string, unknown>) { return http.put(`/purchase/requests/${id}`, payload); }
export function deletePurchaseRequest(id: string) { return http.delete(`/purchase/requests/${id}`); }
export function requestAction(id: string, action: "submit" | "approve" | "reject") { return http.post(`/purchase/requests/${id}/${action}`); }
export function listPurchaseReturns() { return http.get("/purchase/returns"); }
export function createPurchaseReturn(payload: Record<string, unknown>) { return http.post("/purchase/returns", payload); }
export function updatePurchaseReturn(id: string, payload: Record<string, unknown>) { return http.put(`/purchase/returns/${id}`, payload); }
export function deletePurchaseReturn(id: string) { return http.delete(`/purchase/returns/${id}`); }
export function submitPurchaseReturn(id: string) { return http.post(`/purchase/returns/${id}/submit`); }
export function completePurchaseReturn(id: string) { return http.post(`/purchase/returns/${id}/complete`); }
