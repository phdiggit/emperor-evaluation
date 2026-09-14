"use strict";

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
      description: "只适用于建国、复国或统一创业主链；A、B1、B2、C先形成第一项净分，再折成总榜附加分。",
      groups: ["first"],
    },
    second: {
      title: "第二项 · 治国净收益",
      description: "制度行政、财政民生与交班质量共同构成治国净收益。",
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
    finance: "第二项 · 财政与民生",
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
    "治国净收益": "second",
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
    "A1": "看安全与控制状态相对接手时发生了什么变化，并只计本人可归责部分。",
    "A2": "看重要战略目标最终取得、维持或丧失了多少实际安全收益。",
    "B1": "看本人新增或稳住了多少有效控制规模，避免把继承存量重复算作成果。",
    "B2": "看取得的控制与军事成果有多大战略价值，而不是只按面积或战役数量计分。",
    "B4": "看这些安全成果能否稳定交班，而不是在本人离场前后迅速失效。",
    "C1实战交付": "看军事体系在真实高压任务中能否把国家资源转化为可兑现的战场结果。",
    "C2持续作战": "看军事体系能否跨阶段持续动员、补充和完成任务。",
    "C3体系可靠性": "看体系在不同战区和压力下是否稳定，还是频繁出现结构性失灵。",
    "普通成本扣分": "看本人统治窗口内战争对本方军队、军事资产、后勤和持续动员造成的实际成本。",
    "ML扣分": "只在重大军事净毁损同时满足结果、成本和本人责任门槛时追加扣分，普通失败不会自动触发。",
    "A国家共同体": "看本人窗口对不同区域、群体与身份之间的参与、接纳和排斥造成了什么净变化。",
    "B教育与人才": "看教育供给、学习机会和跨地域跨身份流动是否出现可归责的真实变化。",
    "C文化知识": "看知识生产、保存、传播和文化生态是否出现可归责的真实变化。",
  };

  const firstItemDocs = {
    "A统一贡献": "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/01-第一项A统一主链客观贡献正式结算.md",
    "B1创业难度与效率": "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/02-第一项B1创业难度与战略效率正式结算.md",
    "B2组织与整合": "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/03-第一项B2创业组织与政治整合正式结算.md",
    "C军事统帅与战争解题": "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/04-第一项C本人军事统帅与战争解题能力正式结算.md",
  };

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
        cell.setAttribute("aria-label", `查看${record.ruler_name}的${label}`);
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
        meta.append(polity, document.createTextNode(` · ${record.actual_power_window}`));
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
      .net-audit-sources{margin-top:14px}
      .net-audit-sources>.subline{margin-top:6px}
      .net-detail-group{margin:0 0 20px}.net-detail-group>h2{margin-top:0}
      .net-detail-total{border-left:3px solid var(--green);padding:12px 16px;background:#eef1ea;margin-top:18px}
      @media(max-width:700px){.net-major-grid{grid-template-columns:1fr}.net-major-nav{gap:5px}.net-metric-detail>summary{grid-template-columns:1fr auto}}
    `;
    document.head.append(style);
  }

  function netValue(item) {
    if (item?.value == null) return item?.unit === "不单独计分" ? "不单独计分" : "—";
    const signed = item.value > 0 && item.label?.includes("文明") ? `+${item.value}` : String(item.value);
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
      const label = row.querySelector("span")?.textContent.trim();
      const major = overviewMajorByLabel[label];
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
      const judgments = items.filter(item => item.reader_kind === "judgment" && item.value != null);
      const firstNotApplicable = key === "first" && items.every(item =>
        item.value == null || (item.label === "附加F" && Number(item.value) === 0)
      );
      const preview = firstNotApplicable
        ? `<p class="notice">该人物不适用第一项，本项不参与净收益计分。</p>`
        : judgments.map(item => `<div class="component"><span>${esc(item.label)}</span><b>${esc(netValue(item))}</b></div>`).join("");
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
    return String(value ?? "")
      .replace(/\bC-([0-9]+)-(LOW|MID|HIGH)\b/g, (_, n, p) => `第${n}档·${({LOW:"低位",MID:"中位",HIGH:"高位"})[p]}`)
      .replace(/\bC-0\b/g, "第0档")
      .replace(/\bML([0-4])\b/g, "军事净毁损第$1级")
      .replace(/\bCIV([0-4])\b/g, "文明影响量级$1")
      .replace(/\bDA([0-9]+)\b/g, "破坏放大第$1级")
      .replace(/\bHYBRID\b/g, "战略统筹与本人主帅／临阵并存")
      .replace(/\bSTRATEGIC_COMMAND\b/g, "战略统筹路线")
      .replace(/\bNONE\b/g, "未形成可计的本人统帅责任")
      .replace(/\bHIGH\b/g, "高位")
      .replace(/\bMID\b/g, "中位")
      .replace(/\bLOW\b/g, "低位")
      .replace(/\bmiddle-upper\b/g, "中上位")
      .replace(/\bmiddle-lower\b/g, "中下位")
      .replace(/\bupper\b/g, "上位")
      .replace(/\bmiddle\b/g, "中位")
      .replace(/\blower\b/g, "下位")
      .replace(/\bPOSITIVE\b/g, "正向")
      .replace(/\bNEGATIVE\b/g, "负向")
      .replace(/\bBALANCED\b/g, "正负相抵")
      .replace(/\s+/g, " ")
      .trim();
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
    return `<details class="net-audit-sources"><summary>原始正式文档与史料（审计）</summary><p class="subline">这些链接指向整份正式文件，供核对使用；上面的“当前人物结算逻辑”才是面向读者的单人解释。</p><p class="sources">${links}</p></details>`;
  }

  function metricDetail(item, record) {
    const intro = netPublicIntro[item.label] || "";
    const summary = cleanNetText(item.reader_summary || "");
    const fullBasis = cleanNetText(item.reader_full_basis || "");
    const highlights = (Array.isArray(item.reader_highlights) ? item.reader_highlights : [])
      .map(cleanNetText).filter(Boolean);
    const boundary = cleanNetText(item.reader_boundary || "");
    const how = cleanNetText(item.reader_how || "");
    const logic = [intro, summary].filter(Boolean).join("\n");
    const full = fullBasis && fullBasis !== summary
      ? `<details><summary>当前人物的完整裁决原文</summary>${prose(fullBasis)}</details>`
      : "";
    const facts = highlights.length
      ? `<div class="label">关键事实</div><ul>${highlights.map(text => `<li>${esc(text)}</li>`).join("")}</ul>`
      : "";
    const limit = boundary ? `<div class="label">限制与边界</div>${prose(boundary)}` : "";
    const formula = how ? `<details><summary>这个分怎么算？</summary>${prose(how)}</details>` : "";
    return `<details class="net-metric-detail"><summary><span><strong>${esc(item.label)}</strong>${intro ? `<small>${esc(intro)}</small>` : ""}</span><b>${esc(netValue(item))}</b></summary><div class="net-metric-body">${logic ? `<div class="label">当前人物结算逻辑</div>${prose(logic)}` : ""}${facts}${limit}${formula}${full}${auditSourceBlock(item, record)}</div></details>`;
  }

  function calculationBlock(items) {
    const calculations = items.filter(item => item.reader_kind === "calculation" && item.value != null);
    if (!calculations.length) return "";
    return `<details class="net-calculations"><summary>计算过程与小计</summary>${calculations.map(item => `<div class="component"><span><strong>${esc(item.label)}</strong><small>${esc(cleanNetText(item.reader_how || "按正式公式换算。"))}</small></span><b>${esc(netValue(item))}</b></div>`).join("")}</details>`;
  }

  function genericNetGroup(record, key, items) {
    const judgments = items.filter(item => item.reader_kind === "judgment" && item.value != null);
    return `<section id="net-group-${esc(key)}" class="panel net-detail-group"><h2>${esc(netGroupNames[key] || key)}</h2>${judgments.map(item => metricDetail(item, record)).join("")}${calculationBlock(items)}</section>`;
  }

  function firstItemRawUrl(ref) {
    const path = String(ref || "").split("#", 1)[0];
    return `../${path}?raw=1`;
  }

  async function loadFirstItemDoc(ref) {
    if (!ref) return "";
    if (firstItemDocCache.has(ref)) return firstItemDocCache.get(ref);
    const pending = fetch(firstItemRawUrl(ref), {cache: "no-cache"})
      .then(response => response.ok ? response.text() : "")
      .catch(() => "");
    firstItemDocCache.set(ref, pending);
    return pending;
  }

  function firstItemBullets(markdown, rulerName) {
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

  function firstItemPublicText(value) {
    return String(value ?? "")
      .replace(/\bR([0-6])\b/g, "起点R$1级")
      .replace(/\bO([1-6])\b/g, "对手O$1级")
      .replace(/\bL([0-5])\b/g, "L$1级")
      .replace(/\bHYBRID\b/g, "战略统筹与本人主帅／临阵并存")
      .replace(/\bSTRATEGIC_COMMAND\b/g, "战略统筹路线")
      .replace(/\bNONE\b/g, "未形成可计的本人统帅责任")
      .replace(/\bC-([0-5])-(LOW|MID|HIGH)\b/g, (_, n, p) => `第${n}档·${({LOW:"低位",MID:"中位",HIGH:"高位"})[p]}`)
      .replace(/\bC-0\b/g, "第0档")
      .replace(/\s+/g, " ")
      .trim();
  }

  function firstMetricDetail(id, title, subtitle, score, body, item, record) {
    return `<details id="${id}" data-ruler="${esc(record.ruler_name)}" class="net-metric-detail"><summary><span><strong>${title}</strong><small>${subtitle}</small></span><b>${esc(netValue(item))}</b></summary><div class="net-metric-body">${body}${auditSourceBlock(item, record)}</div></details>`;
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
    const result = bullets["结算结果"] || bullets["A结算"] || "";
    const scale = bullets["本人取得/归属成果"] || bullets["取得/恢复成果"] || "";
    const project = bullets["项目总成果"] || "";
    const content = bullets["成果内容"] || "";
    const calculation = bullets["计算"] || item.reader_how || "";
    const boundary = bullets["分账边界"] || "";
    const allocation = project ? `<div class="label">共同成果为什么这样分</div><p class="prose">${firstEvidenceMarkup(boundary || "当前正式条目未单列分账理由。", "A统一贡献")}</p>${/暂按/.test(boundary || content) ? '<p class="notice">这里保留的是正式记录的整体信用分配。当前条目未展开逐地区、逐成果节点的份额证明；下方公式说明如何换分，不代表已经证明分配比例。</p>' : ""}` : "";
    const body = `<div class="label">A是什么意思</div>${prose("A只评价建国、复国或统一主链中，本人最终真正留下了多少稳定控制成果。继承来的既有版图不算本人新增；起点强弱、对手、速度、组织和本人军事能力分别放到B1、B2、C。")}<div class="label">U是什么意思</div>${prose("U = 有效控制信用。新增的稳定控制按100%计，恢复旧有稳定控制按50%计；1000代表一个“全国核心统一尺度”。U不是人口、面积或军队人数，而是统一成果规模的标准化信用。公式：U = 新增稳定空间控制 + 50% × 恢复稳定空间控制。")}${scale || content ? `<div class="label">当前人物的U怎么来</div>${prose([project, scale, content, bullets["分账说明"]].filter(Boolean).join("\n"))}` : ""}${allocation}<details><summary>这个分怎么算？</summary>${prose(`单人项目：A = 120 × (min(1000, U) / 1000)^0.65；共同项目先算项目A池，再按本人控制信用占项目总信用的比例分配，不把个人信用再次代入曲线。最后保留1位小数。${calculation ? `\n当前人物正式代入：${calculation}` : ""}${result ? `\n正式结算：${result}` : ""}`)}</details>`;
    return firstMetricDetail("net-first-a", "A · 统一主链客观贡献", "满分120；只看本人最终留下的稳定控制成果", item.value, body, item, record);
  }

  function renderFirstB1(item, bullets, record) {
    const result = bullets["B1结算"] || "";
    const start = bullets["起点"] || "";
    const opponent = bullets["对手"] || "";
    const efficiency = bullets["效率"] || "";
    const body = `<div class="label">B1是什么意思</div>${prose("B1不重复奖励统一规模，而是问：本人从多强的家底起步、面对多强的实际竞争对手、用了多高效率完成核心成果。起点越弱、对手越强、完成越快，B1越高。")}<div class="label">三个变量怎么读</div><ul><li>起点R档：看本人进入主链时能直接调用的军政资源。R0最弱，得15分；R6接近统一的成熟国家机器，得0分。</li><li>对手O档：看实际竞争阶段的战争机器强度。最强对手全值，第二强只按50%计。</li><li>效率：先算期望完成年 = 4 + 8 × √(效率阶段有效控制信用 / 1000)，再用“实际年数 ÷ 期望年数”得到速度比；速度比越小，效率分越高。</li></ul>${start ? `<div class="label">起点怎么判</div>${prose(firstItemPublicText(start))}` : ""}${opponent ? `<div class="label">对手怎么判</div>${prose(firstItemPublicText(opponent))}` : ""}${efficiency ? `<div class="label">效率怎么判</div>${prose(firstItemPublicText(efficiency))}` : ""}<details><summary>这个分怎么算？</summary>${prose(`B1 = 起点难度分 + 对手难度分 + 完成效率分。${result ? `\n当前人物正式结算：${firstItemPublicText(result)}` : ""}`)}</details>`;
    return firstMetricDetail("net-first-b1", "B1 · 创业难度与战略效率", "满分50；起点15 + 对手15 + 完成效率20", item.value, body, item, record);
  }

  function renderFirstB2(item, bullets, record, contract) {
    const result = bullets["B2结算"] || "";
    const explainLevel = (value, section) => {
      const level = String(value || "").match(/L[0-5]/)?.[0];
      const part = contract.split(`### ${section}`)[1]?.split(/\n###? /)[0] || "";
      const row = part.split("\n").find(line => level && line.startsWith(`| ${level} |`));
      const meaning = row?.split("|")[3]?.trim();
      return [firstItemPublicText(value), meaning ? `本档要求：${meaning}。` : ""].filter(Boolean).join(" ");
    };
    const parallel = explainLevel(bullets["并行执行"], "4.1");
    const coverage = explainLevel(bullets["团队能力覆盖与组织杠杆"] || bullets["能力覆盖/组织杠杆"], "4.2");
    const integration = explainLevel(bullets["异质整合"], "4.3");
    const basis = bullets["裁决依据"] || "";
    const body = `<div class="label">B2是什么意思</div>${prose("B2看创业或统一机器能不能脱离本人逐项盯办而运行：能否多线并行、能否把高难任务交给专业责任中心、能否把不同地域和旧集团稳定整合进同一执行体系。")}<div class="label">L档怎么换分</div>${prose("每个维度都用L0—L5六档：L0=0分、L1=2分、L2=4分、L3=6分、L4=8分、L5=10分。三项相加就是B2。")}${parallel ? `<div class="label">并行执行</div>${prose(parallel)}` : ""}${coverage ? `<div class="label">专业覆盖与组织杠杆</div>${prose(coverage)}` : ""}${integration ? `<div class="label">异质整合</div>${prose(integration)}` : ""}${basis ? `<div class="label">本人组织表现与限制</div>${prose(firstItemPublicText(basis))}` : ""}${bullets["材料来源"] ? `<div class="label">史料与归责来源</div><p class="sources">${firstEvidenceMarkup(bullets["材料来源"], "B2组织与整合")}</p>` : ""}<details><summary>这个分怎么算？</summary>${prose(`B2 = 并行执行分 + 专业覆盖／组织杠杆分 + 异质整合分。${result ? `\n当前人物正式结算：${firstItemPublicText(result)}` : ""}`)}</details>`;
    return firstMetricDetail("net-first-b2", "B2 · 创业组织与政治整合", "满分30；三项各10分", item.value, body, item, record);
  }

  function renderFirstC(item, bullets, record) {
    const result = bullets["C结算"] || "";
    const responsibilityRoute = bullets["责任路线"] || "";
    const basis = bullets["结算依据"] || "";
    const body = `<div class="label">C是什么意思</div>${prose("C不是把国家打赢的战争都算给最高统治者。它只看本人是否真正承担战略统筹、实际主帅或临阵指挥责任，以及高难成果、复验和可归责失败。将领独立完成的战果不能自动转成本人的C分。")}${responsibilityRoute ? `<div class="label">本人走哪条责任路线</div>${prose(firstItemPublicText(responsibilityRoute))}` : ""}${basis ? `<div class="label">当前人物为什么是这个档</div>${prose(firstItemPublicText(basis))}` : ""}<details><summary>这个分怎么算？</summary>${prose(`C先按正式证据判统帅档位，再由档位直接映射到0—40分；不是把战役逐场相加。${result ? `\n当前人物正式结算：${firstItemPublicText(result)}` : ""}`)}</details>`;
    return firstMetricDetail("net-first-c", "C · 本人军事统帅与战争解题", "满分40；只计本人可归责的统帅能力", item.value, body, item, record);
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
    return `<div class="net-detail-total"><div class="label">第一项最后怎么进入总榜</div>${prose(`四轴毛分 = A + B1 + B2 + C = ${a} + ${b1} + ${b2} + ${c} = ${gross}。\n第一项净分 S1 = max(0, 四轴毛分 − 军事成本扣分) = max(0, ${gross} − ${cost ?? 0}) = ${net}。\n总榜不是把S1直接再加一次，而是把它折成条件附加分：F = 0.20 × 637 × (S1 / 240)^1.25 = ${addOn}。`)}</div>`;
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

    const labels = ["A统一贡献", "B1创业难度与效率", "B2组织与整合", "C军事统帅与战争解题"];
    const bulletsByLabel = {};
    await Promise.all(labels.map(async label => {
      bulletsByLabel[label] = firstItemBullets(await loadFirstItemDoc(firstItemDocs[label]), record.ruler_name);
    }));
    if (!location.hash.startsWith(`#net/${encodeURIComponent(record.ruler_id)}/first`)) return;

    const contract = await loadFirstItemDoc("docs/分项规则/第一项政权奠基与统一贡献及能力/00-规则与计分合同.md");
    const mainWindow = contract.split("## 7. ")[1]?.split("## 8.")[0]?.split("\n").find(line => line.startsWith("| ") && line.split("|")[1]?.trim() === record.ruler_name)?.split("|")[2]?.trim();
    const byLabel = Object.fromEntries(items.map(item => [item.label, item]));
    const windowText = bulletsByLabel["B1创业难度与效率"]["效率"] || "";
    const ownA = bulletsByLabel["A统一贡献"];
    if (ownA["项目总成果"]) {
      const aDoc = await loadFirstItemDoc(firstItemDocs["A统一贡献"]);
      const people = [...aDoc.matchAll(/^###\s+\d+\.\s+(.+)$/gm)].map(match => match[1].trim());
      const partners = people.map(name => ({name, fields:firstItemBullets(aDoc,name)})).filter(person => person.fields["项目总成果"] === ownA["项目总成果"]);
      ownA["分账说明"] = `分账对象与分数：${partners.map(person => {
        const credit = (person.fields["本人取得/归属成果"] || "").split("；")[0].replace(/[。；]+$/, "");
        const score = (person.fields["结算结果"] || "").replace(/[。；]+$/, "");
        return `${person.name}：${credit}，${score}`;
      }).join("；")}。`;
    }
    if (!container.isConnected) return;
    const cards = [];
    if (byLabel["A统一贡献"]) cards.push(renderFirstA(byLabel["A统一贡献"], bulletsByLabel["A统一贡献"], record));
    if (byLabel["B1创业难度与效率"]) cards.push(renderFirstB1(byLabel["B1创业难度与效率"], bulletsByLabel["B1创业难度与效率"], record));
    if (byLabel["B2组织与整合"]) cards.push(renderFirstB2(byLabel["B2组织与整合"], bulletsByLabel["B2组织与整合"], record, contract));
    if (byLabel["C军事统帅与战争解题"]) cards.push(renderFirstC(byLabel["C军事统帅与战争解题"], bulletsByLabel["C军事统帅与战争解题"], record));
    if (byLabel["军事成本扣分"]?.value != null) cards.push(metricDetail(byLabel["军事成本扣分"], record));

    container.innerHTML = `<section class="panel net-detail-group"><div class="notice"><strong>这页采用哪些时间与责任范围？</strong><p>本项评价建国、复国或统一主链，可以包含即位前的本人责任。B1完成效率的计时点，不自动截断A、B2、C及军事成本范围。</p><dl><dt>创业／统一主链</dt><dd>${esc(mainWindow || ownA["成果内容"] || "按逐人正式条目确定主链，未单列统一起止年份。")}</dd>${windowText ? `<dt>B1完成效率计时</dt><dd>${esc(firstItemPublicText(windowText))}</dd>` : ""}${byLabel["军事成本扣分"]?.reader_boundary ? `<dt>军事成本责任范围</dt><dd>${esc(byLabel["军事成本扣分"].reader_boundary)}</dd>` : ""}</dl><p class="sources"><a href="../docs/分项规则/第一项政权奠基与统一贡献及能力/00-规则与计分合同.md" target="_blank" rel="noopener">主链与分项边界 ↗</a></p></div>${cards.join("")}${firstTotals(items)}</section>`;
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
      ? `<p class="subline">第一项原始净分 S1：${number(record.net.first_item_raw_score)}；此处显示进入总榜的附加分。</p>`
      : major === "first" ? `<p class="subline">该人物第一项不适用。</p>` : "";
    return `<a class="panel net-major-card" href="${netHref(record, major)}"><h2>${esc(spec.title)}</h2><div class="big">${value == null ? "—" : number(value)}</div>${extra}<p>${esc(spec.description)}</p><p class="sources">查看完整计分逻辑 →</p></a>`;
  }

  function renderNetShell(record, active, body) {
    nav("");
    screen.innerHTML = `<a class="back" href="#person/${encodeURIComponent(record.ruler_id)}">← 返回${esc(record.ruler_name)}人物页</a><div class="person-head net-detail-head"><div><div class="eyebrow">${esc(record.polity)} / 净收益计分</div><h1>${esc(record.ruler_name)} · ${esc(netMajorSpecs[active]?.title || "净收益")}</h1><p class="muted">${active === "first" ? "人物在位／掌权时期（不是本项采用窗口）" : "实际权力窗口"}：${esc(record.actual_power_window)} · 总榜净收益 ${number(record.net?.total_score)}</p></div></div>${majorNav(record, active)}<section class="net-detail-page">${body}</section>`;
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
    const scoreNote = major === "first" && record.net?.first_item_status === "APPLICABLE"
      ? `进入总榜的附加分：${number(value)}；第一项扣军事成本后的原始净分 S1：${number(record.net.first_item_raw_score)}。`
      : major === "first" ? "该人物第一项不适用。" : `本项进入总榜的分值：${value == null ? "—" : number(value)}。`;
    renderNetShell(record, major, `<section class="panel">${major === "first" ? "" : `<h2>${esc(spec.title)}</h2>`}<p>${esc(spec.description)}</p><p class="subline">${esc(scoreNote)}</p></section><div id="net-major-body"><div class="empty">正在整理当前人物的逐项结算逻辑…</div></div>`);
    if (major === "first") void renderFirstMajor(record, focus);
    else renderGenericMajor(record, major, focus);
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
        screen.innerHTML = `<div class="empty"><p>${esc(record.ruler_name)}没有可展示的净收益正式结算。</p><a href="#person/${encodeURIComponent(record.ruler_id)}">返回人物页</a></div>`;
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

  // #screen survives route changes, while child views are rebuilt. Enhance both
  // the overview table and the person page whenever their DOM appears.
  new MutationObserver(() => {
    enhanceHomeRows();
    enhancePersonNet();
  }).observe(screen, {childList: true, subtree: true});
  enhanceHomeRows();
  ensureNetStyles();
  enhancePersonNet();

  screen.addEventListener("click", event => {
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

  // Replace the original hash router with a thin extension that owns #net routes
  // and delegates every existing route unchanged. This keeps lazy person loading,
  // comparison, overview, and guide behavior intact.
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
