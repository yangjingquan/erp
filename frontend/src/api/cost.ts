import { http } from "./http";
export const createAllocation = (payload: unknown) => http.post("/cost/allocations", payload);
export const listAllocations = () => http.get("/cost/allocations");
export const postAllocation = (id: string) => http.post(`/cost/allocations/${id}/post`);
export const closePeriod = (period: string) => http.post(`/cost/periods/${period}/close`);
export const reopenPeriod = (period: string) => http.post(`/cost/periods/${period}/reopen`);
