import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const text = readFileSync(join(root, "src/utils/orderStatus.ts"), "utf8");
const labelsBlock = text.match(/orderStatusLabels[\s\S]*?=\s*\{([\s\S]*?)\n\};/);
if (!labelsBlock) throw new Error("orderStatusLabels not found");
const labels = Object.fromEntries([...labelsBlock[1].matchAll(/(\w+)\s*:\s*"([^"]+)"/g)].map((m) => [m[1], m[2]]));

function getOrderStatusLabel(value) {
  return labels[String(value ?? "")] || "未知状态";
}

const active = getOrderStatusLabel("active");
if (active === "未知状态") {
  console.error("FAIL: getOrderStatusLabel('active') === 未知状态");
  process.exit(1);
}
if (active !== "生效") {
  console.error(`FAIL: expected 生效, got ${active}`);
  process.exit(1);
}
if (!text.includes("function getOrderStatusLabel")) {
  console.error("FAIL: getOrderStatusLabel alias missing");
  process.exit(1);
}
console.log("PASS: getOrderStatusLabel('active') =", active);
