"use strict";

(() => {
  // State belongs to a person/system, while scroll positions belong to exact
  // routes. Opening a new axis must still follow its explicit destination.
  const pages = new Map(), positions = new Map();
  const pageKey = hash => /^#(?:person|net)\//.test(hash)
    ? hash.split('/').slice(0, 3).join('/') : hash;
  let active = location.hash, restoring = false, queued = false, generation = 0;

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
      const target = document.getElementById(parts[2] === 'profile' ? 'reason-' + id : id);
      for(let node=target;node;node=node.parentElement)if(node.tagName==='DETAILS')node.open=true;
      if(target?.id==='history-evidence'){const evidence=target.querySelector('.narrative-evidence');if(evidence)evidence.open=true;}
    }
    if (restoring && parts[0] === '#net' && parts.length === 4) {
      const target=document.getElementById((parts[2]==='first'?'net-first-':'net-group-')+parts[3]);
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
})();
