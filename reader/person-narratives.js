"use strict";

function narrativeSourceId(system, focus) {
  return ['profile','impact','second','third','fourth'].includes(system) &&
    new RegExp(`^reading-${system}-source-[1-9][0-9]*$`).test(focus) ? focus : '';
}

function netEntryFocus(system, focus) {
  if (system !== 'second' || typeof focus !== 'string') return null;
  const match = focus.match(/^entry-(method|finance|handoff)-([^/]+)$/);
  return match ? {group:match[1], label:match[2]} : null;
}

function netFocusTarget(system, focus) {
  const entry = netEntryFocus(system, focus);
  if (entry) {
    const group = document.getElementById(`net-group-${entry.group}`);
    return [...(group?.querySelectorAll('[data-second-source-label]') || [])]
      .find(node => node.dataset.secondSourceLabel === entry.label) || null;
  }
  return document.getElementById(narrativeSourceId(system, focus) || (system === 'first' ? 'net-first-' : 'net-group-') + focus);
}

function personNarrative(record, system) {
  const chapters = record.reader_narratives?.[system];
  if (!chapters?.length) return '';
  const resolve = path => path.reduce((value, key) => value?.[key], record);
  if (chapters.some(chapter => chapter.evidence.some(ref => typeof resolve(ref.path) !== 'string' || !resolve(ref.path).includes(ref.quote)))) {
    return '<p class="notice">这篇正文的依据已更新，请先阅读下方逐项评价。</p>';
  }
  const id = `reading-${system}`;
  const rid = encodeURIComponent(record.ruler_id);
  const sourceRoute = ['profile','impact'].includes(system) ? `#person/${rid}/${system}` : `#net/${rid}/${system}`;
  const evidenceDestination = ([group, axis, component, position]) => {
    if (group === 'axes') return {href:`#person/${rid}/profile/${axis}`,label:`查看${({M1:'军事统帅',M2:'外交博弈',M4:'内部联盟',M5:'组织执行',C1:'战略判断',C2:'学习纠错',C3:'用人授权',C4:'制度设计',C5:'权力运用与克制'})[axis]||'人物画像'}依据`};
    if (group === 'impact') return {href:`#person/${rid}/impact/history-evidence`,label:'查看历史影响详情'};
    const item = record.net?.component_details?.[component]?.[position];
    if (system === 'second' && ['method','finance','handoff'].includes(component) && item?.reader_kind === 'judgment') {
      const labels = {'A制度建设':'制度建设','B1官僚治理':'官僚治理','B2反馈与约束':'反馈与约束','C1民生':'民生','C2经济财政':'经济财政','C3社会安全':'社会安全','C4恢复与成本':'恢复与额外代价','D1继任行政连续性':'行政连续性','D3政权交接稳定':'交接稳定'};
      return {href:`#net/${rid}/second/${encodeURIComponent(`entry-${component}-${item.label}`)}`,label:`查看${labels[item.label] || item.public_component_label || item.label}具体依据`};
    }
    const labels={method:'制度与行政',finance:'民生与社会',handoff:'政权交接',strategic:'战略与控制成果',military:'军事体系与代价',civilization:'文明与国家整合'};
    return {href:`#net/${rid}/${system}${labels[component]?'/'+component:''}`,label:`查看${labels[component]||'本项'}依据`};
  };
  return `<section class="person-narrative" aria-label="人物评价正文">${chapters.map((chapter, index) =>
    `<article><h2>${esc(chapter.title)}</h2><p>${esc(chapter.text)} <a class="narrative-reference" href="${sourceRoute}/${id}-source-${index + 1}" data-narrative-source="${id}-source-${index + 1}" aria-label="查看第${index + 1}段依据">[${index + 1}]</a></p></article>`).join('')}
    <details id="${id}-sources" class="narrative-sources"><summary>正文依据</summary>${chapters.map((chapter,index)=>{
      if (chapter.evidence.some(ref => ref.explanation)) {
        const cards = chapter.evidence.map(ref => {
          const destination = evidenceDestination(ref.path);
          return `<div class="narrative-evidence-note">${ref.explanation ? `<p>${esc(ref.explanation)}</p>` : ''}<p><a href="${destination.href}" data-narrative-evidence="${system}">${esc(destination.label)} →</a></p><details><summary>核对对应评价原文</summary><blockquote>${esc(ref.quote)}</blockquote></details></div>`;
        }).join('');
        return `<section id="${id}-source-${index + 1}" tabindex="-1"><h3>${index+1}. ${esc(chapter.title)}</h3>${cards}</section>`;
      }
      const quotes = [...new Set(chapter.evidence.map(ref=>ref.quote))].map(quote => `<blockquote>${esc(quote)}</blockquote>`).join('');
      const routes = new Map(chapter.evidence.map(ref => {const destination=evidenceDestination(ref.path);return [destination.href,destination.label];}));
      const links = [...routes].map(([href,label]) => `<p><a href="${href}" data-narrative-evidence="${system}">${esc(label)} →</a></p>`).join('');
      return `<section id="${id}-source-${index + 1}" tabindex="-1"><h3>${index+1}. ${esc(chapter.title)}</h3>${quotes}${links}</section>`;
    }).join('')}</details></section>`;
}

function explorationSummary(record, kind) {
  const action = '<span class="explore-action"><span class="explore-closed">展开</span><span class="explore-open">收起</span><span aria-hidden="true">↗</span></span>';
  if (kind === 'profile') {
    const preview = ['C1','C3','C5'].filter(code=>record.axes?.[code]).map(code=>{
      const scope=profileGradeScope(record.axes[code]);
      return `<span class="explore-grade"><span>${esc({C1:'战略判断',C3:'用人授权',C5:'权力克制'}[code])}${scope?`<small class="explore-grade-scope">${esc(scope)}</small>`:''}</span><b>${grade(record.axes[code])}</b></span>`;
    }).join('');
    return `<strong class="explore-title">能力雷达与九轴等级</strong><span class="explore-preview">${preview}</span>${action}`;
  }
  return `<strong class="explore-title">代表史事、反例与限制、史料出处</strong>${action}`;
}

function narrativeEvidence(record, system, html) {
  if (!record.reader_narratives?.[system]) return html;
  return `<details class="narrative-evidence" data-narrative-system="${system}"><summary class="explore-summary explore-evidence">${explorationSummary(record,'evidence')}</summary>${html}</details>`;
}

function openReadingAncestors(target) {
  for (let node=target;node&&node!==screen;node=node.parentElement) {
    if (node.tagName==='DETAILS') node.open=true;
  }
}

function bindNarrativeLinks() { screen.addEventListener('click', event=>{
  if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button > 0) return;
  const source=event.target.closest('[data-narrative-source]');
  if (source && source.getAttribute('href')===location.hash) {
    event.preventDefault();
    const target=document.getElementById(source.dataset.narrativeSource);
    openReadingAncestors(target);
    target?.focus({preventScroll:true});
    target?.scrollIntoView({block:'start'});
    return;
  }
  const evidence=event.target.closest('[data-narrative-evidence]');
  if (evidence?.getAttribute('href')===location.hash) {
    event.preventDefault();
    const parts=location.hash.split('/');
    const target=netEntryFocus(parts[2],decodeURIComponent(parts[3] || '')) ? netFocusTarget(parts[2],decodeURIComponent(parts[3])) : screen.querySelector('.narrative-evidence');
    openReadingAncestors(target);target?.scrollIntoView({block:'start'});
  }
}); }
