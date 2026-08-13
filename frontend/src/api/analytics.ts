import { http } from "./http";

export const listReportDefinitions = () => http.get("/analytics/reports");
export const createReportDefinition = (payload: unknown) => http.post("/analytics/reports", payload);
export const runReport = (reportId: string, payload: unknown) => http.post("/analytics/reports/" + reportId + "/run", payload);
export const listReportRuns = (limit = 50) => http.get("/analytics/runs", { params: { limit } });
export const getReportRun = (runId: string) => http.get("/analytics/runs/" + runId);
export const exportReportRun = (runId: string) => http.get("/analytics/runs/" + runId + "/export", { responseType: "blob" });
