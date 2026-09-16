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
    return links || basis ? `<details><summary>裁决依据与来源</summary>${links ? `<p class="sources">${links}</p>` : ""}${basis}</details>` : "";
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
      .replace(/\bC-[0-5](?:-(?:LOW|MID|HIGH))?\b/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function publicOutcomeText(value) {
    return publicFact(value)
      .replace(/(?:有效控制信用|个人分得|本人六国统一净新增)\s*(?:为|是|约)?\s*\d+(?:\.\d+)?/g, "")
      .replace(/约?\d+(?:\.\d+)?\s*单位/g, "")
      .replace(/按(?:完整)?\s*\d+(?:\.\d+)?\s*池/g, "")
      .replace(/约?\d+(?:\.\d+)?\s*(?:空间)?恢复(?:控制)?(?:按\s*50%\s*折成\s*\d+(?:\.\d+)?\s*有效信用|[×x*]\s*50%\s*=?\s*\d+(?:\.\d+)?)/g, "")
      .replace(/\s*×\s*50%\s*折成\s*\d+(?:\.\d+)?\s*有效信用/g, "")
      .replace(/约占\s*\d+(?:\.\d+)?%/g, "")
      .replace(/约\d+(?:\.\d+)?(?:\s*=\s*\d+(?:\.\d+)?)?(?=[。；，])/g, "")
      .replace(/控制信用/g, "")
      .replace(/；\s*；/g, "；")
      .replace(/；\s*。/g, "。")
      .replace(/，\s*。/g, "。")
      .replace(/从女真整合到1683核心统一一次结算；玄烨的。?/g, "从女真各部整合与东北根据地起步，先后取得辽东、华北及全国核心区域；不同阶段按人物分别归属。")
      .replace(/郭威取得中原核心、柴荣续接淮南及北方阶段成果；同一后周统一主链只生成一次池。?/g, "从后周中原核心起步，郭威取得中原核心，柴荣续取淮南及北方部分区域；不同阶段按人物分别归属。")
      .replace(/李克用前置基盘、李存勖灭梁主体、李嗣源独立方面贡献合并一次结算。?/g, "从李克用建立的河东基盘起步，李存勖灭梁并取得中原主体，李嗣源完成后续独立方面的区域取得；不同阶段按人物分别归属。")
      .replace(/石勒建基与后赵扩展合并一次结算；石虎按现有重大独立方向。?/g, "从河北据点起步，石勒建立后赵并扩展至中原，石虎取得部分北方独立区域；不同阶段按人物分别归属。")
      .replace(/姚苌建基与姚兴接续扩展合并；姚兴本人去世前已大量退失，不按峰值锁分。?/g, "从后秦关中核心起步，姚苌建立政权，姚兴一度扩展至秦陇、河东等区域；退出前部分区域已退失。")
      .replace(/总池封顶100；仅计元统一主链直接继承成果，花剌子模及中西亚扩张排除。?/g, "从蒙古帝国既有草原与北方核心起步，推进华北、四川、大理和江南等元统一主链区域；花剌子模与中西亚扩张不计入本项。")
      .replace(/只计司马昭灭蜀与司马炎灭吴的空间增量；司马懿、司马师的中枢夺权不生成A空间信用。?/g, "从曹魏既有中原核心起步，司马昭完成蜀地统一，司马炎完成吴地统一；中枢权力更替不计为区域成果。")
      .replace(/赵匡胤南方统一主体；赵光义只计北汉河东终局，燕云失败不生成。?/g, "从后周中原核心起步，赵匡胤完成南方大部统一，赵光义完成北汉、河东终局；燕云未能取得。")
      .replace(/南宋重建按恢复型处理；江南、荆襄、巴蜀、岭南等。?/g, "从江南立足，恢复江南、荆襄、巴蜀、岭南等主要区域，形成南宋核心。")
      .replace(/东晋属恢复型；南方。?/g, "从江南既有政权基础起步，恢复东晋南方主要区域。")
      .replace(/190—220整条创业链重建；汉中219已失不计，保守取北方主体。?/g, "从东汉末年地方军政集团起步，逐步取得兖州、豫州、河北、关中等北方主要区域；汉中后来失守，最终保留北方主体。")
      .replace(/极小创业基盘到明初全国核心统一。?/g, "从很小的创业基盘起步，取得江南、中原和北方核心区域，完成明初全国统一。")
      .replace(/受命西川为基线，只计兼并东川约半个巴蜀宏区=50。?/g, "从西川据点起步，兼并东川，形成巴蜀主要区域。")
      .replace(/域外等价值块：1124西迁至1134巴拉沙衮建都闭合，轻量折算120；1141怛罗斯\/卡特万后续扩张不进A。?/g, "从辽朝残部与西迁部众起步，迁至中亚并在巴拉沙衮建立西辽；后续中亚扩张不计入本项。")
      .replace(/后燕复国至394灭西燕的稳定终点，取。?/g, "从后燕复国据点起步，收复河北、山东等区域，至灭西燕形成后燕稳定核心。")
      .replace(/建立南燕青齐主体，约山东0\.75=75。?/g, "从后燕残部起步，南迁并取得青齐，建立南燕核心。")
      .replace(/从零起兵到控制河西主体，按一个major region 60。?/g, "从河西小型集团起步，取得凉州、张掖、酒泉等河西主体区域。")
      .replace(/后凉初建控制河西。?/g, "从凉州远征军起步，建立并控制河西的后凉核心。")
      .replace(/杭州为基线，到两浙吴越核心，按宽口径江南宏区约新增30。?/g, "从杭州据点起步，扩展到两浙吴越核心区域。")
      .replace(/继承刘隐岭南主体，仅计容管、高州等少量新增。?/g, "从刘隐留下的岭南主体起步，取得容管、高州等少量新增区域。")
      .replace(/只结算901—916契丹国家创建；916年后的成熟国家扩张不进入第一项。?/g, "从契丹部落联盟起步，建立契丹国家并形成初始核心；916年后成熟扩张不计入本项。")
      .replace(/\s+/g, " ")
      .trim();
  }

  function publicCommanderText(value) {
    return publicFact(value)
      .replace(/\b[SABCD][+−-]?\/D[0-4]\b/g, "")
      .replace(/\b[SABCD][+−-]?(?:至|到)[SABCD][+−-]?\/D[0-4]\b/g, "")
      .replace(/[SABCD][+−-]?档/g, "")
      .replace(/统帅证据[:：]?/g, "")
      .replace(/现场与败责复验[:：]?/g, "")
      .replace(/第一项(?:主链|建国统一链)内已有/g, "本项主链中已有")
      .replace(/(?:高难|高质量)统帅锚/g, "高难度战役")
      .replace(/统帅锚/g, "战役案例")
      .replace(/峰值/g, "最高表现")
      .replace(/复验/g, "其他案例")
      .replace(/场景跨度/g, "不同战场和时期")
      .replace(/责任中心/g, "将领")
      .replace(/具体军事统帅信用/g, "具体战役指挥责任")
      .replace(/已闭合到/g, "主要由")
      .replace(/(主要由[^；。]+?将领)(?=；|。)/g, "$1承担")
      .replace(/([^；。]+?)由B2等轴承接/g, "$1另行评价")
      .replace(/现有(?:登记|材料)不足以证明([^；。]+?)承担具体战争统帅责任/g, "现有材料没有确认$1亲自统领具体战役")
      .replace(/因此C为0/g, "因此不计入本人统帅表现")
      .replace(/\bC为0\b/g, "不计入本人统帅表现")
      .replace(/\s*；\s*；/g, "；")
      .replace(/\s*，\s*。/g, "。")
      .replace(/\s+/g, " ")
      .trim();
  }

  function outcomePercent(...values) {
    for (const value of values) {
      const match = String(value || "").match(/约相当于全国核心统一尺度的\s*(\d+(?:\.\d+)?)%/);
      if (match) {
        const numeric = Number(match[1]);
        return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(1);
      }
    }
    const raw = values.map(value => String(value || "")).join("；");
    const credit = raw.match(/(?:有效控制信用|个人分得)\s*(?:为|是)?\s*(\d+(?:\.\d+)?)/);
    if (credit) return (Number(credit[1]) / 10).toFixed(1);
    return "";
  }

  function cleanStart(value) {
    return String(value || "")
      .replace(/^R[0-6](?:（[^）]*分）)?[。；]?\s*/, "")
      .replace(/\bR([0-6])\b/g, (_, n) => R_GRADES[Number(n)] || "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function cleanOpponent(value) {
    return String(value || "")
      .replace(/^O[1-6](?:\s*\+\s*O[1-6])?(?:（第二强半值）)?，?共\s*\d+(?:\.\d+)?分[。；]?\s*/, "")
      .replace(/\bO([1-6])\b/g, (_, n) => O_GRADES[Number(n)] || "")
      .replace(/是典型(?=[EDCBAS])/g, "为")
      .replace(/取最强同级竞争极(?=[EDCBAS])/g, "为")
      .replace(/取第二强(?=[EDCBAS])/g, "为")
      .replace(/（第二强半值）/g, "")
      .replace(/共\s*\d+(?:\.\d+)?分/g, "")
      .replace(/；\s*；/g, "；")
      .replace(/\s+/g, " ")
      .trim();
  }

  function efficiencyYears(value) {
    return String(value || "").match(/实际\s*(\d+(?:\.\d+)?)年/)?.[1] || "";
  }

  function efficiencyNarrative(value) {
    const text = String(value || "");
    const firstStop = text.indexOf("。");
    if (firstStop < 0) return "";
    return publicFact(text.slice(firstStop + 1))
      .replace(/效率U\s*=\s*\d+(?:\.\d+)?[，,]?/g, "")
      .replace(/期望\s*\d+(?:\.\d+)?年[，,]?/g, "")
      .replace(/速度比\s*\d+(?:\.\d+)?[，,]?/g, "")
      .replace(/得\s*\d+(?:\.\d+)?分[。；]?/g, "")
      .trim();
  }

  function lDimension(value) {
    const code = String(value || "").match(/\bL[0-5]\b/)?.[0] || "";
    return {
      grade: code ? grade(code, "L") : "",
      fact: String(value || "").replace(/^L[0-5][。；]?\s*/, "").trim(),
    };
  }

  function normalizeResultGrade(value) {
    return String(value || "").replace(/-/g, "−");
  }

  function sortBattleAnchors(anchors) {
    const resultRank = {"S+": 12, "S": 11, "S−": 10, "A+": 9, "A": 8, "A−": 7, "B+": 6, "B": 5, "B−": 4, "C+": 3, "C": 2, "C−": 1};
    const difficultyRank = {S: 5, A: 4, B: 3, C: 2, D: 1};
    return anchors.sort((a, b) => (resultRank[b.result] || 0) - (resultRank[a.result] || 0) || (difficultyRank[b.difficulty] || 0) - (difficultyRank[a.difficulty] || 0));
  }

  function structuredBattleAnchors(value) {
    const result = [];
    for (const part of String(value || "").split(/[；;]/)) {
      const fields = part.split(/[｜|]/).map(field => field.trim());
      if (fields.length < 4) continue;
      const name = fields[0];
      const role = fields[1];
      const resultGrade = normalizeResultGrade(fields[2].replace(/成果/g, "").trim());
      const difficultyCode = fields[3].match(/\bD([0-4])\b/)?.[1];
      if (!name || !["前线作战", "战略统筹"].includes(role) || !/^(?:S[+−]?|A[+−]?|B[+−]?|C[+−]?|D[+−]?|E)$/.test(resultGrade)) continue;
      const entry = {
        name,
        role,
        result: resultGrade,
        difficulty: difficultyCode == null ? "" : D_GRADES[Number(difficultyCode)] || "",
      };
      if (!result.some(existing => existing.name === entry.name)) result.push(entry);
    }
    return sortBattleAnchors(result);
  }

  function fallbackBattleAnchors(value) {
    const primary = String(value || "").split(/；?现场与败责复验[:：]/)[0];
    const result = [];
    const add = (rawName, role, resultGrade, difficultyCode = "") => {
      let name = String(rawName || "").trim()
        .replace(/^(?:(?:统帅证据|现场与败责复验)[:：]|第一项(?:主链|建国统一链)内已有|已有|另有|并有|并以|又有|又以|其中|包括|以及|有|以)+/, "")
        .replace(/^[、，；：\s]+/, "")
        .replace(/^(?:多个|多次)/, "")
        .replace(/(?:等|一役)$/g, "")
        .trim();
      if (!name || name.length > 24 || /(?:存在|可进入|高层|大量|多项|多次|形成|成果中|等)/.test(name)) return;
      const entry = {
        name,
        role,
        result: normalizeResultGrade(resultGrade),
        difficulty: difficultyCode ? D_GRADES[Number(difficultyCode)] || "" : "",
      };
      if (!result.some(existing => existing.name === entry.name)) result.push(entry);
    };

    const battlePattern = /([^，；。]{1,36}?)(S\+|S[−-]|S|A[+−-]?|B[+−-]?|C[+−-]?|D[+−-]?|E[+−-]?)\/D([0-4])/g;
    let match;
    while ((match = battlePattern.exec(primary)) !== null) {
      const role = /统筹|统总|战略|方案|部署/.test(match[1]) ? "战略统筹" : "前线作战";
      add(match[1], role, match[2], match[3]);
    }

    const strategyPattern = /([^，；。]{1,36}?)(S\+|S[−-]|S|A[+−-]?|B[+−-]?|C[+−-]?|D[+−-]?|E)(?:级)?[^，；。]{0,12}(?:战争|战略)?统筹/g;
    while ((match = strategyPattern.exec(primary)) !== null) {
      add(match[1], "战略统筹", match[2]);
    }
    return sortBattleAnchors(result);
  }

  function battleAnchors(value, structured = "") {
    const explicit = structuredBattleAnchors(structured);
    if (explicit.length) return explicit;
    return fallbackBattleAnchors(value);
  }

  function renderBattles(basis, structured = "") {
    const anchors = battleAnchors(basis, structured);
    if (!anchors.length) return "";
    return `<ul class="first-item-battles">${anchors.map(anchor => `<li><strong>${esc(anchor.name)}</strong> · ${esc(anchor.role)} · ${esc(anchor.result)}成果 · ${esc(anchor.difficulty ? `${anchor.difficulty}难度` : "难度不单列")}　<a href="military.html#search=${encodeURIComponent(anchor.name)}">查看战役档案 ↗</a></li>`).join("")}</ul>`;
  }

  function renderA(item, data, record) {
    const result = data["A结算"] || data["结算结果"] || "";
    const project = data["项目总成果"] || "";
    const scale = data["本人取得/归属成果"] || data["取得/恢复成果"] || data["成果规模"] || "";
    const content = publicOutcomeText(data["成果内容"] || "");
    const calculation = data["计算"] || item.reader_how || "";
    const percent = outcomePercent(scale, project);
    const scaleText = percent ? `成果占比：约${percent}%` : "";
    return `<article class="context-story net-public-item first-item-card"><div class="component"><span><strong>统一成果</strong><small>先看本人实际完成并留下的统一成果</small></span><b>${esc(score(item))}</b></div>${content ? prose(content) : ""}${scaleText ? prose(scaleText) : ""}${ruleDetails(["内部指标：A。", project, scale, calculation, result])}${sourceBlock(item, record)}</article>`;
  }

  function renderB1(item, data, record) {
    const result = data["B1结算"] || "";
    const start = data["起点"] || "";
    const opponent = data["对手"] || "";
    const efficiency = data["效率"] || "";
    const startCode = start.match(/\bR[0-6]\b/)?.[0] || "";
    const opponentCodes = [...opponent.matchAll(/\bO[1-6]\b/g)].map(match => match[0]).filter((code, index, values) => values.indexOf(code) === index).slice(0, 2);
    const years = efficiencyYears(efficiency);
    const metrics = [
      startCode ? `起点实力 <strong>${grade(startCode, "R")}</strong>` : "",
      opponentCodes[0] ? `最强对手 <strong>${grade(opponentCodes[0], "O")}</strong>` : "",
      opponentCodes[1] ? `次强对手 <strong>${grade(opponentCodes[1], "O")}</strong>` : "",
      years ? `<strong>${esc(years)}年</strong>完成核心成果` : "",
    ].filter(Boolean).join(" · ");
    const startFact = cleanStart(start);
    const opponentFact = cleanOpponent(opponent);
    const efficiencyFact = efficiencyNarrative(efficiency);
    return `<article class="context-story net-public-item first-item-card"><div class="component"><span><strong>起点、强敌与速度</strong><small>起点实力越强，不等于创业难度越高</small></span><b>${esc(score(item))}</b></div>${metrics ? `<p class="prose">${metrics}</p>` : ""}${startFact ? `<div class="label">起点</div>${prose(startFact)}` : ""}${opponentFact ? `<div class="label">主要对手</div>${prose(opponentFact)}` : ""}${efficiencyFact ? `<div class="label">完成速度</div>${prose(efficiencyFact)}` : ""}${ruleDetails(["内部指标：B1。", start, opponent, efficiency, result])}${sourceBlock(item, record)}</article>`;
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
    const basis = data["结算依据"] || "";
    const battles = renderBattles(basis, data["统一链战役清单"] || "");
    const fallback = battles ? "" : publicCommanderText(basis);
    return `<article class="context-story net-public-item first-item-card"><div class="component"><span><strong>本人统帅</strong><small>只看本人亲自承担并完成的军事指挥事实</small></span><b>${esc(score(item))}</b></div>${battles || (fallback ? prose(fallback) : "")}${ruleDetails(["这里只看本人亲自承担的整体部署、战役指挥或临阵处理；将领独立完成的战果不直接归到本人名下。"])}${sourceBlock(item, record)}</article>`;
  }

  function costGrade(item) {
    const raw = `${item?.grade || ""} ${item?.note || ""}`;
    const level = raw.match(/\bC-?([0-7])\b/)?.[1];
    const position = raw.match(/\b(LOW|MID|HIGH)\b/)?.[1];
    return {
      severity: level != null ? COST_SEVERITY[Number(level)] || "" : "",
      position: position ? POSITION[position] : "",
    };
  }

  function costPublicText(value) {
    return String(value || "")
      .replace(/\bC-?([0-7])\s*门/g, "更高严重度门槛")
      .replace(/\bC-?([0-7])\b/g, (_, n) => COST_SEVERITY[Number(n)] || "")
      .replace(/\bLOW\b/g, "低位")
      .replace(/\bMID\b/g, "中位")
      .replace(/\bHIGH\b/g, "高位")
      .replace(/归责/g, "责任归属")
      .replace(/分账/g, "区分责任")
      .replace(/\s+/g, " ")
      .trim();
  }

  function renderCost(item, record) {
    const publicGrade = costGrade(item);
    const gradeText = [publicGrade.severity, publicGrade.position].filter(Boolean).join(" · ");
    const summary = costPublicText(item.reader_summary);
    return `<article class="context-story net-public-item first-item-card"><div class="component"><span><strong>战争代价${gradeText ? `：${esc(gradeText)}` : ""}</strong><small>严重度越高，代表本人创业／统一窗口内本方军事损失越重</small></span><b>${esc(score(item, "扣"))}</b></div>${summary ? prose(summary) : ""}${ruleDetails([`内部成本档：${item.grade || "未标明"}。`, item.reader_how || ""])}${sourceBlock(item, record, true)}</article>`;
  }

  function renderTotals(items) {
    const byLabel = itemMap(items);
    const a = byLabel["A统一贡献"]?.value;
    const b1 = byLabel["B1创业难度与效率"]?.value;
    const b2 = byLabel["B2组织与整合"]?.value;
    const c = byLabel["C军事统帅与战争解题"]?.value;
    const gross = byLabel["四轴合计"]?.value;
    const cost = byLabel["军事成本扣分"]?.value ?? 0;
    const net = byLabel["第一项净分"]?.value;
    const addOn = byLabel["附加F"]?.value;
    if ([a, b1, b2, c, gross, net, addOn].some(value => value == null)) return "";
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
    if (record.net?.first_item_status !== "APPLICABLE") {
      group.innerHTML = `<div class="first-item-public-v2">${heading}<p class="notice"><strong>本项不适用。</strong>这不代表军事能力差，只表示该人物没有进入建国、复国或统一创业主链的本项加分口径。</p></div>`;
      return;
    }
    const formalName = FORMAL_NAME_ALIASES[record.ruler_name] || record.ruler_name;
    const names = [record.ruler_name, formalName];
    const entries = await Promise.all(Object.entries(DOCS).map(async ([label, ref]) => [label, bullets(await loadDoc(ref, record), names)]));
    if (!group.isConnected || currentRecord()?.ruler_id !== record.ruler_id) return;
    const data = Object.fromEntries(entries);
    const byLabel = itemMap(items);
    const cards = [];
    if (byLabel["A统一贡献"]) cards.push(renderA(byLabel["A统一贡献"], data["A统一贡献"], record));
    if (byLabel["B1创业难度与效率"]) cards.push(renderB1(byLabel["B1创业难度与效率"], data["B1创业难度与效率"], record));
    if (byLabel["B2组织与整合"]) cards.push(renderB2(byLabel["B2组织与整合"], data["B2组织与整合"], record));
    if (byLabel["C军事统帅与战争解题"]) cards.push(renderC(byLabel["C军事统帅与战争解题"], data["C军事统帅与战争解题"], record));
    if (byLabel["军事成本扣分"]?.value != null) cards.push(renderCost(byLabel["军事成本扣分"], record));
    const netScore = Number(byLabel["第一项净分"]?.value);
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
