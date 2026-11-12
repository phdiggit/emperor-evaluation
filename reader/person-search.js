"use strict";

(() => {
  const normalize = value => String(value ?? "").normalize("NFKC").toLowerCase().replace(/\s+/g, "");
  const byId = new Map();
  const byName = new Map();
  for (const [id, name, aliases, sourceIds, polities] of globalThis.READER_PERSON_IDENTITIES || []) {
    const terms = [...new Set([name, ...aliases].map(normalize))];
    for (const key of [id, ...sourceIds]) {
      // Shared source IDs and same-name records must not silently select one person.
      byId.set(key, byId.has(key) ? null : terms);
    }
    byName.set(name, byName.has(name) ? null : {terms, polities});
  }

  function matches(id, query) {
    const q = normalize(query);
    return Boolean(q && (byId.get(id) || byName.get(id)?.terms)?.includes(q));
  }

  function aliasesForCommander(name, dynasty) {
    const identity = byName.get(name);
    if (!identity) return [];
    const scopes = String(dynasty || "").split(/[／/、]/);
    const polities = new Set(identity.polities.flatMap(polity => [polity, polity.replace(/^[东西南北前后]([汉晋宋魏齐周燕赵凉秦])$/, "$1")]));
    return scopes.some(scope => polities.has(scope.trim())) ? identity.terms : [];
  }

  function prioritize(entries, direct) {
    const parent = entries[0]?.parentElement;
    if (!parent) return;
    const priority = new Set(direct);
    let next = parent.firstElementChild;
    for (const entry of [...direct, ...entries.filter(item => !priority.has(item))]) {
      if (next === entry) next = next.nextElementSibling;
      else parent.insertBefore(entry, next);
    }
  }

  function filterCards(entries, query, {text = entry => entry.textContent, identityOnly = false} = {}) {
    const q = normalize(query);
    const direct = entries.filter(entry => matches(entry.id, q) || normalize(entry.id) === q);
    const selected = new Set(direct);
    const textMatches = !identityOnly || !direct.length;
    const results = [];
    for (const entry of entries) {
      entry.hidden = Boolean(q && !selected.has(entry) && (!textMatches || !normalize(text(entry)).includes(q)));
      if (!entry.hidden) results.push(entry);
    }
    prioritize(entries, direct);
    return results;
  }

  globalThis.ReaderPersonSearch = Object.freeze({matches, filterCards, aliasesForCommander});
})();
