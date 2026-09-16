"use strict";

(() => {
  const screenEl = document.getElementById("screen");
  if (!screenEl) return;

  const PUBLIC_GRADE = {G0:"E",G1:"D",G2:"C",G3:"B",G4:"A",G5:"S"};
  const POSITION_SUFFIX = {lower:"-",low:"-",middle:"",mid:"",upper:"+",high:"+"};
  const BAND_TEXT_GRADE = {"最低档":"E","较低档":"D","中低档":"C","中档":"B","较高档":"A","最高档":"S"};
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

  function publicMethodGrade(item) {
    const text = String(item?.grade || "");
    const band = text.match(/\bG([0-5])\b/i);
    if (!band) return "";
    const base = PUBLIC_GRADE[`G${band[1]}`] || "";
    const position = text.match(/(?:\/|-)\s*(lower|middle|upper|low|mid|high)\b/i)?.[1]?.toLowerCase();
    return `${base}${position ? POSITION_SUFFIX[position] ?? "" : ""}`;
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
    const first = text.match(/^.*?[。！？；;]/)?.[0] || text;
    return `边界：${first.trim()}`;
  }

  function ensureStyles() {
    if (document.getElementById("second-item-public-polish-style")) return;
    const style = document.createElement("style");
    style.id = "second-item-public-polish-style";
    style.textContent = `
      .second-item-public-grade-ready > .second-item-scale-note{display:none!important}
      .second-item-public-grade-ready::after{content:attr(data-public-grade-note);display:block;margin-top:4px;font-size:11px;line-height:1.55;color:var(--green);font-weight:600}
      .second-item-public-reading{margin:2px 0 4px}
      .second-item-public-reading .label{margin-top:8px}
      .second-item-public-reading ul{margin:8px 0 12px;padding-left:20px}
      .second-item-public-reading li{margin:5px 0;line-height:1.8}
      .second-item-public-reading .prose{margin:8px 0 12px}
      .second-item-page-note{margin-top:18px;padding-top:12px}
      .second-item-page-note>summary{font-size:13px;color:var(--muted)}
    `;
    document.head.append(style);
  }

  function setPublicGrade(span, valueNode, grade, noteParts) {
    if (!span || !grade) return;
    if (valueNode && valueNode.textContent !== grade) valueNode.textContent = grade;
    const note = noteParts.filter(Boolean).join("｜");
    span.classList.add("second-item-public-grade-ready");
    if (span.dataset.publicGradeNote !== note) span.dataset.publicGradeNote = note;
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
      setPublicGrade(
        summary?.querySelector(":scope > span"),
        summary?.querySelector(":scope > b"),
        grade,
        [`原始方向指数 ${Number(item.value).toFixed(1)} / ${METHOD_MAX[sourceLabel]}`, boundaryExcerpt(item)],
      );
    }

    for (const span of root.querySelectorAll(".component > span[data-second-source-label]")) {
      const sourceLabel = span.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const grade = publicMethodGrade(item);
      if (!item || !grade || !METHOD_MAX[sourceLabel]) continue;
      setPublicGrade(
        span,
        span.parentElement?.querySelector(":scope > b"),
        grade,
        [`原始方向指数 ${Number(item.value).toFixed(1)} / ${METHOD_MAX[sourceLabel]}`, boundaryExcerpt(item)],
      );
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
      setPublicGrade(
        summary?.querySelector(":scope > span"),
        summary?.querySelector(":scope > b"),
        meta.grade,
        [`结算分 ${Number(item.value).toFixed(1)}`, meta.lossText, boundaryExcerpt(item)],
      );
    }

    for (const span of root.querySelectorAll(".component > span[data-second-source-label]")) {
      const sourceLabel = span.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const meta = stateGradeMeta(item);
      if (!item || !meta?.grade || !FINANCE_MAX[sourceLabel]) continue;
      setPublicGrade(
        span,
        span.parentElement?.querySelector(":scope > b"),
        meta.grade,
        [`结算分 ${Number(item.value).toFixed(1)}`, meta.lossText, boundaryExcerpt(item)],
      );
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
      setPublicGrade(
        summary?.querySelector(":scope > span"),
        summary?.querySelector(":scope > b"),
        grade,
        [HANDOFF_LABELS[sourceLabel], boundaryExcerpt(item)],
      );
    }

    for (const span of root.querySelectorAll(".component > span[data-second-source-label]")) {
      const sourceLabel = span.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const grade = publicHandoffGrade(item);
      if (!item || !grade || !HANDOFF_LABELS[sourceLabel]) continue;
      setPublicGrade(
        span,
        span.parentElement?.querySelector(":scope > b"),
        grade,
        [HANDOFF_LABELS[sourceLabel], boundaryExcerpt(item)],
      );
    }
  }

  function patchGradeGroups(root, record) {
    patchMethodGrades(root, record);
    patchFinanceGrades(root, record);
    patchHandoffGrades(root, record);
  }

  function publicizeBandText(root) {
    if (!root) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      const parent = node.parentElement;
      if (!parent || parent.closest(".net-formal-basis-raw") || parent.closest(".net-audit-sources") || parent.closest(".sources") || parent.closest("a")) continue;
      const before = node.nodeValue || "";
      const after = before
        .replace(/(最低档|较低档|中低档|中档|较高档|最高档)(?:\s*[-/]\s*(lower|middle|upper|low|mid|high))?/gi, (_, label, pos) => {
          const base = BAND_TEXT_GRADE[label] || label;
          const suffix = pos ? POSITION_SUFFIX[String(pos).toLowerCase()] ?? "" : "";
          return `${base}${suffix}`;
        })
        .replace(/\bC[123]-([1-6])\b/g, (_, level) => `${STATE_GRADE[Number(level)] || level}档`)
        .replace(/\bD3-([0-5])\b/g, (_, level) => `${HANDOFF_GRADE[Number(level)] || level}档`)
        .replace(/\bH([0-5])\b/g, (_, level) => `${HANDOFF_GRADE[Number(level)] || level}档`)
        .replace(/\bL([0-3])\b/g, (_, level) => LOSS_TEXT[Number(level)] || "");
      if (after !== before) node.nodeValue = after;
    }
  }

  function cleanHistoricalText(value) {
    let text = String(value || "").replace(/`/g, "").trim();
    if (!text) return "";

    text = text
      .replace(/\bC[123]-([1-6])\b/g, (_, level) => `${STATE_GRADE[Number(level)] || level}档`)
      .replace(/\bD3-([0-5])\b/g, (_, level) => `${HANDOFF_GRADE[Number(level)] || level}档`)
      .replace(/\bH([0-5])\b/g, (_, level) => `${HANDOFF_GRADE[Number(level)] || level}档`)
      .replace(/\bL([0-3])\b/g, (_, level) => LOSS_TEXT[Number(level)] || "")
      .replace(/\b(?:B1-)?distributed\/personnel\s*M[0-3]\b/gi, "")
      .replace(/\b(?:MAJOR_RESTRUCTURE|mixed_positive|mixed_negative|external_constraint|canonical|support|core|central|distributed)\b/gi, "")
      .replace(/(?:正向|负向|混合偏正|混合偏负)?\s*M[0-3]\b/gi, "")
      .replace(/\bG[0-5](?:\s*[-/]\s*(?:lower|middle|upper|low|mid|high))?\b/gi, "")
      .replace(/\bS[+−-]?\b/g, "")
      .replace(/\bS_(?:end|main|avg|0)\b/gi, "")
      .replace(/\bP面\b/g, "生产方面")
      .replace(/\bM侧\b/g, "市场与货币方面")
      .replace(/\bF\/R面\b/g, "财政与储备方面")
      .replace(/^正向保留\s*\d+(?:\.\d+)?分[；，。]?\s*/, "")
      .replace(/(?:正向|负向)\s*\d+(?:\.\d+)?[；，。]?/g, "")
      .replace(/(?:制度净值|净值|合计)\s*\d+(?:\.\d+)?[；，。]?/g, "")
      .replace(/主阶段负态主导定\s*[。；]?/g, "主要阶段负面表现占主导。")
      .replace(/角色改为\s*[。；]?/g, "")
      .replace(/保留正向\s*[、，。；]?/g, "")
      .replace(/保留负向\s*[、，。；]?/g, "")
      .replace(/结算\s*[，,]?\s*/g, "")
      .replace(/不能从政治清洗或同一问责损害另造[^。；]*[。；]?/g, "")
      .replace(/不因正负规模或建设名望抬档[。；]?/g, "")
      .replace(/未过[^。；]*档门[。；]?/g, "")
      .replace(/阻断[^。；]*档[。；]?/g, "")
      .replace(/闭合/g, "确认")
      .replace(/去重/g, "避免重复计算")
      .replace(/[；，、]\s*[；，、]+/g, "；")
      .replace(/。\s*。+/g, "。")
      .replace(/；\s*。/g, "。")
      .replace(/，\s*。/g, "。")
      .replace(/\s+/g, " ")
      .trim();

    return text
      .split(/(?<=[。！？])/)
      .map(part => part.trim())
      .filter(part => part.length >= 6 && !/^(保留|角色|正式方向|旧结算|改档)/.test(part))
      .join("")
      .replace(/^[；，、：\s]+|[；，、：\s]+$/g, "")
      .trim();
  }

  function publicFacts(item) {
    const highlights = (Array.isArray(item?.reader_highlights) ? item.reader_highlights : [])
      .map(cleanHistoricalText)
      .filter(Boolean)
      .slice(0, 3);
    if (highlights.length) return highlights;
    const summary = cleanHistoricalText(item?.reader_summary || "");
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

  function patchMetricBodies(record) {
    if (!record?.net || !location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) return;
    const items = secondItems(record);
    const root = document.getElementById("net-major-body");
    if (!root) return;

    for (const detail of root.querySelectorAll(".net-metric-detail[data-second-source-label]")) {
      const label = detail.dataset.secondSourceLabel || "";
      const item = items.get(label);
      if (!item || item.reader_kind !== "judgment") continue;
      const body = detail.querySelector(":scope > .net-metric-body");
      if (!body) continue;

      const key = [item.reader_summary || "", ...(item.reader_highlights || []), item.reader_boundary || "", item.reader_how || "", item.reader_full_basis || ""].join("|");
      if (body.dataset.secondPublicBodyKey === key && body.querySelector(":scope > .second-item-public-reading")) {
        for (const note of body.querySelectorAll(".second-item-pool-note")) note.remove();
        continue;
      }

      const audit = body.querySelector(":scope > .net-audit-sources");
      if (audit) audit.remove();
      for (const note of audit?.querySelectorAll(".second-item-pool-note") || []) note.remove();

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
      const facts = publicFacts(item);
      if (facts.length > 1) {
        const list = document.createElement("ul");
        for (const fact of facts) list.append(makeTextBlock("li", "", fact));
        reading.append(list);
      } else if (facts.length === 1) {
        reading.append(makeTextBlock("p", "prose", facts[0]));
      } else {
        reading.append(makeTextBlock("p", "prose", "当前公开层没有可进一步压缩的独立事实摘要，可展开正式裁决原文核对。"));
      }
      body.append(reading);

      const boundary = cleanHistoricalText(item.reader_boundary || "");
      const boundaryDetails = makeDetails("范围与边界", boundary);
      if (boundaryDetails) body.append(boundaryDetails);

      const howDetails = makeDetails("这个分数怎么算？", String(item.reader_how || "").trim());
      if (howDetails) body.append(howDetails);
      if (formal) body.append(formal);
      if (audit) body.append(audit);
      body.dataset.secondPublicBodyKey = key;
    }
  }

  function patchGroupIntros(record) {
    if (!record?.net || !location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) return;
    const method = document.querySelector('[data-second-intro="method"]');
    const finance = document.querySelector('[data-second-intro="finance"]');
    const handoff = document.querySelector('[data-second-intro="handoff"]');
    const values = secondTotals(record);

    const methodText = `这一组看国家机器如何建立规则、配置官僚并形成反馈约束。当前合计 ${fmt(values.method)} 分；公开层先看等级和历史依据，具体指数与折算放在展开内容里。`;
    const financeText = `这一组看统治时期普通家庭、经济财政和社会安全的主要状态，再结合任内低谷、恢复与额外代价形成结果判断。当前合计 ${fmt(values.finance)} 分。`;
    const handoffText = `统治如何收尾，会直接影响国家机器和继承秩序能否平稳延续。行政连续性看旧国家机器有多少被接住，交接稳定看继承过程是否顺利；两项均以 S—E 六档显示。`;

    if (method && method.textContent !== methodText) method.textContent = methodText;
    if (finance && finance.textContent !== financeText) finance.textContent = financeText;
    if (handoff && handoff.textContent !== handoffText) handoff.textContent = handoffText;
  }

  function patchScorePresentation(record) {
    if (!record?.net) return;
    const totals = secondTotals(record);
    const rank = secondRankText(record);

    if (location.hash.match(/^#net\/[^/?#]+\/(?:all)?$/)) {
      const card = Array.from(document.querySelectorAll(".net-major-card")).find(node => /\/second(?:\/|$)/.test(node.getAttribute("href") || ""));
      if (card) {
        const big = card.querySelector(".big");
        if (big && totals.total != null) big.textContent = `${fmt(totals.total)} 分`;
        const breakdown = card.querySelector(":scope > .second-item-card-breakdown");
        if (breakdown && [totals.method, totals.finance, totals.handoff].every(value => value != null)) {
          breakdown.textContent = `${rank ? `${rank} · ` : ""}制度与行政 ${fmt(totals.method)} · 民生与社会 ${fmt(totals.finance)} · 政权交接 ${fmt(totals.handoff)}`;
        }
      }
    }

    if (location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) {
      const summary = document.querySelector(".second-item-reader-summary");
      const cards = summary?.querySelectorAll(".second-item-total-grid > div");
      if (cards?.length >= 3) {
        const values = [totals.method, totals.finance, totals.handoff];
        cards.forEach((card, index) => {
          const value = card.querySelector("b");
          if (value && values[index] != null) value.textContent = `${fmt(values[index])} 分`;
        });
        const financeSmall = cards[1]?.querySelector("small");
        if (financeSmall) financeSmall.textContent = "民生、经济财政、社会安全、恢复与额外代价";
      }

      const intro = document.querySelector(".net-detail-page > .panel");
      const scoreLine = intro?.querySelector(":scope > p.subline");
      if (scoreLine && totals.total != null) {
        scoreLine.textContent = `治国成效：${fmt(totals.total)} 分${rank ? `；${rank}` : ""}。先看结论，再展开到各项依据。`;
      }
    }

    if (location.hash.startsWith("#person/")) {
      const panel = document.getElementById("person-outcome");
      for (const row of panel?.querySelectorAll(":scope > .component") || []) {
        const span = row.querySelector("span");
        if (!span || !span.textContent.trim().startsWith("治国成效")) continue;
        const value = row.querySelector("b");
        if (value && totals.total != null) value.textContent = `${fmt(totals.total)} 分`;
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
      const value = cell.querySelector("b");
      if (value) value.textContent = `${fmt(score)} 分`;
    });
  }

  function replacePublicText(root) {
    if (!root) return;
    const replacements = [
      ["净收益计分总览", "统治绩效构成"],
      ["完整净收益计分页", "完整统治绩效详情"],
      ["独立净收益计分页", "独立统治绩效详情页"],
      ["净收益计分页", "统治绩效详情"],
      ["净收益计分详情加载失败", "统治绩效详情加载失败"],
      ["净收益详情地址无效", "统治绩效详情地址无效"],
      ["净收益正式结算", "统治绩效正式结算"],
      ["总榜净收益", "统治绩效总分"],
      ["净收益计分", "统治绩效"],
      ["本项不参与净收益计分", "本项不参与统治绩效计分"],
      ["恢复与额外成本", "恢复与额外代价"],
      ["社会安全与恢复成本", "社会安全、恢复与额外代价"],
    ];
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    while (walker.nextNode()) nodes.push(walker.currentNode);
    for (const node of nodes) {
      const parent = node.parentElement;
      if (!parent || parent.closest(".net-formal-basis-raw") || parent.closest(".net-audit-sources")) continue;
      let next = node.nodeValue || "";
      for (const [from, to] of replacements) next = next.replaceAll(from, to);
      if (next !== node.nodeValue) node.nodeValue = next;
    }
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
    replacePublicText(screenEl);

    const nav = document.querySelector(".net-major-nav");
    if (nav) nav.setAttribute("aria-label", "统治绩效详情");

    const secondNav = Array.from(document.querySelectorAll(".net-major-nav a")).find(a => /\/second(?:\/|$)/.test(a.getAttribute("href") || ""));
    if (secondNav && secondNav.textContent !== "治国成效") secondNav.textContent = "治国成效";

    for (const heading of document.querySelectorAll(".net-detail-head h1, .net-major-card h2")) {
      if (heading.textContent.includes("治国净收益")) heading.textContent = heading.textContent.replace(/治国净收益/g, "治国成效");
    }

    const reading = document.querySelector("#person-evidence .net-reading[data-net-compact='done']");
    if (reading) {
      const section = reading.closest("section.panel");
      const heading = section?.querySelector(":scope > h2, :scope > h3");
      if (heading?.textContent.trim() === "净收益构成") heading.textContent = "统治绩效构成";
    }
  }

  function patchPoolNote(record) {
    if (!record?.net || !location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) return;
    const root = document.getElementById("net-major-body");
    if (!root) return;
    for (const note of root.querySelectorAll(".second-item-pool-note")) note.remove();

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
      publicizeBandText(root);
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
