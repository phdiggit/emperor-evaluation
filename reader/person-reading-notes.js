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
  const forbidden = /\b(?:M[1245]|C[1-5]|G[0-5]|MI[0-4]|PS[0-4]|DW[0-4]|AM[1-4])(?:[_-][A-Z_]+)?\b|(?:正式记录|回填|倒灌|闭合|整改|本项|该项|项目同时|现有裁决|正式裁决|现有结算|正式画像|提前计入|取证|复验|正式评价|评价依据|归责)|<|>/;
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
    if (Array.isArray(path) && path.length === 1 && path[0] === "settlement_readiness") return true;
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
      if (!/^(?:RULER|HIMPACT)-[^/\\]+$/.test(id) || !plain(notes)) throw Error("Invalid reading-note identity");
      // System overviews and the missing third-item conclusion share this
      // editorial source. Numeric decisions remain in the formal records.
      if (!own(notes, 'overview') || Object.keys(notes).some(key => !['overview','net','reading','profile_grade_reasons'].includes(key))) throw Error("Invalid reading-note sections");
      if (own(notes, 'profile_grade_reasons')) {
        if (id.startsWith('HIMPACT-') || !plain(notes.profile_grade_reasons)) throw Error('Invalid profile grade reasons');
        for (const [axis, reason] of Object.entries(notes.profile_grade_reasons)) {
          if (!/^(?:C[1-5]|M[1245])$/.test(axis) || !exactKeys(reason, ['source', 'text']) || !text(reason.source) || !text(reason.text) || forbidden.test(reason.text)) throw Error('Invalid profile grade reason');
        }
      }
      if (notes.reading) {
        if (!plain(notes.reading) || id.startsWith('HIMPACT-')) throw Error('Invalid narrative owner');
        for (const [system, chapters] of Object.entries(notes.reading)) {
          if (!['profile','impact','second','third','fourth'].includes(system) || !Array.isArray(chapters) || !chapters.length) throw Error('Invalid narrative section');
          for (const chapter of chapters) {
            if (!exactKeys(chapter,['title','text','evidence']) || !text(chapter.title)) throw Error('Invalid narrative chapter');
            validateBlock({text:chapter.text,evidence:chapter.evidence});
            const groups={second:['method','finance','handoff'],third:['strategic','military'],fourth:['civilization']};
            if (chapter.evidence.some(ref=>system==='profile'?ref.path[0]!=='axes':system==='impact'?ref.path[0]!=='impact':ref.path[0]!=='net'||ref.path[1]!=='component_details'||!groups[system].includes(ref.path[2]))) throw Error('Narrative evidence belongs to another system');
          }
        }
      }
      if (notes.net) {
        if (id.startsWith("HIMPACT-") || (!exactKeys(notes.net, ["third"]) && !exactKeys(notes.net, ["third", "fourth"]))) throw Error("Invalid net conclusion");
        for (const block of Object.values(notes.net)) validateBlock(block);
        if (notes.net.third.evidence.some(ref => ref.path[0] !== "net" || ref.path.some(key => key === "reader_public_third_c"))) throw Error("Military overview needs current strategic and cost evidence");
        if (notes.net.fourth?.evidence.some(ref => ref.path[0] !== "net" || ref.path[1] !== "component_details" || ref.path[2] !== "civilization")) throw Error("Civilization conclusion needs its own outcome evidence");
      }
      const impactOnly = exactKeys(notes.overview, ["impact"]);
      if (!impactOnly && (id.startsWith("HIMPACT-") || !exactKeys(notes.overview, overviewKeys))) {
        throw Error("Reading note needs three overview sections or an impact-only overview");
      }
      for (const block of Object.values(notes.overview)) validateBlock(block);
      if (impactOnly && notes.overview.impact.evidence.some(ref => ref.path[0] !== "impact")) {
        throw Error("Impact-only reading note needs historical impact evidence");
      }
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
    module.exports = {validateNotes, validateBlock, validPath, resolve, assessBlock, sourceFor};
    return;
  }

  const root = document.getElementById("screen");
  if (!root) return;
  let payload = null, loading = null, failed = false, queued = false, versionMismatch = false;
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
    const id = encodeURIComponent(record.ruler_id);
    if (path[0] === "settlement_readiness") {
      return {href: `#net/${id}/all`, label: "查看本人结算状态"};
    }
    if (path[0] === "axes") {
      return {href: `#person/${id}/profile/${path[1]}`, label: "查看本轴依据"};
    }
    if (path[0] === "impact") {
      const focus = {
        scope_assessment: "history-dimension-scope",
        depth_review: "history-dimension-depth_duration",
        causal_review: "history-dimension-personal_causality",
        paradigm_review: "history-dimension-paradigm",
        public_boundary: "history-judgment-boundary",
      }[path[1]] || "history-evidence";
      return {href: `#person/${id}/impact/${focus}`, label: "查看本人历史影响依据"};
    }
    const group = path[2];
    const section = {
      first: "first", method: "second/method", finance: "second/finance", handoff: "second/handoff",
      strategic: "third/strategic", military: "third/military", civilization: "fourth",
    }[group] || "all";
    return {href: `#net/${id}/${section}`, label: "查看本人统治绩效依据"};
  }

  function evidenceList(block, record) {
    const fold = el("details", "note-evidence");
    fold.append(el("summary", "", "进一步核对：这段提要依据什么？"));
    fold.append(el("p", "note-provenance", "以下列出本段提要对应的定位语句；史料出处和完整说明见相应记录。"));
    const list = el("ul");
    for (const ref of block.evidence) {
      const item = el("li"), source = sourceFor(record, ref.path);
      if (source.href) {
        const anchor = el("a", "", source.label + " →");
        anchor.href = source.href;
        if (ref.path[0] === "impact") {
          anchor.addEventListener("click", () => {
            if (location.hash === source.href) focusImpactSection();
          });
        }
        item.append(anchor);
      }
      if (ref.path[0] === "settlement_readiness") {
        item.append(el("span", "note-provenance", missingNetStatus(record)));
      } else {
        item.append(el("q", "", ref.quote));
      }
      list.append(item);
    }
    fold.append(list);
    return fold;
  }

  function renderBlock(key, block, record, className) {
    const heading = record.reader_narratives ? {outcome:'他治下的人过得怎样？',profile:'他怎样作决定和用人？',impact:'他留下了什么？'}[key] : labels[key];
    if (assessBlock(block, record).status !== "current") {
      const notice = el("section", className);
      notice.append(el("h3", "", heading), el("p", "subline", "这段摘要的依据已更新，正在等待复核；请继续阅读下方的当前评价与逐项依据。"));
      return notice;
    }
    const section = el("section", className);
    section.append(el("h3", "", heading));
    section.append(el("p", "note-text", block.text), evidenceList(block, record));
    return section;
  }

  function applyOverview(record, notes) {
    if (personView() && record.reader_narratives?.[personView()]) return;
    for (const [key, id] of [["outcome", "person-outcome"], ["profile", "person-capability"], ["impact", "person-impact"]]) {
      const panel = document.getElementById(id);
      if (!panel || !notes.overview[key] || panel.querySelector(":scope > .person-reading-note")) continue;
      const block = renderBlock(key, notes.overview[key], record, "person-reading-note");
      if (block) {
        const anchor = panel.querySelector(":scope > [data-reading-note-anchor]") || panel.querySelector(":scope > h2");
        anchor?.after(block);
      }
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
        if (versionMismatch && !root.querySelector('[data-notes-version-notice]')) {
          const notice = el('p', 'notice', '阅读摘要已更新，请刷新页面后继续；当前页面保留原有评价。');
          notice.dataset.notesVersionNotice = '';
          root.prepend(notice);
        }
        return;
      } else if (!loading) {
        loading = fetch("data/person-reading-notes.json", {cache: "no-cache"})
          .then(response => { if (!response.ok) throw Error("Reading notes unavailable"); return response.text(); })
          .then(value => requireReaderTextVersion(value, DATA.notes_version))
          .then(JSON.parse)
          .then(validateNotes)
          .then(value => { payload = value; schedule(); })
          .catch(error => {
            failed = true;
            versionMismatch = Boolean(error.readerVersionMismatch);
            schedule();
          });
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
  globalThis.PersonReadingNotes = Object.freeze({enhance});
})();
