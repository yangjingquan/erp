import { readdirSync, readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const distRoot = fileURLToPath(new URL("../dist/", import.meta.url));
const forbidden = [
  /https?:\/\/127\.0\.0\.1(?::\d+)?\/api/i,
  /https?:\/\/localhost(?::\d+)?\/api/i,
];
const files = [];

function visit(directory) {
  for (const entry of readdirSync(directory)) {
    const path = join(directory, entry);
    if (statSync(path).isDirectory()) visit(path);
    else files.push(path);
  }
}

visit(distRoot);
const matches = files.flatMap((path) => {
  const content = readFileSync(path, "utf8");
  return forbidden.filter((pattern) => pattern.test(content)).map((pattern) => `${path}: ${pattern}`);
});

if (matches.length) {
  console.error("生产构建产物包含禁止的本地 API 地址:\n" + matches.join("\n"));
  process.exitCode = 1;
} else {
  console.log(`生产构建产物检查通过（${files.length} 个文件）`);
}
