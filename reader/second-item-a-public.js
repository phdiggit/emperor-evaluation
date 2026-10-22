"use strict";

// Historical words come verbatim from the authored formal A record.
(() => {
  const screen = document.getElementById("screen");
  if (!screen) return;
  function currentRecord() {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#net\/([^/?#]+)\/(?:second|all)(?:\/|$)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; } catch { return null; }
  }
  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }
  function fold(title, text) {
    if (!text) return null;
    const node = make("details", "second-item-a-boundary");
    node.append(make("summary", "", title), make("p", "prose", text));
    return node;
  }
  function card(entry, record) {
    const li = make("li", "adjudication-material-card second-item-a-card");
    li.dataset.institutionNodeId = entry.institution_node_id;
    const head = make("div", "adjudication-material-head");
    head.append(make("strong", "", entry.public_label));
    const meta = make("div", "adjudication-material-meta");
    for (const text of [entry.public_direction, ...(entry.public_tags || [])]) {
      if (text) meta.append(make("span", "adjudication-material-chip", text));
    }
    head.append(meta);
    li.append(head, make("p", "adjudication-material-basis", entry.public_basis));
    const boundary = fold("范围与边界", entry.public_boundary);
    if (boundary) li.append(boundary);
    const sources = make("details", "second-item-a-sources");
    sources.append(make("summary", "", "本条证据与原始记录"));
    if (entry.public_reception) sources.append(make("p", "second-item-a-reception", entry.public_reception));
    if (typeof link === "function") {
      const holder = make("p", "sources");
      holder.innerHTML = (entry.public_sources || []).map(source => link(source.ref, source.label + " ↗", record)).join(" ");
      sources.append(holder);
    }
    li.append(sources);
    return li;
  }
  function section(title, entries, record) {
    if (!entries.length) return document.createDocumentFragment();
    const wrapper = make("section", "second-item-a-group");
    const list = make("ul", "adjudication-material-list second-item-a-list");
    list.replaceChildren(...entries.map(entry => card(entry, record)));
    wrapper.append(make("h4", "", title), list);
    return wrapper;
  }
  function patch() {
    const record = currentRecord();
    const item = record?.net?.component_details?.method?.find(value => value.label === "A制度建设");
    const detail = Array.from(screen.querySelectorAll(".net-metric-detail[data-second-source-label]"))
      .find(node => node.dataset.secondSourceLabel === "A制度建设");
    const body = detail?.querySelector(":scope > .net-metric-body");
    if (!item || !body) return;
    const key = JSON.stringify(item);
    if (body.dataset.aPublicKey === key && body.querySelector(":scope > .second-item-a-reading")) return;
    const story = item.reader_story;
    const summary = item.reader_summary;
    const evidence = item.reader_public_evidence_items;
    if (!story || !summary || !Array.isArray(evidence)) {
      body.replaceChildren(make("p", "notice", "制度建设的正式阅读正文尚未同步。"));
      body.dataset.aPublic = "missing";
      return;
    }
    const reading = make("div", "second-item-a-reading");
    reading.append(make("p", "prose second-item-a-story", story));
    const reason = make("div", "second-item-a-summary");
    reason.append(make("strong", "", "为什么是这个等级"), make("p", "prose", summary));
    reading.append(reason);
    const grouped = {positive:[], negative:[], mixed:[]};
    for (const entry of evidence) {
      const direction = entry.public_direction;
      const key = direction === "正向" ? "positive" : direction === "负向" ? "negative" : "mixed";
      grouped[key].push(entry);
    }
    reading.append(section("制度建设与修复", grouped.positive, record));
    reading.append(section("制度性损害", grouped.negative, record));
    reading.append(section("收益与代价并存", grouped.mixed, record));
    body.replaceChildren(reading);
    const boundary = fold("评价范围与证据边界", item.reader_boundary);
    if (boundary) body.append(boundary);
    const scoreHow = globalThis.SecondItemScoreHowDetails?.(item, "A制度建设");
    if (scoreHow) body.append(scoreHow);
    const audit = make("details", "second-item-dedicated-audit");
    audit.append(make("summary", "", "完整正式记录"));
    if (typeof link === "function") {
      const holder = make("p", "sources");
      holder.innerHTML = [...new Set([item.source, ...(item.reader_source_refs || [])].filter(Boolean))]
        .map(ref => link(ref, "正式记录 ↗", record)).join(" ");
      audit.append(holder);
    }
    body.append(audit);
    body.dataset.aPublic = "done";
    body.dataset.aPublicKey = key;
    body.dataset.secondPublicOwner = "A";
  }
  globalThis.SecondItemAPublic = Object.freeze({patch});
})();
