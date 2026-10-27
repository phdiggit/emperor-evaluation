"use strict";

(() => {
  const screen = document.getElementById("screen");
  if (!screen) return;

  const PUBLIC_LABELS = globalThis.SecondItemDisplay.labels;

  function publicLabel(sourceLabel) {
    return PUBLIC_LABELS[String(sourceLabel || "")] || "";
  }

  function patchLabelNode(node, label) {
    if (!node || !label) return;
    node.classList.add("second-item-public-title");
    if (node.dataset.publicTitle !== label) node.dataset.publicTitle = label;
    const strong = node.querySelector(":scope > strong");
    if (strong) {
      if (strong.dataset.publicTitle !== label) strong.dataset.publicTitle = label;
      if (strong.textContent !== label) strong.textContent = label;
      return;
    }
    // Compact rows keep notes, links and other child elements intact.
    const texts = Array.from(node.childNodes).filter(child => child.nodeType === Node.TEXT_NODE);
    if (!texts.length) node.insertBefore(document.createTextNode(label + " "), node.firstChild);
    else {
      if (texts[0].nodeValue !== label + " ") texts[0].nodeValue = label + " ";
      for (const text of texts.slice(1)) if (text.nodeValue) text.nodeValue = "";
    }
  }

  function ensureStyles() {
    if (document.getElementById("second-item-public-title-style")) return;
    const style = document.createElement("style");
    style.id = "second-item-public-title-style";
    style.textContent = `
      .second-item-public-title{font-size:13px}
      .net-metric-detail>summary .second-item-public-title{font-size:14px}
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

    for (const label of screen.querySelectorAll(".compare-evidence-label")) {
      if (label.textContent.trim() === "展开依据") label.textContent = "详情";
    }
  }

  globalThis.SecondItemPublicLabels = Object.freeze({patch});
})();
