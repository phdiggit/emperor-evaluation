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

  function simplifyDifferenceToggle() {
    const toggle = document.querySelector("#screen .difference-toggle:not([data-readable-toggle])");
    if (!toggle) return;
    for (const node of toggle.childNodes) {
      if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
        node.textContent = "只看不同项";
        break;
      }
    }
    toggle.dataset.readableToggle = "done";
  }

  function axisRecordForEvidence(details) {
    const id = details.id || "";
    let match = id.match(/^reason-([A-Z]\d)$/);
    if (match) {
      const person = location.hash.match(/^#person\/([^/?#]+)/);
      if (!person) return null;
      try {
        return byId.get(decodeURIComponent(person[1]))?.axes?.[match[1]] || null;
      } catch {
        return null;
      }
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
      const box = Array.from(details.children).find(
        node => node.tagName === "DETAILS" && node.classList.contains("metadata") && !node.classList.contains("adjudication")
      );
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

  function enhance() {
    foldHomeStatus();
    compactComparisonEvidence();
    simplifyDifferenceToggle();
    publicAxisMetadata();
  }

  new MutationObserver(enhance).observe(screen, {childList: true, subtree: true});
  enhance();
})();