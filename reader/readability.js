"use strict";

(() => {
  const baseReaderText = readerText;
  const publicReaderText = value => baseReaderText(value)
    .replace(/\bMIXED_NEGATIVE\b/g, "正负混合、以负向为主")
    .replace(/\bMIXED_POSITIVE\b/g, "正负混合、以正向为主")
    .replace(/\bNEGATIVE\b/g, "负向")
    .replace(/\bPOSITIVE\b/g, "正向")
    .replace(/\bMIXED\b/g, "正负混合")
    .replace(/\bCOUNTEREVIDENCE_FOUND\b/g, "已找到明确反例")
    .replace(/\bBACKGROUND_VALIDATION\b/g, "背景核验")
    .replace(/\bAXIS_OUT_WITH_REASON\b/g, "不计入本轴（有明确理由）")
    .replace(/\bFORMAL_CURRENT\b/g, "当前正式记录")
    .replace(/\bSCORING_PARENT\b/g, "主要计分证据")
    .replace(/\bREFUSAL_OR_RECURRENCE\b/g, "拒绝更新或同类复发情境")
    .replace(/\bTRUTH_ACQUISITION\b/g, "求真取证情境")
    .replace(/正式快照/g, "当前正式记录")
    .replace(/高档门/g, "高等级标准")
    .replace(/低档门/g, "低等级标准")
    .replace(/不转档/g, "不改变等级")
    .replace(/消费点/g, "评价落点")
    .replace(/消费的是/g, "评价关注的是")
    .replace(/父链/g, "证据链")
    .replace(/裁档/g, "定档")
    .replace(/重裁/g, "重新评估")
    .replace(/复验/g, "复核")
    .replace(/重开/g, "重新评估")
    .replace(/上沿/g, "更高等级空间")
    .replace(/下沿/g, "较低边界")
    .replace(/档内/g, "同档")
    .replace(/跨轴/g, "跨维度")
    .replace(/轴外/g, "本维度之外")
    .replace(/路由/g, "归类")
    .replace(/审计/g, "核对")
    .replace(/消费/g, "采用");

  readerText = publicReaderText;

  function foldHomeStatus() {
    const note = document.querySelector("#screen .footer-note:not([data-readability-status])");
    if (!note) return;
    const text = note.textContent.trim();
    const firstStop = text.indexOf("。");
    note.dataset.readabilityStatus = "done";
    if (firstStop < 0 || firstStop === text.length - 1) return;
    const headline = text.slice(0, firstStop + 1).trim();
    const detailText = text.slice(firstStop + 1).trim();
    if (!detailText) return;
    note.textContent = "";
    const summary = document.createElement("span");
    summary.className = "home-count-summary";
    summary.textContent = headline;
    const details = document.createElement("details");
    details.className = "data-status";
    const toggle = document.createElement("summary");
    toggle.textContent = "数据状态";
    const body = document.createElement("p");
    body.textContent = detailText;
    details.append(toggle, body);
    note.append(summary, details);
  }

  function compactComparisonEvidence() {
    for (const summary of document.querySelectorAll("#screen .comparison .axis-evidence > summary:not([data-compact-compare])")) {
      const badge = summary.querySelector(".badge");
      if (!badge) continue;
      const grade = badge.textContent.trim();
      summary.textContent = "";
      const compactBadge = document.createElement("span");
      compactBadge.className = "badge";
      compactBadge.textContent = grade;
      const label = document.createElement("span");
      label.className = "compare-evidence-label";
      label.textContent = "展开依据";
      summary.append(compactBadge, label);
      summary.dataset.compactCompare = "done";
    }
  }

  function simplifyDifferenceToggle() {
    const toggle = document.querySelector("#screen .difference-toggle:not([data-readable-toggle])");
    if (!toggle) return;
    for (const node of toggle.childNodes) {
      if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
        node.textContent = "只看不同项";
        break;
      }
    }
    toggle.dataset.readableToggle = "done";
  }

  function publicGradeHelp() {
    const profile = document.querySelector("#person-capability .grade-help:not([data-public-help])");
    if (profile) {
      const paragraphs = profile.querySelectorAll(":scope > p");
      if (paragraphs[0]) paragraphs[0].textContent = "各轴从E−到S+分18级；−、无符号、+分别表示同一字母等级中的较低、中间和较高位置。人物画像与历史影响使用不同尺度，字母相同也不能直接比较。";
      if (paragraphs[1]) paragraphs[1].textContent = "八个能力轴分别依据本轴行为证据；C5只评价权力运用风格与克制，不当作能力高低，也不计入能力雷达。不适用、待补证、待重裁会单独标明，不按低分处理。";
      profile.dataset.publicHelp = "done";
    }
    const impact = document.querySelector("#person-impact .grade-help:not([data-public-help])");
    if (impact) {
      const paragraph = impact.querySelector(":scope > p");
      if (paragraph) paragraph.textContent = "这是历史改变的量级，不是能力或功绩等级。最终等级与四个维度分别判断，不做简单平均。";
      impact.dataset.publicHelp = "done";
    }
  }

  function axisRecordForEvidence(details) {
    const id = details.id || "";
    let match = id.match(/^reason-([A-Z]\d)$/);
    if (match) {
      const person = location.hash.match(/^#person\/([^/?#]+)/);
      if (!person) return null;
      try { return byId.get(decodeURIComponent(person[1]))?.axes?.[match[1]] || null; } catch { return null; }
    }
    match = id.match(/^reason-([A-Z]\d)-compare-(\d+)$/);
    if (match) {
      const rulerId = state.compare[Number(match[2])];
      return rulerId ? byId.get(rulerId)?.axes?.[match[1]] || null : null;
    }
    return null;
  }

  function publicAxisMetadata() {
    for (const details of document.querySelectorAll("#screen .axis-evidence:not([data-public-metadata])")) {
      const axis = axisRecordForEvidence(details);
      if (!axis) continue;
      const box = Array.from(details.children).find(node => node.tagName === "DETAILS" && node.classList.contains("metadata") && !node.classList.contains("adjudication"));
      if (!box) continue;
      const summary = box.querySelector(":scope > summary");
      if (summary) summary.textContent = "专业信息与正式记录";
      const line = box.querySelector(":scope > .subline");
      if (line) {
        let status;
        if (ungraded(axis)) status = "当前状态：无档结案";
        else if (pending(axis)) status = `当前状态：${grade(axis)}`;
        else if (axis.applicability_status === "NOT_APPLICABLE" || axis.output_mode === "NOT_APPLICABLE") status = "当前状态：不适用";
        else status = `公开等级：${grade(axis)}`;
        line.textContent = `展示模式：${mode(axis.output_mode)} · 判断把握：${conf(axis.confidence)} · ${status}`;
      }
      details.dataset.publicMetadata = "done";
    }
  }

  function translateResidualAxisCodes() {
    for (const details of document.querySelectorAll("#screen .axis-evidence:not([data-public-terms])")) {
      const walker = document.createTreeWalker(details, NodeFilter.SHOW_TEXT);
      const nodes = [];
      while (walker.nextNode()) nodes.push(walker.currentNode);
      for (const node of nodes) {
        const parent = node.parentElement;
        if (!parent || parent.closest("a, code, .sources, .unavailable-source")) continue;
        const translated = publicReaderText(node.nodeValue);
        if (translated !== node.nodeValue) node.nodeValue = translated;
      }
      details.dataset.publicTerms = "done";
    }
  }

  const firstCostBandMeaning = {
    C0: "已核实没有实质军事投入或毁损；材料缺失不能当作C0。",
    C1: "局部、短期、常规投入，没有显著军资或兵团毁损。",
    C2: "有限方向投入，或轻度且容易恢复的人员、军资、编组损害。",
    C3: "明显方向级投入或可见累计负担，但还没有国家级长期高强度承载。",
    C4: "大规模或持续显著的区域、国家行动，已有实质兵团毁损或显著战争准备、后勤工程。",
    C5: "主要野战力量、重要兵团或军事资产严重毁损，或长期反复高强度战争形成国家尺度负担。",
    C6: "极端人员损耗，或国家核心军事能力严重毁损。",
    C7: "在C6级灾难之后又反复发生灾难，或持续投入走向军事耗竭。",
  };
  const firstCostPositionMeaning = {
    LOW: "刚达到本档，规模或累计强化有限",
    MID: "本档结构清楚，并有一项明显强化",
    HIGH: "本档结构很强，多项同向强化，但仍未达到更高档门槛",
    HIGHEST: "仅C7使用，代表实际损失、持续补充消耗和军事失能综合处于极端上沿",
  };
  const firstCostPositionName = {LOW: "低位", MID: "中位", HIGH: "高位", HIGHEST: "最高位"};
  const firstCostDebits = {
    C0: {LOW: 0, MID: 0, HIGH: 0},
    C1: {LOW: 0.5, MID: 1, HIGH: 1.5},
    C2: {LOW: 2, MID: 2.5, HIGH: 3},
    C3: {LOW: 4, MID: 5, HIGH: 6},
    C4: {LOW: 8.8, MID: 10, HIGH: 12.5},
    C5: {LOW: 18, MID: 22.5, HIGH: 27},
    C6: {LOW: 35, MID: 42, HIGH: 49},
    C7: {LOW: 60, MID: 68, HIGH: 76, HIGHEST: 80},
  };

  function currentFirstNetRecord() {
    const match = location.hash.match(/^#net\/([^/?#]+)\/first(?:\/|$)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; } catch { return null; }
  }

  function firstNetItem(record, label) {
    return record?.net?.component_details?.first?.find(item => item.label === label) || null;
  }

  function firstCostCard() {
    return Array.from(document.querySelectorAll("#net-major-body .net-metric-detail")).find(card => card.querySelector(":scope > summary strong")?.textContent.trim() === "军事成本扣分") || null;
  }

  function enhanceFirstItemCost() {
    const record = currentFirstNetRecord();
    const item = firstNetItem(record, "军事成本扣分");
    const card = firstCostCard();
    if (!record?.detail_loaded || !item || !card || card.dataset.costExplained === "done") return;
    const match = String(item.grade || "").match(/^(C[0-7])\s*\/\s*(LOW|MID|HIGH|HIGHEST)$/);
    if (!match) return;
    const [, band, position] = match;
    const body = card.querySelector(":scope > .net-metric-body");
    if (!body) return;
    const oldLogicLabel = Array.from(body.querySelectorAll(":scope > .label")).find(label => label.textContent.trim() === "当前人物结算逻辑");
    if (oldLogicLabel) oldLogicLabel.textContent = "计分理由";
    const current = document.createElement("div");
    current.className = "first-cost-explainer";
    const mappedDebit = firstCostDebits[band]?.[position];
    current.innerHTML = `<div class="label">当前军事成本档</div><p class="prose"><strong>${band} · ${firstCostPositionName[position] || position}</strong>：${firstCostBandMeaning[band]}；${firstCostPositionMeaning[position] || ""}。</p><p class="notice">这里的“成本${band}”衡量的是本方军事投入与毁损，不是第一项C“本人军事统帅能力”的C-${band.slice(1)}档；两套C完全独立。</p><details><summary>C0—C7大致怎么读？</summary><ul>${Object.entries(firstCostBandMeaning).map(([key, text]) => `<li><strong>${key}</strong>：${esc(text)}</li>`).join("")}</ul></details><details><summary>档位怎样换成扣分？</summary><p class="prose">先定成本档，再比较同档中的规模、核心角色、动员后勤、时长、战区与重建情况确定低／中／高位置；最后查第一项固定扣分表。当前为 <strong>${band} · ${firstCostPositionName[position] || position}</strong>${mappedDebit == null ? "" : `，对应扣 ${mappedDebit} 分`}。页面正式扣分为 ${esc(String(item.value))} 分。</p></details>`;
    body.prepend(current);
    card.dataset.costExplained = "done";
  }

  function enhanceFirstItemCommandGuide() {
    if (!currentFirstNetRecord()?.detail_loaded) return;
    const card = document.getElementById("net-first-c");
    if (!card || card.dataset.commandGuide === "done") return;
    const body = card.querySelector(":scope > .net-metric-body");
    if (!body) return;
    const audit = body.querySelector(":scope > .net-audit-sources");
    const guide = document.createElement("div");
    guide.className = "first-command-guide";
    guide.innerHTML = `<details><summary>战役标记怎样读？</summary><p class="prose"><strong>S−/D3</strong>不是一个总等级，而是两个彼此独立的标签：左边 <strong>S−</strong> 是这场战役兑现了多大的战略结果，右边 <strong>D3</strong> 是战前这个军事问题本身有多难。</p><ul><li><strong>结果档</strong>：C=局部战术结果；B=重要单项目标；A=主要区域、门户、主力集团或重大阶段结果；S−=强区域终局、核心根据地或长期独立战略方向；S=决定性击败第一梯队竞争极或国家级终局；S+=多个第一梯队竞争极／统一终局等最高结果。</li><li><strong>难度档</strong>：D0=几乎未形成有效军事对抗；D1=本方明显优势；D2=有一项重大难点但总体风险可控；D3=两项以上重大约束相互强化，需要高质量一线统帅；D4=极端劣势、被围断粮、濒临崩溃或连续败退后的临阵逆转。</li></ul><p class="prose">所以“S−/D3”可以读成：在高难条件下完成了一个独立战略方向级的重大结果。结果档高不等于难度一定高，难度高也不保证结果优秀。</p><p class="sources">${link("docs/证据规则/公共成果登记与人物画像规则.md", "战役结果与难度正式规则 ↗")} <a href="military.html">打开战役与武将档案 →</a></p></details><details><summary>这些战役怎样形成第一项C档？</summary><p class="prose">第一项C<strong>不是把S、A、D3、D4换成分数后求和或平均</strong>。战役登记只是证据锚，最终按下面的顺序整体裁决：</p><ol><li><strong>先过责任门</strong>：只采用本人真正承担的战略统筹、实际主帅或临阵指挥；普通任将、批准出兵、国家总成果和下属独立判断不能转给本人。</li><li><strong>再过窗口门</strong>：只看第一项建国、复国、统一或政权取得主链；主链闭合后的成熟扩张、防务不能拿来抬本项C。</li><li><strong>看正向证据结构</strong>：最高峰值、是否有独立复核、D3/D4高难成果、不同战区与战争形态的跨度，以及高层统筹和前线能力是否能反复成立。</li><li><strong>加入负向证据</strong>：本人可归责的重大失败、同类错误复发和未纠偏会压低档位或档内位置；敌强、天气、史源冲突或下属失败本身不算本人败责。</li><li><strong>最后定C档与档内位置</strong>：C-0=无可用本人军事责任证据；C-1=基础统帅；C-2=重要统帅；C-3=优秀统帅；C-4=顶级统帅；C-5=历史级统帅。低／中／高位再映射到0—40分。</li></ol><p class="prose">一个高质量闭环但没有独立复核，最高只能到C-3；C-4、C-5必须跨情境稳定成立。因此“一场S/D4”不会自动等于C-5，多场A/D3也不是简单相加。</p><p class="prose">公共军事人才登记中的“elite / top / historic”等全生涯聚合标签可以帮助复核证据厚度，但它有自己的窗口和聚合门槛，<strong>不能机械换算成第一项C</strong>。</p><p class="sources">${link("docs/分项规则/第一项政权奠基与统一贡献及能力/00-规则与计分合同.md#5-c本人军事统帅与战争解题能力40", "第一项C正式档位规则 ↗")} ${link("docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/05-第一项C战役标记与统帅档聚合说明.md", "C战役标记与聚合说明 ↗")}</p></details>`;
    if (audit) body.insertBefore(guide, audit);
    else body.append(guide);
    card.dataset.commandGuide = "done";
  }

  function battleTerms(text) {
    const found = [];
    const re = /([\u3400-\u9fff]{2,8}(?:[—－-][\u3400-\u9fff]{2,8})?)(S\+|S-|S−|S|A|B|C)\/(D[0-4])/g;
    for (const match of String(text || "").matchAll(re)) {
      const term = match[1];
      if (!found.includes(term)) found.push(term);
      if (found.length >= 10) break;
    }
    return found;
  }

  function enhanceFirstItemBattleLinks() {
    const card = document.getElementById("net-first-c");
    if (!card || card.dataset.battleLinks === "done") return;
    const labels = Array.from(card.querySelectorAll(".net-metric-body > .label"));
    const label = labels.find(node => node.textContent.trim() === "当前人物为什么是这个档");
    const prose = label?.nextElementSibling;
    if (!prose?.classList.contains("prose")) return;
    const terms = battleTerms(prose.textContent);
    if (!terms.length) { card.dataset.battleLinks = "done"; return; }
    const block = document.createElement("div");
    block.className = "first-battle-links";
    block.innerHTML = `<div class="label">相关战役档案</div><p class="sources">${terms.map(term => `<a href="military.html#search=${encodeURIComponent(term)}">${esc(term)} →</a>`).join(" ")}</p>`;
    prose.insertAdjacentElement("afterend", block);
    card.dataset.battleLinks = "done";
  }

  function enhance() {
    foldHomeStatus();
    compactComparisonEvidence();
    simplifyDifferenceToggle();
    publicGradeHelp();
    publicAxisMetadata();
    translateResidualAxisCodes();
    enhanceFirstItemCost();
    enhanceFirstItemCommandGuide();
    enhanceFirstItemBattleLinks();
  }

  new MutationObserver(enhance).observe(screen, {childList: true, subtree: true});
  enhance();
})();
