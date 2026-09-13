"use strict";

(() => {
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
    for (const summary of document.querySelectorAll(
      "#screen .comparison .axis-evidence > summary:not([data-compact-compare])"
    )) {
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

  function enhance() {
    foldHomeStatus();
    compactComparisonEvidence();
  }

  new MutationObserver(enhance).observe(screen, {childList: true, subtree: true});
  enhance();
})();
