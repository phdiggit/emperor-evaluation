"use strict";

(() => {
  const screen = document.getElementById("screen");
  if (!screen) return;

  const PUBLIC_LABELS = {
    "A制度建设": "制度建设",
    "B1官僚治理": "官僚治理",
    "B2反馈与约束": "反馈与约束",
    "C1民生": "民生",
    "C2经济财政": "经济财政",
    "C3社会安全": "社会安全",
    "C4恢复与成本": "恢复与额外代价",
    "D1继任行政连续性": "行政连续性",
    "D3政权交接稳定": "交接稳定",
  };

  let scheduled = false;

  function publicLabel(sourceLabel) {
    return PUBLIC_LABELS[String(sourceLabel || "")] || "";
  }

  function patchLabelNode(node, label) {
    if (!node || !label) return;
    node.classList.add("second-item-public-title");
    node.dataset.publicTitle = label;
  }

  function ensureStyles() {
    if (document.getElementById("second-item-public-title-style")) return;
    const style = document.createElement("style");
    style.id = "second-item-public-title-style";
    style.textContent = `
      .second-item-public-title{font-size:0!important}
      .second-item-public-title::before{content:attr(data-public-title);font-size:13px;line-height:inherit;color:inherit;font-weight:inherit}
      .net-metric-detail>summary .second-item-public-title::before{font-size:14px}
    `;
    document.head.append(style);
  }

  function patch() {
    ensureStyles();

    for (const span of screen.querySelectorAll("span[data-second-source-label]")) {
      const label = publicLabel(span.dataset.secondSourceLabel);
      if (label) patchLabelNode(span, label);
    }

    for (const detail of screen.querySelectorAll(".net-metric-detail[data-second-source-label]")) {
      const label = publicLabel(detail.dataset.secondSourceLabel);
      if (!label) continue;
      const span = detail.querySelector(":scope > summary > span");
      patchLabelNode(span, label);
    }
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      patch();
    });
  }

  new MutationObserver(schedule).observe(screen, {childList:true, subtree:true, characterData:true});
  window.addEventListener("hashchange", schedule);
  schedule();
})();
