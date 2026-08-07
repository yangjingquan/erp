import { http } from "./http";
export const listLeads = () => http.get("/crm/leads");
export const createLead = (payload: unknown) => http.post("/crm/leads", payload);
export const transitionLead = (id: string, status: string) => http.post(`/crm/leads/${id}/transition/${status}`);
export const convertLead = (id: string) => http.post(`/crm/leads/${id}/convert`);
export const listOpportunities = () => http.get("/crm/opportunities");
export const addFollowUp = (id: string, payload: unknown) => http.post(`/crm/opportunities/${id}/follow-ups`, payload);
