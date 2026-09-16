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
      if (/成果信用U\s*=/.test(small.textContent)) small.textContent = "本人归责后的统一成果分";
    }
    addCardNote(
      card,
      "attribution-score",
      `这里的 ${value.toFixed(1)} / 120 是本人归责后的统一成果分，不是“只完成了 ${Math.round(value / 1.2)}% 的统一”。共同完成的成果会按正式责任分账。`
    );
    const scoreBox = document.querySelector(".first-item-reader-summary .first-item-score-grid div:first-child");
    if (scoreBox && !scoreBox.querySelector('[data-first-boundary="attribution-score-mini"]')) {
      const mini = document.createElement("small");
      mini.className = "first-item-boundary-mini";
      mini.dataset.firstBoundary = "attribution-score-mini";
      mini.textContent = "本人归责分，不是统一完成度";
      scoreBox.append(mini);
    }
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

  function directLabels(card) {
    return new Set(Array.from(card?.querySelectorAll(".net-metric-body > .label") || [])
      .map(label => label.textContent.trim()));
  }

  function clarifyMissingPersonDetails() {
    const summary = document.querySelector(".first-item-reader-summary");
    if (!summary) return;
    const checks = [
      ["统一成果", "net-first-a", ["当前人物实际留下了什么"]],
      ["创业难度与效率", "net-first-b1", ["当前人物的起点", "当前人物面对的对手", "完成效率"]],
      ["组织整合", "net-first-b2", ["并行执行", "专业覆盖与组织杠杆", "异质整合"]],
      ["本人统帅", "net-first-c", ["本人走哪条责任路线", "当前人物为什么是这个档"]],
    ];
    const missing = [];
    for (const [name, id, required] of checks) {
      const card = document.getElementById(id);
      if (!card) {
        missing.push(name);
        continue;
      }
      const labels = directLabels(card);
      if (required.some(label => !labels.has(label))) missing.push(name);
    }
    if (!missing.length) return;
    addSummaryNote(
      summary,
      "formal-detail-load",
      `“${missing.join("、")}”的人物化正式条目没有完整加载。本页分值仍读取正式结算；具体依据请以各卡片下方“原始正式文档”为准。刷新后仍出现此提示时，应检查正式文档标题或字段格式。`
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
    clarifyZeroOutcome(items);
    clarifyMissingPersonDetails();
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
