"use strict";

(() => {
  const baseReaderText = readerText;
  const publicReaderText = value => baseReaderText(value)
    .replace(/\bMIXED_NEGATIVE\b/g, "正负混合、以负向为主")
    .replace(/\bMIXED_POSITIVE\b/g, "正负混合、以正向为主")
    .replace(/\bNEGATIVE\b/g, "负向")
    .replace(/\bPOSITIVE\b/g, "正向")
    .replace(/\bMIXED\b/g, "正负混合")
    .replace(/\bCOUNTEREVIDENCE_FOUND\b/g, "已找到明确反例")
    .replace(/\bBACKGROUND_VALIDATION\b/g, "背景核验")
    .replace(/\bAXIS_OUT_WITH_REASON\b/g, "不计入本轴（有明确理由）")
    .replace(/\bFORMAL_CURRENT\b/g, "当前正式记录")
    .replace(/\bSCORING_PARENT\b/g, "主要计分证据")
    .replace(/\bREFUSAL_OR_RECURRENCE\b/g, "拒绝更新或同类复发情境")
    .replace(/\bTRUTH_ACQUISITION\b/g, "求真取证情境");

  readerText = publicReaderText;

  function foldHomeStatus() {
    const note = document.querySelector("#screen .footer-note:not([data-readability-status])");
    if (!note) return;
    const text = note.textContent.trim();
    const firstStop = text.indexOf("。");
    note.dataset.readabilityStatus = "done";
    if (firstStop < 0 || firstStop === text.length - 1) return;
    const headline = text.slice(0, firstStop + 1).trim();
    const detailText = text.slice(firstStop + 1).trim();
    if (!detailText) return;
    note.textContent = "";
    const summary = document.createElement("span");
    summary.className = "home-count-summary";
    summary.textContent = headline;
    const details = document.createElement("details");
    details.className = "data-status";
    const toggle = document.createElement("summary");
    toggle.textContent = "数据状态";
    const body = document.createElement("p");
    body.textContent = detailText;
    details.append(toggle, body);
    note.append(summary, details);
  }

  function compactComparisonEvidence() {
    for (const summary of document.querySelectorAll("#screen .comparison .axis-evidence > summary:not([data-compact-compare])")) {
      const badge = summary.querySelector(".badge");
      if (!badge) continue;
      const grade = badge.textContent.trim();
      summary.textContent = "";
      const compactBadge = document.createElement("span");
      compactBadge.className = "badge";
      compactBadge.textContent = grade;
      const label = document.createElement("span");
      label.className = "compare-evidence-label";
      label.textContent = "展开依据";
      summary.append(compactBadge, label);
      summary.dataset.compactCompare = "done";
    }
  }

  function publicGradeHelp() {
    const profile = document.querySelector("#person-capability .grade-help:not([data-public-help])");
    if (profile) {
      const paragraphs = profile.querySelectorAll(":scope > p");
      if (paragraphs[0]) paragraphs[0].textContent = "各轴从E−到S+分18级；−、无符号、+分别表示同一字母等级中的较低、中间和较高位置。人物画像与历史影响使用不同尺度，字母相同也不能直接比较。";
      if (paragraphs[1]) paragraphs[1].textContent = "八个能力轴分别依据本轴行为证据；C5只评价权力运用风格与克制，不当作能力高低，也不计入能力雷达。不适用、待补证、待重裁会单独标明，不按低分处理。";
      profile.dataset.publicHelp = "done";
    }
    const impact = document.querySelector("#person-impact .grade-help:not([data-public-help])");
    if (impact) {
      const paragraph = impact.querySelector(":scope > p");
      if (paragraph) paragraph.textContent = "这是历史改变的量级，不是能力或功绩等级。最终等级与四个维度分别判断，不做简单平均。";
      impact.dataset.publicHelp = "done";
    }
  }

  function axisRecordForEvidence(details) {
    const id = details.id || "";
    let match = id.match(/^reason-([A-Z]\d)$/);
    if (match) {
      const person = location.hash.match(/^#person\/([^/?#]+)/);
      if (!person) return null;
      try { return byId.get(decodeURIComponent(person[1]))?.axes?.[match[1]] || null; } catch { return null; }
    }
    match = id.match(/^reason-([A-Z]\d)-compare-(\d+)$/);
    if (match) {
      const rulerId = state.compare[Number(match[2])];
      return rulerId ? byId.get(rulerId)?.axes?.[match[1]] || null : null;
    }
    return null;
  }

  function publicAxisMetadata() {
    for (const details of document.querySelectorAll("#screen .axis-evidence:not([data-public-metadata])")) {
      const axis = axisRecordForEvidence(details);
      if (!axis) continue;
      const box = Array.from(details.children).find(node => node.tagName === "DETAILS" && node.classList.contains("metadata") && !node.classList.contains("adjudication"));
      if (!box) continue;
      const summary = box.querySelector(":scope > summary");
      if (summary) summary.textContent = "专业信息与正式记录";
      const line = box.querySelector(":scope > .subline");
      if (line) {
        let status;
        if (ungraded(axis)) status = "当前状态：无档结案";
        else if (pending(axis)) status = `当前状态：${grade(axis)}`;
        else if (axis.applicability_status === "NOT_APPLICABLE" || axis.output_mode === "NOT_APPLICABLE") status = "当前状态：不适用";
        else status = `公开等级：${grade(axis)}`;
        line.textContent = `展示模式：${mode(axis.output_mode)} · 判断把握：${conf(axis.confidence)} · ${status}`;
      }
      details.dataset.publicMetadata = "done";
    }
  }

  function translateResidualAxisCodes() {
    for (const details of document.querySelectorAll("#screen .axis-evidence:not([data-public-terms])")) {
      const walker = document.createTreeWalker(details, NodeFilter.SHOW_TEXT);
      const nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      for (const node of nodes) {
        const parent = node.parentElement;
        if (!parent || parent.closest("a, code, .sources, .unavailable-source")) continue;
        const translated = publicReaderText(node.nodeValue);
        if (translated !== node.nodeValue) node.nodeValue = translated;
      }
      details.dataset.publicTerms = "done";
    }
  }

  function enhance() {
    foldHomeStatus();
    compactComparisonEvidence();
    publicGradeHelp();
    publicAxisMetadata();
    translateResidualAxisCodes();
  }

  new MutationObserver(enhance).observe(screen, {childList: true, subtree: true});
  enhance();
})();
