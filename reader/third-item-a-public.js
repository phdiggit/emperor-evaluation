"use strict";

(() => {
  const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const paragraphs = value => String(value ?? "").split(/\n\n+/).filter(Boolean).map(text => `<p class="prose">${escape(text)}</p>`).join("");
  function guide(data) {
    if (!data) return "";
    const scales = data.axes.map(axis => `<h4>${escape(axis.title)}</h4><ul>${axis.rows.map(row => `<li>${escape(row)}</li>`).join("")}</ul>`).join("");
    return `<details class="third-a-guide"><summary>战略安全的通用规则与状态档位</summary>${data.paragraphs.map(paragraphs).join("")}${scales}</details>`;
  }
  function sharedResponsibility([a, b]) {
    const text = (a?.display_responsibility ?? a?.responsibility)?.trim();
    const other = (b?.display_responsibility ?? b?.responsibility)?.trim();
    return text && text === other && text !== a.handover.trim() && text !== b.handover.trim() ? text : "";
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
    const shownResponsibility = data.display_responsibility ?? data.responsibility;
    const responsibility = !shownResponsibility || combined || shownResponsibility.trim() === shared
      ? "" : responsibilitySection("本人归责", shownResponsibility);
    const start = `接班 · ${escape(data.start_label)}`;
    const end = `${combined ? "交班与归责依据" : "交班"} · ${escape(data.end_label)}`;
    const inherited = paragraphs(data.display_inherited ?? data.inherited);
    const handover = paragraphs(data.display_handover ?? data.handover);
    const states = data.shared_state_basis
      ? `<div class="third-a-states"><section><h4>${start} → ${end}</h4>${inherited}</section></div>`
      : `<div class="third-a-states"><section><h4>${start}</h4>${inherited}</section><section><h4>${end}</h4>${handover}</section></div>`;
    const scope = [data.boundary, data.state_grade_note, ...data.scale].filter(Boolean).map(paragraphs).join("");
    return `<div class="third-a-public-reading" data-formal-public-source><p class="meta">评价时期：${escape(data.window)} · <strong class="third-a-type">${escape(data.type_label)}</strong></p><div class="third-a-story">${paragraphs(data.story)}</div>${states}${responsibility}<details><summary>定档理由</summary>${paragraphs(data.decision)}</details><details><summary>这个分怎么算？</summary>${paragraphs(data.method)}${paragraphs(data.display_calculation ?? data.calculation)}</details><details><summary>经历与评价的史料依据</summary>${paragraphs(data.source_note)}${data.sources.some(ref => ref.url) ? "" : '<p class="meta">原典直达链接暂缺。</p>'}${sources ? `<ul class="sources">${sources}</ul>` : ""}</details>${scope ? `<details><summary>个案范围与限制</summary>${scope}</details>` : ""}${official ? `<p class="sources">${official}</p>` : ""}</div>`;
  }
  globalThis.ThirdItemAReading = Object.freeze({html, guide, sharedResponsibility, responsibilitySection});
})();
