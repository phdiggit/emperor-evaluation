import fs from "node:fs/promises";
import path from "node:path";
import { getChromium, loadData, pageRadar, pageTemplate, render, root } from "./render-common.js";
import { radarDebugHtml } from "./radar.js";

export async function renderBase(input) {
  const data = await loadData(input); const output = path.join(root, "output", data.id, "base");
  await fs.mkdir(output, { recursive: true }); await fs.mkdir(path.join(root, "output", data.id, "debug"), { recursive: true }); const browser = await getChromium().launch({ headless: true });
  try {
    await render(browser, await pageTemplate("page1.html"), data, pageRadar(data, 1), path.join(output, "page1_base.png"));
    await render(browser, await pageTemplate("page2.html"), data, pageRadar(data, 2), path.join(output, "page2_base.png"));
    const debug = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
    await debug.setContent(radarDebugHtml(data), { waitUntil: "load" }); await debug.screenshot({ path: path.join(root, "output", data.id, "debug", "radar_debug.png") }); await debug.close();
  } finally { await browser.close(); }
  return data;
}

if (process.argv[1] === new URL(import.meta.url).pathname) { if (!process.argv[2]) throw new Error("用法：node scripts/render-base.js data/emperors/<id>.json"); await renderBase(process.argv[2]); }
