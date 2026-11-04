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
    const sources = data.sources.map(ref => `<li><span>${escape(ref.kind)} · </span>${link(ref.path, ref.label + " ↗", record)}</li>`).join("");
    if (!data.inherited || !data.handover) throw new Error("缺少第三项A接班或交班正文");
    const combined = data.handover.trim() === data.responsibility.trim();
    const responsibility = combined || data.responsibility.trim() === shared
      ? "" : responsibilitySection("本人归责", data.responsibility);
    const states = `<div class="third-a-states"><section><h4>接班 · ${escape(data.start_label)}</h4>${paragraphs(data.inherited)}</section><section><h4>${combined ? "交班与归责依据" : "交班"} · ${escape(data.end_label)}</h4>${paragraphs(data.handover)}</section></div>`;
    return `<div class="third-a-public-reading" data-formal-public-source><p class="meta">评价时期：${escape(data.window)} · <strong class="third-a-type">${escape(data.type_label)}</strong></p>${states}${responsibility}<details><summary>任内经历与定档理由</summary><div class="third-a-story"><h4>完整经历</h4>${paragraphs(data.story)}</div><h4>定档理由</h4>${paragraphs(data.decision)}</details><details><summary>这个分怎么算？</summary>${paragraphs(data.method)}${paragraphs(data.calculation)}</details><details><summary>经历与裁决的来源</summary>${paragraphs(data.source_note)}<ul class="sources">${sources}</ul></details><details><summary>范围与安全状态档位</summary>${paragraphs(data.state_grade_note)}${paragraphs(data.boundary)}${paragraphs(data.scale.join("\n\n"))}</details></div>`;
  }
  globalThis.ThirdItemAReading = Object.freeze({html, sharedResponsibility, responsibilitySection});
})();
