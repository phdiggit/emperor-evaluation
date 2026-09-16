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

  function influenceLabel(node) {
    const weight = Math.abs(weightValue(node));
    if (weight >= 4) return "最高影响";
    if (weight >= 3) return "高影响";
    if (weight >= 2) return "中等影响";
    if (weight >= 1) return "基础影响";
    if (weight > 0) return "有限影响";
    return "不单独加权";
  }

  function officialTotals(formal) {
    const positive = numberValue(formal?.P_gross);
    const negative = numberValue(formal?.N_gross);
    const net = numberValue(formal?.A_net_units);
    return {
      available: positive != null && negative != null && net != null,
      positive,
      negative,
      net,
    };
  }

  function rawLabel(node) {
    return String(node?.label_zh || node?.mechanism || "").trim();
  }

  function labelBigrams(value) {
    const chars = String(value || "").replace(/[^\u3400-\u9fff]/g, "");
    const result = [];
    for (let i = 0; i + 1 < chars.length; i += 1) result.push(chars.slice(i, i + 2));
    return [...new Set(result)];
  }

  function relevantSource(node) {
    if (node?.adjudication_basis) return String(node.adjudication_basis);
    const source = String(node?.reason || node?.direction_reason || "").trim();
    if (!source) return "";
    const clauses = source.split(/(?<=[。；])/).map(part => part.trim()).filter(Boolean);
    if (clauses.length <= 1) return source;
    const bigrams = labelBigrams(rawLabel(node));
    if (!bigrams.length) return source;
    const scored = clauses.map((clause, index) => ({
      clause,
      index,
      score:bigrams.reduce((sum, token) => sum + (clause.includes(token) ? 1 : 0), 0),
    }));
    const max = Math.max(...scored.map(item => item.score));
    if (!max) return source;
    const kept = scored
      .filter(item => item.score >= Math.max(1, Math.ceil(max * 0.45)))
      .slice(0, 2)
      .sort((a, b) => a.index - b.index)
      .map(item => item.clause);
    return kept.length ? kept.join("") : source;
  }

  function auditClause(value) {
    const clause = String(value || "").trim();
    if (!clause) return true;
    if (/^(?:保留|改判|普通S|角色改为)/.test(clause) && /(?:M[0-3]|S(?:\+\+|[+−-])?|非S|合计\s*[+−-]?\d|C_A|MAJOR_)/i.test(clause)) return true;
    if (/^(?:按正式显式复核|按跨朝同领域谱系横向复裁|按A审查清单)/.test(clause)) return true;
    if (/^(?:正负S|S净值)/.test(clause)) return true;
    if (/(?:结算G[0-5]|制度净值|V\d|A结构厚度|主档消费|position权重|统一净余|净账与独立门槛)/i.test(clause)) return true;
    return false;
  }

  function cleanClause(value) {
    return String(value || "")
      .replace(/新增\s*R4\s*专属接收材料/gi, "新增了跨朝代长期沿用的证据")
      .replace(/新增\s*R3\s*专属接收材料/gi, "新增了多个后继统治阶段持续采用的证据")
      .replace(/后继接收闭合\s*R4/gi, "跨朝代长期沿用已有充分证据")
      .replace(/后继接收闭合\s*R3/gi, "多个后继统治阶段持续采用已有充分证据")
      .replace(/现(?:有)?材料未(?:独立)?闭合\s*R4/gi, "现有证据尚不足以证明跨朝代长期沿用")
      .replace(/现(?:有)?材料未(?:独立)?闭合\s*R3/gi, "现有证据尚不足以证明多个后继统治阶段持续采用")
      .replace(/长期基线门禁闭合/g, "长期沿用已有充分证据")
      .replace(/撤去\s*S\+\+\s*溢价/g, "现有证据不足以支持更高的跨朝代长期影响")
      .replace(/保留独立重大贡献\s*S\+/g, "构成独立的重大正向贡献")
      .replace(/保留\s*S\+/g, "确认具有长期正向影响")
      .replace(/按\s*mixed\s*非?S?\s*处理/gi, "正负作用并存")
      .replace(/按\s*balanced\s*非?S?\s*处理/gi, "正负作用大体相抵")
      .replace(/混合?偏负\s*M[0-3]|混负\s*M[0-3]/gi, "负向作用占主导")
      .replace(/混合?偏正\s*M[0-3]|混正\s*M[0-3]/gi, "正向作用占主导")
      .replace(/平衡\s*M[0-3]/gi, "正负作用大体相抵")
      .replace(/正向\s*M[0-3]/gi, "正向制度作用")
      .replace(/负向\s*M[0-3]/gi, "负向制度作用")
      .replace(/([^；。]{2,70})按[^；。]{0,36}完成生命周期裁决/g, "$1的设立、运行与后续变化已有材料支持")
      .replace(/完成生命周期裁决/g, "其设立、运行与后续变化已有材料支持")
      .replace(/生命周期/g, "设立、运行与后续变化")
      .replace(/闭合\s*R4/gi, "已有证据证明跨朝代长期沿用")
      .replace(/闭合\s*R3/gi, "已有证据证明多个后继统治阶段持续采用")
      .replace(/\bR4\b/gi, "跨朝代长期沿用")
      .replace(/\bR3\b/gi, "多个后继统治阶段持续采用")
      .replace(/\bR[12]\b/gi, "后世接收范围有限")
      .replace(/\bR0\b/gi, "本人任内已有实际运行")
      .replace(/\bM[0-3]\b/gi, "")
      .replace(/S\+\+|S\+|S−|S-/g, "")
      .replace(/非S/g, "")
      .replace(/\bmixed\b/gi, "正负作用并存")
      .replace(/\bbalanced\b/gi, "正负作用大体相抵")
      .replace(/门禁/g, "长期接收条件")
      .replace(/接收材料/g, "后世沿用证据")
      .replace(/耐久溢价/g, "长期影响加权")
      .replace(/移出A计权/g, "不在制度建设中重复计算")
      .replace(/A计权/g, "制度建设计分")
      .replace(/不折入A/g, "不计入制度建设")
      .replace(/不增单位/g, "不额外增加本项权重")
      .replace(/本节点/g, "这里")
      .replace(/谱系/g, "制度沿革")
      .replace(/前态/g, "此前状态")
      .replace(/正功/g, "正向贡献")
      .replace(/归责/g, "责任归属")
      .replace(/不重复折入/g, "不重复计算")
      .replace(/不再重复奖惩/g, "不再重复计算")
      .replace(/重复计入/g, "重复计算")
      .replace(/重复消费/g, "重复计算")
      .replace(/消费/g, "计入")
      .replace(/倒算本人/g, "归到本人")
      .replace(/倒算/g, "归入")
      .replace(/倒归/g, "归入")
      .replace(/径判/g, "直接判断为")
      .replace(/抬档/g, "提高等级")
      .replace(/抬M3或S/g, "提高等级")
      .replace(/独立门槛/g, "独立成立条件")
      .replace(/[；，]\s*[；，]+/g, "；")
      .replace(/。\s*。+/g, "。")
      .replace(/；\s*。/g, "。")
      .replace(/，\s*。/g, "。")
      .replace(/^\s*[；，。]+|[；，。\s]+$/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function cleanBasis(value) {
    const raw = String(value || "").replace(/`/g, "").replace(/\s+/g, " ").trim();
    if (!raw) return "";
    const clauses = raw.split(/(?<=[。；])/).map(part => part.trim()).filter(Boolean);
    return clauses
      .filter(clause => !auditClause(clause))
      .map(cleanClause)
      .filter(Boolean)
      .join("")
      .replace(/[；，]\s*[；，]+/g, "；")
      .replace(/。\s*。+/g, "。")
      .replace(/；\s*。/g, "。")
      .replace(/^[；，。\s]+|[；，。\s]+$/g, "")
      .trim();
  }

  function matchingCards(reading, label) {
    return Array.from(reading.querySelectorAll(".second-item-institution-list > li")).filter(card =>
      card.querySelector(".second-item-institution-head strong")?.textContent.trim() === label
    );
  }

  function cardForNode(reading, node, nodes, index) {
    const label = rawLabel(node);
    if (!label) return null;
    const occurrence = nodes.slice(0, index).filter(other => rawLabel(other) === label).length;
    return matchingCards(reading, label)[occurrence] || null;
  }

  function patchCard(reading, node, nodes, index) {
    const card = cardForNode(reading, node, nodes, index);
    if (!card) return;

    let impact = card.querySelector(".second-item-institution-impact");
    if (!impact) {
      const head = card.querySelector(".second-item-institution-head");
      if (head) {
        impact = document.createElement("span");
        impact.className = "second-item-institution-impact";
        head.append(impact);
      }
    }
    if (impact) impact.textContent = `对最终等级：${influenceLabel(node)}`;

    const cleaned = cleanBasis(relevantSource(node));
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

  function durabilityText(formal) {
    const cross = numberValue(formal?.S_plus_plus) || 0;
    const multi = numberValue(formal?.S_plus_regular) || 0;
    const negative = numberValue(formal?.S_minus) || 0;
    const positiveParts = [];
    if (cross) positiveParts.push(`${fmt(cross)} 项正向制度达到跨朝代长期接收`);
    if (multi) positiveParts.push(`${fmt(multi)} 项正向制度被多个后继统治阶段持续采用`);
    const parts = [];
    if (positiveParts.length) parts.push(positiveParts.join("，"));
    if (negative) parts.push(`${fmt(negative)} 项负向制度因长期延续形成耐久扣减`);
    return parts.length ? `${parts.join("；")}。` : "";
  }

  function summaryText(formal, item) {
    const totals = officialTotals(formal);
    const grade = publicGrade(item);
    const parts = [];
    if (totals.available) {
      parts.push(`本项不按制度条数相减。正式结算的制度影响权重：正向 ${fmt(totals.positive)}、负向 ${fmt(totals.negative)}，净值 ${signed(totals.net)}。`);
      const durable = durabilityText(formal);
      if (durable) parts.push(durable);
      parts.push(`${balancePhrase(totals.positive, totals.negative)}${grade ? `，最终制度建设为 ${grade}` : ""}。`);
    } else {
      parts.push("本项不按制度条数相减；制度作用强度、实际运行和后世接收共同决定等级，页面不自行把列表节点等权相加。");
      const durable = durabilityText(formal);
      if (durable) parts.push(durable);
      if (grade) parts.push(`最终制度建设按正式结论为 ${grade}。`);
    }
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

    nodes.forEach((node, index) => patchCard(reading, node, nodes, index));

    const text = summaryText(formal, item);
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
