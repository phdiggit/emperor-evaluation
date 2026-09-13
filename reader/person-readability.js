"use strict";

(() => {
  const normalized = value => {
    if (Array.isArray(value)) return value.map(normalized).filter(Boolean).join("\n");
    if (value && typeof value === "object") return JSON.stringify(value);
    return String(value ?? "").replace(/\s+/g, " ").trim();
  };

  const fragment = html => {
    const template = document.createElement("template");
    template.innerHTML = html;
    return template.content;
  };

  const directLabels = details => Array.from(details.children).filter(
    node => node.classList && node.classList.contains("label")
  );

  const c5PublicText = value => {
    if (Array.isArray(value)) return value.map(c5PublicText);
    if (typeof value !== "string") return value;
    return value
      .replace(/\bC5\b/g, "本轴")
      .replace(/COUNTEREVIDENCE_FOUND/g, "已找到明确反例")
      .replace(/高档反例审查/g, "反例检查")
      .replace(/父链/g, "证据链");
  };

  const impactPublicText = value => String(value ?? "")
    .replace(/取基础([SABCDE](?:[+−-])?)/g, "，基础影响量级为$1")
    .replace(/([SABCDE](?:[+−-])?)个人因果/g, "个人因果$1")
    .replace(/上调至内部([SABCDE](?:[+−-])?)/g, "使最终判断上调为$1")
    .replace(/内部([SABCDE](?:[+−-])?)/g, "综合判断$1")
    .replace(/公众([SABCDE](?:[+−-])?)/g, "最终等级$1")
    .replace(/不增加第二份深度/g, "不重复计入深度")
    .replace(/抬升基础/g, "提高基础影响量级");

  const historyPublicText = value => readerText(String(value ?? ""))
    .replace(/\bNEGATIVE\b/g, "负向")
    .replace(/\bPOSITIVE\b/g, "正向")
    .replace(/\bMIXED\b/g, "正负混合")
    .replace(/负向\s*\/\s*持续系统性情境/g, "持续系统性负向情境")
    .replace(/正向\s*\/\s*持续系统性情境/g, "持续系统性正向情境")
    .replace(/正负混合\s*\/\s*持续系统性情境/g, "持续系统性正负混合情境")
    .replace(/项目正式战役群/g, "正式战役材料")
    .replace(/项目重审明确把/g, "现有裁决将")
    .replace(/项目(?:M1|M2|M4|M5|C1|C2|C3|C4|C5)明确指出/g, "相关人物画像材料指出")
    .replace(/项目(?:M1|M2|M4|M5|C1|C2|C3|C4|C5)因此把这一链裁为/g, "相关人物画像材料将这一链认定为")
    .replace(/项目(?:M1|M2|M4|M5|C1|C2|C3|C4|C5)/g, "相关人物画像材料");

  function evidenceSection(title) {
    return Array.from(document.querySelectorAll("#person-evidence > section.panel")).find(section => {
      const heading = section.querySelector(":scope > h2, :scope > h3");
      return heading?.textContent.trim() === title;
    }) || null;
  }

  function normalizeEvidenceCardHeadings() {
    for (const title of ["净收益构成", "人物画像依据", "历史影响依据"]) {
      const section = evidenceSection(title);
      if (!section || section.dataset.publicHeading === "done") continue;
      const heading = section.querySelector(":scope > h2, :scope > h3");
      if (!heading) continue;
      if (heading.tagName === "H2") {
        heading.classList.add("evidence-card-title");
      } else {
        const replacement = document.createElement("h2");
        replacement.className = "evidence-card-title";
        replacement.textContent = title;
        heading.replaceWith(replacement);
      }
      section.dataset.publicHeading = "done";
    }
  }

  function addNetSourceLinks(record) {
    const section = evidenceSection("净收益构成");
    const groups = Object.entries(record.net?.component_details || {});
    if (!section || !groups.length || section.dataset.netSources === "done") return;

    const detailBoxes = Array.from(section.querySelectorAll(":scope > details:not(.net-ledger)"));
    for (const [groupIndex, [, items]] of groups.entries()) {
      const box = detailBoxes[groupIndex];
      if (!box || !Array.isArray(items)) continue;
      const rows = Array.from(box.querySelectorAll(":scope > .component"));
      rows.forEach((row, itemIndex) => {
        const item = items[itemIndex];
        if (!item || (!item.source && !item.applied_source)) return;
        const links = document.createElement("span");
        links.className = "net-score-links";
        if (item.source) links.append(fragment(link(item.source, "评分依据 ↗", record)));
        if (item.applied_source && item.applied_source !== item.source) {
          links.append(document.createTextNode(" "));
          links.append(fragment(link(item.applied_source, "采用值来源 ↗", record)));
        }
        row.append(links);
      });
    }
    section.dataset.netSources = "done";
  }

  function replaceLead(details, labelText, html) {
    const label = directLabels(details)[0];
    if (!label || !html) return;

    label.textContent = labelText;
    let node = label.nextSibling;
    while (node) {
      const next = node.nextSibling;
      if (
        node.nodeType === Node.ELEMENT_NODE &&
        (node.classList.contains("label") || node.tagName === "DETAILS")
      ) break;
      node.remove();
      node = next;
    }
    label.after(fragment(html));
  }

  function publicEvidencePoints(points) {
    if (!Array.isArray(points) || !points.length) return "";
    return `<details class="public-evidence-points"><summary>查看代表性证据</summary>${points.map(point => {
      const publicTitle = point && point.title ? readerText(c5PublicText(point.title)) : "";
      const title = publicTitle ? `<div class="label">${esc(publicTitle)}</div>` : "";
      const details = point && point.details ? c5PublicText(point.details) : "";
      return `${title}${axisProse(details)}`;
    }).join("")}</details>`;
  }

  function c4Lead(axis) {
    const contexts = Array.isArray(axis.representative_contexts) ? axis.representative_contexts : [];
    if (!contexts.length) return axisProse(axis.grade_basis || axis.typical_pattern);
    return contexts.map(context => {
      const rawTitle = String(context.title || "").trim();
      const title = rawTitle && !/^(?:主要)?父(?:情境|链)/.test(rawTitle)
        ? `<div class="public-context-title">${esc(rawTitle)}</div>`
        : "";
      const body = context.mechanism || context.cycle_basis || context.basis || "";
      return `<div class="context-story public-context">${title}${axisProse(body)}</div>`;
    }).join("");
  }

  function uniqueValue(value, seen) {
    if (Array.isArray(value)) {
      const kept = value.filter(item => {
        const key = normalized(item);
        if (!key || seen.has(key)) return false;
        seen.add(key);
        return true;
      });
      return kept;
    }
    const key = normalized(value);
    if (!key || seen.has(key)) return "";
    seen.add(key);
    return value;
  }

  function rebuildAdjudication(details, axis, leadValues) {
    const box = Array.from(details.children).find(
      node => node.tagName === "DETAILS" && node.classList.contains("adjudication")
    );
    if (!box) return;

    const seen = new Set((leadValues || []).map(normalized).filter(Boolean));
    const fields = [
      ["定档依据", axis.grade_basis],
      ["档内定位", axis.position_basis],
      ["限制与证据边界", axis.limitations],
      ["证据评估", axis.evidence_assessment_basis],
    ];
    const sections = [];
    for (const [label, value] of fields) {
      const unique = uniqueValue(value, seen);
      if (!normalized(unique)) continue;
      sections.push(`<div class="label">${label}</div>${axisProse(unique)}`);
    }

    const closure = axis.no_grade_closure;
    if (closure) {
      for (const [label, value] of [
        ["复查范围", closure.review_scope],
        ["证据缺口", closure.evidence_gap],
        ["重开条件", closure.reopen_condition],
      ]) {
        const unique = uniqueValue(value, seen);
        if (normalized(unique)) sections.push(`<div class="label">${label}</div>${axisProse(unique)}`);
      }
    }

    if (!sections.length) {
      box.remove();
      return;
    }
    box.innerHTML = `<summary>裁决详情</summary>${sections.join("")}`;
  }

  function enhanceAxis(details, axisCode, axis) {
    if (!details || !axis || details.dataset.personReadable === "done") return;

    let leadValues = [axis.typical_pattern];
    if (axisCode === "C2") {
      const lead = axis.grade_basis || axis.typical_pattern;
      replaceLead(details, "最能说明这个判断的表现", axisProse(lead));
      leadValues = [lead];
    } else if (axisCode === "C4") {
      replaceLead(details, "最能说明这个判断的制度设计", c4Lead(axis));
      leadValues = axis.representative_contexts?.length
        ? axis.representative_contexts.map(context => context.mechanism || context.cycle_basis || context.basis)
        : [axis.grade_basis || axis.typical_pattern];
    } else if (axisCode === "C5") {
      const type = axis.person_type
        ? `<p class="prose public-person-type"><strong>${esc(axis.person_type)}</strong></p>`
        : axisProse(axis.typical_pattern);
      replaceLead(
        details,
        "权力运用风格概括",
        `${type}${publicEvidencePoints(axis.public_evidence_points)}`
      );
      leadValues = [axis.person_type || axis.typical_pattern];
    }

    if (typeof axis.counterpattern === "string" && axis.counterpattern.trim()) {
      for (const label of directLabels(details)) {
        if (label.textContent.trim() === "反例与限制") {
          label.textContent = "补充证据与边界";
          break;
        }
      }
    }

    rebuildAdjudication(details, axis, leadValues);
    details.dataset.personReadable = "done";
  }

  function enhanceC5Overview(record) {
    const axis = record.axes?.C5;
    if (!axis) return;
    const row = document.querySelector("#person-capability .style-axis .axis-row");
    if (!row || row.querySelector(".c5-scale-note")) return;
    if (axis.person_type) {
      const type = document.createElement("div");
      type.className = "c5-type subline";
      type.textContent = axis.person_type;
      row.append(type);
    }
    const note = document.createElement("div");
    note.className = "c5-scale-note subline";
    note.textContent = "C5越接近S，表示越能在压力和个人利益面前约束自身权力；越接近E，表示强制、报复或特权越容易越过合理边界。它描述权力风格，不计入八项能力雷达。";
    row.append(note);
  }

  function rewriteHistoryChains(impact) {
    for (const chain of impact.macro_chains || []) {
      const box = document.getElementById(`chain-${chain.chain_id}`);
      const summary = box?.querySelector(":scope > summary");
      if (!box || !summary || box.dataset.publicNarrative === "done") continue;
      let node = summary.nextSibling;
      while (node) {
        const next = node.nextSibling;
        node.remove();
        node = next;
      }
      summary.after(fragment(prose(historyPublicText(chain.narrative))));
      box.dataset.publicNarrative = "done";
    }
  }

  function enhanceImpact(record) {
    const impact = record.impact || {};
    const joint = impact.foundation?.joint_footprint_basis;

    const panel = document.querySelector("#person-impact");
    if (joint && panel && !panel.querySelector(".impact-summary")) {
      const dimensions = panel.querySelector(".dimensions");
      const summary = document.createElement("div");
      summary.className = "impact-summary";
      summary.innerHTML = `<div class="label">为什么是 ${esc(impact.public_grade)}？</div>${prose(impactPublicText(joint))}`;
      (dimensions || panel).after(summary);
    }

    rewriteHistoryChains(impact);
    const evidence = document.querySelector("#history-evidence");
    if (!evidence || evidence.dataset.personReadable === "done") return;
    const heading = evidence.querySelector(":scope > h2, :scope > h3.section-title");
    const firstDetails = heading?.nextElementSibling;
    if (firstDetails?.tagName === "DETAILS") {
      const summary = firstDetails.querySelector(":scope > summary");
      if (summary) summary.textContent = "完整定档依据";
    }
    evidence.dataset.personReadable = "done";
  }

  function foldNetLedger() {
    const section = evidenceSection("净收益构成");
    if (!section || section.dataset.ledgerFolded === "done") return;

    const items = Array.from(section.children).filter(node => node.tagName === "DETAILS");
    if (!items.length) return;
    const note = document.createElement("p");
    note.className = "subline net-ledger-note";
    note.textContent = "展开后可核对每项分值、折算过程及对应的正式评分依据。";
    const wrapper = document.createElement("details");
    wrapper.className = "net-ledger";
    const toggle = document.createElement("summary");
    toggle.textContent = "完整计分明细与依据";
    wrapper.append(toggle, ...items);
    section.append(note, wrapper);
    section.dataset.ledgerFolded = "done";
  }

  function currentRecord() {
    const match = location.hash.match(/^#person\/([^/?#]+)/);
    if (!match) return null;
    return byId.get(decodeURIComponent(match[1])) || null;
  }

  function enhance() {
    const record = currentRecord();
    if (!record) return;
    for (const code of DATA.axis_order) {
      enhanceAxis(document.getElementById(`reason-${code}`), code, record.axes?.[code]);
    }
    enhanceC5Overview(record);
    enhanceImpact(record);
    normalizeEvidenceCardHeadings();
    addNetSourceLinks(record);
    foldNetLedger();
  }

  new MutationObserver(enhance).observe(screen, {childList: true, subtree: true});
  window.addEventListener("hashchange", enhance);
  enhance();
})();
