"use strict";

(() => {
  const screen = document.getElementById("screen");
  if (!screen) return;

  const formalCache = new Map();
  const registryCache = new Map();
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
    if (formalCache.has(key)) return formalCache.get(key);
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
      console.error("Failed to load institution scope data", error);
      return null;
    });
    formalCache.set(key, pending);
    return pending;
  }

  function nodeKey(node) {
    return node?.institution_node_id || `${node?.label_zh || node?.mechanism || ""}\u0000${node?.direction || node?.normative_direction || ""}`;
  }

  function nonEmpty(...values) {
    for (const value of values) {
      if (typeof value === "string" && value.trim()) return value.trim();
    }
    return "";
  }

  function mergeNode(important, profile) {
    const merged = {...(important || {}), ...(profile || {})};
    for (const key of ["label_zh", "mechanism", "institution_domain", "institution_lineage", "major_node_role", "reason", "source_artifact_refs"]) {
      const current = merged[key];
      const empty = Array.isArray(current) ? !current.length : !nonEmpty(current);
      if (empty && important?.[key]) merged[key] = important[key];
    }
    return merged;
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
      result.push(mergeNode(important.get(key) || null, profile));
    };
    for (const node of formal?.M_positive_profile || []) add(node);
    for (const node of formal?.M_negative_profile || []) add(node);
    for (const node of formal?.M_mixed_profile || []) add(node);
    for (const node of important.values()) if (!seen.has(nodeKey(node))) add(node);
    return result;
  }

  function numberValue(value) {
    if (value == null || value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function fmt(value) {
    const number = numberValue(value);
    if (number == null) return "";
    const text = Number.isInteger(number) ? String(number) : number.toFixed(1).replace(/\.0$/, "");
    return number > 0 ? `+${text}` : text;
  }

  function contributionText(node) {
    const weight = numberValue(node?.signed_weight);
    if (weight == null) return "本项计入：结构性依据";
    if (weight === 0) return "本项计入：0（不增加净值）";
    return `本项计入：${fmt(weight)}`;
  }

  function registryPaths(node) {
    return [...new Set((node?.source_artifact_refs || [])
      .filter(ref => typeof ref === "string")
      .map(sourcePath)
      .filter(path => /\/01-制度行政计分材料登记\/[^/]+\.json$/.test(path))
    )];
  }

  async function registryRows(path) {
    if (registryCache.has(path)) return registryCache.get(path);
    const pending = repoJson(path).then(rows).catch(error => {
      console.error("Failed to load institution material registry", error);
      return [];
    });
    registryCache.set(path, pending);
    return pending;
  }

  function materialIds(node) {
    return [...new Set([
      ...(node?.construction_operation_material_ids || []),
      ...(node?.material_ids || []),
    ].filter(value => typeof value === "string" && value))];
  }

  async function materialForNode(node) {
    const ids = new Set(materialIds(node));
    if (!ids.size) return null;
    for (const path of registryPaths(node)) {
      const materials = await registryRows(path);
      const material = materials.find(row => ids.has(row?.material_id));
      if (material) return material;
    }
    return null;
  }

  function cardForNode(reading, node) {
    if (node?.institution_node_id) {
      const found = Array.from(reading.querySelectorAll(".second-item-institution-list > li"))
        .find(card => card.dataset.institutionNodeId === node.institution_node_id);
      if (found) return found;
    }
    const key = nodeKey(node);
    return Array.from(reading.querySelectorAll(".second-item-institution-list > li"))
      .find(card => card.dataset.institutionKey === key) || null;
  }

  function normalizeText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function appendScope(card, material) {
    if (!card || !material || card.querySelector(":scope > .second-item-institution-scope")) return;
    const measure = normalizeText(material.measure || material.operation || "");
    const boundary = normalizeText(material.cost_or_capture || "");
    if (!measure && !boundary) return;
    const box = document.createElement("div");
    box.className = "second-item-institution-scope";
    if (measure) {
      const p = document.createElement("p");
      p.textContent = `具体范围：${measure}`;
      box.append(p);
    }
    if (boundary) {
      const p = document.createElement("p");
      p.textContent = `边界：${boundary}`;
      box.append(p);
    }
    const reception = card.querySelector(":scope > .second-item-institution-reception");
    if (reception) reception.before(box);
    else card.append(box);
  }

  function ensureStyles() {
    if (document.getElementById("second-item-institution-scope-style")) return;
    const style = document.createElement("style");
    style.id = "second-item-institution-scope-style";
    style.textContent = `
      .second-item-institution-scope{margin-top:6px;padding:7px 9px;background:rgba(0,0,0,.025);font-size:11px;line-height:1.65}
      .second-item-institution-scope p{margin:0}
      .second-item-institution-scope p+p{margin-top:3px}
    `;
    document.head.append(style);
  }

  async function patch() {
    ensureStyles();
    const record = currentRecord();
    if (!record) return;
    const item = methodItem(record);
    const detail = Array.from(document.querySelectorAll(".net-metric-detail[data-second-source-label]"))
      .find(node => node.dataset.secondSourceLabel === "A制度建设");
    const reading = detail?.querySelector(":scope > .net-metric-body > .second-item-institution-reading");
    if (!item || !reading || reading.dataset.scopeReading === "done") return;
    if (reading.dataset.publicCleanup !== "done") return;

    const formal = await formalA(record, item);
    if (!formal || !reading.isConnected || currentRecord()?.ruler_id !== record.ruler_id) return;
    const nodes = formalNodes(formal);

    for (const node of nodes) {
      const card = cardForNode(reading, node);
      if (!card) continue;
      const impact = card.querySelector(".second-item-institution-impact");
      if (impact) impact.textContent = contributionText(node);

      const note = card.querySelector(":scope > .second-item-institution-note");
      if (!note || normalizeText(note.textContent).length < 18) {
        const material = await materialForNode(node);
        appendScope(card, material);
      }
    }

    const intro = reading.querySelector(".second-item-institution-intro");
    if (intro) intro.textContent = "按正向、负向和正负并存分类阅读。每项制度标明在本项结算中的计入权重；重大制度另标类型和后世接收。";
    reading.dataset.scopeReading = "done";
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
