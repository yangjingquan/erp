import { http } from "./http";
export const createApiClient = (payload: unknown) => http.post("/platform/api-clients", payload);
export const listEvents = (status?: string) => http.get("/platform/events", { params: { status } });
