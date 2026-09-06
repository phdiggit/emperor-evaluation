import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";
import { loadData, root } from "./render-common.js";
import { verifyOverlay } from "./verify-overlay.js";

const size = { width: 1920, height: 1080, fit: "cover", position: "centre" };
function args(argv) { const out = {}; for (let i = 2; i < argv.length; i += 1) { if (argv[i].startsWith("--")) out[argv[i]] = argv[i + 1]?.startsWith("--") ? true : (argv[i + 1] ?? true); } return out; }
export async function composeFinal({ data: dataFile, page1Ai, page2Ai, useText = true, useRadar = true, useStroke = true }) {
  if (!dataFile || !page1Ai || !page2Ai) throw new Error("用法：node scripts/compose-final.js --data <json> --page1-ai <png> --page2-ai <png>");
  const data = await loadData(dataFile); const output = path.join(root, "output", data.id, "final"); await fs.mkdir(output, { recursive: true });
  for (const [index, ai] of [[1, page1Ai], [2, page2Ai]]) {
    await fs.access(ai); const policy = data.overlayOptions?.[`page${index}`] ?? {}; const overlays = [["stroke", useStroke && policy.useStroke !== false], ["radar", useRadar && policy.useRadar !== false], ["text", useText && policy.useText !== false]].filter(([, use]) => use).map(([name]) => path.join(root, "output", data.id, "overlay", `page${index}_overlay_${name}.png`));
    for (const overlay of overlays) await fs.access(overlay);
    await sharp(ai).resize(size).composite(overlays.map(input => ({ input, blend: "over" }))).png().toFile(path.join(output, `page${index}_final_v2.png`));
  }
  await verifyOverlay(data.id);
  return data;
}
if (path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) { const input = args(process.argv); await composeFinal({ data: input["--data"], page1Ai: input["--page1-ai"], page2Ai: input["--page2-ai"], useText: Boolean(input["--use-text"]), useRadar: Boolean(input["--use-radar"]), useStroke: Boolean(input["--use-stroke"]) }); }
