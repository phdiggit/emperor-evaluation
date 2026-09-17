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
      console.error("Failed to load B1 adjudication data", error);
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
    return profile?.grade_independence_lifecycle_key || profile?.lifecycle_group_key || profile?.lifecycle_key || profile?.profile_id || profile?.material_id || "";
  }

  function allProfiles(formal) {
    return [
      ...(formal?.M_positive_profile || []),
      ...(formal?.M_mixed_profile || []),
      ...(formal?.M_negative_profile || []),
    ].filter(profile => profile && typeof profile === "object");
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

  function mechanism(value) {
    return String(value || "")
      .replace(/`/g, "")
      .replace(/^B1[-_/]?(?:central|distributed|personnel)?/i, "")
      .replace(/(?:core|support)\s*$/gi, "")
      .replace(/\b(?:core|support|central|distributed|context)\b/gi, "")
      .replace(/\bM[0-3]\b/gi, "")
      .replace(/\s+/g, " ")
      .replace(/^[：:、，；\s]+|[：:、，；\s]+$/g, "")
      .trim() || "行政运行机制";
  }

  function make(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  function tagRow(tags) {
    const row = make("div", "second-item-b1-adjudication-tags");
    for (const tag of tags || []) row.append(make("span", "second-item-b1-adjudication-tag", tag));
    return row;
  }

  function addBoundary(card, text) {
    card.querySelector(":scope > .second-item-b1-adjudication-boundary")?.remove();
    if (!text) return;
    const box = make("div", "second-item-b1-adjudication-boundary");
    box.append(make("strong", "", "范围与边界"), make("p", "", text));
    card.append(box);
  }

  function primaryCard(reading, profile) {
    if (profile?.profile_id) {
      const found = reading.querySelector(`.second-item-b1-card[data-b1-profile-id="${CSS.escape(profile.profile_id)}"]`);
      if (found) return found;
    }
    const key = profileKey(profile);
    return Array.from(reading.querySelectorAll(".second-item-b1-card")).find(card => card.dataset.b1LifecycleKey === key) || null;
  }

  function patchPrimaryCard(reading, profile) {
    const card = primaryCard(reading, profile);
    if (!card) return null;
    const head = card.querySelector(":scope > .second-item-b1-head");
    if (head) {
      head.querySelectorAll(".second-item-b1-role,.second-item-b1-direction").forEach(node => node.remove());
      const impact = head.querySelector(".second-item-b1-impact");
      if (impact) impact.textContent = contribution(profile);
      const tags = tagRow(profile.adjudication_tags || []);
      head.prepend(tags);
    }
    let note = card.querySelector(":scope > .second-item-b1-note");
    const basis = String(profile?.adjudication_basis || "").trim();
    if (basis) {
      if (!note) {
        note = make("p", "second-item-b1-note");
        card.append(note);
      }
      note.textContent = basis;
    } else {
      note?.remove();
    }
    card.querySelector(":scope > .second-item-b1-merged")?.remove();
    addBoundary(card, String(profile?.adjudication_boundary || "").trim());
    return card;
  }

  function supplementCard(profile) {
    const card = make("div", "second-item-b1-supplement-card");
    const head = make("div", "second-item-b1-supplement-head");
    head.append(make("strong", "", mechanism(profile?.mechanism || profile?.material_id)));
    head.append(make("span", "second-item-b1-impact", contribution(profile)));
    card.append(head, tagRow(profile?.adjudication_tags || []));
    if (profile?.adjudication_basis) card.append(make("p", "second-item-b1-note", profile.adjudication_basis));
    if (profile?.adjudication_boundary) addBoundary(card, profile.adjudication_boundary);
    return card;
  }

  function appendSupplements(reading, formal) {
    reading.querySelectorAll(".second-item-b1-supplements").forEach(node => node.remove());
    const primaries = new Map();
    for (const profile of allProfiles(formal)) {
      if (profile?.adjudication_status === "COUNTED_INDEPENDENT" || profile?.adjudication_status === "ZERO_NET") {
        primaries.set(profileKey(profile), profile);
      }
    }
    for (const profile of allProfiles(formal)) {
      if (profile?.adjudication_status !== "ABSORBED_SAME_LIFECYCLE") continue;
      const target = String(profile?.absorbed_into_lifecycle_key || profileKey(profile));
      const primary = primaries.get(target) || allProfiles(formal).find(item => profileKey(item) === target);
      const card = primary ? primaryCard(reading, primary) : null;
      if (!card) continue;
      let box = card.querySelector(":scope > .second-item-b1-supplements");
      if (!box) {
        box = make("div", "second-item-b1-supplements");
        box.append(make("div", "second-item-b1-supplements-title", "并入同一运行链的补充材料"));
        card.append(box);
      }
      box.append(supplementCard(profile));
    }
  }

  function appendContextSection(reading, formal) {
    reading.querySelector(":scope > .second-item-b1-context-group")?.remove();
    const profiles = allProfiles(formal).filter(profile => profile?.adjudication_status === "BOUNDARY_CONTEXT");
    if (!profiles.length) return;
    const section = make("section", "second-item-b1-group second-item-b1-context-group");
    section.append(make("h4", "", "边界材料（不单独计入）"));
    const list = make("div", "second-item-b1-context-list");
    list.replaceChildren(...profiles.map(supplementCard));
    section.append(list);
    reading.append(section);
  }

  function finalSummary(formal, item) {
    const summary = String(formal?.public_adjudication_summary || "").trim();
    const grade = publicGrade(item);
    if (!summary) return grade ? `官僚治理的正式公开等级为 ${grade}。` : "";
    return `${summary}${grade ? `综合这些正式裁决，官僚治理的公开等级为 ${grade}。` : ""}`;
  }

  function ensureStyles() {
    if (document.getElementById("second-item-b1-adjudication-style")) return;
    const style = document.createElement("style");
    style.id = "second-item-b1-adjudication-style";
    style.textContent = `
      .second-item-b1-adjudication-tags{display:flex;gap:5px;flex-wrap:wrap;align-items:center}
      .second-item-b1-adjudication-tag{display:inline-block;padding:1px 6px;border:1px solid var(--line);border-radius:999px;font-size:10px;line-height:1.6;color:var(--green);font-weight:700;background:#f4f5ef}
      .second-item-b1-adjudication-boundary{margin-top:7px;padding:7px 9px;background:rgba(0,0,0,.025);font-size:11px;line-height:1.65}
      .second-item-b1-adjudication-boundary strong{font-size:11px;color:var(--muted)}
      .second-item-b1-adjudication-boundary p{margin:2px 0 0}
      .second-item-b1-supplements{margin-top:9px;padding-top:8px;border-top:1px dashed var(--line)}
      .second-item-b1-supplements-title{margin-bottom:6px;font-size:11px;color:var(--muted);font-weight:700}
      .second-item-b1-supplement-card{margin-top:6px;padding:7px 9px;background:#f7f5ef;border-radius:4px}
      .second-item-b1-supplement-head{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
      .second-item-b1-supplement-head strong{font-size:12px}
      .second-item-b1-context-list{display:grid;gap:8px}
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
    const reading = body?.querySelector(":scope > .second-item-b1-reading");
    if (!item || !body || !reading || body.dataset.b1Adjudication === "done") return;
    if (body.dataset.b1Public !== "done") return;

    const formal = await formalB1(record, item);
    if (!formal || !reading.isConnected || currentRecord()?.ruler_id !== record.ruler_id) return;
    if (formal.profile_adjudication_style !== "B1-PROFILE-ADJUDICATION-V1") return;

    for (const profile of allProfiles(formal)) {
      if (profile?.adjudication_status === "COUNTED_INDEPENDENT" || profile?.adjudication_status === "ZERO_NET") {
        patchPrimaryCard(reading, profile);
      }
    }
    appendSupplements(reading, formal);
    appendContextSection(reading, formal);

    const intro = reading.querySelector(":scope > .second-item-b1-intro");
    if (intro) intro.textContent = "每条计分材料直接显示正式标签、本项计入和对应裁决；同一运行链的补充材料标为并入，边界材料单独列出。";
    const text = finalSummary(formal, item);
    const summary = reading.querySelector(":scope > .second-item-b1-summary");
    if (summary && text) summary.textContent = text;

    const gradeDetails = Array.from(body.querySelectorAll(":scope > details")).find(node =>
      node.querySelector(":scope > summary")?.textContent.trim() === "为什么最终是这个等级？"
    );
    const prose = gradeDetails?.querySelector(":scope > .prose, :scope > p");
    if (prose && text) prose.textContent = text;

    body.querySelector(":scope > .net-formal-basis-raw")?.remove();
    body.dataset.b1Adjudication = "done";
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
