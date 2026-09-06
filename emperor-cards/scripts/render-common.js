import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { AXES, radarSvg } from "./radar.js";
import { assertEmperor } from "./utils.js";

export const here = path.dirname(fileURLToPath(import.meta.url));
export const root = path.resolve(here, "..");
export const repoRoot = path.resolve(root, "..");
const require = createRequire(import.meta.url);

export function getChromium() {
  try { return require("playwright").chromium; }
  catch { return require(path.join(repoRoot, ".tmp", "bilibili_rank_analysis", "node_modules", "playwright")).chromium; }
}

export async function loadData(input) {
  const data = JSON.parse(await fs.readFile(path.resolve(input), "utf8"));
  assertEmperor(data);
  for (const axis of AXES) if (!data.axes[axis]) throw new Error(`缺少固定轴：${axis}`);
  if (data.cards.map(card => card.axis).join("|") !== AXES.join("|")) throw new Error("cards 必须按固定八轴顺序排列");
  const portrait = typeof data.portrait === "string" ? data.portrait : data.portrait.src;
  const portraitPath = path.resolve(root, portrait);
  const portraitBase64 = (await fs.readFile(portraitPath)).toString("base64");
  data.portraitUrl = `data:image/${path.extname(portraitPath).slice(1)};base64,${portraitBase64}`;
  const haloBase64 = (await fs.readFile(path.join(root, "assets", "theme", "gold_brush_halo.png"))).toString("base64");
  data.theme = { id: typeof data.theme === "string" ? data.theme : data.theme?.id, ...(typeof data.theme === "object" ? data.theme : {}), haloUrl: `data:image/png;base64,${haloBase64}` };
  return data;
}

export async function pageTemplate(name) { return fs.readFile(path.join(root, "templates", name), "utf8"); }
export function pageRadar(data, page) {
  return page === 1
    ? radarSvg(data.axes, { width: 600, height: 700, cx: 300, cy: 350, radius: 215, labelRadius: 310, axisFont: 22, gradeFont: 28 })
    : radarSvg(data.axes, { width: 430, height: 270, cx: 220, cy: 111, radius: 96, labelRadius: 145, axisFont: 14, gradeFont: 16 });
}

export async function render(browser, html, data, radar, destination, overlayCss = "", cleanplate = []) {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.setContent(html, { waitUntil: "load" });
  await page.evaluate(({ payload, chart, css, plates }) => {
    window.renderCard(payload, chart);
    for (const plate of plates) { const node = document.createElement("i"); node.className = "ai-cleanplate"; Object.assign(node.style, plate); document.querySelector("#app").prepend(node); }
    if (css) { const style = document.createElement("style"); style.textContent = css; document.head.append(style); }
  }, { payload: data, chart: radar, css: overlayCss, plates: cleanplate });
  await page.screenshot({ path: destination, type: "png", omitBackground: Boolean(overlayCss) });
  await page.close();
}
