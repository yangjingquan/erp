import { http } from "./http";

export type SalesOrderPayload = {
  customer_id: string;
  order_date?: string;
  expected_date?: string | null;
  remark?: string;
  items: Array<{
    material_id: string;
    quantity: number;
    unit_price: number;
    warehouse_id?: string | null;
    tax_rate?: number;
  }>;
};

export function listSalesOrders(params?: Record<string, unknown>) {
  return http.get("/sales/orders", { params });
}

export function createSalesOrder(payload: SalesOrderPayload) {
  return http.post("/sales/orders", payload);
}

export function submitSalesOrder(orderId: string) {
  return http.post(`/sales/orders/${orderId}/submit`);
}

export function approveSalesOrder(orderId: string) {
  return http.post(`/sales/orders/${orderId}/approve`);
}

export function createSalesDelivery(orderId: string) {
  return http.post(`/sales/orders/${orderId}/create-delivery`);
}

export function listSalesQuotes() { return http.get("/sales/quotes"); }
export function createSalesQuote(payload: SalesOrderPayload & { quote_date?: string; valid_until?: string | null }) { return http.post("/sales/quotes", payload); }
export function quoteAction(id: string, action: "submit" | "approve" | "reject") { return http.post(`/sales/quotes/${id}/${action}`); }
export function listSalesReturns() { return http.get("/sales/returns"); }
export function createSalesReturn(payload: Record<string, unknown>) { return http.post("/sales/returns", payload); }
