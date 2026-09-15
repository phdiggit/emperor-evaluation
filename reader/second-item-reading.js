"use strict";

(() => {
  const screenEl = document.getElementById("screen");
  if (!screenEl) return;

  const METHOD_BAND_LABELS = {
    G0: "最低档",
    G1: "较低档",
    G2: "中低档",
    G3: "中档",
    G4: "较高档",
    G5: "最高档",
  };
  const FINANCE_MAX = {
    "C1民生": 80,
    "C2经济财政": 35,
    "C3社会安全": 60,
  };

  let scheduled = false;

  function finite(value) {
    if (value == null || value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function fmt(value, digits = 1) {
    const number = finite(value);
    return number == null ? "—" : number.toFixed(digits);
  }

  function signedFmt(value, digits = 1) {
    const number = finite(value);
    if (number == null) return "—";
    return `${number > 0 ? "+" : ""}${number.toFixed(digits)}`;
  }

  function setNodeText(node, text) {
    if (node && node.textContent !== text) node.textContent = text;
  }

  function directText(node) {
    if (!node) return "";
    return Array.from(node.childNodes)
      .filter(child => child.nodeType === Node.TEXT_NODE)
      .map(child => child.nodeValue || "")
      .join("")
      .trim();
  }

  function recordForNetRoute() {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#net\/([^/?#]+)\/(?:all|second)(?:\/|$)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; }
    catch { return null; }
  }

  function recordForPersonRoute() {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#person\/([^/?#]+)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; }
    catch { return null; }
  }

  function recordsForCompareRoute() {
    if (typeof byId === "undefined" || !location.hash.startsWith("#compare/")) return [];
    const ids = location.hash.slice("#compare/".length).split("/").filter(Boolean);
    return ids.slice(0, 2).map(id => {
      try { return byId.get(decodeURIComponent(id)) || null; }
      catch { return null; }
    }).filter(Boolean);
  }

  function itemsFor(record, key) {
    return new Map((record?.net?.component_details?.[key] || []).map(item => [item.label, item]));
  }

  function currentSecondPool() {
    if (typeof byId === "undefined") return [];
    return Array.from(byId.values())
      .filter(record => !record?.supplementary && finite(record?.net?.second_item_score) != null)
      .map(record => ({
        id: String(record.ruler_id || ""),
        score: finite(record.net.second_item_score),
      }));
  }

  function secondPoolPosition(record) {
    const score = finite(record?.net?.second_item_score);
    if (score == null) return null;
    const eligible = currentSecondPool();
    if (!eligible.length) return null;
    return {
      rank: 1 + eligible.filter(item => item.score > score).length,
      total: eligible.length,
    };
  }

  function secondTotals(record) {
    const method = itemsFor(record, "method");
    const finance = itemsFor(record, "finance");
    const handoff = itemsFor(record, "handoff");
    return {
      method,
      finance,
      handoff,
      methodScore: finite(method.get("治理手段")?.value),
      resultScore: finite(finance.get("治理结果")?.value),
      handoffScore: finite(handoff.get("交接得分")?.value),
      c1: finite(finance.get("C1民生")?.value),
      c2: finite(finance.get("C2经济财政")?.value),
      c3: finite(finance.get("C3社会安全")?.value),
      c4: finite(finance.get("C4恢复与成本")?.value),
      totalScore: finite(record?.net?.second_item_score ?? handoff.get("第二项合计")?.value),
      pool: secondPoolPosition(record),
    };
  }

  function methodBand(item) {
    const match = String(item?.grade || "").match(/\bG([0-5])\b/);
    return match ? METHOD_BAND_LABELS[`G${match[1]}`] : "正式档未标明";
  }

  function stateMeta(item) {
    const grade = String(item?.grade || "");
    const match = grade.match(/\bC[123]-(\d+)\s*\/\s*L(\d+)\b/);
    if (!match) return "";
    const low = Number(match[2]);
    return `主要状态第${match[1]}档｜${low === 0 ? "无额外低谷修正" : `低谷修正${low}级`}`;
  }

  function boundaryHint(item) {
    const text = String(item?.reader_boundary || "").trim();
    if (!text) return "";
    const tags = [];
    if (/短任|短窗口|任期极短|窗口较短|最高权力窗口较短/.test(text)) tags.push("短窗口");
    if (/缺少|缺人口|材料.{0,8}(?:不足|稀疏|有限)|证据.{0,8}(?:不足|稀疏|有限|敏感)|对新增.{0,8}敏感|未闭合.{0,10}(?:证据|强锚)|不足以/.test(text)) tags.push("证据限制");
    return tags.length ? `正式边界：${[...new Set(tags)].join(" / ")}` : "";
  }

  function rankText(totals) {
    return totals.pool
      ? `当前主池已完成第二项结算：第 ${fmt(totals.pool.rank, 0)} / ${fmt(totals.pool.total, 0)}`
      : "";
  }

  function personConclusion(totals) {
    const a = methodBand(totals.method.get("A制度建设"));
    const b1 = methodBand(totals.method.get("B1官僚治理"));
    const b2 = methodBand(totals.method.get("B2反馈与约束"));
    return `三块总账：治理手段 ${fmt(totals.methodScore)} / 165，治理结果 ${fmt(totals.resultScore)} / 202，交接质量 ${fmt(totals.handoffScore)} / 20。制度行政正式方向档：制度建设${a}、官僚治理${b1}、反馈约束${b2}；C1—C3记录统治窗口内状态，C4净调整 ${signedFmt(totals.c4)}。`;
  }

  function ensureStyles() {
    if (document.getElementById("second-item-reading-style")) return;
    const style = document.createElement("style");
    style.id = "second-item-reading-style";
    style.textContent = `
      .second-item-reader-summary{border:1px solid var(--line);border-left:4px solid var(--green);border-radius:6px;padding:16px 18px;margin:0 0 18px;background:#f6f7f1}
      .second-item-reader-summary h2{font-size:21px;margin:0 0 8px}
      .second-item-person-conclusion{font-size:15px;line-height:1.8;margin:8px 0 10px}
      .second-item-rank{display:inline-block;margin:2px 0 8px;padding:4px 9px;border-radius:4px;background:#e8ece4;color:var(--green);font-size:12px;font-weight:600}
      .second-item-total-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:12px 0}
      .second-item-total-grid div{border:1px solid var(--line);border-radius:5px;padding:10px 12px;background:#fcfbf7;font-size:12px}
      .second-item-total-grid b{display:block;font:21px Georgia,serif;color:var(--green);margin-top:3px}
      .second-item-equation{margin-top:12px;padding-top:11px;border-top:1px solid var(--line);font-size:14px}
      .second-item-equation strong{color:var(--green)}
      .second-item-scale-note{display:block;margin-top:4px;font-size:11px;color:var(--green);font-weight:600}
      .second-item-group-intro{margin:0 0 14px;padding:11px 13px;border-left:3px solid var(--gold);background:#f1eee6;font-size:13px;line-height:1.75}
      .second-item-c4-note{margin:0 0 12px;padding:9px 11px;border-left:3px solid var(--green);background:#f1eee6;font-size:13px;line-height:1.75}
      .second-item-card-breakdown,.second-item-inline-rank{font-size:12px;color:var(--muted);line-height:1.65}
      .second-item-inline-rank{display:block;margin-top:3px;color:var(--green)}
      .second-item-formal-basis{margin-top:12px;border-top:1px solid var(--line)}
      .second-item-formal-basis>.second-item-formal-basis-content{padding-top:8px}
      .net-major-card.second-item-card .big{font-size:30px}
      @media(max-width:700px){.second-item-total-grid{grid-template-columns:1fr}}
    `;
    document.head.append(style);
  }

  function addGroupIntro(section, key, text) {
    if (!section) return;
    let intro = section.querySelector(`:scope > [data-second-intro="${key}"]`);
    if (!intro) {
      intro = document.createElement("p");
      intro.className = "second-item-group-intro";
      intro.dataset.secondIntro = key;
      const heading = section.querySelector(":scope > h2");
      if (heading?.nextSibling) section.insertBefore(intro, heading.nextSibling);
      else section.append(intro);
    }
    setNodeText(intro, text);
  }

  function metricDetail(section, labels) {
    const wanted = new Set(Array.isArray(labels) ? labels : [labels]);
    return Array.from(section?.querySelectorAll(":scope > .net-metric-detail") || []).find(detail =>
      wanted.has(detail.dataset.secondSourceLabel || detail.querySelector(":scope > summary strong")?.textContent.trim())
    ) || null;
  }

  function markSourceLabel(detail, label) {
    if (detail && !detail.dataset.secondSourceLabel) detail.dataset.secondSourceLabel = label;
  }

  function setMetricDisplay(detail, valueText, noteText, titleText = "") {
    if (!detail) return;
    const summary = detail.querySelector(":scope > summary");
    const strong = summary?.querySelector("strong");
    const value = summary?.querySelector(":scope > b");
    const span = summary?.querySelector(":scope > span");
    if (titleText) setNodeText(strong, titleText);
    setNodeText(value, valueText);
    if (!span) return;
    let note = span.querySelector(":scope > .second-item-scale-note");
    if (!note) {
      note = document.createElement("small");
      note.className = "second-item-scale-note";
      span.append(note);
    }
    setNodeText(note, noteText);
  }

  function joinNote(...parts) {
    return parts.filter(Boolean).join("｜");
  }

  function ensureLandingCard(record, totals) {
    if (!location.hash.match(/^#net\/[^/?#]+\/(?:all)?$/)) return;
    const card = Array.from(document.querySelectorAll(".net-major-card")).find(item =>
      item.getAttribute("href")?.includes("/second")
    );
    if (!card) return;
    card.classList.add("second-item-card");
    setNodeText(card.querySelector(".big"), totals.totalScore == null ? "—" : `${fmt(totals.totalScore)} / 387`);
    const description = Array.from(card.querySelectorAll(":scope > p")).find(p =>
      !p.classList.contains("sources") && !p.classList.contains("second-item-card-breakdown")
    );
    setNodeText(description, "先看治理机器怎么运转、本人统治窗口内社会处于什么状态，再看离场时如何完成终局交班。");

    if ([totals.methodScore, totals.resultScore, totals.handoffScore].some(value => value == null)) return;
    let breakdown = card.querySelector(":scope > .second-item-card-breakdown");
    if (!breakdown) {
      breakdown = document.createElement("p");
      breakdown.className = "second-item-card-breakdown";
      const sources = card.querySelector(":scope > p.sources");
      card.insertBefore(breakdown, sources || null);
    }
    const rank = rankText(totals);
    setNodeText(
      breakdown,
      `${rank ? `${rank} · ` : ""}治理手段 ${fmt(totals.methodScore)}/165 · 治理结果 ${fmt(totals.resultScore)}/202 · 交接质量 ${fmt(totals.handoffScore)}/20`
    );
  }

  function ensureSecondSummary(record, totals) {
    if (!location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) return;
    const container = document.getElementById("net-major-body");
    if (!container) return;
    if ([totals.methodScore, totals.resultScore, totals.handoffScore, totals.totalScore].some(value => value == null)) return;

    const rank = rankText(totals);
    let summary = container.querySelector(":scope > .second-item-reader-summary");
    if (!summary) {
      summary = document.createElement("section");
      summary.className = "second-item-reader-summary";
      container.insertBefore(summary, container.firstChild);
    }

    const renderKey = [
      totals.methodScore, totals.resultScore, totals.handoffScore, totals.totalScore, totals.c4, rank,
      methodBand(totals.method.get("A制度建设")),
      methodBand(totals.method.get("B1官僚治理")),
      methodBand(totals.method.get("B2反馈与约束")),
    ].join("|");
    if (summary.dataset.secondRenderKey !== renderKey) {
      summary.innerHTML = `<h2>先看这个人的治国结论</h2><p class="second-item-person-conclusion">${personConclusion(totals)}</p>${rank ? `<span class="second-item-rank">${rank}</span>` : ""}<div class="second-item-total-grid"><div>治理手段<b>${fmt(totals.methodScore)} / 165</b><small>制度建设、官僚执行、反馈纠错</small></div><div>治理结果<b>${fmt(totals.resultScore)} / 202</b><small>C1—C3状态账 + C4恢复、恶化与额外成本净调整</small></div><div>交接质量<b>${fmt(totals.handoffScore)} / 20</b><small>离场前后的行政承接与继承稳定</small></div></div><div class="second-item-equation">${fmt(totals.methodScore)} + ${fmt(totals.resultScore)} + ${fmt(totals.handoffScore)} = <strong>第二项 ${fmt(totals.totalScore)} / 387</strong></div><p class="subline">本项量表理论范围为 -27.5～387。0不是及格线、历史平均或“中性线”；公开名次只在当前主池中已完成第二项结算的人物之间比较。</p>`;
      summary.dataset.secondRenderKey = renderKey;
    }

    const page = document.querySelector(".net-detail-page");
    const intro = page?.querySelector(":scope > .panel");
    if (intro) {
      const main = Array.from(intro.querySelectorAll(":scope > p")).find(p => !p.classList.contains("subline"));
      const score = intro.querySelector(":scope > p.subline");
      setNodeText(main, "治国净收益分三层看：治理机器如何运转、本人统治窗口内社会实际处于什么状态、本人离场前后是否完成稳定交班。状态本身不等于全部由本人造成。");
      setNodeText(score, `第二项总分：${fmt(totals.totalScore)} / 387${rank ? `；${rank}` : ""}。下面先看正式结论，再展开到各指标。`);
    }
  }

  function ensureMethodGroup(totals) {
    const section = document.getElementById("net-group-method");
    if (!section) return;
    setNodeText(section.querySelector(":scope > h2"), "治理手段 · 制度与行政");
    addGroupIntro(section, "method", `这一组看国家机器怎么运转。A、B1、B2右侧显示的是正式方向指数，不是可直接相加的分数；它们按正式公式折算后，当前人物的治理手段小计为 ${fmt(totals.methodScore)} / 165。公开层只翻译正式方向档，不按总分比例另造强弱档。`);

    for (const label of ["A制度建设", "B1官僚治理", "B2反馈与约束"]) {
      const item = totals.method.get(label);
      const detail = metricDetail(section, label);
      markSourceLabel(detail, label);
      if (!item || !detail) continue;
      setMetricDisplay(
        detail,
        `${fmt(item.value)} 指数`,
        joinNote(`正式方向档：${methodBand(item)}`, boundaryHint(item))
      );
    }
  }

  function ensureC4Note(detail, value) {
    const body = detail?.querySelector(":scope > .net-metric-body");
    if (!body) return;
    let note = body.querySelector(":scope > .second-item-c4-note");
    if (!note) {
      note = document.createElement("p");
      note.className = "second-item-c4-note";
      body.insertBefore(note, body.firstChild);
    }
    if (value == null) {
      setNodeText(note, "这是净调整项，不与C1—C3使用同一满分尺度；具体正负构成以下方正式裁决为准。");
    } else if (value > 0) {
      setNodeText(note, "这是净调整项。正数表示恢复增量在扣除本人可归责恶化与额外民力、治理成本后仍有净加分；最终社会状态仍看C1—C3。");
    } else if (value < 0) {
      setNodeText(note, "这是净调整项。负数表示本人可归责恶化和/或额外民力、治理成本超过恢复增量，形成净扣分；具体是哪一部分造成负值，以下方正式裁决为准。");
    } else {
      setNodeText(note, "本调整项为0只表示这里的净调整为0：可能没有新增可计变化，也可能相关恶化已经在C1—C3消费而不再重复扣。0不等于“没有问题”。");
    }
  }

  function ensureFinanceGroup(totals) {
    const section = document.getElementById("net-group-finance");
    if (!section) return;
    setNodeText(section.querySelector(":scope > h2"), "治理结果 · 财政与民生");
    addGroupIntro(section, "finance", `C1—C3首先记录本人统治窗口内观察到的实际状态，不等于把全部好坏归给本人；接手基线、外生冲击以及本人造成或放大的变化，由正式裁决另行分账。三项满分分别为民生80、经济财政35、社会安全60，不能直接拿绝对数字比高低。C4另记恢复增量、本人可归责恶化与额外民力/治理成本的净调整。四项合计为 ${fmt(totals.resultScore)} / 202。`);

    for (const label of ["C1民生", "C2经济财政", "C3社会安全"]) {
      const item = totals.finance.get(label);
      const detail = metricDetail(section, label);
      markSourceLabel(detail, label);
      if (!item || !detail) continue;
      setMetricDisplay(
        detail,
        `${fmt(item.value)} / ${FINANCE_MAX[label]} 分`,
        joinNote(`状态分·满分${FINANCE_MAX[label]}`, stateMeta(item), "状态不等于本人全责", boundaryHint(item))
      );
    }

    const c4Item = totals.finance.get("C4恢复与成本");
    const c4Detail = metricDetail(section, ["C4恢复与成本", "C4恢复、恶化与额外成本调整"]);
    markSourceLabel(c4Detail, "C4恢复与成本");
    if (c4Item && c4Detail) {
      setMetricDisplay(
        c4Detail,
        `${signedFmt(c4Item.value)} 分`,
        joinNote("净调整项", "恢复 − 可归责恶化 − 额外成本", boundaryHint(c4Item)),
        "C4恢复、恶化与额外成本调整"
      );
      ensureC4Note(c4Detail, c4Item.value);
    }
  }

  function ensureHandoffGroup(totals) {
    const section = document.getElementById("net-group-handoff");
    if (!section) return;
    setNodeText(section.querySelector(":scope > h2"), "交接质量 · 政权交接");

    const d1Item = totals.handoff.get("D1继任行政连续性");
    const d3Item = totals.handoff.get("D3政权交接稳定");
    const d1 = finite(d1Item?.value);
    const d3 = finite(d3Item?.value);
    const cap = finite(totals.handoff.get("低侧封顶")?.value);
    const score = totals.handoffScore;

    let explanation = "D1、D3主要评价本人离场前后的终局交班：D1看旧国家机器有多少被接住，D3看继承过程是否稳定。任内更早发生过继承危机，不会自动把终局交接判低；关键看离场前是否真正修复并完成可运行的承接。";
    if ([d1, d3, cap, score].every(value => value != null)) {
      explanation = `行政连续性为 ${fmt(d1, 0)} / 5级，交接稳定为 ${fmt(d3, 0)} / 5级。两项主要评价本人离场前后的终局交班：D1看旧国家机器有多少被接住，D3看继承过程是否稳定；任内更早的继承危机若在离场前被真正修复，不会自动把终局交接判低。较弱一侧把本项最高分限制在 ${fmt(cap)}，最终交接得分 ${fmt(score)} / 20。`;
    }
    addGroupIntro(section, "handoff", explanation);

    const d1Detail = metricDetail(section, "D1继任行政连续性");
    const d3Detail = metricDetail(section, "D3政权交接稳定");
    markSourceLabel(d1Detail, "D1继任行政连续性");
    markSourceLabel(d3Detail, "D3政权交接稳定");
    setMetricDisplay(d1Detail, d1 == null ? "—" : `${fmt(d1, 0)} / 5 级`, joinNote("等级输入·行政承接", boundaryHint(d1Item)));
    setMetricDisplay(d3Detail, d3 == null ? "—" : `${fmt(d3, 0)} / 5 级`, joinNote("等级输入·终局继承", boundaryHint(d3Item)));

    for (const strong of section.querySelectorAll(".net-calculations .component strong")) {
      if (strong.textContent.trim() === "低侧封顶") setNodeText(strong, "交接短板上限");
    }
    for (const small of section.querySelectorAll(".net-calculations .component small")) {
      setNodeText(small, small.textContent.replace(/低侧封顶/g, "交接短板上限"));
    }
  }

  function formalBasisDetails(detail) {
    return Array.from(detail?.querySelectorAll(":scope > .net-metric-body > details") || []).find(block => {
      const text = block.querySelector(":scope > summary")?.textContent.trim() || "";
      return block.classList.contains("second-item-formal-basis") || text === "当前人物的完整裁决原文" || text === "正式裁决原文（未改写）";
    }) || null;
  }

  function restoreFormalBasis(section, itemMap) {
    if (!section) return;
    for (const [label, item] of itemMap.entries()) {
      const raw = String(item?.reader_full_basis || "").trim();
      if (!raw) continue;
      const detail = metricDetail(section, [label, label === "C4恢复与成本" ? "C4恢复、恶化与额外成本调整" : label]);
      if (!detail) continue;
      markSourceLabel(detail, label);
      const block = formalBasisDetails(detail);
      if (!block) continue;
      block.classList.add("second-item-formal-basis");
      const summary = block.querySelector(":scope > summary");
      setNodeText(summary, "正式裁决原文（未改写）");
      let content = block.querySelector(":scope > .second-item-formal-basis-content");
      if (!content) {
        for (const child of Array.from(block.children)) {
          if (child !== summary) child.remove();
        }
        content = document.createElement("div");
        content.className = "second-item-formal-basis-content";
        block.append(content);
      }
      const rawKey = raw;
      if (content.dataset.rawKey !== rawKey) {
        content.innerHTML = typeof prose === "function" ? prose(raw) : `<p class="prose"></p>`;
        if (typeof prose !== "function") setNodeText(content.querySelector("p"), raw);
        content.dataset.rawKey = rawKey;
      }
    }
  }

  function humanizeText(text) {
    return text
      .replace(/B1-distributed\/personnel M3/gi, "多责任官的人事配置强机制链")
      .replace(/distributed\/personnel M3/gi, "多责任官的人事配置强机制链")
      .replace(/central M2/gi, "中央有限机制链")
      .replace(/混负M3/g, "较强、持续的混合偏负机制链")
      .replace(/混合偏负M3/g, "较强、持续的混合偏负机制链")
      .replace(/核心M3链/g, "较强、持续或跨阶段的核心机制链")
      .replace(/正向M3/g, "较强、持续或跨阶段的正向机制链")
      .replace(/正M3/g, "较强、持续或跨阶段的正向机制链")
      .replace(/负向M3/g, "较强、持续或跨阶段的负向机制链")
      .replace(/负M3/g, "较强、持续或跨阶段的负向机制链")
      .replace(/M3链/g, "较强、持续或跨阶段的机制链")
      .replace(/\bM3\b/g, "较强机制链")
      .replace(/平衡M2/g, "影响大致相抵的有限机制链")
      .replace(/正向M2/g, "明确但有限的正向机制链")
      .replace(/正M2/g, "明确但有限的正向机制链")
      .replace(/负向M2/g, "明确但有限的负向机制链")
      .replace(/负M2/g, "明确但有限的负向机制链")
      .replace(/M2链/g, "有限机制链")
      .replace(/\bM2\b/g, "有限机制链")
      .replace(/\bS_end\b/g, "终点状态")
      .replace(/\bS0\b/g, "接手状态")
      .replace(/\bG0\b/g, "最低档")
      .replace(/\bG1\b/g, "较低档")
      .replace(/\bG2\b/g, "中低档")
      .replace(/\bG3\b/g, "中档")
      .replace(/\bG4\b/g, "较高档")
      .replace(/\bG5\b/g, "最高档")
      .replace(/\bL([0-3])\b/g, (_, level) => `低谷修正${level}级`)
      .replace(/\bH([0-5])\b/g, (_, level) => `交接第${level}级`)
      .replace(/\bDA([0-3])\b/g, (_, level) => `额外成本第${level}级`)
      .replace(/\bexternal_constraint\b/gi, "外部反馈约束")
      .replace(/\bmixed_positive\b/gi, "混合偏正")
      .replace(/\bcentral\b/gi, "中央")
      .replace(/\bdistributed\b/gi, "地方分布式")
      .replace(/\bcanonical\b/gi, "规范")
      .replace(/\bcore\b/gi, "核心")
      .replace(/\bsupport\b/gi, "辅助")
      .replace(/V2净值/g, "复核净值")
      .replace(/责任路线=NONE/g, "未进入本人军事归责路线");
  }

  function humanizeInternalLanguage() {
    const root = document.getElementById("net-major-body");
    if (!root) return;
    for (const body of root.querySelectorAll(".net-metric-body")) {
      const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
      const nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      for (const node of nodes) {
        const parent = node.parentElement;
        if (!parent || parent.closest(".second-item-formal-basis") || parent.closest(".net-audit-sources") || parent.closest(".sources") || parent.closest("a")) continue;
        const next = humanizeText(node.nodeValue || "");
        if (next !== node.nodeValue) node.nodeValue = next;
      }
    }
  }

  function groupKindFromSummary(summary) {
    const text = summary?.textContent.trim() || "";
    if (text.includes("制度与行政")) return "method";
    if (text.includes("财政与民生")) return "finance";
    if (text.includes("政权交接") || text.includes("交接质量")) return "handoff";
    return "";
  }

  function ensureRowSmall(span, text) {
    if (!span || !text) return;
    let note = span.querySelector(":scope > small.second-item-scale-note");
    if (!note) {
      note = document.createElement("small");
      note.className = "second-item-scale-note";
      span.append(note);
    }
    setNodeText(note, text);
  }

  function setRowLabel(span, label) {
    if (!span) return;
    const textNode = Array.from(span.childNodes).find(child => child.nodeType === Node.TEXT_NODE);
    if (textNode) textNode.nodeValue = `${label} `;
    else span.insertBefore(document.createTextNode(`${label} `), span.firstChild);
  }

  function formatCompactGroup(root, record, kind) {
    if (!root || !record?.net || !kind) return;
    const map = itemsFor(record, kind);
    for (const row of root.querySelectorAll(":scope .component")) {
      const span = row.querySelector(":scope > span");
      const value = row.querySelector(":scope > b");
      if (!span || !value) continue;
      const label = directText(span) || span.querySelector("strong")?.textContent.trim() || "";
      const item = map.get(label);

      if (kind === "method" && item && ["A制度建设", "B1官僚治理", "B2反馈与约束"].includes(label)) {
        setNodeText(value, `${fmt(item.value)} 指数`);
        ensureRowSmall(span, joinNote(`正式方向档：${methodBand(item)}`, boundaryHint(item)));
      } else if (kind === "finance" && item && FINANCE_MAX[label]) {
        setNodeText(value, `${fmt(item.value)} / ${FINANCE_MAX[label]} 分`);
        ensureRowSmall(span, joinNote(stateMeta(item), "状态不等于本人全责", boundaryHint(item)));
      } else if (kind === "finance" && item && label === "C4恢复与成本") {
        setRowLabel(span, "C4恢复、恶化与额外成本调整");
        setNodeText(value, `${signedFmt(item.value)} 分`);
        ensureRowSmall(span, joinNote("净调整项", "恢复 − 可归责恶化 − 额外成本", boundaryHint(item)));
      } else if (kind === "handoff" && item && label === "D1继任行政连续性") {
        setNodeText(value, `${fmt(item.value, 0)} / 5 级`);
        ensureRowSmall(span, joinNote("离场前后的行政承接", boundaryHint(item)));
      } else if (kind === "handoff" && item && label === "D3政权交接稳定") {
        setNodeText(value, `${fmt(item.value, 0)} / 5 级`);
        ensureRowSmall(span, joinNote("离场前后的终局继承", boundaryHint(item)));
      } else if (kind === "handoff" && label === "低侧封顶") {
        setRowLabel(span, "交接短板上限");
      } else if (kind === "handoff" && label === "交接得分") {
        setNodeText(value, `${fmt(item?.value)} / 20 分`);
      } else if (kind === "handoff" && label === "第二项合计") {
        setNodeText(value, `${fmt(item?.value)} / 387 分`);
      }
    }
  }

  function enhanceCompactGroups(record) {
    if (!record?.detail_loaded || !record?.net) return;
    for (const details of screenEl.querySelectorAll("details")) {
      const summary = details.querySelector(":scope > summary");
      const kind = groupKindFromSummary(summary);
      if (kind) formatCompactGroup(details, record, kind);
    }
  }

  function enhancePersonOverview(record) {
    if (!record?.detail_loaded || !record?.net || !location.hash.startsWith("#person/")) return;
    const panel = document.getElementById("person-outcome");
    if (!panel) return;
    const totals = secondTotals(record);
    for (const row of panel.querySelectorAll(":scope > .component")) {
      const span = row.querySelector("span");
      if (!span || !directText(span).startsWith("治国净收益")) continue;
      setNodeText(row.querySelector("b"), `${fmt(totals.totalScore)} / 387`);
      let rank = span.querySelector(":scope > .second-item-inline-rank");
      if (!rank) {
        rank = document.createElement("small");
        rank.className = "second-item-inline-rank";
        span.append(rank);
      }
      setNodeText(rank, rankText(totals));
    }
    enhanceCompactGroups(record);
  }

  function enhanceCompare(records) {
    if (records.length < 2 || records.some(record => !record?.detail_loaded)) return;
    const rows = Array.from(screenEl.querySelectorAll(".comparison tbody tr"));
    const secondRow = rows.find(row => row.cells?.[0]?.textContent.trim() === "治国净收益");
    if (secondRow) {
      records.forEach((record, index) => {
        const cell = secondRow.cells[index + 1];
        if (!cell || !record?.net) return;
        const totals = secondTotals(record);
        const key = `${totals.totalScore}|${rankText(totals)}`;
        if (cell.dataset.secondItemKey === key) return;
        cell.innerHTML = `<b>${fmt(totals.totalScore)} / 387</b>${rankText(totals) ? `<small class="second-item-inline-rank">${rankText(totals)}</small>` : ""}`;
        cell.dataset.secondItemKey = key;
      });
    }

    const structureRow = rows.find(row => row.cells?.[0]?.textContent.trim() === "构成与依据");
    if (structureRow) {
      records.forEach((record, index) => {
        const cell = structureRow.cells[index + 1];
        if (!cell || !record?.net) return;
        for (const details of cell.querySelectorAll("details")) {
          const kind = groupKindFromSummary(details.querySelector(":scope > summary"));
          if (kind) formatCompactGroup(details, record, kind);
        }
      });
    }
  }

  function enhanceNetSecond(record) {
    if (!record?.net) return;
    const totals = secondTotals(record);
    ensureLandingCard(record, totals);
    if (!location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) return;
    ensureSecondSummary(record, totals);
    restoreFormalBasis(document.getElementById("net-group-method"), totals.method);
    restoreFormalBasis(document.getElementById("net-group-finance"), totals.finance);
    restoreFormalBasis(document.getElementById("net-group-handoff"), totals.handoff);
    ensureMethodGroup(totals);
    ensureFinanceGroup(totals);
    ensureHandoffGroup(totals);
    humanizeInternalLanguage();
  }

  function enhance() {
    ensureStyles();
    const netRecord = recordForNetRoute();
    if (netRecord) enhanceNetSecond(netRecord);

    const personRecord = recordForPersonRoute();
    if (personRecord) enhancePersonOverview(personRecord);

    const compareRecords = recordsForCompareRoute();
    if (compareRecords.length) enhanceCompare(compareRecords);
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      enhance();
    });
  }

  new MutationObserver(schedule).observe(screenEl, {childList: true, subtree: true, characterData: true});
  window.addEventListener("hashchange", schedule);
  schedule();
})();
