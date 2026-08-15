import { http } from "./http";

export const listRevisions = (keyword?: string) => http.get("/phase2/plm/revisions", { params: { keyword } });
export const createRevision = (payload: unknown) => http.post("/phase2/plm/revisions", payload);
export const transitionRevision = (id: string, status: string) => http.post(`/phase2/plm/revisions/${id}/transition`, { status });
export const listChangeRequests = (status?: string) => http.get("/phase2/plm/changes", { params: { status } });
export const createChangeRequest = (payload: unknown) => http.post("/phase2/plm/changes", payload);
export const transitionChangeRequest = (id: string, status: string) => http.post(`/phase2/plm/changes/${id}/transition`, { status });
export const listChangeImpacts = (id: string) => http.get(`/phase2/plm/changes/${id}/impacts`);
export const resolveChangeImpact = (id: string, status = "applied") => http.post(`/phase2/plm/impacts/${id}/resolve`, { status });

export const listRfqs = (status?: string) => http.get("/phase2/srm/rfqs", { params: { status } });
export const compareRfqs = (materialId?: string) => http.get("/phase2/srm/compare", { params: materialId ? { material_id: materialId } : undefined });
export const createRfq = (payload: unknown) => http.post("/phase2/srm/rfqs", payload);
export const quoteRfq = (id: string, payload: unknown) => http.post(`/phase2/srm/rfqs/${id}/quote`, payload);
export const acceptRfq = (id: string) => http.post(`/phase2/srm/rfqs/${id}/accept`);
export const listSupplierScores = (supplierId?: string) => http.get("/phase2/srm/scores", { params: supplierId ? { supplier_id: supplierId } : undefined });
export const createSupplierScore = (payload: unknown) => http.post("/phase2/srm/scores", payload);

export const listProjects = () => http.get("/phase2/projects");
export const createProject = (payload: unknown) => http.post("/phase2/projects", payload);
export const createWbs = (payload: unknown) => http.post("/phase2/projects/wbs", payload);
export const listProjectWbs = (id: string) => http.get(`/phase2/projects/${id}/wbs`);
export const createProjectMilestone = (payload: unknown) => http.post("/phase2/projects/milestones", payload);
export const listProjectMilestones = (id: string) => http.get(`/phase2/projects/${id}/milestones`);
export const getProjectDashboard = (id: string) => http.get(`/phase2/projects/${id}/dashboard`);
export const createProjectEntry = (payload: unknown) => http.post("/phase2/projects/entries", payload);
export const listProjectEntries = (id: string) => http.get(`/phase2/projects/${id}/entries`);

export const listAssets = () => http.get("/phase2/eam/assets");
export const createAsset = (payload: unknown) => http.post("/phase2/eam/assets", payload);
export const listAssetWorkOrders = () => http.get("/phase2/eam/work-orders");
export const createAssetWorkOrder = (payload: unknown) => http.post("/phase2/eam/work-orders", payload);
export const listMaintenancePlans = (assetId?: string) => http.get("/phase2/eam/maintenance-plans", { params: assetId ? { asset_id: assetId } : undefined });
export const createMaintenancePlan = (payload: unknown) => http.post("/phase2/eam/maintenance-plans", payload);
export const transitionAssetWorkOrder = (id: string, status: string) => http.post(`/phase2/eam/work-orders/${id}/transition/${status}`);
export const listServiceCases = () => http.get("/phase2/service/cases");
export const createServiceContract = (payload: unknown) => http.post("/phase2/service/contracts", payload);
export const createServiceCase = (payload: unknown) => http.post("/phase2/service/cases", payload);
export const transitionServiceCase = (id: string, status: string) => http.post(`/phase2/service/cases/${id}/transition/${status}`);
export const createServiceVisit = (payload: unknown) => http.post("/phase2/service/visits", payload);
export const listServiceVisits = (caseId?: string) => http.get("/phase2/service/visits", { params: caseId ? { case_id: caseId } : undefined });

export const listLeaveRequests = () => http.get("/phase2/hr/leave-requests");
export const listAttendance = (attendanceDate?: string) => http.get("/phase2/hr/attendance", { params: attendanceDate ? { attendance_date: attendanceDate } : undefined });
export const createLeaveRequest = (payload: unknown) => http.post("/phase2/hr/leave-requests", payload);
export const transitionLeaveRequest = (id: string, status: string) => http.post(`/phase2/hr/leave-requests/${id}/transition/${status}`);

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
export const updateGroupMember = (id: string, payload: unknown) => http.put("/phase2/group/members/" + id, payload);
export const deleteGroupMember = (id: string) => http.delete("/phase2/group/members/" + id);
export const listLowCode = () => http.get("/phase2/low-code/definitions");
export const createLowCode = (payload: unknown) => http.post("/phase2/low-code/definitions", payload);
export const publishLowCode = (id: string) => http.post(`/phase2/low-code/definitions/${id}/publish`);
export const listMetrics = () => http.get("/phase2/metrics");
export const createMetric = (payload: unknown) => http.post("/phase2/metrics", payload);
export const explainMetric = (key: string) => http.get(`/phase2/metrics/${key}/explain`);
export const listAiAlerts = () => http.get("/phase2/ai/alerts");
export const scanAiAlerts = () => http.post("/phase2/ai/scan");
export const resolveAiAlert = (id: string, resolution: string) => http.post(`/phase2/ai/alerts/${id}/resolve`, { resolution });
