import { http } from "./http";
export const createApiClient = (payload: unknown) => http.post("/platform/api-clients", payload);
export const listApiClients = () => http.get("/platform/api-clients");
export const setApiClientStatus = (id: string, status: "active" | "inactive") => http.post(`/platform/api-clients/${id}/status`, { status });
export const listEvents = (status?: string) => http.get("/platform/events", { params: { status } });
