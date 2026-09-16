"use strict";

(() => {
  const screenEl = document.getElementById("screen");
  if (!screenEl) return;

  const firstDescriptions = {
    landing: "只适用于建国、复国或统一创业主链。先看统一成果、创业难度与效率、组织整合、本人统帅，再扣战争成本；第一项净分最后折成总榜附加分。",
    detail: "先看这个人在创业／统一主链中实际留下了什么，再看完成难度、组织方式、本人军事责任和战争成本。规则代码与公式放在各块后面。",
  };
  const firstLabels = {
    "A统一贡献": "统一成果",
    "B1创业难度与效率": "创业难度与效率",
    "B2组织与整合": "组织整合",
    "C军事统帅与战争解题": "本人统帅",
  };
  let commanderIndexPromise = null;
  let scheduled = false;

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    })[c]);
  }

  function formatNumber(value) {
    return typeof value === "number" && Number.isFinite(value) ? value.toFixed(2) : "—";
  }

  function setText(node, value) {
    if (node && node.textContent !== value) node.textContent = value;
  }

  function currentRecord() {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#(?:person|net)\/([^/?#]+)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; }
    catch { return null; }
  }

  function firstItems(record) {
    return new Map((record?.net?.component_details?.first || []).map(item => [item.label, item]));
  }

  function ensureStyles() {
    if (document.getElementById("first-item-reading-style")) return;
    const style = document.createElement("style");
    style.id = "first-item-reading-style";
    style.textContent = `
      .first-item-reader-summary{border:1px solid var(--line);border-left:4px solid var(--green);border-radius:6px;padding:16px 18px;margin:0 0 18px;background:#f6f7f1}
      .first-item-reader-summary h2{font-size:21px;margin:0 0 8px}
      .first-item-reader-summary .first-item-outcome{font-size:14px;line-height:1.85;margin:8px 0 14px}
      .first-item-score-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:12px 0}
      .first-item-score-grid div{border:1px solid var(--line);border-radius:5px;padding:9px 10px;background:#fcfbf7;font-size:12px}
      .first-item-score-grid b{display:block;font:19px Georgia,serif;color:var(--green);margin-top:2px}
      .first-item-flow{margin-top:12px;padding-top:10px;border-top:1px solid var(--line);font-size:14px}
      .first-item-flow strong{color:var(--green)}
      .first-item-rules{margin-top:12px}
      .first-item-military-links{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 8px;padding:12px;background:#eef1ea;border-radius:5px}
      .first-item-military-links a{font-size:13px}
      .net-major-card.first-item-card .big{font-size:28px}
      @media(max-width:700px){.first-item-score-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.first-item-military-links{display:grid}}
    `;
    document.head.append(style);
  }

  function ensureFirstOverview(record) {
    const panel = document.getElementById("person-outcome");
    if (!panel || !record?.net) return;
    const row = Array.from(panel.querySelectorAll(":scope > .component")).find(item =>
      item.textContent.includes("奠基与统一")
    );
    if (!row || row.dataset.firstItemReader === "done") return;

    let anchor = row.querySelector("a");
    if (!anchor) {
      anchor = document.createElement("a");
      anchor.className = "net-overview-jump";
      anchor.href = `#net/${encodeURIComponent(record.ruler_id)}/first`;
      while (row.firstChild) anchor.append(row.firstChild);
      row.append(anchor);
    }
    const label = anchor.querySelector("span");
    const score = anchor.querySelector("b");
    if (record.net.first_item_status === "APPLICABLE") {
      if (label) label.innerHTML = `奠基与统一<small>第一项净分 S1：${formatNumber(record.net.first_item_raw_score)} / 240 → 总榜附加：+${formatNumber(record.net.first_item_add_on)}</small><small>查看计分逻辑 →</small>`;
      setText(score, `+${formatNumber(record.net.first_item_add_on)}`);
    } else {
      if (label) label.innerHTML = `奠基与统一<small>本项不适用；总榜附加为 0，不代表能力失败</small><small>查看适用边界 →</small>`;
      setText(score, "0.00");
    }
    row.dataset.firstItemReader = "done";
  }

  function ensureLandingCard(record) {
    if (!location.hash.match(/^#net\/[^/?#]+\/(?:all)?$/)) return;
    const card = Array.from(document.querySelectorAll(".net-major-card")).find(item =>
      item.getAttribute("href")?.includes("/first")
    );
    if (!card || card.dataset.firstItemReader === "done") return;
    card.classList.add("first-item-card");
    const big = card.querySelector(".big");
    const subline = card.querySelector(".subline");
    const paragraphs = Array.from(card.querySelectorAll("p"));
    const description = paragraphs.find(p => !p.classList.contains("subline") && !p.classList.contains("sources"));
    if (record.net.first_item_status === "APPLICABLE") {
      setText(big, `S1 ${formatNumber(record.net.first_item_raw_score)} / 240`);
      setText(subline, `总榜附加：+${formatNumber(record.net.first_item_add_on)}`);
    } else {
      setText(big, "不适用");
      setText(subline, "本项不参与总榜附加；不代表能力失败。");
    }
    setText(description, firstDescriptions.landing);
    card.dataset.firstItemReader = "done";
  }

  function extractOutcome() {
    const card = document.getElementById("net-first-a");
    const body = card?.querySelector(".net-metric-body");
    if (!body) return "";
    const label = Array.from(body.querySelectorAll(":scope > .label")).find(item =>
      ["当前人物的U怎么来", "当前人物实际留下了什么"].includes(item.textContent.trim())
    );
    if (!label) return "";
    const parts = [];
    let node = label.nextElementSibling;
    while (node && !node.classList.contains("label") && node.tagName !== "DETAILS") {
      const text = node.textContent.replace(/\s+/g, " ").trim();
      if (text) parts.push(text);
      node = node.nextElementSibling;
    }
    const text = parts.join(" ");
    return text.length > 240 ? `${text.slice(0, 238)}…` : text;
  }

  function ensureFirstSummary(record) {
    const section = document.querySelector("#net-major-body > .panel.net-detail-group");
    if (!section || section.querySelector(":scope > .first-item-reader-summary")) return;
    const items = firstItems(record);
    if (!items.size) return;
    const scores = [
      ["A统一贡献", 120],
      ["B1创业难度与效率", 50],
      ["B2组织与整合", 30],
      ["C军事统帅与战争解题", 40],
    ];
    if (scores.some(([key]) => items.get(key)?.value == null)) return;

    const gross = items.get("四轴合计")?.value ?? scores.reduce((sum, [key]) => sum + Number(items.get(key)?.value || 0), 0);
    const cost = Number(items.get("军事成本扣分")?.value || 0);
    const net = items.get("第一项净分")?.value ?? record.net.first_item_raw_score;
    const addOn = items.get("附加F")?.value ?? record.net.first_item_add_on;
    const outcome = extractOutcome() || "主链成果请看下方“统一成果”卡；这里先把结论、成本和总榜折算放在一起。";
    const summary = document.createElement("div");
    summary.className = "first-item-reader-summary";
    summary.innerHTML = `<h2>先看结论</h2><div class="label">这个人实际做成了什么</div><p class="first-item-outcome">${escapeHtml(outcome)}</p><div class="first-item-score-grid">${scores.map(([key, max]) => `<div>${escapeHtml(firstLabels[key])}<b>${formatNumber(items.get(key).value)} / ${max}</b></div>`).join("")}</div><div class="first-item-flow">四块合计 ${formatNumber(gross)} − 军事成本 ${formatNumber(cost)} = <strong>第一项净分 S1 ${formatNumber(net)} / 240</strong> → 总榜附加 <strong>+${formatNumber(addOn)}</strong></div><p class="subline">下面先讲当前人物，再讲规则与公式；不需要先理解 A / B1 / B2 / C 才能读这页。</p>`;
    section.insertBefore(summary, section.firstChild);
  }

  function renameDirectLabel(body, from, to) {
    const label = Array.from(body.querySelectorAll(":scope > .label")).find(item => item.textContent.trim() === from);
    if (label) setText(label, to);
  }

  function moveRuleBlocks(card, labels) {
    const body = card?.querySelector(".net-metric-body");
    if (!body || body.dataset.readerRulesMoved === "done") return;
    const nodes = [];
    for (const text of labels) {
      const label = Array.from(body.children).find(item => item.classList?.contains("label") && item.textContent.trim() === text);
      if (!label) continue;
      nodes.push(label);
      let node = label.nextElementSibling;
      while (node && !node.classList.contains("label") && node.tagName !== "DETAILS") {
        const next = node.nextElementSibling;
        nodes.push(node);
        node = next;
      }
    }
    if (nodes.length) {
      const rules = document.createElement("details");
      rules.className = "first-item-rules";
      const summary = document.createElement("summary");
      summary.textContent = "这个指标看什么？";
      rules.append(summary);
      nodes.forEach(node => rules.append(node));
      const formula = Array.from(body.children).find(item => item.tagName === "DETAILS" && !item.classList.contains("net-audit-sources"));
      body.insertBefore(rules, formula || body.querySelector(":scope > .net-audit-sources") || null);
    }
    body.dataset.readerRulesMoved = "done";
  }

  function humanizeFirstCards() {
    const a = document.getElementById("net-first-a");
    const b1 = document.getElementById("net-first-b1");
    const b2 = document.getElementById("net-first-b2");
    const c = document.getElementById("net-first-c");
    const titles = [
      [a, "统一成果（A）"],
      [b1, "创业难度与效率（B1）"],
      [b2, "组织整合（B2）"],
      [c, "本人统帅与战争解题（C）"],
    ];
    for (const [card, title] of titles) {
      const strong = card?.querySelector(":scope > summary strong");
      if (strong && !strong.dataset.readerTitle) {
        setText(strong, title);
        strong.dataset.readerTitle = "done";
      }
    }
    const aBody = a?.querySelector(".net-metric-body");
    const b1Body = b1?.querySelector(".net-metric-body");
    if (aBody) renameDirectLabel(aBody, "当前人物的U怎么来", "当前人物实际留下了什么");
    if (b1Body) {
      renameDirectLabel(b1Body, "起点怎么判", "当前人物的起点");
      renameDirectLabel(b1Body, "对手怎么判", "当前人物面对的对手");
      renameDirectLabel(b1Body, "效率怎么判", "完成效率");
    }
    moveRuleBlocks(a, ["A是什么意思", "U是什么意思"]);
    moveRuleBlocks(b1, ["B1是什么意思", "三个变量怎么读"]);
    moveRuleBlocks(b2, ["B2是什么意思", "L档怎么换分"]);
    moveRuleBlocks(c, ["C是什么意思"]);
  }

  function loadCommanderIndex() {
    if (!commanderIndexPromise) {
      commanderIndexPromise = fetch("data/military/commanders-index.json", {cache: "no-cache"})
        .then(response => response.ok ? response.json() : null)
        .catch(() => null);
    }
    return commanderIndexPromise;
  }

  async function resolveCommanderHref(name) {
    const payload = await loadCommanderIndex();
    const rows = Array.isArray(payload?.records) ? payload.records : [];
    const exact = rows.filter(row => row.name === name || (Array.isArray(row.aliases) && row.aliases.includes(name)));
    return exact.length ? `military.html#commander=${encodeURIComponent(exact[0].profile_ref)}` : "";
  }

  function ensureMilitaryLinks(record) {
    const body = document.querySelector("#net-first-c .net-metric-body");
    if (!body || body.querySelector(":scope > .first-item-military-links")) return;
    const box = document.createElement("div");
    box.className = "first-item-military-links";
    const direct = document.createElement("a");
    direct.href = `military.html#search=${encodeURIComponent(record.ruler_name)}`;
    direct.textContent = "查看统帅档案（按当前人物筛选） →";
    const battles = document.createElement("a");
    battles.href = `military.html#search=${encodeURIComponent(record.ruler_name)}`;
    battles.textContent = "查看相关战役与个人责任 →";
    box.append(direct, battles);
    const formula = Array.from(body.children).find(item => item.tagName === "DETAILS" && !item.classList.contains("net-audit-sources"));
    body.insertBefore(box, formula || body.querySelector(":scope > .net-audit-sources") || null);
    resolveCommanderHref(record.ruler_name).then(href => {
      if (!href || !direct.isConnected) return;
      direct.href = href;
      setText(direct, "直接打开统帅档案 →");
    });
  }

  function rewriteFirstIntro(record) {
    if (!location.hash.match(/^#net\/[^/?#]+\/first(?:\/|$)/)) return;
    const page = document.querySelector(".net-detail-page");
    const intro = page?.querySelector(":scope > .panel");
    if (intro) {
      const main = Array.from(intro.querySelectorAll(":scope > p")).find(p => !p.classList.contains("subline"));
      const score = intro.querySelector(":scope > p.subline");
      setText(main, firstDescriptions.detail);
      const scoreText = record.net.first_item_status === "APPLICABLE"
        ? `第一项净分 S1：${formatNumber(record.net.first_item_raw_score)} / 240 → 总榜附加：+${formatNumber(record.net.first_item_add_on)}。`
        : "该人物第一项不适用，不参与总榜附加；不代表能力失败。";
      setText(score, scoreText);
    }
    const scope = document.querySelector("#net-major-body .notice");
    if (scope?.querySelector("strong")?.textContent.includes("时间与责任范围")) {
      const p = scope.querySelector(":scope > p");
      setText(p, "本项可以追溯到即位前的创业／统一责任。完成效率的计时点，只服务于效率判断，不会自动截断统一成果、组织整合、本人统帅或战争成本的责任范围。");
      for (const dt of scope.querySelectorAll("dt")) {
        if (dt.textContent.trim() === "B1完成效率计时") setText(dt, "完成效率计时");
      }
    }
  }

  function enhance() {
    ensureStyles();
    const record = currentRecord();
    if (!record?.net) return;
    if (location.hash.startsWith("#person/")) ensureFirstOverview(record);
    if (location.hash.startsWith("#net/")) {
      ensureLandingCard(record);
      rewriteFirstIntro(record);
      if (location.hash.match(/^#net\/[^/?#]+\/first(?:\/|$)/)) {
        humanizeFirstCards();
        ensureFirstSummary(record);
        ensureMilitaryLinks(record);
      }
    }
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
