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

export function submitPurchaseOrder(orderId: string) {
  return http.post(`/purchase/orders/${orderId}/submit`);
}

export function approvePurchaseOrder(orderId: string) {
  return http.post(`/purchase/orders/${orderId}/approve`);
}

export function createPurchaseReceipt(orderId: string) {
  return http.post(`/purchase/orders/${orderId}/create-receipt`);
}

export function listPurchaseRequests() { return http.get("/purchase/requests"); }
export function createPurchaseRequest(payload: Record<string, unknown>) { return http.post("/purchase/requests", payload); }
export function requestAction(id: string, action: "submit" | "approve" | "reject") { return http.post(`/purchase/requests/${id}/${action}`); }
export function listPurchaseReturns() { return http.get("/purchase/returns"); }
export function createPurchaseReturn(payload: Record<string, unknown>) { return http.post("/purchase/returns", payload); }
