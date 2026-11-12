"use strict";

(() => {
  const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const paragraphs = value => String(value ?? "").split(/\n\n+/).map(text => `<p class="prose">${escape(text)}</p>`).join("");
  function sources(refs, record) {
    return `<ul class="sources">${refs.map(ref => `<li>${escape(ref.kind)} · ${ref.url ? link(ref.url, ref.label + ' ↗', record) : ref.archive_href ? `<a href="${escape(ref.archive_href)}">${escape(ref.label)} ↗</a>` : escape(ref.label)}${ref.context ? paragraphs(ref.context) : ''}${ref.quote ? `<blockquote>${escape(ref.quote)}</blockquote>` : ''}</li>`).join('')}</ul>`;
  }
  function heading(item) {
    const data = item.reader_public_b;
    if (!data) throw new Error('缺少第三项B正式公开正文');
    return `<div class="component third-b-result" data-raw-rate="${escape(data.raw_rate)}" data-adopted-rate="${escape(data.adopted_rate)}"><strong>${escape(item.public_component_label)}</strong></div>`;
  }
  function combinationHtml(items) {
    const data = items.find(item => item.reader_public_b)?.reader_public_b;
    return data ? `<details class="third-b-combination"><summary>控制成果的共同计算规则</summary>${paragraphs(data.method)}${paragraphs(data.combination)}</details>` : '';
  }
  function html(item, record) {
    const data = item.reader_public_b;
    if (!data) throw new Error('缺少第三项B正式公开正文');
    const number = value => value == null ? '未单列' : String(value);
    const regionTable = data.regions?.length ? `<details class="third-b-regions"><summary>接班、交班的区域控制明细</summary><p class="meta">当量用于比较不同时代的控制范围，不等于面积或人口。未单列的数据不代表0；已在其他项目计分的成果不重复计入，各地区数值不能直接相加。</p><div class="table-wrap"><table class="b-control-table"><thead><tr><th>控制对象</th><th>接班当量</th><th>交班当量</th><th>采用范围</th></tr></thead><tbody>${data.regions.map(region => `<tr><td>${escape(region.label)}</td><td>${escape(number(region.start))}</td><td>${escape(number(region.end))}</td><td>${region.excluded ? '已排除，不作独立控制增益' : '按本项范围计入'}</td></tr>`).join('')}</tbody></table></div></details>` : '';
    const review = data.review_status ? `<p class="notice third-b-review" data-review-status="${escape(data.review_status)}">${escape(data.review_note)}</p>` : '';
    const evidence = data.evidence_items.map(entry => `<li><h4>${escape(entry.label)}</h4>${paragraphs(entry.basis)}<details><summary>本条判断的史料依据</summary>${sources(entry.sources, record)}</details></li>`).join('');
    const isControlScope = Array.isArray(data.regions);
    const facts = `<ul class="third-b-evidence">${evidence}</ul>`;
    const decision = `<div class="label">为什么这样评</div>${paragraphs(data.decision)}`;
    const additional = data.sources;
    const official = item.reader_source_refs?.find(ref => ref.startsWith(item.source + '#ruler_id=')) || item.source;
    const officialEntry = official ? `<p class="sources">${link(official, '查看第三项控制成果正式记录 ↗', record)}</p>` : '';
    return `<div class="third-b-public-reading" data-formal-public-source><p class="meta">评价时期：${escape(data.window)}</p><div class="third-b-story">${paragraphs(data.story)}</div>${review}${isControlScope ? facts : ""}${data.review_explanation ? `<details><summary>成熟度复核的具体依据</summary>${paragraphs(data.review_explanation)}</details>` : ''}${regionTable}<details><summary>本人贡献与采用范围</summary>${paragraphs(data.responsibility)}${paragraphs(data.contribution_note)}${paragraphs(data.boundary)}</details><details class="third-b-calculation"><summary>分数怎么算：采用率 ${escape(data.adopted_rate)}%</summary>${decision}${data.control_measurement ? paragraphs(data.control_measurement) : ""}${paragraphs(data.rate_note)}${paragraphs(data.adoption_basis)}${data.diagnostic_note ? paragraphs(data.diagnostic_note) : ''}${paragraphs(data.calculation)}<details><summary>档位与得分率对照</summary>${paragraphs(data.rate_table.join('\n\n'))}${paragraphs(data.scale.join('\n\n'))}</details></details><details><summary>逐条控制依据与来源</summary>${paragraphs(data.source_note)}${isControlScope ? "" : facts}${additional.length ? `<details><summary>补充来源</summary>${sources(additional, record)}</details>` : ""}</details>${officialEntry}</div>`;
  }
  globalThis.ThirdItemBReading = Object.freeze({html, heading, combinationHtml});
})();
