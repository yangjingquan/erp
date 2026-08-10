import { http } from "./http";

export interface OperationLog {
  id: string;
  action: string;
  resource: string;
  username: string;
  created_at: string;
}

export interface OperationLogPage {
  items: OperationLog[];
  total: number;
  page: number;
  page_size: number;
}

export function listOperationLogs(page = 1, pageSize = 20) {
  return http.get<{ code: number; data: OperationLogPage | OperationLog[] }>("/system/operation-logs", {
    params: { page, page_size: pageSize },
  });
}
