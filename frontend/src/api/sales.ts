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

export type SalesQuotePayload = {
  customer_id: string;
  quote_date: string;
  valid_until?: string | null;
  items: Array<{
    material_id: string;
    quantity: number;
    unit_price: number;
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
export function createSalesQuote(payload: SalesQuotePayload) {
  return http.post("/sales/quotes", {
    customer_id: payload.customer_id,
    quote_date: payload.quote_date,
    valid_until: payload.valid_until?.trim() || null,
    items: payload.items.map(({ material_id, quantity, unit_price }) => ({ material_id, quantity, unit_price })),
  });
}
export function quoteAction(id: string, action: "submit" | "approve" | "reject") { return http.post(`/sales/quotes/${id}/${action}`); }
export function listSalesReturns() { return http.get("/sales/returns"); }
export function createSalesReturn(payload: Record<string, unknown>) { return http.post("/sales/returns", payload); }
