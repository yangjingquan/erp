import { http } from "./http";
export const createInspection = (payload: unknown) => http.post("/quality/inspections", payload);
export const listInspections = () => http.get("/quality/inspections");
export const submitInspection = (id: string, results: unknown) => http.post(`/quality/inspections/${id}/submit`, results);
export const closeInspection = (id: string, disposition: string) => http.post(`/quality/inspections/${id}/close`, { disposition });
