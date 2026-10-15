import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const main = readFileSync(join(root, "src/main.ts"), "utf8");
const foundation = readFileSync(join(root, "src/views/finance/FinanceFoundation.vue"), "utf8");
const layout = readFileSync(join(root, "src/layouts/AdminLayout.vue"), "utf8");

const checks = [
  ["hasRenderedUi", main.includes("function hasRenderedUi")],
  ["multi checkpoint", main.includes("2500") && main.includes("7000")],
  ["navigating guard", main.includes("erpNavigating")],
  ["cancel on rendered", main.includes("hasRenderedUi()")],
  ["foundation ready", foundation.includes('data-erp-ready="1"')],
  ["layout ready", layout.includes('data-erp-ready="1"')],
  ["no naive 1500-only", !/setTimeout\(\(\)\s*=>\s*\{\s*if\s*\(!document\.querySelector\("#app"\)\?\.children\.length\)/.test(main)],
];

let failed = 0;
for (const [name, ok] of checks) {
  if (!ok) {
    console.error("FAIL:", name);
    failed += 1;
  } else {
    console.log("PASS:", name);
  }
}
if (failed) process.exit(1);
console.log("PASS: white-screen monitor hardened");
