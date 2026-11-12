"use strict";

function personNarrative(record, system) {
  const chapters = record.reader_narratives?.[system];
  if (!chapters?.length) return '';
  const resolve = path => path.reduce((value, key) => value?.[key], record);
  if (chapters.some(chapter => chapter.evidence.some(ref => typeof resolve(ref.path) !== 'string' || !resolve(ref.path).includes(ref.quote)))) {
    return '<p class="notice">这篇正文的依据已更新，请先阅读下方逐项评价。</p>';
  }
  const id = `reading-${system}`;
  const rid = encodeURIComponent(record.ruler_id);
  const evidenceDestination = ([group, axis, component]) => {
    if (group === 'axes') return {href:`#person/${rid}/profile/${axis}`,label:`查看${({M1:'军事统帅',M2:'外交博弈',M4:'内部联盟',M5:'组织执行',C1:'战略判断',C2:'学习纠错',C3:'用人授权',C4:'制度设计',C5:'权力运用与克制'})[axis]||'人物画像'}依据`};
    if (group === 'impact') return {href:`#person/${rid}/impact/history-evidence`,label:'查看历史影响依据'};
    const labels={method:'制度与行政',finance:'民生与社会',handoff:'政权交接',strategic:'战略与控制成果',military:'军事体系与代价',civilization:'文明与国家整合'};
    return {href:`#net/${rid}/${system}${labels[component]?'/'+component:''}`,label:`查看${labels[component]||'本项'}依据`};
  };
  return `<section class="person-narrative" aria-label="人物评价正文">${chapters.map((chapter, index) =>
    `<article><h2>${esc(chapter.title)}</h2><p>${esc(chapter.text)} <a class="narrative-reference" href="#${id}-source-${index + 1}" data-narrative-source="${id}-source-${index + 1}" aria-label="查看本段依据">[${index + 1}]</a></p></article>`).join('')}
    <details id="${id}-sources" class="narrative-sources"><summary>正文依据</summary>${chapters.map((chapter,index)=>{
      const quotes = [...new Set(chapter.evidence.map(ref=>ref.quote))].map(quote => `<blockquote>${esc(quote)}</blockquote>`).join('');
      const routes = new Map(chapter.evidence.map(ref => {const destination=evidenceDestination(ref.path);return [destination.href,destination.label];}));
      const links = [...routes].map(([href,label]) => `<p><a href="${href}" data-narrative-evidence="${system}">${esc(label)} →</a></p>`).join('');
      return `<section id="${id}-source-${index + 1}" tabindex="-1"><h3>${index+1}. ${esc(chapter.title)}</h3>${quotes}${links}</section>`;
    }).join('')}</details></section>`;
}

function explorationSummary(record, kind) {
  if (kind === 'profile') {
    const preview = ['C1','C3','C5'].filter(code=>record.axes?.[code]).map(code=>{
      const scope=profileGradeScope(record.axes[code]);
      return `<span class="explore-grade"><span>${esc({C1:'战略判断',C3:'用人授权',C5:'权力克制'}[code])}${scope?`<small class="explore-grade-scope">${esc(scope)}</small>`:''}</span><b>${grade(record.axes[code])}</b></span>`;
    }).join('');
    return `<span class="explore-kicker">能力图谱</span><strong class="explore-title">看他的能力轮廓</strong><span class="explore-description">哪些是长处，哪些有局限？展开九轴等级与能力雷达。</span><span class="explore-preview">${preview}</span><span class="explore-action"><span class="explore-closed">展开能力图谱</span><span class="explore-open">收起能力图谱</span><span aria-hidden="true">↗</span></span>`;
  }
  return '<span class="explore-kicker">回到史事</span><strong class="explore-title">这些评价，凭什么成立？</strong><span class="explore-description">沿着具体经历，查看判断理由，也看看哪些事实与结论相反。</span><span class="explore-topics"><span>代表事件</span><span>反例与限制</span><span>史料出处</span></span><span class="explore-action"><span class="explore-closed">展开史事与依据</span><span class="explore-open">收起史事与依据</span><span aria-hidden="true">↗</span></span>';
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
  const source=event.target.closest('[data-narrative-source]');
  if (source) {
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
    const target=screen.querySelector('.narrative-evidence');
    openReadingAncestors(target);target?.scrollIntoView({block:'start'});
  }
}); }
