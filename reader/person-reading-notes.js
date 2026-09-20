"use strict";

(() => {
  const schema = "reader-person-overviews-v2";
  const overviewKeys = ["outcome", "profile", "impact"];
  const labels = {
    outcome: "统治记录摘要", profile: "人物经历摘要", impact: "历史变化摘要",
  };
  const own = (object, key) => object != null && Object.prototype.hasOwnProperty.call(object, key);
  const plain = value => value && typeof value === "object" && !Array.isArray(value);
  const text = value => typeof value === "string" && value.trim().length > 0;
  const forbidden = /\b(?:M[1245]|C[1-5]|G[0-5]|MI[0-4]|PS[0-4]|DW[0-4]|AM[1-4])(?:[_-][A-Z_]+)?\b|<|>/;
  const unsafeKeys = new Set(["__proto__", "prototype", "constructor"]);

  function resolve(record, path) {
    let value = record;
    for (const key of path) {
      if (unsafeKeys.has(key) || !own(value, key)) return undefined;
      value = value[key];
    }
    return value;
  }

  function validPath(path) {
    if (!Array.isArray(path) || path.length < 2) return false;
    if (!path.every(key => (typeof key === "string" && key && !unsafeKeys.has(key)) ||
        (Number.isInteger(key) && key >= 0))) return false;
    // Notes may refer to factual prose, not scores or an independently stored summary.
    if (path.some(key => /^(?:.*grade.*|.*score.*|rank|position|radar_value|reader_governance_summary)$/.test(String(key)))) return false;
    return path[0] === "impact" ||
      (path[0] === "axes" && path.length >= 3 && /^(?:M[1245]|C[1-5])$/.test(path[1])) ||
      (path[0] === "net" && path[1] === "component_details" && path.length >= 5);
  }

  const exactKeys = (value, keys) => plain(value) && Object.keys(value).length === keys.length && keys.every(key => own(value, key));

  function validateBlock(block) {
    if (!exactKeys(block, ["text", "evidence"]) || !text(block.text) || forbidden.test(block.text)) throw Error("Invalid reading-note prose");
    if (!Array.isArray(block.evidence) || !block.evidence.length) throw Error("Reading note needs evidence");
    for (const ref of block.evidence) {
      if (!exactKeys(ref, ["path", "quote"]) || !validPath(ref.path) || !text(ref.quote)) throw Error("Invalid reading-note locator");
    }
  }

  function validateNotes(payload) {
    if (!exactKeys(payload, ["schema_id", "records"]) || payload.schema_id !== schema || !plain(payload.records)) throw Error("Invalid reading-note schema");
    for (const [id, notes] of Object.entries(payload.records)) {
      if (!id.startsWith("RULER-") || /[\/\\]/.test(id) || !plain(notes)) throw Error("Invalid reading-note identity");
      // Editorial freedom is limited to the three overview summaries. Decisions,
      // strength, counterevidence and boundaries belong to the formal records.
      if (!exactKeys(notes, ["overview"])) throw Error("Only overview summaries are allowed");
      if (!exactKeys(notes.overview, overviewKeys)) throw Error("Reading note needs three overview sections");
      for (const block of Object.values(notes.overview)) validateBlock(block);
    }
    return payload;
  }

  function assessBlock(block, record) {
    const missing = block.evidence.filter(ref => {
      const value = resolve(record, ref.path);
      return typeof value !== "string" || !value.includes(ref.quote);
    });
    return {status: missing.length ? "needs_review" : "current", missing};
  }

  // Shared deterministic logic is also exercised with synthetic records in Node.
  if (typeof module !== "undefined" && module.exports) {
    module.exports = {validateNotes, validateBlock, validPath, resolve, assessBlock};
    return;
  }

  const root = document.getElementById("screen");
  if (!root) return;
  let payload = null, loading = null, failed = false, queued = false;
  const el = (tag, className, value) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (value !== undefined) node.textContent = value;
    return node;
  };

  function addStyles() {
    if (document.getElementById("person-reading-notes-style")) return;
    const style = el("style");
    style.id = "person-reading-notes-style";
    style.textContent = `
      .person-reading-note{margin:12px 0 16px;padding:10px 12px;border-left:2px solid var(--line);background:var(--paper)}
      .person-reading-note h3{font-size:14px;margin:0 0 6px}
      .person-reading-note p{font-size:14px;line-height:1.85;margin:6px 0;overflow-wrap:anywhere}
      .note-evidence{font-size:12px;padding:5px 0;margin-top:8px}
      .note-evidence summary{font-size:12px;color:var(--muted)}
      .note-evidence li{white-space:normal;overflow-wrap:anywhere;margin:8px 0}
      .note-evidence q{display:block;margin-top:4px;color:var(--muted)}
      .note-provenance,.reading-note-pending{color:var(--muted);font-size:13px}
    `;
    document.head.append(style);
  }

  function sourceFor(record, path) {
    if (path[0] === "axes") {
      const spec = DATA.axis_specs[path[1]];
      return spec ? {path: spec.json, label: `${spec.name}正式记录`} : null;
    }
    if (path[0] === "impact") return {path: DATA.sources.impact, label: "历史影响正式记录"};
    const item = record.net?.component_details?.[path[2]]?.[path[3]];
    return item?.source ? {path: item.source, label: "统治绩效相关正式记录"} : null;
  }

  function evidenceList(block, record) {
    const fold = el("details", "note-evidence");
    fold.append(el("summary", "", "原始记录：这段提要依据什么？"));
    fold.append(el("p", "note-provenance", "以下是项目现有记录中的定位语句；史料出处和完整说明见相应记录。"));
    const list = el("ul");
    for (const ref of block.evidence) {
      const item = el("li"), source = sourceFor(record, ref.path);
      if (source) {
        const holder = el("span");
        // Reuse the established source router; it supplies local availability and person parameters.
        holder.innerHTML = link(source.path.split("#")[0] + "#ruler_id=" + record.ruler_id, source.label + " ↗", record);
        item.append(holder);
      }
      item.append(el("q", "", ref.quote));
      list.append(item);
    }
    fold.append(list);
    return fold;
  }

  function pendingNote() {
    return el("p", "reading-note-pending", "这段阅读提要待复核；以下正式记录仍可查阅。这不是人物裁决状态的变化。");
  }

  function renderBlock(key, block, record, className) {
    const section = el("section", className);
    section.append(el("h3", "", labels[key]));
    if (assessBlock(block, record).status !== "current") section.append(pendingNote());
    else section.append(el("p", "note-text", block.text), evidenceList(block, record));
    return section;
  }

  function applyOverview(record, notes) {
    for (const [key, id] of [["outcome", "person-outcome"], ["profile", "person-capability"], ["impact", "person-impact"]]) {
      const panel = document.getElementById(id);
      if (!panel || panel.querySelector(":scope > .person-reading-note")) continue;
      panel.querySelector(":scope > h2")?.after(renderBlock(key, notes.overview[key], record, "person-reading-note"));
    }
  }

  function subjects() {
    // Comparisons use the formal evidence directly; they need no editorial file.
    if (!location.hash.startsWith("#person/")) return [];
    const record = byId.get(personId());
    return record && record.detail_loaded ? [record] : [];
  }

  function enhance() {
    queued = false;
    const active = subjects();
    if (!active.length) return; // Home and comparison views do not fetch overview summaries.
    if (!payload) {
      if (failed) {
        if (!root.querySelector(".notes-load-notice")) root.prepend(el("p", "notes-load-notice reading-note-pending", "阅读提要暂未加载，现有正式记录仍可阅读。刷新页面可重试。"));
      } else if (!loading) {
        loading = fetch("data/person-reading-notes.json", {cache: "no-cache"})
          .then(response => { if (!response.ok) throw Error("Reading notes unavailable"); return response.json(); })
          .then(validateNotes)
          .then(value => { payload = value; schedule(); })
          .catch(() => { failed = true; schedule(); });
      }
      return;
    }
    addStyles();
    for (const record of active) {
      const notes = payload.records[record.ruler_id];
      if (!notes) continue; // No invented fallback paragraph for people not yet editorially reviewed.
      applyOverview(record, notes);
    }
  }

  function schedule() {
    if (!queued) { queued = true; requestAnimationFrame(enhance); }
  }
  new MutationObserver(schedule).observe(root, {childList: true, subtree: true});
  window.addEventListener("hashchange", schedule);
  schedule();
})();
