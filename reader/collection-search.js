"use strict";

(() => {
  function bind({input, scope, filter, locate}) {
    function update() {
      history.replaceState({
        ...history.state,
        collectionSearch: {query: input.value, scope: scope?.value}
      }, "");
      return filter();
    }

    function reset() {
      input.value = "";
      return update();
    }

    function route(force = false) {
      // A new fragment gets its own history entry. Returning to an entry
      // restores the search it held before the reader followed a link.
      const saved = history.state?.collectionSearch;
      if (saved && !force) {
        input.value = saved.query;
        if (scope) scope.value = saved.scope;
      }
      return locate({ready: update(), reset: !saved || force ? reset : null});
    }

    input.addEventListener("input", update);
    scope?.addEventListener("change", update);
    addEventListener("hashchange", () => route());
    route();
    return () => route(true);
  }

  function fragment() {
    try {
      return decodeURIComponent(location.hash.slice(1));
    } catch {
      return null;
    }
  }

  function bindCards(entries, {input, count, empty, note, identityOnly, bodyStart}) {
    const readings = new Map();
    for (const entry of entries) {
      const start = entry.querySelector(bodyStart);
      if (!start) continue;
      const reading = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = "展开正文";
      reading.append(summary);
      start.before(reading);
      while (reading.nextSibling) reading.append(reading.nextSibling);
      readings.set(entry, reading);
    }

    function filter() {
      const matches = ReaderPersonSearch.filterCards(entries, input.value, {identityOnly});
      count.textContent = matches.length;
      if (empty) empty.hidden = matches.length !== 0;
    }

    function locate({reset}) {
      note.textContent = "";
      const id = fragment();
      if (id === "") return;
      const target = id && document.getElementById(id);
      if (!target) {
        note.textContent = id === null ? "人物定位地址无效。" : "未找到链接指定的人物记录。";
        return;
      }
      const entry = entries.find(card => card.contains(target));
      if (!entry) return;
      if (entry.hidden) {
        if (!reset) return;
        reset();
      }
      if (readings.has(entry)) readings.get(entry).open = true;
      for (let parent = target.parentElement; parent && parent !== entry; parent = parent.parentElement) {
        if (parent.tagName === "DETAILS") parent.open = true;
      }
      target.scrollIntoView({block: "start"});
    }

    bind({input, filter, locate});
  }

  globalThis.ReaderCollectionSearch = Object.freeze({bind, bindCards, fragment});
})();
