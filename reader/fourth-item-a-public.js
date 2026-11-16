"use strict";
(() => {
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const prose = v => String(v ?? "").split(/\n\n+/).filter(Boolean).map(p => `<p class="prose">${esc(p)}</p>`).join("");
  const sources = (refs, record) => `<ul class="sources">${refs.map(s => `<li>${esc(s.kind)}：${s.target ? link(s.target, s.label + " ↗", record) : esc(s.label)}${s.locator ? prose(s.locator) : ""}${s.context ? prose(s.context) : ""}${s.quote ? `<p class="meta">${esc(s.quote_label)}</p><blockquote>${esc(s.quote)}</blockquote>` : ""}${s.claim ? prose("采用说明：" + s.claim) : ""}${s.limit ? prose("采用范围：" + s.limit) : ""}</li>`).join("")}</ul>`;
  function heading(item, {collection = false} = {}) {
    const data = item.reader_public_fourth_a;
    if (!data) throw new Error("缺少第四项A正式公开正文");
    return `<div class="component">${collection ? '' : '<strong>国家共同体与社会整合</strong>'}<b>${data.points > 0 ? "+" : ""}${esc(data.points)} 分</b></div><p class="subline">${esc(data.status)}</p>`;
  }
  function html(item, record, {collection = false} = {}) {
    const data = item.reader_public_fourth_a;
    if (!data) throw new Error("缺少第四项A正式公开正文");
    const cards = data.evidence_items.map(e => `<article class="net-material-card"><h4>${esc(e.title)}</h4><p class="subline">${esc(e.status)}</p>${e.level_basis ? prose(e.level_basis) : ""}<p class="subline">${esc(e.components)}</p><details><summary>史源与跨项边界</summary>${e.boundary ? prose(e.boundary) : ""}${sources(e.sources,record)}</details></article>`).join("");
    const context = data.context_items.map(e => `<article class="context-story">${e.story !== e.title ? prose(e.story) : ""}${prose(e.boundary)}<details><summary>相关背景来源（不代替本轴结果证据）</summary>${sources(e.sources,record)}</details></article>`).join("");
    const decision = FourthItemReasons.decision(data.display_decision ?? data.decision, prose);
    return `<div class="fourth-a-public-reading" data-formal-public-source><h4>${esc(data.question)}</h4><p class="meta">评价时期：${esc(data.window)}</p>${record.net ? '<p class="sources"><a href="fourth-item-a.html">查看全池同轴依据 →</a></p>' : ""}${cards || decision}${context}${FourthItemReasons.sharedContext(data, prose)}${cards ? `<details><summary>本轴为什么这样计</summary>${decision}</details>` : ""}${FourthItemReasons.calculation(data, prose, {collection, axis: "a"})}<details><summary>评价范围与材料限制</summary>${prose(data.display_boundary ?? data.boundary)}${sources(data.assessment_sources || [],record)}</details></div>`;
  }
  globalThis.FourthItemAReading = Object.freeze({heading,html});
})();
