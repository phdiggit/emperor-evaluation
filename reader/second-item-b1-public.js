"use strict";

// B1 官僚治理专用阅读器：只消费构建后人物记录中的正式人物级公开投影。
// 分组依据仅来自 public_direction / public_tags，不回读原始 profile。
(() => {
  const screen = document.getElementById("screen");
  if (!screen) return;

  let scheduled = false;

  function currentRecord() {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#net\/([^/?#]+)\/second(?:\/|$)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; } catch { return null; }
  }

  function methodItem(record) {
    return (record?.net?.component_details?.method || []).find(item => item.label === "B1官僚治理") || null;
  }

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function detailsBlock(title, text, className = "") {
    const value = String(text || "").trim();
    if (!value) return null;
    const details = make("details", className);
    details.append(make("summary", "", title), make("p", "prose", value));
    return details;
  }

  function evidenceGroup(entry) {
    const tags = Array.isArray(entry?.public_tags) ? entry.public_tags : [];
    if (tags.includes("不单独计入")) return "boundary";
    if (tags.includes("并入同一运行链")) return "supplement";
    const direction = String(entry?.public_direction || "");
    if (direction === "边界材料") return "boundary";
    if (direction.startsWith("正向")) return "positive";
    if (direction.startsWith("负向")) return "negative";
    return "mixed";
  }

  function groupedEvidence(evidence) {
    const groups = {positive:[], negative:[], mixed:[], supplement:[], boundary:[]};
    for (const entry of evidence || []) groups[evidenceGroup(entry)].push(entry);
    return groups;
  }

  function card(entry, {supplement = false} = {}) {
    const api = globalThis.SecondItemMaterialCards;
    const direction = String(entry?.public_direction || "");
    const tags = (Array.isArray(entry?.public_tags) ? entry.public_tags : [])
      .filter(tag => !/^(?:正向|负向|正负并存)/.test(String(tag)));
    if (api?.card) return api.card({
      title: entry?.public_label || "行政运行机制",
      direction,
      tags,
      body: entry?.public_basis,
      boundary: entry?.public_boundary,
      supplement,
      verbatim: true,
    });

    const li = make("li", supplement ? "second-item-b1-card second-item-b1-supplement" : "second-item-b1-card");
    li.append(make("strong", "", entry?.public_label || "行政运行机制"));
    if (entry?.public_basis) li.append(make("p", "", entry.public_basis));
    return li;
  }

  function group(title, entries, {supplement = false} = {}) {
    const api = globalThis.SecondItemMaterialCards;
    if (api?.group) return api.group(title, entries.map(entry => card(entry, {supplement})));
    if (!entries.length) return document.createDocumentFragment();
    const section = make("section", "second-item-b1-group");
    section.append(make("h4", "", title));
    const list = make("ul", "second-item-b1-list");
    list.replaceChildren(...entries.map(entry => card(entry, {supplement})));
    section.append(list);
    return section;
  }

  function publicKey(item) {
    return JSON.stringify([
      item?.reader_story || "",
      item?.reader_responsibility || "",
      item?.reader_summary || "",
      item?.reader_boundary || "",
      item?.reader_public_evidence_items || [],
      item?.reader_how || "",
    ]);
  }

  function appendDedicatedAudit(body, item, record) {
    const details = make("details", "second-item-dedicated-audit");
    details.append(make("summary", "", "完整正式记录与来源"));
    const refs = [...new Set([item?.source, item?.applied_source, ...(item?.reader_source_refs || [])].filter(Boolean))];
    if (refs.length && typeof link === "function") {
      const holder = make("p", "sources");
      holder.innerHTML = refs.map((ref, i) => link(ref, i ? "补充正式记录 ↗" : "正式记录 ↗", record)).join("");
      details.append(holder);
    }
    body.append(details);
  }

  function ensureStyles() {
    if (document.getElementById("second-item-b1-public-style")) return;
    const style = document.createElement("style");
    style.id = "second-item-b1-public-style";
    style.textContent = `
      .second-item-b1-reading{margin:4px 0 8px}
      .second-item-b1-intro{margin:4px 0 14px;line-height:1.75}
      .second-item-b1-summary{margin:10px 0 16px;padding:11px 13px;border-left:3px solid var(--gold);background:#f1eee6;font-size:12px;line-height:1.75}
      .second-item-b1-group{margin:14px 0 18px}
      .second-item-b1-group>h4{margin:0 0 8px;font-size:15px}
      .second-item-b1-list{list-style:none;margin:0;padding:0;display:grid;gap:8px}
      .second-item-b1-card{margin:0;padding:10px 12px;border:1px solid var(--line);border-radius:5px;background:#fff}
      .second-item-b1-supplement{background:#f7f5ef}
    `;
    document.head.append(style);
  }

  function patch() {
    ensureStyles();
    const record = currentRecord();
    if (!record) return;
    const item = methodItem(record);
    const detail = Array.from(document.querySelectorAll(".net-metric-detail[data-second-source-label]"))
      .find(node => node.dataset.secondSourceLabel === "B1官僚治理");
    const body = detail?.querySelector(":scope > .net-metric-body");
    if (!item || !body) return;

    const evidence = Array.isArray(item.reader_public_evidence_items) ? item.reader_public_evidence_items : [];
    const formalSummary = String(item.reader_summary || "").trim();
    const story = String(item.reader_story || "").trim();
    const responsibility = String(item.reader_responsibility || "").trim();
    const key = publicKey(item);
    if (body.dataset.secondPublicBodyKey === key && body.querySelector(":scope > .second-item-b1-reading")) return;

    if (!evidence.length || !formalSummary || !story || !responsibility) {
      body.innerHTML = "";
      body.append(make("p", "notice", "官僚治理的正式人物级公开投影尚未同步。"));
      body.dataset.b1Public = "missing";
      body.dataset.secondPublicBodyKey = key;
      return;
    }

    const groups = groupedEvidence(evidence);
    body.innerHTML = "";
    const reading = make("div", "second-item-public-reading second-item-b1-reading");
    reading.append(make("h4", "", "具体经历"), make("p", "prose second-item-b1-story", story));
    reading.append(make("h4", "", "本人承担什么责任"), make("p", "prose second-item-b1-responsibility", responsibility));
    const reason = make("div", "second-item-b1-summary");
    reason.append(make("strong", "", "为什么是这个等级"), make("p", "prose", formalSummary));
    reading.append(reason);
    reading.append(group("正向行政运行", groups.positive));
    reading.append(group("负向行政失灵", groups.negative));
    reading.append(group("正负并存的行政机制", groups.mixed));
    reading.append(group("并入同一运行链的补充材料", groups.supplement, {supplement:true}));
    reading.append(group("边界材料（不单独计入）", groups.boundary));
    body.append(reading);

    const boundaryText = item.reader_boundary;
    const boundary = detailsBlock("总体范围与边界", boundaryText);
    if (boundary) body.append(boundary);

    const scoreHow = globalThis.SecondItemScoreHowDetails?.(item, "B1官僚治理");
    if (scoreHow) body.append(scoreHow);
    appendDedicatedAudit(body, item, record);

    body.dataset.secondPublicBodyKey = key;
    body.dataset.secondPublicOwner = "B1";
    body.dataset.b1Public = "done";
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      patch();
    });
  }

  new MutationObserver(schedule).observe(screen, {childList:true, subtree:true, characterData:true});
  window.addEventListener("hashchange", schedule);
  schedule();
})();
