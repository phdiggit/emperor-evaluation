import fs from "node:fs/promises";
import path from "node:path";
import { renderBase } from "./render-base.js";
import { renderOverlay } from "./render-overlay.js";
import { composeFinal } from "./compose-final.js";
import { root } from "./render-common.js";

const stage = process.argv[3];
if (!process.argv.includes("--stage") || !["base", "overlay", "final", "pipeline"].includes(stage)) throw new Error("用法：node scripts/render-all.js --stage base|overlay|final|pipeline");
const files = (await fs.readdir(path.join(root, "data", "emperors"))).filter(file => file.endsWith(".json")); const missing = [];
for (const file of files) {
  const source = path.join(root, "data", "emperors", file); const data = JSON.parse(await fs.readFile(source, "utf8")); const ai = n => path.join(root, "output", data.id, "ai", `page${n}_ai.png`);
  if (stage === "base" || stage === "pipeline") await renderBase(source);
  if (stage === "overlay" || stage === "pipeline") await renderOverlay(source);
  if (stage === "final" || stage === "pipeline") { try { await composeFinal({ data: source, page1Ai: ai(1), page2Ai: ai(2), useText: true, useRadar: true, useStroke: true }); console.log(`${data.id}: final v2 完成`); } catch { missing.push(`${data.id}: 缺少 AI 成片或覆盖层`); } }
}
if (missing.length) { console.log("缺失清单：\n" + missing.join("\n")); process.exitCode = 2; }
