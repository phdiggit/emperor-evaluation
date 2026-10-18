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

    const record = typeof byId !== "undefined" ? byId.get(rulerId) : null;
    if (!record?.detail_loaded) return;
    const first = record.net?.component_details?.first || [];
    const a = first.find(item => item.label === "A统一贡献")?.reader_public_outcome;
    const b1 = first.find(item => item.label === "B1创业难度与效率")?.reader_public_b1;
    const b2 = first.find(item => item.label === "B2组织与整合")?.reader_public_b2;
    const c = first.find(item => item.label === "C军事统帅与战争解题")?.reader_public_commander;
    const bureaucracy = (record.net?.component_details?.method || []).find(item => item.label === "B1官僚治理");
    const feedback = (record.net?.component_details?.method || []).find(item => item.label === "B2反馈与约束");
    const civilian = (record.net?.component_details?.finance || []).filter(item => item.reader_public_c);
    const strategicA = (record.net?.component_details?.strategic || []).filter(item => item.reader_public_a);
    const strategicB = (record.net?.component_details?.strategic || []).filter(item => item.reader_public_b);
    const militaryC = (record.net?.component_details?.military || []).find(item => item.reader_public_third_c);

    const encoded = encodeURIComponent(rulerId);
    panel.dataset.canonicalNetEntry = "done";
    panel.dataset.netReadable = "done";
    panel.dataset.ledgerFolded = "done";
    panel.innerHTML = `
      <h2>统治绩效详情</h2>
      <p class="reading-intro">按具体经历、本人责任和实际结果展开阅读，各项计算与来源可继续查看。<a href="second-item-b2.html">阅读全池反馈纠错与权力约束 ↗</a> · <a href="second-item-c.html">阅读全池民生与社会 ↗</a></p>
      <div class="person-net-canonical-grid">
        ${feedback && globalThis.SecondItemB2Reading ? `<article class="person-net-canonical-card b2-overview" data-b2-public-overview><strong>反馈与约束：具体过程与定档理由</strong>${globalThis.SecondItemB2Reading.html(feedback)}<a href="#net/${encoded}/second/method">查看完整治国成效与计算 →</a></article>` : ""}
        ${bureaucracy?.reader_story && bureaucracy?.reader_responsibility && bureaucracy?.reader_summary ? `<article class="person-net-canonical-card b1-overview" data-b1-public-overview><strong>官僚治理：具体经历与定档理由</strong><p>${esc(bureaucracy.reader_story)}</p><strong>本人承担什么责任</strong><p>${esc(bureaucracy.reader_responsibility)}</p><strong>为什么是这个等级</strong><p>${esc(bureaucracy.reader_summary)}</p><a href="#net/${encoded}/second/method">查看逐条依据与计算 →</a></article>` : ""}
        ${globalThis.SecondItemCReading ? civilian.map(item => `<article class="person-net-canonical-card c-overview" data-c-public-overview><strong>${esc(item.public_component_label)} · ${esc(item.value)}分</strong>${globalThis.SecondItemCReading.html(item)}<a href="#net/${encoded}/second/finance">查看完整治国成效构成 →</a></article>`).join("") : ""}
        ${globalThis.ThirdItemAReading ? strategicA.map(item => `<article class="person-net-canonical-card third-a-overview" data-third-a-public-overview><strong>战略安全 · ${esc(item.public_component_label)} · ${esc(item.value)} / 60 分</strong>${globalThis.ThirdItemAReading.html(item, record)}<a href="#net/${encoded}/third/strategic">查看完整军事与边疆构成 →</a></article>`).join("") : ""}
        ${globalThis.ThirdItemBReading ? strategicB.map(item => `<article class="person-net-canonical-card third-b-overview" data-third-b-public-overview><p class="meta">领土与控制成果</p>${globalThis.ThirdItemBReading.heading(item)}${globalThis.ThirdItemBReading.html(item, record)}<a href="#net/${encoded}/third/strategic">查看完整军事与边疆构成 →</a></article>`).join("") : ""}
        ${militaryC ? `<article class="person-net-canonical-card third-c-overview" data-third-c-public-overview>${globalThis.ThirdItemCReading.heading(militaryC)}${globalThis.ThirdItemCReading.html(militaryC, record)}<a href="#net/${encoded}/third/military">查看完整军事与边疆构成 →</a></article>` : ""}
        ${record.net?.first_item_status === "APPLICABLE" && a?.public_question ? `<a class="person-net-canonical-card first-a-entry" href="#net/${encoded}/first/a"><strong>${esc(a.public_question)}</strong><small>${esc(a.public_story)}</small><span>读统一成果 →</span></a>` : ""}
        ${record.net?.first_item_status === "APPLICABLE" && b1?.public_question ? `<a class="person-net-canonical-card first-b1-entry" href="#net/${encoded}/first/b1"><strong>${esc(b1.public_question)}</strong><small>${esc(b1.public_story)}</small><span>读条件与效率 →</span></a>` : ""}
        ${record.net?.first_item_status === "APPLICABLE" && b2?.public_question ? `<a class="person-net-canonical-card first-b2-entry" href="#net/${encoded}/first/b2"><strong>${esc(b2.public_question)}</strong><small>${esc(b2.public_story)}</small><span>读组织与协作 →</span></a>` : ""}
        ${record.net?.first_item_status === "APPLICABLE" && c?.public_question ? `<a class="person-net-canonical-card first-c-entry" href="#net/${encoded}/first/c"><strong>${esc(c.public_question)}</strong><small>${esc(c.public_story)}</small><span>读本人战争解题 →</span></a>` : ""}
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
      .person-net-canonical-card.b1-overview{grid-column:1/-1}
      .person-net-canonical-card.c-overview{grid-column:1/-1}
      .person-net-canonical-card.third-a-overview{grid-column:1/-1}
      .person-net-canonical-card.third-b-overview{grid-column:1/-1}
      .person-net-canonical-card.third-c-overview{grid-column:1/-1}
      .b1-overview p{margin:0;line-height:1.8}
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

  globalThis.SecondItemPublicLabels = Object.freeze({patch});
})();
