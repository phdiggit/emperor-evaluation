"use strict";

(() => {
  const DOCS = {
    "A统一贡献": "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/01-第一项A统一主链客观贡献正式结算.md",
    "B1创业难度与效率": "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/02-第一项B1创业难度与战略效率正式结算.md",
    "B2组织与整合": "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/03-第一项B2创业组织与政治整合正式结算.md",
    "C军事统帅与战争解题": "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/04-第一项C本人军事统帅与战争解题能力正式结算.md",
  };
  const FORMAL_NAME_ALIASES = {"完颜晟": "完颜吴乞买"};
  const R_GRADES = ["E", "D", "C", "B", "A", "S", "S+"];
  const O_GRADES = [null, "E", "D", "C", "B", "A", "S"];
  const L_GRADES = ["E", "D", "C", "B", "A", "S"];
  const D_GRADES = ["D", "C", "B", "A", "S"];
  const COST_SEVERITY = ["无显著代价", "很低", "较低", "中等", "较高", "高", "极高", "灾难级"];
  const POSITION = {LOW: "低位", MID: "中位", HIGH: "高位"};
  const docCache = new Map();
  const pending = new Set();

  function currentRecord() {
    const match = location.hash.match(/^#(?:person|net)\/([^/?#]+)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; }
    catch { return null; }
  }

  function rawUrl(ref) {
    return `../${String(ref || "").split("#", 1)[0]}?raw=1`;
  }

  function loadDoc(ref, record) {
    const rulerId = record?.ruler_id || currentRecord()?.ruler_id || "";
    const cacheKey = `${rulerId}\u0000${ref}`;
    if (!docCache.has(cacheKey)) {
      docCache.set(cacheKey, fetch(rawUrl(ref), {cache: "force-cache"})
        .then(response => response.ok ? response.text() : "")
        .catch(() => ""));
    }
    return docCache.get(cacheKey);
  }

  function bulletForName(markdown, rulerName) {
    if (!markdown || !rulerName) return {};
    const escaped = rulerName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const heading = new RegExp(`^###\\s+\\d+\\.\\s+${escaped}\\s*$`, "m");
    const match = heading.exec(markdown);
    if (!match) return {};
    const tail = markdown.slice(match.index + match[0].length);
    const next = tail.search(/^###\s+\d+\./m);
    const section = next >= 0 ? tail.slice(0, next) : tail;
    const result = {};
    for (const line of section.split(/\r?\n/)) {
      const bullet = line.match(/^-\s+\*\*(.+?)\*\*：\s*(.*)$/);
      if (!bullet) continue;
      result[bullet[1].trim()] = bullet[2].replace(/\*\*/g, "").replace(/`/g, "").trim();
    }
    return result;
  }

  function bullets(markdown, rulerNames) {
    const names = Array.isArray(rulerNames) ? rulerNames : [rulerNames];
    for (const rulerName of [...new Set(names.filter(Boolean))]) {
      const result = bulletForName(markdown, rulerName);
      if (Object.keys(result).length) return result;
    }
    return {};
  }

  function itemMap(items) {
    return Object.fromEntries((items || []).map(item => [item.label, item]));
  }

  function score(item, prefix = "") {
    if (!item || item.value == null) return "—";
    return `${prefix}${item.value}分`;
  }

  function sourceBlock(item, record, includeBasis = false) {
    if (!item) return "";
    const refs = [...new Set([item.source, item.applied_source, ...(item.reader_source_refs || [])].filter(Boolean))];
    const links = refs.map((ref, index) => link(ref, index ? `补充来源 ${index} ↗` : "裁决依据 ↗", record)).join(" ");
    const basis = includeBasis && item.reader_full_basis ? prose(item.reader_full_basis) : "";
    return links || basis ? `<details${item.reader_public_commander || item.reader_public_b1 || item.reader_public_cost ? ' data-formal-public-source' : ''}><summary>裁决依据与来源</summary>${links ? `<p class="sources">${links}</p>` : ""}${basis}</details>` : "";
  }

  function ruleDetails(lines) {
    const body = lines.filter(Boolean).join("\n");
    return body ? `<details><summary>规则与计算</summary>${prose(body)}</details>` : "";
  }

  function grade(code, family) {
    const match = String(code || "").match(/([ROLD])(\d)/);
    if (!match) return "";
    const index = Number(match[2]);
    if (family === "R") return R_GRADES[index] || "";
    if (family === "O") return O_GRADES[index] || "";
    if (family === "L") return L_GRADES[index] || "";
    if (family === "D") return D_GRADES[index] || "";
    return "";
  }

  function publicFact(value) {
    return String(value || "")
      .replace(/\bR([0-6])\b/g, (_, n) => R_GRADES[Number(n)] || "")
      .replace(/\bO([1-6])\b/g, (_, n) => O_GRADES[Number(n)] || "")
      .replace(/\bL([0-5])\b/g, (_, n) => L_GRADES[Number(n)] || "")
      .replace(/\bD([0-4])\b/g, (_, n) => `${D_GRADES[Number(n)] || ""}难度`)
      .replace(/\bHYBRID\b/g, "战略统筹与本人主帅／临阵并存")
      .replace(/\bSTRATEGIC_COMMAND\b/g, "战略统筹路线")
      .replace(/\bNONE\b/g, "未形成可计的本人统帅责任")
      .replace(/\s+/g, " ")
      .trim();
  }

  function publicOutcomeText(value) {
    return String(value ?? "").trim();
  }

  function publicOutcomeParts(outcome) {
    if (!outcome || typeof outcome !== "object") return [];
    return [
      ["起点与继承背景", outcome.public_outcome_basis],
      ["本人实际成果范围", outcome.public_scope],
      ["公开边界", outcome.public_boundary],
    ].filter(([, value]) => publicOutcomeText(value));
  }

  function publicSharePercent(outcome) {
    const value = Number(outcome?.public_share_percent);
    if (!Number.isFinite(value)) return "";
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
  }

  function lDimension(value) {
    const code = String(value || "").match(/\bL[0-5]\b/)?.[0] || "";
    return {
      grade: code ? grade(code, "L") : "",
      fact: String(value || "").replace(/^L[0-5][。；]?\s*/, "").trim(),
    };
  }

  function renderA(item, data, record) {
    const publicOutcome = item.reader_public_outcome || {};
    const calculation = item.reader_how || "";
    const percent = publicSharePercent(publicOutcome);
    const scaleText = percent ? `成果占比：约${percent}%` : "";
    const project = publicOutcome.public_project ? `<div class="label">共同项目</div>${prose(publicOutcomeText(publicOutcome.public_project))}` : "";
    const facts = publicOutcomeParts(publicOutcome)
      .map(([label, value]) => `<div class="label">${esc(label)}</div>${prose(publicOutcomeText(value))}`)
      .join("");
    return `<article class="context-story net-public-item first-item-card"><div class="component"><span><strong>统一成果</strong><small>先看本人实际完成并留下的统一成果</small></span><b>${esc(score(item))}</b></div>${project}${facts}${scaleText ? prose(scaleText) : ""}${ruleDetails(["内部指标：A。", calculation])}${sourceBlock(item, record)}</article>`;
  }

  function renderB1(item, data, record) {
    return `<article class="context-story net-public-item first-item-card"><div class="component"><span><strong>起点、强敌与速度</strong><small>起点实力越强，不等于创业难度越高</small></span><b>${esc(score(item))}</b></div>${firstB1Markup(item)}${ruleDetails(["内部指标：B1。", item.reader_public_b1?.public_calculation || ""])}${sourceBlock(item, record)}</article>`;
  }


  function renderB2(item, data, record) {
    const result = data["B2结算"] || "";
    const parallel = data["并行执行"] || "";
    const coverage = data["团队能力覆盖与组织杠杆"] || data["能力覆盖/组织杠杆"] || "";
    const integration = data["异质整合"] || "";
    const basis = data["裁决依据"] || "";
    const p = lDimension(parallel);
    const c = lDimension(coverage);
    const i = lDimension(integration);
    const metrics = [["并行执行", p.grade], ["专业分工", c.grade], ["异质整合", i.grade]]
      .filter(([, value]) => value)
      .map(([label, value]) => `${label} <strong>${value}</strong>`)
      .join(" · ");
    return `<article class="context-story net-public-item first-item-card"><div class="component"><span><strong>组织与整合</strong><small>看多线执行、专业分工和不同集团能否进入同一套运行体系</small></span><b>${esc(score(item))}</b></div>${metrics ? `<p class="prose">${metrics}</p>` : ""}${p.fact ? `<div class="label">并行执行</div>${prose(publicFact(p.fact))}` : ""}${c.fact ? `<div class="label">专业分工</div>${prose(publicFact(c.fact))}` : ""}${i.fact ? `<div class="label">异质整合</div>${prose(publicFact(i.fact))}` : ""}${basis ? `<div class="label">补充依据</div>${prose(publicFact(basis))}` : ""}${ruleDetails(["内部指标：B2。", parallel, coverage, integration, result])}${sourceBlock(item, record)}</article>`;
  }

  function renderC(item, data, record) {
    const facts = firstCommanderMarkup(item);
    return `<article class="context-story net-public-item first-item-card"><div class="component"><span><strong>本人统帅</strong><small>只看本人亲自承担并完成的军事指挥事实</small></span><b>${esc(score(item))}</b></div>${facts}${ruleDetails(["这里只看本人亲自承担的整体部署、战役指挥或临阵处理；将领独立完成的战果不直接归到本人名下。"])}${sourceBlock(item, record)}</article>`;
  }

  function renderCost(item, record) {
    return `<article class="context-story net-public-item first-item-card"><div class="component"><span><strong>战争代价</strong><small>本人创业／统一窗口内本方军事损失</small></span><b>${esc(score(item, "扣"))}</b></div>${firstCostMarkup(item)}${ruleDetails([item.reader_how || ""])}${sourceBlock(item, record)}</article>`;
  }

  function renderTotals(items) {
    const byLabel = itemMap(items);
    const a = byLabel["A统一贡献"]?.value;
    const b1 = byLabel["B1创业难度与效率"]?.value;
    const b2 = byLabel["B2组织与整合"]?.value;
    const c = byLabel["C军事统帅与战争解题"]?.value;
    const gross = byLabel["四轴合计"]?.value;
    const cost = byLabel["军事成本扣分"]?.value;
    const net = byLabel["第一项净分"]?.value;
    const addOn = byLabel["附加F"]?.value;
    if ([a, b1, b2, c, gross, cost, net, addOn].some(value => value == null)) return "";
    const addOnText = Number(addOn) > 0 ? `+${addOn}分` : `${addOn}分`;
    const publicEquation = `统一成果 ${a} + 难度效率 ${b1} + 组织整合 ${b2} + 统帅 ${c} − 战争代价 ${cost} = ${net}`;
    return `<article class="context-story net-public-item first-item-total"><div class="component"><span><strong>第一项结算</strong><small>${esc(publicEquation)}</small></span><b>${esc(`${net}分`)}</b></div><div class="component"><span><strong>进入总榜的加成</strong><small>统一使用同一条折算曲线</small></span><b>${esc(addOnText)}</b></div>${ruleDetails([`内部四项：A + B1 + B2 + C = ${a} + ${b1} + ${b2} + ${c} = ${gross}。`, `第一项净分 S1 = max(0, ${gross} − ${cost}) = ${net}。`, `总榜附加分 F = 0.20 × 637 × (S1 / 240)^1.25 = ${addOn}。`])}</article>`;
  }

  function firstItemTarget() {
    if (/^#net\/[^/?#]+\/first(?:\/|$)/.test(location.hash)) {
      return document.getElementById("net-major-body");
    }
    return document.querySelector('.net-public-group[data-net-group="first"]');
  }

  async function build(group, record, items) {
    const dedicated = /^#net\/[^/?#]+\/first(?:\/|$)/.test(location.hash);
    const heading = dedicated ? "" : `<h3>第一项 · 奠基与统一</h3>`;
    const firstStatus = record.net?.first_item_status;
    if (firstStatus === "NOT_APPLICABLE") {
      group.innerHTML = `<div class="first-item-public-v2">${heading}<p class="notice"><strong>本项不适用。</strong>这不代表军事能力差，只表示该人物没有进入建国、复国或统一创业主链的本项加分口径。</p></div>`;
      return;
    }
    if (firstStatus !== "APPLICABLE") {
      group.innerHTML = `<div class="first-item-public-v2">${heading}<p class="notice"><strong>第一项正式适用状态未发布。</strong>阅读层不根据现有分项自行判断是否适用。</p></div>`;
      return;
    }
    const formalName = FORMAL_NAME_ALIASES[record.ruler_name] || record.ruler_name;
    const names = [record.ruler_name, formalName];
    const entries = await Promise.all(Object.entries(DOCS).filter(([label]) => label !== "C军事统帅与战争解题")
      .filter(([label]) => label !== "A统一贡献" && label !== "B1创业难度与效率")
      .map(async ([label, ref]) => [label, bullets(await loadDoc(ref, record), names)]));
    if (!group.isConnected || currentRecord()?.ruler_id !== record.ruler_id) return;
    const data = Object.fromEntries(entries);
    const byLabel = itemMap(items);
    const cards = [];
    if (byLabel["A统一贡献"]) cards.push(renderA(byLabel["A统一贡献"], data["A统一贡献"], record));
    if (byLabel["B1创业难度与效率"]) cards.push(renderB1(byLabel["B1创业难度与效率"], data["B1创业难度与效率"], record));
    if (byLabel["B2组织与整合"]) cards.push(renderB2(byLabel["B2组织与整合"], data["B2组织与整合"], record));
    if (byLabel["C军事统帅与战争解题"]) cards.push(renderC(byLabel["C军事统帅与战争解题"], data["C军事统帅与战争解题"], record));
    if (byLabel["军事成本扣分"]?.value != null) cards.push(renderCost(byLabel["军事成本扣分"], record));
    const rawNetScore = byLabel["第一项净分"]?.value;
    const netScore = rawNetScore == null || rawNetScore === "" ? null : Number(rawNetScore);
    const zeroNote = Number.isFinite(netScore) && netScore === 0
      ? `<p class="notice"><strong>本项适用，但没有形成正向净收益。</strong>这里已经进入第一项结算，只是成果在扣除相关战争代价后没有留下正的净值。</p>`
      : "";
    const intro = dedicated
      ? `<p class="reading-intro"><strong>先看${esc(record.ruler_name)}在这条主链里实际做了什么。</strong>内部指标代号、变量定义和公式全部收进“规则与计算”。</p>`
      : `<p class="reading-intro"><strong>默认层只讲这个人实际做了什么。</strong>内部指标代号、变量定义和公式统一收进“规则与计算”；公众等级只用来辅助读事实。</p>`;
    group.innerHTML = `<div class="first-item-public-v2">${heading}${intro}${zeroNote}${cards.join("")}${renderTotals(items)}</div>`;
  }

  async function enhance() {
    const record = currentRecord();
    if (!record?.net) return;
    const group = firstItemTarget();
    if (!group || group.querySelector(":scope > .first-item-public-v2") || pending.has(record.ruler_id)) return;
    const items = record.net.component_details?.first;
    if (!Array.isArray(items)) return;
    pending.add(record.ruler_id);
    try { await build(group, record, items); }
    finally { pending.delete(record.ruler_id); }
  }

  const root = document.getElementById("screen") || document.body;
  new MutationObserver(enhance).observe(root, {childList: true, subtree: true});
  window.addEventListener("hashchange", enhance);
  enhance();
})();
