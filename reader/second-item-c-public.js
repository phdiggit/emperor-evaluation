"use strict";

(() => {
  const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const paragraphs = value => String(value ?? "").split(/\n\n+/).map(text => `<p class="prose">${escape(text)}</p>`).join("");
  function sources(refs) {
    return refs.map(ref => {
      const target = typeof link === "function" ? link(ref.path, "查看所引原记录 ↗") : `<a href="${escape(ref.path)}">查看所引原记录 ↗</a>`;
      const original = ref.source_url ? ` <a href="${escape(ref.source_url)}" target="_blank" rel="noopener">查看所引史源 ↗</a>` : "";
      return `<section class="c-public-source"><p>${escape(ref.source_kind)} · ${escape(ref.source_title)} · ${escape(ref.source_locator)}</p><blockquote class="prose">${escape(ref.exact_quote)}</blockquote><p class="sources">${target}${original}</p></section>`;
    }).join("");
  }
  function html(item) {
    const record = item.reader_public_c;
    if (!record) throw new Error("缺少第二项C正式公开正文");
    const modes = {DIRECT:"史料直接记载",INFERRED:"受约束推断",ASSESSMENT:"正式评价判断",BACKGROUND:"背景互证",EXCLUDED:"不采用的范围核对"};
    const facts = record.public_evidence_items.map(entry => `<li class="c-public-fact" data-public-evidence-id="${escape(entry.id)}"><h4>${escape(entry.public_label)}</h4><p class="meta">${escape(modes[entry.evidence_mode])}</p>${paragraphs(entry.public_basis)}<p class="prose"><strong>采用范围：</strong>${escape(entry.public_scope)}</p>${entry.public_boundary ? `<p class="prose">${escape(entry.public_boundary)}</p>` : ""}${entry.source_binding_kind === "CLAIM_SUPPORT" ? `<details class="c-public-sources"><summary>本条史料与评价依据</summary>${sources(entry.source_refs)}</details>` : `<p class="meta">本条沿用正式裁决叙述；相关材料列于人物材料汇集，尚未建立逐条事实的支持关系。</p>`}</li>`).join("");
    const related = record.public_related_source_refs.length ? `<details class="c-public-related"><summary>相关材料汇集（不代表逐条事实已获证明）</summary>${sources(record.public_related_source_refs)}</details>` : "";
    return `<div class="c-public-reading" data-formal-public-source><div class="c-public-story">${paragraphs(record.public_story)}</div>${paragraphs(record.public_source_note)}<details class="c-public-decision"><summary>为什么这样评</summary>${paragraphs(record.public_adjudication_summary)}${paragraphs(record.public_loss_label)}</details><details class="c-public-evidence"><summary>裁决叙述与来源</summary><ul class="c-public-facts">${facts}</ul>${related}</details><details class="c-public-boundary"><summary>评价范围与限制</summary>${paragraphs(record.public_boundary)}</details><details class="c-public-calculation"><summary>这个分怎么算？</summary>${paragraphs(record.public_calculation)}</details></div>`;
  }
  globalThis.SecondItemCReading = Object.freeze({html});
})();
