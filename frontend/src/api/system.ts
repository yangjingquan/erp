import { http } from "./http";

export interface OperationLog {
  id: string;
  action: string;
  resource: string;
  username: string;
  created_at: string;
}

export function listOperationLogs() {
  return http.get("/system/operation-logs");
}
