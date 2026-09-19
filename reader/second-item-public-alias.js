"use strict";

(() => {
  const screenEl = document.getElementById("screen");
  if (!screenEl) return;

  const PUBLIC_GRADE = {G0:"E",G1:"D",G2:"C",G3:"B",G4:"A",G5:"S"};
  const STATE_GRADE = {1:"E",2:"D",3:"C",4:"B",5:"A",6:"S"};
  const HANDOFF_GRADE = {0:"E",1:"D",2:"C",3:"B",4:"A",5:"S"};
  const LOSS_TEXT = {
    0:"未见独立有效低谷",
    1:"有局部或短时损害",
    2:"出现明显低谷",
    3:"出现严重低谷",
  };
  const METHOD_MAX = {"A制度建设":100,"B1官僚治理":100,"B2反馈与约束":80};
  const FINANCE_MAX = {"C1民生":80,"C2经济财政":35,"C3社会安全":60};
  const HANDOFF_LABELS = {
    "D1继任行政连续性":"行政承接",
    "D3政权交接稳定":"终局继承",
  };
  const SECOND_GROUPS = ["method", "finance", "handoff"];
  let scheduled = false;

  function finite(value) {
    if (value == null || value === "") return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function fmt(value, digits = 1) {
    const n = finite(value);
    return n == null ? "—" : n.toFixed(digits);
  }

  function personRecord() {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#person\/([^/?#]+)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; } catch { return null; }
  }

  function netRecord() {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#net\/([^/?#]+)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; } catch { return null; }
  }

  function compareRecords() {
    if (typeof byId === "undefined" || !location.hash.startsWith("#compare/")) return [];
    return location.hash.slice(9).split("/").filter(Boolean).slice(0, 2).map(id => {
      try { return byId.get(decodeURIComponent(id)) || null; } catch { return null; }
    }).filter(Boolean);
  }

  function itemMap(record, key) {
    return new Map((record?.net?.component_details?.[key] || []).map(item => [item.label, item]));
  }

  function secondItems(record) {
    const result = new Map();
    for (const key of SECOND_GROUPS) {
      for (const item of record?.net?.component_details?.[key] || []) result.set(item.label, item);
    }
    return result;
  }

  function secondTotals(record) {
    const method = itemMap(record, "method");
    const finance = itemMap(record, "finance");
    const handoff = itemMap(record, "handoff");
    return {
      method: finite(method.get("治理手段")?.value),
      finance: finite(finance.get("治理结果")?.value),
      handoff: finite(handoff.get("交接得分")?.value),
      total: finite(record?.net?.second_item_score ?? handoff.get("第二项合计")?.value),
    };
  }

  function currentSecondPool() {
    if (typeof byId === "undefined") return [];
    return Array.from(byId.values()).filter(record =>
      !record?.supplementary && finite(record?.net?.second_item_score) != null
    );
  }

  function secondRankText(record) {
    const score = finite(record?.net?.second_item_score);
    if (score == null) return "";
    const pool = currentSecondPool();
    if (!pool.length) return "";
    const rank = 1 + pool.filter(item => finite(item?.net?.second_item_score) > score).length;
    const pct = Math.max(1, Math.min(100, Math.ceil(rank / pool.length * 100)));
    return `当前已结算人物：第 ${rank} / ${pool.length}（约前 ${pct}%）`;
  }

  function positionSuffix(text) {
    const lower = String(text || "").toLowerCase();
    if (/lower|low/.test(lower)) return "-";
    if (/upper|high/.test(lower)) return "+";
    return "";
  }

  function publicMethodGrade(item) {
    const text = String(item?.grade || "");
    const band = text.match(/\bG([0-5])\b/i);
    if (!band) return "";
    return `${PUBLIC_GRADE[`G${band[1]}`] || ""}${positionSuffix(text)}`;
  }

  function stateGradeMeta(item) {
    const match = String(item?.grade || "").match(/\bC[123]-(\d)\s*\/\s*L([0-3])\b/i);
    if (!match) return null;
    const band = Number(match[1]);
    const loss = Number(match[2]);
    return {grade:STATE_GRADE[band] || "",lossText:LOSS_TEXT[loss] || ""};
  }

  function publicHandoffGrade(item) {
    const level = Number(item?.value);
    return Number.isInteger(level) ? HANDOFF_GRADE[level] || "" : "";
  }

  function boundaryExcerpt(item) {
    const text = String(item?.reader_boundary || "").trim();
    if (!text) return "";
    return "适用范围与限制见展开说明";
  }

  function ensureStyles() {
    if (document.getElementById("second-item-public-polish-style")) return;
    const style = document.createElement("style");
    style.id = "second-item-public-polish-style";
    style.textContent = `
      .second-item-public-grade-ready > .second-item-scale-note{display:block;margin-top:4px;font-size:11px;line-height:1.55;color:var(--green);font-weight:600}
      .net-metric-detail>summary b.second-item-public-value{font:20px Georgia,serif;color:var(--green)}
      .component>b.second-item-public-value{font-size:13px;color:var(--green)}
      .second-item-public-copy{font-size:13px;line-height:1.7}
      small.second-item-public-copy{font-size:11px;color:var(--muted);line-height:1.55}
      .net-major-card .big.second-item-public-score{font:30px Georgia,serif;color:var(--green)}
      .second-item-total-grid b.second-item-public-score{font:21px Georgia,serif;color:var(--green)}
      .second-item-public-reading{margin:2px 0 4px}
      .second-item-public-reading .label{margin-top:8px}
      .second-item-public-reading ul{margin:8px 0 12px;padding-left:20px}
      .second-item-public-reading li{margin:5px 0;line-height:1.8}
      .second-item-public-reading .prose{margin:8px 0 12px}
      .second-item-pool-note{display:none!important}
      .second-item-page-note{margin-top:18px;padding-top:12px}
      .second-item-page-note>summary{font-size:13px;color:var(--muted)}
    `;
    document.head.append(style);
  }

  // The public layer owns these text nodes. The structural renderer respects
  // the data-public-* markers instead of restoring its intermediate copy.
  // Write real text: CSS generated content is not a replacement for readable DOM.
  function setPublicText(node, text, key, className) {
    if (!node || !text) return;
    node.classList.add(className);
    if (node.dataset[key] !== text) node.dataset[key] = text;
    if (node.textContent !== text) node.textContent = text;
  }

  function writePublicCopy(node, text) {
    setPublicText(node, text, "publicCopy", "second-item-public-copy");
  }

  function writePublicScore(node, text) {
    setPublicText(node, text, "publicScore", "second-item-public-score");
  }

  function setPublicGrade(span, valueNode, grade, noteParts) {
    if (!span || !grade) return;
    const note = noteParts.filter(Boolean).join("｜");
    span.classList.add("second-item-public-grade-ready");
    if (span.dataset.publicGradeNote !== note) span.dataset.publicGradeNote = note;
    let noteNode = span.querySelector(":scope > .second-item-scale-note");
    if (!noteNode) {
      noteNode = document.createElement("small");
      noteNode.className = "second-item-scale-note";
      span.append(noteNode);
    }
    if (noteNode.textContent !== note) noteNode.textContent = note;
    setPublicText(valueNode, grade, "publicValue", "second-item-public-value");
  }

  function patchMethodGrades(root, record) {
    if (!root || !record?.net) return;
    const items = itemMap(record, "method");
    if (!items.size) return;
    for (const detail of root.querySelectorAll(".net-metric-detail[data-second-source-label]")) {
      const sourceLabel = detail.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const grade = publicMethodGrade(item);
      if (!item || !grade || !METHOD_MAX[sourceLabel]) continue;
      const summary = detail.querySelector(":scope > summary");
      setPublicGrade(summary?.querySelector(":scope > span"), summary?.querySelector(":scope > b"), grade,
        [`原始方向指数 ${Number(item.value).toFixed(1)} / ${METHOD_MAX[sourceLabel]}`, boundaryExcerpt(item)]);
    }
    for (const span of root.querySelectorAll(".component > span[data-second-source-label]")) {
      const sourceLabel = span.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const grade = publicMethodGrade(item);
      if (!item || !grade || !METHOD_MAX[sourceLabel]) continue;
      setPublicGrade(span, span.parentElement?.querySelector(":scope > b"), grade,
        [`原始方向指数 ${Number(item.value).toFixed(1)} / ${METHOD_MAX[sourceLabel]}`, boundaryExcerpt(item)]);
    }
  }

  function patchFinanceGrades(root, record) {
    if (!root || !record?.net) return;
    const items = itemMap(record, "finance");
    if (!items.size) return;
    for (const detail of root.querySelectorAll(".net-metric-detail[data-second-source-label]")) {
      const sourceLabel = detail.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const meta = stateGradeMeta(item);
      if (!item || !meta?.grade || !FINANCE_MAX[sourceLabel]) continue;
      const summary = detail.querySelector(":scope > summary");
      setPublicGrade(summary?.querySelector(":scope > span"), summary?.querySelector(":scope > b"), meta.grade,
        [`结算分 ${Number(item.value).toFixed(1)}`, meta.lossText, boundaryExcerpt(item)]);
    }
    for (const span of root.querySelectorAll(".component > span[data-second-source-label]")) {
      const sourceLabel = span.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const meta = stateGradeMeta(item);
      if (!item || !meta?.grade || !FINANCE_MAX[sourceLabel]) continue;
      setPublicGrade(span, span.parentElement?.querySelector(":scope > b"), meta.grade,
        [`结算分 ${Number(item.value).toFixed(1)}`, meta.lossText, boundaryExcerpt(item)]);
    }
  }

  function patchHandoffGrades(root, record) {
    if (!root || !record?.net) return;
    const items = itemMap(record, "handoff");
    if (!items.size) return;
    for (const detail of root.querySelectorAll(".net-metric-detail[data-second-source-label]")) {
      const sourceLabel = detail.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const grade = publicHandoffGrade(item);
      if (!item || !grade || !HANDOFF_LABELS[sourceLabel]) continue;
      const summary = detail.querySelector(":scope > summary");
      setPublicGrade(summary?.querySelector(":scope > span"), summary?.querySelector(":scope > b"), grade,
        [HANDOFF_LABELS[sourceLabel], boundaryExcerpt(item)]);
    }
    for (const span of root.querySelectorAll(".component > span[data-second-source-label]")) {
      const sourceLabel = span.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const grade = publicHandoffGrade(item);
      if (!item || !grade || !HANDOFF_LABELS[sourceLabel]) continue;
      setPublicGrade(span, span.parentElement?.querySelector(":scope > b"), grade,
        [HANDOFF_LABELS[sourceLabel], boundaryExcerpt(item)]);
    }
  }

  function patchGradeGroups(root, record) {
    patchMethodGrades(root, record);
    patchFinanceGrades(root, record);
    patchHandoffGrades(root, record);
  }

  function publicTechnicalText(value) {
    return String(value ?? "")
      .replace(/\bG([0-5])\s*[-/]\s*([A-Za-z-]+)\b/gi, (_, band, position) => `${PUBLIC_GRADE[`G${band}`] || ""}${positionSuffix(position)}`)
      .replace(/\bG([0-5])\b/g, (_, band) => PUBLIC_GRADE[`G${band}`] || band)
      .replace(/\bC[123]-([1-6])\s*\/\s*L([0-3])\b/g, (_, band, loss) => `${STATE_GRADE[Number(band)] || band}档；${LOSS_TEXT[Number(loss)] || ""}`)
      .replace(/\bC[123]-([1-6])\b/g, (_, band) => `${STATE_GRADE[Number(band)] || band}档`)
      .replace(/\bD3-([0-5])\b/g, (_, level) => `${HANDOFF_GRADE[Number(level)] || level}档`)
      .replace(/\bH([0-5])\b/g, (_, level) => `${HANDOFF_GRADE[Number(level)] || level}档`)
      .replace(/\bL([0-3])\b/g, (_, level) => LOSS_TEXT[Number(level)] || "")
      .trim();
  }

  // Public prose is already adjudicated upstream. Keep short sentences,
  // negation, quotations and boundaries verbatim; format only outer whitespace.
  function publicText(value) {
    return String(value ?? "").trim();
  }

  function publicFacts(item) {
    const evidence = Array.isArray(item?.reader_public_evidence_items) ? item.reader_public_evidence_items : [];
    if (evidence.length) {
      return evidence.map(entry => {
        if (!entry || typeof entry !== "object") return "";
        const label = String(entry.public_label || "").trim();
        const direction = String(entry.public_direction || "").trim();
        const basis = publicText(entry.public_basis || "");
        const boundary = publicText(entry.public_boundary || "");
        return [
          [label, direction].filter(Boolean).join(" · "),
          basis,
          boundary ? `边界：${boundary}` : "",
        ].filter(Boolean).join("；");
      }).map(publicText).filter(Boolean);
    }
    const highlights = (Array.isArray(item?.reader_highlights) ? item.reader_highlights : [])
      .map(publicText).filter(Boolean);
    if (highlights.length) return highlights;
    const summary = publicText(item?.reader_summary || "");
    return summary ? [summary] : [];
  }

  function makeTextBlock(tagName, className, text) {
    const node = document.createElement(tagName);
    if (className) node.className = className;
    node.textContent = text;
    return node;
  }

  function makeDetails(title, text, className = "") {
    if (!text) return null;
    const details = document.createElement("details");
    if (className) details.className = className;
    const summary = document.createElement("summary");
    summary.textContent = title;
    details.append(summary, makeTextBlock("p", "prose", text));
    return details;
  }

  function publicEvidenceList(evidence) {
    const list = makeTextBlock("ul", "second-item-public-evidence", "");
    for (const entry of evidence) {
      const card = makeTextBlock("li", "second-item-public-evidence-card", "");
      const title = [publicText(entry.public_label || entry.public_role), publicText(entry.public_direction)].filter(Boolean).join(" · ");
      if (title) card.append(makeTextBlock("strong", "", title));
      card.append(makeTextBlock("p", "prose", publicText(entry.public_basis)));
      const boundary = makeDetails("适用范围与限制", publicText(entry.public_boundary));
      if (boundary) card.append(boundary);
      list.append(card);
    }
    return list;
  }

  function patchMetricBodies(record) {
    if (!record?.net || !location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) return;
    const items = secondItems(record);
    const root = document.getElementById("net-major-body");
    if (!root) return;
    for (const detail of root.querySelectorAll(".net-metric-detail[data-second-source-label]")) {
      const label = detail.dataset.secondSourceLabel || "";
      // Dedicated A/B1 renderers own these bodies. Do not overwrite them when
      // their asynchronous formal data load triggers the shared observer.
      if (label === "A制度建设" || label === "B1官僚治理") continue;
      const item = items.get(label);
      if (!item || item.reader_kind !== "judgment") continue;
      const body = detail.querySelector(":scope > .net-metric-body");
      if (!body) continue;
      const key = [item.reader_summary || "", JSON.stringify(item.reader_public_evidence_items || []), ...(item.reader_highlights || []), item.reader_boundary || "", item.reader_how || "", item.reader_full_basis || ""].join("|");
      if (body.dataset.secondPublicBodyKey === key && body.querySelector(":scope > .second-item-public-reading")) continue;
      const audit = body.querySelector(":scope > .net-audit-sources");
      if (audit) audit.remove();
      let formal = body.querySelector(":scope > .net-formal-basis-raw");
      if (formal) formal.remove();
      const raw = String(item.reader_full_basis || "").trim();
      if (!formal && raw && raw !== String(item.reader_summary || "").trim()) {
        formal = makeDetails("正式裁决原文（未改写）", raw, "net-formal-basis-raw");
      }
      body.innerHTML = "";
      const reading = document.createElement("div");
      reading.className = "second-item-public-reading";
      reading.append(makeTextBlock("div", "label", "为什么这样判断"));
      const evidence = item.reader_public_evidence_items;
      const facts = publicFacts(item);
      if (Array.isArray(evidence) && evidence.length) {
        reading.append(publicEvidenceList(evidence));
      } else if (facts.length > 1) {
        const list = document.createElement("ul");
        for (const fact of facts) list.append(makeTextBlock("li", "", fact));
        reading.append(list);
      } else if (facts.length === 1) {
        reading.append(makeTextBlock("p", "prose", facts[0]));
      } else {
        reading.append(makeTextBlock("p", "prose", "当前尚未提供公开说明，请查看正式记录。"));
      }
      body.append(reading);
      const boundaryDetails = makeDetails("范围与边界", publicText(item.reader_boundary || ""));
      if (boundaryDetails) body.append(boundaryDetails);
      const howDetails = makeDetails("这个分数怎么算？", publicTechnicalText(item.reader_how || ""));
      if (howDetails) body.append(howDetails);
      if (formal) body.append(formal);
      if (audit) body.append(audit);
      body.dataset.secondPublicBodyKey = key;
    }
  }

  function patchGroupIntros(record) {
    if (!record?.net || !location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) return;
    const values = secondTotals(record);
    writePublicCopy(document.querySelector('[data-second-intro="method"]'),
      `这一组看国家机器如何建立规则、配置官僚并形成反馈约束。当前合计 ${fmt(values.method)} 分；公开层先看等级和历史依据，具体指数与折算放在展开内容里。`);
    writePublicCopy(document.querySelector('[data-second-intro="finance"]'),
      `这一组看统治时期普通家庭、经济财政和社会安全的主要状态，再结合任内低谷、恢复与额外代价形成结果判断。当前合计 ${fmt(values.finance)} 分。`);
    writePublicCopy(document.querySelector('[data-second-intro="handoff"]'),
      "统治如何收尾，会直接影响国家机器和继承秩序能否平稳延续。行政连续性看旧国家机器有多少被接住，交接稳定看继承过程是否顺利；两项均以 S—E 六档显示。");
  }

  function patchScorePresentation(record) {
    if (!record?.net) return;
    const totals = secondTotals(record);
    const rank = secondRankText(record);
    if (location.hash.match(/^#net\/[^/?#]+\/(?:all)?$/)) {
      const card = Array.from(document.querySelectorAll(".net-major-card")).find(node => /\/second(?:\/|$)/.test(node.getAttribute("href") || ""));
      if (card) {
        if (totals.total != null) writePublicScore(card.querySelector(".big"), `${fmt(totals.total)} 分`);
        if ([totals.method, totals.finance, totals.handoff].every(value => value != null)) {
          writePublicCopy(card.querySelector(":scope > .second-item-card-breakdown"),
            `${rank ? `${rank} · ` : ""}制度与行政 ${fmt(totals.method)} · 民生与社会 ${fmt(totals.finance)} · 政权交接 ${fmt(totals.handoff)}`);
        }
      }
    }
    if (location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) {
      const summary = document.querySelector(".second-item-reader-summary");
      const cards = summary?.querySelectorAll(".second-item-total-grid > div");
      if (cards?.length >= 3) {
        const values = [totals.method, totals.finance, totals.handoff];
        cards.forEach((card, index) => { if (values[index] != null) writePublicScore(card.querySelector("b"), `${fmt(values[index])} 分`); });
        writePublicCopy(cards[1]?.querySelector("small"), "民生、经济财政、社会安全、恢复与额外代价");
      }
      const intro = document.querySelector(".net-detail-page > .panel");
      const scoreLine = intro?.querySelector(":scope > p.subline");
      if (totals.total != null) writePublicCopy(scoreLine, `治国成效：${fmt(totals.total)} 分${rank ? `；${rank}` : ""}。先看结论，再展开到各项依据。`);
    }
    if (location.hash.startsWith("#person/")) {
      const panel = document.getElementById("person-outcome");
      for (const row of panel?.querySelectorAll(":scope > .component") || []) {
        const span = row.querySelector("span");
        if (!span || !span.textContent.trim().startsWith("治国成效")) continue;
        if (totals.total != null) writePublicScore(row.querySelector("b"), `${fmt(totals.total)} 分`);
      }
    }
  }

  function patchCompareScores(records) {
    if (records.length < 2 || !location.hash.startsWith("#compare/")) return;
    const row = Array.from(screenEl.querySelectorAll(".comparison tbody tr")).find(item => item.cells?.[0]?.textContent.trim() === "治国成效");
    if (!row) return;
    records.forEach((record, index) => {
      const score = finite(record?.net?.second_item_score);
      const cell = row.cells?.[index + 1];
      if (!cell || score == null) return;
      writePublicScore(cell.querySelector("b"), `${fmt(score)} 分`);
    });
  }

  function replaceText(node, replacements) {
    if (!node) return;
    let next = node.textContent;
    for (const [from, to] of replacements) next = next.replaceAll(from, to);
    if (next !== node.textContent) node.textContent = next;
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

  function patchShellLanguage() {
    const head = document.querySelector(".net-detail-head");
    replaceText(head?.querySelector(".eyebrow"), [["净收益计分", "统治绩效"]]);
    replaceText(head?.querySelector("h1"), [["净收益计分总览", "统治绩效构成"], ["治国净收益", "治国成效"]]);
    replaceText(head?.querySelector(".muted"), [["总榜净收益", "统治绩效总分"]]);
    const nav = document.querySelector(".net-major-nav");
    if (nav) nav.setAttribute("aria-label", "统治绩效详情");
    const secondNav = Array.from(nav?.querySelectorAll("a") || []).find(a => /\/second(?:\/|$)/.test(a.getAttribute("href") || ""));
    if (secondNav && secondNav.textContent !== "治国成效") secondNav.textContent = "治国成效";
    for (const cardTitle of document.querySelectorAll(".net-major-card h2")) {
      replaceText(cardTitle, [["治国净收益", "治国成效"], ["净收益计分总览", "统治绩效构成"]]);
    }
    const reading = document.querySelector("#person-evidence .net-reading[data-net-compact='done']");
    if (reading) {
      const section = reading.closest("section.panel");
      const heading = section?.querySelector(":scope > h2, :scope > h3");
      if (heading?.textContent.trim() === "净收益构成") heading.textContent = "统治绩效构成";
      for (const link of reading.querySelectorAll("a")) replaceText(link, [["净收益计分页", "统治绩效详情"], ["净收益计分", "统治绩效"]]);
      for (const intro of reading.querySelectorAll("p.reading-intro")) replaceText(intro, [["独立净收益计分页", "独立统治绩效详情页"]]);
    }
    for (const message of screenEl.querySelectorAll(".empty p, .empty[role='status']")) {
      replaceText(message, [
        ["净收益计分详情加载失败", "统治绩效详情加载失败"],
        ["净收益详情地址无效", "统治绩效详情地址无效"],
        ["净收益正式结算", "统治绩效正式结算"],
        ["净收益计分逻辑", "统治绩效详情"],
      ]);
    }
  }

  function patchPoolNote(record) {
    if (!record?.net || !location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) return;
    const root = document.getElementById("net-major-body");
    if (!root) return;
    let details = root.querySelector(":scope > .second-item-page-note");
    if (!details) {
      details = document.createElement("details");
      details.className = "second-item-page-note";
      const summary = document.createElement("summary");
      summary.textContent = "排名与数据口径";
      details.append(summary, document.createElement("p"));
      root.append(details);
    }
    const pool = currentSecondPool().length;
    const text = `当前公开名次只比较已完成治国成效正式结算并进入当前主池的人物，共 ${pool} 人；待正式结算与补充对象不进入本名次。`;
    const p = details.querySelector("p");
    if (p && p.textContent !== text) p.textContent = text;
  }

  function patchPublicGrades() {
    const net = netRecord();
    if (net && location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) {
      const root = document.getElementById("net-major-body");
      patchGradeGroups(root, net);
      patchMetricBodies(net);
      patchGroupIntros(net);
      patchPoolNote(net);
    }
    const person = personRecord();
    if (person) patchGradeGroups(screenEl, person);
    const records = compareRecords();
    if (records.length) {
      const rows = Array.from(screenEl.querySelectorAll(".comparison tbody tr"));
      const structureRow = rows.find(row => row.cells?.[0]?.textContent.trim() === "构成与依据");
      if (structureRow) records.forEach((record, index) => patchGradeGroups(structureRow.cells[index + 1], record));
      patchCompareScores(records);
    }
  }

  function patch() {
    ensureStyles();
    patchPersonOutcomeLink();
    patchShellLanguage();
    patchPublicGrades();
    const net = netRecord();
    if (net) patchScorePresentation(net);
    const person = personRecord();
    if (person) patchScorePresentation(person);
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      patch();
    });
  }

  new MutationObserver(schedule).observe(screenEl, {childList:true, subtree:true, characterData:true});
  window.addEventListener("hashchange", schedule);
  schedule();
})();
