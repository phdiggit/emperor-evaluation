"use strict";

(() => {
  const normalized = value => {
    if (Array.isArray(value)) return value.map(normalized).filter(Boolean).join("\n");
    if (value && typeof value === "object") return JSON.stringify(value);
    return String(value ?? "").replace(/\s+/g, " ").trim();
  };

  const fragment = html => {
    const template = document.createElement("template");
    template.innerHTML = html;
    return template.content;
  };

  const directLabels = details => Array.from(details.children).filter(
    node => node.classList && node.classList.contains("label")
  );

  const c5PublicText = value => {
    if (Array.isArray(value)) return value.map(c5PublicText);
    if (typeof value !== "string") return value;
    return value
      .replace(/\bC5\b/g, "本轴")
      .replace(/COUNTEREVIDENCE_FOUND/g, "已找到明确反例")
      .replace(/高档反例审查/g, "反例检查")
      .replace(/父链/g, "证据链");
  };

  const impactPublicText = value => String(value ?? "")
    .replace(/取基础([SABCDE](?:[+−-])?)/g, "，基础影响量级为$1")
    .replace(/([SABCDE](?:[+−-])?)个人因果/g, "个人因果$1")
    .replace(/上调至内部([SABCDE](?:[+−-])?)/g, "使最终判断上调为$1")
    .replace(/内部([SABCDE](?:[+−-])?)/g, "综合判断$1")
    .replace(/公众([SABCDE](?:[+−-])?)/g, "最终等级$1")
    .replace(/不增加第二份深度/g, "不重复计入深度")
    .replace(/抬升基础/g, "提高基础影响量级");

  const historyPublicText = value => readerText(String(value ?? ""))
    .replace(/\bNEGATIVE\b/g, "负向")
    .replace(/\bPOSITIVE\b/g, "正向")
    .replace(/\bMIXED\b/g, "正负混合")
    .replace(/负向\s*\/\s*持续系统性情境/g, "持续系统性负向情境")
    .replace(/正向\s*\/\s*持续系统性情境/g, "持续系统性正向情境")
    .replace(/正负混合\s*\/\s*持续系统性情境/g, "持续系统性正负混合情境")
    .replace(/项目正式战役群/g, "正式战役材料")
    .replace(/项目重审明确把/g, "现有裁决将")
    .replace(/项目(?:M1|M2|M4|M5|C1|C2|C3|C4|C5)明确指出/g, "相关人物画像材料指出")
    .replace(/项目(?:M1|M2|M4|M5|C1|C2|C3|C4|C5)因此把这一链裁为/g, "相关人物画像材料将这一链认定为")
    .replace(/项目(?:M1|M2|M4|M5|C1|C2|C3|C4|C5)/g, "相关人物画像材料");

  const netPublicText = value => readerText(String(value ?? ""))
    .replace(/\bC-([0-9]+)-(LOW|MID|HIGH)\b/g, (_, n, p) => `第${n}档·${({LOW:"低位",MID:"中位",HIGH:"高位"})[p]}`)
    .replace(/\b([ABCD]\d?)-([0-9]+)\b/g, "$1第$2档")
    .replace(/\bML([0-4])\b/g, "军事净毁损第$1级")
    .replace(/\bCIV([0-4])\b/g, "文明影响量级$1")
    .replace(/\bDA([0-9]+)\b/g, "破坏放大第$1级")
    .replace(/\bM4\b/g, "跨阶段重要机制")
    .replace(/\bM3\b/g, "重要机制")
    .replace(/\bM2\b/g, "中等强度机制")
    .replace(/\bM1\b/g, "局部机制")
    .replace(/S\+/g, "高权重正向节点")
    .replace(/S[−-]1?/g, "高权重负向节点")
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
    .replace(/\bHYBRID\b/g, "混合归责")
    .replace(/未闭合独立计分链/g, "没有形成可独立确认的正向表现")
    .replace(/未闭合独立正向链/g, "没有形成可独立确认的正向表现")
    .replace(/不拆分重复扣分/g, "不重复计算")
    .replace(/不重复消费/g, "不重复计算")
    .replace(/\bcore\b/gi, "核心链")
    .replace(/\bsupport\b/gi, "支撑链")
    .replace(/正向\s*\d+(?:\.\d+)?/g, "")
    .replace(/负向\s*\d+(?:\.\d+)?/g, "")
    .replace(/合计\s*\d+(?:\.\d+)?/g, "")
    .replace(/；\s*；/g, "；")
    .replace(/，\s*；/g, "；")
    .replace(/\s+/g, " ")
    .trim();

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

  function conciseNetText(value, maxChars = 220) {
    let text = netPublicText(value)
      .replace(/各为负向重要机制与普通高权重负向节点/g, "构成重要负向机制")
      .replace(/合并为混负重要机制/g, "合并判断为明显负向机制")
      .replace(/合为一个平衡中等强度机制/g, "合并判断为正负相抵的中等机制")
      .replace(/制度净值/g, "正负相抵后的制度结果")
      .replace(/主档/g, "主要等级")
      .replace(/裁为/g, "判断为")
      .replace(/定档/g, "确定等级")
      .replace(/出票/g, "重复计分")
      .replace(/消费/g, "计入")
      .replace(/父任务/g, "上层任务")
      .replace(/父链/g, "证据链")
      .replace(/归责/g, "责任归属")
      .replace(/净账/g, "正负净效果")
      .replace(/独立门槛/g, "独立成立条件");
    if (text.length <= maxChars) return text;
    const parts = text.split(/(?<=[。！？；])/).filter(Boolean);
    let result = "";
    for (const part of parts) {
      if (result && result.length + part.length > maxChars) break;
      result += part;
    }
    return result || `${text.slice(0, maxChars - 1)}…`;
  }

  function evidenceSection(title) {
    return Array.from(document.querySelectorAll("#person-evidence > section.panel")).find(section => {
      const heading = section.querySelector(":scope > h2, :scope > h3");
      return heading?.textContent.trim() === title;
    }) || null;
  }

  function normalizeEvidenceCardHeadings() {
    for (const title of ["净收益构成", "人物画像依据", "历史影响依据"]) {
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
    finance: "第二项 · 财政与民生",
    handoff: "第二项 · 政权交接",
    strategic: "第三项 · 战略收益与国防",
    military: "第三项 · 军事体系与成本",
    civilization: "第四项 · 文明与国家整合",
  };

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
      let labelText = index === 0 ? "正式评分记录 ↗" : `补充来源 ${index} ↗`;
      if (ref === item.applied_source && ref !== item.source) labelText = "采用值记录 ↗";
      return link(ref, labelText, record);
    }).join(" ");
  }

  function netJudgment(item, record) {
    const intro = netPublicIntro[item.label] || "";
    const decision = item.reader_summary ? conciseNetText(item.reader_summary) : "";
    const summaryText = [intro, decision].filter(Boolean).join("\n");
    const summary = summaryText
      ? `<div class="label">为什么这样评</div>${prose(summaryText)}`
      : "";
    const highlightTexts = (Array.isArray(item.reader_highlights) ? item.reader_highlights : [])
      .map(text => conciseNetText(text, 150))
      .filter((text, index, values) => text && text !== decision && values.indexOf(text) === index);
    const highlights = highlightTexts.length
      ? `<div class="label">关键事实</div><ul>${highlightTexts.map(text => `<li>${esc(text)}</li>`).join("")}</ul>`
      : "";
    const boundaryText = item.reader_boundary ? conciseNetText(item.reader_boundary, 180) : "";
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
    return `<article class="context-story net-public-item"><div class="component"><span><strong>${esc(item.label)}</strong></span><b>${esc(netValue(item))}</b></div>${summary}${highlights}${boundary}${how}${sourceBlock}</article>`;
  }

  function netCalculation(item) {
    const how = item.reader_how || `${item.label}为计算项，具体公式见完整计分账本。`;
    if (/\bNone\b/.test(String(how))) return "";
    return `<div class="component"><span><strong>${esc(item.label)}</strong><small>${esc(netPublicText(how))}</small></span><b>${esc(netValue(item))}</b></div>`;
  }

  function buildNetReading(record) {
    const section = evidenceSection("净收益构成");
    const groups = Object.entries(record.net?.component_details || {});
    if (!section || !groups.length || section.dataset.netReadable === "done") return;

    const intro = document.createElement("div");
    intro.className = "net-reading";
    intro.innerHTML = `<p class="reading-intro">先看历史事实与判断，再看分数如何换算。小计、折算和总计属于计算过程，不再伪装成独立“评分依据”。</p>`;

    for (const [key, items] of groups) {
      if (!Array.isArray(items)) continue;
      const group = document.createElement("section");
      group.className = "net-public-group";
      const title = `<h3>${esc(netGroupNames[key] || groupNames[key] || key)}</h3>`;

      const firstNotApplicable = key === "first" && items.every(item =>
        item.value == null || (item.label === "附加F" && Number(item.value) === 0)
      );
      if (firstNotApplicable) {
        group.innerHTML = `${title}<p class="notice">本项只评价建国、复国或统一创业主链；该人物不适用，因此这一项不参与净收益计分。</p>`;
        intro.append(group);
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

  function replaceLead(details, labelText, html) {
    const label = directLabels(details)[0];
    if (!label || !html) return;

    label.textContent = labelText;
    let node = label.nextSibling;
    while (node) {
      const next = node.nextSibling;
      if (
        node.nodeType === Node.ELEMENT_NODE &&
        (node.classList.contains("label") || node.tagName === "DETAILS")
      ) break;
      node.remove();
      node = next;
    }
    label.after(fragment(html));
  }

  function publicEvidencePoints(points) {
    if (!Array.isArray(points) || !points.length) return "";
    return `<details class="public-evidence-points"><summary>查看代表性证据</summary>${points.map(point => {
      const publicTitle = point && point.title ? readerText(c5PublicText(point.title)) : "";
      const title = publicTitle ? `<div class="label">${esc(publicTitle)}</div>` : "";
      const details = point && point.details ? c5PublicText(point.details) : "";
      return `${title}${axisProse(details)}`;
    }).join("")}</details>`;
  }

  function c4Lead(axis) {
    const contexts = Array.isArray(axis.representative_contexts) ? axis.representative_contexts : [];
    if (!contexts.length) return axisProse(axis.grade_basis || axis.typical_pattern);
    return contexts.map(context => {
      const rawTitle = String(context.title || "").trim();
      const title = rawTitle && !/^(?:主要)?父(?:情境|链)/.test(rawTitle)
        ? `<div class="public-context-title">${esc(rawTitle)}</div>`
        : "";
      const body = context.mechanism || context.cycle_basis || context.basis || "";
      return `<div class="context-story public-context">${title}${axisProse(body)}</div>`;
    }).join("");
  }

  function uniqueValue(value, seen) {
    if (Array.isArray(value)) {
      const kept = value.filter(item => {
        const key = normalized(item);
        if (!key || seen.has(key)) return false;
        seen.add(key);
        return true;
      });
      return kept;
    }
    const key = normalized(value);
    if (!key || seen.has(key)) return "";
    seen.add(key);
    return value;
  }

  function rebuildAdjudication(details, axis, leadValues) {
    const box = Array.from(details.children).find(
      node => node.tagName === "DETAILS" && node.classList.contains("adjudication")
    );
    if (!box) return;

    const seen = new Set((leadValues || []).map(normalized).filter(Boolean));
    const fields = [
      ["定档依据", axis.grade_basis],
      ["档内定位", axis.position_basis],
      ["限制与证据边界", axis.limitations],
      ["证据评估", axis.evidence_assessment_basis],
    ];
    const sections = [];
    for (const [label, value] of fields) {
      const unique = uniqueValue(value, seen);
      if (!normalized(unique)) continue;
      sections.push(`<div class="label">${label}</div>${axisProse(unique)}`);
    }

    const closure = axis.no_grade_closure;
    if (closure) {
      for (const [label, value] of [
        ["复查范围", closure.review_scope],
        ["证据缺口", closure.evidence_gap],
        ["重开条件", closure.reopen_condition],
      ]) {
        const unique = uniqueValue(value, seen);
        if (normalized(unique)) sections.push(`<div class="label">${label}</div>${axisProse(unique)}`);
      }
    }

    if (!sections.length) {
      box.remove();
      return;
    }
    box.innerHTML = `<summary>裁决详情</summary>${sections.join("")}`;
  }

  function enhanceAxis(details, axisCode, axis) {
    if (!details || !axis || details.dataset.personReadable === "done") return;

    let leadValues = [axis.typical_pattern];
    if (axisCode === "C2") {
      const lead = axis.grade_basis || axis.typical_pattern;
      replaceLead(details, "最能说明这个判断的表现", axisProse(lead));
      leadValues = [lead];
    } else if (axisCode === "C4") {
      replaceLead(details, "最能说明这个判断的制度设计", c4Lead(axis));
      leadValues = axis.representative_contexts?.length
        ? axis.representative_contexts.map(context => context.mechanism || context.cycle_basis || context.basis)
        : [axis.grade_basis || axis.typical_pattern];
    } else if (axisCode === "C5") {
      const type = axis.person_type
        ? `<p class="prose public-person-type"><strong>${esc(axis.person_type)}</strong></p>`
        : axisProse(axis.typical_pattern);
      replaceLead(
        details,
        "权力运用风格概括",
        `${type}${publicEvidencePoints(axis.public_evidence_points)}`
      );
      leadValues = [axis.person_type || axis.typical_pattern];
    }

    if (typeof axis.counterpattern === "string" && axis.counterpattern.trim()) {
      for (const label of directLabels(details)) {
        if (label.textContent.trim() === "反例与限制") {
          label.textContent = "补充证据与边界";
          break;
        }
      }
    }

    rebuildAdjudication(details, axis, leadValues);
    details.dataset.personReadable = "done";
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
    note.textContent = "C5越接近S，表示越能在压力和个人利益面前约束自身权力；越接近E，表示强制、报复或特权越容易越过合理边界。它描述权力风格，不计入八项能力雷达。";
    row.append(note);
  }

  function rewriteHistoryChains(impact) {
    for (const chain of impact.macro_chains || []) {
      const box = document.getElementById(`chain-${chain.chain_id}`);
      const summary = box?.querySelector(":scope > summary");
      if (!box || !summary || box.dataset.publicNarrative === "done") continue;
      let node = summary.nextSibling;
      while (node) {
        const next = node.nextSibling;
        node.remove();
        node = next;
      }
      summary.after(fragment(prose(historyPublicText(chain.narrative))));
      box.dataset.publicNarrative = "done";
    }
  }

  function enhanceImpact(record) {
    const impact = record.impact || {};
    const joint = impact.foundation?.joint_footprint_basis;

    const panel = document.querySelector("#person-impact");
    if (joint && panel && !panel.querySelector(".impact-summary")) {
      const dimensions = panel.querySelector(".dimensions");
      const summary = document.createElement("div");
      summary.className = "impact-summary";
      summary.innerHTML = `<div class="label">为什么是 ${esc(impact.public_grade)}？</div>${prose(impactPublicText(joint))}`;
      (dimensions || panel).after(summary);
    }

    rewriteHistoryChains(impact);
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

  function foldNetLedger() {
    const section = evidenceSection("净收益构成");
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

  function currentRecord() {
    const match = location.hash.match(/^#person\/([^/?#]+)/);
    if (!match) return null;
    return byId.get(decodeURIComponent(match[1])) || null;
  }

  function enhance() {
    const record = currentRecord();
    if (!record) return;
    for (const code of DATA.axis_order) {
      enhanceAxis(document.getElementById(`reason-${code}`), code, record.axes?.[code]);
    }
    enhanceC5Overview(record);
    enhanceImpact(record);
    normalizeEvidenceCardHeadings();
    buildNetReading(record);
    foldNetLedger();
  }

  new MutationObserver(enhance).observe(screen, {childList: true, subtree: true});
  window.addEventListener("hashchange", enhance);
  enhance();
})();
