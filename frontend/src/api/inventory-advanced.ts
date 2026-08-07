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
