"use strict";

(() => {
  function evidenceSection(title) {
    return Array.from(document.querySelectorAll("#person-evidence > section.panel")).find(section => {
      const heading = section.querySelector(":scope > h2, :scope > h3");
      return heading?.textContent.trim() === title;
    }) || null;
  }

  function normalizeEvidenceCardHeadings() {
    for (const title of ["统治绩效构成", "人物画像详情", "人物画像依据", "历史影响详情", "历史影响依据"]) {
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
    note.textContent = "S端表示更能约束自身权力，E端表示更易出现报复、强制滥用或特权；不计入能力雷达。";
    row.append(note);
  }

  function enhanceImpact(record) {
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

  function openHistoricalImpactTarget(event) {
    const link = event.target.closest('[data-section^="history-dimension-"], [data-section="history-judgment-boundary"]');
    if (!link) return;
    const target = document.getElementById(link.dataset.section);
    if (target?.tagName === "DETAILS") target.open = true;
  }

  function ensureMilitaryArchiveNav() {
    const nav = document.querySelector("header nav");
    if (!nav || nav.querySelector("[data-military-archive-nav]")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.militaryArchiveNav = "true";
    button.textContent = "军事档案";
    button.addEventListener("click", () => { location.href = "military.html"; });
    nav.append(button);
  }

  function currentRecord() {
    const match = location.hash.match(/^#person\/([^/?#]+)/);
    if (!match) return null;
    return byId.get(decodeURIComponent(match[1])) || null;
  }

  function enhance() {
    ensureMilitaryArchiveNav();
    const record = currentRecord();
    if (!record) return;
    enhanceC5Overview(record);
    enhanceImpact(record);
    normalizeEvidenceCardHeadings();
  }

  screen.addEventListener("click", openHistoricalImpactTarget, true);
  new MutationObserver(enhance).observe(screen, {childList: true, subtree: true});
  window.addEventListener("hashchange", enhance);
  enhance();
})();
