import axios from "axios";

import { http } from "./http";

export type MasterResource = "materials" | "customers" | "suppliers" | "warehouses" | "units" | "tax-rates";

export interface MasterListParams {
  keyword?: string;
  page?: number;
  pageSize?: number;
}

export function listMasterData(resource: MasterResource, params: MasterListParams = {}) {
  const { pageSize, ...rest } = params;
  return http.get(`/master/${resource}`, {
    params: pageSize === undefined ? rest : { ...rest, page_size: pageSize },
  });
}

export function createMasterData(resource: MasterResource, payload: Record<string, unknown>) {
  return http.post(`/master/${resource}`, payload);
}

export function importMasterData(resource: MasterResource, file: File) {
  const form = new FormData();
  form.append("file", file);
  return http.post(`/master/${resource}/import`, form);
}

export function exportMasterData(resource: MasterResource) {
  return http.get(`/master/${resource}/export`, { responseType: "blob" });
}

export function getMasterDataErrorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    const responseData = error.response?.data as { msg?: string } | undefined;
    if (responseData?.msg) return responseData.msg;
  }
  return error instanceof Error && error.message ? error.message : fallback;
}
