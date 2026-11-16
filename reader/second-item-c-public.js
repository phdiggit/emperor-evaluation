"use strict";

(() => {
  const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const paragraphs = value => String(value ?? "").split(/\n\n+/).filter(Boolean).map(text => `<p class="prose">${escape(text)}</p>`).join("");
  function excerpts(passages) {
    return passages.map(p => {
      const title = p.url ? `<a href="${escape(p.url)}" target="_blank" rel="noopener">${escape(p.title)}</a>` : escape(p.title);
      return `<section>${title ? `<p>${title}</p>` : ""}${p.context ? paragraphs(p.context) : ""}<blockquote class="prose">${escape(p.text)}</blockquote></section>`;
    }).join("");
  }
  function sourceExcerpts(ref) {
    return ref.passages?.length ? ref.passages : [{text:ref.exact_quote}];
  }
  function sources(refs, showQuotes = true) {
    return refs.map(ref => {
      const urls = ref.source_urls || [];
      const original = urls.map((url, i) => `<a href="${escape(url)}" target="_blank" rel="noopener">${urls.length > 1 ? `查看史源 ${i + 1}` : "查看所引史源"} ↗</a>`).join(" ");
      const citation = [ref.source_kind, ref.source_title, ref.source_locator].filter(Boolean).join(" · ");
      const context = ref.source_context ? paragraphs(ref.source_context) : "";
      const quote = showQuotes ? excerpts(sourceExcerpts(ref)) : "";
      return `<section class="c-public-source"><p>${escape(citation)}</p>${context}${quote}${original ? `<p class="sources">${original}</p>` : ""}</section>`;
    }).join("");
  }
  function html(item) {
    const record = item.reader_public_c;
    if (!record) throw new Error("缺少第二项C正式公开正文");
    const modes = {DIRECT:"史料直接记载",INFERRED:"受约束推断",ASSESSMENT:"正式评价判断",BACKGROUND:"背景互证",EXCLUDED:"不采用的范围核对"};
    const storyEvidence = new Set(record.story_evidence_ids);
    const commonScope = new Set(record.shared_collection_scope_ids);
    const facts = record.public_evidence_items.map(entry => {
      const direct = entry.source_binding_kind === "CLAIM_SUPPORT";
      const scope = commonScope.has(entry.id) ? "" : `<p class="prose"><strong>采用范围：</strong>${escape(entry.public_scope)}</p>`;
      return `<li class="c-public-fact" data-public-evidence-id="${escape(entry.id)}"><h4>${escape(entry.public_label)}</h4><p class="meta">${escape(modes[entry.evidence_mode])} · ${direct ? "逐条史源" : "材料汇集"}</p>${storyEvidence.has(entry.id) ? "" : paragraphs(entry.display_basis ?? entry.public_basis)}${scope}${entry.public_boundary ? `<p class="prose">${escape(entry.public_boundary)}</p>` : ""}${direct ? `<details class="c-public-sources"><summary>本条史料与评价依据</summary>${sources(entry.source_refs)}</details>` : ""}</li>`;
    }).join("");
    const refs = record.public_related_source_refs;
    const groups = record.related_material_groups;
    const relatedTitle = "相关材料汇集";
    const materials = groups ? Object.entries(groups).map(([label, entries]) => {
      const blocks = entries.map((indices, i) => {
        const excerptsForGroup = record.related_material_excerpts?.[label]?.[i] || sourceExcerpts(refs[indices[0]]);
        return `<section>${sources(indices.map(index => refs[index]), false)}${excerpts(excerptsForGroup)}</section>`;
      }).join("");
      return `<section><h4>${escape(label)}</h4>${blocks}</section>`;
    }).join("") : sources(refs);
    const related = refs.length ? `<details class="c-public-related"><summary>${relatedTitle}</summary>${materials}</details>` : "";
    const story = record.public_reading_sections
      ? record.public_reading_sections.map(s => `<section class="c-recovery-section" data-recovery-section="${escape(s.id)}"><h4>${escape(s.title)}</h4>${paragraphs(s.body)}</section>`).join("")
      : paragraphs(record.public_story);
    const boundary = record.specific_boundary ?? record.public_boundary;
    const limits = boundary ? `<details class="c-public-boundary"><summary>评价范围与限制</summary>${paragraphs(boundary)}</details>` : "";
    return `<div class="c-public-reading" data-formal-public-source><div class="c-public-story">${story}</div><details class="c-public-decision"><summary>为什么这样评</summary>${paragraphs(record.display_adjudication_summary ?? record.public_adjudication_summary)}${paragraphs(record.display_loss_label ?? record.public_loss_label)}</details><details class="c-public-evidence"><summary>具体事实与史料依据</summary>${paragraphs(record.specific_source_note ?? record.public_source_note)}<ul class="c-public-facts">${facts}</ul>${related}</details>${limits}<details class="c-public-calculation"><summary>这个分怎么算？</summary>${paragraphs(record.display_calculation ?? record.public_calculation)}</details></div>`;
  }
  function guide(text, boundaries = []) {
    const sources = text ? `<details class="c-source-guide"><summary>史源关系怎样读？</summary>${paragraphs(text)}</details>` : "";
    const axes = boundaries.map(item => `<dt>${escape(item.label)}</dt><dd>${escape(item.text)}</dd>`).join("");
    return sources + (axes ? `<details class="c-axis-scope"><summary>四轴范围与共同计分规则</summary><dl>${axes}</dl></details>` : "");
  }
  globalThis.SecondItemCReading = Object.freeze({html, guide});
})();
