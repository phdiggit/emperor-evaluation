"use strict";

(() => {
  const basePerson = person;
  const baseCompare = compare;
  const baseHome = home;
  const baseGuide = guide;
  const pendingLoads = new Map();
  let renderGeneration = 0;

  // First-item detail pages read compact build-time per-person source slices.
  // Cache failures fall back to the formal Markdown source so auditability remains.
  const browserFetch = window.fetch.bind(window);
  const firstItemSourceMarkers = new Map([
    ["01-第一项A统一主链客观贡献正式结算.md", "A统一贡献"],
    ["02-第一项B1创业难度与战略效率正式结算.md", "B1创业难度与效率"],
    ["03-第一项B2创业组织与政治整合正式结算.md", "B2组织与整合"],
    ["04-第一项C本人军事统帅与战争解题能力正式结算.md", "C军事统帅与战争解题"],
  ]);
  const firstItemSourceLoads = new Map();
  const FIRST_ITEM_TOTAL_DOC = "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/01-第一项政权奠基与统一贡献及能力正式结算.md";

  function firstItemRouteId() {
    const match = location.hash.match(/^#(?:person|net)\/([^/?#]+)(?:\/first)?(?:\/|$)/);
    if (!match) return "";
    try { return decodeURIComponent(match[1]); }
    catch { return ""; }
  }

  function requestText(input) {
    const raw = typeof input === "string"
      ? input
      : input instanceof URL ? input.href : input?.url || String(input || "");
    try { return decodeURIComponent(raw); }
    catch { return raw; }
  }

  function loadFirstItemSource(rulerId) {
    if (!firstItemSourceLoads.has(rulerId)) {
      const pending = browserFetch(`data/first-item/${encodeURIComponent(rulerId)}.json`, {cache: "no-cache"})
        .then(response => {
          if (!response.ok) throw new Error(`First-item source cache HTTP ${response.status}`);
          return response.json();
        })
        .then(payload => {
          if (!payload || payload.ruler_id !== rulerId || !payload.documents || !payload.public_outcome) {
            throw new Error(`First-item source cache mismatch for ${rulerId}`);
          }
          return payload;
        })
        .catch(error => {
          firstItemSourceLoads.delete(rulerId);
          throw error;
        });
      firstItemSourceLoads.set(rulerId, pending);
    }
    return firstItemSourceLoads.get(rulerId);
  }

  window.fetch = async function(input, options) {
    const text = requestText(input);
    const match = [...firstItemSourceMarkers.entries()].find(([marker]) => text.includes(marker));
    if (match) {
      const rulerId = firstItemRouteId();
      if (rulerId) {
        try {
          const payload = await loadFirstItemSource(rulerId);
          const markdown = payload.documents[match[1]];
          if (typeof markdown === "string" && markdown) {
            return new Response(markdown, {status: 200, headers: {"Content-Type": "text/markdown; charset=utf-8"}});
          }
        } catch (error) {
          console.warn("First-item source cache unavailable; falling back to formal source.", error);
        }
      }
    }
    return browserFetch(input, options);
  };

  function loading(message) {
    screen.innerHTML = `<div class="empty" role="status">${esc(message)}</div>`;
  }

  function loadFailure(error) {
    console.error(error);
    screen.innerHTML = `<div class="empty"><p>完整资料加载失败。</p><p class="subline">请检查网络后重试；人物总览仍可正常使用。</p><button data-home>返回人物总览</button></div>`;
  }

  function simplifyFirstItemSourceLinks() {
    const root = document.querySelector(".first-item-public-v2");
    if (!root) return;

    for (const details of root.querySelectorAll(".first-item-card > details")) {
      const summary = details.querySelector(":scope > summary");
      if (summary?.textContent.trim() === "裁决依据与来源") details.remove();
    }

    if (root.querySelector(":scope > .first-item-total-source")) return;
    const rulerId = firstItemRouteId();
    const record = rulerId ? byId.get(rulerId) : null;
    const paragraph = document.createElement("p");
    paragraph.className = "sources first-item-total-source";
    paragraph.innerHTML = link(FIRST_ITEM_TOTAL_DOC, "查看第一项总榜 ↗", record);
    const total = root.querySelector(":scope .first-item-total");
    if (total) total.after(paragraph);
    else root.append(paragraph);
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

  if (!document.querySelector('script[data-first-item-reading]')) {
    const script = document.createElement("script");
    script.src = "first-item-reading.js";
    script.async = false;
    script.dataset.firstItemReading = "true";
    document.head.append(script);
  }

  // Second-item guidance is still a separate lazy-loaded view helper.
  if (!document.querySelector('script[data-second-item-reading]')) {
    const script = document.createElement("script");
    script.src = "second-item-reading.js";
    script.async = false;
    script.dataset.secondItemReading = "true";
    document.head.append(script);
  }

  new MutationObserver(simplifyFirstItemSourceLinks).observe(screen, {childList: true, subtree: true});
  window.addEventListener("hashchange", simplifyFirstItemSourceLinks);

  // The template performs one synchronous first render before this enhancement is
  // injected. Re-route once so direct person/compare URLs immediately switch to
  // the lazy detail path while the overview remains unchanged.
  route();
})();
