import { http } from "./http";
export const getDashboardOverview = () => http.get("/dashboard/overview");
export const getDashboardPhase2 = (period: string, warehouse_id?: string) => http.get("/dashboard/phase2", { params: { period, warehouse_id } });
