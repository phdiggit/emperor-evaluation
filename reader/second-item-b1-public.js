"use strict";

(() => {
  const screen = document.getElementById("screen");
  if (!screen) return;

  const PUBLIC_GRADE = {G0:"E",G1:"D",G2:"C",G3:"B",G4:"A",G5:"S"};
  const ROLE_LABEL = {
    core:"核心行政链",
    central:"中枢行政链",
    support:"支撑行政链",
    distributed:"分布式行政链",
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
    return (record?.net?.component_details?.method || []).find(item => item.label === "B1官僚治理") || null;
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

  async function formalB1(record, item) {
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
      console.error("Failed to load formal B1 record", error);
      return null;
    });
    cache.set(key, pending);
    return pending;
  }

  function publicGrade(item) {
    const match = String(item?.grade || "").match(/\bG([0-5])\b/i);
    if (!match) return "";
    const suffix = /(?:upper|high)/i.test(item.grade) ? "+" : /(?:lower|low)/i.test(item.grade) ? "-" : "";
    return `${PUBLIC_GRADE[`G${match[1]}`] || ""}${suffix}`;
  }

  function profileKey(profile) {
    return profile?.lifecycle_group_key || profile?.lifecycle_key || profile?.profile_id || profile?.material_id || profile?.mechanism || "";
  }

  function excluded(profile) {
    return profile?.position_count_mode === "context_only" || profile?.direction === "context";
  }

  function absorbed(profile) {
    return profile?.position_count_mode === "absorbed_same_lifecycle" || (
      Number(profile?.position_weight_override) === 0 && Boolean(profile?.absorbed_into_lifecycle_key)
    );
  }

  function groupKey(profile) {
    const direction = String(profile?.direction || "").toLowerCase();
    if (direction === "positive") return "positive";
    if (direction === "negative") return "negative";
    return "mixed";
  }

  function profiles(formal) {
    const groups = {positive:[], negative:[], mixed:[]};
    const all = [
      ...(formal?.M_positive_profile || []),
      ...(formal?.M_negative_profile || []),
      ...(formal?.M_mixed_profile || []),
    ].filter(profile => profile && typeof profile === "object");

    const primary = new Map();
    const supplements = new Map();
    for (const profile of all) {
      if (excluded(profile)) continue;
      if (absorbed(profile)) {
        const target = profile.absorbed_into_lifecycle_key || profileKey(profile);
        if (!supplements.has(target)) supplements.set(target, []);
        supplements.get(target).push(profile);
        continue;
      }
      const key = profileKey(profile);
      if (!key || primary.has(key)) continue;
      primary.set(key, {...profile, _key:key});
    }
    for (const profile of primary.values()) {
      profile._supplements = supplements.get(profile._key) || supplements.get(profile.lifecycle_key) || [];
      groups[groupKey(profile)].push(profile);
    }
    return groups;
  }

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function roleLabel(profile) {
    return ROLE_LABEL[String(profile?.b1_role || "").toLowerCase()] || "独立行政链";
  }

  function impactLabel(profile) {
    const value = Number(profile?.signed_weight);
    if (!Number.isFinite(value)) return "结构性依据";
    const abs = Math.abs(value);
    if (abs >= 2) return "主要影响";
    if (abs >= 1) return "重要影响";
    if (abs > 0) return "有限影响";
    return "不单独计入";
  }

  function directionLabel(profile) {
    return ({
      positive:"正向",
      negative:"负向",
      mixed_positive:"正向主导",
      mixed_negative:"负向主导",
      mixed:"正负并存",
      balanced:"正负并存",
      neutral:"正负并存",
    })[profile?.direction] || "正负并存";
  }

  function mechanismText(value) {
    return String(value || "")
      .replace(/`/g, "")
      .replace(/^B1[-_/]?(?:central|distributed|personnel)?/i, "")
      .replace(/(?:core|support)\s*$/gi, "")
      .replace(/\b(?:core|support|central|distributed)\b/gi, "")
      .replace(/\bM[0-3]\b/gi, "")
      .replace(/\s+/g, " ")
      .replace(/^[：:、，；\s]+|[：:、，；\s]+$/g, "")
      .trim();
  }

  function publicText(value) {
    return String(value || "")
      .replace(/`/g, "")
      .replace(/\bB1\b/g, "官僚治理")
      .replace(/\bB2\b/g, "反馈与约束")
      .replace(/G([0-5])/g, (_, n) => `${PUBLIC_GRADE[`G${n}`] || n}档`)
      .replace(/核心行政机制\s*M3|core\s*M3/gi, "核心行政运行链")
      .replace(/中枢(?:运行)?链?\s*M3|central\s*M3/gi, "中枢行政运行链")
      .replace(/支撑(?:链)?\s*M3|support\s*M3/gi, "支撑行政运行链")
      .replace(/独立\s*M[0-3]/gi, "独立行政运行链")
      .replace(/\bM[0-3]\b/gi, "行政运行链")
      .replace(/\bcore\b/gi, "核心行政链")
      .replace(/\bsupport\b/gi, "支撑行政链")
      .replace(/\bcentral\b/gi, "中枢行政链")
      .replace(/\bdistributed\b/gi, "分布式行政链")
      .replace(/\bcontext\b/gi, "背景材料")
      .replace(/闭合/g, "形成充分证据")
      .replace(/消费/g, "计入")
      .replace(/主档/g, "等级")
      .replace(/门槛占用/g, "等级要求")
      .replace(/净余量/g, "剩余有效依据")
      .replace(/不重复计数/g, "不重复计算")
      .replace(/不再作为独立[^；。]*计入/g, "不再单独计算")
      .replace(/改作背景材料/g, "作为背景材料处理")
      .replace(/改作context/gi, "作为背景材料处理")
      .replace(/撤为背景材料/g, "作为背景材料处理")
      .replace(/撤为context/gi, "作为背景材料处理")
      .replace(/\s+/g, " ")
      .replace(/[；，]\s*[；，]+/g, "；")
      .trim();
  }

  function summaryText(formal, item, groups) {
    const grade = publicGrade(item);
    const names = group => group.map(profile => mechanismText(profile.mechanism)).filter(Boolean);
    const parts = ["本项按独立行政运行链判断，不按列表条数等权相加；同一运行生命周期中已经归并的材料不会重复列项。"];
    const positive = names(groups.positive);
    const negative = names(groups.negative);
    const mixed = names(groups.mixed);
    if (positive.length) parts.push(`正式认定的正向运行包括：${positive.join("；")}。`);
    if (negative.length) parts.push(`明确的负向行政失灵包括：${negative.join("；")}。`);
    if (mixed.length) parts.push(`另有正负并存的运行机制：${mixed.join("；")}。`);
    if (!positive.length && !negative.length && !mixed.length) parts.push("现有正式记录没有形成可独立计入的行政运行链。");
    if (grade) parts.push(`综合运行强度、独立性和持续性后，官僚治理的正式等级为 ${grade}。`);
    return parts.join("");
  }

  function noteText(profile) {
    const source = profile?.source_basis || "";
    if (!source) return "";
    return publicText(source);
  }

  function card(profile) {
    const li = make("li", "second-item-b1-card");
    if (profile?.profile_id) li.dataset.b1ProfileId = profile.profile_id;
    if (profile?._key) li.dataset.b1LifecycleKey = profile._key;

    const head = make("div", "second-item-b1-head");
    head.append(make("span", "second-item-b1-role", roleLabel(profile)));
    head.append(make("strong", "", mechanismText(profile.mechanism) || "行政运行机制"));
    head.append(make("span", "second-item-b1-direction", directionLabel(profile)));
    head.append(make("span", "second-item-b1-impact", `对本项等级：${impactLabel(profile)}`));
    li.append(head);

    const note = noteText(profile);
    if (note) li.append(make("p", "second-item-b1-note", note));
    if (profile?._supplements?.length) {
      li.append(make("small", "second-item-b1-merged", "同一运行链还有补充材料，已合并判断，不重复列为独立机制。"));
    }
    return li;
  }

  function group(title, items) {
    const section = make("section", "second-item-b1-group");
    section.append(make("h4", "", title));
    if (!items.length) {
      section.append(make("p", "second-item-b1-empty", "没有独立可计的运行链。"));
      return section;
    }
    const list = make("ul", "second-item-b1-list");
    list.replaceChildren(...items.map(card));
    section.append(list);
    return section;
  }

  function makeDetails(title, text, className = "") {
    if (!text) return null;
    const details = make("details", className);
    details.append(make("summary", "", title), make("p", "prose", text));
    return details;
  }

  function ensureStyles() {
    if (document.getElementById("second-item-b1-public-style")) return;
    const style = document.createElement("style");
    style.id = "second-item-b1-public-style";
    style.textContent = `
      .second-item-b1-reading{margin:4px 0 8px}
      .second-item-b1-intro{margin:4px 0 14px;line-height:1.75}
      .second-item-b1-summary{margin:10px 0 16px;padding:11px 13px;border-left:3px solid var(--gold);background:#f1eee6;font-size:12px;line-height:1.75}
      .second-item-b1-group{margin:14px 0 18px}
      .second-item-b1-group>h4{margin:0 0 8px;font-size:15px}
      .second-item-b1-list{list-style:none;margin:0;padding:0;display:grid;gap:8px}
      .second-item-b1-card{margin:0;padding:10px 12px;border:1px solid var(--line);border-radius:5px;background:#fff}
      .second-item-b1-head{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
      .second-item-b1-head strong{font-size:14px}
      .second-item-b1-role{display:inline-block;padding:1px 6px;border:1px solid var(--line);border-radius:999px;font-size:10px;line-height:1.6;color:var(--green);font-weight:700;background:#f4f5ef}
      .second-item-b1-direction{font-size:10px;color:var(--muted);font-weight:700}
      .second-item-b1-impact{display:inline-block;margin-left:auto;padding:1px 7px;border-radius:999px;background:#ecefe6;color:var(--ink);font-size:10px;font-weight:700;white-space:nowrap}
      .second-item-b1-note{margin:6px 0 0;font-size:12px;line-height:1.72}
      .second-item-b1-merged{display:block;margin-top:5px;font-size:11px;line-height:1.65;color:var(--muted)}
      .second-item-b1-empty{margin:4px 0;color:var(--muted);font-size:12px}
    `;
    document.head.append(style);
  }

  async function patch() {
    ensureStyles();
    const record = currentRecord();
    if (!record) return;
    const item = methodItem(record);
    const detail = Array.from(document.querySelectorAll(".net-metric-detail[data-second-source-label]"))
      .find(node => node.dataset.secondSourceLabel === "B1官僚治理");
    const body = detail?.querySelector(":scope > .net-metric-body");
    if (!item || !body || body.dataset.b1Public === "done") return;
    if (!body.querySelector(":scope > .second-item-public-reading")) return;

    const formal = await formalB1(record, item);
    if (!formal || !body.isConnected || currentRecord()?.ruler_id !== record.ruler_id) return;
    const grouped = profiles(formal);

    const audit = body.querySelector(":scope > .net-audit-sources");
    audit?.remove();
    const rawFormal = body.querySelector(":scope > .net-formal-basis-raw");
    rawFormal?.remove();
    const boundary = Array.from(body.querySelectorAll(":scope > details")).find(node =>
      node.querySelector(":scope > summary")?.textContent.trim() === "范围与边界"
    );
    boundary?.remove();
    const how = Array.from(body.querySelectorAll(":scope > details")).find(node =>
      node.querySelector(":scope > summary")?.textContent.trim() === "这个分数怎么算？"
    );
    how?.remove();

    body.innerHTML = "";
    const reading = make("div", "second-item-b1-reading");
    reading.append(make("div", "label", "官僚治理运行链"));
    reading.append(make("p", "second-item-b1-intro", "按独立行政运行链展示。核心、中枢、支撑等角色表示它在正式判断中的结构位置；同一生命周期内已经归并的材料不会重复列项。"));
    reading.append(make("div", "second-item-b1-summary", summaryText(formal, item, grouped)));
    reading.append(group("正向行政运行", grouped.positive));
    reading.append(group("负向行政失灵", grouped.negative));
    reading.append(group("正负并存的行政机制", grouped.mixed));
    body.append(reading);

    body.append(makeDetails("为什么最终是这个等级？", summaryText(formal, item, grouped)));
    if (boundary) body.append(boundary);
    if (how) body.append(how);
    if (rawFormal) body.append(rawFormal);
    if (audit) body.append(audit);
    body.dataset.b1Public = "done";
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
