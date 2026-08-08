export interface WorkflowNode {
  key: string;
  name: string;
  approver: string;
}

export function getWorkflowDefinition(businessType: string) {
  return http.get(`/workflow/definitions/${businessType}`);
}

export function saveWorkflowDefinition(businessType: string, payload: { name: string; status: string; nodes: WorkflowNode[] }) {
  return http.put(`/workflow/definitions/${businessType}`, payload);
}
import { http } from "./http";
