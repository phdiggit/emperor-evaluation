"use strict";

(() => {
  const screenEl = document.getElementById("screen");
  if (!screenEl) return;
  let scheduled = false;

  function currentRecord() {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#net\/([^/?#]+)\/first(?:\/|$)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; }
    catch { return null; }
  }

  function firstItems(record) {
    return new Map((record?.net?.component_details?.first || []).map(item => [item.label, item]));
  }

  function ensureStyles() {
    if (document.getElementById("first-item-boundary-style")) return;
    const style = document.createElement("style");
    style.id = "first-item-boundary-style";
    style.textContent = `
      .first-item-boundary-note{margin:10px 0;padding:10px 12px;border-left:3px solid var(--gold);background:#f1eee6;font-size:13px;line-height:1.75}
      .first-item-boundary-mini{display:block;margin-top:4px;font:12px/1.55 "Microsoft YaHei",sans-serif;color:var(--muted)}
    `;
    document.head.append(style);
  }

  function addCardNote(card, key, text) {
    const body = card?.querySelector(".net-metric-body");
    if (!body || body.querySelector(`[data-first-boundary="${key}"]`)) return;
    const note = document.createElement("p");
    note.className = "first-item-boundary-note";
    note.dataset.firstBoundary = key;
    note.textContent = text;
    body.insertBefore(note, body.firstChild);
  }

  function addSummaryNote(summary, key, text) {
    if (!summary || summary.querySelector(`[data-first-boundary="${key}"]`)) return;
    const note = document.createElement("p");
    note.className = "first-item-boundary-note";
    note.dataset.firstBoundary = key;
    note.textContent = text;
    const flow = summary.querySelector(".first-item-flow");
    if (flow?.nextSibling) summary.insertBefore(note, flow.nextSibling);
    else summary.append(note);
  }

  function clarifyZeroCommander(items) {
    const item = items.get("C军事统帅与战争解题");
    if (!item || Number(item.value) !== 0 || !/NONE/i.test(`${item.grade || ""} ${item.note || ""}`)) return;
    const card = document.getElementById("net-first-c");
    const summary = card?.querySelector(":scope > summary");
    for (const small of summary?.querySelectorAll("small") || []) {
      let text = small.textContent;
      text = text.replace(/C-0/g, "本项未计本人统帅分");
      text = text.replace(/责任路线\s*=\s*NONE/gi, "主链无本人可归责统帅责任");
      small.textContent = text;
    }
    addCardNote(
      card,
      "commander-zero",
      "这里的0分只表示创业／统一主链没有计入可归责给本人的实际统帅分，不等于人物画像中的军事判断与统帅能力为0。"
    );
  }

  function clarifyAttributionScore(items) {
    const item = items.get("A统一贡献");
    const value = Number(item?.value);
    if (!item || !(value > 0 && value < 120)) return;
    const card = document.getElementById("net-first-a");
    const summary = card?.querySelector(":scope > summary");
    for (const small of summary?.querySelectorAll("small") || []) {
      if (/成果信用U\s*=/.test(small.textContent)) small.textContent = "稳定控制成果换算分";
    }
    addCardNote(
      card,
      "attribution-score",
      `这里的 ${value.toFixed(1)} / 120 是由稳定控制成果规模和本人归责共同换算出的 A 分，不是“统一完成度”。区域项目即使把本区域做完整，A也会低于全国尺度；共同项目还要再按个人责任分账。`
    );
    const scoreBox = document.querySelector(".first-item-reader-summary .first-item-score-grid div:first-child");
    if (scoreBox && !scoreBox.querySelector('[data-first-boundary="attribution-score-mini"]')) {
      const mini = document.createElement("small");
      mini.className = "first-item-boundary-mini";
      mini.dataset.firstBoundary = "attribution-score-mini";
      mini.textContent = "成果规模／归责换分，不是统一完成度";
      scoreBox.append(mini);
    }
  }

  function clarifySharedOutcome() {
    const summary = document.querySelector(".first-item-reader-summary .first-item-outcome");
    if (!summary || summary.dataset.sharedOutcome === "done") return;
    const body = document.querySelector("#net-first-a .net-metric-body");
    if (!body) return;
    const label = Array.from(body.querySelectorAll(":scope > .label")).find(node =>
      node.textContent.trim() === "当前人物实际留下了什么"
    );
    if (!label) return;
    const chunks = [];
    let node = label.nextElementSibling;
    while (node && !node.classList.contains("label") && node.tagName !== "DETAILS") {
      const text = node.textContent.replace(/\s+/g, " ").trim();
      if (text) chunks.push(text);
      node = node.nextElementSibling;
    }
    const text = chunks.join(" ");
    const personal = text.match(/个人分得[^。]+。?/);
    if (!personal) return;
    const project = text.slice(0, personal.index).trim();
    const afterPersonal = text.slice(personal.index + personal[0].length).trim();
    const content = afterPersonal.split("分账对象与分数")[0].trim();
    const ordered = [
      personal[0].trim(),
      content,
      project ? `共同项目总成果：${project}` : "",
    ].filter(Boolean).join(" ");
    summary.textContent = ordered.length > 240 ? `${ordered.slice(0, 238)}…` : ordered;
    summary.dataset.sharedOutcome = "done";
  }

  function clarifyZeroOutcome(items) {
    const a = Number(items.get("A统一贡献")?.value || 0);
    const gross = Number(items.get("四轴合计")?.value || 0);
    const cost = Number(items.get("军事成本扣分")?.value || 0);
    const net = Number(items.get("第一项净分")?.value || 0);
    if (!(a === 0 && gross > 0)) return;
    const parts = ["本项仍可能有创业条件、组织整合等过程分，但统一成果为0，表示没有留下符合本项口径的稳定统一成果；过程分不等于最终统一成果。"];
    if (net === 0 && cost >= gross) parts.push("军事成本扣除后，第一项净分归零，因此也不形成总榜附加。");
    addSummaryNote(document.querySelector(".first-item-reader-summary"), "zero-outcome", parts.join(""));
    addCardNote(
      document.getElementById("net-first-a"),
      "zero-outcome-a",
      "统一成果为0：这里评价的是最终留下的稳定控制成果，不会因为存在创业或组织过程就自动给统一成果分。"
    );
  }

  function enhance() {
    const record = currentRecord();
    if (!record?.net) return;
    const items = firstItems(record);
    if (!items.size) return;
    ensureStyles();
    clarifyZeroCommander(items);
    clarifyAttributionScore(items);
    clarifySharedOutcome();
    clarifyZeroOutcome(items);
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      enhance();
    });
  }

  new MutationObserver(schedule).observe(screenEl, {childList: true, subtree: true});
  window.addEventListener("hashchange", schedule);
  schedule();
})();
