import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";
import { root } from "./render-common.js";

async function rgba(file, size) { const image = sharp(file); if (size) image.resize({ ...size, fit: "cover", position: "centre" }); return image.ensureAlpha().raw().toBuffer({ resolveWithObject: true }); }
const alphaCount = buffer => { let total = 0; for (let index = 3; index < buffer.length; index += 4) if (buffer[index]) total += 1; return total; };

export async function verifyOverlay(id) {
  const output = path.join(root, "output", id); const report = { id, pages: {} };
  await fs.mkdir(path.join(output, "debug"), { recursive: true });
  for (const page of [1, 2]) {
    const layer = name => path.join(output, "overlay", `page${page}_overlay_${name}.png`); const text = await rgba(layer("text")); const { width, height } = text.info;
    const [radar, stroke, ai, final] = await Promise.all([rgba(layer("radar")), rgba(layer("stroke")), rgba(path.join(output, "ai", `page${page}_ai.png`), { width, height }), rgba(path.join(output, "final", `page${page}_final_v2.png`))]);
    const pixels = width * height;
    if (![radar, stroke, ai, final].every(image => image.info.width === width && image.info.height === height)) throw new Error(`page${page} 尺寸不一致`);
    let overlap = 0; let outsideDiff = 0; const union = Buffer.alloc(pixels * 4);
    for (let pixel = 0, offset = 0; pixel < pixels; pixel += 1, offset += 4) {
      const textAlpha = text.data[offset + 3]; const radarAlpha = radar.data[offset + 3]; const strokeAlpha = stroke.data[offset + 3];
      if (textAlpha && radarAlpha) overlap += 1;
      const covered = textAlpha || radarAlpha || strokeAlpha; if (covered) union[offset] = union[offset + 1] = union[offset + 2] = union[offset + 3] = 255;
      if (!covered && (ai.data[offset] !== final.data[offset] || ai.data[offset + 1] !== final.data[offset + 1] || ai.data[offset + 2] !== final.data[offset + 2] || ai.data[offset + 3] !== final.data[offset + 3])) outsideDiff += 1;
    }
    await sharp(union, { raw: { width, height, channels: 4 } }).png().toFile(path.join(output, "overlay", `page${page}_overlay_union_mask.png`));
    report.pages[`page${page}`] = { pixels, textNonTransparent: alphaCount(text.data), radarNonTransparent: alphaCount(radar.data), strokeNonTransparent: alphaCount(stroke.data), textRadarOverlap: overlap, finalAiOutsideOverlayDifference: outsideDiff };
    if (overlap !== 0 || outsideDiff !== 0) throw new Error(`page${page} 覆盖层验收失败：text/radar=${overlap}，overlay 外差异=${outsideDiff}`);
  }
  await fs.writeFile(path.join(output, "debug", "overlay-report.json"), JSON.stringify(report, null, 2) + "\n", "utf8");
  console.log(JSON.stringify(report)); return report;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) { const id = process.argv[3]; if (process.argv[2] !== "--id" || !id) throw new Error("用法：node scripts/verify-overlay.js --id <id>"); await verifyOverlay(id); }
