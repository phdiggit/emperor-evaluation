"use strict";

(() => {
  const basePerson = person;
  const baseCompare = compare;
  const baseHome = home;
  const baseGuide = guide;
  const pendingLoads = new Map();
  let renderGeneration = 0;

  function loading(message) {
    screen.innerHTML = `<div class="empty" role="status">${esc(message)}</div>`;
  }

  function loadFailure(error) {
    console.error(error);
    screen.innerHTML = `<div class="empty"><p>完整资料加载失败。</p><p class="subline">请检查网络后重试；人物总览仍可正常使用。</p><button data-home>返回人物总览</button></div>`;
  }

  async function loadRecord(record) {
    if (!record || record.detail_loaded) return record;
    const id = record.ruler_id;
    if (pendingLoads.has(id)) return pendingLoads.get(id);
    if (!record.detail_ref) throw new Error(`Missing detail_ref for ${id}`);

    const request = (async () => {
      const response = await fetch(record.detail_ref, {cache: "no-cache"});
      if (!response.ok) throw new Error(`Failed to load ${record.detail_ref}: HTTP ${response.status}`);
      const payload = await response.json();
      if (!payload || !payload.record || payload.record.ruler_id !== id) {
        throw new Error(`Detail payload ruler_id mismatch for ${id}`);
      }
      const full = {
        ...payload.record,
        detail_ref: record.detail_ref,
        detail_loaded: true,
      };
      byId.set(id, full);
      Object.assign(DATA.source_availability, payload.source_availability || {});
      return full;
    })().finally(() => pendingLoads.delete(id));

    pendingLoads.set(id, request);
    return request;
  }

  person = function(record) {
    if (!record || record.detail_loaded) {
      renderGeneration += 1;
      return basePerson(record);
    }

    const generation = ++renderGeneration;
    nav("");
    loading(`正在加载${record.ruler_name}的完整资料…`);
    loadRecord(record).then(full => {
      if (generation !== renderGeneration || personId() !== full.ruler_id) return;
      basePerson(full);
    }).catch(error => {
      if (generation === renderGeneration) loadFailure(error);
    });
  };

  compare = function() {
    if (state.compare.length < 2) {
      renderGeneration += 1;
      return baseCompare();
    }

    const selected = state.compare.map(id => byId.get(id));
    if (selected.some(record => !record)) {
      renderGeneration += 1;
      return baseCompare();
    }
    if (selected.every(record => record.detail_loaded)) {
      renderGeneration += 1;
      return baseCompare();
    }

    const generation = ++renderGeneration;
    nav("compare");
    loading("正在加载两位人物的完整对照资料…");
    Promise.all(selected.map(loadRecord)).then(() => {
      if (generation !== renderGeneration || !location.hash.startsWith("#compare")) return;
      baseCompare();
    }).catch(error => {
      if (generation === renderGeneration) loadFailure(error);
    });
  };

  home = function() {
    renderGeneration += 1;
    return baseHome();
  };

  guide = function() {
    renderGeneration += 1;
    return baseGuide();
  };

  // Keep first-item newcomer guidance outside the base template and load it as a
  // small progressive enhancement. The base reader still works if this file is
  // unavailable, while generated index.html does not need another large inline block.
  if (!document.querySelector('script[data-first-item-reading]')) {
    const script = document.createElement("script");
    script.src = "first-item-reading.js";
    script.async = false;
    script.dataset.firstItemReading = "true";
    document.head.append(script);
  }

  // Boundary notes only appear for first-item cases that are easy to misread:
  // zero personal command attribution, partial attribution scores, or zero outcome.
  if (!document.querySelector('script[data-first-item-boundary-notes]')) {
    const script = document.createElement("script");
    script.src = "first-item-boundary-notes.js";
    script.async = false;
    script.dataset.firstItemBoundaryNotes = "true";
    document.head.append(script);
  }

  // Second-item reading guidance makes the three real score blocks explicit before
  // readers enter the lower-level method, outcome and handoff indicators.
  if (!document.querySelector('script[data-second-item-reading]')) {
    const script = document.createElement("script");
    script.src = "second-item-reading.js";
    script.async = false;
    script.dataset.secondItemReading = "true";
    document.head.append(script);
  }

  // The template performs one synchronous first render before this enhancement is
  // injected. Re-route once so direct person/compare URLs immediately switch to
  // the lazy detail path while the overview remains unchanged.
  route();
})();
