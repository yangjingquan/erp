import { beforeEach, describe, expect, it, vi } from "vitest";

const { deleteMock, getMock, postMock, putMock } = vi.hoisted(() => ({
  deleteMock: vi.fn(),
  getMock: vi.fn(),
  postMock: vi.fn(),
  putMock: vi.fn(),
}));

vi.mock("../src/api/http", () => ({
  http: {
    get: getMock,
    post: postMock,
    put: putMock,
    delete: deleteMock,
  },
}));

import {
  approveSalesOrder,
  createSalesQuote,
  createSalesDelivery,
  createSalesOrder,
  listSalesOrders,
  submitSalesOrder,
} from "../src/api/sales";
import {
  approvePurchaseOrder,
  createPurchaseOrder,
  createPurchaseReceipt,
  deletePurchaseOrder,
  listPurchaseOrders,
  createPurchaseRequest,
  deletePurchaseRequest,
  listPurchaseRequests,
  submitPurchaseOrder,
  updatePurchaseOrder,
  updatePurchaseRequest,
  createPurchaseReturn,
  deletePurchaseReturn,
  listPurchaseReturns,
  updatePurchaseReturn,
} from "../src/api/purchase";
import {
  approveInventoryTransfer,
  completeInventoryCount,
  completeInventoryTransfer,
  createInventoryCount,
  createInventoryTransfer,
  listInventoryCounts,
  listInventoryStock,
  listInventoryTransactions,
  listInventoryTransfers,
  listInventoryWarnings,
} from "../src/api/inventory";
import {
  createExpense,
  approveExpense,
  createPayment,
  createReceipt,
  generateVoucher,
  listExpenses,
  listPayables,
  listReceipts,
  listReceivables,
  listPayments,
  listVouchers,
  settleExpense,
} from "../src/api/finance";

describe("一期业务 API 路由", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("uses the sales order list and lifecycle endpoints", async () => {
    const payload = { customer_id: "customer-1", items: [{ material_id: "material-1", quantity: 2, unit_price: 10, warehouse_id: "warehouse-1" }] };

    await listSalesOrders({ status: "draft" });
    await createSalesOrder(payload);
    await submitSalesOrder("sales-1");
    await approveSalesOrder("sales-1");
    await createSalesDelivery("sales-1");

    expect(getMock).toHaveBeenCalledWith("/sales/orders", { params: { status: "draft" } });
    expect(postMock).toHaveBeenNthCalledWith(1, "/sales/orders", payload);
    expect(postMock).toHaveBeenNthCalledWith(2, "/sales/orders/sales-1/submit");
    expect(postMock).toHaveBeenNthCalledWith(3, "/sales/orders/sales-1/approve");
    expect(postMock).toHaveBeenNthCalledWith(4, "/sales/orders/sales-1/create-delivery");
  });

  it("normalizes an empty quote validity date and whitelists quote fields", async () => {
    const payload = {
      customer_id: "customer-1",
      quote_date: "2026-08-09",
      valid_until: "",
      supplier_id: "",
      warehouse_id: "",
      items: [{ material_id: "material-1", quantity: 2, unit_price: 3, estimated_price: 0 }],
    };

    await createSalesQuote(payload);

    expect(postMock).toHaveBeenCalledWith("/sales/quotes", {
      customer_id: "customer-1",
      quote_date: "2026-08-09",
      valid_until: null,
      items: [{ material_id: "material-1", quantity: 2, unit_price: 3 }],
    });
  });

  it("uses the purchase order list and lifecycle endpoints", async () => {
    const payload = { supplier_id: "supplier-1", items: [{ material_id: "material-1", quantity: 3, unit_price: 8 }] };

    await listPurchaseOrders({ status: "submitted" });
    await createPurchaseOrder(payload);
    await submitPurchaseOrder("purchase-1");
    await approvePurchaseOrder("purchase-1");
    await createPurchaseReceipt("purchase-1");

    expect(getMock).toHaveBeenCalledWith("/purchase/orders", { params: { status: "submitted" } });
    expect(postMock).toHaveBeenNthCalledWith(1, "/purchase/orders", payload);
    expect(postMock).toHaveBeenNthCalledWith(2, "/purchase/orders/purchase-1/submit");
    expect(postMock).toHaveBeenNthCalledWith(3, "/purchase/orders/purchase-1/approve");
    expect(postMock).toHaveBeenNthCalledWith(4, "/purchase/orders/purchase-1/create-receipt");
  });

  it("uses the purchase request CRUD endpoints", async () => {
    const payload = { supplier_id: "supplier-1", request_date: "2026-08-10", items: [{ material_id: "material-1", quantity: 2, estimated_price: 5 }] };

    await listPurchaseRequests();
    await createPurchaseRequest(payload);
    await updatePurchaseRequest("request-1", payload);
    await deletePurchaseRequest("request-1");

    expect(getMock).toHaveBeenCalledWith("/purchase/requests");
    expect(postMock).toHaveBeenCalledWith("/purchase/requests", payload);
    expect(putMock).toHaveBeenCalledWith("/purchase/requests/request-1", payload);
    expect(deleteMock).toHaveBeenCalledWith("/purchase/requests/request-1");
  });

  it("uses the purchase order and return CRUD endpoints", async () => {
    const orderPayload = { supplier_id: "supplier-1", order_date: "2026-08-10", items: [{ material_id: "material-1", quantity: 2, unit_price: 5 }] };
    const returnPayload = { supplier_id: "supplier-1", warehouse_id: "warehouse-1", return_date: "2026-08-10", items: [{ material_id: "material-1", quantity: 1, unit_price: 5 }] };

    await updatePurchaseOrder("order-1", orderPayload);
    await deletePurchaseOrder("order-1");
    await listPurchaseReturns();
    await createPurchaseReturn(returnPayload);
    await updatePurchaseReturn("return-1", returnPayload);
    await deletePurchaseReturn("return-1");

    expect(putMock).toHaveBeenCalledWith("/purchase/orders/order-1", orderPayload);
    expect(deleteMock).toHaveBeenCalledWith("/purchase/orders/order-1");
    expect(getMock).toHaveBeenCalledWith("/purchase/returns");
    expect(postMock).toHaveBeenCalledWith("/purchase/returns", returnPayload);
    expect(putMock).toHaveBeenCalledWith("/purchase/returns/return-1", returnPayload);
    expect(deleteMock).toHaveBeenCalledWith("/purchase/returns/return-1");
  });

  it("reserves all inventory list and transaction endpoints", async () => {
    const transfer = { from_warehouse_id: "warehouse-1", to_warehouse_id: "warehouse-2", items: [{ material_id: "material-1", quantity: 1 }] };
    const count = { warehouse_id: "warehouse-1", items: [{ material_id: "material-1", actual_quantity: 5 }] };

    await listInventoryStock();
    await listInventoryTransactions({ warehouse_id: "warehouse-1" });
    await listInventoryTransfers();
    await listInventoryCounts();
    await listInventoryWarnings();
    await createInventoryTransfer(transfer);
    await approveInventoryTransfer("transfer-1");
    await completeInventoryTransfer("transfer-1");
    await createInventoryCount(count);
    await completeInventoryCount("count-1");

    expect(getMock).toHaveBeenNthCalledWith(1, "/inventory/stock", { params: undefined });
    expect(getMock).toHaveBeenNthCalledWith(2, "/inventory/transactions", { params: { warehouse_id: "warehouse-1" } });
    expect(getMock).toHaveBeenNthCalledWith(3, "/inventory/transfers", { params: undefined });
    expect(getMock).toHaveBeenNthCalledWith(4, "/inventory/counts", { params: undefined });
    expect(getMock).toHaveBeenNthCalledWith(5, "/inventory/warnings", { params: undefined });
    expect(postMock).toHaveBeenNthCalledWith(1, "/inventory/transfers", transfer);
    expect(postMock).toHaveBeenNthCalledWith(2, "/inventory/transfers/transfer-1/approve");
    expect(postMock).toHaveBeenNthCalledWith(3, "/inventory/transfers/transfer-1/complete");
    expect(postMock).toHaveBeenNthCalledWith(4, "/inventory/counts", count);
    expect(postMock).toHaveBeenNthCalledWith(5, "/inventory/counts/count-1/complete");
  });

  it("uses finance list endpoints and existing write endpoints", async () => {
    await listReceivables();
    await listPayables();
    await listReceipts();
    await listPayments();
    await listExpenses();
    await listVouchers();
    await createReceipt({ customer_id: "customer-1", amount: 100 });
    await createPayment({ supplier_id: "supplier-1", amount: 80 });
    await createExpense({ expense_type: "交通", amount: 20 });
    await generateVoucher("expense", "expense-1");

    expect(getMock).toHaveBeenNthCalledWith(1, "/finance/receivables", { params: undefined });
    expect(getMock).toHaveBeenNthCalledWith(2, "/finance/payables", { params: undefined });
    expect(getMock).toHaveBeenNthCalledWith(3, "/finance/receipts", { params: undefined });
    expect(getMock).toHaveBeenNthCalledWith(4, "/finance/payments", { params: undefined });
    expect(getMock).toHaveBeenNthCalledWith(5, "/finance/expenses", { params: undefined });
    expect(getMock).toHaveBeenNthCalledWith(6, "/finance/vouchers", { params: undefined });
    expect(postMock).toHaveBeenNthCalledWith(1, "/finance/receipts", { customer_id: "customer-1", amount: 100 });
    expect(postMock).toHaveBeenNthCalledWith(2, "/finance/payments", { supplier_id: "supplier-1", amount: 80 });
    expect(postMock).toHaveBeenNthCalledWith(3, "/finance/expenses", { expense_type: "交通", amount: 20 });
    expect(postMock).toHaveBeenNthCalledWith(4, "/finance/vouchers/expense/expense-1");
  });

  it("uses the expense approval and settlement endpoints", async () => {
    await approveExpense("expense-1");
    await settleExpense("expense-1");

    expect(postMock).toHaveBeenNthCalledWith(1, "/finance/expenses/expense-1/approve");
    expect(postMock).toHaveBeenNthCalledWith(2, "/finance/expenses/expense-1/settle");
  });
});
