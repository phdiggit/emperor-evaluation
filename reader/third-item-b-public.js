"use strict";

(() => {
  const escape = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const paragraphs = value => String(value ?? "").split(/\n\n+/).map(text => `<p class="prose">${escape(text)}</p>`).join("");
  function sources(refs, record) {
    return `<ul class="sources">${refs.map(ref => `<li>${escape(ref.kind)} · ${ref.url ? link(ref.url, ref.label + ' ↗', record) : ref.archive_href ? `<a href="${escape(ref.archive_href)}">${escape(ref.label)} ↗</a>` : escape(ref.label)}${ref.context ? paragraphs(ref.context) : ''}${ref.quote ? `<blockquote>${escape(ref.quote)}</blockquote>` : ''}</li>`).join('')}</ul>`;
  }
  function heading(item) {
    const data = item.reader_public_b;
    if (!data) throw new Error('缺少第三项B正式公开正文');
    return `<div class="component third-b-result" data-raw-rate="${escape(data.raw_rate)}" data-adopted-rate="${escape(data.adopted_rate)}"><strong>${escape(item.public_component_label)}</strong></div>`;
  }
  function combinationHtml(items) {
    const axes = items.filter(item => item.reader_public_b);
    const data = axes[0]?.reader_public_b;
    if (!data) return "";
    const boundary = items.find(item => item.reader_public_b?.shared_boundary)?.reader_public_b.boundary;
    const sourceNote = items.find(item => item.reader_public_b?.shared_source_note)?.reader_public_b.source_note;
    const points = items.find(item => item.label === "B80")?.value;
    const total = points == null ? "" : ` · ${escape(points)} / 80分`;
    const rules = [data.method, boundary, data.contribution_note, sourceNote].filter(Boolean).map(paragraphs).join("");
    const rates = data.rate_table.length
      ? `<details><summary>各档的低、中、高位得分率</summary>${paragraphs(data.rate_table.join("\n\n"))}</details>` : "";
    const scales = axes.filter(item => item.reader_public_b.scale.length).map(item =>
      `<h4>${escape(item.public_component_label)}</h4>${paragraphs(item.reader_public_b.scale.join("\n\n"))}`).join("");
    return `<details class="third-b-combination"><summary>控制成果小计${total}</summary>${paragraphs(data.combination)}<details><summary>各轴档位、得分率与共同规则</summary>${rules}${rates}${scales}</details></details>`;
  }
  function html(item, record, {sharedRules = false} = {}) {
    const data = item.reader_public_b;
    if (!data) throw new Error('缺少第三项B正式公开正文');
    const number = value => value == null ? '未单列' : String(value);
    const regionTable = data.regions?.length ? `<details class="third-b-regions"><summary>接班、交班的区域控制明细</summary><div class="table-wrap"><table class="b-control-table"><thead><tr><th>控制对象</th><th>接班当量</th><th>交班当量</th><th>采用范围</th></tr></thead><tbody>${data.regions.map(region => `<tr><td>${escape(region.label)}</td><td>${escape(number(region.start))}</td><td>${escape(number(region.end))}</td><td>${region.excluded ? '已排除，不作独立控制增益' : '按本项范围计入'}</td></tr>`).join('')}</tbody></table></div></details>` : '';
    const review = data.review_status ? `<p class="notice third-b-review" data-review-status="${escape(data.review_status)}">${escape(data.review_note)}</p>` : '';
    const evidence = data.evidence_items.map(entry => {
      const basis = entry.display_basis ?? entry.basis;
      return `<li><h4>${escape(entry.label)}</h4>${basis ? paragraphs(basis) : ""}<details><summary>本条判断的史料依据</summary>${sources(entry.sources, record)}</details></li>`;
    }).join('');
    const isControlScope = Array.isArray(data.regions);
    const facts = `<ul class="third-b-evidence">${evidence}</ul>`;
    const decision = `<div class="label">为什么这样评</div>${paragraphs(data.decision)}`;
    const additional = data.sources;
    const official = item.reader_source_refs?.find(ref => ref.startsWith(item.source + '#ruler_id=')) || item.source;
    const officialEntry = official ? `<p class="sources">${link(official, '查看第三项控制成果正式记录 ↗', record)}</p>` : '';
    const calculation = data.calculation === `${data.rate_note} ${data.adoption_basis}` ? "" : paragraphs(data.calculation);
    const responsibility = sharedRules ? (data.display_responsibility ?? data.responsibility) : data.responsibility;
    const scope = [responsibility, !sharedRules && data.contribution_note, (!sharedRules || !data.shared_boundary) && data.boundary]
      .filter(Boolean).map(paragraphs).join("");
    const sourceNote = sharedRules && data.shared_source_note ? "" : paragraphs(data.source_note);
    const scale = sharedRules ? "" : [...data.rate_table, ...data.scale].map(paragraphs).join("");
    const reviewExplanation = data.display_review_explanation ?? data.review_explanation;
    const measurement = sharedRules ? (data.display_control_measurement ?? data.control_measurement) : data.control_measurement;
    const scopeDetails = scope ? `<details><summary>本人贡献与采用范围</summary>${scope}</details>` : "";
    return `<div class="third-b-public-reading" data-formal-public-source><p class="meta">评价时期：${escape(data.window)}</p><div class="third-b-story">${paragraphs(data.story)}</div>${review}${isControlScope ? facts : ""}${reviewExplanation ? `<details><summary>成熟度复核的具体依据</summary>${paragraphs(reviewExplanation)}</details>` : ''}${regionTable}${scopeDetails}<details class="third-b-calculation"><summary>分数怎么算：采用率 ${escape(data.adopted_rate)}%</summary>${decision}${measurement ? paragraphs(measurement) : ""}${paragraphs(data.rate_note)}${sharedRules && data.shared_adoption_basis ? "" : paragraphs(data.adoption_basis)}${data.diagnostic_note ? paragraphs(data.diagnostic_note) : ''}${calculation}${scale ? `<details><summary>本轴各档的判定条件</summary>${scale}</details>` : ""}</details><details><summary>逐条控制依据与来源</summary>${sourceNote}${isControlScope ? "" : facts}${additional.length ? `<details><summary>补充来源</summary>${sources(additional, record)}</details>` : ""}</details>${officialEntry}</div>`;
  }
  globalThis.ThirdItemBReading = Object.freeze({html, heading, combinationHtml});
})();
