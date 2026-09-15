"use strict";

(() => {
  const screenEl = document.getElementById("screen");
  if (!screenEl) return;

  const SECOND_ITEM_FORMAL_URL = "../docs/评分结算/净收益/第二项治国净收益/01-第二项治国净收益正式结算.json?raw=1";
  const METHOD_BAND_LABELS = {
    G0: "最低档",
    G1: "较低档",
    G2: "中低档",
    G3: "中档",
    G4: "较高档",
    G5: "最高档",
  };

  let scheduled = false;
  let secondPoolPromise = null;
  let officialSecondPool = null;

  function currentRecord() {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#net\/([^/?#]+)\/(?:all|second)(?:\/|$)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; }
    catch { return null; }
  }

  function itemsFor(record, key) {
    return new Map((record?.net?.component_details?.[key] || []).map(item => [item.label, item]));
  }

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

  function requestOfficialSecondPool() {
    if (officialSecondPool || secondPoolPromise) return;
    secondPoolPromise = fetch(SECOND_ITEM_FORMAL_URL, {cache: "no-store"})
      .then(response => {
        if (!response.ok) throw new Error(`second item settlement HTTP ${response.status}`);
        return response.json();
      })
      .then(payload => {
        const rows = Array.isArray(payload?.records) ? payload.records : [];
        const total = finite(payload?.record_count) ?? rows.length;
        const positions = new Map();
        for (const row of rows) {
          const rank = finite(row?.rank);
          const id = String(row?.ruler_id || "");
          if (id && rank != null) positions.set(id, {rank, total});
        }
        officialSecondPool = {positions, total};
      })
      .catch(() => {
        // Never fall back to the 184-person comprehensive reader pool: it is
        // not the same population as the formal 185-person second-item pool.
        officialSecondPool = {positions: new Map(), total: null};
      })
      .finally(() => {
        secondPoolPromise = null;
        schedule();
      });
  }

  function secondPoolPosition(record) {
    const id = String(record?.ruler_id || "");
    const position = officialSecondPool?.positions?.get(id) || null;
    if (!officialSecondPool) requestOfficialSecondPool();
    return position;
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

  function formalMethodBand(item) {
    const match = String(item?.grade || "").match(/\bG([0-5])\b/);
    return match ? METHOD_BAND_LABELS[`G${match[1]}`] : "未标明正式档";
  }

  function personConclusion(totals) {
    const a = formalMethodBand(totals.method.get("A制度建设"));
    const b1 = formalMethodBand(totals.method.get("B1官僚治理"));
    const b2 = formalMethodBand(totals.method.get("B2反馈与约束"));
    return `三块总账：治理手段 ${fmt(totals.methodScore)} / 165，治理结果 ${fmt(totals.resultScore)} / 202，交接质量 ${fmt(totals.handoffScore)} / 20。制度行政正式档：制度建设${a}、官僚治理${b1}、反馈约束${b2}；C1—C3首先记录统治窗口内的实际状态，C4净调整 ${signedFmt(totals.c4)}。`;
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
      .second-item-card-breakdown{font-size:12px;color:var(--muted);line-height:1.65}
      .net-major-card.second-item-card .big{font-size:30px}
      @media(max-width:700px){.second-item-total-grid{grid-template-columns:1fr}}
    `;
    document.head.append(style);
  }

  function rankText(totals) {
    return totals.pool ? `第二项正式结算第 ${fmt(totals.pool.rank, 0)} / ${fmt(totals.pool.total, 0)}` : "";
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
      totals.methodScore, totals.resultScore, totals.handoffScore, totals.totalScore, totals.c4,
      rank,
      formalMethodBand(totals.method.get("A制度建设")),
      formalMethodBand(totals.method.get("B1官僚治理")),
      formalMethodBand(totals.method.get("B2反馈与约束")),
    ].join("|");
    if (summary.dataset.secondRenderKey !== renderKey) {
      summary.innerHTML = `<h2>先看这个人的治国结论</h2><p class="second-item-person-conclusion">${personConclusion(totals)}</p>${rank ? `<span class="second-item-rank">${rank}</span>` : ""}<div class="second-item-total-grid"><div>治理手段<b>${fmt(totals.methodScore)} / 165</b><small>制度建设、官僚执行、反馈纠错</small></div><div>治理结果<b>${fmt(totals.resultScore)} / 202</b><small>C1—C3状态账 + C4恢复、恶化与额外成本净调整</small></div><div>交接质量<b>${fmt(totals.handoffScore)} / 20</b><small>离场前后的行政承接与继承稳定</small></div></div><div class="second-item-equation">${fmt(totals.methodScore)} + ${fmt(totals.resultScore)} + ${fmt(totals.handoffScore)} = <strong>第二项 ${fmt(totals.totalScore)} / 387</strong></div><p class="subline">本项量表理论范围为 -27.5～387。0不是及格线、历史平均或“中性线”；名次直接读取第二项185人正式结算，不用综合阅读主池重新推算。</p>`;
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
      wanted.has(detail.querySelector(":scope > summary strong")?.textContent.trim())
    ) || null;
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

  function addScaleNotes(section, text) {
    for (const detail of section?.querySelectorAll(":scope > .net-metric-detail") || []) {
      const span = detail.querySelector(":scope > summary > span");
      if (!span) continue;
      let note = span.querySelector(":scope > .second-item-scale-note");
      if (!note) {
        note = document.createElement("small");
        note.className = "second-item-scale-note";
        span.append(note);
      }
      setNodeText(note, text);
    }
  }

  function ensureMethodGroup(totals) {
    const section = document.getElementById("net-group-method");
    if (!section) return;
    setNodeText(section.querySelector(":scope > h2"), "治理手段 · 制度与行政");
    addGroupIntro(section, "method", `这一组看国家机器怎么运转。A、B1、B2右侧显示的是正式方向指数，不是可直接相加的分数；它们按正式公式折算后，当前人物的治理手段小计为 ${fmt(totals.methodScore)} / 165。公开结论只翻译正式G档，不再按总分比例另造“强弱档”。`);
    addScaleNotes(section, "方向指数｜按正式档与公式折算后计入");
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

    setMetricDisplay(metricDetail(section, "C1民生"), `${fmt(totals.c1)} / 80 分`, "状态分｜满分80｜状态不等于本人全责");
    setMetricDisplay(metricDetail(section, "C2经济财政"), `${fmt(totals.c2)} / 35 分`, "状态分｜满分35｜状态不等于本人全责");
    setMetricDisplay(metricDetail(section, "C3社会安全"), `${fmt(totals.c3)} / 60 分`, "状态分｜满分60｜状态不等于本人全责");

    const c4Detail = metricDetail(section, ["C4恢复与成本", "C4恢复、恶化与额外成本调整"]);
    setMetricDisplay(c4Detail, `${signedFmt(totals.c4)} 分`, "净调整项｜恢复 − 可归责恶化 − 额外成本", "C4恢复、恶化与额外成本调整");
    ensureC4Note(c4Detail, totals.c4);
  }

  function ensureHandoffGroup(totals) {
    const section = document.getElementById("net-group-handoff");
    if (!section) return;
    setNodeText(section.querySelector(":scope > h2"), "交接质量 · 政权交接");

    const d1 = finite(totals.handoff.get("D1继任行政连续性")?.value);
    const d3 = finite(totals.handoff.get("D3政权交接稳定")?.value);
    const cap = finite(totals.handoff.get("低侧封顶")?.value);
    const score = totals.handoffScore;

    let explanation = "D1、D3主要评价本人离场前后的终局交班：D1看旧国家机器有多少被接住，D3看继承过程是否稳定。任内更早发生过继承危机，不会自动把终局交接判低；关键看离场前是否真正修复并完成可运行的承接。";
    if ([d1, d3, cap, score].every(value => value != null)) {
      explanation = `行政连续性为 ${fmt(d1, 0)} / 5级，交接稳定为 ${fmt(d3, 0)} / 5级。两项主要评价本人离场前后的终局交班：D1看旧国家机器有多少被接住，D3看继承过程是否稳定；任内更早的继承危机若在离场前被真正修复，不会自动把终局交接判低。较弱一侧把本项最高分限制在 ${fmt(cap)}，最终交接得分 ${fmt(score)} / 20。`;
    }
    addGroupIntro(section, "handoff", explanation);

    setMetricDisplay(metricDetail(section, "D1继任行政连续性"), d1 == null ? "—" : `${fmt(d1, 0)} / 5 级`, "等级输入｜离场前后的行政承接");
    setMetricDisplay(metricDetail(section, "D3政权交接稳定"), d3 == null ? "—" : `${fmt(d3, 0)} / 5 级`, "等级输入｜离场前后的终局继承");

    for (const strong of section.querySelectorAll(".net-calculations .component strong")) {
      if (strong.textContent.trim() === "低侧封顶") setNodeText(strong, "交接短板上限");
    }
    for (const small of section.querySelectorAll(".net-calculations .component small")) {
      setNodeText(small, small.textContent.replace(/低侧封顶/g, "交接短板上限"));
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
      .replace(/\bC1-([0-5])\b/g, (_, level) => `民生第${level}档`)
      .replace(/\bC2-([0-5])\b/g, (_, level) => `经济财政第${level}档`)
      .replace(/\bC3-([0-5])\b/g, (_, level) => `社会安全第${level}档`)
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
      if (body.dataset.secondLanguage === "done") continue;
      const walker = document.createTreeWalker(body, NodeFilter.SHOW_TEXT);
      const nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      for (const node of nodes) {
        const parent = node.parentElement;
        if (!parent || parent.closest(".net-audit-sources") || parent.closest(".sources") || parent.closest("a")) continue;
        const next = humanizeText(node.nodeValue || "");
        if (next !== node.nodeValue) node.nodeValue = next;
      }
      body.dataset.secondLanguage = "done";
    }
  }

  function enhance() {
    const record = currentRecord();
    if (!record?.net) return;
    ensureStyles();
    const totals = secondTotals(record);
    ensureLandingCard(record, totals);
    if (!location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) return;
    ensureSecondSummary(record, totals);
    ensureMethodGroup(totals);
    ensureFinanceGroup(totals);
    ensureHandoffGroup(totals);
    humanizeInternalLanguage();
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      enhance();
    });
  }

  new MutationObserver(schedule).observe(screenEl, {childList: true, subtree: true});
  window.addEventListener("hashchange", schedule);
  schedule();
})();
