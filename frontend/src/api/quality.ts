import { http } from "./http";

export interface QualityCapaAction {
  id: string;
  action_type: "corrective" | "preventive";
  description: string;
  owner_id: string;
  due_date: string;
  status: "open" | "completed";
  completion_evidence?: string | null;
  completed_at?: string | null;
  completed_by?: string | null;
  overdue: boolean;
}

export interface QualityNonconformance {
  id: string;
  inspection_id?: string | null;
  supplier_quality_id?: string | null;
  supplier_id?: string | null;
  supplier_period?: string | null;
  inspection_type?: string | null;
  source_type?: string | null;
  source_id?: string | null;
  source_document_name?: string | null;
  description: string;
  status: "open" | "investigating" | "closed";
  severity: "minor" | "major" | "critical";
  disposition?: "rework" | "accept" | "scrap" | "return_to_supplier" | null;
  owner_id?: string | null;
  due_date?: string | null;
  root_cause?: string | null;
  closure_evidence?: string | null;
  closed_at?: string | null;
  closed_by?: string | null;
  overdue: boolean;
  actions: QualityCapaAction[];
}

export interface QualityInvestigationPayload {
  severity: QualityNonconformance["severity"];
  disposition: NonNullable<QualityNonconformance["disposition"]>;
  owner_id: string;
  due_date: string;
  root_cause: string;
}

export interface QualityCapaCreatePayload {
  action_type: QualityCapaAction["action_type"];
  description: string;
  owner_id: string;
  due_date: string;
}

export const createInspection = (payload: unknown) => http.post("/quality/inspections", payload);
export const listInspections = () => http.get("/quality/inspections");
export const submitInspection = (id: string, results: unknown) => http.post(`/quality/inspections/${id}/submit`, results);
export const closeInspection = (id: string, disposition: string) => http.post(`/quality/inspections/${id}/close`, { disposition });
export const listNonconformances = () => http.get<{
  code: number;
  msg: string;
  data: QualityNonconformance[];
}>("/quality/nonconformances");
export const updateNonconformanceInvestigation = (id: string, payload: QualityInvestigationPayload) =>
  http.put(`/quality/nonconformances/${id}/investigation`, payload);
export const createCapaAction = (id: string, payload: QualityCapaCreatePayload) =>
  http.post(`/quality/nonconformances/${id}/actions`, payload);
export const completeCapaAction = (id: string, completionEvidence: string) =>
  http.post(`/quality/capa-actions/${id}/complete`, { completion_evidence: completionEvidence });
export const closeNonconformance = (id: string, closureEvidence: string) =>
  http.post(`/quality/nonconformances/${id}/close`, { closure_evidence: closureEvidence });
export const listQualityPlans = () => http.get("/quality/plans");
export const createQualityPlan = (payload: unknown) => http.post("/quality/plans", payload);
export const listDefects = () => http.get("/quality/defects");
export const createDefect = (payload: unknown) => http.post("/quality/defects", payload);
export const createInspectionFromPlan = (payload: unknown) => http.post("/quality/inspections/from-plan", payload);
