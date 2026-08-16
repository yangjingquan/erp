import { http } from "./http";

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

export function listMyWorkflowTasks() {
  return http.get("/workflow/tasks");
}

export function approveWorkflowTask(taskId: string, comment = "") {
  return http.post(`/workflow/tasks/${taskId}/approve`, null, { params: { comment } });
}

export function rejectWorkflowTask(taskId: string, comment = "") {
  return http.post(`/workflow/tasks/${taskId}/reject`, null, { params: { comment } });
}
