import { http } from "./http";

export type InventoryTransferPayload = {
  from_warehouse_id: string;
  to_warehouse_id: string;
  items: Array<{ material_id: string; quantity: number; unit_cost?: number }>;
};

export type InventoryCountPayload = {
  warehouse_id: string;
  items: Array<{ material_id: string; actual_quantity: number }>;
};

export function listInventoryStock(params?: Record<string, unknown>) {
  return http.get("/inventory/stock", { params });
}

export function listInventoryTransactions(params?: Record<string, unknown>) {
  return http.get("/inventory/transactions", { params });
}

export function listInventoryTransfers(params?: Record<string, unknown>) {
  return http.get("/inventory/transfers", { params });
}

export function listInventoryCounts(params?: Record<string, unknown>) {
  return http.get("/inventory/counts", { params });
}

export function listInventoryWarnings(params?: Record<string, unknown>) {
  return http.get("/inventory/warnings", { params });
}

export function createInventoryTransfer(payload: InventoryTransferPayload) {
  return http.post("/inventory/transfers", payload);
}

export function approveInventoryTransfer(transferId: string) {
  return http.post(`/inventory/transfers/${transferId}/approve`);
}

export function completeInventoryTransfer(transferId: string) {
  return http.post(`/inventory/transfers/${transferId}/complete`);
}

export function createInventoryCount(payload: InventoryCountPayload) {
  return http.post("/inventory/counts", payload);
}

export function completeInventoryCount(countId: string) {
  return http.post(`/inventory/counts/${countId}/complete`);
}
