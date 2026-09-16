"use strict";

(() => {
  const screen = document.getElementById("screen");
  if (!screen) return;

  const PUBLIC_GRADE = {G0:"E",G1:"D",G2:"C",G3:"B",G4:"A",G5:"S"};
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
      console.error("Failed to load public institution cleanup data", error);
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
      result.push({...major, ...profile});
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

  function numberValue(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function fmt(value) {
    const number = numberValue(value);
    if (number == null) return "—";
    return Number.isInteger(number) ? String(number) : number.toFixed(1).replace(/\.0$/, "");
  }

  function signed(value) {
    const number = numberValue(value);
    if (number == null) return "—";
    return `${number > 0 ? "+" : ""}${fmt(number)}`;
  }

  function weightValue(node) {
    const value = Number(node?.signed_weight);
    return Number.isFinite(value) ? value : 0;
  }

  function officialTotals(formal, nodes) {
    let positive = numberValue(formal?.P_gross);
    let negative = numberValue(formal?.N_gross);
    let net = numberValue(formal?.A_net_units);
    if (positive == null || negative == null) {
      positive = 0;
      negative = 0;
      for (const node of nodes) {
        const weight = weightValue(node);
        if (weight > 0) positive += weight;
        if (weight < 0) negative += Math.abs(weight);
      }
    }
    if (net == null) net = positive - negative;
    return {positive, negative, net};
  }

  function cleanBasis(value) {
    const raw = String(value || "").replace(/`/g, "").replace(/\s+/g, " ").trim();
    if (!raw) return "";
    const parts = raw.split(/(?<=[。！？])/).map(part => part.trim()).filter(Boolean);
    const kept = parts.filter(part => {
      if (/^(?:保留|改判|普通S|按正式|按跨朝|角色改为)/.test(part) && /(?:M[0-3]|S(?:\+\+|[+−-])?|非S|合计\s*[+−-]?\d|C_A|MAJOR_|V\d)/i.test(part)) return false;
      if (/(?:合并净方向|重大非S建设支持|C_A\s*=|balanced|mixed_(?:positive|negative)|结算G[0-5]|制度净值|V\d)/i.test(part)) return false;
      return true;
    });
    return kept.join("")
      .replace(/闭合\s*R4/gi, "已有证据证明跨朝代长期沿用")
      .replace(/闭合\s*R3/gi, "已有证据证明多个后继统治阶段持续采用")
      .replace(/\bR4\b/gi, "跨朝代长期沿用")
      .replace(/\bR3\b/gi, "多个后继统治阶段持续采用")
      .replace(/\bR[12]\b/gi, "后世接收范围有限")
      .replace(/\bR0\b/gi, "本人任内已有实际运行")
      .replace(/\bM[0-3]\b/gi, "")
      .replace(/(?:普通)?S(?:\+\+|[+−-])?/g, "")
      .replace(/非S/g, "")
      .replace(/本节点/g, "这里")
      .replace(/不重复折入/g, "不重复计算")
      .replace(/不再重复奖惩/g, "不再重复计算")
      .replace(/重复计入/g, "重复计算")
      .replace(/消费/g, "另行计算")
      .replace(/倒算/g, "归入")
      .replace(/倒归/g, "归入")
      .replace(/径判/g, "直接判断为")
      .replace(/抬档/g, "提高等级")
      .replace(/抬M3或S/g, "提高等级")
      .replace(/[；，]\s*[；，]+/g, "；")
      .replace(/。\s*。+/g, "。")
      .replace(/；\s*。/g, "。")
      .replace(/^[；，。\s]+|[；，。\s]+$/g, "")
      .trim();
  }

  function cardForNode(reading, node) {
    const label = String(node?.label_zh || node?.mechanism || "").trim();
    if (!label) return null;
    return Array.from(reading.querySelectorAll(".second-item-institution-list > li")).find(card =>
      card.querySelector(".second-item-institution-head strong")?.textContent.trim() === label
    ) || null;
  }

  function patchCard(reading, node) {
    const card = cardForNode(reading, node);
    if (!card) return;
    const source = node?.adjudication_basis || node?.reason || "";
    const cleaned = cleanBasis(source);
    let note = card.querySelector(".second-item-institution-note");
    if (!cleaned) {
      note?.remove();
      return;
    }
    if (!note) {
      note = document.createElement("p");
      note.className = "second-item-institution-note";
      const reception = card.querySelector(".second-item-institution-reception");
      if (reception) reception.before(note);
      else card.append(note);
    }
    note.textContent = cleaned;
  }

  function balancePhrase(positive, negative) {
    const largest = Math.max(positive, negative, 1);
    const gap = Math.abs(positive - negative) / largest;
    if (gap <= 0.1) return positive >= negative ? "正负几乎相抵，只留下小幅正向净值" : "正负几乎相抵，最终略偏负向";
    if (positive >= negative * 1.8) return "正向影响明显占优";
    if (negative >= positive * 1.8) return "负向影响明显占优";
    return positive > negative ? "正向影响占优" : negative > positive ? "负向影响占优" : "正负完全相抵";
  }

  function summaryText(formal, item, nodes) {
    const {positive, negative, net} = officialTotals(formal, nodes);
    const durablePositive = numberValue(formal?.S_total) || 0;
    const durableNegative = numberValue(formal?.S_minus) || 0;
    const parts = [
      `本项不按制度条数相减。综合影响：正向 ${fmt(positive)}、负向 ${fmt(negative)}，净值 ${signed(net)}；这些数字表示制度影响权重，不是制度数量。`,
    ];
    if (durablePositive > 0 && durableNegative > 0) {
      parts.push(`其中 ${fmt(durablePositive)} 项正向制度因后世持续接收获得耐久加权，${fmt(durableNegative)} 项负向制度也因长期延续形成耐久扣减。`);
    } else if (durablePositive > 0) {
      parts.push(`其中 ${fmt(durablePositive)} 项正向制度因后世持续接收获得耐久加权；现有负向制度未形成同等级的耐久扣减。`);
    } else if (durableNegative > 0) {
      parts.push(`其中 ${fmt(durableNegative)} 项负向制度因长期延续形成耐久扣减；现有正向制度未形成同等级的长期接收加权。`);
    }
    const grade = publicGrade(item);
    parts.push(`${balancePhrase(positive, negative)}${grade ? `，最终制度建设为 ${grade}` : ""}。`);
    return parts.join("");
  }

  async function patch() {
    const record = currentRecord();
    if (!record) return;
    const item = methodItem(record);
    const detail = Array.from(document.querySelectorAll(".net-metric-detail[data-second-source-label]"))
      .find(node => node.dataset.secondSourceLabel === "A制度建设");
    const body = detail?.querySelector(":scope > .net-metric-body");
    const reading = body?.querySelector(":scope > .second-item-institution-reading");
    if (!item || !body || !reading || reading.dataset.publicCleanup === "done") return;
    if (reading.dataset.weightPolish !== "done") return;

    const formal = await formalA(record, item);
    if (!formal || !reading.isConnected || currentRecord()?.ruler_id !== record.ruler_id) return;
    const nodes = formalNodes(formal);

    for (const node of nodes) patchCard(reading, node);

    const text = summaryText(formal, item, nodes);
    const balance = reading.querySelector(".second-item-institution-balance");
    if (balance) balance.textContent = text;

    const gradeDetails = Array.from(body.querySelectorAll(":scope > details")).find(details =>
      details.querySelector(":scope > summary")?.textContent.trim() === "为什么最终是这个等级？"
    );
    if (gradeDetails) {
      let prose = gradeDetails.querySelector(":scope > .prose, :scope > p");
      if (!prose) {
        prose = document.createElement("p");
        prose.className = "prose";
        gradeDetails.append(prose);
      }
      prose.textContent = text;
    }

    reading.dataset.publicCleanup = "done";
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
