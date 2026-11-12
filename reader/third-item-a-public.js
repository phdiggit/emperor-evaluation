"use strict";

(() => {
  const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const paragraphs = value => String(value ?? "").split(/\n\n+/).map(text => `<p class="prose">${escape(text)}</p>`).join("");
  function sharedResponsibility([a, b]) {
    const text = a?.responsibility.trim();
    return text && text === b?.responsibility.trim() && text !== a.handover.trim() && text !== b.handover.trim() ? text : "";
  }
  function responsibilitySection(title, text) {
    return `<section class="third-a-responsibility"><h4>${escape(title)}</h4>${paragraphs(text)}</section>`;
  }
  function html(item, record, shared = "") {
    const data = item.reader_public_a;
    if (!data) throw new Error("缺少第三项A正式公开正文");
    const sources = data.sources.map(ref => `<li>${escape(ref.kind)} · ${ref.url ? link(ref.url, ref.label + ' ↗', record) : ref.archive_href ? `<a href="${escape(ref.archive_href)}">${escape(ref.label)} ↗</a>` : escape(ref.label)}${ref.context ? paragraphs(ref.context) : ''}${ref.quote ? `<blockquote>${escape(ref.quote)}</blockquote>` : ''}</li>`).join("");
    const official = (data.official_sources || []).map(ref => link(ref.path, ref.label + " ↗", record)).join(" ");
    if (!data.inherited || !data.handover) throw new Error("缺少第三项A接班或交班正文");
    const combined = data.handover.trim() === data.responsibility.trim();
    const responsibility = combined || data.responsibility.trim() === shared
      ? "" : responsibilitySection("本人归责", data.responsibility);
    const states = `<div class="third-a-states"><section><h4>接班 · ${escape(data.start_label)}</h4>${paragraphs(data.inherited)}</section><section><h4>${combined ? "交班与归责依据" : "交班"} · ${escape(data.end_label)}</h4>${paragraphs(data.handover)}</section></div>`;
    return `<div class="third-a-public-reading" data-formal-public-source><p class="meta">评价时期：${escape(data.window)} · <strong class="third-a-type">${escape(data.type_label)}</strong></p>${states}${responsibility}<details><summary>任内经历与定档理由</summary><div class="third-a-story"><h4>完整经历</h4>${paragraphs(data.story)}</div><h4>定档理由</h4>${paragraphs(data.decision)}</details><details><summary>这个分怎么算？</summary>${paragraphs(data.method)}${paragraphs(data.calculation)}</details><details><summary>经历与评价的史料依据</summary>${paragraphs(data.source_note)}${data.sources.some(ref => ref.url) ? "" : `<p class="meta">本轴尚未单列可直接打开的原典卷篇。</p>`}${sources ? `<ul class="sources">${sources}</ul>` : ""}</details><details><summary>范围与安全状态档位</summary>${paragraphs(data.state_grade_note)}${paragraphs(data.boundary)}${paragraphs(data.scale.join("\n\n"))}</details>${official ? `<p class="sources">${official}</p>` : ""}</div>`;
  }
  globalThis.ThirdItemAReading = Object.freeze({html, sharedResponsibility, responsibilitySection});
})();
