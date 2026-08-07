export interface WorkflowNode {
  key: string;
  name: string;
  approver: string;
}

export const WORKFLOW_CONFIG_STORAGE_KEY = "erp.workflow.config";

export function loadWorkflowConfig(fallback: WorkflowNode[]) {
  try {
    const saved = localStorage.getItem(WORKFLOW_CONFIG_STORAGE_KEY);
    if (!saved) return fallback;
    const parsed = JSON.parse(saved) as unknown;
    return Array.isArray(parsed) ? (parsed as WorkflowNode[]) : fallback;
  } catch {
    return fallback;
  }
}

export function saveWorkflowConfig(nodes: WorkflowNode[]) {
  localStorage.setItem(WORKFLOW_CONFIG_STORAGE_KEY, JSON.stringify(nodes));
}

export function getWorkflowDefinition(businessType: string) {
  return http.get(`/workflow/definitions/${businessType}`);
}

export function saveWorkflowDefinition(businessType: string, payload: { name: string; status: string; nodes: WorkflowNode[] }) {
  return http.put(`/workflow/definitions/${businessType}`, payload);
}
import { http } from "./http";
