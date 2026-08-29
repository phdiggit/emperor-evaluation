import fs from "node:fs/promises";
import path from "node:path";
import { getChromium, loadData, pageRadar, pageTemplate, render, root } from "./render-common.js";

const common = `body,.page{background:transparent!important}.page:before,.portrait-zone,.mini-portrait,.cloud,.landscape,.palace{display:none!important}`;
const text = `${common}.outer,.inner,.corner,.radar-panel,.mini-radar,.divider,.tag-title:before,.tag-title:after{display:none!important}.tag{background:transparent!important;border-color:transparent!important;outline:0!important}.tag:before,.tag:after{display:none!important}.side-label,.mini-label{background:transparent!important;border-color:transparent!important;box-shadow:none!important}.card{border:0!important;background:transparent!important;box-shadow:none!important}.card:before,.card:after,.icon{display:none!important}.card .grade{border-color:transparent!important;outline:0!important;background:transparent!important}`;
const radar = `${common}#app>*:not(.radar-panel):not(.mini-radar){display:none!important}.radar .axis,.radar .grade,.radar .level{display:none!important}`;
const stroke = `${common}.radar-panel,.mini-radar,.side-label,.mini-label,.info,.tag-title,.tags,.headline,.identity,.years,.axis,.text,.grade,.icon{display:none!important}.card{background:transparent!important;box-shadow:none!important}`;

export async function renderOverlay(input) {
  const data = await loadData(input); const output = path.join(root, "output", data.id, "overlay"); await fs.mkdir(output, { recursive: true });
  const browser = await getChromium().launch({ headless: true });
  try { for (const pageNumber of [1, 2]) { const html = await pageTemplate(`page${pageNumber}.html`); const chart = pageRadar(data, pageNumber); const options = data.overlayOptions?.[`page${pageNumber}`] ?? {}; const enabled = key => data.overlay?.[key] !== false; const textCss = `${text}${!enabled("mainTitle") ? ".name,.headline{display:none!important}" : ""}${!enabled("subtitle") ? ".subtitle,.identity{display:none!important}" : ""}${!enabled("years") ? ".years{display:none!important}" : ""}${!enabled("cards") ? ".cards{display:none!important}" : ""}${!enabled("tags") ? ".tag-title,.tags{display:none!important}" : ""}${options.renderSideLabel === false || !enabled("sideLabel") ? ".side-label,.mini-label{display:none!important}" : ""}`; const radarCss = `${radar}${!enabled("radar") ? ".radar-panel,.mini-radar{display:none!important}" : ""}`; const strokeCss = `${stroke}${!enabled("frame") ? ".outer,.inner,.corner{display:none!important}" : ""}${!enabled("cards") ? ".cards{display:none!important}" : ""}${!enabled("tags") ? ".tags{display:none!important}" : ""}`; await render(browser, html, data, chart, path.join(output, `page${pageNumber}_overlay_text.png`), textCss); await render(browser, html, data, chart, path.join(output, `page${pageNumber}_overlay_radar.png`), radarCss); await render(browser, html, data, chart, path.join(output, `page${pageNumber}_overlay_stroke.png`), strokeCss); await render(browser, html, data, chart, path.join(output, `page${pageNumber}_overlay_precise.png`), common); } }
  finally { await browser.close(); }
  return data;
}

if (process.argv[1] === new URL(import.meta.url).pathname) { if (!process.argv[2]) throw new Error("用法：node scripts/render-overlay.js data/emperors/<id>.json"); await renderOverlay(process.argv[2]); }
