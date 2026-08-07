import { http } from "./http";
export const listWorkOrders = () => http.get("/production/work-orders");
export const releaseWorkOrder = (id: string) => http.post(`/production/work-orders/${id}/release`);
export const issueMaterial = (id: string, items: unknown) => http.post(`/production/work-orders/${id}/issue`, { items });
export const completeWorkOrder = (id: string) => http.post(`/production/work-orders/${id}/complete`);
