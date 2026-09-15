"use strict";

(() => {
  const screenEl = document.getElementById("screen");
  if (!screenEl) return;
  let scheduled = false;

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

  function secondPoolPosition(record) {
    if (typeof byId === "undefined") return null;
    const score = finite(record?.net?.second_item_score);
    if (score == null) return null;
    const eligible = Array.from(byId.values())
      .map(item => ({id: String(item?.ruler_id || ""), score: finite(item?.net?.second_item_score)}))
      .filter(item => item.score != null);
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

  function scorePhrase(score, max, phrases) {
    const value = finite(score);
    if (value == null) return phrases[2];
    const ratio = value / max;
    if (ratio >= 0.75) return phrases[4];
    if (ratio >= 0.55) return phrases[3];
    if (ratio >= 0.35) return phrases[2];
    if (ratio >= 0.18) return phrases[1];
    return phrases[0];
  }

  function personConclusion(totals) {
    const method = scorePhrase(totals.methodScore, 165, ["运转很弱", "运转偏弱", "表现中等", "运转较强", "运转很强"]);
    const result = scorePhrase(totals.resultScore, 202, ["很差", "偏弱", "中等", "较好", "很好"]);
    const handoffRatio = totals.handoffScore == null ? null : totals.handoffScore / 20;
    const handoff = handoffRatio == null
      ? "交接情况暂无法概括"
      : handoffRatio >= 0.8
        ? "离场交接稳"
        : handoffRatio >= 0.5
          ? "交接总体尚可"
          : handoffRatio > 0
            ? "交接存在明显短板"
            : "基本未完成有效交接";
    let c4 = "";
    if (totals.c4 != null && totals.c4 >= 8) c4 = `；另有明显恢复增量（${signedFmt(totals.c4)}）`;
    else if (totals.c4 != null && totals.c4 <= -4) c4 = `；额外治理或民力成本又拖累 ${fmt(Math.abs(totals.c4))} 分`;
    return `国家机器${method}，治理后的社会状态${result}；${handoff}${c4}。`;
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
    return totals.pool ? `正式池第 ${totals.pool.rank} / ${totals.pool.total}` : "";
  }

  function ensureLandingCard(record, totals) {
    if (!location.hash.match(/^#net\/[^/?#]+\/(?:all)?$/)) return;
    const card = Array.from(document.querySelectorAll(".net-major-card")).find(item =>
      item.getAttribute("href")?.includes("/second")
    );
    if (!card || card.dataset.secondItemReader === "done") return;
    card.classList.add("second-item-card");
    const big = card.querySelector(".big");
    if (big && totals.totalScore != null) big.textContent = `${fmt(totals.totalScore)} / 387`;
    const description = Array.from(card.querySelectorAll(":scope > p")).find(p =>
      !p.classList.contains("sources") && !p.classList.contains("second-item-card-breakdown")
    );
    if (description) description.textContent = "先看治理机器怎么运转、治理后社会处于什么状态，再看离场时是否把国家稳稳交出去。";
    if ([totals.methodScore, totals.resultScore, totals.handoffScore].every(value => value != null)) {
      const breakdown = document.createElement("p");
      breakdown.className = "second-item-card-breakdown";
      const rank = rankText(totals);
      breakdown.textContent = `${rank ? `${rank} · ` : ""}治理手段 ${fmt(totals.methodScore)}/165 · 治理结果 ${fmt(totals.resultScore)}/202 · 交接质量 ${fmt(totals.handoffScore)}/20`;
      const sources = card.querySelector(":scope > p.sources");
      card.insertBefore(breakdown, sources || null);
    }
    card.dataset.secondItemReader = "done";
  }

  function ensureSecondSummary(record, totals) {
    if (!location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) return;
    const container = document.getElementById("net-major-body");
    if (!container || container.querySelector(":scope > .second-item-reader-summary")) return;
    if ([totals.methodScore, totals.resultScore, totals.handoffScore, totals.totalScore].some(value => value == null)) return;

    const rank = rankText(totals);
    const summary = document.createElement("section");
    summary.className = "second-item-reader-summary";
    summary.innerHTML = `<h2>先看这个人的治国结论</h2><p class="second-item-person-conclusion">${personConclusion(totals)}</p>${rank ? `<span class="second-item-rank">${rank}</span>` : ""}<div class="second-item-total-grid"><div>治理手段<b>${fmt(totals.methodScore)} / 165</b><small>制度建设、官僚执行、反馈纠错</small></div><div>治理结果<b>${fmt(totals.resultScore)} / 202</b><small>民生、经济财政、社会安全、恢复与额外成本</small></div><div>交接质量<b>${fmt(totals.handoffScore)} / 20</b><small>行政连续性与交接稳定共同决定</small></div></div><div class="second-item-equation">${fmt(totals.methodScore)} + ${fmt(totals.resultScore)} + ${fmt(totals.handoffScore)} = <strong>第二项 ${fmt(totals.totalScore)} / 387</strong></div><p class="subline">本项量表理论范围为 -27.5～387。0不是及格线、历史平均或“中性线”；优先结合正式池名次理解高低，再下钻到各指标。</p>`;
    container.insertBefore(summary, container.firstChild);

    const page = document.querySelector(".net-detail-page");
    const intro = page?.querySelector(":scope > .panel");
    if (intro) {
      const main = Array.from(intro.querySelectorAll(":scope > p")).find(p => !p.classList.contains("subline"));
      const score = intro.querySelector(":scope > p.subline");
      if (main) main.textContent = "治国净收益分三层看：治理机器是否有效、治理后社会实际变成什么样、本人离场时能否把这套国家机器稳定交出去。";
      if (score) score.textContent = `第二项总分：${fmt(totals.totalScore)} / 387${rank ? `；${rank}` : ""}。下面先看人物结论，再展开到各指标。`;
    }
  }

  function addGroupIntro(section, key, text) {
    if (!section || section.querySelector(`:scope > [data-second-intro="${key}"]`)) return;
    const intro = document.createElement("p");
    intro.className = "second-item-group-intro";
    intro.dataset.secondIntro = key;
    intro.textContent = text;
    const heading = section.querySelector(":scope > h2");
    if (heading?.nextSibling) section.insertBefore(intro, heading.nextSibling);
    else section.append(intro);
  }

  function metricDetail(section, label) {
    return Array.from(section?.querySelectorAll(":scope > .net-metric-detail") || []).find(detail =>
      detail.querySelector(":scope > summary strong")?.textContent.trim() === label
    ) || null;
  }

  function setMetricDisplay(detail, valueText, noteText, titleText = "") {
    if (!detail) return;
    const summary = detail.querySelector(":scope > summary");
    const strong = summary?.querySelector("strong");
    const value = summary?.querySelector(":scope > b");
    const span = summary?.querySelector(":scope > span");
    if (titleText && strong) strong.textContent = titleText;
    if (value) value.textContent = valueText;
    if (span) {
      let note = span.querySelector(":scope > .second-item-scale-note");
      if (!note) {
        note = document.createElement("small");
        note.className = "second-item-scale-note";
        span.append(note);
      }
      note.textContent = noteText;
    }
  }

  function addScaleNotes(section, text) {
    for (const detail of section?.querySelectorAll(":scope > .net-metric-detail") || []) {
      const span = detail.querySelector(":scope > summary > span");
      if (!span || span.querySelector(":scope > .second-item-scale-note")) continue;
      const note = document.createElement("small");
      note.className = "second-item-scale-note";
      note.textContent = text;
      span.append(note);
    }
  }

  function ensureMethodGroup(totals) {
    const section = document.getElementById("net-group-method");
    if (!section) return;
    const heading = section.querySelector(":scope > h2");
    if (heading) heading.textContent = "治理手段 · 制度与行政";
    addGroupIntro(section, "method", `这一组看国家机器怎么运转。A、B1、B2右侧显示的是方向指数，不是可直接相加的分数；它们按正式公式折算后，当前人物的治理手段小计为 ${fmt(totals.methodScore)} / 165。`);
    addScaleNotes(section, "方向指数｜折算后计入");
  }

  function ensureC4Note(detail, value) {
    const body = detail?.querySelector(":scope > .net-metric-body");
    if (!body || body.querySelector(":scope > .second-item-c4-note")) return;
    const note = document.createElement("p");
    note.className = "second-item-c4-note";
    if (value == null) {
      note.textContent = "这是调整项，不与C1—C3使用同一满分尺度。";
    } else if (value > 0) {
      note.textContent = "这是调整项。正数表示相对接手基线保留了恢复增量；仍要结合C1—C3判断治理后的最终状态。";
    } else if (value < 0) {
      note.textContent = "这是调整项。负数表示本人可归责的恶化或额外民力、治理成本在这里继续扣分；不代表C1—C3状态分本身为负。";
    } else {
      note.textContent = "本项为0只表示这里没有新增净加分或新增净扣分；已经在C1—C3消费的恶化不会重复扣，因此0不等于“没有问题”。";
    }
    body.insertBefore(note, body.firstChild);
  }

  function ensureFinanceGroup(totals) {
    const section = document.getElementById("net-group-finance");
    if (!section) return;
    const heading = section.querySelector(":scope > h2");
    if (heading) heading.textContent = "治理结果 · 财政与民生";
    addGroupIntro(section, "finance", `C1—C3是三种不同满分的状态分：民生80、经济财政35、社会安全60；不能直接拿绝对数字比高低。C4不是第四个状态分，而是“恢复增量与额外成本”调整项。四项合计为 ${fmt(totals.resultScore)} / 202。`);

    setMetricDisplay(metricDetail(section, "C1民生"), `${fmt(totals.c1)} / 80 分`, "状态分｜满分80");
    setMetricDisplay(metricDetail(section, "C2经济财政"), `${fmt(totals.c2)} / 35 分`, "状态分｜满分35");
    setMetricDisplay(metricDetail(section, "C3社会安全"), `${fmt(totals.c3)} / 60 分`, "状态分｜满分60");
    const c4Detail = metricDetail(section, "C4恢复与成本");
    setMetricDisplay(c4Detail, `${signedFmt(totals.c4)} 分`, "调整项｜正数加分，负数扣分，0不代表无问题", "C4恢复增量与额外成本调整");
    ensureC4Note(c4Detail, totals.c4);
  }

  function ensureHandoffGroup(totals) {
    const section = document.getElementById("net-group-handoff");
    if (!section) return;
    const heading = section.querySelector(":scope > h2");
    if (heading) heading.textContent = "交接质量 · 政权交接";
    const d1 = finite(totals.handoff.get("D1继任行政连续性")?.value);
    const d3 = finite(totals.handoff.get("D3政权交接稳定")?.value);
    const cap = finite(totals.handoff.get("低侧封顶")?.value);
    const score = totals.handoffScore;
    let explanation = "行政连续性评价旧国家机器还有多少被接住；交接稳定评价本人是否完成稳定继承。前者即使留有残余分，也不代表交班成功。两项都是0—5级输入，最终共同合成20分交接质量。";
    if ([d1, d3, cap, score].every(value => value != null)) {
      explanation = `行政连续性为 ${fmt(d1, 0)} / 5级，交接稳定为 ${fmt(d3, 0)} / 5级。行政连续性看旧国家机器还有多少被接住，交接稳定看本人是否完成稳定继承；前者有残余分不等于交班成功。较弱一侧把本项最高分限制在 ${fmt(cap)}，最终交接得分 ${fmt(score)} / 20。`;
    }
    addGroupIntro(section, "handoff", explanation);

    setMetricDisplay(metricDetail(section, "D1继任行政连续性"), d1 == null ? "—" : `${fmt(d1, 0)} / 5 级`, "等级输入｜行政机器承接");
    setMetricDisplay(metricDetail(section, "D3政权交接稳定"), d3 == null ? "—" : `${fmt(d3, 0)} / 5 级`, "等级输入｜继承过程稳定");

    for (const strong of section.querySelectorAll(".net-calculations .component strong")) {
      if (strong.textContent.trim() === "低侧封顶") strong.textContent = "交接短板上限";
    }
    for (const small of section.querySelectorAll(".net-calculations .component small")) {
      small.textContent = small.textContent.replace(/低侧封顶/g, "交接短板上限");
    }
  }

  function humanizeText(text) {
    return text
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
