"use strict";

(() => {
  const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const paragraphs = value => String(value ?? "").split(/\n\n+/).map(text => `<p class="prose">${escape(text)}</p>`).join("");
  function sources(refs, record) {
    return `<ul class="sources">${refs.map(ref => `<li>${escape(ref.kind)} · ${link(ref.path, ref.label + ' ↗', record)}</li>`).join('')}</ul>`;
  }
  function heading(item) {
    const data = item.reader_public_b;
    if (!data) throw new Error('缺少第三项B正式公开正文');
    return `<div class="component third-b-result" data-raw-rate="${escape(data.raw_rate)}" data-adopted-rate="${escape(data.adopted_rate)}"><strong>${escape(item.public_component_label)}</strong><b>合成采用 ${escape(data.adopted_rate)}%</b></div>`;
  }
  function html(item, record) {
    const data = item.reader_public_b;
    if (!data) throw new Error('缺少第三项B正式公开正文');
    const number = value => value == null ? '未单列' : String(value);
    const regionTable = data.regions?.length ? `<details class="third-b-regions"><summary>接班、交班的区域控制明细</summary><p class="meta">当量来自正式区域裁决；未单列的锚点不补作0。跨项排除先看正式总快照，不能把以下历史区域记录不加区分地重新相加。</p><div class="table-wrap"><table class="b-control-table"><thead><tr><th>控制对象</th><th>接班当量</th><th>交班当量</th><th>采用范围</th></tr></thead><tbody>${data.regions.map(region => `<tr><td>${escape(region.label)}</td><td>${escape(number(region.start))}</td><td>${escape(number(region.end))}</td><td>${region.excluded ? '已排除，不作独立控制增益' : '按现行快照核对'}</td></tr>`).join('')}</tbody></table></div></details>` : '';
    const review = data.review_status ? `<p class="notice third-b-review" data-review-status="${escape(data.review_status)}">${escape(data.review_note)}</p>` : '';
    const evidence = data.evidence_items.map(entry => `<li><h4>${escape(entry.label)}</h4><p class="meta">现行裁决叙述</p>${paragraphs(entry.basis)}<details><summary>本条裁决与所引材料</summary>${sources(entry.sources, record)}</details></li>`).join('');
    return `<div class="third-b-public-reading" data-formal-public-source><p class="meta">评价时期：${escape(data.window)}</p><div class="third-b-story">${paragraphs(data.story)}</div>${review}<div class="label">为什么这样评</div>${paragraphs(data.decision)}${data.review_explanation ? `<details><summary>成熟度复核的具体依据</summary>${paragraphs(data.review_explanation)}</details>` : ''}${regionTable}<details><summary>本人贡献与采用范围</summary>${paragraphs(data.responsibility)}${paragraphs(data.contribution_note)}${paragraphs(data.boundary)}</details><details class="third-b-calculation"><summary>原始率、实际采用率与分数计算</summary>${paragraphs(data.rate_note)}${paragraphs(data.adoption_basis)}${data.diagnostic_note ? paragraphs(data.diagnostic_note) : ''}${paragraphs(data.method)}${paragraphs(data.calculation)}${paragraphs(data.combination)}<details><summary>档位与得分率对照</summary>${paragraphs(data.rate_table.join('\n\n'))}${paragraphs(data.scale.join('\n\n'))}</details></details><details><summary>逐条控制依据与来源</summary>${paragraphs(data.source_note)}<ul class="third-b-evidence">${evidence}</ul><details><summary>人物相关现行材料汇集</summary>${sources(data.sources, record)}</details></details></div>`;
  }
  globalThis.ThirdItemBReading = Object.freeze({html, heading});
})();
