export type OrderStatusTagType = "primary" | "success" | "warning" | "danger" | "info";

export const orderStatusLabels: Record<string, string> = {
  draft: "草稿",
  submitted: "待审核",
  approved: "已审核",
  completed: "已完成",
  rejected: "已驳回",
  cancelled: "已取消",
};

export const orderStatusTagTypes: Record<string, OrderStatusTagType> = {
  draft: "info",
  submitted: "warning",
  approved: "success",
  completed: "success",
  rejected: "danger",
  cancelled: "danger",
};

export function orderStatusLabel(value: unknown): string {
  const key = String(value ?? "");
  return orderStatusLabels[key] || "未知状态";
}

export function orderStatusTagType(value: unknown): OrderStatusTagType {
  return orderStatusTagTypes[String(value ?? "")] || "warning";
}

export function isKnownOrderStatus(value: unknown): boolean {
  return Object.prototype.hasOwnProperty.call(orderStatusLabels, String(value ?? ""));
}
