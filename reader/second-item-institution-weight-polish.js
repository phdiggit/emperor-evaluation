"use strict";

(() => {
  const screen = document.getElementById("screen");
  if (!screen) return;

  const PUBLIC_GRADE = {G0:"E",G1:"D",G2:"C",G3:"B",G4:"A",G5:"S"};
  const ROLE_LABELS = {
    FOUNDATIONAL_CREATION:"创设",
    MAJOR_RESTRUCTURE:"重构",
    MAJOR_RECONSTRUCTION:"重建",
    CANONICALIZATION:"定型",
    MAJOR_CIVILIZATIONAL_CORRECTION:"重大纠偏",
    MAJOR_NEGATIVE_RESTRUCTURE:"负向重构",
    MAJOR_NEGATIVE_CREATION:"负向创设",
    STRUCTURAL_NON_DURABLE:"核心结构",
    DURABILITY_EVIDENCE_PENDING:"核心结构",
  };
  const cache = new Map();
  let scheduled = false;

  function currentRecord() {
    if (typeof byId === "undefined") return null;
    const match = location.hash.match(/^#net\/([^/?#]+)\/second(?:\/|$)/);
    if (!match) return null;
    try { return byId.get(decodeURIComponent(match[1])) || null; } catch { return null; }
  }

  function methodItem(record) {
    return (record?.net?.component_details?.method || []).find(item => item.label === "A制度建设") || null;
  }

  function sourcePath(ref) {
    return decodeURIComponent(String(ref || "").split("#", 1)[0]).replace(/:\d+(?:-\d+)?$/, "");
  }

  function dirname(path) {
    const at = path.lastIndexOf("/");
    return at < 0 ? "" : path.slice(0, at);
  }

  function rows(payload) {
    if (Array.isArray(payload?.records)) return payload.records;
    if (Array.isArray(payload?.collections?.records?.records)) return payload.collections.records.records;
    return [];
  }

  async function repoJson(path) {
    const response = await fetch(`../${path}?raw=1`, {cache:"no-cache"});
    if (!response.ok) throw new Error(`HTTP ${response.status}: ${path}`);
    return response.json();
  }

  async function formalA(record, item) {
    const path = sourcePath(item?.source);
    if (!path) return null;
    const key = `${record.ruler_id}\u0000${path}`;
    if (cache.has(key)) return cache.get(key);
    const pending = (async () => {
      const payload = await repoJson(path);
      let records = rows(payload);
      if (!records.length && Array.isArray(payload?.routes)) {
        const route = payload.routes.find(entry => entry?.polity === record.polity);
        if (!route?.path) return null;
        records = rows(await repoJson(`${dirname(path)}/${route.path}`));
      }
      return records.find(row => row?.ruler_id === record.ruler_id) || null;
    })().catch(error => {
      console.error("Failed to load institution weights", error);
      return null;
    });
    cache.set(key, pending);
    return pending;
  }

  function nodeKey(node) {
    return node?.institution_node_id || `${node?.label_zh || node?.mechanism || ""}\u0000${node?.direction || node?.normative_direction || ""}`;
  }

  function formalNodes(formal) {
    const important = new Map();
    for (const node of formal?.important_institutions || []) {
      if (node && typeof node === "object") important.set(nodeKey(node), node);
    }
    const result = [];
    const seen = new Set();
    const add = profile => {
      if (!profile || typeof profile !== "object") return;
      const key = nodeKey(profile);
      if (seen.has(key)) return;
      seen.add(key);
      const major = important.get(key) || null;
      result.push({...major, ...profile, _major:Boolean(major || profile.decision === "MAJOR_NODE")});
    };
    for (const node of formal?.M_positive_profile || []) add(node);
    for (const node of formal?.M_negative_profile || []) add(node);
    for (const node of formal?.M_mixed_profile || []) add(node);
    for (const node of important.values()) if (!seen.has(nodeKey(node))) add(node);
    return result;
  }

  function publicGrade(item) {
    const match = String(item?.grade || "").match(/\bG([0-5])\b/i);
    if (!match) return "";
    const suffix = /(?:upper|high)/i.test(item.grade) ? "+" : /(?:lower|low)/i.test(item.grade) ? "-" : "";
    return `${PUBLIC_GRADE[`G${match[1]}`] || ""}${suffix}`;
  }

  function weightValue(node) {
    const value = Number(node?.signed_weight);
    return Number.isFinite(value) ? value : 0;
  }

  function influenceLabel(node) {
    const weight = Math.abs(weightValue(node));
    if (weight >= 4) return "最高影响";
    if (weight >= 3) return "高影响";
    if (weight >= 2) return "中等影响";
    if (weight >= 1) return "基础影响";
    if (weight > 0) return "有限影响";
    return "不单独加权";
  }

  function receptionClass(node) {
    const effect = String(node?.S_effect || "").toUpperCase();
    const gate = String(node?.durability_gate || "").toUpperCase();
    if (effect === "S++" || gate.includes("PLUSPLUS")) return "cross-dynasty";
    if (effect === "S+" || gate.includes("PASS")) return "multi-reign";
    return "none";
  }

  function cleanPublicText(value) {
    return String(value || "")
      .replace(/按正式显式复核完成(?:canonical)?生命周期复核[；，。]?/gi, "")
      .replace(/按跨朝同领域谱系横向复裁[：:]?/g, "")
      .replace(/V\d+(?:\.\d+)?(?:净值\s*-?\d+(?:\.\d+)?)?/gi, "")
      .replace(/(?:完整制度)?净值\s*-?\d+(?:\.\d+)?/g, "")
      .replace(/结算\s*[SABCDE][+\-]?[-—]?\w*/gi, "")
      .replace(/\bcanonical\b/gi, "")
      .replace(/闭合\s*R4/gi, "已证明跨朝代长期沿用")
      .replace(/闭合\s*R3/gi, "已证明被多个后继统治阶段持续采用")
      .replace(/\bR4\b/gi, "跨朝代长期沿用")
      .replace(/\bR3\b/gi, "多个后继统治阶段持续采用")
      .replace(/\bR[12]\b/gi, "后世接收范围有限")
      .replace(/\bR0\b/gi, "本人任内已有实际运行")
      .replace(/只保留改变核心规则的创设、重大重组、重大重建、权威化定型或重大文明纠偏；一般沿袭和维护已排除。/g,
        "这项制度改变了本领域的核心规则；一般沿袭和日常维护不重复算作制度建设。")
      .replace(/生命周期/g, "长期运行过程")
      .replace(/复核/g, "核对")
      .replace(/[；，]\s*[；，]+/g, "；")
      .replace(/^\s*[；，。]+|[；，。\s]+$/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function balanceSummary(formal, item, nodes) {
    let positive = 0;
    let negative = 0;
    for (const node of nodes) {
      const weight = weightValue(node);
      if (weight > 0) positive += weight;
      if (weight < 0) negative += Math.abs(weight);
    }
    let balance = "正负影响大体接近";
    if (positive > 0 && positive >= negative * 2) balance = "正向影响显著占优";
    else if (positive > negative * 1.15) balance = "正向影响占优";
    else if (negative > 0 && negative >= positive * 2) balance = "负向影响显著占优";
    else if (negative > positive * 1.15) balance = "负向影响占优";

    const cross = nodes.filter(node => weightValue(node) > 0 && receptionClass(node) === "cross-dynasty").length;
    const multi = nodes.filter(node => weightValue(node) > 0 && receptionClass(node) === "multi-reign").length;
    const negativeMajor = nodes.filter(node => weightValue(node) < 0 && node._major).length;
    const parts = ["制度数量不直接决定等级。"];
    if (cross) parts.push(`${cross}项正向制度形成跨朝代长期沿用的核心制度骨架。`);
    else if (multi) parts.push(`${multi}项正向制度被多个后继统治阶段持续采用。`);
    if (negativeMajor) {
      parts.push(`${negativeMajor}项负向重大制度构成明确扣减，但其结算影响需按各自权重判断，不能与正向重大制度按条数一一相抵。`);
    }
    const grade = publicGrade(item);
    parts.push(`${balance}${grade ? `，最终制度建设为 ${grade}` : ""}。`);
    return parts.join("");
  }

  function ensureStyles() {
    if (document.getElementById("second-item-institution-weight-style")) return;
    const style = document.createElement("style");
    style.id = "second-item-institution-weight-style";
    style.textContent = `
      .second-item-institution-balance{margin:10px 0 16px;padding:11px 13px;border-left:3px solid var(--gold);background:#f1eee6;font-size:12px;line-height:1.75}
      .second-item-institution-impact{display:inline-block;margin-left:auto;padding:1px 7px;border-radius:999px;background:#ecefe6;color:var(--ink);font-size:10px;font-weight:700;white-space:nowrap}
      .second-item-institution-head{align-items:center}
      .second-item-institution-reception[data-reception="cross-dynasty"]{font-weight:700}
    `;
    document.head.append(style);
  }

  function cardForNode(reading, node) {
    const label = cleanPublicText(node?.label_zh || node?.mechanism || "");
    if (!label) return null;
    return Array.from(reading.querySelectorAll(".second-item-institution-list > li")).find(card =>
      card.querySelector(".second-item-institution-head strong")?.textContent.trim() === label
    ) || null;
  }

  function patchCard(reading, node) {
    const card = cardForNode(reading, node);
    if (!card) return;
    const head = card.querySelector(".second-item-institution-head");
    if (!head) return;

    let badge = head.querySelector(".second-item-institution-badge");
    if (node._major) {
      if (!badge) {
        badge = document.createElement("span");
        badge.className = "second-item-institution-badge";
        head.prepend(badge);
      }
      const role = ROLE_LABELS[node.major_node_role] || "";
      badge.textContent = role ? `重大制度 · ${role}` : "重大制度";
    }

    let impact = head.querySelector(".second-item-institution-impact");
    if (!impact) {
      impact = document.createElement("span");
      impact.className = "second-item-institution-impact";
      head.append(impact);
    }
    impact.textContent = `对最终等级：${influenceLabel(node)}`;

    const note = card.querySelector(".second-item-institution-note");
    const cleaned = cleanPublicText(node.reason || note?.textContent || "");
    if (note) {
      if (cleaned) note.textContent = cleaned;
      else note.remove();
    }

    const reception = card.querySelector(".second-item-institution-reception");
    const receptionType = receptionClass(node);
    if (reception) {
      reception.dataset.reception = receptionType;
      if (receptionType === "cross-dynasty") {
        reception.textContent = "后世接收：跨朝代长期沿用，属于本项最高耐久层级。";
      } else if (receptionType === "multi-reign") {
        reception.textContent = "后世接收：多个后继统治阶段持续采用。";
      }
    }
  }

  async function patch() {
    ensureStyles();
    const record = currentRecord();
    if (!record) return;
    const item = methodItem(record);
    const detail = Array.from(document.querySelectorAll(".net-metric-detail[data-second-source-label]"))
      .find(node => node.dataset.secondSourceLabel === "A制度建设");
    const body = detail?.querySelector(":scope > .net-metric-body");
    const reading = body?.querySelector(":scope > .second-item-institution-reading");
    if (!item || !body || !reading || reading.dataset.weightPolish === "done") return;

    const formal = await formalA(record, item);
    if (!formal || !reading.isConnected || currentRecord()?.ruler_id !== record.ruler_id) return;
    const nodes = formalNodes(formal);

    const intro = reading.querySelector(".second-item-institution-intro");
    if (intro) intro.textContent = "按正向、负向和正负并存分类阅读；重大制度会标明类型、后世接收和对最终等级的影响强度。";

    for (const heading of reading.querySelectorAll(".second-item-institution-group > h4")) {
      heading.textContent = heading.textContent.replace(/\s*·\s*\d+项\s*$/, "");
    }

    let balance = reading.querySelector(".second-item-institution-balance");
    if (!balance) {
      balance = document.createElement("div");
      balance.className = "second-item-institution-balance";
      intro?.after(balance);
    }
    balance.textContent = balanceSummary(formal, item, nodes);

    for (const node of nodes) patchCard(reading, node);

    const gradeDetails = Array.from(body.querySelectorAll(":scope > details")).find(details =>
      details.querySelector(":scope > summary")?.textContent.trim() === "为什么最终是这个等级？"
    );
    if (gradeDetails) {
      const prose = gradeDetails.querySelector(":scope > .prose, :scope > p");
      const text = balanceSummary(formal, item, nodes);
      if (prose) prose.textContent = text;
      else gradeDetails.append(Object.assign(document.createElement("p"), {className:"prose", textContent:text}));
    }

    reading.dataset.weightPolish = "done";
  }

  function schedule() {
    if (scheduled) return;
    scheduled = true;
    requestAnimationFrame(() => {
      scheduled = false;
      void patch();
    });
  }

  new MutationObserver(schedule).observe(screen, {childList:true, subtree:true, characterData:true});
  window.addEventListener("hashchange", schedule);
  schedule();
})();
