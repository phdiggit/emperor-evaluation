"use strict";

(() => {
  const screenEl = document.getElementById("screen");
  if (!screenEl) return;
  let scheduled = false;

  function personRecord() {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#person\/([^/?#]+)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; } catch { return null; }
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

  function patch() {
    patchPersonOutcomeLink();
    patchSecondItemShell();
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
