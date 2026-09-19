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

  function currentPersonId() {
    const match = location.hash.match(/^#person\/([^/?#]+)/);
    if (!match) return "";
    try { return decodeURIComponent(match[1]); } catch { return ""; }
  }

  function patchPersonNetEvidence() {
    const rulerId = currentPersonId();
    if (!rulerId) return;
    const evidence = document.getElementById("person-evidence");
    if (!evidence) return;
    const panel = Array.from(evidence.querySelectorAll(":scope > section.panel")).find(section => {
      const heading = section.querySelector(":scope > h2, :scope > h3");
      return ["统治绩效构成", "统治绩效详情"].includes(heading?.textContent.trim());
    });
    if (!panel || panel.dataset.canonicalNetEntry === "done") return;

    const encoded = encodeURIComponent(rulerId);
    panel.dataset.canonicalNetEntry = "done";
    panel.dataset.netReadable = "done";
    panel.dataset.ledgerFolded = "done";
    panel.innerHTML = `
      <h2>统治绩效详情</h2>
      <p class="reading-intro">查看完整构成，或直接进入治国成效。</p>
      <div class="person-net-canonical-grid">
        <a class="person-net-canonical-card" href="#net/${encoded}/all">
          <strong>完整统治绩效构成</strong>
          <small>治国、军事、统一与文明整合</small>
          <span>查看详情 →</span>
        </a>
        <a class="person-net-canonical-card" href="#net/${encoded}/second">
          <strong>治国成效</strong>
          <small>制度与行政、民生与社会、政权交接</small>
          <span>查看详情 →</span>
        </a>
      </div>
    `;
  }

  function ensureStyles() {
    if (document.getElementById("second-item-public-title-style")) return;
    const style = document.createElement("style");
    style.id = "second-item-public-title-style";
    style.textContent = `
      .second-item-public-title{font-size:13px}
      .net-metric-detail>summary .second-item-public-title{font-size:14px}
      .person-net-canonical-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:14px}
      .person-net-canonical-card{display:flex;min-width:0;min-height:118px;flex-direction:column;gap:5px;padding:16px 18px;border:1px solid var(--line);border-radius:6px;background:#fff;text-decoration:none!important}
      .person-net-canonical-card:hover{border-color:var(--green);background:#f6f7f1}
      .person-net-canonical-card strong{font-size:16px;color:var(--ink)}
      .person-net-canonical-card small{display:block;line-height:1.65;color:var(--muted)}
      .person-net-canonical-card span{margin-top:auto;font-size:13px;color:var(--green);font-weight:600}
      @media(max-width:700px){.person-net-canonical-grid{grid-template-columns:1fr}.person-net-canonical-card{min-height:0}}
    `;
    document.head.append(style);
  }

  function patch() {
    ensureStyles();
    patchPersonNetEvidence();

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
