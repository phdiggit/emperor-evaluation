"use strict";

(() => {
  const screenEl = document.getElementById("screen");
  if (!screenEl) return;
  let scheduled = false;

  // Reader-only wording cleanup. Keep this semantic and ordered: rewrite the
  // most specific project-language phrases first, then fall back to generic
  // terms that may already have been partially normalized by historyReaderText.
  const internalWording = [
    [/项目制度行政底账(?:已经)?(?:闭合|已有充分证据支持)/g, "现有制度行政材料可确认"],
    [/项目(?:财政民生|民生与财政)底账(?:显示|给出)?/g, "现有民生与财政材料显示"],
    [/项目第三项底账(?:已经)?(?:把|将)?/g, "现有军事与边疆材料"],
    [/项目第一项A/g, "统治绩效第一项"],
    [/项目B2把/g, "相关创业组织材料将"],
    [/项目B2/g, "相关创业组织材料"],
    [/项目还明确剔除了/g, "现有裁决已排除"],
    [/项目既有反向检索(?:已经)?把/g, "现有反向证据已将"],
    [/项目已经把/g, "现有裁决已将"],
    [/项目明确记载/g, "现有正式材料记载"],
    [/项目重审明确把/g, "现有裁决将"],
    [/项目重审把/g, "现有裁决将"],
    [/项目重审/g, "现有裁决"],
    [/被项目定为/g, "在正式材料中评为"],
    [/项目定为/g, "正式材料评为"],
    [/项目D把/g, "相关军事与政权终局材料将"],
    [/项目D/g, "相关军事与政权终局材料"],
    [/项目战役底账/g, "正式战役材料"],
    [/项目正式战役群/g, "正式战役材料"],
    [/项目底账/g, "现有正式材料"],
    [/项目(?:M1|M2|M3|M4|M5|C1|C2|C3|C4|C5)/g, "现有相关材料"],
    [/相关人物画像材料已有充分证据支持/g, "现有材料可确认"],
    [/相关人物画像材料(?:已经)?明确/g, "现有材料明确"],
    [/相关人物画像材料(?:已)?把/g, "现有材料已将"],
    [/相关人物画像材料(?:已)?将/g, "现有材料将"],
    [/相关人物画像材料(?:又)?显示/g, "现有材料还显示"],
    [/相关人物画像材料记录/g, "现有材料记录"],
    [/相关人物画像材料/g, "现有相关材料"],
    [/本轮又补到/g, "现有材料还包括"],
    [/本轮反查/g, "现有材料复核可确认"],
    [/全池人物范式系统扩搜[：:]?/g, ""],
    [/\bC1-(\d+)\b/g, "民生状态第$1档"],
    [/\bC2-(\d+)\b/g, "经济财政状态第$1档"],
    [/\bC3-(\d+)\b/g, "社会安全状态第$1档"],
    [/([\u4e00-\u9fff]{2,12}级)\s+O\d+\b/g, "$1"],
    [/\bO([1-6])\b/g, "对手压力第$1级"],
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

  function ruleClause(value, kind) {
    let text = String(value || "").replace(/\s+/g, " ").trim();
    if (!text) return "";
    if (kind === "causal") {
      text = text.replace(/^[SABCDE](?:[+−-])?个人因果(?:仅作用于这些核心足迹)?[，；:]?\s*/, "");
    } else if (kind === "paradigm") {
      text = text.replace(/^范式[SABCDE](?:[+−-])?/, "").replace(/^[，；:：]?\s*/, "");
    }
    return text.replace(/[。；]+$/, "");
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

    const parts = [base
      ? `范围${scope}、深度${depth}先形成基础影响量级${base}`
      : `范围${scope}、深度${depth}先确定基础影响量级`];
    const causalRule = ruleClause(foundation.causal_adjustment, "causal");
    const paradigmRule = ruleClause(foundation.paradigm_adjustment, "paradigm");
    parts.push(causalRule
      ? `个人因果${causal}：${causalRule}`
      : `个人因果${causal}再按归责规则修正基础量级`);
    parts.push(paradigmRule
      ? `政治范式${paradigm}：${paradigmRule}`
      : `政治范式${paradigm}只作有限补充，不替代主链`);
    parts.push(`规则细分档位为${internal}，公开显示为${published}`);
    return `${parts.join("；")}。`;
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
      next = next.replace(/\s{2,}/g, " ");
      if (next !== text) node.nodeValue = next;
    }
  }

  function ensureEvidenceGuide(root) {
    const core = root.querySelector(".impact-core-chains");
    const coreHint = core?.querySelector(":scope > .subline");
    if (coreHint) {
      coreHint.textContent = "这里是事实主链索引。四维会从不同问题重新引用这些事实；只想理解等级时，可直接展开四维，不必把同一段事实读两遍。";
    }
    if (root.querySelector(":scope > [data-impact-reading-guide]")) return;
    const note = document.createElement("p");
    note.className = "subline";
    note.dataset.impactReadingGuide = "done";
    note.textContent = "推荐顺序：先看“历史影响等级为什么这样定”，再按疑问展开四维；核心历史主链主要用于追溯事实。总档与四维使用不同刻度，不能直接求平均。";
    const heading = root.querySelector(":scope > h2, :scope > h3, :scope > summary");
    if (heading?.nextSibling) root.insertBefore(note, heading.nextSibling);
    else root.insertBefore(note, root.firstChild);
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
      ensureEvidenceGuide(root);
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
