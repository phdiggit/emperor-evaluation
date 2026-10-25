"use strict";

(() => {
  const entries = [...document.querySelectorAll('article[data-detail-url]')];
  const byId = new Map(entries.map(entry => [entry.id, entry]));
  const input = document.getElementById('search');
  const scope = document.getElementById('search-scope');
  const status = document.getElementById('search-status');
  const normalize = value => String(value).normalize('NFKC').toLowerCase().replace(/\s+/g, ' ').trim();
  const overview = new Map(entries.map(entry => [entry.id, normalize(entry.dataset.search)]));
  const loaded = new Set();
  const pending = new Map();
  let searchIndex, searchPromise, searchVersion = 0, navigationVersion = 0;

  function localSources(container) {
    if (['localhost', '127.0.0.1', '[::1]'].includes(location.hostname)) {
      for (const link of container.querySelectorAll('[data-local-source]')) link.href = '../' + link.dataset.localSource;
    }
  }

  function loadPerson(entry) {
    if (loaded.has(entry.id)) return Promise.resolve(true);
    if (pending.has(entry.id)) return pending.get(entry.id);
    const slot = entry.querySelector('.third-c-detail-slot');
    slot.textContent = '正在加载完整正文与材料…';
    slot.setAttribute('aria-busy', 'true');
    const request = (async () => {
      try {
        const response = await fetch(entry.dataset.detailUrl, {cache: 'no-cache'});
        if (!response.ok) throw new Error('Detail unavailable');
        slot.innerHTML = await response.text();
        localSources(slot);
        loaded.add(entry.id);
        return true;
      } catch {
        slot.textContent = '正文加载失败，请重试。';
        const retry = document.createElement('button');
        retry.type = 'button';
        retry.textContent = '重新加载';
        retry.addEventListener('click', () => loadPerson(entry));
        slot.append(retry);
        return false;
      } finally {
        pending.delete(entry.id);
        slot.removeAttribute('aria-busy');
      }
    })();
    pending.set(entry.id, request);
    return request;
  }

  async function fullTextIndex() {
    if (searchIndex) return searchIndex;
    if (!searchPromise) {
      searchPromise = (async () => {
        const response = await fetch(status.dataset.searchUrl, {cache: 'no-cache'});
        if (!response.ok) throw new Error('Search unavailable');
        const data = await response.json();
        if (Object.keys(data).length !== byId.size || entries.some(entry => typeof data[entry.id] !== 'string')) {
          throw new Error('Search coverage mismatch');
        }
        searchIndex = new Map(Object.entries(data).map(([id, text]) => [id, normalize(text)]));
        return searchIndex;
      })().finally(() => { searchPromise = null; });
    }
    return searchPromise;
  }

  async function filter() {
    const version = ++searchVersion;
    const query = normalize(input.value);
    let index = overview;
    if (query && scope.value === 'full') {
      status.textContent = '正在加载全文搜索索引…';
      try {
        index = await fullTextIndex();
      } catch {
        if (version === searchVersion) {
          status.textContent = '全文搜索加载失败，当前结果未更新。';
          const retry = document.createElement('button');
          retry.type = 'button'; retry.textContent = '重试搜索';
          retry.addEventListener('click', filter); status.append(retry);
        }
        return;
      }
    }
    if (version !== searchVersion) return;
    const matches = [];
    for (const entry of entries) {
      entry.hidden = Boolean(query && !index.get(entry.id).includes(query));
      if (!entry.hidden) matches.push(entry);
    }
    document.getElementById('count').textContent = matches.length;
    status.textContent = query ? `找到 ${matches.length} 位人物。` : '完整正文与材料在选用该搜索范围时加载。';
    if (query && matches.length === 1) {
      matches[0].querySelector('.third-c-person').open = true;
      loadPerson(matches[0]);
    }
  }

  async function revealPerson() {
    const version = ++navigationVersion;
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    const entry = byId.get(id) || entries.find(person => id.startsWith(person.id + '--evidence--'));
    if (!entry) return;
    // A direct link takes priority over previous filters; its visible count stays accurate.
    if (entry.hidden) { input.value = ''; await filter(); }
    entry.querySelector('.third-c-person').open = true;
    const ready = await loadPerson(entry);
    if (version !== navigationVersion) return;
    const target = ready && document.getElementById(id) || entry;
    const materialBody = target.dataset.cEvidence && target.querySelector('details');
    if (materialBody) materialBody.open = true;
    for (let parent = target.parentElement; parent; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
    }
    target.scrollIntoView();
    if (target !== entry) target.focus({preventScroll: true});
  }

  for (const entry of entries) {
    const details = entry.querySelector('.third-c-person');
    details.addEventListener('toggle', () => { if (details.open) loadPerson(entry); });
  }
  document.addEventListener('click', event => {
    const link = event.target.closest('a[data-c-material-ref]');
    if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    const hash = '#' + encodeURIComponent(link.dataset.cMaterialRef);
    if (location.hash === hash) revealPerson();
    else location.hash = hash;
  });
  input.addEventListener('input', filter);
  scope.addEventListener('change', filter);
  addEventListener('hashchange', revealPerson);
  revealPerson();
})();
