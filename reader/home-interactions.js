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

function firstB1Markup(item) {
  const data = item?.reader_public_b1 || {};
  return [["起点", data.public_start_basis], ["主要对手", data.public_opponent_basis], ["完成速度", data.public_efficiency_basis]]
    .filter(([, value]) => value)
    .map(([label, value]) => `<div class="label">${esc(label)}</div>${prose(value)}`).join("");
}

function firstCostPublicText(value) {
  const severity = ["无显著代价","很低成本","较低成本","中等成本","较高成本","高成本","极高成本","灾难级成本"];
  const chinese = {"零":0,"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7};
  return String(value || "")
    .replace(/第([0-7一二三四五六七])级(?:成本)?/g, (_, level) => {
      const index = chinese[level] != null ? chinese[level] : Number(level);
      return severity[index] || level;
    });
}

function firstCostMarkup(item) {
  const data = item?.reader_public_cost || {};
  const publicLevel = firstCostPublicText(data.public_level_label);
  const fields = [["成本程度", publicLevel], ["证据状态", data.public_status_label], ["责任时期", data.public_responsibility_window], ["完整成本说明", firstCostPublicText(data.public_basis)]];
  const facts = fields.filter(([, value]) => value).map(([label, value]) => `<div class="label">${esc(label)}</div>${prose(value)}`).join("");
  const gaps = (data.public_unresolved_gaps || []).map(value => `<li>${esc(firstCostPublicText(value))}</li>`).join("");
  const sources = (data.public_source_links || []).filter(source => /^https?:\/\//.test(source.url))
    .map(source => `<a href="${esc(source.url)}" target="_blank" rel="noopener">${esc(source.label)} ↗</a>`).join(" ");
  return `${facts}${gaps ? `<div class="label">证据缺口</div><ul>${gaps}</ul>` : ""}${sources ? `<p class="sources">${sources}</p>` : ""}`;
}

function firstCommanderMarkup(item) {
  const source = item?.reader_public_commander;
  if (!source?.public_basis || !source?.public_boundary || !Array.isArray(source.public_battles)) {
    return '<p class="notice">本人统帅的公开说明尚未同步。</p>';
  }
  const battles = source.public_battles.length
    ? `<details class="first-item-battle-evidence"><summary>查看已明确记载的战役与统筹成果</summary><ul class="first-item-battles">${source.public_battles.map(battle => `<li><strong>${esc(battle.name)}</strong> · ${esc(battle.role)} · ${esc(battle.result)}成果 · ${esc(battle.difficulty ? `${battle.difficulty}难度` : '难度未单列')} <a href="military.html#search=${encodeURIComponent(battle.name)}">查看战役档案 ↗</a></li>`).join('')}</ul></details>`
    : '';
  return `<div class="first-item-commander-public"><div class="label">为什么这样评</div>${prose(source.public_basis)}<div class="label">责任与限制</div>${prose(source.public_boundary)}${battles}</div>`;
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
      title: "净收益计分总览",
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
      title: "第三项 · 军事与边疆净收益",
      description: "战略安全收益、军事体系兑现与军事成本在同一项内结算。",
      groups: ["strategic", "military"],
    },
    fourth: {
      title: "第四项 · 文明与国家整合",
      description: "以有符号调整进入总榜，正向、负向与零调整都保留具体结算依据。",
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
    civilization: "第四项 · 文明与国家整合",
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
    const hash = "#person/" + encodeURIComponent(id);
    if (!section) {
      go(hash);
      return;
    }
    if (location.hash === hash) {
      route();
      scrollWhenReady(section);
      return;
    }

    const afterRoute = () => {
      window.removeEventListener("hashchange", afterRoute);
      scrollWhenReady(section);
    };
    window.addEventListener("hashchange", afterRoute);
    location.hash = hash;
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
        cell.classList.add("home-jump-cell");
        cell.dataset.homeSection = section;
        cell.tabIndex = 0;
        cell.setAttribute("role", "link");
        const label = section === "person-outcome" ? "净收益" : section === "person-capability" ? "人物画像" : "历史影响";
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
      .net-material-boundary>p{margin:5px 0 0;font-size:11px;line-height:1.7}\n      .net-material-summary{margin:10px 0 0}\n      .net-material-summary>summary{font-size:12px;color:var(--muted)}
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
    if (item?.value == null) return item?.unit === "不单独计分" ? "不单独计分" : "—";
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
      return heading?.textContent.trim() === "净收益构成";
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
      sourceLink.textContent = "查看完整净收益计分页 →";
    }
    panel.dataset.netLinks = "done";
  }

  function compactNetReading(record) {
    const section = netEvidenceSection();
    const reading = section?.querySelector(".net-reading");
    if (!reading || reading.dataset.netCompact === "done") return;
    const groups = Object.entries(record.net?.component_details || {});
    if (!groups.length) return;

    reading.innerHTML = `<p class="reading-intro">这里保留各大项的快速摘要。完整的逐人判断、变量、公式和计分来源放到独立净收益计分页，避免单人主页无限变长。</p><p class="sources"><a href="${netHref(record, "all")}">打开完整净收益计分页 →</a></p>`;

    for (const [key, items] of groups) {
      if (!Array.isArray(items)) continue;
      const details = document.createElement("details");
      details.className = "net-summary-group";
      const major = netGroupMajor[key] || "all";
      const judgments = items.filter(item => item.reader_kind === "judgment" && (item.value != null || item.unit === "不单独计分" || item.public_level_label));
      const firstNotApplicable = key === "first" && items.every(item =>
        item.value == null || (item.label === "附加F" && Number(item.value) === 0)
      );
      const preview = firstNotApplicable
        ? `<p class="notice">该人物不适用第一项，本项不参与净收益计分。</p>`
        : judgments.map(item => `<div class="component"><span>${esc(item.public_component_label || item.label)}</span><b>${esc(netValue(item, key))}</b></div>`).join("");
      details.innerHTML = `<summary>${esc(netGroupNames[key] || key)}</summary>${preview}<p class="sources"><a href="${netHref(record, major, key)}">查看这组完整计分逻辑 →</a></p>`;
      reading.append(details);
    }
    reading.dataset.netCompact = "done";
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
    const isCost = itemLabel === "普通成本扣分";
    text = text
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
      .replace(/([0-5])→([0-5])/g, (_, from, to) => `${thirdGradeText(from)}→${thirdGradeText(to)}`)
      .replace(/三轴(?:维持)?([0-5])\/\1\/\1/g, (_, level) => `三方面均为${thirdGradeText(level)}`)
      .replace(/(支持|阻断|维持|压至|达到)([0-5])档/g, (_, verb, level) => `${verb}${thirdGradeText(level)}`)
      .replace(/([0-5])档(高位|中位|低位)/g, (_, level, position) => `${thirdGradeText(level)}${position}`)
      .replace(/([一二三四五六七])档本人改善/g, (_, count) => `${count}个等级的本人改善`)
      .replace(/客观变动[+-]?\d+档按[+-]?\d+档本人责任/g, "客观状态变化按已裁本人责任计入")
      .replace(/\bA1\b/g, "主要安全威胁")
      .replace(/\bA2\b/g, "防线与纵深")
      .replace(/\bB1\b/g, "控制范围")
      .replace(/\bB2\b/g, "战略价值")
      .replace(/\bB4\b/g, "成果稳定性")
      .replace(/三轴/g, "三方面");
    return text;
  }
  const SECOND_PUBLIC_GROUPS = new Set(["method", "finance", "handoff"]);
  const CIV_PUBLIC_DIRECTION = {POSITIVE:"正向",NEGATIVE:"负向",BALANCED:"正负相抵"};
  const CIV_PUBLIC_POSITION = {HIGH:"高位",MID:"中位",LOW:"低位",HIGHEST:"极端上沿"};
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

  function civilizationPublicStatus(item, formalLevel = "") {
    const parts = String(item?.grade || "").split("/").map(value => value.trim());
    const direction = CIV_PUBLIC_DIRECTION[parts[0]] || "";
    const position = CIV_PUBLIC_POSITION[parts[2]] || "";
    return [direction, formalLevel, position].filter(Boolean).join(" · ");
  }

  function civilizationExactHow(item, fallback) {
    const parts = String(item?.grade || "").split("/").map(value => value.trim());
    const magnitude = parts[1]?.match(/^CIV([1-4])$/);
    const position = parts[2];
    const points = magnitude ? CIV_PUBLIC_POINTS[Number(magnitude[1])]?.[position] : null;
    const direction = CIV_PUBLIC_DIRECTION[parts[0]] || "";
    if (points == null || !direction) return fallback;
    const signed = parts[0] === "NEGATIVE" ? -points : parts[0] === "BALANCED" ? 0 : points;
    return `第${magnitude[1]}级影响的${CIV_PUBLIC_POSITION[position] || position}固定对应${points}分；方向为${direction}，所以当前调整为${signed > 0 ? "+" : ""}${signed}分。`;
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

  function detailedHowText(item, groupKey, how, record) {
    const groupItems = new Map((record?.net?.component_details?.[groupKey] || []).map(entry => [entry.label, entry]));
    if (groupKey === "strategic" && ["A1","A2"].includes(item.label)) {
      const a1 = groupItems.get("A1");
      const a2 = groupItems.get("A2");
      const total = groupItems.get("A120");
      const subtotal = [a1?.value, a2?.value, total?.value].every(value => value != null)
        ? `两个战略安全轴随后直接相加：${a1.value} + ${a2.value} = ${total.value}分。`
        : "";
      return `本轴分数 = 0.6 × 轨迹值；轨迹值由终点状态价值、本人改善、本人回吐、专项信用和负向调整共同形成。当前本轴：${how}${subtotal ? " " + subtotal : ""}`;
    }
    if (groupKey === "strategic" && ["B1","B2","B4"].includes(item.label)) {
      const b1 = groupItems.get("B1");
      const b2 = groupItems.get("B2");
      const b4 = groupItems.get("B4");
      const total = groupItems.get("B80");
      const current = [b1?.value, b2?.value, b4?.value, total?.value].every(value => value != null)
        ? `当前三项得分率为控制范围 ${b1.value}%、战略价值 ${b2.value}%、成果稳定性 ${b4.value}%；正式合成结果为 ${total.value}分。`
        : "";
      return `三项先各自形成得分率；控制范围与战略价值按55%/45%合成，再由成果稳定性修正。${current ? " " + current : ""} 当前本项：${how}`;
    }
    if (groupKey === "military" && ["C1实战交付","C2持续作战","C3体系可靠性"].includes(item.label)) {
      const axes = ["C1实战交付","C2持续作战","C3体系可靠性"].map(label => groupItems.get(label)).filter(Boolean);
      const total = groupItems.get("C50");
      const statuses = axes.map(entry => thirdPublicText(entry.public_level_label || entry.reader_summary || "", entry.label)).filter(Boolean);
      const current = statuses.length && total
        ? `当前三方面：${statuses.join("；")}；${thirdPublicText(total.public_level_label || "", total.label)}，军事体系结果为 ${total.value}分。`
        : "";
      return `三方面分别定档但不单独加分，共同确定军事体系整体档位。整体档位对应50分项得分率：E档0%—29%、D档30%—44%、C档45%—59%、B档60%—74%、A档75%—89%、S档90%—100%。${current ? " " + current : ""} 当前本项：${how}`;
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

  function metricMaterialCards(item, groupKey) {
    if (!MATERIAL_CARD_GROUPS.has(groupKey)) return "";
    const evidence = Array.isArray(item.reader_public_evidence_items) ? item.reader_public_evidence_items : [];
    if (!evidence.length) return "";
    const cards = evidence.map(entry => {
      const thirdItem = groupKey === "strategic" || groupKey === "military";
      const format = value => thirdItem ? thirdPublicText(value, item.label) : cleanNetText(value);
      const title = format(entry?.public_label || entry?.public_role || "正式裁决材料");
      const role = format(entry?.public_role || "");
      const direction = format(entry?.public_direction || "");
      const tags = Array.isArray(entry?.public_tags) ? entry.public_tags.map(format).filter(Boolean) : [];
      const chips = [...new Set([role, direction, ...tags].filter(Boolean))]
        .map(value => `<span class="net-material-chip">${esc(value)}</span>`).join("");
      const basis = format(entry?.public_basis || "");
      const boundary = format(entry?.public_boundary || "");
      const basisMarkup = thirdItem ? thirdBasisMarkup(entry?.public_basis || "", item.label) : (basis ? `<p class="net-material-body">${esc(basis)}</p>` : "");
      return `<li class="net-material-card"><div class="net-material-head"><strong>${esc(title)}</strong>${chips ? `<span class="net-material-meta">${chips}</span>` : ""}</div>${basisMarkup}${boundary ? `<details class="net-material-boundary"><summary>该材料的范围与边界</summary><p>${esc(boundary)}</p></details>` : ""}</li>`;
    }).join("");
    return cards ? `<div class="label">正式裁决材料</div><ul class="net-material-list">${cards}</ul>` : "";
  }

  function metricDetail(item, record, groupKey = "") {
    const displayLabel = item.public_component_label || item.label;
    const intro = netPublicIntro[displayLabel] || netPublicIntro[item.label] || "";
    const thirdItem = groupKey === "strategic" || groupKey === "military";
    const formatPublic = value => thirdItem ? thirdPublicText(value, item.label) : cleanNetText(value);
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
    const logic = (structuredMaterials ? [intro] : [intro, summary]).filter(Boolean).join("\n");
    const formalLevel = MATERIAL_CARD_GROUPS.has(groupKey) ? formatPublic(item.public_level_label || "") : "";
    const full = fullBasis && fullBasis !== summary
      ? `<details><summary>当前人物的完整裁决原文</summary>${prose(fullBasis)}</details>`
      : "";
    const materialCards = metricMaterialCards(item, groupKey);
    const summaryFold = structuredMaterials && summary
      ? `<details class="net-material-summary"><summary>总体裁决摘要</summary>${prose(summary)}</details>`
      : "";
    const facts = materialCards || (highlights.length
      ? `<div class="label">关键事实</div><ul>${highlights.map(text => `<li>${esc(text)}</li>`).join("")}</ul>`
      : "");
    const limit = boundary ? `<div class="label">${materialCards ? "总体范围与边界" : "限制与边界"}</div>${prose(boundary)}` : "";
    const formula = scoreHowDetails(item, groupKey, how, formalLevel, record);
    const secondSource = SECOND_PUBLIC_GROUPS.has(groupKey) ? ` data-second-source-label="${esc(item.label)}"` : "";
    return `<details class="net-metric-detail"${secondSource}><summary><span><strong>${esc(displayLabel)}</strong>${intro ? `<small>${esc(intro)}</small>` : ""}${formalLevel ? `<small class="net-formal-level">正式层级：${esc(formalLevel)}</small>` : ""}</span><b>${esc(netValue(item, groupKey))}</b></summary><div class="net-metric-body">${logic ? `<div class="label">当前人物结算逻辑</div>${prose(logic)}` : ""}${facts}${summaryFold}${limit}${formula}${full}${auditSourceBlock(item, record)}</div></details>`;
  }

  function calculationBlock(items, groupKey = "") {
    const calculations = items.filter(item => item.reader_kind === "calculation" && item.value != null);
    if (!calculations.length) return "";
    const thirdItem = groupKey === "strategic" || groupKey === "military";
    return `<details class="net-calculations"><summary>计算过程与小计</summary>${calculations.map(item => {
      const how = thirdItem ? thirdPublicText(item.reader_how || "按正式公式换算。", item.label) : cleanNetText(item.reader_how || "按正式公式换算。");
      return `<div class="component"><span><strong>${esc(item.public_component_label || item.label)}</strong><small>${esc(how)}</small></span><b>${esc(netValue(item, groupKey))}</b></div>`;
    }).join("")}</details>`;
  }

  function genericNetGroup(record, key, items) {
    const judgments = items.filter(item => item.reader_kind === "judgment" && item.value != null);
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
    const calculation = item.reader_how || "";
    const percent = firstPublicSharePercent(publicOutcome);
    const project = publicOutcome.public_project ? `<div class="label">共同项目</div>${prose(firstPublicOutcomeText(publicOutcome.public_project))}` : "";
    const facts = firstPublicOutcomeParts(publicOutcome)
      .map(([label, value]) => `<div class="label">${esc(label)}</div>${prose(firstPublicOutcomeText(value))}`)
      .join("");
    const share = percent ? `<div class="label">成果占比</div>${prose(`约${percent}%`)}` : "";
    const rules = `<details class="first-item-rule-box"><summary>这个分怎么算？</summary><div class="label">A看什么</div>${prose("A只评价建国、复国或统一主链中，本人最终真正留下的稳定控制成果。继承来的既有版图不算本人新增；起点、对手、速度、组织和本人军事能力分别放到B1、B2、C。")}<div class="label">有效控制信用U</div>${prose("新增稳定控制按100%计，恢复旧有稳定控制按50%计；1000代表一个全国核心统一尺度。U不是人口、面积或军队人数。")}${prose(`单人项目按统一贡献曲线换分；共同项目先算项目A池，再按本人控制信用占项目总信用的比例分配。${calculation ? `\n当前人物正式代入：${calculation}` : ""}`)}</details>`;
    return firstMetricDetail("net-first-a", "统一成果", "先看本人真正留下了什么", item, `${project}${facts}${share}${rules}`, record);
  }

  function renderFirstB1(item, bullets, record) {
    const rules = `<details class="first-item-rule-box"><summary>这个分怎么算？</summary>${prose(item.reader_public_b1?.public_calculation || "")}</details>`;
    return firstMetricDetail("net-first-b1", "起点、强敌与速度", "起点、主要对手和完成效率", item, `${firstB1Markup(item)}${rules}`, record);
  }


  function renderFirstB2(item, bullets, record) {
    const result = bullets["B2结算"] || "";
    const parallel = bullets["并行执行"] || "";
    const coverage = bullets["团队能力覆盖与组织杠杆"] || bullets["能力覆盖/组织杠杆"] || "";
    const integration = bullets["异质整合"] || "";
    const basis = bullets["裁决依据"] || "";
    const facts = `${parallel ? `<div class="label">多线任务怎样同时推进</div>${prose(firstFactText(parallel))}` : ""}${coverage ? `<div class="label">团队怎样分工</div>${prose(firstFactText(coverage))}` : ""}${integration ? `<div class="label">旧部、降附者与异质集团怎样整合</div>${prose(firstFactText(integration))}` : ""}${basis ? `<div class="label">本人组织表现与限制</div>${prose(firstFactText(basis))}` : ""}${bullets["材料来源"] ? `<details><summary>史料与归责来源</summary><p class="sources">${firstEvidenceMarkup(bullets["材料来源"], "B2组织与整合")}</p></details>` : ""}`;
    const rules = `<details class="first-item-rule-box"><summary>这个分怎么算？</summary>${prose("B2看创业或统一机器能否多线并行、把高难任务交给专业责任中心，并把不同地域和旧集团稳定接入同一执行体系。三个维度均分为 E、D、C、B、A、S 六档，依次对应0、2、4、6、8、10分，三项相加。")}${result ? prose(`当前人物正式结算：${firstFactText(result)}`) : ""}</details>`;
    return firstMetricDetail("net-first-b2", "创业组织与政治整合", "多线并行、专业分工与异质整合", item, `${facts}${rules}`, record);
  }

  function renderFirstC(item, bullets, record) {
    const facts = firstCommanderMarkup(item);
    const grade = firstItemPublicText(item.grade || "");
    const how = firstItemPublicText(item.reader_how || "");
    const rules = `<details class="first-item-rule-box"><summary>这个分怎么算？</summary>${prose(`这里只看本人亲自承担的整体部署、战役指挥或临阵处理；将领独立完成的战果不直接归到本人名下。\\n当前能力裁决：${grade || "按正式能力档裁决"}。\\n当前换算：${how || "按正式能力档与责任路线换算。"}\\n当前结果：${item.value} 分。`)}</details>`;
    return firstMetricDetail("net-first-c", "本人统帅", "只看本人亲自承担并完成的军事指挥事实", item, `${facts}${rules}`, record);
  }

  function renderFirstCost(item, record) {
    const level = firstCostPublicText(item.reader_public_cost?.public_level_label || "");
    const rule = `<details class="first-item-rule-box"><summary>这个分怎么算？</summary>${prose(`当前成本裁决：${level || "按正式成本严重度裁决"}。\\n换算规则：按正式成本严重度与同级位置查固定扣分表。\\n当前换算：${firstCostPublicText(item.reader_how || "")}\\n当前扣减：${item.value} 分。`)}</details>`;
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
    if ([a, b1, b2, c, gross, net, addOn].some(value => value == null)) return "";
    return `<div class="net-detail-total"><div class="label">第一项结算</div><p class="first-item-scoreline">统一成果 ${a} + 创业难度与效率 ${b1} + 创业组织 ${b2} + 本人统帅 ${c} − 战争代价 ${cost ?? 0} = <strong>原始净收益 ${net} / 240</strong> → 总榜附加 <strong>+${addOn}</strong></p><details><summary>查看完整折算公式</summary>${prose(`四轴毛分 = A + B1 + B2 + C = ${a} + ${b1} + ${b2} + ${c} = ${gross}。\nS1 = max(0, ${gross} − ${cost ?? 0}) = ${net}。\n总榜附加 F = 0.20 × 637 × (S1 / 240)^1.25 = ${addOn}。`)}</details></div>`;
  }

  function firstItemOverview(record, bulletsByLabel, byLabel) {
    const a = byLabel["A统一贡献"]?.reader_public_outcome || {};
    const b1 = byLabel["B1创业难度与效率"]?.reader_public_b1 || {};
    const b2 = bulletsByLabel["B2组织与整合"] || {};
    const cost = byLabel["军事成本扣分"];
    const aPercent = firstPublicSharePercent(a);
    const aText = [
      a.public_project ? `共同项目：${a.public_project}` : "",
      ...firstPublicOutcomeParts(a).map(([, value]) => firstPublicOutcomeText(value)),
      aPercent ? `成果占比：约${aPercent}%` : "",
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
    const cText = byLabel["C军事统帅与战争解题"]?.reader_public_commander?.public_basis || "";
    const costText = cost?.reader_public_cost?.public_basis || "";
    const items = record.net?.component_details?.first || [];
    const parts = Object.fromEntries(items.map(item => [item.label, item.value]));
    const score = [parts["A统一贡献"], parts["B1创业难度与效率"], parts["B2组织与整合"], parts["C军事统帅与战争解题"], parts["第一项净分"], parts["附加F"]];
    return `<section class="first-item-overview"><h2>先看${esc(personLabel(record))}在这条主链里实际做了什么</h2><p class="subline">下面默认只放当前人物的成果、难题、组织、统帅和代价；指标定义与公式都收进折叠项。</p><div class="first-item-story-grid">${aText ? `<div class="first-item-story-card"><b>统一成果</b><p>${esc(aText)}</p></div>` : ""}${b1Parts.length ? `<div class="first-item-story-card"><b>起点、强敌与速度</b><ul>${b1Parts.map(([label, value]) => `<li><strong>${label}：</strong>${esc(value)}</li>`).join("")}</ul></div>` : ""}${b2Parts.length ? `<div class="first-item-story-card"><b>组织与整合</b><ul>${b2Parts.map(([label, value]) => `<li><strong>${label}：</strong>${esc(firstFactText(value))}</li>`).join("")}</ul></div>` : ""}${cText ? `<div class="first-item-story-card"><b>本人统帅</b><p>${esc(cText)}</p></div>` : ""}${costText ? `<div class="first-item-story-card wide"><b>战争代价</b><p>${esc(costText)}</p></div>` : ""}</div>${score.every(value => value != null) ? `<div class="first-item-scoreline">统一成果 ${score[0]} + 创业难度与效率 ${score[1]} + 创业组织 ${score[2]} + 本人统帅 ${score[3]} − 战争代价 ${parts["军事成本扣分"] ?? 0} = <strong>原始净收益 ${score[4]}</strong> → 总榜附加 <strong>+${score[5]}</strong></div>` : ""}</section>`;
  }

  async function renderFirstMajor(record, focus = "") {
    const items = record.net?.component_details?.first || [];
    const container = document.getElementById("net-major-body");
    if (!container) return;
    const firstNotApplicable = items.every(item =>
      item.value == null || (item.label === "附加F" && Number(item.value) === 0)
    );
    if (firstNotApplicable) {
      container.innerHTML = `<section class="panel"><h2>${esc(netMajorSpecs.first.title)}</h2><p class="notice">本项只评价建国、复国或统一创业主链；该人物不适用，因此这一项不参与净收益计分。</p></section>`;
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
    const zeroNote = record.net?.first_item_status === "APPLICABLE" && Number(record.net?.first_item_raw_score) === 0
      ? '<p class="notice"><strong>本项适用，但没有形成正向净收益。</strong>这与“不适用”不同：本项已经进入结算，只是成果在扣除本人窗口内军事代价后归零，因此总榜附加为0。</p>'
      : "";
    const scope = `<details class="first-item-scope"><summary>本项采用的时间与责任范围</summary><dl>${ownA.public_project ? `<dt>共同项目</dt><dd>${esc(firstPublicOutcomeText(ownA.public_project))}</dd>` : ""}${firstPublicOutcomeParts(ownA).map(([label, value]) => `<dt>${esc(label)}</dt><dd>${esc(firstPublicOutcomeText(value))}</dd>`).join("")}${windowText ? `<dt>完成效率计时</dt><dd>${esc(firstFactText(windowText))}</dd>` : ""}${byLabel["军事成本扣分"]?.reader_boundary ? `<dt>军事成本责任范围</dt><dd>${esc(byLabel["军事成本扣分"].reader_boundary)}</dd>` : ""}</dl><p class="sources">${link('docs/分项规则/第一项政权奠基与统一贡献及能力/00-规则与计分合同.md','查看完整规则合同 ↗',record)}</p></details>`;

    container.innerHTML = `<section class="panel net-detail-group">${firstItemOverview(record, bulletsByLabel, byLabel)}${zeroNote}${scope}${cards.join("")}${firstTotals(items)}</section>`;
    if (focus) requestAnimationFrame(() => document.getElementById(`net-first-${focus}`)?.scrollIntoView({behavior: "smooth", block: "start"}));
  }

  function renderGenericMajor(record, major, focus = "") {
    const spec = netMajorSpecs[major];
    const details = record.net?.component_details || {};
    const content = spec.groups.map(key => genericNetGroup(record, key, details[key] || [])).join("");
    const container = document.getElementById("net-major-body");
    if (container) container.innerHTML = content || `<section class="panel"><p class="notice">这一项暂未形成可展示的完整分项记录。</p></section>`;
    if (focus) requestAnimationFrame(() => document.getElementById(`net-group-${focus}`)?.scrollIntoView({behavior: "smooth", block: "start"}));
  }

  function majorNav(record, active) {
    const links = ["all", "first", "second", "third", "fourth"].map(key => {
      const label = key === "all" ? "总览" : netMajorSpecs[key].title.replace(/^第[一二三四]项 · /, "");
      return `<a class="${active === key ? "active" : ""}" href="${netHref(record, key)}">${esc(label)}</a>`;
    }).join("");
    return `<nav class="net-major-nav" aria-label="净收益计分页">${links}</nav>`;
  }

  function majorCard(record, major) {
    const value = majorValue(record, major);
    const spec = netMajorSpecs[major];
    const extra = major === "first" && record.net?.first_item_status === "APPLICABLE"
      ? Number(record.net.first_item_raw_score) === 0
        ? '<p class="subline">本项适用，但原始净收益为0；总榜附加为0。</p>'
        : `<p class="subline">第一项原始净收益：${number(record.net.first_item_raw_score)}；此处显示进入总榜的附加分。</p>`
      : major === "first" ? `<p class="subline">该人物第一项不适用。</p>` : "";
    const shownValue = value == null ? "—" : major === "fourth" && Number(value) > 0 ? `+${number(value)}` : number(value);
    return `<a class="panel net-major-card" href="${netHref(record, major)}"><h2>${esc(spec.title)}</h2><div class="big">${shownValue}</div>${extra}<p>${esc(spec.description)}</p><p class="sources">查看完整计分逻辑 →</p></a>`;
  }

  function renderNetShell(record, active, body) {
    nav("");
    screen.innerHTML = `<a class="back" href="#person/${encodeURIComponent(record.ruler_id)}">← 返回${esc(personLabel(record))}人物页</a><div class="person-head net-detail-head"><div><div class="eyebrow">${esc(record.polity)} / 净收益计分</div><h1>${esc(personLabel(record))} · ${esc(netMajorSpecs[active]?.title || "净收益")}</h1><p class="muted">掌权背景：${esc(record.actual_power_window || "未列")} · 总榜净收益 ${number(record.net?.total_score)}</p></div></div><p class="subline net-power-context-note">本项采用的时间与责任范围见各条依据；不能仅凭上述背景时期判断事件是否计入。</p>${majorNav(record, active)}<section class="net-detail-page">${body}</section>`;
  }

  function renderNetLanding(record) {
    renderNetShell(record, "all", `<section class="panel"><h2>怎么读这页</h2><p>先选一个大项。每个指标优先展示当前人物自己的结算逻辑和公式；整份正式结算文件只保留为最深层审计入口。</p></section><div class="net-major-grid">${["first", "second", "third", "fourth"].map(major => majorCard(record, major)).join("")}</div>`);
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
    const shownValue = value == null ? "—" : major === "fourth" && Number(value) > 0 ? `+${number(value)}` : number(value);
    const scoreNote = `本项进入总榜的分值：${shownValue}。`;
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
      screen.innerHTML = `<div class="empty"><p>净收益详情地址无效。</p><a href="#overview">返回人物总览</a></div>`;
      return true;
    }
    const generation = ++netRenderGeneration;
    screen.innerHTML = `<div class="empty" role="status">正在加载${esc(summary.ruler_name)}的净收益计分逻辑…</div>`;
    try {
      const record = await loadNetRecord(summary);
      if (generation !== netRenderGeneration || !location.hash.startsWith("#net/")) return true;
      if (!record.net) {
        screen.innerHTML = `<div class="empty"><p>${esc(personLabel(record))}没有可展示的净收益正式结算。</p><a href="#person/${encodeURIComponent(record.ruler_id)}">返回人物页</a></div>`;
        return true;
      }
      renderNetMajor(record, parsed.major, parsed.focus);
      window.scrollTo(0, 0);
    } catch (error) {
      console.error(error);
      if (generation === netRenderGeneration) {
        screen.innerHTML = `<div class="empty"><p>净收益计分详情加载失败。</p><p class="subline">人物总览与人物主页仍可正常使用。</p><a href="#person/${encodeURIComponent(summary.ruler_id)}">返回人物页</a></div>`;
      }
    }
    return true;
  }

  new MutationObserver(() => {
    enhanceHomeRows();
    enhancePersonNet();
  }).observe(screen, {childList: true, subtree: true});
  enhanceHomeRows();
  ensureNetStyles();
  enhancePersonNet();

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
