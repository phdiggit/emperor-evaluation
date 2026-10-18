"use strict";
(() => {
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const prose = v => String(v ?? "").split(/\n\n+/).filter(Boolean).map(p => `<p class="prose">${esc(p)}</p>`).join("");
  function sourceList(items, record) {
    return `<ol class="sources fourth-c-sources">${items.map(s => `<li><strong>${esc(s.kind)}</strong>：${s.target ? link(s.target,s.label+" ↗",record) : esc(s.label)}${s.target ? `<details><summary>原引用与定位</summary>${prose(s.original)}</details>` : prose(s.original)}</li>`).join("")}</ol>`;
  }
  function reading(item) {
    if (!item.reader_public_fourth_c) throw new Error("缺少第四项C正式来源与分数说明");
    return item.reader_public_fourth_c;
  }
  function heading(item) {
    const d = reading(item);
    return `<div class="component"><strong>知识生产与文化生态</strong><b>${d.points>0?"+":""}${esc(d.points)} 分</b></div><p class="subline">${esc(d.status)}</p>`;
  }
  function entryLinks(record, options = {}) {
    const links = [];
    if (options.collection) {
      if (record.person_href) links.push(`<a href="${esc(record.person_href)}">查看人物页 →</a>`);
      if (record.detail_href) links.push(`<a href="${esc(record.detail_href)}">查看此人的知识文化详情 →</a>`);
    } else {
      const id = options.formalId || record.fourth_c_collection_ref || record.net?.source_item_ids?.fourth_item || record.ruler_id;
      if (id) links.push(`<a href="fourth-item-c.html#${encodeURIComponent(id)}">知识文化全池 · 定位此人 →</a>`);
      if (record.net && record.ruler_id) links.push(`<a href="#net/${encodeURIComponent(record.ruler_id)}/fourth/c">查看此人的知识文化详情 →</a>`);
    }
    return links.length ? `<nav class="fourth-c-entry-links" aria-label="知识文化阅读入口">${links.join('')}</nav>` : '';
  }
  function html(item, record, options = {}) {
    const d = reading(item);
    const materials = d.evidence_items.map((e,i) => `<article class="net-material-card"><h4>材料${i+1} · ${esc(e.status)}</h4>${prose(e.result)}<details><summary>本人责任与跨项边界</summary>${prose(e.responsibility)}${prose(e.scope)}</details>${e.exclusion_reason?`<div class="label">为什么这条不计分</div>${prose(e.exclusion_reason)}`:""}<details><summary>这条材料怎样参与合成</summary>${prose(e.components)}${prose(e.hard_negative)}</details><details><summary>这条材料的逐条史源（${e.sources.length}条引用）</summary>${sourceList(e.sources,record)}</details></article>`).join("");
    return `<div class="fourth-c-public-reading" data-formal-public-source><h4>${esc(d.question)}</h4><p class="meta">评价时期：${esc(d.window)}</p>${entryLinks(record,{...options,formalId:item.reader_c_collection_id})}${d.zero_reason?`<div class="label">为什么是0分</div>${prose(d.zero_reason)}`:""}<div class="label">为什么采用这个幅度和位置</div>${prose(d.decision_basis)}${materials}<details><summary>查看完整分数合成</summary>${prose(d.calculation)}<details><summary>通用规则与尺度</summary>${prose(d.method)}<ul>${d.scale.map((v,i)=>`<li>${i+1}级：${esc(v)}</li>`).join("")}</ul></details></details><details><summary>现行评价依据与材料范围</summary>${prose(d.review_basis)}${prose(d.source_note)}${sourceList(d.assessment_sources,record)}</details></div>`;
  }
  globalThis.FourthItemCReading = Object.freeze({heading,html,entryLinks});
})();
