export type OrderStatusTagType = "primary" | "success" | "warning" | "danger" | "info";

export const orderStatusLabels: Record<string, string> = {
  draft: "草稿",
  submitted: "待审核",
  approved: "已审核",
  partially_received: "部分入库",
  partially_delivered: "部分出库",
  completed: "已完成",
  rejected: "已驳回",
  cancelled: "已取消",
  // Legacy/demo rows may still carry "active"; treat as effective without console noise.
  active: "生效",
};

export const orderStatusTagTypes: Record<string, OrderStatusTagType> = {
  draft: "info",
  submitted: "warning",
  approved: "success",
  partially_received: "warning",
  partially_delivered: "warning",
  completed: "success",
  rejected: "danger",
  cancelled: "danger",
  active: "success",
};

export function orderStatusLabel(value: unknown): string {
  const key = String(value ?? "");
  return orderStatusLabels[key] || "未知状态";
}

/** Alias used by tests / callers expecting getOrderStatusLabel naming. */
export function getOrderStatusLabel(value: unknown): string {
  return orderStatusLabel(value);
}

export function orderStatusTagType(value: unknown): OrderStatusTagType {
  return orderStatusTagTypes[String(value ?? "")] || "warning";
}

export function isKnownOrderStatus(value: unknown): boolean {
  return Object.prototype.hasOwnProperty.call(orderStatusLabels, String(value ?? ""));
}
