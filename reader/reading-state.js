"use strict";

function readerPageTitle(hash, records, compareIds = []) {
  const brand = '帝王三镜';
  let parts;
  try { parts = hash.split('/').map(decodeURIComponent); }
  catch { return `地址无效 · ${brand}`; }
  const name = id => records.get(id)?.ruler_name;
  if (['#person','#net'].includes(parts[0])) {
    const person = name(parts[1]);
    if (!person) return `未找到人物 · ${brand}`;
    const sections = parts[0] === '#person'
      ? {profile:'人物画像',impact:'历史影响',net:'统治绩效'}
      : {first:'政权奠基与统一',second:'治国成效',third:'军事与边疆',fourth:'文明与国家整合',all:'统治绩效'};
    const section = sections[parts[2]] || (parts[0] === '#net' ? '统治绩效' : '人物总览');
    return `${person} · ${section} · ${brand}`;
  }
  if (parts[0] === '#compare') {
    const ids = parts.length > 1 ? parts.slice(1) : compareIds;
    const names = ids.map(name).filter(Boolean);
    return `${names.length === 2 ? names.join('与') + ' · ' : ''}人物对照 · ${brand}`;
  }
  return `${parts[0] === '#guide' ? '阅读指南' : '综合阅读'} · ${brand}`;
}

(() => {
  // State belongs to a person/system, while scroll positions belong to exact
  // routes. Opening a new axis must still follow its explicit destination.
  const pages = new Map(), positions = new Map();
  const pageKey = hash => /^#(?:person|net)\//.test(hash)
    ? hash.split('/').slice(0, 3).join('/') : hash;
  let active = location.hash, restoring = true, queued = false, generation = 0;

  function detailKey(node) {
    const parts = [];
    for (let current = node; current && current !== screen; current = current.parentElement) {
      if (current.id) { parts.unshift('#' + current.id); break; }
      if (current.tagName === 'DETAILS') {
        const label = current.querySelector(':scope > summary')?.textContent.trim() || '';
        const peers = [...(current.parentElement?.children || [])].filter(other =>
          other.tagName === 'DETAILS' && other.querySelector(':scope > summary')?.textContent.trim() === label);
        parts.unshift(label + ':' + peers.indexOf(current));
      } else if (current.dataset?.comparePerson) {
        parts.unshift('person:' + current.dataset.comparePerson);
      } else if (current.tagName === 'TR') {
        parts.unshift('row:' + (current.firstElementChild?.textContent.trim() || ''));
      }
    }
    return parts.join('/');
  }

  function save() {
    if (restoring || screen.querySelector('.empty')) return;
    const saved = pages.get(pageKey(active)) || new Map();
    for (const node of screen.querySelectorAll('details')) saved.set(detailKey(node), node.open);
    pages.set(pageKey(active), saved);
    const table = screen.querySelector('.comparison-scroll');
    positions.set(active, {x:window.scrollX, y:window.scrollY, tableX:table?.scrollLeft || 0, tableY:table?.scrollTop || 0});
  }

  function restore() {
    queued = false;
    document.title = readerPageTitle(location.hash, byId, state.compare);
    if (location.hash !== active || screen.querySelector('.empty')) return;
    const saved = pages.get(pageKey(active));
    for (const node of screen.querySelectorAll('details')) {
      const key = detailKey(node);
      if (saved?.has(key) && node.open !== saved.get(key)) node.open = saved.get(key);
    }
    // A direct axis/section link takes precedence over a saved closed fold.
    const parts = active.split('/');
    if (restoring && parts[0] === '#person' && parts.length === 4) {
      let id;
      try { id = decodeURIComponent(parts[3]); } catch { return; }
      const target = document.getElementById(narrativeSourceId(parts[2], id) || (parts[2] === 'profile' ? 'reason-' + id : id));
      for(let node=target;node;node=node.parentElement)if(node.tagName==='DETAILS')node.open=true;
      if(target?.id==='history-evidence'){const evidence=target.querySelector('.narrative-evidence');if(evidence)evidence.open=true;}
    }
    if (restoring && parts[0] === '#net' && parts.length === 4) {
      let focus;
      try { focus = decodeURIComponent(parts[3]); } catch { return; }
      const target=netFocusTarget(parts[2], focus);
      for(let node=target;node;node=node.parentElement)if(node.tagName==='DETAILS')node.open=true;
    }
    if (restoring) {
      const position = positions.get(active), token = generation;
      requestAnimationFrame(() => requestAnimationFrame(() => {
        if (token !== generation || location.hash !== active) return;
        if (position) {
          window.scrollTo(position.x, position.y);
          const table = screen.querySelector('.comparison-scroll');
          if (table) { table.scrollLeft = position.tableX; table.scrollTop = position.tableY; }
        }
        restoring = false;
      }));
    }
  }

  function schedule() {
    if (!queued) { queued = true; requestAnimationFrame(restore); }
  }

  function begin() {
    save();
    active = location.hash;
    document.title = readerPageTitle(active, byId, state.compare);
    restoring = true;
    generation++;
    schedule();
  }

  screen.addEventListener('toggle', event => {
    if (restoring || event.target.tagName !== 'DETAILS') return;
    const saved = pages.get(pageKey(active)) || new Map();
    saved.set(detailKey(event.target), event.target.open);
    pages.set(pageKey(active), saved);
  }, true);
  window.addEventListener('scroll', save, {passive:true});
  screen.addEventListener('scroll', save, {capture:true, passive:true});
  new MutationObserver(schedule).observe(screen, {childList:true, subtree:true});
  const priorRoute = route;
  window.removeEventListener('hashchange', priorRoute);
  route = function() { begin(); return priorRoute(); };
  window.addEventListener('hashchange', route);
  // Same-route renders (swap, reading settings, picker cancellation) also save
  // state before replacing the DOM. Async completions are restored by observer.
  for (const name of ['person', 'compare', 'home', 'guide']) {
    const prior = window[name];
    window[name] = function(...args) {
      if (!restoring) begin();
      return prior(...args);
    };
  }
  document.title = readerPageTitle(location.hash, byId, state.compare);
  schedule(); // Initial deep links also wait for their asynchronously loaded DOM.
})();
