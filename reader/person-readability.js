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
      const title = point && point.title ? `<div class="label">${esc(point.title)}</div>` : "";
      return `${title}${axisProse(point && point.details ? point.details : "")}`;
    }).join("")}</details>`;
  }

  function c4Lead(axis) {
    const contexts = Array.isArray(axis.representative_contexts) ? axis.representative_contexts : [];
    if (!contexts.length) return axisProse(axis.grade_basis || axis.typical_pattern);
    return contexts.map(context => {
      const title = context.title ? `<div class="public-context-title">${esc(context.title)}</div>` : "";
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
    if (!axis?.person_type) return;
    const row = document.querySelector("#person-capability .style-axis .axis-row");
    if (!row || row.querySelector(".c5-type")) return;
    const type = document.createElement("div");
    type.className = "c5-type subline";
    type.textContent = axis.person_type;
    row.append(type);
  }

  function enhanceImpact(record) {
    const impact = record.impact || {};
    const joint = impact.foundation?.joint_footprint_basis;
    if (!joint) return;

    const panel = document.querySelector("#person-impact");
    if (panel && !panel.querySelector(".impact-summary")) {
      const dimensions = panel.querySelector(".dimensions");
      const summary = document.createElement("div");
      summary.className = "impact-summary";
      summary.innerHTML = `<div class="label">为什么是 ${esc(impact.public_grade)}？</div>${prose(joint)}`;
      (dimensions || panel).after(summary);
    }

    const evidence = document.querySelector("#history-evidence");
    if (!evidence || evidence.dataset.personReadable === "done") return;
    const heading = evidence.querySelector(".section-title");
    const firstDetails = heading?.nextElementSibling;
    if (firstDetails?.tagName === "DETAILS") {
      const summary = firstDetails.querySelector(":scope > summary");
      if (summary) summary.textContent = "完整定档依据";
    }
    evidence.dataset.personReadable = "done";
  }

  function foldNetLedger() {
    const evidence = document.querySelector("#person-evidence");
    if (!evidence) return;
    const section = Array.from(evidence.children).find(node =>
      node.matches?.("section.panel") && node.querySelector(":scope > h3")?.textContent.trim() === "净收益构成"
    );
    if (!section || section.dataset.ledgerFolded === "done") return;

    const items = Array.from(section.children).filter(node => node.tagName === "DETAILS");
    if (!items.length) return;
    const note = document.createElement("p");
    note.className = "subline net-ledger-note";
    note.textContent = "需要核对原始指标、折算与小计时，再展开完整计分明细。";
    const wrapper = document.createElement("details");
    wrapper.className = "net-ledger";
    const toggle = document.createElement("summary");
    toggle.textContent = "完整计分明细";
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
    foldNetLedger();
  }

  new MutationObserver(enhance).observe(screen, {childList: true, subtree: true});
  window.addEventListener("hashchange", enhance);
  enhance();
})();
