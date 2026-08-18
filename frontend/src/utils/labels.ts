export type TagType = "primary" | "success" | "warning" | "danger" | "info";

export const statusLabels: Record<string, string> = {
  active: "启用", inactive: "停用", draft: "草稿", submitted: "待审核", pending_review: "待审核", investigating: "调查中", approved: "已审核",
  rejected: "已驳回", cancelled: "已取消", completed: "已完成", open: "待处理", partial: "部分完成",
  settled: "已结清", confirmed: "已确认", posted: "已过账", pending: "待处理", in_progress: "进行中",
  released: "已发布", effective: "已生效", obsolete: "已作废", quoted: "已报价", accepted: "已接受", reversed: "已冲销",
  reserved: "预留中", released_reservation: "已释放", ready: "待执行", assigned: "已分配", resolved: "已解决",
  ignored: "已忽略", passed: "已通过", failed: "未通过", new: "新建", contacted: "已联系", qualified: "已合格",
  converted: "已转化", lost: "已丢失", won: "赢单", proposal: "商谈中", issued: "已开具", red_issued: "已红冲",
  approved_for_release: "已批准", executing: "执行中", closed: "已关闭", voided: "已作废", planned: "已计划",
  dispatched: "已发运", in_transit: "运输中", delivered: "已签收",
};

export const reportTypeLabels: Record<string, string> = {
  management_kpi: "经营管理 KPI", operations_kpi: "运营模块 KPI", "Biz Report Run": "经营管理 KPI",
};
export const materialTypeLabels: Record<string, string> = {
  raw: "原材料", semi: "半成品", finished: "成品", service: "服务", asset: "资产", 商品: "商品",
};
export const directionLabels: Record<string, string> = { in: "入库", out: "出库", debit: "借", credit: "贷" };
export const sourceTypeLabels: Record<string, string> = {
  sales_order: "销售订单", sales_delivery: "销售出库", purchase_order: "采购订单", purchase_receipt: "采购入库",
  purchase_request: "采购申请", work_order: "生产工单", material_issue: "生产领料", inventory_count: "库存盘点",
  transfer: "库存调拨", manual: "手工录入", system: "系统生成", bank: "银行流水",
};
export const accountTypeLabels: Record<string, string> = {
  asset: "资产", liability: "负债", equity: "所有者权益", cost: "成本", revenue: "收入", expense: "费用",
};
export const dimensionTypeLabels: Record<string, string> = {
  department: "部门", customer: "客户", supplier: "供应商", employee: "员工", project: "项目", custom: "自定义",
};
export const stageLabels: Record<string, string> = { lead: "线索", qualification: "资格审查", proposal: "方案报价", negotiation: "商务谈判", won: "赢单", lost: "输单" };
export const changeTypeLabels: Record<string, string> = { engineering: "工程变更", quality: "质量变更", supplier: "供应商变更", production: "生产变更" };
export const allocationBasisLabels: Record<string, string> = { headcount: "人数", hours: "工时", amount: "金额", quantity: "数量", manual: "手工" };
export const reconciliationStatusLabels: Record<string, string> = { open: "未核销", partial: "部分核销", settled: "已核销" };
export const reconciliationRecordStatusLabels: Record<string, string> = { draft: "草稿", confirmed: "已确认", partial: "部分核销", settled: "已核销" };

export function labelOf(map: Record<string, string>, value: unknown, fallback = "-") {
  const key = String(value ?? "");
  return map[key] || (key ? key : fallback);
}

export function statusLabel(value: unknown, fallback = "-") { return labelOf(statusLabels, value, fallback); }
export function tagTypeOf(value: unknown): TagType {
  const key = String(value ?? "");
  if (["active", "approved", "completed", "settled", "posted", "effective", "won", "converted", "resolved", "passed"].includes(key)) return "success";
  if (["submitted", "pending_review", "open", "investigating", "pending", "in_progress", "assigned", "proposal", "partial", "quoted"].includes(key)) return "warning";
  if (["rejected", "cancelled", "failed", "lost", "obsolete", "closed"].includes(key)) return "danger";
  return "info";
}
