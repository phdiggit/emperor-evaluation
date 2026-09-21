"use strict";

(() => {
  const netPublicText = value => String(value ?? "").trim();

  const netPublicIntro = {
    "A制度建设": "看本人是否建立了真正运行、能够延续的制度，同时把制度性副作用一起计入净效果。",
    "B1官僚治理": "看选任、奖惩、职责问责和命令落实，是否形成稳定有效的官僚执行。",
    "B2反馈与约束": "看真实信息能否上达、错误能否纠正，以及监察和复核能否实际约束权力。",
    "C1民生": "看普通家庭在本人统治主要阶段的基本生计状态，并对严重低谷作独立修正。",
    "C2经济财政": "看财政、生产、流通与国家汲取之间的净状态，而不是只看国库或单项政策。",
    "C3社会安全": "看社会秩序、人身安全和大范围破坏的实际结果，并区分局部事件与主要阶段。",
    "C4恢复与成本": "看危机后的恢复成果，同时扣除本人造成或放大的民力与治理成本。",
    "D1继任行政连续性": "看权力交接后行政机器、政策执行和基本治理能否继续运转。",
    "D3政权交接稳定": "看交接本身是否造成中枢失控、内战或严重继承危机。",
    "主要安全威胁与战略主动": "看安全与控制状态相对接手时发生了什么变化，并只计本人责任范围内的部分。",
    "防线协同与战略纵深": "看重要方向的防线和战略纵深最终取得、维持或丧失了多少实际安全收益。",
    "实际控制范围": "看本人新增或稳住了多少有效控制范围，避免把继承存量重复算作成果。",
    "战略成果价值": "看取得的控制与军事成果有多大战略价值，而不是只按面积或战役数量计分。",
    "控制成果稳定性": "看这些安全成果能否稳定交付，而不是在本人离场前后迅速失效。",
    "实战任务交付": "看军事体系在真实高压任务中能否把国家资源转化为可兑现的战场结果。",
    "持续作战与任务承载": "看军事体系能否跨阶段持续动员、补充和完成任务。",
    "军事体系可靠性": "看体系在不同战区和压力下是否稳定，还是频繁出现结构性失灵。",
    "普通军事代价": "看本人统治窗口内战争对本方军队、军事资产、后勤和持续动员造成的实际成本。",
    "重大军事净毁损": "看是否同时出现重大结果、较高本方代价和足够本人责任，从而需要追加扣减。",
    "国家共同体与社会整合": "看本人窗口对不同区域、群体与身份之间的参与、接纳和排斥造成了什么净变化。",
    "教育可及与人才流动": "看教育供给、学习机会和跨地域跨身份流动是否出现可归责的真实变化。",
    "知识生产、传播与文化生态": "看知识生产、保存、传播和文化生态是否出现可归责的真实变化。",
  };

  function conciseNetText(value) {
    return netPublicText(value);
  }

  function evidenceSection(title) {
    return Array.from(document.querySelectorAll("#person-evidence > section.panel")).find(section => {
      const heading = section.querySelector(":scope > h2, :scope > h3");
      return heading?.textContent.trim() === title;
    }) || null;
  }

  function normalizeEvidenceCardHeadings() {
    for (const title of ["统治绩效构成", "人物画像详情", "人物画像依据", "历史影响详情", "历史影响依据"]) {
      const section = evidenceSection(title);
      if (!section || section.dataset.publicHeading === "done") continue;
      const heading = section.querySelector(":scope > h2, :scope > h3");
      if (!heading) continue;
      if (heading.tagName === "H2") {
        heading.classList.add("evidence-card-title");
      } else {
        const replacement = document.createElement("h2");
        replacement.className = "evidence-card-title";
        replacement.textContent = title;
        heading.replaceWith(replacement);
      }
      section.dataset.publicHeading = "done";
    }
  }

  const netGroupNames = {
    first: "第一项 · 奠基与统一",
    method: "第二项 · 制度与行政",
    finance: "第二项 · 民生与社会",
    handoff: "第二项 · 政权交接",
    strategic: "第三项 · 战略收益与国防",
    military: "第三项 · 军事体系与成本",
    civilization: "第四项 · 文明与国家整合",
  };

  const firstItemDocs = {
    "A统一贡献": "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/01-第一项A统一主链客观贡献正式结算.md",
    "B1创业难度与效率": "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/02-第一项B1创业难度与战略效率正式结算.md",
    "B2组织与整合": "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/03-第一项B2创业组织与政治整合正式结算.md",
    "C军事统帅与战争解题": "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/04-第一项C本人军事统帅与战争解题能力正式结算.md",
  };
  const firstItemFormalNames = {"完颜晟": "完颜吴乞买"};
  const firstItemDocCache = new Map();

  function firstItemRawUrl(ref) {
    const path = String(ref || "").split("#", 1)[0];
    return typeof validatedRawUrl === "function" ? validatedRawUrl(path) : `../${path}?raw=1`;
  }

  async function loadFirstItemDoc(ref, record) {
    if (!ref) return "";
    const rulerId = record?.ruler_id || "";
    const cacheKey = `${rulerId}\u0000${ref}`;
    if (firstItemDocCache.has(cacheKey)) return firstItemDocCache.get(cacheKey);
    const pending = fetch(firstItemRawUrl(ref), {cache: "force-cache"})
      .then(response => response.ok ? response.text() : "")
      .catch(() => "");
    firstItemDocCache.set(cacheKey, pending);
    return pending;
  }

  function firstItemBulletsForName(markdown, rulerName) {
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

  function firstItemBullets(markdown, rulerNames) {
    const names = Array.isArray(rulerNames) ? rulerNames : [rulerNames];
    for (const rulerName of [...new Set(names.filter(Boolean))]) {
      const result = firstItemBulletsForName(markdown, rulerName);
      if (Object.keys(result).length) return result;
    }
    return {};
  }

  const FIRST_PUBLIC_R_GRADES = ["E","D","C","B","A","S","S+"];
  const FIRST_PUBLIC_O_GRADES = [null,"E","D","C","B","A","S"];
  const FIRST_PUBLIC_L_GRADES = ["E","D","C","B","A","S"];
  const FIRST_PUBLIC_D_GRADES = ["D","C","B","A","S"];
  const FIRST_PUBLIC_C_GRADES = {0:"E",1:"D",2:"C",3:"B",4:"A",5:"S"};
  const FIRST_PUBLIC_POSITION = {LOW:"低位",MID:"中位",HIGH:"高位"};

  function firstItemPublicText(value) {
    return String(value ?? "")
      .replace(/\bR([0-6])\b/g, (_, n) => `起点${FIRST_PUBLIC_R_GRADES[Number(n)] || n}档`)
      .replace(/\bO([1-6])\b/g, (_, n) => `对手${FIRST_PUBLIC_O_GRADES[Number(n)] || n}档`)
      .replace(/\bL([0-5])\b/g, (_, n) => `${FIRST_PUBLIC_L_GRADES[Number(n)] || n}档`)
      .replace(/\bD([0-4])\b/g, (_, n) => `${FIRST_PUBLIC_D_GRADES[Number(n)] || n}档难度`)
      .replace(/\bHYBRID\b/g, "战略统筹与本人主帅／临阵并存")
      .replace(/\bSTRATEGIC_COMMAND\b/g, "战略统筹路线")
      .replace(/\bNONE\b/g, "未形成可计的本人统帅责任")
      .replace(/\bC-([0-5])-(LOW|MID|HIGH)\b/g, (_, n, p) => `${FIRST_PUBLIC_C_GRADES[Number(n)] || n}档·${FIRST_PUBLIC_POSITION[p] || p}`)
      .replace(/\bC-0\b/g, `${FIRST_PUBLIC_C_GRADES[0]}档`)
      .replace(/\s+/g, " ")
      .trim();
  }

  const FIRST_COST_DEBIT = {
    0:{LOW:0,MID:0,HIGH:0},
    1:{LOW:0.5,MID:1,HIGH:1.5},
    2:{LOW:2,MID:2.5,HIGH:3},
    3:{LOW:4,MID:5,HIGH:6},
    4:{LOW:8.8,MID:10,HIGH:12.5},
    5:{LOW:18,MID:22.5,HIGH:27},
    6:{LOW:35,MID:42,HIGH:49},
    7:{LOW:60,MID:68,HIGH:76,HIGHEST:80},
  };
  const FIRST_COST_POSITION = {LOW:"低位",MID:"中位",HIGH:"高位",HIGHEST:"极端上沿"};

  function firstCostExactHow(item) {
    const match = String(item?.grade || "").match(/\bC([0-7])\s*\/\s*(LOW|MID|HIGH|HIGHEST)\b/i);
    if (!match) return firstCostPublicText(item?.reader_how || "");
    const level = Number(match[1]);
    const position = match[2].toUpperCase();
    const debit = FIRST_COST_DEBIT[level]?.[position];
    if (debit == null) return firstCostPublicText(item?.reader_how || "");
    const severity = firstCostPublicText(`第${level}级成本`);
    return `当前裁决为${severity}、${FIRST_COST_POSITION[position] || position}；固定扣分表直接对应${debit}分，所以本项扣${debit}分。`;
  }

  function firstB1ScoreText(item) {
    const current = firstItemPublicText(item?.reader_public_b1?.public_calculation || item?.reader_how || "");
    const start = "起点资源档表示入链时可调用的军政资源强弱，不是好坏评分；资源越弱，创业难度分越高：E档15、D档13、C档11、B档8、A档5、S档2、S+档0。";
    const opponent = "对手压力按最强两个独立战争机器计：E档1、D档2、C档4、B档6、A档8、S档10；最强全值，第二强取50%，合计最多15分。";
    const efficiency = "完成效率最多20分：期望完成年 = 4 + 8 × √(本阶段有效控制信用 / 1000)；速度比 = 实际阶段年数 / 期望完成年。速度比≤0.75、1.00、1.25、1.50、2.00、2.50、3.00、4.00时，依次得20、18、16、14、11、8、5、2分；超过4.00得0分。";
    return `B1满分50 = 起点难度15 + 对手难度15 + 完成效率20。\n${start}\n${opponent}\n${efficiency}${current ? `\n当前人物：${current}` : ""}`;
  }

  function firstCommanderScoreText(item) {
    const grade = firstItemPublicText(item?.grade || "");
    const table = "固定换算：E档=0分；D档（基础统帅）低/中/高位=4/7/10分；C档（重要统帅）=12/15/18分；B档（优秀统帅）=20/23/26分；A档（顶级统帅）=28/31/34分；S档（历史级统帅）=36/38/40分。";
    return `${table}${grade ? ` 当前为${grade}，对应${item.value}分。` : ""}`;
  }

  function firstFactText(value) {
    return firstItemPublicText(value)
      .replace(/^(?:S\+?|A|B|C|D|E)档[。；：]?\s*/, "")
      .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
      .trim();
  }

  function firstPublicOutcomeText(value) {
    return String(value ?? "").replace(/\s+/g, " ").trim();
  }

  function firstPublicOutcomeParts(outcome) {
    if (!outcome || typeof outcome !== "object") return [];
    return [
      ["起点与继承背景", outcome.public_outcome_basis],
      ["本人实际成果范围", outcome.public_scope],
      ["公开边界", outcome.public_boundary],
    ].filter(([, value]) => firstPublicOutcomeText(value));
  }

  function firstPublicSharePercent(outcome) {
    const value = Number(outcome?.public_share_percent);
    if (!Number.isFinite(value)) return "";
    return Number.isInteger(value) ? String(value) : value.toFixed(1);
  }

  function firstItemSourceBlock(item, record) {
    const sources = netSourceLinks(item, record);
    return sources ? `<details><summary>裁决依据与来源</summary><p class="sources">${sources}</p></details>` : "";
  }

  function renderFirstA(item, bullets, record) {
    const publicOutcome = item.reader_public_outcome || {};
    const calculation = item.reader_how || "";
    const percent = firstPublicSharePercent(publicOutcome);
    const project = publicOutcome.public_project ? `<div class="label">共同项目</div>${prose(firstPublicOutcomeText(publicOutcome.public_project))}` : "";
    const facts = firstPublicOutcomeParts(publicOutcome)
      .map(([label, value]) => `<div class="label">${esc(label)}</div>${prose(firstPublicOutcomeText(value))}`)
      .join("");
    const share = percent ? `<div class="label">成果占比</div>${prose(`约${percent}%`)}` : "";
    return `<article class="context-story net-public-item first-item-card"><div class="component"><span><strong>统一成果</strong><small>满分120；只看本人最终留下的稳定控制成果</small></span><b>${esc(netValue(item))}</b></div>${project}${facts}${share}<details><summary>这个分怎么算？</summary>${prose(`A = 120 × (min(1000, U) / 1000)^0.65，最后保留1位小数。${calculation ? `\n当前人物的正式代入：${calculation}` : ""}`)}</details>${firstItemSourceBlock(item, record)}</article>`;
  }

  function renderFirstB1(item, bullets, record) {
    return `<article class="context-story net-public-item first-item-card"><div class="component"><strong>起点、强敌与速度</strong><b>${esc(netValue(item))}</b></div>${firstB1Markup(item)}<details><summary>这个分怎么算？</summary>${prose(firstB1ScoreText(item))}</details>${firstItemSourceBlock(item, record)}</article>`;
  }


  function renderFirstB2(item, bullets, record) {
    const result = bullets["B2结算"] || "";
    const parallel = bullets["并行执行"] || "";
    const coverage = bullets["团队能力覆盖与组织杠杆"] || bullets["能力覆盖/组织杠杆"] || "";
    const integration = bullets["异质整合"] || "";
    const basis = bullets["裁决依据"] || "";
    return `<article class="context-story net-public-item first-item-card"><div class="component"><span><strong>创业组织与政治整合</strong><small>满分30；看多线并行、专业分工与异质整合</small></span><b>${esc(netValue(item))}</b></div><div class="label">这项看什么</div>${prose("看创业或统一机器能不能脱离本人逐项盯办而运行：能否多线并行、能否把高难任务交给专业责任中心、能否把不同地域和旧集团稳定整合进同一执行体系。")}${parallel ? `<div class="label">并行执行</div>${prose(firstFactText(parallel))}` : ""}${coverage ? `<div class="label">专业覆盖与组织杠杆</div>${prose(firstFactText(coverage))}` : ""}${integration ? `<div class="label">异质整合</div>${prose(firstFactText(integration))}` : ""}${basis ? `<div class="label">为什么这样判</div>${prose(firstFactText(basis))}` : ""}<details><summary>这个分怎么算？</summary>${prose(`三个维度均分为 E、D、C、B、A、S 六档，依次对应0、2、4、6、8、10分；B2 = 并行执行分 + 专业覆盖／组织杠杆分 + 异质整合分。${result ? `\n本人的正式结算：${firstItemPublicText(result)}` : ""}`)}</details>${firstItemSourceBlock(item, record)}</article>`;
  }

  function renderFirstC(item, bullets, record) {
    const facts = firstCommanderMarkup(item);
    return `<article class="context-story net-public-item first-item-card"><div class="component"><span><strong>本人统帅</strong><small>满分40；只看本人亲自承担并完成的军事指挥事实</small></span><b>${esc(netValue(item))}</b></div>${facts}<details><summary>这个分怎么算？</summary>${prose(`这里只看本人亲自承担的整体部署、战役指挥或临阵处理；将领独立完成的战果不直接归到本人名下。\\n${firstCommanderScoreText(item)}`)}</details>${firstItemSourceBlock(item, record)}</article>`;
  }

  function firstItemTotals(items) {
    const byLabel = Object.fromEntries(items.map(item => [item.label, item]));
    const a = byLabel["A统一贡献"]?.value;
    const b1 = byLabel["B1创业难度与效率"]?.value;
    const b2 = byLabel["B2组织与整合"]?.value;
    const c = byLabel["C军事统帅与战争解题"]?.value;
    const gross = byLabel["四轴合计"]?.value;
    const cost = byLabel["军事成本扣分"]?.value;
    const net = byLabel["第一项净分"]?.value;
    const addOn = byLabel["附加F"]?.value;
    if ([a, b1, b2, c, gross, cost, net, addOn].some(value => value == null)) return "";
    const addOnText = Number(addOn) > 0 ? `+${addOn}` : String(addOn);
    return `<article class="context-story net-public-item first-item-total"><div class="label">第一项最后怎么进入总榜</div><div class="component"><span><strong>第一项原始净收益</strong><small>统一成果、创业难度与效率、创业组织、本人统帅合计后，再扣除本人窗口内的军事代价</small></span><b>${esc(net)}</b></div><div class="component"><span><strong>进入总榜的加成</strong><small>所有人物都使用同一条折算曲线，避免第一项量纲直接压过其他项目</small></span><b>${esc(addOnText)}</b></div>${prose("先算第一项原始净收益，再按全员统一曲线折算为总榜加成；因此两个数字不是同一量纲，也不应直接比较大小。") }<details><summary>查看完整公式</summary>${prose(`四轴毛分 = A + B1 + B2 + C = ${a} + ${b1} + ${b2} + ${c} = ${gross}。\n第一项净分 S1 = max(0, 四轴毛分 − 军事代价扣减) = max(0, ${gross} − ${cost}) = ${net}。\n总榜附加分 F = 0.20 × 637 × (S1 / 240)^1.25 = ${addOn}。`)}</details></article>`;
  }

  async function hydrateFirstItemGroup(group, record, items) {
    const firstNotApplicable = record.net?.first_item_status === "NOT_APPLICABLE";
    if (firstNotApplicable) {
      group.innerHTML = `<h3>${esc(netGroupNames.first)}</h3><p class="notice"><strong>本项不适用。</strong>这不代表军事能力差，只表示该人物没有进入“建国、复国或统一创业主链”的本项加分口径，因此第一项不参与净收益计分。</p>`;
      return;
    }

    const labels = ["B1创业难度与效率", "B2组织与整合"];
    const bulletsByLabel = {};
    const names = [record.ruler_name, firstItemFormalNames[record.ruler_name]];
    await Promise.all(labels.map(async label => {
      const markdown = await loadFirstItemDoc(firstItemDocs[label], record);
      bulletsByLabel[label] = firstItemBullets(markdown, names);
    }));
    if (!group.isConnected || currentRecord()?.ruler_id !== record.ruler_id) return;

    const byLabel = Object.fromEntries(items.map(item => [item.label, item]));
    const cards = [];
    if (byLabel["A统一贡献"]) cards.push(renderFirstA(byLabel["A统一贡献"], {}, record));
    if (byLabel["B1创业难度与效率"]) cards.push(renderFirstB1(byLabel["B1创业难度与效率"], bulletsByLabel["B1创业难度与效率"], record));
    if (byLabel["B2组织与整合"]) cards.push(renderFirstB2(byLabel["B2组织与整合"], bulletsByLabel["B2组织与整合"], record));
    if (byLabel["C军事统帅与战争解题"]) cards.push(renderFirstC(byLabel["C军事统帅与战争解题"], bulletsByLabel["C军事统帅与战争解题"], record));
    if (byLabel["军事成本扣分"]?.value != null) cards.push(`<article class="context-story net-public-item first-item-card"><div class="component"><strong>战争代价</strong><b>${esc(netValue(byLabel["军事成本扣分"]))}</b></div>${firstCostMarkup(byLabel["军事成本扣分"])}<details><summary>扣分怎样换算</summary>${prose(firstCostExactHow(byLabel["军事成本扣分"]))}</details>${firstItemSourceBlock(byLabel["军事成本扣分"], record)}</article>`);
    const totals = firstItemTotals(items);
    const rawNetScore = byLabel["第一项净分"]?.value;
    const netScore = rawNetScore == null || rawNetScore === "" ? null : Number(rawNetScore);
    const zeroNote = Number.isFinite(netScore) && netScore === 0
      ? `<p class="notice"><strong>本项适用，但没有形成正向净收益。</strong>这与“不适用”不同：这里已经进入第一项结算，只是正向成果在扣除相关军事代价后没有留下正的净值。</p>`
      : "";
    group.innerHTML = `<h3>${esc(netGroupNames.first)}</h3><p class="reading-intro"><strong>本项只计算本人实际承担的创业／统一成果、本人统帅贡献及其代价；先形成原始净收益，再统一折算为总榜加成。</strong>不适用不等于军事能力差。下面再按统一成果、创业难度与效率、创业组织与政治整合、本人统帅展开具体依据。</p>${zeroNote}${cards.join("")}${totals}`;
  }

  function netValue(item) {
    if (item.value == null) return item.unit === "不单独计分" ? "不单独计分" : "—";
    const signed = item.value > 0 && item.label?.includes("文明") ? `+${item.value}` : String(item.value);
    return `${signed}${item.unit ? ` ${item.unit}` : ""}`;
  }

  function netSourceLinks(item, record) {
    const refs = Array.isArray(item.reader_source_refs) ? item.reader_source_refs : [];
    if (!refs.length && !item.source && !item.applied_source) return "";
    const ordered = [...new Set([item.source, item.applied_source, ...refs].filter(Boolean))];
    return ordered.map((ref, index) => {
      let labelText = index === 0 ? "看裁决依据 ↗" : `看补充来源 ${index} ↗`;
      if (ref === item.applied_source && ref !== item.source) labelText = "看采用值依据 ↗";
      return link(ref, labelText, record);
    }).join(" ");
  }

  function netJudgment(item, record) {
    const displayLabel = item.public_component_label || (item.label === "军事成本扣分" ? "军事代价扣减" : item.label);
    const intro = netPublicIntro[displayLabel] || netPublicIntro[item.label] || "";
    const decision = item.reader_summary ? conciseNetText(item.reader_summary) : "";
    const summaryText = [intro, decision].filter(Boolean).join("\n");
    const summary = summaryText
      ? `<div class="label">为什么这样评</div>${prose(summaryText)}`
      : "";
    const publicEvidence = Array.isArray(item.reader_public_evidence_items) ? item.reader_public_evidence_items : [];
    const highlightTexts = (publicEvidence.length
      ? publicEvidence.map(entry => `${entry?.public_label || entry?.public_role || "公开依据"}：${entry?.public_basis || ""}`)
      : (Array.isArray(item.reader_highlights) ? item.reader_highlights : []))
      .map(text => conciseNetText(text))
      .filter((text, index, values) => text && text !== decision && values.indexOf(text) === index);
    const highlights = highlightTexts.length
      ? `<div class="label">关键事实</div><ul>${highlightTexts.map(text => `<li>${esc(text)}</li>`).join("")}</ul>`
      : "";
    const boundaryText = item.reader_boundary ? conciseNetText(item.reader_boundary) : "";
    const boundary = boundaryText
      ? `<div class="label">限制与边界</div>${prose(boundaryText)}`
      : "";
    const rawHow = String(item.reader_how || "");
    const how = rawHow && !/\bNone\b/.test(rawHow)
      ? `<details><summary>这个分怎么算？</summary>${prose(netPublicText(rawHow))}</details>`
      : "";
    const fullBasis = item.reader_full_basis
      ? `<details><summary>完整裁决依据（原文）</summary>${prose(netPublicText(item.reader_full_basis))}</details>`
      : "";
    const sources = netSourceLinks(item, record);
    const sourceBlock = sources
      ? `<details><summary>正式记录与史料</summary><p class="sources">${sources}</p>${fullBasis}</details>`
      : fullBasis;
    return `<article class="context-story net-public-item"><div class="component"><span><strong>${esc(displayLabel)}</strong></span><b>${esc(netValue(item))}</b></div>${summary}${highlights}${boundary}${how}${sourceBlock}</article>`;
  }

  function netCalculation(item) {
    const how = item.reader_how || `${item.label}为计算项，具体公式见完整计分账本。`;
    if (/\bNone\b/.test(String(how))) return "";
    return `<div class="component"><span><strong>${esc(item.public_component_label || item.label)}</strong><small>${esc(netPublicText(how))}</small></span><b>${esc(netValue(item))}</b></div>`;
  }

  function buildNetReading(record) {
    const section = evidenceSection("统治绩效构成");
    const groups = Object.entries(record.net?.component_details || {});
    if (!section || !groups.length || section.dataset.netReadable === "done") return;

    const intro = document.createElement("div");
    intro.className = "net-reading";
    intro.innerHTML = `<p class="reading-intro">先看历史事实与判断，再看分数如何换算。小计、折算和总计属于计算过程，不再伪装成独立“评分依据”。</p>`;

    for (const [key, items] of groups) {
      if (!Array.isArray(items)) continue;
      const group = document.createElement("section");
      group.className = "net-public-group";
      group.dataset.netGroup = key;
      const title = `<h3>${esc(netGroupNames[key] || groupNames[key] || key)}</h3>`;

      const firstNotApplicable = key === "first" && record.net?.first_item_status === "NOT_APPLICABLE";
      if (firstNotApplicable) {
        group.innerHTML = `${title}<p class="notice"><strong>本项不适用。</strong>这不代表军事能力差，只表示该人物没有进入“建国、复国或统一创业主链”的本项加分口径，因此第一项不参与净收益计分。</p>`;
        intro.append(group);
        continue;
      }

      if (key === "first") {
        group.innerHTML = `${title}<p class="subline">正在整理第一项的逐人计算口径…</p>`;
        intro.append(group);
        void hydrateFirstItemGroup(group, record, items);
        continue;
      }

      const judgments = items.filter(item => item.reader_kind === "judgment");
      const calculations = items.filter(item => item.reader_kind === "calculation" && item.value != null);
      if (!judgments.length && !calculations.length) continue;
      group.innerHTML = `${title}${judgments.map(item => netJudgment(item, record)).join("")}${calculations.length ? `<details class="net-calculations"><summary>这一组怎么算出来？</summary>${calculations.map(netCalculation).join("")}</details>` : ""}`;
      intro.append(group);
    }

    const heading = section.querySelector(":scope > h2, :scope > h3");
    heading?.after(intro);
    section.dataset.netReadable = "done";
  }

  function enhanceC5Overview(record) {
    const axis = record.axes?.C5;
    if (!axis) return;
    const row = document.querySelector("#person-capability .style-axis .axis-row");
    if (!row || row.querySelector(".c5-scale-note")) return;
    if (axis.person_type) {
      const type = document.createElement("div");
      type.className = "c5-type subline";
      type.textContent = axis.person_type;
      row.append(type);
    }
    const note = document.createElement("div");
    note.className = "c5-scale-note subline";
    note.textContent = "S端表示更能约束自身权力，E端表示更易出现报复、强制滥用或特权；不计入能力雷达。";
    row.append(note);
  }

  function enhanceImpact(record) {
    const evidence = document.querySelector("#history-evidence");
    if (!evidence || evidence.dataset.personReadable === "done") return;
    const heading = evidence.querySelector(":scope > h2, :scope > h3.section-title");
    const firstDetails = heading?.nextElementSibling;
    if (firstDetails?.tagName === "DETAILS") {
      const summary = firstDetails.querySelector(":scope > summary");
      if (summary) summary.textContent = "完整定档依据";
    }
    evidence.dataset.personReadable = "done";
  }

  function openHistoricalImpactTarget(event) {
    const link = event.target.closest('[data-section^="history-dimension-"], [data-section="history-judgment-boundary"]');
    if (!link) return;
    const target = document.getElementById(link.dataset.section);
    if (target?.tagName === "DETAILS") target.open = true;
  }

  function foldNetLedger() {
    const section = evidenceSection("统治绩效构成");
    if (!section || section.dataset.ledgerFolded === "done") return;

    const items = Array.from(section.children).filter(node => node.tagName === "DETAILS");
    if (!items.length) return;
    const note = document.createElement("p");
    note.className = "subline net-ledger-note";
    note.textContent = "下面保留原始指标、内部档位、折算与小计，供复核使用；普通阅读无需展开。";
    const wrapper = document.createElement("details");
    wrapper.className = "net-ledger";
    const toggle = document.createElement("summary");
    toggle.textContent = "完整计分账本（审计视图）";
    wrapper.append(toggle, ...items);
    section.append(note, wrapper);
    section.dataset.ledgerFolded = "done";
  }

  function ensureMilitaryArchiveNav() {
    const nav = document.querySelector("header nav");
    if (!nav || nav.querySelector("[data-military-archive-nav]")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.militaryArchiveNav = "true";
    button.textContent = "军事档案";
    button.addEventListener("click", () => { location.href = "military.html"; });
    nav.append(button);
  }

  function currentRecord() {
    const match = location.hash.match(/^#person\/([^/?#]+)/);
    if (!match) return null;
    return byId.get(decodeURIComponent(match[1])) || null;
  }

  function enhance() {
    ensureMilitaryArchiveNav();
    const record = currentRecord();
    if (!record) return;
    enhanceC5Overview(record);
    enhanceImpact(record);
    normalizeEvidenceCardHeadings();
    buildNetReading(record);
    foldNetLedger();
  }

  screen.addEventListener("click", openHistoricalImpactTarget, true);
  new MutationObserver(enhance).observe(screen, {childList: true, subtree: true});
  window.addEventListener("hashchange", enhance);
  enhance();
})();
