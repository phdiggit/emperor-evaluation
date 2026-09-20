"use strict";

(() => {
  const screen = document.getElementById("screen");
  if (!screen) return;

  const PUBLIC_GRADE = {G0:"E",G1:"D",G2:"C",G3:"B",G4:"A",G5:"S"};
  const PROFILE_KEYS = ["M_positive_profile", "M_mixed_profile", "M_negative_profile"];
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
    const url = typeof validatedRawUrl === "function" ? validatedRawUrl(path) : `../${path}?raw=1`;
    const response = await fetch(url, {cache:"no-cache"});
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

  function allProfiles(formal) {
    return PROFILE_KEYS.flatMap(key => formal?.[key] || [])
      .filter(profile => profile && typeof profile === "object");
  }

  function directionGroup(profile) {
    const tags = Array.isArray(profile?.adjudication_tags) ? profile.adjudication_tags : [];
    if (tags.includes("正向") && !tags.includes("正向主导")) return "positive";
    if (tags.includes("负向") && !tags.includes("负向主导")) return "negative";
    return "mixed";
  }

  function groupedProfiles(formal) {
    const groups = {positive:[], negative:[], mixed:[], boundary:[]};
    const profiles = allProfiles(formal);
    const byId = new Map(profiles.map(profile => [String(profile.profile_id), profile]));
    const supplements = new Map();
    for (const profile of profiles) {
      const status = profile.adjudication_status;
      if (status === "BOUNDARY_CONTEXT") {
        groups.boundary.push(profile);
      } else if (status === "ABSORBED_SAME_LIFECYCLE") {
        const target = byId.get(String(profile.absorbed_into_profile_id));
        if (target) {
          const targetId = String(target.profile_id);
          if (!supplements.has(targetId)) supplements.set(targetId, []);
          supplements.get(targetId).push(profile);
        }
      } else if (status === "ZERO_NET") {
        groups.mixed.push(profile);
      } else if (status === "COUNTED_INDEPENDENT") {
        groups[directionGroup(profile)].push(profile);
      }
    }
    return {groups, supplements};
  }

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function fmtWeight(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "—";
    const text = Number.isInteger(number) ? String(number) : number.toFixed(1).replace(/\.0$/, "");
    return number > 0 ? `+${text}` : text;
  }

  function contribution(profile) {
    switch (profile?.adjudication_status) {
      case "ABSORBED_SAME_LIFECYCLE": return "本项计入：并入同一运行链";
      case "BOUNDARY_CONTEXT": return "本项计入：不单独计入";
      case "ZERO_NET": return "本项计入：0（不增加净值）";
      default: return `本项计入：${fmtWeight(profile?.signed_weight)}`;
    }
  }

  function tagRow(tags) {
    const row = make("div", "second-item-b1-tags");
    for (const tag of tags || []) row.append(make("span", "second-item-b1-tag", tag));
    return row;
  }

  function boundaryBox(text) {
    if (!text) return null;
    const box = make("div", "second-item-b1-boundary");
    box.append(make("strong", "", "范围与边界"), make("p", "", text));
    return box;
  }

  function card(profile, {supplement = false} = {}) {
    const api = globalThis.SecondItemMaterialCards;
    if (api?.card) return api.card({
      title: profile?.public_label || "行政运行机制",
      direction: (profile?.adjudication_tags || []).find(tag => /^正向|^负向/.test(tag)) || "",
      tags: (profile?.adjudication_tags || []).filter(tag => !/^正向|^负向/.test(tag)),
      contribution: contribution(profile),
      body: profile?.adjudication_basis,
      boundary: profile?.adjudication_boundary,
      supplement,
      dataset: {b1ProfileId: profile?.profile_id || ""},
    });

    const li = make("li", supplement ? "second-item-b1-card second-item-b1-supplement" : "second-item-b1-card");
    li.append(make("strong", "", profile?.public_label || "行政运行机制"));
    if (profile?.adjudication_basis) li.append(make("p", "", profile.adjudication_basis));
    return li;
  }

  function group(title, items, supplements) {
    const section = make("section", "second-item-b1-group");
    section.append(make("h4", "", title));
    if (!items.length) {
      section.append(make("p", "second-item-b1-empty", "当前没有该类材料。"));
      return section;
    }
    const list = make("ul", "second-item-b1-list");
    for (const profile of items) {
      const item = card(profile);
      const nested = supplements.get(String(profile.profile_id)) || [];
      if (nested.length) {
        const box = make("div", "second-item-b1-supplements");
        box.append(make("div", "second-item-b1-supplements-title", "并入同一运行链的补充材料"));
        const nestedList = make("ul", "second-item-b1-nested-list");
        nestedList.replaceChildren(...nested.map(supplementProfile => card(supplementProfile, {supplement:true})));
        box.append(nestedList);
        item.append(box);
      }
      list.append(item);
    }
    section.append(list);
    return section;
  }

  function boundaryGroup(items) {
    if (!items.length) return null;
    const section = make("section", "second-item-b1-group second-item-b1-boundary-group");
    section.append(make("h4", "", "边界材料（不单独计入）"));
    const list = make("ul", "second-item-b1-list");
    list.replaceChildren(...items.map(profile => card(profile)));
    section.append(list);
    return section;
  }

  function summaryText(formal, item) {
    const summary = String(formal?.public_adjudication_summary || "").trim();
    const grade = publicGrade(item);
    if (!summary) return grade ? `官僚治理的正式公开等级为 ${grade}。` : "";
    return `${summary}${grade ? `综合这些正式裁决，官僚治理的公开等级为 ${grade}。` : ""}`;
  }
  function genericBodyKey(item) {
    return [
      item?.reader_summary || "",
      ...(Array.isArray(item?.reader_highlights) ? item.reader_highlights : []),
      item?.reader_boundary || "",
      item?.reader_how || "",
      item?.reader_full_basis || "",
    ].join("|");
  }

  function appendDedicatedAudit(body, item, record) {
    const api = globalThis.SecondItemMaterialCards;
    const details = make("details", "second-item-dedicated-audit");
    details.append(make("summary", "", "原始记录与计算口径"));
    const how = api?.publicEnumText ? api.publicEnumText(item?.reader_how || "") : String(item?.reader_how || "").trim();
    if (how) details.append(make("p", "prose", how));
    const refs = [...new Set([item?.source, item?.applied_source, ...(item?.reader_source_refs || [])].filter(Boolean))];
    if (refs.length && typeof link === "function") {
      const holder = make("p", "sources");
      holder.innerHTML = refs.map((ref, i) => link(ref, i ? "补充正式记录 ↗" : "正式记录 ↗", record)).join("");
      details.append(holder);
    }
    body.append(details);
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
      .second-item-b1-list,.second-item-b1-nested-list{list-style:none;margin:0;padding:0;display:grid;gap:8px}
      .second-item-b1-card{margin:0;padding:10px 12px;border:1px solid var(--line);border-radius:5px;background:#fff}
      .second-item-b1-head{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
      .second-item-b1-head strong{font-size:14px}
      .second-item-b1-tags{display:flex;gap:5px;flex-wrap:wrap;align-items:center}
      .second-item-b1-tag{display:inline-block;padding:1px 6px;border:1px solid var(--line);border-radius:999px;font-size:10px;line-height:1.6;color:var(--green);font-weight:700;background:#f4f5ef}
      .second-item-b1-impact{display:inline-block;margin-left:auto;padding:1px 7px;border-radius:999px;background:#ecefe6;color:var(--ink);font-size:10px;font-weight:700;white-space:nowrap}
      .second-item-b1-basis{margin:6px 0 0;font-size:12px;line-height:1.72}
      .second-item-b1-boundary{margin-top:7px;padding:7px 9px;background:rgba(0,0,0,.025);font-size:11px;line-height:1.65}
      .second-item-b1-boundary strong{font-size:11px;color:var(--muted)}
      .second-item-b1-boundary p{margin:2px 0 0}
      .second-item-b1-supplements{margin-top:9px;padding-top:8px;border-top:1px dashed var(--line)}
      .second-item-b1-supplements-title{margin-bottom:6px;font-size:11px;color:var(--muted);font-weight:700}
      .second-item-b1-supplement{background:#f7f5ef}
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
    if (!item || !body || body.dataset.b1Public === "done" || body.dataset.b1Public === "loading") return;

    body.dataset.b1Public = "loading";
    const formal = await formalB1(record, item);
    if (!formal || !body.isConnected || currentRecord()?.ruler_id !== record.ruler_id) {
      if (body.isConnected) delete body.dataset.b1Public;
      return;
    }
    if (formal.profile_adjudication_style !== "B1-PROFILE-ADJUDICATION-V2") {
      delete body.dataset.b1Public;
      return;
    }
    const {groups, supplements} = groupedProfiles(formal);

    body.innerHTML = "";
    const reading = make("div", "second-item-public-reading second-item-b1-reading");
    reading.append(make("div", "label", "官僚治理运行链"));
    reading.append(make("p", "second-item-b1-intro", "每条材料直接读取正式名称、公开标签、本项计入方式与对应裁决；并入材料嵌套在明确的主运行链下。"));
    reading.append(make("div", "second-item-b1-summary", summaryText(formal, item)));
    reading.append(group("正向行政运行", groups.positive, supplements));
    reading.append(group("负向行政失灵", groups.negative, supplements));
    reading.append(group("正负并存的行政机制", groups.mixed, supplements));
    const boundarySection = boundaryGroup(groups.boundary);
    if (boundarySection) reading.append(boundarySection);
    body.append(reading);

    const gradeDetails = make("details", "", "");
    gradeDetails.append(make("summary", "", "为什么最终是这个等级？"));
    gradeDetails.append(make("p", "prose", summaryText(formal, item)));
    body.append(gradeDetails);
    appendDedicatedAudit(body, item, record);

    body.dataset.secondPublicBodyKey = genericBodyKey(item);
    body.dataset.secondPublicOwner = "B1";
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
