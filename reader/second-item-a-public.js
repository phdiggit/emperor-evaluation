"use strict";

// A 制度建设专用阅读器：只消费构建后人物记录中的正式人物级公开投影。
// 不回读制度节点正式分片，也不在浏览器中重新组合裁决来源。
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
    return (record?.net?.component_details?.method || []).find(item => item.label === "A制度建设") || null;
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

  function groupKey(entry) {
    const direction = String(entry?.public_direction || "");
    if (direction.startsWith("正向")) return "positive";
    if (direction.startsWith("负向")) return "negative";
    if (direction) return "mixed";
    return "other";
  }

  function groups(evidence) {
    const result = {positive:[], negative:[], mixed:[], other:[]};
    for (const entry of evidence || []) result[groupKey(entry)].push(entry);
    return result;
  }

  function card(entry) {
    const api = globalThis.SecondItemMaterialCards;
    if (api?.card) return api.card({
      title: entry?.public_label || "制度建设材料",
      direction: entry?.public_direction,
      tags: entry?.public_tags || [],
      body: entry?.public_basis,
      boundary: entry?.public_boundary,
    });

    const li = make("li", "second-item-a-card");
    li.append(make("strong", "", entry?.public_label || "制度建设材料"));
    if (entry?.public_basis) li.append(make("p", "", entry.public_basis));
    return li;
  }

  function section(title, entries) {
    const api = globalThis.SecondItemMaterialCards;
    if (api?.group) return api.group(title, entries.map(card));
    if (!entries.length) return document.createDocumentFragment();
    const wrapper = make("section", "second-item-a-group");
    wrapper.append(make("h4", "", title));
    const list = make("ul", "second-item-a-list");
    list.replaceChildren(...entries.map(card));
    wrapper.append(list);
    return wrapper;
  }

  function publicKey(item) {
    return JSON.stringify([
      item?.reader_summary || "",
      item?.reader_boundary || "",
      item?.reader_public_evidence_items || [],
      item?.reader_how || "",
    ]);
  }

  function appendDedicatedAudit(body, item, record) {
    const api = globalThis.SecondItemMaterialCards;
    const details = make("details", "second-item-dedicated-audit");
    details.append(make("summary", "", "原始记录与计算口径"));
    const how = api?.publicEnumText ? api.publicEnumText(item?.reader_how || "") : String(item?.reader_how || "").trim();
    if (how) details.append(make("p", "prose", how));
    const refs = [...new Set([item?.source, item?.applied_source, ...(item?.reader_source_refs || [])].filter(Boolean))];
    if (refs.length && typeof link === "function") {
      const holder = make("p", "sources");
      holder.innerHTML = refs.map((ref, i) => link(ref, i ? "补充正式记录 ↗" : "正式记录 ↗", record)).join("");
      details.append(holder);
    }
    body.append(details);
  }

  function ensureStyles() {
    if (document.getElementById("second-item-a-public-style")) return;
    const style = document.createElement("style");
    style.id = "second-item-a-public-style";
    style.textContent = `
      .second-item-a-reading{margin:4px 0 8px}
      .second-item-a-intro{margin:4px 0 14px;line-height:1.75}
      .second-item-a-summary{margin:10px 0 16px;padding:11px 13px;border-left:3px solid var(--gold);background:#f1eee6;font-size:12px;line-height:1.75}
      .second-item-a-group{margin:14px 0 18px}
      .second-item-a-group>h4{margin:0 0 8px;font-size:15px}
      .second-item-a-list{list-style:none;margin:0;padding:0;display:grid;gap:8px}
      .second-item-a-card{margin:0;padding:10px 12px;border:1px solid var(--line);border-radius:5px;background:#fff}
    `;
    document.head.append(style);
  }

  function patch() {
    ensureStyles();
    const record = currentRecord();
    if (!record) return;
    const item = methodItem(record);
    const detail = Array.from(document.querySelectorAll(".net-metric-detail[data-second-source-label]"))
      .find(node => node.dataset.secondSourceLabel === "A制度建设");
    const body = detail?.querySelector(":scope > .net-metric-body");
    if (!item || !body) return;

    const evidence = Array.isArray(item.reader_public_evidence_items) ? item.reader_public_evidence_items : [];
    const summary = String(item.reader_summary || "").trim();
    const key = publicKey(item);
    if (body.dataset.aPublicKey === key && body.querySelector(":scope > .second-item-a-reading")) return;

    if (!evidence.length || !summary) {
      body.innerHTML = "";
      body.append(make("p", "notice", "制度建设的正式人物级公开投影尚未同步。"));
      body.dataset.aPublic = "missing";
      body.dataset.aPublicKey = key;
      return;
    }

    body.innerHTML = "";
    const reading = make("div", "second-item-a-reading");
    reading.append(make("div", "label", "制度建设材料"));
    reading.append(make("p", "second-item-a-intro", "每张卡直接读取正式人物级公开投影；没有可单列制度节点时，会明确显示对应说明，不由页面自行补判。"));
    reading.append(make("div", "second-item-a-summary", summary));

    const grouped = groups(evidence);
    reading.append(section("正向制度建设", grouped.positive));
    reading.append(section("负向制度设计与制度性损害", grouped.negative));
    reading.append(section("正负并存的制度", grouped.mixed));
    reading.append(section("其他正式说明", grouped.other));
    body.append(reading);

    const boundary = detailsBlock("总体范围与边界", item.reader_boundary);
    if (boundary) body.append(boundary);

    const gradeDetails = detailsBlock("为什么最终是这个等级？", summary);
    if (gradeDetails) body.append(gradeDetails);
    const scoreHow = globalThis.SecondItemScoreHowDetails?.(item, "A制度建设");
    if (scoreHow) body.append(scoreHow);
    appendDedicatedAudit(body, item, record);

    body.dataset.aPublic = "done";
    body.dataset.aPublicKey = key;
    body.dataset.secondPublicOwner = "A";
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
