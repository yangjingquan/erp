import { http } from "./http";

export interface GlobalParameter {
  id?: string;
  parameter_key: string;
  parameter_value: string;
  value_type: string;
  description?: string | null;
}

export function listGlobalParameters() {
  return http.get("/config/parameters");
}

export function updateGlobalParameter(parameterKey: string, payload: Omit<GlobalParameter, "id" | "parameter_key">) {
  return http.put(`/config/parameters/${encodeURIComponent(parameterKey)}`, payload);
}

export interface PrintTemplate {
  id?: string;
  business_type: string;
  name: string;
  template_html: string;
  status: string;
}

export function listPrintTemplates() {
  return http.get("/config/print-templates");
}

export function createPrintTemplate(payload: Omit<PrintTemplate, "id">) {
  return http.post("/config/print-templates", payload);
}

export function updatePrintTemplate(id: string, payload: Omit<PrintTemplate, "id">) {
  return http.put(`/config/print-templates/${id}`, payload);
}

export function deletePrintTemplate(id: string) {
  return http.delete(`/config/print-templates/${id}`);
}

export function renderPrintTemplate(businessType: string, businessId: string, templateId?: string) {
  return http.get("/config/print-templates/render", {
    params: { business_type: businessType, business_id: businessId, template_id: templateId },
  });
}
