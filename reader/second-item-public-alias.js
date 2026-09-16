"use strict";

(() => {
  const screenEl = document.getElementById("screen");
  if (!screenEl) return;

  const PUBLIC_GRADE = {G0:"E",G1:"D",G2:"C",G3:"B",G4:"A",G5:"S"};
  const POSITION_SUFFIX = {lower:"-",low:"-",middle:"",mid:"",upper:"+",high:"+"};
  const BAND_TEXT_GRADE = {"最低档":"E","较低档":"D","中低档":"C","中档":"B","较高档":"A","最高档":"S"};
  const STATE_GRADE = {1:"E",2:"D",3:"C",4:"B",5:"A",6:"S"};
  const HANDOFF_GRADE = {0:"E",1:"D",2:"C",3:"B",4:"A",5:"S"};
  const LOSS_TEXT = {
    0:"未见独立有效低谷",
    1:"有局部或短时损害",
    2:"出现明显低谷",
    3:"出现严重低谷",
  };
  const METHOD_MAX = {"A制度建设":100,"B1官僚治理":100,"B2反馈与约束":80};
  const FINANCE_MAX = {"C1民生":80,"C2经济财政":35,"C3社会安全":60};
  const HANDOFF_LABELS = {
    "D1继任行政连续性":"行政承接",
    "D3政权交接稳定":"终局继承",
  };
  let scheduled = false;

  function personRecord() {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#person\/([^/?#]+)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; } catch { return null; }
  }

  function netRecord() {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#net\/([^/?#]+)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; } catch { return null; }
  }

  function compareRecords() {
    if (typeof byId === "undefined" || !location.hash.startsWith("#compare/")) return [];
    return location.hash.slice(9).split("/").filter(Boolean).slice(0, 2).map(id => {
      try { return byId.get(decodeURIComponent(id)) || null; } catch { return null; }
    }).filter(Boolean);
  }

  function itemMap(record, key) {
    return new Map((record?.net?.component_details?.[key] || []).map(item => [item.label, item]));
  }

  function publicMethodGrade(item) {
    const text = String(item?.grade || "");
    const band = text.match(/\bG([0-5])\b/i);
    if (!band) return "";
    const base = PUBLIC_GRADE[`G${band[1]}`] || "";
    const position = text.match(/(?:\/|-)\s*(lower|middle|upper|low|mid|high)\b/i)?.[1]?.toLowerCase();
    return `${base}${position ? POSITION_SUFFIX[position] ?? "" : ""}`;
  }

  function stateGradeMeta(item) {
    const match = String(item?.grade || "").match(/\bC[123]-(\d)\s*\/\s*L([0-3])\b/i);
    if (!match) return null;
    const band = Number(match[1]);
    const loss = Number(match[2]);
    return {grade:STATE_GRADE[band] || "",lossText:LOSS_TEXT[loss] || ""};
  }

  function publicHandoffGrade(item) {
    const level = Number(item?.value);
    return Number.isInteger(level) ? HANDOFF_GRADE[level] || "" : "";
  }

  function boundaryExcerpt(item) {
    const text = String(item?.reader_boundary || "").trim();
    if (!text) return "";
    const first = text.match(/^.*?[。！？；;]/)?.[0] || text;
    return `边界：${first.trim()}`;
  }

  function ensureGradeStyles() {
    if (document.getElementById("second-item-public-grade-style")) return;
    const style = document.createElement("style");
    style.id = "second-item-public-grade-style";
    style.textContent = `
      .second-item-public-grade-ready > .second-item-scale-note{display:none!important}
      .second-item-public-grade-ready::after{content:attr(data-public-grade-note);display:block;margin-top:4px;font-size:11px;line-height:1.55;color:var(--green);font-weight:600}
    `;
    document.head.append(style);
  }

  function setPublicGrade(span, valueNode, grade, noteParts) {
    if (!span || !grade) return;
    if (valueNode && valueNode.textContent !== grade) valueNode.textContent = grade;
    const note = noteParts.filter(Boolean).join("｜");
    span.classList.add("second-item-public-grade-ready");
    if (span.dataset.publicGradeNote !== note) span.dataset.publicGradeNote = note;
  }

  function patchMethodGrades(root, record) {
    if (!root || !record?.net) return;
    const items = itemMap(record, "method");
    if (!items.size) return;

    for (const detail of root.querySelectorAll(".net-metric-detail[data-second-source-label]")) {
      const sourceLabel = detail.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const grade = publicMethodGrade(item);
      if (!item || !grade || !METHOD_MAX[sourceLabel]) continue;
      const summary = detail.querySelector(":scope > summary");
      setPublicGrade(
        summary?.querySelector(":scope > span"),
        summary?.querySelector(":scope > b"),
        grade,
        [`原始方向指数 ${Number(item.value).toFixed(1)} / ${METHOD_MAX[sourceLabel]}`,boundaryExcerpt(item)],
      );
    }

    for (const span of root.querySelectorAll(".component > span[data-second-source-label]")) {
      const sourceLabel = span.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const grade = publicMethodGrade(item);
      if (!item || !grade || !METHOD_MAX[sourceLabel]) continue;
      setPublicGrade(
        span,
        span.parentElement?.querySelector(":scope > b"),
        grade,
        [`原始方向指数 ${Number(item.value).toFixed(1)} / ${METHOD_MAX[sourceLabel]}`,boundaryExcerpt(item)],
      );
    }
  }

  function patchFinanceGrades(root, record) {
    if (!root || !record?.net) return;
    const items = itemMap(record, "finance");
    if (!items.size) return;

    for (const detail of root.querySelectorAll(".net-metric-detail[data-second-source-label]")) {
      const sourceLabel = detail.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const meta = stateGradeMeta(item);
      const max = FINANCE_MAX[sourceLabel];
      if (!item || !meta?.grade || !max) continue;
      const summary = detail.querySelector(":scope > summary");
      setPublicGrade(
        summary?.querySelector(":scope > span"),
        summary?.querySelector(":scope > b"),
        meta.grade,
        [`结算 ${Number(item.value).toFixed(1)} / ${max} 分`,meta.lossText,boundaryExcerpt(item)],
      );
    }

    for (const span of root.querySelectorAll(".component > span[data-second-source-label]")) {
      const sourceLabel = span.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const meta = stateGradeMeta(item);
      const max = FINANCE_MAX[sourceLabel];
      if (!item || !meta?.grade || !max) continue;
      setPublicGrade(
        span,
        span.parentElement?.querySelector(":scope > b"),
        meta.grade,
        [`结算 ${Number(item.value).toFixed(1)} / ${max} 分`,meta.lossText,boundaryExcerpt(item)],
      );
    }
  }

  function patchHandoffGrades(root, record) {
    if (!root || !record?.net) return;
    const items = itemMap(record, "handoff");
    if (!items.size) return;

    for (const detail of root.querySelectorAll(".net-metric-detail[data-second-source-label]")) {
      const sourceLabel = detail.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const grade = publicHandoffGrade(item);
      if (!item || !grade || !HANDOFF_LABELS[sourceLabel]) continue;
      const summary = detail.querySelector(":scope > summary");
      setPublicGrade(
        summary?.querySelector(":scope > span"),
        summary?.querySelector(":scope > b"),
        grade,
        [HANDOFF_LABELS[sourceLabel],boundaryExcerpt(item)],
      );
    }

    for (const span of root.querySelectorAll(".component > span[data-second-source-label]")) {
      const sourceLabel = span.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const grade = publicHandoffGrade(item);
      if (!item || !grade || !HANDOFF_LABELS[sourceLabel]) continue;
      setPublicGrade(
        span,
        span.parentElement?.querySelector(":scope > b"),
        grade,
        [HANDOFF_LABELS[sourceLabel],boundaryExcerpt(item)],
      );
    }
  }

  function patchGradeGroups(root, record) {
    patchMethodGrades(root, record);
    patchFinanceGrades(root, record);
    patchHandoffGrades(root, record);
  }

  function publicizeBandText(root) {
    if (!root) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      const parent = node.parentElement;
      if (!parent || parent.closest(".net-formal-basis-raw") || parent.closest(".net-audit-sources") || parent.closest(".sources") || parent.closest("a")) continue;
      const before = node.nodeValue || "";
      const after = before
        .replace(/(最低档|较低档|中低档|中档|较高档|最高档)(?:\s*[-/]\s*(lower|middle|upper|low|mid|high))?/gi, (_, label, pos) => {
          const base = BAND_TEXT_GRADE[label] || label;
          const suffix = pos ? POSITION_SUFFIX[String(pos).toLowerCase()] ?? "" : "";
          return `${base}${suffix}`;
        })
        .replace(/\bC[123]-([1-6])\b/g, (_, level) => `${STATE_GRADE[Number(level)] || level}档`)
        .replace(/\bD3-([0-5])\b/g, (_, level) => `${HANDOFF_GRADE[Number(level)] || level}档`)
        .replace(/\bH([0-5])\b/g, (_, level) => `${HANDOFF_GRADE[Number(level)] || level}档`)
        .replace(/\bL([0-3])\b/g, (_, level) => LOSS_TEXT[Number(level)] || "");
      if (after !== before) node.nodeValue = after;
    }
  }

  function patchPersonOutcomeLink() {
    const record = personRecord();
    const panel = document.getElementById("person-outcome");
    if (!record || !panel) return;
    const row = Array.from(panel.querySelectorAll(":scope > .component")).find(component => {
      const label = component.querySelector("span")?.textContent.trim() || "";
      return label.startsWith("治国成效") || label.startsWith("治国净收益");
    });
    if (!row || row.querySelector(":scope > .net-overview-jump")) return;

    const anchor = document.createElement("a");
    anchor.className = "net-overview-jump";
    anchor.href = `#net/${encodeURIComponent(record.ruler_id)}/second`;
    anchor.setAttribute("aria-label", `查看${record.ruler_name}的治国成效计分逻辑`);
    while (row.firstChild) anchor.append(row.firstChild);
    row.append(anchor);
  }

  function patchSecondItemShell() {
    if (!location.hash.match(/^#net\/[^/?#]+\/(?:all|second)(?:\/|$)/)) return;

    const secondNav = Array.from(document.querySelectorAll(".net-major-nav a")).find(a => /\/second(?:\/|$)/.test(a.getAttribute("href") || ""));
    if (secondNav) secondNav.textContent = "治国成效";

    for (const heading of document.querySelectorAll(".net-detail-head h1, .net-major-card h2")) {
      if (heading.textContent.includes("治国净收益")) {
        heading.textContent = heading.textContent.replace(/治国净收益/g, "治国成效");
      }
    }
  }

  function patchPublicGrades() {
    ensureGradeStyles();

    const net = netRecord();
    if (net && location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) {
      const root = document.getElementById("net-major-body");
      patchGradeGroups(root, net);
      publicizeBandText(root);
    }

    const person = personRecord();
    if (person) patchGradeGroups(screenEl, person);

    const records = compareRecords();
    if (records.length) {
      const rows = Array.from(screenEl.querySelectorAll(".comparison tbody tr"));
      const structureRow = rows.find(row => row.cells?.[0]?.textContent.trim() === "构成与依据");
      if (structureRow) records.forEach((record, index) => patchGradeGroups(structureRow.cells[index + 1], record));
    }
  }

  function patch() {
    patchPersonOutcomeLink();
    patchSecondItemShell();
    patchPublicGrades();
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      patch();
    });
  }

  new MutationObserver(schedule).observe(screenEl, {childList: true, subtree: true, characterData: true});
  window.addEventListener("hashchange", schedule);
  schedule();
})();
