import { http } from "./http";
export const createEmployee = (payload: unknown) => http.post("/hr/employees", payload);
export const listEmployees = () => http.get("/hr/employees");
export const listPayroll = (period?: string) => http.get("/hr/payroll", { params: { period } });
export const recordAttendance = (id: string, payload: unknown) => http.post(`/hr/employees/${id}/attendance`, payload);
export const calculatePayroll = (period: string) => http.post(`/hr/payroll/${period}/calculate`);
export const approvePayroll = (id: string) => http.post(`/hr/payroll/${id}/approve`);
export const payPayroll = (id: string) => http.post(`/hr/payroll/${id}/pay`);
