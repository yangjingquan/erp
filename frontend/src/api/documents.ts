import { http } from "./http";

export type DocumentListParams = {
  business_type?: string;
  status?: string;
  keyword?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
  sort?: string;
};

export function listDocuments(params: DocumentListParams) {
  return http.get("/documents", { params });
}

export function getDocumentWorkspace(businessType: string, businessId: string) {
  return http.get(`/documents/${businessType}/${businessId}`);
}

export function runDocumentCommand(businessType: string, businessId: string, command: string, payload: Record<string, unknown> = {}) {
  return http.post(`/documents/${businessType}/${businessId}/commands`, { command, payload });
}

export function runBulkDocumentCommand(businessType: string, businessIds: string[], command: string, payload: Record<string, unknown> = {}) {
  return http.post("/documents/bulk-commands", { business_type: businessType, business_ids: businessIds, command, payload });
}

export const listSavedDocumentViews = () => http.get("/documents/views");
export const createSavedDocumentView = (payload: { name: string; business_type?: string; filters: Record<string, unknown>; is_shared?: boolean }) => http.post("/documents/views", payload);
export const deleteSavedDocumentView = (id: string) => http.delete(`/documents/views/${id}`);
export const listDocumentExports = () => http.get("/documents/exports");
export const startDocumentExport = (payload: { business_type?: string; filters: Record<string, unknown> }) => http.post("/documents/exports", payload);
export const downloadDocumentExport = (id: string) => http.get(`/documents/exports/${id}/download`, { responseType: "blob" });

export function addDocumentComment(businessType: string, businessId: string, content: string) {
  return http.post(`/documents/${businessType}/${businessId}/comments`, { content });
}

export function uploadDocumentAttachment(businessType: string, businessId: string, file: File) {
  const data = new FormData();
  data.append("file", file);
  return http.post(`/documents/${businessType}/${businessId}/attachments`, data, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}

export function downloadDocumentAttachment(attachmentId: string) {
  return http.get(`/documents/attachments/${attachmentId}/download`, { responseType: "blob" });
}

export function deleteDocumentAttachment(attachmentId: string) {
  return http.delete(`/documents/attachments/${attachmentId}`);
}

export function listNotifications(params: { unread_only?: boolean; page?: number; page_size?: number } = {}) {
  return http.get("/notifications", { params });
}

export function markNotificationRead(id: string) {
  return http.post(`/notifications/${id}/read`);
}

export function markAllNotificationsRead() {
  return http.post("/notifications/read-all");
}
