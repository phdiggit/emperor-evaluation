"use strict";

(() => {
  const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const paragraphs = value => String(value ?? "").split(/\n\n+/).map(text => `<p class="prose">${escape(text)}</p>`).join("");
  function html(item, record) {
    const data = item.reader_public_a;
    if (!data) throw new Error("缺少第三项A正式公开正文");
    const sources = data.sources.map(ref => `<li><span>${escape(ref.kind)} · </span>${link(ref.path, ref.label + " ↗", record)}</li>`).join("");
    return `<div class="third-a-public-reading" data-formal-public-source><p class="meta">评价时期：${escape(data.window)}</p><div class="third-a-story">${paragraphs(data.story)}</div><div class="label">为什么这样评</div>${paragraphs(data.decision)}<details><summary>本人承担什么责任？</summary>${paragraphs(data.responsibility)}</details><details><summary>这个分怎么算？</summary>${paragraphs(data.method)}${paragraphs(data.calculation)}</details><details><summary>经历与裁决的来源</summary>${paragraphs(data.source_note)}<ul class="sources">${sources}</ul></details><details><summary>范围与0—5档含义</summary>${paragraphs(data.boundary)}${paragraphs(data.scale.join("\n\n"))}</details></div>`;
  }
  globalThis.ThirdItemAReading = Object.freeze({html});
})();
