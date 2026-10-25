"use strict";
(() => {
  const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const paragraphs = value => String(value ?? "").split(/\n\n+/).filter(Boolean).map(t => `<p class="prose">${escape(t)}</p>`).join("");
  function dataFor(item) {
    if (!item.reader_public_third_c) throw new Error("缺少第三项C正式公开正文");
    return item.reader_public_third_c;
  }
  function heading(item) {
    return `<div class="component"><strong>军事体系表现</strong><b>${escape(dataFor(item).calculation.total_label)}</b></div>`;
  }
  function html(item, record) {
    const data = dataFor(item), c = data.calculation, review = data.contract_review;
    const commanders = `<details class="third-c-commanders"><summary>将领与本任事实</summary>${paragraphs(data.commander_profiles.note)}${data.commander_profiles.entries.map(e => `<p><a href="${escape(e.archive_href)}">${escape(e.name)} · ${escape(e.grade_label)}</a></p>${paragraphs(e.qualification_text)}${e.own_window_results.map(r => paragraphs(r.label)).join("")}`).join("")}</details>`;
    const evidence = data.evidence_items.map(e => `<li class="third-c-material" data-c-evidence="${escape(e.id)}" tabindex="-1"><details><summary>${escape(e.label)}</summary>${paragraphs(e.kind)}${paragraphs(e.text)}${e.reason ? paragraphs(e.reason) : ""}<details><summary>范围、记录与来源摘录</summary>${paragraphs(e.scope)}<p>${e.sources.map(s => link(s.path, s.label + " ↗", record)).join(" ")}</p>${(e.source_passages || []).map(p => `${p.source_subject_phase ? paragraphs(p.source_subject_phase) : ""}<blockquote>${escape(p.quote)}</blockquote>`).join("")}</details></details></li>`).join("");
    const phases = review.phase_reviews.map(p => `<details><summary>${escape(p.label)}</summary>${paragraphs(p.joint_phase_reason)}</details>`).join("");
    const tasks = review.chains.map(t => `<details><summary>${escape(t.title)}</summary>${paragraphs((t.adopted ? "纳入整体判断；" : "保留记录，未纳入采用；") + t.scope + "；" + t.result)}${t.opponent_windows.map(w => paragraphs(w.label + "；" + w.status)).join("")}<details><summary>详细裁决依据</summary>${paragraphs(t.basis)}</details></details>`).join("");
    const excluded = review.excluded_chain_reviews.map(e => `<details><summary>未采用：${escape(e.label)}</summary>${paragraphs(e.basis)}</details>`).join("");
    return `<div class="third-c-public-reading"><p class="meta">评价时期：${escape(data.window)}</p><div class="third-c-story">${paragraphs(data.story)}</div><details class="third-c-reasons"><summary>档位与档内位置</summary>${paragraphs(c.grade_path)}${paragraphs(data.position_explanation)}<details><summary>各档含义与判断方法</summary><ol start="0">${data.axes.C1.scale.map(t => `<li>${escape(t)}</li>`).join("")}</ol>${paragraphs(data.axes.C1.assessment_guide)}${paragraphs(data.assessment_scope_note)}</details></details><details><summary>本人责任与评价范围</summary>${paragraphs(data.responsibility)}${paragraphs(data.boundary)}</details>${commanders}<details class="third-c-evidence-list"><summary>战事摘要与来源（${data.evidence_items.length}条）</summary>${paragraphs(data.source_note)}<ul>${evidence}</ul></details><details class="third-c-audit"><summary>任务范围、对手与关键阶段</summary>${paragraphs(review.method)}${tasks}${phases}${excluded}${review.limitations.map(paragraphs).join("")}</details><details class="third-c-calculation"><summary>分数怎样计算</summary>${paragraphs(c.formula)}${paragraphs(c.method)}</details><p><a href="third-item-c.html#${encodeURIComponent(data.ruler_id)}">查看所有人物的军事体系表现 ↗</a></p></div>`;
  }
  if (typeof document !== "undefined") document.addEventListener("click", event => {
    const anchor = event.target.closest("a[data-c-local-evidence]");
    if (!anchor || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const root = anchor.closest(".third-c-public-reading");
    const target = root && [...root.querySelectorAll(".third-c-evidence-list [data-c-evidence]")].find(e => e.dataset.cEvidence === anchor.dataset.cLocalEvidence);
    if (!target) return;
    event.preventDefault();
    for (let parent = target.parentElement; parent && parent !== root; parent = parent.parentElement) if (parent.tagName === "DETAILS") parent.open = true;
    const materialBody = target.querySelector("details");
    if (materialBody) materialBody.open = true;
    target.scrollIntoView();
    target.focus({preventScroll: true});
  });
  globalThis.ThirdItemCReading = Object.freeze({html, heading});
})();
