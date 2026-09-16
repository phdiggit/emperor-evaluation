"use strict";

(() => {
  const screenEl = document.getElementById("screen");
  if (!screenEl) return;

  const PUBLIC_GRADE = {G0:"E",G1:"D",G2:"C",G3:"B",G4:"A",G5:"S"};
  const STATE_GRADE = {1:"E",2:"D",3:"C",4:"B",5:"A",6:"S"};
  const HANDOFF_GRADE = {0:"E",1:"D",2:"C",3:"B",4:"A",5:"S"};
  const LOSS_TEXT = {
    0:"未见独立有效低谷",
    1:"有局部或短时损害",
    2:"出现明显低谷",
    3:"出现严重低谷",
  };
  const METHOD_MAX = {"A制度建设":100,"B1官僚治理":100,"B2反馈与约束":80};
  const FINANCE_MAX = {"C1民生":80,"C2经济财政":35,"C3社会安全":60};
  const HANDOFF_LABELS = {
    "D1继任行政连续性":"行政承接",
    "D3政权交接稳定":"终局继承",
  };
  const SECOND_GROUPS = ["method", "finance", "handoff"];
  const MAJOR_ROLE_LABELS = {
    FOUNDATIONAL_CREATION:"创设",
    MAJOR_RESTRUCTURE:"重构",
    MAJOR_RECONSTRUCTION:"重建",
    CANONICALIZATION:"定型",
    MAJOR_CIVILIZATIONAL_CORRECTION:"重大纠偏",
    STRUCTURAL_NON_DURABLE:"核心结构",
    DURABILITY_EVIDENCE_PENDING:"核心结构",
  };
  const CLOSURE_LABELS = {
    OBSERVED:"已有实际运行",
    SUSTAINED_OR_SYSTEMIC:"形成持续或系统运行",
    REVERSED:"后续被逆转",
    NOT_CLOSED:"尚未形成完整运行证据",
  };
  const formalACache = new Map();
  let scheduled = false;

  function finite(value) {
    if (value == null || value === "") return null;
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }

  function fmt(value, digits = 1) {
    const n = finite(value);
    return n == null ? "—" : n.toFixed(digits);
  }

  function personRecord() {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#person\/([^/?#]+)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; } catch { return null; }
  }

  function netRecord() {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#net\/([^/?#]+)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; } catch { return null; }
  }

  function compareRecords() {
    if (typeof byId === "undefined" || !location.hash.startsWith("#compare/")) return [];
    return location.hash.slice(9).split("/").filter(Boolean).slice(0, 2).map(id => {
      try { return byId.get(decodeURIComponent(id)) || null; } catch { return null; }
    }).filter(Boolean);
  }

  function itemMap(record, key) {
    return new Map((record?.net?.component_details?.[key] || []).map(item => [item.label, item]));
  }

  function secondItems(record) {
    const result = new Map();
    for (const key of SECOND_GROUPS) {
      for (const item of record?.net?.component_details?.[key] || []) result.set(item.label, item);
    }
    return result;
  }

  function secondTotals(record) {
    const method = itemMap(record, "method");
    const finance = itemMap(record, "finance");
    const handoff = itemMap(record, "handoff");
    return {
      method: finite(method.get("治理手段")?.value),
      finance: finite(finance.get("治理结果")?.value),
      handoff: finite(handoff.get("交接得分")?.value),
      total: finite(record?.net?.second_item_score ?? handoff.get("第二项合计")?.value),
    };
  }

  function currentSecondPool() {
    if (typeof byId === "undefined") return [];
    return Array.from(byId.values()).filter(record =>
      !record?.supplementary && finite(record?.net?.second_item_score) != null
    );
  }

  function secondRankText(record) {
    const score = finite(record?.net?.second_item_score);
    if (score == null) return "";
    const pool = currentSecondPool();
    if (!pool.length) return "";
    const rank = 1 + pool.filter(item => finite(item?.net?.second_item_score) > score).length;
    const pct = Math.max(1, Math.min(100, Math.ceil(rank / pool.length * 100)));
    return `当前已结算人物：第 ${rank} / ${pool.length}（约前 ${pct}%）`;
  }

  function positionSuffix(text) {
    const lower = String(text || "").toLowerCase();
    if (/lower|low/.test(lower)) return "-";
    if (/upper|high/.test(lower)) return "+";
    return "";
  }

  function publicMethodGrade(item) {
    const text = String(item?.grade || "");
    const band = text.match(/\bG([0-5])\b/i);
    if (!band) return "";
    return `${PUBLIC_GRADE[`G${band[1]}`] || ""}${positionSuffix(text)}`;
  }

  function stateGradeMeta(item) {
    const match = String(item?.grade || "").match(/\bC[123]-(\d)\s*\/\s*L([0-3])\b/i);
    if (!match) return null;
    const band = Number(match[1]);
    const loss = Number(match[2]);
    return {grade:STATE_GRADE[band] || "",lossText:LOSS_TEXT[loss] || ""};
  }

  function publicHandoffGrade(item) {
    const level = Number(item?.value);
    return Number.isInteger(level) ? HANDOFF_GRADE[level] || "" : "";
  }

  function boundaryExcerpt(item) {
    const text = String(item?.reader_boundary || "").trim();
    if (!text) return "";
    const first = text.match(/^.*?[。！？；;]/)?.[0] || text;
    return `边界：${first.trim()}`;
  }

  function ensureStyles() {
    if (document.getElementById("second-item-public-polish-style")) return;
    const style = document.createElement("style");
    style.id = "second-item-public-polish-style";
    style.textContent = `
      .second-item-public-grade-ready > .second-item-scale-note{display:none!important}
      .second-item-public-grade-ready::after{content:attr(data-public-grade-note);display:block;margin-top:4px;font-size:11px;line-height:1.55;color:var(--green);font-weight:600}
      .second-item-public-value{font-size:0!important}
      .net-metric-detail>summary b.second-item-public-value::after{content:attr(data-public-value);font:20px Georgia,serif;color:var(--green)}
      .component>b.second-item-public-value::after{content:attr(data-public-value);font-size:13px;color:var(--green)}
      .second-item-public-copy{font-size:0!important}
      .second-item-public-copy::after{content:attr(data-public-copy);display:block;font-size:13px;line-height:1.7;color:inherit}
      small.second-item-public-copy::after{font-size:11px;color:var(--muted);line-height:1.55}
      .second-item-public-score{font-size:0!important}
      .second-item-public-score::after{content:attr(data-public-score);font:inherit;color:inherit}
      .net-major-card .big.second-item-public-score::after{font:30px Georgia,serif;color:var(--green)}
      .second-item-total-grid b.second-item-public-score::after{font:21px Georgia,serif;color:var(--green)}
      #person-outcome b.second-item-public-score::after,.comparison b.second-item-public-score::after{font:inherit;color:inherit}
      .second-item-public-reading{margin:2px 0 4px}
      .second-item-public-reading .label{margin-top:8px}
      .second-item-public-reading ul{margin:8px 0 12px;padding-left:20px}
      .second-item-public-reading li{margin:5px 0;line-height:1.8}
      .second-item-public-reading .prose{margin:8px 0 12px}
      .second-item-pool-note{display:none!important}
      .second-item-page-note{margin-top:18px;padding-top:12px}
      .second-item-page-note>summary{font-size:13px;color:var(--muted)}
      .second-item-institution-reading{margin:4px 0 8px}
      .second-item-institution-intro{margin:4px 0 14px;line-height:1.75}
      .second-item-institution-group{margin:14px 0 18px;padding-top:2px}
      .second-item-institution-group>h4{margin:0 0 8px;font-size:15px}
      .second-item-institution-list{list-style:none;margin:0;padding:0;display:grid;gap:8px}
      .second-item-institution-list>li{margin:0;padding:10px 12px;border:1px solid var(--line);border-radius:5px;background:#fff}
      .second-item-institution-head{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-bottom:4px}
      .second-item-institution-head strong{font-size:14px}
      .second-item-institution-badge{display:inline-block;padding:1px 6px;border:1px solid var(--line);border-radius:999px;font-size:10px;line-height:1.6;color:var(--green);font-weight:700;background:#f4f5ef}
      .second-item-institution-direction{font-size:10px;color:var(--muted);font-weight:700}
      .second-item-institution-meta{margin:2px 0;font-size:11px;color:var(--muted);line-height:1.6}
      .second-item-institution-note{margin:4px 0 0;font-size:12px;line-height:1.72}
      .second-item-institution-reception{display:block;margin-top:5px;font-size:11px;line-height:1.65;color:var(--green)}
      .second-item-institution-empty{margin:4px 0;color:var(--muted);font-size:12px}
    `;
    document.head.append(style);
  }

  function overlayCopy(node, text) {
    if (!node || !text) return;
    node.classList.add("second-item-public-copy");
    if (node.dataset.publicCopy !== text) node.dataset.publicCopy = text;
  }

  function overlayScore(node, text) {
    if (!node || !text) return;
    node.classList.add("second-item-public-score");
    if (node.dataset.publicScore !== text) node.dataset.publicScore = text;
  }

  function setPublicGrade(span, valueNode, grade, noteParts) {
    if (!span || !grade) return;
    const note = noteParts.filter(Boolean).join("｜");
    span.classList.add("second-item-public-grade-ready");
    if (span.dataset.publicGradeNote !== note) span.dataset.publicGradeNote = note;
    if (valueNode) {
      valueNode.classList.add("second-item-public-value");
      if (valueNode.dataset.publicValue !== grade) valueNode.dataset.publicValue = grade;
    }
  }

  function patchMethodGrades(root, record) {
    if (!root || !record?.net) return;
    const items = itemMap(record, "method");
    if (!items.size) return;
    for (const detail of root.querySelectorAll(".net-metric-detail[data-second-source-label]")) {
      const sourceLabel = detail.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const grade = publicMethodGrade(item);
      if (!item || !grade || !METHOD_MAX[sourceLabel]) continue;
      const summary = detail.querySelector(":scope > summary");
      setPublicGrade(summary?.querySelector(":scope > span"), summary?.querySelector(":scope > b"), grade,
        [`原始方向指数 ${Number(item.value).toFixed(1)} / ${METHOD_MAX[sourceLabel]}`, boundaryExcerpt(item)]);
    }
    for (const span of root.querySelectorAll(".component > span[data-second-source-label]")) {
      const sourceLabel = span.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const grade = publicMethodGrade(item);
      if (!item || !grade || !METHOD_MAX[sourceLabel]) continue;
      setPublicGrade(span, span.parentElement?.querySelector(":scope > b"), grade,
        [`原始方向指数 ${Number(item.value).toFixed(1)} / ${METHOD_MAX[sourceLabel]}`, boundaryExcerpt(item)]);
    }
  }

  function patchFinanceGrades(root, record) {
    if (!root || !record?.net) return;
    const items = itemMap(record, "finance");
    if (!items.size) return;
    for (const detail of root.querySelectorAll(".net-metric-detail[data-second-source-label]")) {
      const sourceLabel = detail.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const meta = stateGradeMeta(item);
      if (!item || !meta?.grade || !FINANCE_MAX[sourceLabel]) continue;
      const summary = detail.querySelector(":scope > summary");
      setPublicGrade(summary?.querySelector(":scope > span"), summary?.querySelector(":scope > b"), meta.grade,
        [`结算分 ${Number(item.value).toFixed(1)}`, meta.lossText, boundaryExcerpt(item)]);
    }
    for (const span of root.querySelectorAll(".component > span[data-second-source-label]")) {
      const sourceLabel = span.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const meta = stateGradeMeta(item);
      if (!item || !meta?.grade || !FINANCE_MAX[sourceLabel]) continue;
      setPublicGrade(span, span.parentElement?.querySelector(":scope > b"), meta.grade,
        [`结算分 ${Number(item.value).toFixed(1)}`, meta.lossText, boundaryExcerpt(item)]);
    }
  }

  function patchHandoffGrades(root, record) {
    if (!root || !record?.net) return;
    const items = itemMap(record, "handoff");
    if (!items.size) return;
    for (const detail of root.querySelectorAll(".net-metric-detail[data-second-source-label]")) {
      const sourceLabel = detail.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const grade = publicHandoffGrade(item);
      if (!item || !grade || !HANDOFF_LABELS[sourceLabel]) continue;
      const summary = detail.querySelector(":scope > summary");
      setPublicGrade(summary?.querySelector(":scope > span"), summary?.querySelector(":scope > b"), grade,
        [HANDOFF_LABELS[sourceLabel], boundaryExcerpt(item)]);
    }
    for (const span of root.querySelectorAll(".component > span[data-second-source-label]")) {
      const sourceLabel = span.dataset.secondSourceLabel || "";
      const item = items.get(sourceLabel);
      const grade = publicHandoffGrade(item);
      if (!item || !grade || !HANDOFF_LABELS[sourceLabel]) continue;
      setPublicGrade(span, span.parentElement?.querySelector(":scope > b"), grade,
        [HANDOFF_LABELS[sourceLabel], boundaryExcerpt(item)]);
    }
  }

  function patchGradeGroups(root, record) {
    patchMethodGrades(root, record);
    patchFinanceGrades(root, record);
    patchHandoffGrades(root, record);
  }

  function translateReceptionCodes(value) {
    return String(value || "")
      .replace(/(?:现有材料|现材料|现有证据)?\s*未(?:独立)?闭合\s*R4/gi, "现有证据尚未证明跨朝代长期接收")
      .replace(/(?:现有材料|现材料|现有证据)?\s*未(?:独立)?闭合\s*R3/gi, "现有证据尚未证明被多个后继统治阶段持续采用")
      .replace(/闭合\s*R4/gi, "已证明跨朝代长期接收")
      .replace(/闭合\s*R3/gi, "已证明被多个后继统治阶段持续采用")
      .replace(/R3\s*\/\s*R4/gi, "长期接收")
      .replace(/R3\s*门(?:槛)?/gi, "长期接收门槛")
      .replace(/\bR4\b/gi, "跨朝代长期接收")
      .replace(/\bR3\b/gi, "被多个后继统治阶段持续采用")
      .replace(/\bR[12]\b/gi, "后世接收范围有限")
      .replace(/\bR0\b/gi, "本人任内运行证据");
  }

  function publicTechnicalText(value) {
    return translateReceptionCodes(String(value || ""))
      .replace(/\bG([0-5])\s*[-/]\s*([A-Za-z-]+)\b/gi, (_, band, position) => `${PUBLIC_GRADE[`G${band}`] || ""}${positionSuffix(position)}`)
      .replace(/\bG([0-5])\b/g, (_, band) => PUBLIC_GRADE[`G${band}`] || band)
      .replace(/\bC[123]-([1-6])\s*\/\s*L([0-3])\b/g, (_, band, loss) => `${STATE_GRADE[Number(band)] || band}档；${LOSS_TEXT[Number(loss)] || ""}`)
      .replace(/\bC[123]-([1-6])\b/g, (_, band) => `${STATE_GRADE[Number(band)] || band}档`)
      .replace(/\bD3-([0-5])\b/g, (_, level) => `${HANDOFF_GRADE[Number(level)] || level}档`)
      .replace(/\bH([0-5])\b/g, (_, level) => `${HANDOFF_GRADE[Number(level)] || level}档`)
      .replace(/\bL([0-3])\b/g, (_, level) => LOSS_TEXT[Number(level)] || "")
      .trim();
  }

  function cleanHistoricalText(value) {
    let text = publicTechnicalText(String(value || "").replace(/`/g, "").trim());
    if (!text) return "";
    text = text
      .replace(/\b(?:B1-)?distributed\/personnel\s*M[0-3]\b/gi, "")
      .replace(/\b(?:MAJOR_RESTRUCTURE|MAJOR_RECONSTRUCTION|FOUNDATIONAL_CREATION|CANONICALIZATION|MAJOR_CIVILIZATIONAL_CORRECTION|STRUCTURAL_NON_DURABLE|DURABILITY_EVIDENCE_PENDING|mixed_positive|mixed_negative|external_constraint|canonical|support|core|central|distributed)\b/gi, "")
      .replace(/(?:正向|负向|混合偏正|混合偏负)?\s*M[0-3]\b/gi, "")
      .replace(/\bS(?:\+\+|[+−-])?(?=[^\w]|$)/g, "")
      .replace(/\bS_(?:end|main|avg|0)\b/gi, "")
      .replace(/\bP面\b/g, "生产方面")
      .replace(/\bM侧\b/g, "市场与货币方面")
      .replace(/\bF\/R面\b/g, "财政与储备方面")
      .replace(/^正向保留\s*\d+(?:\.\d+)?分[；，。]?\s*/, "")
      .replace(/(?:正向|负向)\s*\d+(?:\.\d+)?[；，。]?/g, "")
      .replace(/(?:制度净值|净值|合计)\s*\d+(?:\.\d+)?[；，。]?/g, "")
      .replace(/主阶段负态主导定\s*[。；]?/g, "主要阶段负面表现占主导。")
      .replace(/角色改为\s*[。；]?/g, "")
      .replace(/保留正向\s*[、，。；]?/g, "")
      .replace(/保留负向\s*[、，。；]?/g, "")
      .replace(/结算\s*[，,]?\s*/g, "")
      .replace(/不能从政治清洗或同一问责损害另造[^。；]*[。；]?/g, "")
      .replace(/不因正负规模或建设名望抬档[。；]?/g, "")
      .replace(/未过[^。；]*档门[。；]?/g, "")
      .replace(/阻断[^。；]*档[。；]?/g, "")
      .replace(/闭合/g, "确认")
      .replace(/去重/g, "避免重复计算")
      .replace(/[；，、]\s*[；，、]+/g, "；")
      .replace(/。\s*。+/g, "。")
      .replace(/；\s*。/g, "。")
      .replace(/，\s*。/g, "。")
      .replace(/\s+/g, " ")
      .trim();
    return text
      .split(/(?<=[。！？])/)
      .map(part => part.trim())
      .filter(part => part.length >= 6 && !/^(保留|角色|正式方向|旧结算|改档)/.test(part))
      .join("")
      .replace(/^[；，、：\s]+|[；，、：\s]+$/g, "")
      .trim();
  }

  function publicFacts(item) {
    const highlights = (Array.isArray(item?.reader_highlights) ? item.reader_highlights : [])
      .map(cleanHistoricalText).filter(Boolean).slice(0, 3);
    if (highlights.length) return highlights;
    const summary = cleanHistoricalText(item?.reader_summary || "");
    return summary ? [summary] : [];
  }

  function makeTextBlock(tagName, className, text) {
    const node = document.createElement(tagName);
    if (className) node.className = className;
    node.textContent = text;
    return node;
  }

  function makeDetails(title, text, className = "") {
    if (!text) return null;
    const details = document.createElement("details");
    if (className) details.className = className;
    const summary = document.createElement("summary");
    summary.textContent = title;
    details.append(summary, makeTextBlock("p", "prose", text));
    return details;
  }

  function sourcePath(ref) {
    return decodeURIComponent(String(ref || "").split("#", 1)[0]).replace(/:\d+(?:-\d+)?$/, "");
  }

  function dirname(path) {
    const at = path.lastIndexOf("/");
    return at < 0 ? "" : path.slice(0, at);
  }

  async function fetchRepoJson(path) {
    const response = await fetch(`../${path}?raw=1`, {cache:"no-cache"});
    if (!response.ok) throw new Error(`Failed to load ${path}: HTTP ${response.status}`);
    return response.json();
  }

  function formalRows(payload) {
    if (Array.isArray(payload?.records)) return payload.records;
    if (Array.isArray(payload?.collections?.records?.records)) return payload.collections.records.records;
    return [];
  }

  async function loadFormalARecord(record, item) {
    const path = sourcePath(item?.source);
    if (!path) return null;
    const key = `${record.ruler_id}\u0000${path}`;
    if (formalACache.has(key)) return formalACache.get(key);
    const pending = (async () => {
      const payload = await fetchRepoJson(path);
      let rows = formalRows(payload);
      if (!rows.length && Array.isArray(payload?.routes)) {
        const route = payload.routes.find(entry => entry?.polity === record.polity);
        if (!route?.path) return null;
        const shardPath = `${dirname(path)}/${route.path}`;
        rows = formalRows(await fetchRepoJson(shardPath));
      }
      return rows.find(row => row?.ruler_id === record.ruler_id) || null;
    })().catch(error => {
      console.error("Failed to load formal A institution record", error);
      return null;
    });
    formalACache.set(key, pending);
    return pending;
  }

  function directionGroup(direction) {
    if (direction === "positive") return "positive";
    if (direction === "negative") return "negative";
    return "mixed";
  }

  function directionLabel(direction) {
    return ({
      positive:"正向",
      negative:"负向",
      mixed_positive:"正向主导",
      mixed_negative:"负向主导",
      mixed:"正负并存",
      neutral:"正负并存",
    })[direction] || "正负并存";
  }

  function majorRoleLabel(role) {
    return MAJOR_ROLE_LABELS[role] || "";
  }

  function institutionKey(item) {
    return item?.institution_node_id || `${item?.label_zh || item?.mechanism || ""}\u0000${item?.direction || item?.normative_direction || ""}`;
  }

  function collectInstitutions(formal) {
    const groups = {positive:[], negative:[], mixed:[]};
    if (!formal) return groups;
    const important = new Map();
    for (const node of formal.important_institutions || []) {
      if (node && typeof node === "object") important.set(institutionKey(node), node);
    }
    const seen = new Set();
    const append = (profile, fallbackDirection) => {
      if (!profile || typeof profile !== "object") return;
      const key = institutionKey(profile);
      if (seen.has(key)) return;
      seen.add(key);
      const importantNode = important.get(key) || null;
      const node = {...(importantNode || {}), ...profile};
      node._important = Boolean(importantNode || node.decision === "MAJOR_NODE");
      node._direction = node.direction || node.normative_direction || fallbackDirection || "mixed";
      groups[directionGroup(node._direction)].push(node);
    };
    for (const node of formal.M_positive_profile || []) append(node, "positive");
    for (const node of formal.M_negative_profile || []) append(node, "negative");
    for (const node of formal.M_mixed_profile || []) append(node, node?.direction || "mixed");
    for (const node of important.values()) {
      const key = institutionKey(node);
      if (!seen.has(key)) append(node, node.normative_direction || "mixed");
    }
    return groups;
  }

  function receptionText(node) {
    if (!node?._important) return "";
    const effect = String(node.S_effect || "").toUpperCase();
    const gate = String(node.durability_gate || "").toUpperCase();
    if (effect === "S++") return "后世接收：核心规则跨朝代、经历制度断裂后仍被长期接收。";
    if (gate.includes("PASS") || effect === "S+" || effect.startsWith("S-")) {
      return "后世接收：核心规则在多个后继统治阶段仍被实际采用或持续运行。";
    }
    if (gate.includes("PENDING") || gate.includes("FAIL_R")) {
      return "后世接收：现有证据尚不足以证明长期持续沿用。";
    }
    return "";
  }

  function institutionNote(node) {
    const reason = cleanHistoricalText(node?.reason || "");
    if (reason) return reason;
    const closure = CLOSURE_LABELS[String(node?.result_closure || "").toUpperCase()] || "";
    const mechanism = cleanHistoricalText(node?.mechanism || "");
    const label = cleanHistoricalText(node?.label_zh || "");
    if (mechanism && mechanism !== label) return `${mechanism}${closure ? `；${closure}` : ""}`;
    return closure;
  }

  function institutionListItem(node) {
    const li = document.createElement("li");
    const head = document.createElement("div");
    head.className = "second-item-institution-head";
    if (node._important) {
      const role = majorRoleLabel(node.major_node_role);
      const badge = makeTextBlock("span", "second-item-institution-badge", role ? `重大制度 · ${role}` : "重大制度");
      head.append(badge);
    }
    head.append(makeTextBlock("strong", "", cleanHistoricalText(node.label_zh || node.mechanism || "未命名制度节点") || "未命名制度节点"));
    head.append(makeTextBlock("span", "second-item-institution-direction", directionLabel(node._direction)));
    li.append(head);
    const metaParts = [];
    if (node.institution_domain) metaParts.push(node.institution_domain);
    const closure = CLOSURE_LABELS[String(node.result_closure || "").toUpperCase()] || "";
    if (closure) metaParts.push(closure);
    if (metaParts.length) li.append(makeTextBlock("div", "second-item-institution-meta", metaParts.join(" · ")));
    const note = institutionNote(node);
    if (note) li.append(makeTextBlock("p", "second-item-institution-note", note));
    const reception = receptionText(node);
    if (reception) li.append(makeTextBlock("small", "second-item-institution-reception", reception));
    return li;
  }

  function institutionGroup(title, nodes) {
    const section = document.createElement("section");
    section.className = "second-item-institution-group";
    section.append(makeTextBlock("h4", "", `${title} · ${nodes.length}项`));
    if (!nodes.length) {
      section.append(makeTextBlock("p", "second-item-institution-empty", "当前正式结算没有独立制度节点。"));
      return section;
    }
    const list = document.createElement("ul");
    list.className = "second-item-institution-list";
    for (const node of nodes) list.append(institutionListItem(node));
    section.append(list);
    return section;
  }

  async function patchInstitutionDetail(record) {
    if (!record?.net || !location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) return;
    const item = itemMap(record, "method").get("A制度建设");
    const detail = Array.from(document.querySelectorAll(".net-metric-detail[data-second-source-label]"))
      .find(node => node.dataset.secondSourceLabel === "A制度建设");
    const body = detail?.querySelector(":scope > .net-metric-body");
    if (!item || !body) return;
    const formal = await loadFormalARecord(record, item);
    if (!formal || !body.isConnected || !location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) return;
    const key = `${record.ruler_id}|${formal.direction_index}|${(formal.M_positive_profile || []).length}|${(formal.M_negative_profile || []).length}|${(formal.M_mixed_profile || []).length}|${(formal.important_institutions || []).length}`;
    if (body.dataset.secondInstitutionKey === key) return;

    const audit = body.querySelector(":scope > .net-audit-sources");
    if (audit) audit.remove();
    let rawFormal = body.querySelector(":scope > .net-formal-basis-raw");
    if (rawFormal) rawFormal.remove();
    if (!rawFormal && item.reader_full_basis && item.reader_full_basis !== item.reader_summary) {
      rawFormal = makeDetails("正式裁决原文（未改写）", item.reader_full_basis, "net-formal-basis-raw");
    }

    body.innerHTML = "";
    const reading = document.createElement("div");
    reading.className = "second-item-institution-reading";
    reading.append(makeTextBlock("div", "label", "制度建设清单"));
    reading.append(makeTextBlock("p", "second-item-institution-intro", "按正向、负向和正负并存分类列出制度建设；重大制度另标类型和后世接收。"));
    const groups = collectInstitutions(formal);
    reading.append(institutionGroup("正向制度建设", groups.positive));
    reading.append(institutionGroup("负向制度设计与制度性损害", groups.negative));
    reading.append(institutionGroup("正负并存的制度", groups.mixed));
    body.append(reading);

    const summary = cleanHistoricalText(item.reader_summary || "");
    if (summary) body.append(makeDetails("为什么最终是这个等级？", summary));
    const how = publicTechnicalText(item.reader_how || "");
    if (how) body.append(makeDetails("这个分数怎么算？", how));
    if (rawFormal) body.append(rawFormal);
    if (audit) body.append(audit);
    body.dataset.secondInstitutionKey = key;
  }

  function patchMetricBodies(record) {
    if (!record?.net || !location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) return;
    const items = secondItems(record);
    const root = document.getElementById("net-major-body");
    if (!root) return;
    for (const detail of root.querySelectorAll(".net-metric-detail[data-second-source-label]")) {
      const label = detail.dataset.secondSourceLabel || "";
      if (label === "A制度建设") continue;
      const item = items.get(label);
      if (!item || item.reader_kind !== "judgment") continue;
      const body = detail.querySelector(":scope > .net-metric-body");
      if (!body) continue;
      const key = [item.reader_summary || "", ...(item.reader_highlights || []), item.reader_boundary || "", item.reader_how || "", item.reader_full_basis || ""].join("|");
      if (body.dataset.secondPublicBodyKey === key && body.querySelector(":scope > .second-item-public-reading")) continue;
      const audit = body.querySelector(":scope > .net-audit-sources");
      if (audit) audit.remove();
      let formal = body.querySelector(":scope > .net-formal-basis-raw");
      if (formal) formal.remove();
      const raw = String(item.reader_full_basis || "").trim();
      if (!formal && raw && raw !== String(item.reader_summary || "").trim()) {
        formal = makeDetails("正式裁决原文（未改写）", raw, "net-formal-basis-raw");
      }
      body.innerHTML = "";
      const reading = document.createElement("div");
      reading.className = "second-item-public-reading";
      reading.append(makeTextBlock("div", "label", "为什么这样判断"));
      const facts = publicFacts(item);
      if (facts.length > 1) {
        const list = document.createElement("ul");
        for (const fact of facts) list.append(makeTextBlock("li", "", fact));
        reading.append(list);
      } else if (facts.length === 1) {
        reading.append(makeTextBlock("p", "prose", facts[0]));
      } else {
        reading.append(makeTextBlock("p", "prose", "当前公开层没有可进一步压缩的独立事实摘要，可展开正式裁决原文核对。"));
      }
      body.append(reading);
      const boundaryDetails = makeDetails("范围与边界", cleanHistoricalText(item.reader_boundary || ""));
      if (boundaryDetails) body.append(boundaryDetails);
      const howDetails = makeDetails("这个分数怎么算？", publicTechnicalText(item.reader_how || ""));
      if (howDetails) body.append(howDetails);
      if (formal) body.append(formal);
      if (audit) body.append(audit);
      body.dataset.secondPublicBodyKey = key;
    }
  }

  function patchGroupIntros(record) {
    if (!record?.net || !location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) return;
    const values = secondTotals(record);
    overlayCopy(document.querySelector('[data-second-intro="method"]'),
      `这一组看国家机器如何建立规则、配置官僚并形成反馈约束。当前合计 ${fmt(values.method)} 分；公开层先看等级和历史依据，具体指数与折算放在展开内容里。`);
    overlayCopy(document.querySelector('[data-second-intro="finance"]'),
      `这一组看统治时期普通家庭、经济财政和社会安全的主要状态，再结合任内低谷、恢复与额外代价形成结果判断。当前合计 ${fmt(values.finance)} 分。`);
    overlayCopy(document.querySelector('[data-second-intro="handoff"]'),
      "统治如何收尾，会直接影响国家机器和继承秩序能否平稳延续。行政连续性看旧国家机器有多少被接住，交接稳定看继承过程是否顺利；两项均以 S—E 六档显示。");
  }

  function patchScorePresentation(record) {
    if (!record?.net) return;
    const totals = secondTotals(record);
    const rank = secondRankText(record);
    if (location.hash.match(/^#net\/[^/?#]+\/(?:all)?$/)) {
      const card = Array.from(document.querySelectorAll(".net-major-card")).find(node => /\/second(?:\/|$)/.test(node.getAttribute("href") || ""));
      if (card) {
        if (totals.total != null) overlayScore(card.querySelector(".big"), `${fmt(totals.total)} 分`);
        if ([totals.method, totals.finance, totals.handoff].every(value => value != null)) {
          overlayCopy(card.querySelector(":scope > .second-item-card-breakdown"),
            `${rank ? `${rank} · ` : ""}制度与行政 ${fmt(totals.method)} · 民生与社会 ${fmt(totals.finance)} · 政权交接 ${fmt(totals.handoff)}`);
        }
      }
    }
    if (location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) {
      const summary = document.querySelector(".second-item-reader-summary");
      const cards = summary?.querySelectorAll(".second-item-total-grid > div");
      if (cards?.length >= 3) {
        const values = [totals.method, totals.finance, totals.handoff];
        cards.forEach((card, index) => { if (values[index] != null) overlayScore(card.querySelector("b"), `${fmt(values[index])} 分`); });
        overlayCopy(cards[1]?.querySelector("small"), "民生、经济财政、社会安全、恢复与额外代价");
      }
      const intro = document.querySelector(".net-detail-page > .panel");
      const scoreLine = intro?.querySelector(":scope > p.subline");
      if (totals.total != null) overlayCopy(scoreLine, `治国成效：${fmt(totals.total)} 分${rank ? `；${rank}` : ""}。先看结论，再展开到各项依据。`);
    }
    if (location.hash.startsWith("#person/")) {
      const panel = document.getElementById("person-outcome");
      for (const row of panel?.querySelectorAll(":scope > .component") || []) {
        const span = row.querySelector("span");
        if (!span || !span.textContent.trim().startsWith("治国成效")) continue;
        if (totals.total != null) overlayScore(row.querySelector("b"), `${fmt(totals.total)} 分`);
      }
    }
  }

  function patchCompareScores(records) {
    if (records.length < 2 || !location.hash.startsWith("#compare/")) return;
    const row = Array.from(screenEl.querySelectorAll(".comparison tbody tr")).find(item => item.cells?.[0]?.textContent.trim() === "治国成效");
    if (!row) return;
    records.forEach((record, index) => {
      const score = finite(record?.net?.second_item_score);
      const cell = row.cells?.[index + 1];
      if (!cell || score == null) return;
      overlayScore(cell.querySelector("b"), `${fmt(score)} 分`);
    });
  }

  function replaceText(node, replacements) {
    if (!node) return;
    let next = node.textContent;
    for (const [from, to] of replacements) next = next.replaceAll(from, to);
    if (next !== node.textContent) node.textContent = next;
  }

  function patchPersonOutcomeLink() {
    const record = personRecord();
    const panel = document.getElementById("person-outcome");
    if (!record || !panel) return;
    const row = Array.from(panel.querySelectorAll(":scope > .component")).find(component => {
      const label = component.querySelector("span")?.textContent.trim() || "";
      return label.startsWith("治国成效") || label.startsWith("治国净收益");
    });
    if (!row || row.querySelector(":scope > .net-overview-jump")) return;
    const anchor = document.createElement("a");
    anchor.className = "net-overview-jump";
    anchor.href = `#net/${encodeURIComponent(record.ruler_id)}/second`;
    anchor.setAttribute("aria-label", `查看${record.ruler_name}的治国成效计分逻辑`);
    while (row.firstChild) anchor.append(row.firstChild);
    row.append(anchor);
  }

  function patchShellLanguage() {
    const head = document.querySelector(".net-detail-head");
    replaceText(head?.querySelector(".eyebrow"), [["净收益计分", "统治绩效"]]);
    replaceText(head?.querySelector("h1"), [["净收益计分总览", "统治绩效构成"], ["治国净收益", "治国成效"]]);
    replaceText(head?.querySelector(".muted"), [["总榜净收益", "统治绩效总分"]]);
    const nav = document.querySelector(".net-major-nav");
    if (nav) nav.setAttribute("aria-label", "统治绩效详情");
    const secondNav = Array.from(nav?.querySelectorAll("a") || []).find(a => /\/second(?:\/|$)/.test(a.getAttribute("href") || ""));
    if (secondNav && secondNav.textContent !== "治国成效") secondNav.textContent = "治国成效";
    for (const cardTitle of document.querySelectorAll(".net-major-card h2")) {
      replaceText(cardTitle, [["治国净收益", "治国成效"], ["净收益计分总览", "统治绩效构成"]]);
    }
    const reading = document.querySelector("#person-evidence .net-reading[data-net-compact='done']");
    if (reading) {
      const section = reading.closest("section.panel");
      const heading = section?.querySelector(":scope > h2, :scope > h3");
      if (heading?.textContent.trim() === "净收益构成") heading.textContent = "统治绩效构成";
      for (const link of reading.querySelectorAll("a")) replaceText(link, [["净收益计分页", "统治绩效详情"], ["净收益计分", "统治绩效"]]);
      for (const intro of reading.querySelectorAll("p.reading-intro")) replaceText(intro, [["独立净收益计分页", "独立统治绩效详情页"]]);
    }
    for (const message of screenEl.querySelectorAll(".empty p, .empty[role='status']")) {
      replaceText(message, [
        ["净收益计分详情加载失败", "统治绩效详情加载失败"],
        ["净收益详情地址无效", "统治绩效详情地址无效"],
        ["净收益正式结算", "统治绩效正式结算"],
        ["净收益计分逻辑", "统治绩效详情"],
      ]);
    }
  }

  function patchPoolNote(record) {
    if (!record?.net || !location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) return;
    const root = document.getElementById("net-major-body");
    if (!root) return;
    let details = root.querySelector(":scope > .second-item-page-note");
    if (!details) {
      details = document.createElement("details");
      details.className = "second-item-page-note";
      const summary = document.createElement("summary");
      summary.textContent = "排名与数据口径";
      details.append(summary, document.createElement("p"));
      root.append(details);
    }
    const pool = currentSecondPool().length;
    const text = `当前公开名次只比较已完成治国成效正式结算并进入当前主池的人物，共 ${pool} 人；待正式结算与补充对象不进入本名次。`;
    const p = details.querySelector("p");
    if (p && p.textContent !== text) p.textContent = text;
  }

  function patchPublicGrades() {
    const net = netRecord();
    if (net && location.hash.match(/^#net\/[^/?#]+\/second(?:\/|$)/)) {
      const root = document.getElementById("net-major-body");
      patchGradeGroups(root, net);
      patchMetricBodies(net);
      patchGroupIntros(net);
      patchPoolNote(net);
      void patchInstitutionDetail(net);
    }
    const person = personRecord();
    if (person) patchGradeGroups(screenEl, person);
    const records = compareRecords();
    if (records.length) {
      const rows = Array.from(screenEl.querySelectorAll(".comparison tbody tr"));
      const structureRow = rows.find(row => row.cells?.[0]?.textContent.trim() === "构成与依据");
      if (structureRow) records.forEach((record, index) => patchGradeGroups(structureRow.cells[index + 1], record));
      patchCompareScores(records);
    }
  }

  function patch() {
    ensureStyles();
    patchPersonOutcomeLink();
    patchShellLanguage();
    patchPublicGrades();
    const net = netRecord();
    if (net) patchScorePresentation(net);
    const person = personRecord();
    if (person) patchScorePresentation(person);
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      patch();
    });
  }

  new MutationObserver(schedule).observe(screenEl, {childList:true, subtree:true, characterData:true});
  window.addEventListener("hashchange", schedule);
  schedule();
})();
