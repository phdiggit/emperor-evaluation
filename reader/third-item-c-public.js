"use strict";

(() => {
  const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const paragraphs = value => String(value ?? "").split(/\n\n+/).map(text => `<p class="prose">${escape(text)}</p>`).join("");
  function heading(item) {
    const data = item.reader_public_third_c;
    if (!data) throw new Error("缺少第三项C正式公开正文");
    return `<div class="component"><strong>军事体系表现</strong><b>${escape(data.calculation.total_label)}</b></div>`;
  }
  function material(e, record, target = false) {
    const passages = (e.source_passages || []).map(p => `<p class="meta">来源摘录（${escape(p.kind || e.kind)}）</p><blockquote>${escape(p.quote)}</blockquote>`).join("");
    return `<li class="third-c-material" data-c-evidence="${escape(e.id)}"${target ? ' tabindex="-1"' : ""}><h5>${escape(e.label)}</h5><p class="meta">${escape(e.kind)}</p>${paragraphs(e.text)}${e.reason ? `<p class="third-c-argument"><strong>为什么影响判断：</strong>${escape(e.reason)}</p>` : ""}<details><summary>本条的范围与原记录</summary>${paragraphs(e.scope)}<p class="sources">${e.sources.map(s => link(s.path, s.label + " ↗", record)).join(" ")}</p>${passages}${e.historical_source_refs?.length ? paragraphs("原登记史源：" + e.historical_source_refs.join("；")) : ""}</details></li>`;
  }
  function contractReview(r, record, data) {
    const items = new Map(data.evidence_items.map(e => [e.id, e]));
    const axisLabel = key => data.axes[key].label;
    const materialLink = ref => {
      const e = items.get(ref);
      if (!e) throw new Error("第三项C核查材料未绑定：" + ref);
      const anchor = data.ruler_id + "--evidence--" + ref;
      return `<a href="third-item-c.html#${encodeURIComponent(anchor)}" data-c-local-evidence="${escape(ref)}" title="原材料编号：${escape(ref)}">${escape(e.label + " · " + e.kind)}</a>`;
    };
    const materials = refs => refs.length ? `<ul class="third-c-judgment-materials">${[...new Set(refs)].map(ref => `<li>${materialLink(ref)}</li>`).join("")}</ul>` : `<p class="notice">此处尚无正式关联的材料，不能按名称猜配；具体缺口仍按原说明核查。</p>`;
    const glossary = `<details class="third-c-audit-terms"><summary>核查术语是什么意思？</summary><dl>${data.audit_terms.map(([term, meaning]) => `<dt>${escape(term)}</dt><dd>${escape(meaning)}</dd>`).join("")}</dl></details>`;
    const list = values => `<ul>${values.map(v => `<li>${escape(v)}</li>`).join("")}</ul>`;
    const notice = value => `<p class="notice">${escape(value)}</p>`;
    const chains = r.chains.map(c => `<details class="third-c-contract-chain" data-contract-chain="${escape(c.chain_id)}"><summary>${escape(c.title)} · ${escape(c.result_label)}</summary><p class="meta">${escape(c.consumption_text)}</p>${paragraphs("本人评价窗口：" + c.person_window)}<h5>面对什么对手？</h5>${paragraphs("链内旧称：" + c.legacy_opponent_text)}${c.opponents.length ? `<ul>${c.opponents.map(s => `<li><strong>${escape(s.label)} · ${escape(s.grade + (s.grade_range?.length ? "；现有史料审慎范围" + s.grade_range.join("—") : ""))}</strong>${notice(s.binding_status === "SOURCE_WINDOW_REVIEWED" ? "本人实际交手窗口已经回源核实" : s.binding_status === "SOURCE_OBJECT_ONLY" ? "原战事对象已核对，本人归属或任务准入存在冲突" : s.binding_status === "SOURCE_OBJECT_ONLY" ? "原战事对象已核对，本人归属或任务准入存在冲突" : s.binding_status === "SOURCE_EVIDENCE_UNDETERMINED" ? "来源已核对，组织分级仍缺具名关键事实" : s.binding_status === "PERSON_GATE_AND_TASK" ? "本人资格记录与任务对应" : "公共任务候选，尚待核对本人实际交手窗口")}${paragraphs("交手评定窗口：" + s.window)}${paragraphs(s.basis)}${s.scope_note ? paragraphs(s.scope_note) : ""}${link(s.source,"对手登记依据 ↗",record)}</li>`).join("")}</ul>` : notice("尚无可对应的公共对手O档。")}<details><summary>战争过程与原始分组（父周期）</summary>${paragraphs(c.window_note)}<ul>${c.parent_evidence.map(e=>`<li><code>${escape(e.ref)}</code>${paragraphs(e.status_text)}${e.source_refs.map(s=>link(s,"父周期来源 ↗",record)).join(" ")}</li>`).join("")}</ul>${list(c.phase_results.map(s=>s.ref + " · " + s.result_label + "（阶段参考，不另出票、不平均）"))}<p class="meta">战略链：${escape(c.chain_id)}</p></details><h5>完整任务得到什么？</h5>${paragraphs(c.result_label)}${paragraphs(c.result_basis)}<h5>本次战争已关联的材料</h5>${materials(c.evidence_refs)}${c.boundary_evidence_refs?.length ? `<h5>范围核对材料（不作本人战事采用）</h5>${materials(c.boundary_evidence_refs)}` : ""}${paragraphs("重大体系胜绩：" + (c.major_success ? "有" : "未登记") + "；重大体系失败：" + (c.major_failure ? "有" : "未登记"))}<h5>与三方面判断怎样相连？</h5><ul>${Object.entries(c.axis_links).flatMap(([key, values]) => values.map(v => `<li><strong>${escape(axisLabel(key))}</strong>：${escape(v.reason)}（对应材料：${materialLink(v.evidence_ref)}）</li>`)).join("")}</ul>${list(c.gaps)}${c.evidence_sources.map(s=>link(s.path,s.label + " ↗",record)).join(" ")}</details>`).join("");
    const axes = Object.entries(r.axes).map(([key,a]) => `<section class="third-c-adjacent-boundary" data-contract-axis="${escape(key)}"><h4>${escape(axisLabel(key))} · ${escape(a.grade_label)}的分界审查</h4>${notice(a.status_text)}${paragraphs("本档要求：" + a.criterion)}${paragraphs(a.support)}${paragraphs(a.against_lower)}${paragraphs(a.against_upper)}${paragraphs(a.counterevidence_review)}${list(a.limitations)}<h5>本轴正式关联的材料（含相邻档说明）</h5>${materials([...a.evidence_refs, ...(a.authored_finding_evidence_refs || [])])}</section>`).join("");
    const inherited = r.inheritance ? `<details><summary>继承体系的基线、延续与反证</summary>${paragraphs(r.inheritance.baseline_window)}${list(r.inheritance.counterevidence_review.map(x=>x.basis))}${r.inheritance.baseline_source_refs.map(s=>link(s,"基线来源 ↗",record)).join(" ")}</details>` : "";
    const qualification = paragraphs(r.gate_explanation) + paragraphs("具名将领资格记录：" + (r.gate_commander_names.join("、") || "未登记")) + paragraphs("方向资格记录：" + (r.gate_directions.map(s=>s.direction).join("、") || "未登记")) + list(r.task_aliases.map(s=>s.basis));
    const excluded = r.excluded_chain_reviews?.length ? `<details class="third-c-excluded-tasks"><summary>已排除的错归任务（不计分）</summary>${list(r.excluded_chain_reviews.map(e => e.label + "：" + e.basis))}</details>` : "";
    return `<section class="third-c-contract-review" data-contract-reading><h3>对手、完整任务与相邻档分界</h3>${glossary}${paragraphs(data.audit_link_note)}${paragraphs(r.summary)}${paragraphs(r.method)}<details><summary>对手O档怎么看？</summary><ol>${r.o_scales.map(s => `<li><strong>${escape(s.grade)} ${escape(s.label)}</strong>：${escape(s.definition)}</li>`).join("")}</ol></details><details><summary>已登记的本人对手与资格依据</summary>${paragraphs(r.person_gate_note)}${r.person_opponent_gate_records.length ? list(r.person_opponent_gate_records.map(s => s.opponent_label + " · " + s.organization_grade)) : notice("没有具名登记，不能用空白认定对手低档。")}${qualification}</details>${inherited}${excluded}<details><summary>逐条完整战争及证据分组（战略链、父周期；${r.chains.length}条）</summary>${chains}</details>${axes}${paragraphs(r.return_note)}${notice(r.conclusion)}</section>`;
  }
  function commanderProfiles(data) {
    if (!data) return "";
    const entries = data.entries.map(e => {
      const title = e.name + " · " + e.grade_label + (e.grade_note ? "（" + e.grade_note + "）" : "") + (e.qualification_status === "IDENTITY_PENDING" ? " · " + (e.dynasty || "") : "");
      const results = e.own_window_results.length ? `<details><summary>本任已核准的显著成果</summary><ul>${e.own_window_results.map(r => `<li>${escape(r.label)} · ${escape(r.tier)}</li>`).join("")}</ul></details>` : "";
      return `<li><a href="${escape(e.archive_href)}">${escape(title)} ↗</a><p class="meta">${escape(e.qualification_text)}</p>${results}</li>`;
    }).join("");
    return `<section class="third-c-commanders"><h5>将领档位与本任成果</h5><p class="meta">${escape(data.note)}</p>${entries ? `<ul>${entries}</ul>` : `<p class="meta">本段未列具体将领；执行过程见下方战事材料。<a href="military.html">浏览军事人才档案 ↗</a></p>`}</section>`;
  }
  function html(item, record) {
    const data = item.reader_public_third_c;
    if (!data) throw new Error("缺少第三项C正式公开正文");
    const c = data.calculation;
    const axes = Object.entries(data.axes).map(([key, axis]) => `<section class="third-c-axis" data-axis="${escape(key)}"><h4>${escape(axis.label)} · ${escape(axis.grade_label)}</h4><p class="third-c-review-status" data-review-status="${escape(axis.review_status)}">分界论证：${escape(axis.review_label)}。${escape(axis.review_text)}</p>${paragraphs(axis.basis)}${axis.assessment_guide ? `<details class="third-c-assessment-guide"><summary>目标未完成时，怎样判断实战表现？</summary>${paragraphs(axis.assessment_guide)}</details>` : ""}${key === "C3" ? commanderProfiles(axis.commander_profiles) : ""}${axis.evidence_note ? `<p class="notice third-c-evidence-gap">${escape(axis.evidence_note)}</p>` : ""}${axis.materials.length ? `<details class="third-c-arguments"><summary>具体战事与定档作用（${axis.materials.length}条）</summary><ol>${axis.materials.map(e => material(e, record)).join("")}</ol></details>` : ""}<details><summary>本轴各档含义</summary><ol start="0">${axis.scale.map(text => `<li>${escape(text)}</li>`).join("")}</ol></details></section>`).join("");
    const evidence = data.evidence_items.map(e => material(e, record, true)).join("");
    const overview = Object.values(data.axes).map(axis => `<div><span>${escape(axis.label)}</span><strong>${escape(axis.grade_label)}</strong><small class="third-c-review-status" data-review-status="${escape(axis.review_status)}">分界论证：${escape(axis.review_label)}</small></div>`).join("");
    return `<div class="third-c-public-reading" data-formal-public-source><p class="meta">评价时期：${escape(data.window)}</p><p class="notice third-c-scope-note">${escape(data.assessment_scope_note)}</p><div class="third-c-story">${paragraphs(data.story)}</div><p class="meta third-c-review-note">${escape(data.review_note)}</p><div class="third-c-overview" aria-label="三方面的正式判断">${overview}</div><details class="third-c-reasons"><summary>为什么这样评价？</summary>${axes}</details><details><summary>本人责任与评价范围</summary>${paragraphs(data.responsibility)}${paragraphs(data.boundary)}</details><details class="third-c-evidence-list"><summary>查看战事材料与来源</summary>${paragraphs(data.source_note)}<ul>${evidence}</ul></details><details class="third-c-audit"><summary>深入核对：对手、完整任务与档位分界</summary>${contractReview(data.contract_review,record,data)}</details><details class="third-c-calculation"><summary>查看规则与分数计算</summary>${paragraphs(c.grade_path)}${paragraphs(c.cap_reason)}${paragraphs(c.outcome_text)}${paragraphs(c.position)}${paragraphs(c.formula)}<details><summary>共同计算规则</summary>${paragraphs(c.method)}</details></details><p><a href="third-item-c.html#${encodeURIComponent(data.ruler_id)}">查看所有人物的军队表现 ↗</a></p></div>`;
  }
  if (typeof document !== "undefined") document.addEventListener("click", event => {
    const anchor = event.target.closest("a[data-c-local-evidence]");
    if (!anchor || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const root = anchor.closest(".third-c-public-reading");
    const target = root && [...root.querySelectorAll(".third-c-evidence-list [data-c-evidence]")].find(e => e.dataset.cEvidence === anchor.dataset.cLocalEvidence);
    if (!target) return; // Keep the canonical collection URL as a working fallback.
    event.preventDefault();
    for (let parent = target.parentElement; parent && parent !== root; parent = parent.parentElement) {
      if (parent.tagName === "DETAILS") parent.open = true;
    }
    target.scrollIntoView();
    target.focus({preventScroll: true});
  });
  globalThis.ThirdItemCReading = Object.freeze({html, heading});
})();
