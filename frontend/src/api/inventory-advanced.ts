import { http } from "./http";

export type ScanTask = {
  action: "receive" | "fill" | "return" | "count";
  document_id: string;
  document_no: string;
  warehouse_id: string;
  status: string;
};

export type ScanProcessPayload = {
  scan_id: string;
  action: "receive" | "fill" | "return" | "count";
  document_id: string;
  warehouse_id: string;
  location_id?: string;
  batch_id?: string;
  material_id?: string;
  quantity?: number;
  actual_quantity?: number;
  items?: Array<{ material_id: string; quantity: number }>;
  unit_cost?: number;
};

export function createScanToken() {
  return http.post("/inventory/advanced/scan/token");
}

export function listScanTasks() {
  return http.get("/inventory/advanced/scan/tasks");
}

export function processScan(token: string, payload: ScanProcessPayload) {
  return http.post("/inventory/advanced/scan/process", { token, ...payload });
}

export function listLocations(warehouseId?: string) { return http.get("/inventory/advanced/locations", { params: warehouseId ? { warehouse_id: warehouseId } : undefined }); }
export function createLocation(warehouseId: string, payload: { code: string; name: string; status?: string }) { return http.post("/inventory/advanced/locations", payload, { params: { warehouse_id: warehouseId } }); }
export function updateLocation(locationId: string, payload: { code: string; name: string; status?: string }) { return http.put(`/inventory/advanced/locations/${locationId}`, payload); }
export function deleteLocation(locationId: string) { return http.delete(`/inventory/advanced/locations/${locationId}`); }
export function listBatches(materialId?: string) { return http.get("/inventory/advanced/batches", { params: { material_id: materialId } }); }
export function createBatch(materialId: string, payload: { batch_no: string; production_date?: string | null; expiry_date?: string | null; status?: string }) { return http.post("/inventory/advanced/batches", payload, { params: { material_id: materialId } }); }
export function updateBatch(batchId: string, payload: { batch_no: string; production_date?: string | null; expiry_date?: string | null; status?: string }) { return http.put(`/inventory/advanced/batches/${batchId}`, payload); }
export function deleteBatch(batchId: string) { return http.delete(`/inventory/advanced/batches/${batchId}`); }
export function listReservations(status?: string) { return http.get("/inventory/advanced/reservations", { params: { status } }); }
export function createReservation(payload: unknown) { return http.post("/inventory/advanced/reservations", payload); }
export function releaseReservation(id: string) { return http.post(`/inventory/advanced/reservations/${id}/release`); }
export function listTraceEvents(params?: { material_id?: string; batch_id?: string }) { return http.get("/inventory/advanced/trace", { params }); }
