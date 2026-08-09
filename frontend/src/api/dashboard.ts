import { http } from "./http";
export const getDashboardOverview = (period?: string) => http.get("/dashboard/overview", { params: { period } });
export const getDashboardPhase2 = (period: string, warehouse_id?: string) => http.get("/dashboard/phase2", { params: { period, warehouse_id } });
