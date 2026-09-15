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
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function fmt(value, digits = 1) {
    const number = finite(value);
    return number == null ? "—" : number.toFixed(digits);
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
      totalScore: finite(record?.net?.second_item_score ?? handoff.get("第二项合计")?.value),
    };
  }

  function ensureStyles() {
    if (document.getElementById("second-item-reading-style")) return;
    const style = document.createElement("style");
    style.id = "second-item-reading-style";
    style.textContent = `
      .second-item-reader-summary{border:1px solid var(--line);border-left:4px solid var(--green);border-radius:6px;padding:16px 18px;margin:0 0 18px;background:#f6f7f1}
      .second-item-reader-summary h2{font-size:21px;margin:0 0 8px}
      .second-item-total-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:12px 0}
      .second-item-total-grid div{border:1px solid var(--line);border-radius:5px;padding:10px 12px;background:#fcfbf7;font-size:12px}
      .second-item-total-grid b{display:block;font:21px Georgia,serif;color:var(--green);margin-top:3px}
      .second-item-equation{margin-top:12px;padding-top:11px;border-top:1px solid var(--line);font-size:14px}
      .second-item-equation strong{color:var(--green)}
      .second-item-scale-note{display:block;margin-top:4px;font-size:11px;color:var(--green);font-weight:600}
      .second-item-group-intro{margin:0 0 14px;padding:11px 13px;border-left:3px solid var(--gold);background:#f1eee6;font-size:13px;line-height:1.75}
      .second-item-card-breakdown{font-size:12px;color:var(--muted);line-height:1.65}
      .net-major-card.second-item-card .big{font-size:30px}
      @media(max-width:700px){.second-item-total-grid{grid-template-columns:1fr}}
    `;
    document.head.append(style);
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
      breakdown.textContent = `治理手段 ${fmt(totals.methodScore)}/165 · 治理结果 ${fmt(totals.resultScore)}/202 · 交接质量 ${fmt(totals.handoffScore)}/20`;
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

    const summary = document.createElement("section");
    summary.className = "second-item-reader-summary";
    summary.innerHTML = `<h2>先看三块总账</h2><p>第二项不是九个指标平铺相加，而是先形成三块小计，再汇总成治国净收益。</p><div class="second-item-total-grid"><div>治理手段<b>${fmt(totals.methodScore)} / 165</b><small>制度建设、官僚执行、反馈纠错</small></div><div>治理结果<b>${fmt(totals.resultScore)} / 202</b><small>民生、经济财政、社会安全、恢复与成本</small></div><div>交接质量<b>${fmt(totals.handoffScore)} / 20</b><small>行政连续性与交接稳定共同决定</small></div></div><div class="second-item-equation">${fmt(totals.methodScore)} + ${fmt(totals.resultScore)} + ${fmt(totals.handoffScore)} = <strong>第二项 ${fmt(totals.totalScore)} / 387</strong></div><p class="subline">本项量表理论范围为 -27.5～387。0不是及格线、历史平均或“中性线”；分值用于同一套合同下横向比较。</p>`;
    container.insertBefore(summary, container.firstChild);

    const page = document.querySelector(".net-detail-page");
    const intro = page?.querySelector(":scope > .panel");
    if (intro) {
      const main = Array.from(intro.querySelectorAll(":scope > p")).find(p => !p.classList.contains("subline"));
      const score = intro.querySelector(":scope > p.subline");
      if (main) main.textContent = "治国净收益分三层看：治理机器是否有效、治理后社会实际变成什么样、本人离场时能否把这套国家机器稳定交出去。";
      if (score) score.textContent = `第二项总分：${fmt(totals.totalScore)} / 387。下面先看三块总账，再展开到各指标。`;
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

  function ensureFinanceGroup(totals) {
    const section = document.getElementById("net-group-finance");
    if (!section) return;
    const heading = section.querySelector(":scope > h2");
    if (heading) heading.textContent = "治理结果 · 财政与民生";
    addGroupIntro(section, "finance", `C1—C3看本人统治主要阶段最终达到的民生、经济财政和社会安全状态；C4另看从接手状态到后来状态的恢复增量，并扣本人主动造成或放大的额外成本。正式账已做去重。四项在这里都是直接计分，合计 ${fmt(totals.resultScore)} / 202。`);
    addScaleNotes(section, "直接计分｜计入治理结果");
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
    let explanation = "D1、D3是交接等级输入，不是直接得分；最终按两者共同合成，并由较弱一侧限制上限。";
    if ([d1, d3, cap, score].every(value => value != null)) {
      explanation = `行政连续性为 ${fmt(d1, 0)} 级，交接稳定为 ${fmt(d3, 0)} 级；较弱一侧把本项最高分限制在 ${fmt(cap)}，因此最终交接得分为 ${fmt(score)} / 20。`;
    }
    addGroupIntro(section, "handoff", explanation);
    addScaleNotes(section, "等级输入｜合成后计入");

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
      .replace(/\bcore\b/gi, "核心")
      .replace(/\bsupport\b/gi, "辅助")
      .replace(/\bcanonical\b/gi, "规范");
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