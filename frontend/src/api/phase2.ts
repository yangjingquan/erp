import { http } from "./http";

export const listRevisions = (keyword?: string) => http.get("/phase2/plm/revisions", { params: { keyword } });
export const createRevision = (payload: unknown) => http.post("/phase2/plm/revisions", payload);
export const listChangeRequests = (status?: string) => http.get("/phase2/plm/changes", { params: { status } });
export const createChangeRequest = (payload: unknown) => http.post("/phase2/plm/changes", payload);
export const transitionChangeRequest = (id: string, status: string) => http.post(`/phase2/plm/changes/${id}/transition`, { status });

export const listRfqs = (status?: string) => http.get("/phase2/srm/rfqs", { params: { status } });
export const createRfq = (payload: unknown) => http.post("/phase2/srm/rfqs", payload);
export const quoteRfq = (id: string, payload: unknown) => http.post(`/phase2/srm/rfqs/${id}/quote`, payload);
export const acceptRfq = (id: string) => http.post(`/phase2/srm/rfqs/${id}/accept`);

export const listProjects = () => http.get("/phase2/projects");
export const createProject = (payload: unknown) => http.post("/phase2/projects", payload);
export const createWbs = (payload: unknown) => http.post("/phase2/projects/wbs", payload);
export const createProjectEntry = (payload: unknown) => http.post("/phase2/projects/entries", payload);
export const listProjectEntries = (id: string) => http.get(`/phase2/projects/${id}/entries`);

export const listAssets = () => http.get("/phase2/eam/assets");
export const createAsset = (payload: unknown) => http.post("/phase2/eam/assets", payload);
export const listAssetWorkOrders = () => http.get("/phase2/eam/work-orders");
export const createAssetWorkOrder = (payload: unknown) => http.post("/phase2/eam/work-orders", payload);
export const listServiceCases = () => http.get("/phase2/service/cases");
export const createServiceContract = (payload: unknown) => http.post("/phase2/service/contracts", payload);
export const createServiceCase = (payload: unknown) => http.post("/phase2/service/cases", payload);
export const transitionServiceCase = (id: string, status: string) => http.post(`/phase2/service/cases/${id}/transition/${status}`);
export const createServiceVisit = (payload: unknown) => http.post("/phase2/service/visits", payload);

export const getCustomer360 = (id: string) => http.get(`/phase2/crm/customers/${id}/360`);
export const listTaxCodes = () => http.get("/phase2/compliance/tax-codes");
export const listTaxInvoices = () => http.get("/phase2/compliance/invoices");
export const createTaxCode = (payload: unknown) => http.post("/phase2/compliance/tax-codes", payload);
export const createTaxInvoice = (payload: unknown) => http.post("/phase2/compliance/invoices", payload);
export const transitionTaxInvoice = (id: string, status: string) => http.post(`/phase2/compliance/invoices/${id}/transition/${status}`);
export const listIntercompany = () => http.get("/phase2/group/intercompany");
export const createIntercompany = (payload: unknown) => http.post("/phase2/group/intercompany", payload);
export const listGroupMembers = () => http.get("/phase2/group/members");
export const createGroupMember = (payload: unknown) => http.post("/phase2/group/members", payload);
export const listLowCode = () => http.get("/phase2/low-code/definitions");
export const createLowCode = (payload: unknown) => http.post("/phase2/low-code/definitions", payload);
export const publishLowCode = (id: string) => http.post(`/phase2/low-code/definitions/${id}/publish`);
export const listMetrics = () => http.get("/phase2/metrics");
export const createMetric = (payload: unknown) => http.post("/phase2/metrics", payload);
export const explainMetric = (key: string) => http.get(`/phase2/metrics/${key}/explain`);
export const listAiAlerts = () => http.get("/phase2/ai/alerts");
export const scanAiAlerts = () => http.post("/phase2/ai/scan");
export const resolveAiAlert = (id: string, resolution: string) => http.post(`/phase2/ai/alerts/${id}/resolve`, { resolution });
