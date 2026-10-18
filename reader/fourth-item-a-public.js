"use strict";
(() => {
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const prose = v => String(v ?? "").split(/\n\n+/).map(p => `<p class="prose">${esc(p)}</p>`).join("");
  const sources = (refs, record) => `<ul class="sources">${refs.map(s => `<li>${esc(s.kind)}：${s.target ? link(s.target, s.label + " ↗", record) : esc(s.label)}${!s.target ? `<details><summary>原引用（含项目采用说明）</summary>${prose(s.original)}</details>` : ""}</li>`).join("")}</ul>`;
  function heading(item) {
    const data = item.reader_public_fourth_a;
    if (!data) throw new Error("缺少第四项A正式公开正文");
    return `<div class="component"><strong>国家共同体与社会整合</strong><b>${data.points > 0 ? "+" : ""}${esc(data.points)} 分</b></div><p class="subline">${esc(data.status)}</p>`;
  }
  function html(item, record) {
    const data = item.reader_public_fourth_a;
    if (!data) throw new Error("缺少第四项A正式公开正文");
    const cards = data.evidence_items.map(e => `<article class="net-material-card"><h4>${esc(e.title)}</h4><p class="subline">${esc(e.status)}</p>${prose(e.story)}<details><summary>本人责任与比较起点</summary>${prose(e.responsibility)}${prose(e.baseline)}</details><details><summary>为何达到这一幅度和位置？</summary>${prose(e.level_basis)}${prose(e.coverage)}${prose(e.duration)}${prose(e.components)}${prose(e.major_negative)}</details><details><summary>这条经历的来源与限制</summary>${prose(e.source_note)}${sources(e.sources,record)}${prose(e.boundary)}</details></article>`).join("");
    const context = data.context_items.map(e => `<article class="context-story">${prose(e.story)}${prose(e.boundary)}<details><summary>相关背景来源（不代替本轴结果证据）</summary>${sources(e.sources,record)}</details></article>`).join("");
    const scale = `<p>先判断各方向结果的强度，再按合同合成净幅度。1—4级含义：</p><ul>${data.scale.map((s,i)=>`<li>${i+1}级：${esc(s)}</li>`).join("")}</ul>`;
    return `<div class="fourth-a-public-reading" data-formal-public-source><h4>${esc(data.question)}</h4><p class="meta">评价时期：${esc(data.window)}</p>${prose(data.story)}<div class="label">为什么这样评</div>${prose(data.decision)}<details><summary>本人承担什么责任？</summary>${prose(data.responsibility)}</details>${cards}${context}<details><summary>这个分怎么算？</summary>${prose(data.calculation)}${prose(data.method)}${scale}</details><details><summary>评价范围与材料限制</summary>${prose(data.boundary)}${prose(data.source_note)}${sources(data.assessment_sources || [],record)}</details></div>`;
  }
  globalThis.FourthItemAReading = Object.freeze({heading,html});
})();
