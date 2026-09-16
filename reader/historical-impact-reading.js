"use strict";

(() => {
  const screenEl = document.getElementById("screen");
  if (!screenEl) return;
  let scheduled = false;

  const internalWording = [
    [/项目战役底账/g, "正式战役材料"],
    [/项目正式战役群/g, "正式战役材料"],
    [/项目制度行政底账/g, "制度行政正式材料"],
    [/项目第一项A/g, "统治绩效第一项"],
    [/项目B2把/g, "相关创业组织材料将"],
    [/项目B2/g, "相关创业组织材料"],
    [/项目还明确剔除了/g, "现有裁决已排除"],
    [/项目重审明确把/g, "现有裁决将"],
    [/项目重审/g, "现有裁决"],
    [/项目底账/g, "现有正式材料"],
    [/项目(?:M1|M2|M3|M4|M5|C1|C2|C3|C4|C5)/g, "相关人物画像材料"],
  ];

  function currentPersonRecord() {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#person\/([^/?#]+)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; }
    catch { return null; }
  }

  function compareRecordFor(node) {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#compare\/([^/?#]+)\/([^/?#]+)/);
    const cell = node.closest("td");
    if (!match || !cell || cell.cellIndex < 1 || cell.cellIndex > 2) return null;
    try {
      return byId.get(decodeURIComponent(match[cell.cellIndex])) || null;
    } catch {
      return null;
    }
  }

  function recordFor(node) {
    return currentPersonRecord() || compareRecordFor(node);
  }

  function historyWrappers() {
    const roots = [];
    const person = document.getElementById("history-evidence");
    if (person) roots.push(person);
    for (const details of document.querySelectorAll(".comparison details")) {
      const summary = details.querySelector(":scope > summary");
      if (summary?.textContent.includes("展开历史影响依据")) roots.push(details);
    }
    return roots;
  }

  function publicTotalReason(impact) {
    const foundation = impact?.foundation || {};
    const dims = impact?.dimensions || {};
    const scope = dims.scope?.grade;
    const depth = dims.depth_duration?.grade;
    const causal = dims.personal_causality?.grade;
    const paradigm = dims.paradigm?.grade;
    const base = foundation.base_band;
    const internal = foundation.decided_internal_band || impact?.internal_band;
    const published = foundation.decided_public_grade || impact?.public_grade;
    if (!scope || !depth || !causal || !paradigm || !internal || !published) return "";
    const baseText = base
      ? `范围${scope}、深度${depth}先形成基础影响量级${base}`
      : `范围${scope}、深度${depth}先确定基础影响量级`;
    return `${baseText}；个人因果${causal}与政治范式${paradigm}再按各自规则修正，不把四维字母直接求平均。最终内部判断为${internal}，映射为公众等级${published}。`;
  }

  function rewriteTotalReason(root, record) {
    const reason = publicTotalReason(record?.impact);
    if (!reason) return;
    for (const details of root.querySelectorAll("details")) {
      const summary = details.querySelector(":scope > summary");
      if (!summary || !/(历史影响等级为什么这样定|公众总档为什么这样定)/.test(summary.textContent)) continue;
      if (details.dataset.publicTotalReason === reason) continue;
      while (summary.nextSibling) summary.nextSibling.remove();
      const paragraph = document.createElement("p");
      paragraph.className = "prose impact-total-reason";
      paragraph.textContent = reason;
      details.append(paragraph);
      details.dataset.publicTotalReason = reason;
    }
  }

  function cleanInternalWording(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      const text = node.nodeValue || "";
      let next = text;
      for (const [pattern, replacement] of internalWording) next = next.replace(pattern, replacement);
      if (next !== text) node.nodeValue = next;
    }
  }

  function ensureScaleNote() {
    const panel = document.getElementById("person-impact");
    const dimensions = panel?.querySelector(":scope .dimensions");
    if (!panel || !dimensions || panel.querySelector(":scope > .impact-scale-note")) return;
    const note = document.createElement("p");
    note.className = "subline impact-scale-note";
    note.textContent = "总档与下面四维使用不同刻度：四维保留 S−、A+ 等中间档，不能与上方总档直接横比，也不做平均。";
    dimensions.before(note);
  }

  function enhance() {
    ensureScaleNote();
    for (const root of historyWrappers()) {
      const record = recordFor(root);
      rewriteTotalReason(root, record);
      cleanInternalWording(root);
    }
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
