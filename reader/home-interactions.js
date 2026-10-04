"use strict";

// Formal public fields are shared by the overview and both detail renderers.
// No battle inference, narrative filtering, sorting or truncation belongs here.
function secondMethodDetailsMarkup(item, record) {
  const block = (title, text, className = "") => text
    ? `<details class="${className}"><summary>${esc(title)}</summary>${prose(text)}</details>` : "";
  const refs = [...new Set([item.source, item.applied_source, ...(item.reader_source_refs || [])].filter(Boolean))];
  const sources = refs.map(ref => link(ref, "正式记录与史料 ↗", record)).join(" ");
  return block("范围与边界", item.reader_boundary)
    + block("这个分数怎么算？", item.reader_how)
    + block("正式裁决原文（未改写）", item.reader_full_basis, "net-formal-basis-raw")
    + (sources ? `<details class="net-audit-sources"><summary>正式记录与史料</summary><p class="sources">${sources}</p></details>` : "");
}

function firstPublicText(value) {
  return String(value ?? "")
    .replace(/尚未闭合/g, "尚未形成完整证据")
    .replace(/闭合/g, "完成")
    .replace(/倒灌/g, "追溯计入")
    .replace(/回填/g, "追溯计入")
    .replace(/父链/g, "主链")
    .replace(/准入条件/g, "计入条件")
    .replace(/拆票/g, "拆成多个独立任务")
    .replace(/机械/g, "直接")
    .replace(/按合同/g, "按规则")
    .replace(/合同/g, "规则")
    .replace(/\s+/g, " ")
    .trim();
}

function firstB1Markup(item) {
  const data = item?.reader_public_b1 || {};
  return [["起点", data.public_start_basis], ["主要对手", data.public_opponent_basis], ["完成速度", data.public_efficiency_basis]]
    .filter(([, value]) => value)
    .map(([label, value]) => `<div class="label">${esc(label)}</div>${prose(firstPublicText(value))}`).join("");
}

function firstCostPublicText(value) {
  const severity = ["无显著代价","很低成本","较低成本","中等成本","较高成本","高成本","极高成本","灾难级成本"];
  const chinese = {"零":0,"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7};
  return firstPublicText(value)
    .replace(/现行第三项仍有相关计入，必须同步退出后才启用净分。?/g, "相关战争若已在军事与边疆项计入，本项不重复计算；当前按正式去重后的结果结算。")
    .replace(/跨项证实：/g, "跨项去重：")
    .replace(/由第一项计入/g, "由奠基与统一项计入")
    .replace(/留第三项/g, "留在军事与边疆项")
    .replace(/第([0-7一二三四五六七])级(?:成本)?/g, (_, level) => {
      const index = chinese[level] != null ? chinese[level] : Number(level);
      return severity[index] || level;
    });
}

function firstCostMarkup(item) {
  const data = item?.reader_public_cost || {};
  const publicLevel = firstCostPublicText(data.public_level_label);
  const fields = [["成本程度", publicLevel], ["证据状态", firstCostPublicText(data.public_status_label)], ["责任时期", firstCostPublicText(data.public_responsibility_window)], ["完整成本说明", firstCostPublicText(data.public_basis)]];
  const facts = fields.filter(([, value]) => value).map(([label, value]) => `<div class="label">${esc(label)}</div>${prose(value)}`).join("");
  const gaps = (data.public_unresolved_gaps || []).map(value => `<li>${esc(firstCostPublicText(value))}</li>`).join("");
  const sources = (data.public_source_links || []).filter(source => /^https?:\/\//.test(source.url))
    .map(source => `<a href="${esc(source.url)}" target="_blank" rel="noopener">${esc(source.label)} ↗</a>`).join(" ");
  return `${facts}${gaps ? `<div class="label">证据缺口</div><ul>${gaps}</ul>` : ""}${sources ? `<p class="sources">${sources}</p>` : ""}`;
}

function firstCommanderMarkup(item) {
  const source = item?.reader_public_commander;
  if (!source?.public_basis || !source?.public_boundary || !Array.isArray(source.public_battles)) {
    return '<p class="notice">正式记录未提供本人统帅的公开说明。</p>';
  }
  const battles = source.public_battles.length
    ? `<details class="first-item-battle-evidence"><summary>查看已明确记载的战役与统筹成果</summary><p class="subline">“战役成果”和“任务难度”使用军事材料自己的字母刻度，不是人物画像等级。</p><ul class="first-item-battles">${source.public_battles.map(battle => `<li><strong>${esc(battle.name)}</strong> · ${esc(battle.role)} · 战役成果：${esc(battle.result)} · ${esc(battle.difficulty ? `任务难度：${battle.difficulty}` : '任务难度：未单列')} <a href="military.html#search=${encodeURIComponent(battle.name)}">查看战役档案 ↗</a></li>`).join('')}</ul></details>`
    : '';
  return `<div class="first-item-commander-public"><div class="label">为什么这样评</div>${prose(firstPublicText(source.public_basis))}<div class="label">责任与限制</div>${prose(firstPublicText(source.public_boundary))}${battles}</div>`;
}


(() => {
  const sectionByCell = {
    1: "person-outcome",
    2: "person-capability",
    3: "person-impact",
  };
  const interactiveSelector = "button,a,input,select,textarea,summary,label,[role=button]";

  const netMajorSpecs = {
    all: {
      title: "统治绩效构成",
      description: "四个大项分别展开；先看单人结算逻辑，再看公式，最后才进入原始正式文档。",
      groups: [],
    },
    first: {
      title: "第一项 · 政权奠基与统一",
      description: "先看本人在建国、复国或统一主链里实际做成了什么、面对什么难题、怎样组织与统帅，再看规则怎样把这些事实换成分数。",
      groups: ["first"],
    },
    second: {
      title: "第二项 · 治国成效",
      description: "制度与行政、民生与社会、政权交接共同构成治国成效。",
      groups: ["method", "finance", "handoff"],
    },
    third: {
      title: "第三项 · 军事与边疆",
      description: "战略安全收益、军事体系兑现与军事成本在同一项内结算。",
      groups: ["strategic", "military"],
    },
    fourth: {
      title: "第四项 · 文明与国家整合",
      description: "看本人窗口在共同体、教育人才与知识文化三方面形成的可归责净变化；这是有符号调整，不是文明程度或时代先进程度排名。",
      groups: ["civilization"],
    },
  };

  const netGroupNames = {
    first: "第一项 · 奠基与统一",
    method: "第二项 · 制度与行政",
    finance: "第二项 · 民生与社会",
    handoff: "第二项 · 政权交接",
    strategic: "第三项 · 战略收益与国防",
    military: "第三项 · 军事体系与成本",
    civilization: "文明与国家整合 · 分项结算",
  };

  const netGroupMajor = {
    first: "first",
    method: "second",
    finance: "second",
    handoff: "second",
    strategic: "third",
    military: "third",
    civilization: "fourth",
  };

  const overviewMajorByLabel = {
    "治国成效": "second",
    "治国净收益": "second", // 旧页面/缓存兼容
    "军事与边疆": "third",
    "奠基与统一附加": "first",
    "文明与国家整合": "fourth",
  };

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

  const firstItemDocs = {
    "A统一贡献": "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/01-第一项A统一主链客观贡献正式结算.md",
    "B1创业难度与效率": "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/02-第一项B1创业难度与战略效率正式结算.md",
    "B2组织与整合": "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/03-第一项B2创业组织与政治整合正式结算.md",
    "C军事统帅与战争解题": "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/04-第一项C本人军事统帅与战争解题能力正式结算.md",
  };
  const firstItemFormalNames = {"完颜晟": "完颜吴乞买"};

  const firstItemDocCache = new Map();
  const pendingNetRecords = new Map();
  let netRenderGeneration = 0;

  function recordForRow(row) {
    const id = row.querySelector("[data-person]")?.dataset.person;
    return id ? byId.get(id) : null;
  }

  function scrollWhenReady(section, attempt = 0) {
    if (!section) return;
    requestAnimationFrame(() => {
      const target = document.getElementById(section);
      if (target) {
        target.scrollIntoView({behavior: "smooth", block: "start"});
        return;
      }
      if (attempt < 80) setTimeout(() => scrollWhenReady(section, attempt + 1), 50);
    });
  }

  function openPersonSection(id, section) {
    const encoded = encodeURIComponent(id);
    if (section === "person-outcome") {
      go(`#net/${encoded}/all`);
      return;
    }
    if (section === "person-capability") {
      go(`#person/${encoded}/profile`);
      return;
    }
    if (section === "person-impact") {
      go(`#person/${encoded}/impact`);
      return;
    }
    go("#person/" + encoded);
  }

  function applyPolityFilter(polity) {
    state.polity = polity;
    const select = document.getElementById("polity");
    if (select) select.value = polity;
    renderRows();
  }

  function applyImpactFilter(grade) {
    state.grade = grade;
    const select = document.getElementById("impact-filter");
    if (select) select.value = grade;
    renderRows();
  }

  function enhanceHomeRows() {
    const container = document.getElementById("rows");
    if (!container) return;

    for (const row of container.querySelectorAll("tbody tr")) {
      const record = recordForRow(row);
      if (!record) continue;

      row.classList.add("home-click-row");
      row.dataset.homePerson = record.ruler_id;
      const cells = row.cells || row.querySelectorAll("td");

      for (const [index, section] of Object.entries(sectionByCell)) {
        const cell = cells[Number(index)];
        if (!cell) continue;
        if (section === "person-outcome" && !record.net) continue;
        if (section === "person-capability" && record.supplementary) continue;
        cell.classList.add("home-jump-cell");
        cell.dataset.homeSection = section;
        cell.tabIndex = 0;
        cell.setAttribute("role", "link");
        const label = section === "person-outcome" ? "统治绩效" : section === "person-capability" ? "人物画像" : "历史影响";
        cell.setAttribute("aria-label", `查看${personLabel(record)}的${label}`);
      }

      const identityCell = cells[0];
      identityCell?.classList.add("home-person-cell");
      const meta = identityCell?.querySelector("small");
      if (meta && !meta.querySelector("[data-home-polity]")) {
        meta.textContent = "";
        const polity = document.createElement("button");
        polity.type = "button";
        polity.className = "inline-table-filter";
        polity.dataset.homePolity = record.polity;
        polity.textContent = record.polity;
        polity.title = `只看${record.polity}`;
        meta.append(polity, document.createTextNode(` · 掌权背景：${record.actual_power_window || "未列"}`));
      }

      const grade = cells[3]?.querySelector(".impact-grade");
      if (grade && !grade.hasAttribute("data-home-grade")) {
        grade.dataset.homeGrade = record.impact.public_grade;
        grade.setAttribute("role", "button");
        grade.tabIndex = 0;
        grade.title = `只看历史影响 ${record.impact.public_grade}`;
      }
    }
  }

  function ensureNetStyles() {
    if (document.getElementById("net-detail-interactions-style")) return;
    const style = document.createElement("style");
    style.id = "net-detail-interactions-style";
    style.textContent = `
      .net-overview-jump{display:flex;align-items:center;justify-content:space-between;gap:12px;width:100%;color:inherit;text-decoration:none}
      .net-overview-jump:hover strong,.net-overview-jump:hover span:first-child{color:var(--green)}
      .net-overview-jump small{display:block;margin-top:2px;font-size:11px;color:var(--green)}
      .net-summary-group{margin:0;padding:12px 0}
      .net-summary-group>summary{font-size:15px}
      .net-summary-group .component{margin:9px 0;font-size:13px}
      .net-detail-page{max-width:1040px;margin:26px auto}
      .net-detail-head{margin:8px 0 18px}
      .net-major-nav{position:sticky;top:0;z-index:6;display:flex;gap:10px;padding:10px 12px;margin:0 0 20px;background:#eeefe7;border:1px solid var(--line);border-radius:5px;overflow-x:auto;white-space:nowrap}
      .net-major-nav a{padding:5px 8px;border-radius:4px;text-decoration:none}
      .net-major-nav a.active{background:var(--ink);color:white}
      .net-major-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
      .net-major-card{display:block;color:inherit;text-decoration:none}
      .net-major-card h2{margin-top:0}.net-major-card .big{font-size:36px}
      .net-metric-detail{border:1px solid var(--line);border-radius:6px;padding:0;margin:12px 0;background:#fcfbf7}
      .net-metric-detail>summary{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:14px;padding:14px 38px 14px 14px;margin:0}
      .net-metric-detail>summary small{display:block;margin-top:3px;font-weight:400}
      .net-metric-detail>summary b{font:20px Georgia,serif;color:var(--green)}
      .net-metric-body{padding:0 16px 16px}
      .net-formal-level{color:var(--green)!important;font-weight:600!important}
      .net-material-list{list-style:none;margin:8px 0 12px;padding:0;display:grid;gap:8px}
      .net-material-card{margin:0;padding:11px 12px;border:1px solid var(--line);border-radius:5px;background:#fff}
      .net-material-head{display:flex;align-items:flex-start;justify-content:space-between;gap:8px;flex-wrap:wrap}
      .net-material-head>strong{font-size:14px;line-height:1.55}
      .net-material-meta{display:flex;align-items:center;justify-content:flex-end;gap:5px;flex-wrap:wrap}
      .net-material-chip{display:inline-block;padding:1px 6px;border:1px solid var(--line);border-radius:999px;font-size:10px;line-height:1.6;color:var(--muted);font-weight:700;background:#f4f5ef}
      .net-material-body{margin:7px 0 0!important;font-size:12px!important;line-height:1.78!important}
      .net-material-boundary{margin-top:7px!important;padding-top:6px!important}
      .net-material-boundary>summary{font-size:11px!important;color:var(--muted)}
      .net-material-boundary>p{margin:5px 0 0;font-size:11px;line-height:1.7}\n      .net-source-coverage-note{margin:3px 0 8px!important}\n      .net-material-summary{margin:10px 0 0}\n      .net-material-summary>summary{font-size:12px;color:var(--muted)}
      .net-overall-boundary{margin:10px 0 0}
      .net-overall-boundary>summary{font-size:12px;color:var(--muted)}
      .net-overall-boundary>.prose{margin-top:7px}
      .net-audit-sources{margin-top:14px}
      .net-audit-sources>.subline{margin-top:6px}
      .net-detail-group{margin:0 0 20px}.net-detail-group>h2{margin-top:0}
      .net-detail-total{border-left:3px solid var(--green);padding:12px 16px;background:#eef1ea;margin-top:18px}
      .first-item-overview{border:1px solid var(--line);border-left:4px solid var(--green);border-radius:7px;padding:18px;margin-bottom:16px;background:#f6f7f1}
      .first-item-overview h2{font-size:22px;margin:0 0 6px}.first-item-overview>.subline{margin-bottom:12px}
      .first-item-story-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
      .first-item-story-card{padding:12px 14px;border:1px solid var(--line);border-radius:5px;background:#fcfbf7;min-width:0}
      .first-item-story-card.wide{grid-column:1/-1}.first-item-story-card>b{display:block;color:var(--green);margin-bottom:5px}
      .first-item-story-card p{margin:4px 0;font-size:13px;line-height:1.75}.first-item-story-card ul{margin:5px 0;padding-left:18px;font-size:13px;line-height:1.75}
      .first-item-scoreline{margin-top:12px;padding-top:11px;border-top:1px solid var(--line);font-size:14px;line-height:1.75;overflow-wrap:anywhere}.first-item-scoreline strong{color:var(--green)}
      .first-item-scope{margin:12px 0 16px;padding:10px 0}.first-item-rule-box{margin-top:14px}
      .first-item-rule-box>summary{font-size:13px;color:var(--muted)}
      .net-material-card,.net-material-head>strong,.net-material-body,.net-material-boundary>p{overflow-wrap:anywhere}
      .net-third-basis-list{margin:8px 0 0;padding-left:18px;font-size:12px;line-height:1.75}
      .net-third-basis-list li{margin:4px 0}
      .net-third-subgroup{margin:18px 0 0}
      .net-third-subgroup+.net-third-subgroup{margin-top:24px;padding-top:20px;border-top:1px solid var(--line)}
      .net-third-subgroup>h3{margin:0 0 4px;font-size:17px}
      .net-third-subgroup-note{margin:0 0 10px}
      .net-third-total{margin-top:24px;padding-top:16px;border-top:1px solid var(--line)}
      .net-score-how{margin-top:12px}
      .net-score-how>summary{font-size:12px;color:var(--muted)}
      .net-score-how dl{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:5px 10px;margin:8px 0 0;font-size:12px;line-height:1.7}
      .net-score-how dt{color:var(--muted);font-weight:700}
      .net-score-how dd{margin:0}
      @media(max-width:700px){
        .net-major-grid{grid-template-columns:1fr}
        .net-major-nav{gap:5px}
        .net-metric-detail>summary{grid-template-columns:minmax(0,1fr);gap:5px}
        .net-metric-detail>summary b{justify-self:start}
        .net-material-card{padding:10px}
        .net-material-head{display:block}
        .net-material-meta{justify-content:flex-start;margin-top:6px}
        .net-material-chip{white-space:normal;overflow-wrap:anywhere}
        .first-item-story-grid{grid-template-columns:1fr}
        .first-item-story-card.wide{grid-column:auto}
      }
    `;
    document.head.append(style);
  }

  function netValue(item, groupKey = "") {
    if (item?.value == null) return item?.unit === "不单独计分" ? "参与合成，不单列分值" : "—";
    if (groupKey === "strategic" && item.unit === "%" && ["B1","B2","B4"].includes(item.label)) {
      return `合成采用 ${Number(item.value)}%`;
    }
    const signed = item.value > 0 && groupKey === "civilization" ? `+${item.value}` : String(item.value);
    return `${signed}${item.unit ? ` ${item.unit}` : ""}`;
  }

  function majorValue(record, major) {
    const net = record.net || {};
    if (major === "first") return net.first_item_status === "APPLICABLE" ? net.first_item_add_on : null;
    if (major === "second") return net.second_item_score;
    if (major === "third") return net.third_item_score;
    if (major === "fourth") return net.fourth_item_adjustment;
    return net.total_score;
  }

  function finiteNetNumber(value) {
    if (value == null || value === "") return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function fourthAdjustmentNote(record) {
    const axes = (record.net?.component_details?.civilization || [])
      .filter(item => item.label !== "第四项调整" && finiteNetNumber(item.value) != null);
    const hasPositive = axes.some(item => finiteNetNumber(item.value) > 0);
    const hasNegative = axes.some(item => finiteNetNumber(item.value) < 0);
    const hasBalancedZero = axes.some(item => /^BALANCED\s*\/\s*CIV0$/i.test(String(item.grade || "").trim()));
    const hasNoIndependentChange = axes.some(item => /^NO_ELIGIBLE/i.test(String(item.grade || "").trim()));
    const adjustment = finiteNetNumber(record.net?.fourth_item_adjustment);
    if (adjustment === 0 && hasPositive && hasNegative) {
      return "本项总调整为0：存在正向与负向分轴，合计后相抵；0不代表各轴都没有变化。";
    }
    if (adjustment === 0 && hasBalancedZero && hasNoIndependentChange) {
      return "本项总调整为0：部分分项的已确认正负变化相抵，其余分项未确认可单独计入的净变化；这些0的来源并不相同。";
    }
    if (adjustment === 0 && hasBalancedZero) {
      return "本项总调整为0：至少一个分项存在已确认的正负变化，但在该分项内净算后相抵；0不等于没有变化。";
    }
    if (adjustment === 0 && hasNoIndependentChange) {
      return "本项总调整为0：当前分项未确认可单独计入的净变化；0不表示相关领域没有史料，只表示没有形成独立有符号调整。";
    }
    return "三个分项合计范围为 -67.5～+67.5；正负值直接计入统治绩效总分。";
  }

  function netHref(record, major = "all", focus = "") {
    const suffix = focus ? `/${encodeURIComponent(focus)}` : "";
    return `#net/${encodeURIComponent(record.ruler_id)}/${major}${suffix}`;
  }

  function currentPersonRecord() {
    const match = location.hash.match(/^#person\/([^/?#]+)/);
    if (!match) return null;
    return byId.get(decodeURIComponent(match[1])) || null;
  }

  function netEvidenceSection() {
    return Array.from(document.querySelectorAll("#person-evidence > section.panel")).find(section => {
      const heading = section.querySelector(":scope > h2, :scope > h3");
      return ["统治绩效构成", "净收益构成"].includes(heading?.textContent.trim());
    }) || null;
  }

  function enhanceNetOverview(record) {
    const panel = document.getElementById("person-outcome");
    if (!panel || !record?.net || panel.dataset.netLinks === "done") return;

    for (const row of panel.querySelectorAll(":scope > .component")) {
      const span = row.querySelector("span");
      const label = span?.textContent.trim() || "";
      const major = Object.entries(overviewMajorByLabel)
        .find(([publicLabel]) => label === publicLabel || label.startsWith(publicLabel + " "))?.[1];
      if (!major) continue;
      const anchor = document.createElement("a");
      anchor.className = "net-overview-jump";
      anchor.href = netHref(record, major);
      anchor.setAttribute("aria-label", `查看${record.ruler_name}的${label}计分逻辑`);
      while (row.firstChild) anchor.append(row.firstChild);
      const text = anchor.querySelector("span");
      if (text && !text.querySelector("small")) {
        const hint = document.createElement("small");
        hint.textContent = "查看计分逻辑 →";
        text.append(hint);
      }
      row.append(anchor);
    }

    const sourceLink = panel.querySelector(":scope > p.sources a");
    if (sourceLink) {
      sourceLink.href = netHref(record, "all");
      sourceLink.textContent = "查看完整统治绩效详情 →";
    }
    panel.dataset.netLinks = "done";
  }

  const FIRST_COMPACT_LABELS = {
    "A统一贡献": "统一成果",
    "B1创业难度与效率": "起点、强敌与速度",
    "B2组织与整合": "创业组织与政治整合",
    "C军事统帅与战争解题": "本人统帅",
    "军事成本扣分": "军事代价",
  };
  const NET_PUBLIC_LABELS = {
    ...FIRST_COMPACT_LABELS,
    "A制度建设": "制度建设与实际运行",
    "B1官僚治理": "官僚治理与行政执行",
    "B2反馈与约束": "反馈纠错与权力约束",
    "C1民生": "民生状况",
    "C2经济财政": "经济与财政",
    "C3社会安全": "社会安全",
    "C4恢复与成本": "恢复能力与额外代价",
    "D1继任行政连续性": "继任后的行政连续性",
    "D3政权交接稳定": "政权交接稳定性",
  };
  function publicNetComponentLabel(item) {
    return item?.public_component_label || NET_PUBLIC_LABELS[item?.label] || item?.label || "";
  }

  function compactNetPublicLabel(item, key) {
    return publicNetComponentLabel(item);
  }

  function compactNetPublicValue(item, key) {
    if (key === "first" && item?.label === "军事成本扣分" && finiteNetNumber(item?.value) != null) {
      return `扣 ${item.value} 分`;
    }
    const raw = netValue(item, key);
    if (key === "strategic" || key === "military") {
      const status = thirdItemPublicText(item, item?.public_level_label || "");
      if (!status) return raw;
      if (item?.value == null || item?.unit === "不单独计分") return status;
      return `${status} · ${raw}`;
    }
    if (key === "civilization") {
      const status = civilizationPublicStatus(item, item?.public_level_label || "");
      if (!status) return raw;
      const value = finiteNetNumber(item?.value);
      if (value === 0 && (status.includes("净调整为0") || status.includes("没有确认独立变化"))) return status;
      return `${status} · ${raw}`;
    }
    return raw;
  }

  function compactNetReading(record) {
    const section = netEvidenceSection();
    if (!section) return;
    let reading = section.querySelector(".net-reading");
    if (reading?.dataset.netCompact === "done") return;
    const groups = Object.entries(record.net?.component_details || {});
    if (!groups.length) return;

    if (!reading) {
      reading = document.createElement("div");
      reading.className = "net-reading";
      const heading = section.querySelector(":scope > h2, :scope > h3");
      if (heading) heading.after(reading);
      else section.prepend(reading);
    }
    reading.innerHTML = `<p class="reading-intro">这里保留各大项的快速摘要。完整的逐人判断、变量、公式和计分来源放到独立统治绩效详情页，避免单人主页无限变长。</p><p class="sources"><a href="${netHref(record, "all")}">打开完整统治绩效详情 →</a></p>`;

    for (const [key, items] of groups) {
      if (!Array.isArray(items)) continue;
      const details = document.createElement("details");
      details.className = "net-summary-group";
      const major = netGroupMajor[key] || "all";
      const judgments = items.filter(item => item.reader_kind === "judgment" && (item.value != null || item.unit === "不单独计分" || item.public_level_label));
      const firstStatus = key === "first" ? record.net?.first_item_status : "";
      const preview = firstStatus === "NOT_APPLICABLE"
        ? `<p class="notice">该人物不适用第一项，本项不参与统治绩效计分。</p>`
        : key === "first" && firstStatus !== "APPLICABLE"
          ? `<p class="notice">第一项正式适用状态尚未发布，因此不作适用性推断。</p>`
          : judgments.map(item => `<div class="component"><span>${esc(compactNetPublicLabel(item, key))}</span><b>${esc(compactNetPublicValue(item, key))}</b></div>`).join("");
      details.innerHTML = `<summary>${esc(netGroupNames[key] || key)}</summary>${preview}<p class="sources"><a href="${netHref(record, major, key)}">查看这组完整计分逻辑 →</a></p>`;
      reading.append(details);
    }
    reading.dataset.netCompact = "done";
    // The person page is summary-only. Remove the legacy raw calculation folds
    // that were already emitted by the base template; the independent #net page
    // remains the single full calculation surface.
    for (const node of Array.from(section.children)) {
      if (node.tagName === "DETAILS") node.remove();
    }
    section.dataset.netReadable = "done";
  }

  function enhancePersonNet() {
    const record = currentPersonRecord();
    if (!record?.detail_loaded) return;
    enhanceNetOverview(record);
    compactNetReading(record);
  }

  function cleanNetText(value) {
    return String(value ?? "").replace(/\s+/g, " ").trim();
  }

  function uniqueSourceRefs(item) {
    const refs = Array.isArray(item.reader_source_refs) ? item.reader_source_refs : [];
    return [...new Set([item.source, item.applied_source, ...refs].filter(Boolean))];
  }

  function auditSourceBlock(item, record) {
    const refs = uniqueSourceRefs(item);
    if (!refs.length) return "";
    const links = refs.map((ref, index) => {
      const label = ref === item.applied_source && ref !== item.source
        ? "采用值原始记录 ↗"
        : index === 0 ? "原始正式文档 ↗" : `补充史料／记录 ${index} ↗`;
      return link(ref, label, record);
    }).join(" ");
    return `<details class="net-audit-sources"><summary>正式文档与史料</summary><p class="subline">这些链接指向整份正式文件，供读者核对；上面的当前人物事实才是正文。</p><p class="sources">${links}</p></details>`;
  }

  const MATERIAL_CARD_GROUPS = new Set(["strategic", "military", "civilization"]);
  const THIRD_PUBLIC_GRADE = {0:"E",1:"D",2:"C",3:"B",4:"A",5:"S"};
  const THIRD_COST_SEVERITY = {
    0:"无实质军事成本",
    1:"局部常规军事成本",
    2:"有限军事成本",
    3:"明显军事成本",
    4:"大规模或持续显著军事成本",
    5:"严重军事成本",
    6:"极端军事成本",
    7:"灾难性军事耗竭",
  };
  const THIRD_CN_LEVEL = {"零":0,"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7};

  function thirdGradeText(level) {
    const n = Number(level);
    return Number.isInteger(n) && THIRD_PUBLIC_GRADE[n] ? `${THIRD_PUBLIC_GRADE[n]}档` : String(level);
  }

  function thirdCostText(level) {
    const n = typeof level === "string" && THIRD_CN_LEVEL[level] != null ? THIRD_CN_LEVEL[level] : Number(level);
    return Number.isInteger(n) && THIRD_COST_SEVERITY[n] ? THIRD_COST_SEVERITY[n] : String(level);
  }

  function thirdPublicText(value, itemLabel = "") {
    let text = cleanNetText(value);
    if (!text) return "";
    const isCost = itemLabel === "普通成本扣分" || itemLabel === "ML扣分";
    text = text
      .replace(/已核对\d+项独立任务，其中较好结果\d+项、低回报\d+项、负向结果\d+项。?/g, "")
      .replace(/父周期仅完成边界证实，任务成员与独立父周期结构未变；没有产生新的升降档理由。?/g, "")
      .replace(/河西树机能270、277、279三票归为同一连续父周期，7项降至5项；?/g, "河西树机能270、277、279三次相关行动归为同一连续任务周期；")
      .replace(/278西陵独立突袭由证据不足证据支持评为低回报/g, "278年西陵独立突袭现有证据仅支持判断为低回报")
      .replace(/本批父周期边界未改变足以影响三轴的事实基础，正式横校沿用正式三轴\/既有能力专用判断。?/g, "重新核对任务边界后，三方面事实基础未变，现有等级维持不变。")
      .replace(/前129—前119五条汉匈主战阶段合为一个连续父周期，19票降至15票。河西、漠北等阶段价值与成本必须在父级重新裁任务回报类别，不能再按五票累计；但剩余任务厚度、重大成功与重大失败证据仍足以维持军事体系整体第三级正式横校档。?/g, "前129—前119年汉匈主战阶段按同一连续任务周期合并判断，河西、漠北等阶段不重复累计；其余任务厚度与重大成败证据仍支持军事体系整体B档。")
      .replace(/\d+票(?:降至|升至)\d+票/g, "相关任务按统一边界重新归并")
      .replace(/父级重新裁任务回报类别/g, "在合并后的任务周期重新判断整体回报")
      .replace(/正式横校档/g, "当前等级")
      .replace(/正式横校/g, "交叉核对")
      .replace(/战略链化/g, "按战略主链归并")
      .replace(/本次重做撤销上一版近1:1链化；以\d+条战略链为评分单元，父任务只作证据下钻；三轴与整体水平经复核不变。?/g, "多个具体任务按战略主链归并，避免把同一主链拆成重复计分。")
      .replace(/复裁撤销前166\/162\/158过度合并：三轮均已各自证实，前162还以再和亲形成明确周期终点；仅将前162年汉匈战争重绑至其战役群。?/g, "前166、前162、前158三轮边患分别有独立材料；前162另有再和亲作为阶段终点。")
      .replace(/旧“北方36—46”宽父拆为卢芳—匈奴、乌桓、鲜卑三个独立压力对象，6票升至8票。拆分不是加功，反而要求分别复核回报；?/g, "北方压力按卢芳—匈奴、乌桓、鲜卑三个独立对象分别核对；拆分仅用于避免混并，不额外增加得分。")
      .replace(/规模与控制强度：西北0\.8继承；统一后北方边郡0\.8仅作客观库存；河南地—朔方新增0\.6、岭南新增0\.8；删除旧西南0\.5与1\.05非标准草原包。?/g, "河南地—朔方与岭南的新增控制计入本项；继承存量及未达到正式标准的控制包不重复计算。")
      .replace(/规模与控制强度：废止‘1206—1227新增整链一律归第一项’的形式节点切法；只排除灭夏终局0\.8及攻金遗留控制0\.5，花剌子模—中亚—西亚4\.25保留在第三项，机械落实际控制范围第4级 中位。?/g, "统一主链中已由第一项承担的灭夏终局与攻金遗留控制不重复计入；花剌子模—中亚—西亚的控制成果保留在本项。")
      .replace(/规模与控制强度：旧账把东北等后期新增预埋进起点值，同时把本土海岸1\.0误计实际控制范围；重建后仅保留可独立证实的松外增量。?/g, "只计本人窗口内可独立证实的松外新增控制；后期新增与本土海岸存量不重复算作本人控制增量。")
      .replace(/规模与控制强度：实际控制范围全量复核已确认最终同级率。?/g, "当前正式材料支持维持这一控制范围等级。")
      .replace(/终点值由-?\d+(?:\.\d+)?修正为-?\d+(?:\.\d+)?，净变化由-?\d+(?:\.\d+)?修正为-?\d+(?:\.\d+)?，加权值由-?\d+(?:\.\d+)?修正为-?\d+(?:\.\d+)?；实际控制范围由第([一二三四五0-5])级(高位|中位|低位)的\d+(?:\.\d+)?调整为第([一二三四五0-5])级(高位|中位|低位)的\d+(?:\.\d+)?。?/g, (_, from, fromPos, to, toPos) => `重新核对本人窗口内的实际控制范围后，当前判断由${thirdGradeText(THIRD_CN_LEVEL[from] ?? from)}${fromPos}调整为${thirdGradeText(THIRD_CN_LEVEL[to] ?? to)}${toPos}。`)
      .replace(/规模与控制强度：数值不变；旧标识规范化。?/g, "当前正式材料支持维持这一控制范围等级。")
      .replace(/承接北方边郡遗漏修正：起点值\s*5\.8→6\.6，加权值\s*-3\.48→-3\.96；终局门下档位与得分率不变。?/g, "补齐北方边郡材料后，政权终结这一结论不变，因此控制范围等级仍维持当前判断。")
      .replace(/终局门覆盖任内阶段性占领或扩域尝试。?/g, "政权终结后，任内阶段性占领或扩域尝试不作为可移交成果。")
      .replace(/终局门命中；?/g, "政权终结，因此")
      .replace(/规模与控制强度：数值不变；北方边疆规范化。?/g, "北方边疆作为本项主要控制范围依据。")
      .replace(/规模与控制强度：数值不变；补齐逐区域账。?/g, "按各区域实际控制情况核对。")
      .replace(/规模与控制强度：数值不变；交趾、河西陇右、北方边郡均改为规范锚。?/g, "交趾、河西陇右与北方边郡作为本项主要控制范围依据。")
      .replace(/规模与控制强度：数值与得分率不变；旧唐代河西—陇右规范化为河西—陇右走廊。?/g, "河西—陇右走廊作为本项主要控制范围依据。")
      .replace(/原正式控制规模值为\d+(?:\.\d+)?，实际采用值为\d+(?:\.\d+)?；统一参照点后，客观加权值为\d+(?:\.\d+)?，对应正式值应为\d+(?:\.\d+)?，但第三项有效采用比例仍为0。?/g, "相关控制成果已在奠基与统一项计入，本项不再重复计入。")
      .replace(/旧1\.3→1\.3混淆西南与交州，并漏记北方边郡和启民属部。重建客观库存为2\.4→4\.2；其中602交州0\.8作为统一尾链由第一项计入，第三项有效加权值=2\.76-0\.8=1\.96，实际控制范围率44→60。?/g, "重新核对西南、交州、北方边郡与启民部后，本人窗口内实际控制范围有明显扩大；602年交州属于统一尾链，已由奠基与统一项计入，本项不重复计算。")
      .replace(/旧账错误按靖康覆亡把赵佶终点值直接清零，采用比例29；修正终局时点并保留西北真实扩张后升至60。?/g, "按赵佶实际退位时点判断，不把1127年的靖康覆亡倒推到1126年；退位前已经形成的西北控制成果仍计入。")
      .replace(/有效率仍0，但旧0→0改为0\.725→0，真实表达终局退控。?/g, "任期内实际控制继续收缩，并在政权终结时归零。")
      .replace(/仍为0，但从错误0→0重建为真实\d+(?:\.\d+)?→0的大规模边疆退控。?/g, "重新核对后，确认任内发生大规模边疆退控并最终归零。")
      .replace(/旧0\.65→2\.1使用安南临时0\.5尺度；规范后0\.8→2\.4，加权值\s*1\.71→1\.92，得分率仍60。?/g, "按统一口径重新核对安南及相关边疆控制后，当前控制范围等级不变。")
      .replace(/规模与控制强度：旧账仅以1\.3→0并启用按终局崩溃强制清零。现改为从杨坚真实4\.2交班库存逐区域核退出；吐谷浑、伊吾阶段新增另存峰值但不进入618终点。最终实际控制范围率仍0，但不是由终局标签强制清零。?/g, "按杨坚交班时的实际控制存量逐区域核对；吐谷浑、伊吾虽有阶段新增，但至618年均未形成可保留的终点控制，因此实际控制范围归零。")
      .replace(/执行终局门后/g, "按政权终结时的实际控制结果判断后")
      .replace(/依终局门归零/g, "因政权终结且无可移交成果而归零")
      .replace(/本人可本人责任主干/g, "本人可归责的主干成果")
      .replace(/跨阶梯变化/g, "跨公开等级变化")
      .replace(/真实\d+(?:\.\d+)?边疆库存/g, "既有边疆控制存量")
      .replace(/不使用终局\s*强制修正/g, "按政权终结时的实际控制结果判断")
      .replace(/统一执行终局门/g, "按政权终结时的实际控制结果判断")
      .replace(/依全包及主要方向封顶维持/g, "综合全部方向后维持")
      .replace(/按用户冻结规则/g, "按当前固定口径")
      .replace(/按军事体系整体第([0-5])级重大胜绩硬门封顶军事体系整体第([0-5])级。?/g, (_, ceiling, actual) => `尚未达到${thirdGradeText(ceiling)}所需的重大体系胜绩条件，军事体系整体维持${thirdGradeText(actual)}。`)
      .replace(/正式军事体系按\d+条当前任务与\d+条仅作能力证据支撑三轴([0-5])档/g, (_, level) => `现有正式任务与补充能力证据共同支持三方面均为${thirdGradeText(level)}`)
      .replace(/当前第三项成本清单将其标记为不适用。?/g, "当前本项不单独结算军事代价。")
      .replace(/故客观变动[+-]?\d+档，第三项可本人责任变动取0档。?/g, "客观状态确有改善，但相关创业统一主链已由奠基与统一项计入，本项不再重复计算本人收益。")
      .replace(/得分率不变；删除长江内线伪实际控制范围对象，改用淮河、荆湖北缘、川陕三个真实外部边疆扇区。?/g, "重新核对后，只把淮河、荆湖北缘和川陕三个真实外部边疆方向计入实际控制范围。")
      .replace(/固定父卡将/g, "正式任务记录将")
      .replace(/战略安全净变化链亦裁定/g, "相关正式材料也认定")
      .replace(/战略安全净变化底账/g, "相关正式记录")
      .replace(/当前军事体系项无独立体系压力父周期；本人物现档来自能力专用\/完整任期无压力等既有路由，父周期归并没有新增输入。?/g, "当前没有可与创业统一主链分离的独立体系压力任务；现有等级主要依据能力证据与完整任期表现，任务归并未改变判断。")
      .replace(/同链安全态势\/控制成果\/战略安全净变化退出，仅留军事体系\s*仅作能力证据/g, "同一主链的安全态势和控制成果不在本项重复计入；相关战事只保留为军事体系能力证据")
      .replace(/按当前评定用户指定范围，不重新审查该状态的跨项来源；只确认没有独立军事体系档需要重新定级。?/g, "相关战争成本已按评价边界在其他项目处理，本项不重复结算。")
      .replace(/父卡/g, "正式任务记录")
      .replace(/不生成本人改善信用/g, "不计为本人改善成果")
      .replace(/战略安全净变化链亦记皇帝具体成果责任未建立/g, "现有材料也未能确认皇帝本人对这一改善承担明确成果责任")
      .replace(/剥离创业统一重复计分后/g, "扣除已经由奠基与统一项承担的创业统一成果后")
      .replace(/并通过军事体系整体第([0-5])级条件/g, (_, level) => `并达到军事体系整体${thirdGradeText(level)}所需条件`)
      .replace(/早期\d+条仅保留能力证据/g, "早期相关任务只作为能力证据")
      .replace(/回灌/g, "重复计入")
      .replace(/关键证据仍有缺口缺口保留/g, "关键证据仍有缺口")
      .replace(/轴5必须由第三项本体重大体系胜绩复验/g, "S档必须由本项自身的重大体系胜绩再次验证")
      .replace(/第三项军事体系军事体系正证/g, "本项军事体系的正向证据")
      .replace(/军事体系军事体系/g, "军事体系")
      .replace(/第三项本体/g, "本项自身")
      .replace(/第三项(?!现期)/g, "本项")
      .replace(/第一项/g, "奠基与统一项")
      .replace(/最终([0-5])\/\1\/\1、军事体系整体第\1级。?/g, (_, level) => `三方面均为${thirdGradeText(level)}。`)
      .replace(/军事体系整体第([0-5])级维持\d+/g, (_, level) => `军事体系整体维持${thirdGradeText(level)}`)
      .replace(/重大失败不是独立倍增计票/g, "重大失败不会因事件拆分而重复加重判断")
      .replace(/不重复计算安全态势项宏观边疆态势/g, "不重复计算已经在安全态势中判断的宏观边疆变化")
      .replace(/正式摘要明确本方兵团对象、分母和(\d{4})本人重大决策责任已证实，核心兵团毁损分母仍缺/g, "现有材料已能确认本方兵团对象与$1年的本人重大决策责任，但核心兵团总量及毁损比例仍缺直接证据")
      .replace(/两路径复核/g, "升级条件核对")
      .replace(/内部链覆盖缺口/g, "材料覆盖缺口")
      .replace(/已过([^；。]{1,28})门/g, "已达到$1所需条件")
      .replace(/补门/g, "补足该条件")
      .replace(/不上推/g, "不提高到")
      .replace(/底账/g, "正式记录")
      .replace(/旧账/g, "此前记录")
      .replace(/现行贡献类型为/g, "当前成果类型为")
      .replace(/本包事实/g, "本项已经确认的事实")
      .replace(/控制包/g, "控制成果")
      .replace(/重复交付与恢复/g, "多次维持并在受压后恢复")
      .replace(/按压力保全上限裁/g, "受重大压力下保全的等级上限约束，")
      .replace(/。[^。]{0,16}\s+主要安全威胁与战略主动（主要威胁能力与战略主动）本人责任判断：/g, "。")
      .replace(/。[^。]{0,16}\s+防线协同与战略纵深（边界、门户、纵深与缓冲体系）本人责任判断：/g, "。")
      .replace(/维持主要本人责任0\.75/g, "维持本人主要责任")
      .replace(/本人对后续(恶化|改善)主要本人责任[+-]?\d+(?:\.\d+)?档。?/g, (_, direction) => `本人对后续${direction}承担主要责任。`)
      .replace(/主导国家层面的网络建设，取1；/g, "主导国家层面的网络建设，按本人主要责任计入；")
      .replace(/当前结果先得到\s*[\d.]+%\s*的得分率，合成时采用\s*([\d.]+)%。?/g, "当前等级进入合成时采用 $1%。")
      .replace(/档位(?:和|与)得分率不变/g, "档位和合成比例不变")
      .replace(/得分率/g, "合成比例")
      .replace(/不把([^，。；]+?)损失回填十万或核心门/g, "不把$1任内损失计入本人，也不据此补足更高成本条件")
      .replace(/不回填([^，。；]+)/g, "不把$1重复计入本人")
      .replace(/核心门/g, "更高成本条件")
      .replace(/回填/g, "重复计入")
      .replace(/[，；,;]?故客观变动[+-]?\d+档中取[+-]?\d+(?:\.\d+)?档。?/g, "。")
      .replace(/军事成本为第([0-7一二三四五六七])级(高位|中位|低位|极端上沿)/g, (_, level, position) => `军事成本为${thirdCostText(level)}、${position}`)
      .replace(/军事成本(?:达到)?第([0-7一二三四五六七])级/g, (_, level) => thirdCostText(level))
      .replace(/军事成本第([0-7一二三四五六七])级/g, (_, level) => thirdCostText(level));
    if (isCost) {
      text = text.replace(/第([0-7一二三四五六七])级/g, (_, level) => thirdCostText(level));
    } else {
      text = text
        .replace(/第([0-5])级/g, (_, level) => thirdGradeText(level))
        .replace(/第([一二三四五])级/g, (_, level) => thirdGradeText(THIRD_CN_LEVEL[level]));
    }
    text = text
      .replace(/由([0-5])档升至([0-5])档/g, (_, from, to) => `由${thirdGradeText(from)}升至${thirdGradeText(to)}`)
      .replace(/(?<![\d.])([0-5])→([0-5])档/g, (_, from, to) => `${thirdGradeText(from)}→${thirdGradeText(to)}`)
      .replace(/(?<![\d.])([0-5])→([0-5])(?![\d.])/g, (_, from, to) => `${thirdGradeText(from)}→${thirdGradeText(to)}`)
      .replace(/三轴(?:维持)?([0-5])\/\1\/\1/g, (_, level) => `三方面均为${thirdGradeText(level)}`)
      .replace(/(支持|阻断|维持|压至|达到)([0-5])档/g, (_, verb, level) => `${verb}${thirdGradeText(level)}`)
      .replace(/([0-5])档(高位|中位|低位)/g, (_, level, position) => `${thirdGradeText(level)}${position}`)
      .replace(/([一二三四五六七])档本人改善/g, (_, count) => `${count}个等级的本人改善`)
      .replace(/(实战任务交付|持续作战与任务承载|军事体系可靠性)=([0-5])/g, (_, label, level) => `${label}为${thirdGradeText(level)}`)
      .replace(/(实战任务交付|持续作战与任务承载|军事体系可靠性)维持([0-5])/g, (_, label, level) => `${label}维持${thirdGradeText(level)}`)
      .replace(/故?客观变动[+-]?\d+档按[+-]?\d+档本人责任/g, "相应状态变化按本人责任计入")
      .replace(/第三项独立计入/g, "本项计入")
      .replace(/第三项独立方向/g, "本项")
      .replace(/第三项只读/g, "本项只计")
      .replace(/(实际控制范围|战略成果价值|控制成果稳定性)为当前结果为/g, "$1当前为")
      .replace(/\bA1主要安全威胁与战略主动/g, "主要安全威胁与战略主动")
      .replace(/\bA2防线协同与战略纵深/g, "防线协同与战略纵深")
      .replace(/\bB1实际控制范围/g, "实际控制范围")
      .replace(/\bB1控制规模/g, "控制范围")
      .replace(/\bB2战略成果价值/g, "战略成果价值")
      .replace(/\bB2战略价值/g, "战略价值")
      .replace(/\bB4控制成果稳定性/g, "控制成果稳定性")
      .replace(/\bB4交班成熟度/g, "成果稳定性")
      .replace(/\bA1\b/g, "主要安全威胁")
      .replace(/\bA2\b/g, "防线与纵深")
      .replace(/\bB1\b/g, "控制范围")
      .replace(/\bB2\b/g, "战略价值")
      .replace(/\bB4\b/g, "成果稳定性")
      .replace(/三轴/g, "三方面")
      .replace(/父周期仅完成边界证实，任务成员与独立父周期结构未变；没有产生新的升降档理由。?/g, "复核后，既有任务边界与独立任务划分不变；没有新增升降档依据。")
      .replace(/父周期/g, "独立任务周期")
      .replace(/已核对(\d+)项独立任务，其中较好结果0项、低回报0项、负向结果0项。?/g, "已核对$1项独立任务。")
      .replace(/([0-5])\/\1\/\1维持/g, (_, level) => `三方面维持${thirdGradeText(level)}`)
      .replace(/(?:三方面)?([0-5])\/([0-5])\/([0-5])(?:维持|不变)/g, (_, delivery, endurance, reliability) => `实战任务交付${thirdGradeText(delivery)}、持续作战${thirdGradeText(endurance)}、体系可靠性${thirdGradeText(reliability)}`)
      .replace(/(^|[^\d])([0-5])\/([0-5])\/([0-5])(?=$|[^\d])/g, (_, prefix, delivery, endurance, reliability) => `${prefix}实战任务交付${thirdGradeText(delivery)}、持续作战${thirdGradeText(endurance)}、体系可靠性${thirdGradeText(reliability)}`)
      .replace(/实际控制范围全量复核已确认最终同级率/g, "现有正式复核维持当前控制范围判断")
      .replace(/只作仅作能力证据能力证据/g, "只作能力证据")
      .replace(/能力证据能力证据/g, "能力证据")
      .replace(/旧起点值/g, "此前接手时控制存量")
      .replace(/旧终点值/g, "此前结束时控制存量")
      .replace(/旧加权值/g, "此前综合控制量")
      .replace(/起点值/g, "接手时控制存量")
      .replace(/终点值/g, "结束时控制存量")
      .replace(/(?:第三项有效|客观|有效)?加权值/g, "综合控制量")
      .replace(/实际采用值/g, "本项实际采用值")
      .replace(/采用比例/g, "合成比例")
      .replace(/实际控制范围率/g, "控制范围合成比例")
      .replace(/重建客观库存/g, "重新核对控制存量")
      .replace(/客观起终库存/g, "接手与结束时的控制存量")
      .replace(/交班库存/g, "任期结束时可移交的控制存量")
      .replace(/继承库存/g, "继承控制存量")
      .replace(/真实库存/g, "实际控制存量")
      .replace(/控制范围合成比例\s*(\d+(?:\.\d+)?)→(\d+(?:\.\d+)?)/g, "控制范围合成比例由 $1% 调整为 $2%")
      .replace(/合成比例\s*(\d+(?:\.\d+)?)→(\d+(?:\.\d+)?)/g, "合成比例由 $1% 调整为 $2%")
      .replace(/合成比例仍\s*(\d+(?:\.\d+)?)(?![%\d.])/g, "合成比例仍为$1%")
      .replace(/合成比例\s*(\d+(?:\.\d+)?)(?![%\d.])/g, "合成比例 $1%")
      .replace(/机械落/g, "据此定为")
      .replace(/第三项现期/g, "本项当前窗口")
      .replace(/仅按军事体系规定作为能力专用证据/g, "只作为军事体系判断的补充证据")
      .replace(/军事体系整体([SABCDE]档)稀缺条件成立/g, "军事体系整体满足$1的高档条件")
      .replace(/封顶([0-5])档/g, (_, level) => `最高计至${thirdGradeText(level)}`)
      .replace(/([SABCDE]档)\s+(高位|中位|低位)/g, "$1$2")
      .replace(/受([SABCDE]档)上限约束/g, "最高不超过$1")
      .replace(/本轴客观([SABCDE]档)→\1，无正向跨档/g, "本轴从接手到结束均为$1，未发生正向跨档")
      .replace(/不生成变化分\s+没有确认本人造成的状态变化/g, "不产生变化分；现有材料没有确认本人造成状态变化")
      .replace(/结果\/成本/g, "结果与成本")
      .replace(/普通军事代价为不适用或尚未定级。当前本项不单独结算军事代价。/g, "本项不单独结算军事代价。")
      .replace(/改善成果\s+本人责任按现有材料区分/g, "改善成果。本人责任按现有材料区分")
      // Final public-text hygiene: strip revision bookkeeping that is useful in audit records
      // but should not survive into the reader-facing narrative.
      .replace(/旧5\.0→2\.2把安史危机过度转成空间退控；重建后3\.225→3\.225，控制范围合成比例由\s*15%\s*调整为\s*59%。?/g, "重新核对后，不再把安史危机整体换算为空间退控；当前控制范围合成比例为59%。")
      .replace(/此前接手时控制存量\/(?:此前)?结束时控制存量\s*6\.7→4\.7体系存在东北满额包和北方残量误继承；同一口径后为5\.8→2\.925，控制范围合成比例由\s*44%\s*调整为\s*15%。?/g, "重新核对后，东北控制存量和北方残余控制不再错误计入；当前控制范围合成比例为15%。")
      .replace(/此前结束时控制存量\s*6\.7→5\.8，综合控制量\s*1\.90→1\.00，控制范围合成比例由\s*60%\s*调整为\s*52%；核心修正是高丽—百济故地1\.4改为辽东0\.5。?/g, "重新核对后，当前控制范围合成比例为52%；高丽—百济故地仅按辽东部分计入。")
      .replace(/独立战果票/g, "独立战果")
      .replace(/军事体系整体([SABCDE]档)=\d+(?:\.\d+)?/g, "军事体系整体$1")
      .replace(/此前接手时控制存量\s*-?\d+(?:\.\d+)?→-?\d+(?:\.\d+)?/g, "接手时控制存量已重新核对")
      .replace(/(?:此前)?结束时控制存量\s*-?\d+(?:\.\d+)?→-?\d+(?:\.\d+)?/g, "结束时控制存量已重新核对")
      .replace(/净变化\s*-?\d+(?:\.\d+)?→-?\d+(?:\.\d+)?/g, "净变化已重新核对")
      .replace(/综合控制量\s*-?\d+(?:\.\d+)?→-?\d+(?:\.\d+)?/g, "综合控制量已重新核对")
      .replace(/接手时控制存量已重新核对，结束时控制存量已重新核对，综合控制量已重新核对；档位和合成比例不变/g, "重新核对控制存量后，档位和合成比例不变")
      .replace(/结束时控制存量已重新核对，净变化已重新核对，综合控制量已重新核对；档位和合成比例不变/g, "重新核对控制存量后，档位和合成比例不变")
      .replace(/兵团组织严重毁损战区主力毁损/g, "战区主力遭受严重毁损")
      .replace(/肃宗重建不倒灌本人/g, "肃宗后续重建不归入本人")
      .replace(/不倒灌本人/g, "不归入本人")
      .replace(/倒灌/g, "追溯计入")
      .replace(/(无实质军事成本|局部常规军事成本|有限军事成本|明显军事成本|大规模或持续显著军事成本|严重军事成本|极端军事成本|灾难性军事耗竭)(高位|中位|低位|极端上沿)?军事成本/g, (_, level, position) => position ? `${level}（${position}）` : level)
      .replace(/只取消阶段负面重复计票/g, "阶段负面不重复计入")
      .replace(/重复计票/g, "重复计入")
      .replace(/数值不变；伊吾0\.2改用哈密门户，其余旧标识规范化。?/g, "伊吾部分改用哈密门户口径，当前控制范围等级不变。")
      .replace(/旧-?\d+(?:\.\d+)?→-?\d+(?:\.\d+)?、综合控制量-?\d+(?:\.\d+)?、合成比例\s*\d+(?:\.\d+)?%只记南西恢复；补入继承控制存量和北方恢复后-?\d+(?:\.\d+)?→-?\d+(?:\.\d+)?、综合控制量-?\d+(?:\.\d+)?、合成比例\s*(\d+(?:\.\d+)?)%。?/g, "此前只计南、西方向恢复；补入继承控制存量和北方恢复后，当前合成比例为$1%。")
      .replace(/旧-?\d+(?:\.\d+)?→-?\d+(?:\.\d+)?、综合控制量-?\d+(?:\.\d+)?、合成比例\s*\d+(?:\.\d+)?%；补回长期漏记的北方边疆-?\d+(?:\.\d+)?及统一淮河锚后，-?\d+(?:\.\d+)?→-?\d+(?:\.\d+)?、综合控制量-?\d+(?:\.\d+)?、合成比例\s*(\d+(?:\.\d+)?)%。?/g, "补回此前漏记的北方边疆与统一淮河控制后，当前合成比例为$1%。")
      .replace(/旧0→0\.5是局部结果包且未承接前朝库存；完整库存重建后37→45。?/g, "此前只计局部结果且未承接前朝控制存量；补全控制存量后，当前控制范围判断相应上调。")
      .replace(/旧0→0\.5局部包遗漏绝大多数继承边疆库存；37→59。?/g, "此前局部记录遗漏绝大多数继承边疆控制存量；补全后，当前控制范围判断相应上调。")
      .replace(/旧实际控制范围=29且用0\.15\/0\.10\/0\.25临时绝对当量并提前把襄樊归零；同一口径后为1\.5→1\.05、综合控制量0\.15、合成比例\s*30%。?/g, "此前口径提前把襄樊控制归零；统一口径后，当前合成比例为30%。")
      .replace(/旧实际控制范围=\d+(?:\.\d+)?；([^。]+?)后升至(\d+(?:\.\d+)?)。?/g, "$1后，当前控制范围合成比例为$2%。")
      .replace(/旧区域对象漂移/g, "此前区域对象口径漂移")
      .replace(/旧2\.2→1\.8缺三受降城且使用非标准西域1\.4；规范后3\.225→2\.2，综合控制量\s*0\.265，合成比例仍为37%。?/g, "此前记录漏计三受降城并使用非标准西域尺度；统一口径后，合成比例仍为37%。")
      .replace(/旧1\.4→0\.2改为1\.8→0\.3；删掉805西州伪残值、补回持续存在的三受降城；合成比例仍为15%。?/g, "重新核对后，删除805年西州的错误残余控制，并补回持续存在的三受降城；合成比例仍为15%。")
      .replace(/旧1\.55→1\.3系统漏掉持续存在的北方边郡，并继续使用安南0\.5临时尺度；规范后2\.65→2\.1，综合控制量已重新核对，合成比例仍为37%。?/g, "此前记录漏掉持续存在的北方边郡，并使用非标准安南尺度；统一口径后，合成比例仍为37%。")
      .replace(/旧1\.8→1\.4改为2\.2→1\.8；三受降城补回、西域1\.4改为标准1\.5；合成比例不变。?/g, "重新核对后补回三受降城，并统一西域控制尺度；合成比例不变。")
      .replace(/旧实际控制范围\s*[SABCDE]档→[SABCDE]档与其安全态势\/控制成果材料直接矛盾；补全三方向继承控制存量后合成比例由\s*\d+(?:\.\d+)?%\s*调整为\s*(\d+(?:\.\d+)?)%。?/g, "此前控制范围判断与安全态势、控制成果材料不一致；补全三方向继承控制存量后，当前合成比例为$1%。")
      .replace(/旧954—955合并上层证据先整体退出，955胡卢河若独立拆链后再复核。?/g, "954—955年合并材料不再作为本项独立成本依据；955年胡卢河仅在能够形成独立任务链时另行判断。")
      .replace(/旧E档→E档无法表达真实退控；重建为3\.0→1\.65，控制范围合成比例由\s*0%\s*调整为\s*15%。?/g, "重新核对控制存量后，明确记录任期内真实退控；当前控制范围合成比例为15%。")
      .replace(/旧E档→E档掩盖蒙古造成的真实退控；重建3\.0→1\.5，合成比例由\s*0%\s*调整为\s*15%。?/g, "重新核对控制存量后，纳入蒙古进攻造成的真实退控；当前控制范围合成比例为15%。")
      .replace(/旧E档→E档无法表达河北、山东、河东、陕西持续退控；重建1\.5→0\.725，合成比例由\s*0%\s*调整为\s*29%。?/g, "重新核对控制存量后，纳入河北、山东、河东、陕西的持续退控；当前控制范围合成比例为29%。")
      .replace(/旧1\.0临时包改为草原规范(?:锚|依据)0\.875\+辽东0\.5；45→59。?/g, "统一草原与辽东控制口径后，当前控制范围合成比例为59%。")
      .replace(/旧0\.2西州残值改为0\.3三受降城实际控制存量；综合控制量已重新核对，合成比例仍为30%。?/g, "重新核对后，删除西州错误残余控制并计入三受降城实际控制存量；合成比例仍为30%。")
      .replace(/旧5\.0总量被东北1\.4\+松外0\.5高估；三受降城0\.3保留。控制范围合成比例由\s*67%\s*调整为\s*59%。?/g, "重新核对后，东北与松外控制存量不再高估，三受降城控制仍保留；当前控制范围合成比例为59%。")
      .replace(/旧(?:0|E档)→(?:0|E档)把实际仍存的燕云、辽东、松外和部分草原网络全部漏掉；0→37。?/g, "补全燕云、辽东、松外与草原控制存量后，当前控制范围合成比例为37%。")
      .replace(/旧(?:0|E档)→(?:0|E档)完全漏继承(?:库存|控制存量)；0→45。?/g, "补全继承控制存量后，当前控制范围合成比例为45%。")
      .replace(/旧只记燕云0→0\.8，漏掉阿保机交班草原和辽东库存；45→59。?/g, "此前只计燕云控制，漏掉阿保机交班时的草原和辽东控制存量；补全后当前控制范围判断相应上调。")
      .replace(/此前记录1\.6→1\.6漏掉灭北齐后形成的真实北方边郡任期结束时可移交的控制存量0\.8，同时旧河南—朔方证据混入现代河南\/江陵语义。现重新核对控制存量1\.6→2\.4，并将新增北方边郡0\.8按奠基与统一项统一链去重；本项综合控制量仍0\.64，控制范围合成比例维持44。?/g, "此前记录漏掉灭北齐后形成的北方边郡可移交控制，并混淆河南—朔方的区域语义；重新核对并按奠基与统一项去重后，当前控制范围等级不变。")
      .replace(/432—433益州民变虽旧卡误标已完成，但正文明确程道养二千余家入山、余党仍出没；436—437卡又明称卷122益州民变上层证据余部并以“余党悉平”收束，故两票合并为432—437年益州民变并按完整五年周期复核低回报。?/g, "432—437年益州民变按同一连续任务周期合并判断：前段余党仍在，后段才明确平定，完整周期的总体回报偏低。")
      .replace(/由证据不足证据支持评为/g, "现有证据仅支持判断为")
      .replace(/证据不足证据/g, "证据不足")
      .replace(/独立独立/g, "独立")
      .replace(/不升([0-5])/g, (_, level) => `不提高到${thirdGradeText(level)}`)
      .replace(/主准入/g, "主要计入依据")
      .replace(/准入理由/g, "计入依据")
      .replace(/准入条件/g, "计入条件")
      .replace(/准入/g, "计入条件")
      .replace(/硬门/g, "必要条件")
      .replace(/当前正式路由/g, "当前评价口径")
      .replace(/正式路由/g, "评价口径")
      .replace(/路由/g, "评价路径")
      .replace(/短切片/g, "短时间范围")
      .replace(/切片/g, "时间范围")
      .replace(/闭环/g, "完整证据链")
      .replace(/旧版/g, "此前版本")
      .replace(/上一版/g, "此前版本")
      .replace(/本批/g, "当前复核")
      .replace(/混合票/g, "混合任务记录")
      .replace(/独立战果票/g, "独立战果")
      .replace(/战果票/g, "战果记录")
      .replace(/不能拆成一低一高两票/g, "不能拆成一项低回报和一项高回报分别计算")
      .replace(/军事体系整体D档因此C档→B档；但安西—突骑施方向仍发生关键枢纽失陷且未证明恢复，军事体系整体B档保持2，最终评定仍军事体系整体C档。?/g, "这一北边主链改善了军事体系判断；但安西—突骑施方向仍发生关键枢纽失陷且未证明恢复，因此最终军事体系整体仍维持C档。")
      .replace(/拆票/g, "拆成多个独立任务")
      .replace(/计票/g, "计数")
      .replace(/票数/g, "任务数")
      .replace(/([0-9一二三四五六七八九十两]+)票/g, "$1项任务记录")
      .replace(/机械/g, "直接")
      .replace(/按统一(\d+(?:\.\d+)?)锚×(\d+(?:\.\d+)?)覆盖/g, "按统一控制尺度$1 × 覆盖系数$2")
      .replace(/锚定/g, "确定")
      .replace(/锚点/g, "关键依据")
      .replace(/主锚/g, "主要依据")
      .replace(/直接锚/g, "直接依据")
      .replace(/锚/g, "依据")
      .replace(/现有上层证据/g, "现有材料")
      .replace(/当前正式材料/g, "现有材料")
      .replace(/相关正式记录/g, "相关材料")
      .replace(/正式任务记录/g, "任务记录")
      .replace(/正式材料/g, "现有材料")
      .replace(/正式记录/g, "记录")
      .replace(/本项只读/g, "这里只计")
      .replace(/本项独立方向/g, "这一独立方向")
      .replace(/本窗口/g, "任内")
      .replace(/交班时/g, "任期结束时")
      .replace(/交班为/g, "结束时为")
      .replace(/总量不变；全部旧唐代区域标识迁移到同一口径。?/g, "现有材料支持维持当前控制范围等级。")
      .replace(/阶段扩张只留在战争卡和军事体系\/相关材料/g, "阶段扩张只作为战争与军事体系表现背景，不计作可移交控制成果")
      .replace(/重新核对本人窗口内的实际控制范围后，当前判断由[SABCDE]档(?:高位|中位|低位)?调整为[SABCDE]档(?:高位|中位|低位)?。?/g, "")
      .replace(/。。+/g, "。");
    if (!isCost) {
      text = text
        .replace(/(^|[^A-Za-z0-9_.])([0-5])档/g, (_, prefix, level) => `${prefix}${thirdGradeText(level)}`)
        .replace(/规模与控制强度：/g, "");
    }
    return cleanNetText(text);
  }

  function thirdItemPublicText(item, value) {
    let text = thirdPublicText(value, item?.label || "");
    if (!item || !["A1","A2"].includes(item.label)) return text;
    const transition = String(item.grade || "").match(/([0-5])\s*→\s*([0-5])档/);
    if (!transition) return text;
    const endGrade = thirdGradeText(transition[2]);
    return text
      .replace(/结束时未单列等级安全水平/g, `结束时${endGrade}安全水平`)
      .replace(/结束时为未单列等级/g, `结束时为${endGrade}`);
  }
  const SECOND_PUBLIC_GROUPS = new Set(["method", "finance", "handoff"]);
  const CIV_PUBLIC_DIRECTION = {POSITIVE:"正向",NEGATIVE:"负向",BALANCED:"正负相抵"};
  const CIV_PUBLIC_POSITION = {HIGH:"高位",MID:"中位",LOW:"低位",HIGHEST:"极端上沿"};
  const CIV_PUBLIC_MAGNITUDE = {
    1:"局部、短期或低强度变化",
    2:"清晰但有限的变化",
    3:"主要领域的稳定改变",
    4:"跨场景或系统性改变",
  };
  const CIV_PUBLIC_POINTS = {
    1:{LOW:3.0,MID:4.5,HIGH:6.0},
    2:{LOW:7.5,MID:9.5,HIGH:11.5},
    3:{LOW:13.5,MID:16.0,HIGH:18.0},
    4:{LOW:19.0,MID:21.0,HIGH:22.5},
  };
  const THIRD_COST_FACTOR = {
    0:{LOW:1.0,MID:1.0,HIGH:1.0},
    1:{LOW:1.0,MID:0.995,HIGH:0.99},
    2:{LOW:0.985,MID:0.98,HIGH:0.975},
    3:{LOW:0.965,MID:0.95,HIGH:0.935},
    4:{LOW:0.90625,MID:0.875,HIGH:0.84375},
    5:{LOW:0.7975,MID:0.745,HIGH:0.6925},
    6:{LOW:0.62375,MID:0.545,HIGH:0.44875},
    7:{LOW:0.35,MID:0.24,HIGH:0.12,HIGHEST:0.0},
  };

  function thirdBasisParts(value, itemLabel = "") {
    const text = thirdPublicText(value, itemLabel);
    if (!text) return [];
    return (text.match(/[^。！？；]+[。！？；]?/g) || [text]).map(part => part.trim()).filter(Boolean);
  }

  function thirdBasisMarkup(value, itemLabel = "") {
    const parts = thirdBasisParts(value, itemLabel);
    if (!parts.length) return "";
    if (parts.length === 1) return `<p class="net-material-body">${esc(parts[0])}</p>`;
    return `<div class="label">裁决说明</div><ul class="net-third-basis-list">${parts.map(part => `<li>${esc(part)}</li>`).join("")}</ul>`;
  }

  function civilizationMagnitudeText(level, direction = "") {
    const n = typeof level === "string" && THIRD_CN_LEVEL[level] != null ? THIRD_CN_LEVEL[level] : Number(level);
    if (!Number.isInteger(n) || !CIV_PUBLIC_MAGNITUDE[n]) return String(level || "");
    if (n === 4 && direction === "POSITIVE") return "跨场景的新范式变化";
    if (n === 4 && direction === "NEGATIVE") return "系统性破坏";
    return CIV_PUBLIC_MAGNITUDE[n];
  }

  function civilizationPublicText(value) {
    let text = cleanNetText(value);
    if (!text) return "";
    const magnitude = (level, direction = "") => civilizationMagnitudeText(level, direction);
    return text
      .replace(/净文明影响幅度第0级/g, "正负相抵，净调整为0")
      .replace(/原理由中的相对变化第3级与文明影响幅度第3级为过期表述。?/g, "此前较高等级表述已不再采用。")
      .replace(/补强为负向变化第2(?:级\.5|\.5级)/g, "共同使负向变化在清晰但有限基础上进一步强化")
      .replace(/负向变化第2(?:级\.5|\.5级)/g, "负向变化在清晰但有限基础上进一步强化")
      .replace(/正向变化第2(?:级\.5|\.5级)/g, "正向变化在清晰但有限基础上进一步强化")
      .replace(/文明影响幅度第0级/g, "正负相抵，净调整为0")
      .replace(/不进相对变化第([1-4一二三四])级/g, (_, level) => `不足以达到${magnitude(level)}`)
      .replace(/不能升相对变化第([1-4一二三四])级/g, (_, level) => `不足以达到${magnitude(level)}`)
      .replace(/不构成相对变化第([1-4一二三四])级禁入/g, (_, level) => `本身不会自动排除${magnitude(level)}`)
      .replace(/重大负向限制第([1-4一二三四])级/g, (_, level) => `重大负向限制达到${magnitude(level, "NEGATIVE")}`)
      .replace(/正向变化第([1-4一二三四])级/g, (_, level) => `正向变化达到${magnitude(level, "POSITIVE")}`)
      .replace(/负向变化第([1-4一二三四])级/g, (_, level) => `负向变化达到${magnitude(level, "NEGATIVE")}`)
      .replace(/净文明影响幅度第([1-4一二三四])级/g, (_, level) => `净影响为${magnitude(level)}`)
      .replace(/影响幅度第([1-4一二三四])级/g, (_, level) => `影响幅度为${magnitude(level)}`)
      .replace(/第([1-4一二三四])级影响幅度/g, (_, level) => magnitude(level))
      .replace(/相对变化第([1-4一二三四])级/g, (_, level) => magnitude(level))
      .replace(/结果方向未单列[：:]?/g, "正负变化并存：")
      .replace(/相对既有状态[：:]/g, "比较起点：")
      .replace(/责任范围按现有材料区分。?/g, "")
      .replace(/本人窗口内的责任按事实区分。?/g, "")
      .replace(/本人直接委托并提供支持。?/g, "本人直接委托并提供支持。")
      .replace(/补充限制[：:]/g, "限制：")
      .replace(/故本知识包按轴边界撤资格，保留史实。?/g, "因此该材料保留为背景，但不再单独形成本轴调整。")
      .replace(/撤销本包计分资格/g, "该材料不再单独形成调整")
      .replace(/撤销本包/g, "该材料不再单独计入")
      .replace(/本包未证成/g, "该项材料尚未证明")
      .replace(/本包/g, "该项材料")
      .replace(/现包/g, "当前材料")
      .replace(/原包/g, "原有材料")
      .replace(/旧包/g, "原有材料")
      .replace(/新包/g, "新增材料")
      .replace(/另包/g, "另一项材料")
      .replace(/不作为该项材料普通限制吞并/g, "不与该项材料的普通限制合并")
      .replace(/变化另一项材料共同使/g, "变化与另一项材料共同使")
      .replace(/扩搜新证/g, "新增材料")
      .replace(/计分资格/g, "单独调整依据")
      .replace(/同轴禁毁负包/g, "同一维度中的禁毁负向材料")
      .replace(/同一正包/g, "同一组正向材料")
      .replace(/同包/g, "同组材料")
      .replace(/负包/g, "负向材料")
      .replace(/正包/g, "正向材料")
      .replace(/独立增强包/g, "独立加成")
      .replace(/独立负(?=清晰|主要|广泛|根本性|相对变化)/g, "独立负向")
      .replace(/不在第四项复制军事损益/g, "不在文明与国家整合项重复计算军事得失")
      .replace(/退出第四项/g, "不在文明与国家整合项重复计入")
      .replace(/退出本轴/g, "不在本轴重复计入")
      .replace(/废诽谤妖言罪的法源及受理边界归第二项制度共同体与社会整合；?/g, "废除诽谤、妖言罪的制度与受理边界变化已由相关治理材料承担；")
      .replace(/诏令目的涉及来谏，但不能单靠诏令再算战略成果价值反馈结果，更不独证知识文本或教学网络变化。?/g, "诏令虽有鼓励进谏的目的，但仅凭诏令本身不能证明已经形成实际反馈效果，也不能证明知识文本或教学网络发生独立变化。")
      .replace(/归第二项制度共同体与社会整合/g, "归入相关制度与社会治理材料")
      .replace(/战略成果价值反馈结果/g, "已经形成实际反馈效果")
      .replace(/归第二项社会安全/g, "归入治国成效中的社会安全")
      .replace(/归第二项反馈纠错与权力约束/g, "归入治国成效中的反馈与约束")
      .replace(/轴净/g, "本轴综合")
      .replace(/净轴复核为/g, "综合判断为")
      .replace(/净轴/g, "综合判断")
      .replace(/压低净带位/g, "降低综合档位")
      .replace(/净带位/g, "综合档位")
      .replace(/取中位，撤去原高位/g, "取中位，不再维持此前高位")
      .replace(/撤去普通反证负向变化达到/g, "普通反证不足以另列")
      .replace(/撤去原高位/g, "不再维持此前高位")
      .replace(/原高位持续性不足/g, "此前高位所需的持续性不足")
      .replace(/硬门/g, "强约束")
      .replace(/硬负记录/g, "明确负向记录")
      .replace(/硬负向/g, "强负向")
      .replace(/定文明影响幅度为/g, "综合判断为")
      .replace(/保文明影响幅度为/g, "综合保留为")
      .replace(/本人出口无据/g, "缺少本人任内实际结果依据")
      .replace(/不得以未知写成/g, "不能在证据不足时写成")
      .replace(/共同限制带位/g, "共同限制档内位置")
      .replace(/限制带位/g, "限制档内位置")
      .replace(/保有限正向变化/g, "形成有限正向变化")
      .replace(/保强迁强负向/g, "强迁仍属强负向")
      .replace(/同窗文字标准化/g, "同轴文字标准化")
      .replace(/同账/g, "在同一维度合并判断")
      .replace(/作净算/g, "合并判断")
      .replace(/回填/g, "重复计入本人")
      .replace(/倒算本人/g, "追溯计入本人")
      .replace(/倒算给/g, "追溯计入")
      .replace(/另定整数负向变化/g, "另定为独立负向变化")
      .replace(/轴级/g, "本轴")
      .replace(/轴正负相抵/g, "本轴综合正负相抵")
      .replace(/不足以洗掉/g, "不足以抵消")
      .replace(/不能机械堆成/g, "不能直接叠加为")
      .replace(/不机械升/g, "不直接提高到")
      .replace(/机械转化为/g, "直接转化为")
      .replace(/机械判零/g, "直接判为零")
      .replace(/机械/g, "直接")
      .replace(/\s+；/g, "；")
      .replace(/。；/g, "；")
      .replace(/。。+/g, "。")
      .replace(/\s+/g, " ")
      .trim();
  }

  function civilizationBasisMarkup(value) {
    const text = civilizationPublicText(value);
    if (!text) return "";
    const parts = (text.match(/[^。！？；]+[。！？；]?/g) || [text]).map(part => part.trim()).filter(Boolean);
    if (parts.length === 1) return `<p class="net-material-body">${esc(parts[0])}</p>`;
    return `<div class="label">裁决说明</div><ul class="net-third-basis-list">${parts.map(part => `<li>${esc(part)}</li>`).join("")}</ul>`;
  }

  function civilizationPublicStatus(item, formalLevel = "") {
    const parts = String(item?.grade || "").split("/").map(value => value.trim());
    const direction = CIV_PUBLIC_DIRECTION[parts[0]] || "";
    if (parts[0] === "BALANCED" || parts[1] === "CIV0") return "正负相抵 · 净调整为0";
    const magnitude = parts[1]?.match(/^CIV([1-4])$/);
    const level = magnitude ? civilizationMagnitudeText(magnitude[1], parts[0]) : civilizationPublicText(formalLevel);
    const position = CIV_PUBLIC_POSITION[parts[2]] || "";
    return [direction, level, position].filter(Boolean).join(" · ");
  }

  function civilizationExactHow(item, fallback) {
    const parts = String(item?.grade || "").split("/").map(value => value.trim());
    if (parts[0] === "BALANCED" || parts[1] === "CIV0") {
      return "正向与负向材料在本轴净算后相抵，因此本轴调整为0分。";
    }
    const magnitude = parts[1]?.match(/^CIV([1-4])$/);
    const position = parts[2];
    const points = magnitude ? CIV_PUBLIC_POINTS[Number(magnitude[1])]?.[position] : null;
    const direction = CIV_PUBLIC_DIRECTION[parts[0]] || "";
    if (points == null || !direction) return fallback;
    const signed = parts[0] === "NEGATIVE" ? -points : points;
    const label = civilizationMagnitudeText(magnitude[1], parts[0]);
    return `“${label}”的${CIV_PUBLIC_POSITION[position] || position}固定对应${points}分；方向为${direction}，所以当前调整为${signed > 0 ? "+" : ""}${signed}分。`;
  }

  function thirdCostExactHow(item, fallback) {
    const match = String(item?.grade || "").match(/\bC([0-7])\s*\/\s*(LOW|MID|HIGH|HIGHEST)\b/i);
    if (!match) return fallback;
    const level = Number(match[1]);
    const position = match[2].toUpperCase();
    const factor = THIRD_COST_FACTOR[level]?.[position];
    if (factor == null) return fallback;
    const debit = 80 * (1 - factor);
    const shown = Number(debit.toFixed(1));
    return `当前为${thirdCostText(level)}、${CIV_PUBLIC_POSITION[position] || position}；固定成本系数为${factor}，扣分 = 80 × (1 − ${factor}) = ${shown}分。`;
  }

  function strategicAxisExactHow(item, groupItems) {
    const grade = String(item?.grade || "").match(/([0-5])\s*→\s*([0-5])档/);
    const current = grade
      ? `当前状态是接手${thirdGradeText(grade[1])} → 结束${thirdGradeText(grade[2])}`
      : "";
    const formalCurrent = thirdPublicText(item?.reader_how || "", item?.label || "");
    const subtotal = thirdPublicText(groupItems.get("A120")?.reader_how || "", "A120");
    return `“轨迹值”只是计分中间值，不是另一项评价。计算时 E=0、D=1、C=2、B=3、A=4、S=5；0—5只是在公式中的档位权重，最终等级仍按 E—S 表示，并不是另一套数字档位。轨迹值 = 10 × 结束档位数值 + 14 × 本人可归责档差 + 专项信用 − 负向调整，并限制在0—100；本轴分数 = 0.6 × 轨迹值。专项信用与负向调整均采用当前已确定值，不从最终分数反推。${current ? " " + current + "。" : ""}${formalCurrent ? " 当前人物：" + formalCurrent : ""}${subtotal ? " 两个战略安全轴最后直接相加；当前两轴小计：" + subtotal : ""}`;
  }

  function detailedHowText(item, groupKey, how, record) {
    const groupItems = new Map((record?.net?.component_details?.[groupKey] || []).map(entry => [entry.label, entry]));
    if (groupKey === "strategic" && ["A1","A2"].includes(item.label)) {
      return strategicAxisExactHow(item, groupItems);
    }
    if (groupKey === "strategic" && ["B1","B2","B4"].includes(item.label)) {
      const b1 = groupItems.get("B1");
      const b2 = groupItems.get("B2");
      const b4 = groupItems.get("B4");
      const total = groupItems.get("B80");
      const current = [b1?.value, b2?.value, b4?.value, total?.value].every(value => value != null)
        ? `当前三项得分率为控制范围 ${b1.value}%、战略价值 ${b2.value}%、成果稳定性 ${b4.value}%；当前合成结果为 ${total.value}分。`
        : "";
      return `三项先各自形成得分率；控制范围与战略价值按55%/45%合成，再由成果稳定性修正。${current ? " " + current : ""} 当前结果说明：${how}`;
    }
    if (groupKey === "military" && ["C1实战交付","C2持续作战","C3体系可靠性"].includes(item.label)) {
      const axes = ["C1实战交付","C2持续作战","C3体系可靠性"].map(label => groupItems.get(label)).filter(Boolean);
      const total = groupItems.get("C50");
      const statuses = axes.map(entry => thirdPublicText(entry.public_level_label || entry.reader_summary || "", entry.label)).filter(Boolean);
      const current = statuses.length && total
        ? `当前三方面：${statuses.join("；")}；${thirdPublicText(total.public_level_label || "", total.label)}，军事体系结果为 ${total.value}分。`
        : "";
      return `三方面分别定档但不单独加分，共同确定军事体系整体档位。整体档位对应50分项得分率：E档0%—29%、D档30%—44%、C档45%—59%、B档60%—74%、A档75%—89%、S档90%—100%。${current ? " " + current : ""} 当前结果说明：${how}`;
    }
    if (groupKey === "military" && item.label === "普通成本扣分") return thirdCostExactHow(item, how);
    if (groupKey === "military" && item.label === "ML扣分") {
      return `重大军事净毁损只有在重大结果、较高本方代价和本人责任同时成立时才追加扣减；与普通军事代价取较高扣减，不重复相加。当前人物：${how}`;
    }
    if (groupKey === "civilization") return civilizationExactHow(item, how);
    return how;
  }

  function scoreHowDetails(item, groupKey, how, formalLevel, record) {
    if (!how && !formalLevel) return "";
    const status = groupKey === "civilization" ? civilizationPublicStatus(item, formalLevel) : formalLevel;
    const result = netValue(item, groupKey);
    const detailed = detailedHowText(item, groupKey, how, record);
    const rows = [
      status ? ["当前裁决", status] : null,
      detailed ? ["换算规则", detailed] : null,
      result ? ["当前结果", result] : null,
    ].filter(Boolean);
    return `<details class="net-score-how"><summary>这个分怎么算？</summary><dl>${rows.map(([label,value]) => `<dt>${esc(label)}</dt><dd>${esc(value)}</dd>`).join("")}</dl></details>`;
  }

  function materialSummaryCoveredBySingleEvidence(summaryValue, basisValue) {
    const summary = cleanNetText(summaryValue);
    const basis = cleanNetText(basisValue);
    if (!summary || !basis) return false;
    if (summary === basis) return true;
    const tail = value => {
      const index = value.indexOf("。");
      return index >= 0 ? cleanNetText(value.slice(index + 1)) : "";
    };
    const summaryTail = tail(summary);
    const basisTail = tail(basis);
    return summaryTail.length >= 20 && summaryTail === basisTail;
  }

  function metricMaterialCards(item, groupKey) {
    if (!MATERIAL_CARD_GROUPS.has(groupKey)) return "";
    const evidence = Array.isArray(item.reader_public_evidence_items) ? item.reader_public_evidence_items : [];
    if (!evidence.length) return "";
    const thirdItem = groupKey === "strategic" || groupKey === "military";
    const fourthItem = groupKey === "civilization";
    const format = value => thirdItem ? thirdItemPublicText(item, value) : fourthItem ? civilizationPublicText(value) : cleanNetText(value);
    const overallBoundary = format(item.reader_boundary || "");
    const cards = evidence.map(entry => {
      const title = format(entry?.public_label || entry?.public_role || "正式裁决材料");
      const role = format(entry?.public_role || "");
      const direction = format(entry?.public_direction || "");
      const coverage = format(entry?.public_source_coverage || "");
      const tags = Array.isArray(entry?.public_tags) ? entry.public_tags.map(format).filter(Boolean) : [];
      const chips = [...new Set([role, direction, coverage, ...tags].filter(Boolean))]
        .map(value => `<span class="net-material-chip">${esc(value)}</span>`).join("");
      const basis = format(entry?.public_basis || "");
      const candidateBoundary = format(entry?.public_boundary || "");
      const boundary = candidateBoundary && candidateBoundary !== overallBoundary ? candidateBoundary : "";
      const basisMarkup = thirdItem
        ? thirdBasisMarkup(format(entry?.public_basis || ""), "")
        : fourthItem
          ? civilizationBasisMarkup(entry?.public_basis || "")
          : (basis ? `<p class="net-material-body">${esc(basis)}</p>` : "");
      return `<li class="net-material-card"><div class="net-material-head"><strong>${esc(title)}</strong>${chips ? `<span class="net-material-meta">${chips}</span>` : ""}</div>${basisMarkup}${boundary ? `<details class="net-material-boundary"><summary>该材料的范围与边界</summary><p>${esc(boundary)}</p></details>` : ""}</li>`;
    }).join("");
    const hasSourceCoverage = evidence.some(entry => format(entry?.public_source_coverage || ""));
    const coverageNote = hasSourceCoverage
      ? '<p class="subline net-source-coverage-note">“来源覆盖”只表示当前公开证据包的来源是否足够，不表示材料强度、结果方向或得分高低。</p>'
      : "";
    return cards ? `<div class="label">正式裁决材料</div>${coverageNote}<ul class="net-material-list">${cards}</ul>` : "";
  }

  function metricDetail(item, record, groupKey = "") {
    const displayLabel = publicNetComponentLabel(item);
    const intro = netPublicIntro[displayLabel] || netPublicIntro[item.label] || "";
    const thirdItem = groupKey === "strategic" || groupKey === "military";
    const fourthItem = groupKey === "civilization";
    const formatPublic = value => thirdItem ? thirdItemPublicText(item, value) : fourthItem ? civilizationPublicText(value) : cleanNetText(value);
    const summary = formatPublic(item.reader_summary || "");
    const fullBasis = cleanNetText(item.reader_full_basis || "");
    const publicEvidence = Array.isArray(item.reader_public_evidence_items) ? item.reader_public_evidence_items : [];
    const highlights = publicEvidence.length
      ? publicEvidence.map(entry => {
        const label = formatPublic(entry?.public_label || entry?.public_role || "公开依据");
        const basis = formatPublic(entry?.public_basis || "");
        return basis ? `${label}：${basis}` : "";
      }).filter(Boolean)
      : (Array.isArray(item.reader_highlights) ? item.reader_highlights : [])
        .map(cleanNetText).filter(Boolean);
    const boundary = formatPublic(item.reader_boundary || "");
    const how = formatPublic(item.reader_how || "");
    const structuredMaterials = MATERIAL_CARD_GROUPS.has(groupKey) && publicEvidence.length > 0;
    const singleEvidenceBasis = publicEvidence.length === 1 ? formatPublic(publicEvidence[0]?.public_basis || "") : "";
    const summaryCoveredByEvidence = structuredMaterials
      && materialSummaryCoveredBySingleEvidence(summary, singleEvidenceBasis);
    const logic = structuredMaterials ? "" : summary;
    const formalLevel = MATERIAL_CARD_GROUPS.has(groupKey) ? formatPublic(item.public_level_label || "") : "";
    const formalLevelBase = formalLevel.replace(/^当前结果为\s*/, "");
    const repeatedPrefix = displayLabel + "为";
    const formalLevelDisplay = formalLevelBase.startsWith(repeatedPrefix)
      ? formalLevelBase.slice(repeatedPrefix.length)
      : formalLevelBase;
    const full = fullBasis && fullBasis !== summary
      ? `<details><summary>正式裁决原文（未改写）</summary>${prose(fullBasis)}</details>`
      : "";
    const materialCards = metricMaterialCards(item, groupKey);
    const summaryFold = structuredMaterials && summary && !summaryCoveredByEvidence
      ? `<details class="net-material-summary"><summary>总体裁决摘要</summary>${prose(summary)}</details>`
      : "";
    const facts = materialCards || (highlights.length
      ? `<div class="label">关键事实</div><ul>${highlights.map(text => `<li>${esc(text)}</li>`).join("")}</ul>`
      : "");
    const limit = boundary
      ? materialCards
        ? `<details class="net-overall-boundary"><summary>总体范围与边界</summary>${prose(boundary)}</details>`
        : `<div class="label">限制与边界</div>${prose(boundary)}`
      : "";
    const formula = scoreHowDetails(item, groupKey, how, formalLevel, record);
    const secondSource = SECOND_PUBLIC_GROUPS.has(groupKey) ? ` data-second-source-label="${esc(item.label)}"` : "";
    return `<details class="net-metric-detail"${secondSource}><summary><span><strong>${esc(displayLabel)}</strong>${intro ? `<small>${esc(intro)}</small>` : ""}${formalLevelDisplay ? `<small class="net-formal-level">当前判断：${esc(formalLevelDisplay)}</small>` : ""}</span><b>${esc(netValue(item, groupKey))}</b></summary><div class="net-metric-body">${logic ? `<div class="label">当前人物结算逻辑</div>${prose(logic)}` : ""}${facts}${summaryFold}${limit}${formula}${full}${auditSourceBlock(item, record)}</div></details>`;
  }

  const PUBLIC_CALCULATION_KEEP = {
    method:new Set(["治理手段"]),
    finance:new Set(["治理结果"]),
    handoff:new Set(["交接得分"]),
    strategic:new Set(["A120","B80"]),
    military:new Set(["C50","实际扣分","第三项合计"]),
    civilization:new Set(["第四项调整"]),
  };

  function calculationBlock(items, groupKey = "") {
    const keep = PUBLIC_CALCULATION_KEEP[groupKey];
    const calculations = items.filter(item =>
      item.reader_kind === "calculation"
      && item.value != null
      && (!keep || keep.has(item.label))
    );
    if (!calculations.length) return "";
    const thirdItem = groupKey === "strategic" || groupKey === "military";
    return `<details class="net-calculations"><summary>本组小计怎么形成？</summary>${calculations.map(item => {
      const how = thirdItem ? thirdPublicText(item.reader_how || "按正式公式换算。", item.label) : cleanNetText(item.reader_how || "按正式公式换算。");
      return `<div class="component"><span><strong>${esc(publicNetComponentLabel(item))}</strong><small>${esc(how)}</small></span><b>${esc(netValue(item, groupKey))}</b></div>`;
    }).join("")}</details>`;
  }

  function genericNetGroup(record, key, items) {
    const judgments = items.filter(item =>
      item.reader_kind === "judgment"
      && (item.value != null || item.unit === "不单独计分" || item.public_level_label)
    );
    return `<section id="net-group-${esc(key)}" class="panel net-detail-group"><h2>${esc(netGroupNames[key] || key)}</h2>${judgments.map(item => metricDetail(item, record, key)).join("")}${calculationBlock(items, key)}</section>`;
  }

  function firstItemRawUrl(ref) {
    const path = String(ref || "").split("#", 1)[0];
    return typeof validatedRawUrl === "function" ? validatedRawUrl(path) : `../${path}?raw=1`;
  }

  async function loadFirstItemDoc(ref, record) {
    if (!ref) return "";
    const rulerId = record?.ruler_id || "";
    const cacheKey = `${rulerId}\u0000${ref}`;
    if (firstItemDocCache.has(cacheKey)) return firstItemDocCache.get(cacheKey);
    const pending = fetch(firstItemRawUrl(ref), {cache: "no-cache"})
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
    return firstPublicText(value)
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

  function firstOutcomeCalculationText(value) {
    return firstItemPublicText(value)
      .replace(/成果信用U=(\d+(?:\.\d+)?)/g, "本人有效控制成果值为$1")
      .replace(/单人项目按统一贡献曲线计算，共同项目先生成项目A池再按正式个人信用分账/g, "单人完成时直接按统一成果曲线计算；多人共同完成时，先确定项目整体成果，再按正式归责分给个人")
      .replace(/项目A池/g, "项目整体成果")
      .replace(/正式个人信用分账/g, "按正式归责分配个人成果");
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
    return `“起点、强敌与速度”满分50 = 起点难度15 + 对手难度15 + 完成效率20。\n${start}\n${opponent}\n${efficiency}${current ? `\n当前人物：${current}` : ""}`;
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
    return firstPublicText(value);
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

  function firstMetricDetail(id, title, subtitle, item, body, record, valueText = "") {
    const shown = valueText || netValue(item);
    return `<details id="${id}" data-ruler="${esc(personLabel(record))}" class="net-metric-detail"><summary><span><strong>${title}</strong><small>${subtitle}</small></span><b>${esc(shown)}</b></summary><div class="net-metric-body">${body}${auditSourceBlock(item, record)}</div></details>`;
  }

  function firstEvidenceMarkup(value, component) {
    const text = String(value || "");
    const base = new URL(`../${firstItemDocs[component]}`, location.href);
    let output = "", cursor = 0;
    for (const match of text.matchAll(/\[([^\]]+)\]\(([^)]+)\)/g)) {
      output += esc(text.slice(cursor, match.index));
      const href = new URL(match[2], base);
      output += ["http:", "https:"].includes(href.protocol)
        ? `<a href="${esc(href.href)}" target="_blank" rel="noopener">${esc(match[1])} ↗</a>` : esc(match[1]);
      cursor = match.index + match[0].length;
    }
    return output + esc(text.slice(cursor));
  }

  function renderFirstA(item, bullets, record) {
    const publicOutcome = item.reader_public_outcome || {};
    const calculation = firstOutcomeCalculationText(item.reader_how || "");
    const percent = firstPublicSharePercent(publicOutcome);
    const project = publicOutcome.public_project ? `<div class="label">共同项目</div>${prose(firstPublicOutcomeText(publicOutcome.public_project))}` : "";
    const facts = firstPublicOutcomeParts(publicOutcome)
      .map(([label, value]) => `<div class="label">${esc(label)}</div>${prose(firstPublicOutcomeText(value))}`)
      .join("");
    const share = percent ? `<div class="label">本人成果规模</div>${prose(`约${percent}%全国核心统一尺度（按本人有效控制成果计算；不是共同项目分成，也不是领土、人口或军队比例）`)}` : "";
    const rules = `<details class="first-item-rule-box"><summary>这个分怎么算？</summary><div class="label">这项看什么</div>${prose("这里只评价建国、复国或统一主链中，本人最终真正留下的稳定控制成果。继承来的既有版图不算本人新增；起点、对手、速度、组织和本人军事能力分别在其他分项评价。")}<div class="label">本人有效控制成果值</div>${prose("新增稳定控制按100%计，恢复旧有稳定控制按50%计；1000代表一个全国核心统一尺度。这个数不是人口、面积或军队人数。")}${prose(`统一成果分 = 120 × (min(1000, 本人有效控制成果值) / 1000)^0.65；单人完成时直接计算，多人共同完成时再按正式归责分配个人成果。${calculation ? `\n当前人物正式代入：${calculation}` : ""}`)}</details>`;
    return firstMetricDetail("net-first-a", "统一成果", "先看本人真正留下了什么", item, `${project}${facts}${share}${rules}`, record);
  }

  function renderFirstB1(item, bullets, record) {
    const rules = `<details class="first-item-rule-box"><summary>这个分怎么算？</summary>${prose(firstB1ScoreText(item))}</details>`;
    return firstMetricDetail("net-first-b1", "起点、强敌与速度", "起点、主要对手和完成效率", item, `${firstB1Markup(item)}${rules}`, record);
  }


  function renderFirstB2(item, bullets, record) {
    const result = bullets["B2结算"] || "";
    const parallel = bullets["并行执行"] || "";
    const coverage = bullets["团队能力覆盖与组织杠杆"] || bullets["能力覆盖/组织杠杆"] || "";
    const integration = bullets["异质整合"] || "";
    const basis = bullets["裁决依据"] || "";
    const facts = `${parallel ? `<div class="label">多线任务怎样同时推进</div>${prose(firstFactText(parallel))}` : ""}${coverage ? `<div class="label">团队怎样分工</div>${prose(firstFactText(coverage))}` : ""}${integration ? `<div class="label">旧部、降附者与异质集团怎样整合</div>${prose(firstFactText(integration))}` : ""}${basis ? `<div class="label">本人组织表现与限制</div>${prose(firstFactText(basis))}` : ""}${bullets["材料来源"] ? `<details><summary>史料与归责来源</summary><p class="sources">${firstEvidenceMarkup(bullets["材料来源"], "B2组织与整合")}</p></details>` : ""}`;
    const rules = `<details class="first-item-rule-box"><summary>这个分怎么算？</summary>${prose("“创业组织与政治整合”看创业或统一机器能否多线并行、把高难任务交给专业责任中心，并把不同地域和旧集团稳定接入同一执行体系。三个维度均分为 E、D、C、B、A、S 六档，依次对应0、2、4、6、8、10分，三项相加。")}${result ? prose(`当前人物正式结算：${firstFactText(result)}`) : ""}</details>`;
    return firstMetricDetail("net-first-b2", "创业组织与政治整合", "多线并行、专业分工与异质整合", item, `${facts}${rules}`, record);
  }

  function renderFirstC(item, bullets, record) {
    const facts = firstCommanderMarkup(item);
    const grade = firstItemPublicText(item.grade || "");
    const how = firstItemPublicText(item.reader_how || "");
    const rules = `<details class="first-item-rule-box"><summary>这个分怎么算？</summary>${prose(`这里只看本人亲自承担的整体部署、战役指挥或临阵处理；将领独立完成的战果不直接归到本人名下。\\n${firstCommanderScoreText(item)}\\n当前能力裁决：${grade || "按正式能力档裁决"}。\\n正式记录：${how || "按正式能力档与责任路线换算。"}`)}</details>`;
    const crossSystem = `<p class="subline first-item-cross-system-note">这里使用第一项自己的军事指挥归责口径；人物画像“军事统帅”是独立能力轴，事件范围与归责门槛不同，两者不能按档位或分数直接换算。</p>`;
    return firstMetricDetail("net-first-c", "本人统帅", "只看本人亲自承担并完成的军事指挥事实", item, `${facts}${crossSystem}${rules}`, record);
  }

  function renderFirstCost(item, record) {
    const level = firstCostPublicText(item.reader_public_cost?.public_level_label || "");
    const rule = `<details class="first-item-rule-box"><summary>这个分怎么算？</summary>${prose(`当前成本裁决：${level || "按正式成本严重度裁决"}。\\n${firstCostExactHow(item)}\\n当前扣减：${item.value} 分。`)}</details>`;
    return firstMetricDetail("net-first-cost", "军事成本 · 战争代价", "从四轴毛分中扣除", item, `${firstCostMarkup(item)}${rule}`, record, `扣 ${item.value} 分`);
  }


  function firstTotals(items) {
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
    return `<div class="net-detail-total"><details><summary>查看第一项完整折算公式</summary>${prose(`四轴毛分 = 统一成果 + 创业难度与效率 + 创业组织与整合 + 本人统帅 = ${a} + ${b1} + ${b2} + ${c} = ${gross}。\n军事代价扣减 = ${cost}。\n第一项结算分 = max(0, ${gross} − ${cost}) = ${net} / 240。\n统治绩效附加 = 0.20 × 637 × (第一项结算分 / 240)^1.25 = ${addOn}。`)}</details></div>`;
  }

  function firstItemOverview(record, bulletsByLabel, byLabel) {
    const a = byLabel["A统一贡献"]?.reader_public_outcome || {};
    const b1 = byLabel["B1创业难度与效率"]?.reader_public_b1 || {};
    const b2 = bulletsByLabel["B2组织与整合"] || {};
    const cost = byLabel["军事成本扣分"];
    const aPercent = firstPublicSharePercent(a);
    const aText = [
      a.public_project ? `共同项目：${a.public_project}` : "",
      a.public_outcome_basis ? `起点背景：${firstPublicOutcomeText(a.public_outcome_basis)}` : "",
      a.public_scope ? `实际成果：${firstPublicOutcomeText(a.public_scope)}` : "",
      aPercent ? `本人成果规模：约${aPercent}%全国核心统一尺度（按本人有效控制成果计算；不是共同项目分成，也不是领土、人口或军队比例）` : "",
    ].filter(Boolean).join(" ");
    const b1Parts = [
      ["起点", b1.public_start_basis],
      ["对手", b1.public_opponent_basis],
      ["速度", b1.public_efficiency_basis],
    ].filter(([, value]) => value);
    const b2Parts = [
      ["并行", b2["并行执行"]],
      ["分工", b2["团队能力覆盖与组织杠杆"] || b2["能力覆盖/组织杠杆"]],
      ["整合", b2["异质整合"]],
    ].filter(([, value]) => value);
    const cText = firstPublicText(byLabel["C军事统帅与战争解题"]?.reader_public_commander?.public_basis || "");
    const costData = cost?.reader_public_cost || {};
    const costText = [
      firstCostPublicText(costData.public_level_label || ""),
      firstCostPublicText(costData.public_status_label || ""),
      costData.public_responsibility_window ? `责任窗口：${firstCostPublicText(costData.public_responsibility_window)}` : "",
    ].filter(Boolean).join(" · ");
    const items = record.net?.component_details?.first || [];
    const parts = Object.fromEntries(items.map(item => [item.label, item.value]));
    const netScore = parts["第一项净分"], addOn = parts["附加F"];
    return `<section class="first-item-overview"><h2>先看${esc(personLabel(record))}在这条主链里实际做了什么</h2><p class="subline">下面默认只放当前人物的成果、难题、组织、统帅和代价；指标定义与公式都收进折叠项。</p><div class="first-item-story-grid">${aText ? `<div class="first-item-story-card"><b>统一成果</b><p>${esc(aText)}</p></div>` : ""}${b1Parts.length ? `<div class="first-item-story-card"><b>起点、强敌与速度</b><ul>${b1Parts.map(([label, value]) => `<li><strong>${label}：</strong>${esc(firstPublicText(value))}</li>`).join("")}</ul></div>` : ""}${b2Parts.length ? `<div class="first-item-story-card"><b>组织与整合</b><ul>${b2Parts.map(([label, value]) => `<li><strong>${label}：</strong>${esc(firstFactText(value))}</li>`).join("")}</ul></div>` : ""}${cText ? `<div class="first-item-story-card"><b>本人统帅</b><p>${esc(cText)}</p></div>` : ""}${costText ? `<div class="first-item-story-card wide"><b>战争代价</b><p>${esc(costText)}</p></div>` : ""}</div>${netScore != null && addOn != null ? `<div class="first-item-scoreline">第一项结算分 <strong>${scoreNumber(netScore)} / 240</strong> · 统治绩效附加 <strong>+${scoreNumber(addOn)}</strong></div>` : ""}</section>`;
  }

  async function renderFirstMajor(record, focus = "") {
    const items = record.net?.component_details?.first || [];
    const container = document.getElementById("net-major-body");
    if (!container) return;
    const firstStatus = record.net?.first_item_status;
    if (firstStatus === "NOT_APPLICABLE") {
      container.innerHTML = `<section class="panel"><h2>${esc(netMajorSpecs.first.title)}</h2><p class="notice">本项只评价建国、复国或统一创业主链；该人物不适用，因此这一项不参与统治绩效计分。</p></section>`;
      return;
    }
    if (firstStatus !== "APPLICABLE") {
      container.innerHTML = `<section class="panel"><h2>${esc(netMajorSpecs.first.title)}</h2><p class="notice">第一项正式适用状态尚未发布，因此不根据分项空值或现有材料推断是否适用。</p></section>`;
      return;
    }

    const labels = ["B1创业难度与效率", "B2组织与整合"];
    const bulletsByLabel = {};
    const names = [record.ruler_name, firstItemFormalNames[record.ruler_name]];
    await Promise.all(labels.map(async label => {
      bulletsByLabel[label] = firstItemBullets(await loadFirstItemDoc(firstItemDocs[label], record), names);
    }));
    if (!location.hash.startsWith(`#net/${encodeURIComponent(record.ruler_id)}/first`)) return;

    const byLabel = Object.fromEntries(items.map(item => [item.label, item]));
    const ownA = byLabel["A统一贡献"]?.reader_public_outcome || {};
    if (!container.isConnected) return;

    const cards = [];
    if (byLabel["A统一贡献"]) cards.push(renderFirstA(byLabel["A统一贡献"], bulletsByLabel["A统一贡献"], record));
    if (byLabel["B1创业难度与效率"]) cards.push(renderFirstB1(byLabel["B1创业难度与效率"], bulletsByLabel["B1创业难度与效率"], record));
    if (byLabel["B2组织与整合"]) cards.push(renderFirstB2(byLabel["B2组织与整合"], bulletsByLabel["B2组织与整合"], record));
    if (byLabel["C军事统帅与战争解题"]) cards.push(renderFirstC(byLabel["C军事统帅与战争解题"], bulletsByLabel["C军事统帅与战争解题"], record));
    if (byLabel["军事成本扣分"]?.value != null) cards.push(renderFirstCost(byLabel["军事成本扣分"], record));

    const windowText = bulletsByLabel["B1创业难度与效率"]["效率"] || "";
    const zeroNote = record.net?.first_item_status === "APPLICABLE" && finiteNetNumber(record.net?.first_item_raw_score) === 0
      ? '<p class="notice"><strong>本项适用，但第一项结算分归零。</strong>这与“不适用”不同：本项已经进入结算，成果与能力分在扣除本人责任窗口内军事代价后归零，因此统治绩效附加为0。</p>'
      : "";
    const scope = `<details class="first-item-scope"><summary>本项采用的时间与责任范围</summary><dl>${ownA.public_project ? `<dt>共同项目</dt><dd>${esc(firstPublicOutcomeText(ownA.public_project))}</dd>` : ""}${firstPublicOutcomeParts(ownA).map(([label, value]) => `<dt>${esc(label)}</dt><dd>${esc(firstPublicOutcomeText(value))}</dd>`).join("")}${windowText ? `<dt>完成效率计时</dt><dd>${esc(firstFactText(windowText))}</dd>` : ""}${byLabel["军事成本扣分"]?.reader_boundary ? `<dt>军事成本责任范围</dt><dd>${esc(firstPublicText(byLabel["军事成本扣分"].reader_boundary))}</dd>` : ""}</dl><p class="sources">${link('docs/分项规则/第一项政权奠基与统一贡献及能力/00-规则与计分合同.md','查看完整规则 ↗',record)}</p></details>`;

    container.innerHTML = `<section class="panel net-detail-group">${firstItemOverview(record, bulletsByLabel, byLabel)}${zeroNote}${scope}${cards.join("")}${firstTotals(items)}</section>`;
    if (focus) requestAnimationFrame(() => document.getElementById(`net-first-${focus}`)?.scrollIntoView({behavior: "smooth", block: "start"}));
  }


  function thirdJudgmentCards(record, items, labels, groupKey) {
    const wanted = new Set(labels);
    return items
      .filter(item => wanted.has(item.label) && item.reader_kind === "judgment")
      .map(item => metricDetail(item, record, groupKey)).join("");
  }

  const THIRD_MILITARY_SYSTEM_LABELS = ["C1实战交付","C2持续作战","C3体系可靠性"];

  function thirdMilitaryCommonTail(item, value) {
    const text = thirdItemPublicText(item, value || "");
    return cleanNetText(text.replace(/^该方面为(?:[SABCDE](?:[+−-])?档|未单列等级)水平[。；]?\s*/, ""));
  }

  function thirdMilitarySharedSummary(items) {
    const byLabel = new Map(items.filter(item => item.reader_kind === "judgment").map(item => [item.label, item]));
    const rows = THIRD_MILITARY_SYSTEM_LABELS.map(label => byLabel.get(label));
    if (rows.some(item => !item)) return "";
    const tails = rows.map(item => thirdMilitaryCommonTail(item, item?.reader_summary || ""));
    if (!tails[0] || tails.some(text => text !== tails[0])) return "";
    return tails[0];
  }

  function thirdMilitarySharedEvidence(items) {
    const byLabel = new Map(items.filter(item => item.reader_kind === "judgment").map(item => [item.label, item]));
    const rows = THIRD_MILITARY_SYSTEM_LABELS.map(label => byLabel.get(label));
    if (rows.some(item => !item)) return "";
    const tails = [];
    for (const item of rows) {
      const evidence = Array.isArray(item.reader_public_evidence_items) ? item.reader_public_evidence_items : [];
      if (evidence.length !== 1) return "";
      const entry = evidence[0] || {};
      if (entry.public_direction || entry.public_source_coverage || (Array.isArray(entry.public_tags) && entry.public_tags.length)) return "";
      const entryBoundary = cleanNetText(thirdItemPublicText(item, entry.public_boundary || ""));
      const itemBoundary = cleanNetText(thirdItemPublicText(item, item.reader_boundary || ""));
      if (entryBoundary !== itemBoundary) return "";
      const tail = thirdMilitaryCommonTail(item, entry.public_basis || "");
      if (!tail) return "";
      tails.push(tail);
    }
    if (tails.some(text => text !== tails[0])) return "";
    return tails[0];
  }

  function thirdMilitarySystemCards(record, items) {
    const wanted = new Set(THIRD_MILITARY_SYSTEM_LABELS);
    const sharedSummary = thirdMilitarySharedSummary(items);
    const sharedEvidence = thirdMilitarySharedEvidence(items);
    const collapseMaterials = !!(sharedSummary && sharedEvidence && sharedSummary === sharedEvidence);
    const cards = items
      .filter(item => wanted.has(item.label) && item.reader_kind === "judgment")
      .map(item => {
        const publicItem = collapseMaterials
          ? {...item, reader_summary:"", reader_public_evidence_items:[], reader_highlights:[]}
          : sharedSummary
            ? {...item, reader_summary:""}
            : item;
        return metricDetail(publicItem, record, "military");
      })
      .join("");
    const commonText = collapseMaterials ? sharedEvidence : sharedSummary;
    const commonLabel = collapseMaterials ? "军事体系共同裁决依据" : "军事体系共同裁决摘要";
    const common = commonText
      ? `<details class="net-material-summary net-third-shared-summary"><summary>${commonLabel}</summary>${prose(commonText)}</details>`
      : "";
    return common + cards;
  }

  function thirdCalculationRows(items, labels, groupKey, summary) {
    const wanted = new Set(labels);
    const subset = items.filter(item => wanted.has(item.label));
    if (!subset.length) return "";
    const block = calculationBlock(subset, groupKey);
    return block ? block.replace("<summary>本组小计怎么形成？</summary>", `<summary>${esc(summary)}</summary>`) : "";
  }

  function thirdMajorGroups(record, details) {
    const strategic = details.strategic || [];
    const military = details.military || [];
    const strategicSection = `<section id="net-group-strategic" class="panel net-detail-group"><h2>第三项 · 战略收益与国防</h2>
      <div class="net-third-subgroup"><h3>安全状态变化</h3><p class="subline net-third-subgroup-note">主要安全威胁与防线纵深分别按正式规则直接形成战略安全分。</p>
        ${thirdJudgmentCards(record, strategic, ["A1","A2"], "strategic")}
        ${thirdCalculationRows(strategic, ["A120"], "strategic", "安全状态小计怎么形成？")}
      </div>
      <div class="net-third-subgroup"><h3>控制成果质量</h3><p class="subline net-third-subgroup-note">下面三项显示的是进入控制成果合成的采用率，不是领土占比、现实概率或独立得分。</p>
        ${thirdJudgmentCards(record, strategic, ["B1","B2","B4"], "strategic")}
        ${thirdCalculationRows(strategic, ["B80"], "strategic", "控制成果小计怎么形成？")}
      </div>
    </section>`;
    const militarySection = `<section id="net-group-military" class="panel net-detail-group"><h2>第三项 · 军事体系与成本</h2>
      <div class="net-third-subgroup"><h3>军事体系表现</h3><p class="subline net-third-subgroup-note">三方面共同决定军事体系结果；单项参与合成，不单列分值。</p>
        ${thirdMilitarySystemCards(record, military)}
        ${thirdCalculationRows(military, ["C50"], "military", "军事体系结果怎么形成？")}
      </div>
      <div class="net-third-subgroup"><h3>军事代价</h3><p class="subline net-third-subgroup-note">普通军事代价与重大军事净毁损按正式规则合并，避免同一损失重复扣减。</p>
        ${thirdJudgmentCards(record, military, ["普通成本扣分","ML扣分"], "military")}
        ${thirdCalculationRows(military, ["实际扣分"], "military", "实际军事代价怎么形成？")}
      </div>
      <div class="net-third-total">${thirdCalculationRows(military, ["第三项合计"], "military", "第三项总分怎么形成？")}</div>
    </section>`;
    return strategicSection + militarySection;
  }

  function renderGenericMajor(record, major, focus = "") {
    const spec = netMajorSpecs[major];
    const details = record.net?.component_details || {};
    const content = major === "third"
      ? thirdMajorGroups(record, details)
      : spec.groups.map(key => genericNetGroup(record, key, details[key] || [])).join("");
    const container = document.getElementById("net-major-body");
    if (container) container.innerHTML = content || `<section class="panel"><p class="notice">这一项暂未形成可展示的完整分项记录。</p></section>`;
    if (focus) requestAnimationFrame(() => document.getElementById(`net-group-${focus}`)?.scrollIntoView({behavior: "smooth", block: "start"}));
  }

  function majorNav(record, active) {
    const links = ["all", "first", "second", "third", "fourth"].map(key => {
      const label = key === "all" ? "总览" : netMajorSpecs[key].title.replace(/^第[一二三四]项 · /, "");
      return `<a class="${active === key ? "active" : ""}" href="${netHref(record, key)}">${esc(label)}</a>`;
    }).join("");
    return `<nav class="net-major-nav" aria-label="统治绩效详情">${links}</nav>`;
  }

  function majorCard(record, major) {
    const value = majorValue(record, major);
    const spec = netMajorSpecs[major];
    const rawFirstScore = finiteNetNumber(record.net?.first_item_raw_score);
    const firstStatus = record.net?.first_item_status;
    const extra = major === "first" && firstStatus === "APPLICABLE"
      ? rawFirstScore === 0
        ? '<p class="subline">本项适用，但第一项结算分为0；统治绩效附加为0。</p>'
        : rawFirstScore == null
          ? `<p class="subline">本项适用，但第一项结算分未列；当前显示正式附加分 ${scoreNumber(record.net?.first_item_add_on)}。</p>`
          : `<p class="subline">第一项结算分：${scoreNumber(rawFirstScore)}；此处显示计入统治绩效总分的附加分。</p>`
      : major === "first" && firstStatus === "NOT_APPLICABLE"
        ? `<p class="subline">该人物第一项不适用。</p>`
        : major === "first"
          ? `<p class="subline">第一项正式适用状态未发布，因此不作默认推断。</p>`
          : major === "third"
          ? '<p class="subline">250分制净分；战略、控制与军事体系收益合计后，再扣实际军事代价。</p>'
          : major === "fourth"
            ? `<p class="subline">${esc(fourthAdjustmentNote(record))}</p>`
            : "";
    const shownValue = major === "first" && firstStatus === "NOT_APPLICABLE"
      ? "不适用"
      : value == null ? "—" : major === "fourth" && Number(value) > 0 ? `+${scoreNumber(value)}` : scoreNumber(value);
    return `<a class="panel net-major-card" href="${netHref(record, major)}"><h2>${esc(spec.title)}</h2><div class="big">${shownValue}</div>${extra}<p>${esc(spec.description)}</p><p class="sources">查看完整计分逻辑 →</p></a>`;
  }

  function renderNetShell(record, active, body) {
    nav("");
    const systemNav = typeof personSystemNav === "function" ? personSystemNav(record, "net") : "";
    screen.innerHTML = `<a class="back" href="#person/${encodeURIComponent(record.ruler_id)}">← 返回${esc(personLabel(record))}人物页</a><div class="person-head net-detail-head"><div><div class="eyebrow">${esc(record.polity)} / 统治绩效</div><h1>${esc(personLabel(record))} · ${esc(netMajorSpecs[active]?.title || "统治绩效")}</h1><p class="muted">掌权背景：${esc(record.actual_power_window || "未列")} · 统治绩效总分 ${scoreNumber(record.net?.total_score)}</p></div></div><p class="subline net-power-context-note">本项采用的时间与责任范围见各条依据；不能仅凭上述背景时期判断事件是否计入。</p>${systemNav}${majorNav(record, active)}<section class="net-detail-page">${body}</section>`;
  }

  function renderNetLanding(record) {
    renderNetShell(record, "all", `<section class="panel"><h2>怎么读这页</h2><p>先选一个大项。每个指标优先展示当前人物自己的结算逻辑和公式；整份正式结算文件只保留为最深层复核入口。</p></section><div class="net-major-grid">${["first", "second", "third", "fourth"].map(major => majorCard(record, major)).join("")}</div>`);
  }

  function renderNetMajor(record, major, focus) {
    const spec = netMajorSpecs[major];
    if (!spec || major === "all") {
      renderNetLanding(record);
      return;
    }
    const value = majorValue(record, major);
    if (major === "first") {
      renderNetShell(record, major, `<div id="net-major-body"><div class="empty">正在整理当前人物的主链事实…</div></div>`);
      void renderFirstMajor(record, focus);
      return;
    }
    const shownValue = value == null ? "—" : major === "fourth" && Number(value) > 0 ? `+${scoreNumber(value)}` : scoreNumber(value);
    const scoreNote = major === "third"
      ? `本项计入统治绩效总分的净分：${shownValue} / 250；已扣实际军事代价。分项小数来自统一计分公式，不表示历史判断本身具有同等测量精度；阅读时先看公开档位与事实依据。`
      : major === "fourth"
        ? `本项计入统治绩效总分的有符号调整：${shownValue}。 ${fourthAdjustmentNote(record)}`
        : `本项计入统治绩效总分的分值：${shownValue}。`;
    renderNetShell(record, major, `<section class="panel"><h2>${esc(spec.title)}</h2><p>${esc(spec.description)}</p><p class="subline">${esc(scoreNote)}</p></section><div id="net-major-body"><div class="empty">正在整理当前人物的逐项结算逻辑…</div></div>`);
    renderGenericMajor(record, major, focus);
  }

  function parseNetRoute(hash = location.hash) {
    const match = hash.match(/^#net\/([^/?#]+)(?:\/(all|first|second|third|fourth))?(?:\/([^/?#]+))?$/);
    if (!match) return null;
    try {
      return {
        rulerId: decodeURIComponent(match[1]),
        major: match[2] || "all",
        focus: match[3] ? decodeURIComponent(match[3]) : "",
      };
    } catch {
      return null;
    }
  }

  async function loadNetRecord(record) {
    if (!record || record.detail_loaded) return record;
    const id = record.ruler_id;
    if (pendingNetRecords.has(id)) return pendingNetRecords.get(id);
    if (!record.detail_ref) throw new Error(`Missing detail_ref for ${id}`);
    const pending = (async () => {
      const response = await fetch(record.detail_ref, {cache: "no-cache"});
      if (!response.ok) throw new Error(`Failed to load ${record.detail_ref}: HTTP ${response.status}`);
      const payload = await response.json();
      if (!payload?.record || payload.record.ruler_id !== id) throw new Error(`Detail payload ruler_id mismatch for ${id}`);
      const full = {...payload.record, detail_ref: record.detail_ref, detail_loaded: true};
      byId.set(id, full);
      Object.assign(DATA.source_availability, payload.source_availability || {});
      return full;
    })().finally(() => pendingNetRecords.delete(id));
    pendingNetRecords.set(id, pending);
    return pending;
  }

  async function renderNetRoute() {
    const parsed = parseNetRoute();
    if (!parsed) return false;
    const summary = byId.get(parsed.rulerId);
    nav("");
    if (!summary) {
      screen.innerHTML = `<div class="empty"><p>统治绩效详情地址无效。</p><a href="#overview">返回人物总览</a></div>`;
      return true;
    }
    const generation = ++netRenderGeneration;
    screen.innerHTML = `<div class="empty" role="status">正在加载${esc(summary.ruler_name)}的统治绩效详情…</div>`;
    try {
      const record = await loadNetRecord(summary);
      if (generation !== netRenderGeneration || !location.hash.startsWith("#net/")) return true;
      if (!record.net) {
        screen.innerHTML = `<div class="empty"><p>${esc(personLabel(record))}没有可展示的统治绩效正式结算。</p><a href="#person/${encodeURIComponent(record.ruler_id)}">返回人物页</a></div>`;
        return true;
      }
      renderNetMajor(record, parsed.major, parsed.focus);
      window.scrollTo(0, 0);
    } catch (error) {
      console.error(error);
      if (generation === netRenderGeneration) {
        screen.innerHTML = `<div class="empty"><p>统治绩效详情加载失败。</p><p class="subline">人物总览与人物主页仍可正常使用。</p><a href="#person/${encodeURIComponent(summary.ruler_id)}">返回人物页</a></div>`;
      }
    }
    return true;
  }

  function runReaderEnhancer(name) {
    const enhancer = window[name];
    if (enhancer && typeof enhancer.enhance === "function") enhancer.enhance();
  }

  let readerEnhancementQueued = false;
  function enhanceReaderSurface() {
    readerEnhancementQueued = false;
    enhanceHomeRows();
    enhancePersonNet();
    for (const name of ["SecondItemReading", "ReaderReadability", "PersonReadability", "PersonReadingNotes"]) {
      runReaderEnhancer(name);
    }
  }

  function scheduleReaderSurfaceEnhancement() {
    if (readerEnhancementQueued) return;
    readerEnhancementQueued = true;
    requestAnimationFrame(enhanceReaderSurface);
  }

  window.ReaderSurfaceEnhancer = Object.freeze({schedule: scheduleReaderSurfaceEnhancement});
  new MutationObserver(scheduleReaderSurfaceEnhancement).observe(screen, {childList: true, subtree: true});
  ensureNetStyles();
  enhanceReaderSurface();

  screen.addEventListener("click", event => {
    const quickOpen = event.target.closest("[data-home-open]");
    if (quickOpen) {
      event.preventDefault();
      openPersonSection(quickOpen.dataset.homeOpen, quickOpen.dataset.homeSection || "");
      return;
    }

    const polity = event.target.closest("[data-home-polity]");
    if (polity) {
      event.preventDefault();
      applyPolityFilter(polity.dataset.homePolity);
      return;
    }

    const grade = event.target.closest("[data-home-grade]");
    if (grade) {
      event.preventDefault();
      applyImpactFilter(grade.dataset.homeGrade);
      return;
    }

    if (event.target.closest(interactiveSelector)) return;
    const row = event.target.closest("tr[data-home-person]");
    if (!row) return;
    const cell = event.target.closest("td");
    openPersonSection(row.dataset.homePerson, cell?.dataset.homeSection || "");
  });

  screen.addEventListener("keydown", event => {
    if (event.key !== "Enter" && event.key !== " ") return;

    const grade = event.target.closest("[data-home-grade]");
    if (grade) {
      event.preventDefault();
      applyImpactFilter(grade.dataset.homeGrade);
      return;
    }

    const cell = event.target.closest("td[data-home-section]");
    const row = cell?.closest("tr[data-home-person]");
    if (!cell || !row) return;
    event.preventDefault();
    openPersonSection(row.dataset.homePerson, cell.dataset.homeSection);
  });

  const baseRoute = route;
  window.removeEventListener("hashchange", baseRoute);
  route = function() {
    if (location.hash.startsWith("#net/")) {
      void renderNetRoute();
      return;
    }
    netRenderGeneration += 1;
    baseRoute();
  };
  window.addEventListener("hashchange", route);

  if (location.hash.startsWith("#net/")) void renderNetRoute();
})();
