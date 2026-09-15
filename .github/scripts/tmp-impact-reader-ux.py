from pathlib import Path
import re

root = Path('.')
template_path = root / 'reader/index.template.html'
js_path = root / 'reader/person-readability.js'
css_path = root / 'reader/readability.css'
test_path = root / 'tests/test_reader_person_readability.py'

template = template_path.read_text(encoding='utf-8')

old_impact_re = re.compile(r"function impactPanel\(r\)\{.*?\}\n\nfunction axisEvidence", re.S)
new_impact = r'''function impactPanel(r){const h=r.impact;return `<section id="person-impact" class="panel impact"><div class="eyebrow">03 / 历史后效</div><h2>历史影响</h2><p class="subline">路径改变的规模、深度与归责</p><div class="big" style="color:var(--red)">${esc(h.public_grade)}</div><p>${esc(impactMeaning[h.public_grade]||'')}</p><span class="badge">${esc(h.impact_nature)}</span> <span class="subline">置信度 ${conf(h.confidence)}</span><div class="dimensions">${Object.entries(dimNames).map(([k,n])=>`<div class="impact-dimension-card"><a href="#history-dimension-${k}" data-section="history-dimension-${k}" aria-label="查看${esc(n)}依据"><span>${esc(n)}</span><b>${esc(h.dimensions[k]?.grade||'—')}</b><small>查看依据 ↓</small></a></div>`).join('')}</div>${gradeHelp('impact')}<p class="sources"><a href="#history-evidence" data-section="history-evidence">查看历史影响依据 ↓</a></p></section>`}

function axisEvidence'''
template, count = old_impact_re.subn(new_impact, template, count=1)
if count != 1:
    raise SystemExit(f'impactPanel replacement count={count}')

history_re = re.compile(r"function historySections\(r\)\{.*?\}\n\nconst format=", re.S)
new_history = r'''const impactAuditSource=s=>{
 const name=[s?.document,s?.path,s?.title,s?.kind].filter(Boolean).join(' ');
 return s?.kind==='IMPORTED_ADJUDICATION'||/裁决清单|历史审计|重审持续记录|阶段复裁|整改报告/.test(name);
};
function impactSourceLabel(s){
 if(s?.title)return s.title;
 if(s?.path)return s.path.split('/').pop();
 if(s?.document)return s.document;
 return ({LOCAL_FORMAL_DOCUMENT:'项目正式材料',HISTORICAL_WEB_SOURCE:'史料／研究来源'}[s?.kind]||'来源');
}
function impactSourceList(r,indices,labelText='本节依据'){
 const refs=r.impact?.source_refs||[];
 const selected=[...new Set((indices||[]).filter(Number.isInteger))].map(i=>refs[i]).filter(s=>s&&!impactAuditSource(s));
 if(!selected.length)return '';
 return `<details class="impact-source-list"><summary>${esc(labelText)}</summary><ul>${selected.map(s=>{const target=s.url||s.path||'';const title=impactSourceLabel(s);const head=target?link(target,title,r):`<span>${esc(title)}</span>`;const note=s.evidence_note?`<div class="subline">${esc(readerText(s.evidence_note))}</div>`:'';return `<li>${head}${note}</li>`}).join('')}</ul></details>`;
}
function impactDimensionHead(h,key,title,question){
 return `<div class="impact-dimension-head"><h3>${esc(title)}</h3><span class="badge">${esc(h.dimensions?.[key]?.grade||'—')}</span></div><p class="subline">${esc(question)}</p>`;
}
function historySections(r){
 const h=r.impact,chains=h.macro_chains||[];
 const scopeReview=h.scope_review||{},depthReview=h.depth_review||{},causalReview=h.causal_review||{},paradigmReview=h.paradigm_review||{};
 const scopeIndices=[...(scopeReview.source_ref_indices||[]),...chains.flatMap(c=>c.source_ref_indices||[])];
 const depthIndices=depthReview.source_ref_indices||[];
 const causalIndices=causalReview.source_ref_indices||[];
 const paradigmIndices=paradigmReview.source_ref_indices||[];
 const scopeBasis=scopeReview.basis||h.foundation?.joint_footprint_basis||h.grade_basis;
 const scopeLimit=[scopeReview.limits,scopeReview.limit,h.dimensions?.scope?.boundary_note].filter(Boolean).join('\n\n');
 const depthBasis=depthReview.basis||h.dimensions?.depth_duration?.boundary_note||'';
 const depthLimit=[depthReview.limits,depthReview.limit,h.dimensions?.depth_duration?.boundary_note].filter(Boolean).join('\n\n');
 const causalBasis=causalReview.basis||causalReview.decision||'';
 const counterfactual=h.nearest_feasible_counterfactual||h.counterfactual_entry?.functional_alternative||causalReview.strongest_alternative||'';
 const causalLimit=[causalReview.limit,h.dimensions?.personal_causality?.boundary_note].filter(Boolean).join('\n\n');
 const paradigmLimit=[paradigmReview.limitation,paradigmReview.depth_separation,h.dimensions?.paradigm?.boundary_note].filter(Boolean).join('\n\n');
 const evidenceBoundary=[h.confidence_basis,h.source_review_scope,h.source_trace?.limit].filter(Boolean).join('\n\n');
 return `<h2 class="evidence-card-title">历史影响依据</h2><details><summary>公众总档为什么这样定？</summary>${prose(h.grade_basis)}</details><section class="impact-core-chains"><h3>核心历史主链</h3><p class="subline">先看真正改变了什么，再分别判断覆盖范围、持续深度、个人归责和后世范式。</p>${chains.map(c=>`<details id="chain-${c.chain_id}"><summary>${esc(c.title)}</summary>${prose(c.narrative)}${impactSourceList(r,c.source_ref_indices,'本链依据')}</details>`).join('')}</section><section id="history-dimension-scope" class="impact-dimension-section">${impactDimensionHead(h,'scope','影响范围','回答“实际改变覆盖到多大政治空间，哪些部分不能继续外推”。')}${prose(scopeBasis)}${scopeLimit?`<div class="label">范围边界</div>${prose(scopeLimit)}`:''}${impactSourceList(r,scopeIndices,'范围与主链依据')}</section><section id="history-dimension-depth_duration" class="impact-dimension-section">${impactDimensionHead(h,'depth_duration','深度与持续','回答“本人退出后，哪些结构仍继续约束后继，延续到哪里为止”。')}${prose(depthBasis)}${depthLimit?`<div class="label">持续边界与截断点</div>${prose(depthLimit)}`:''}${impactSourceList(r,depthIndices,'深度依据')}</section><section id="history-dimension-personal_causality" class="impact-dimension-section">${impactDimensionHead(h,'personal_causality','个人因果','回答“这些变化有多少真正依赖本人，而不是前制、臣下、时代趋势或后继者”。')}${causalBasis?`<div class="label">因果判断</div>${prose(causalBasis)}`:''}${counterfactual?`<div class="label">如果没有这个人</div>${prose(counterfactual)}`:''}${h.personal_causal_boundary?`<div class="label">本人、团队与时代如何分账</div>${prose(h.personal_causal_boundary)}`:''}${causalLimit?`<div class="label">因果边界</div>${prose(causalLimit)}`:''}${impactSourceList(r,causalIndices,'因果依据')}</section><section id="history-dimension-paradigm" class="impact-dimension-section">${impactDimensionHead(h,'paradigm','政治范式','回答“后世最高权力是否真的把这个人或其治道当作榜样、反例或现实政治参照”。')}${prose(h.paradigm_analysis)}${paradigmLimit?`<div class="label">范式边界</div>${prose(paradigmLimit)}`:''}${impactSourceList(r,paradigmIndices,'范式依据')}</section><section id="history-judgment-boundary" class="impact-dimension-section impact-boundary"><div class="impact-dimension-head"><h3>判断边界</h3><span class="subline">置信度 ${conf(h.confidence)}</span></div>${evidenceBoundary?prose(evidenceBoundary):'<p class="subline">当前正式记录未另列补充边界。</p>'}</section><p class="sources impact-reading-links">${link(DATA.sources.impact_reader,'历史影响完整阅读页 ↗')}${link(DATA.sources.impact,'正式记录入口 ↗')}</p>`;
}

const format='''
template, count = history_re.subn(new_history, template, count=1)
if count != 1:
    raise SystemExit(f'historySections replacement count={count}')

audit_panel_re = re.compile(r'(<section id=\\"history-evidence\\" class=\\"panel evidence\\">)\$\{historySections\(r\)\}<details><summary>历史影响 · 来源与核对范围</summary>.*?</details></section>', re.S)
template, count = audit_panel_re.subn(r'\1${historySections(r)}</section>', template, count=1)
if count != 1:
    raise SystemExit(f'audit panel replacement count={count}')

template_path.write_text(template, encoding='utf-8', newline='\n')

js = js_path.read_text(encoding='utf-8')
old_rewrite = r'''  function rewriteHistoryChains(impact) {
    for (const chain of impact.macro_chains || []) {
      const box = document.getElementById(`chain-${chain.chain_id}`);
      const summary = box?.querySelector(":scope > summary");
      if (!box || !summary || box.dataset.publicNarrative === "done") continue;
      let node = summary.nextSibling;
      while (node) {
        const next = node.nextSibling;
        node.remove();
        node = next;
      }
      summary.after(fragment(prose(historyPublicText(chain.narrative))));
      box.dataset.publicNarrative = "done";
    }
  }
'''
new_rewrite = r'''  function rewriteHistoryChains(impact) {
    for (const chain of impact.macro_chains || []) {
      const box = document.getElementById(`chain-${chain.chain_id}`);
      const summary = box?.querySelector(":scope > summary");
      if (!box || !summary || box.dataset.publicNarrative === "done") continue;
      const sourceBox = Array.from(box.children).find(
        node => node.tagName === "DETAILS" && node.classList.contains("impact-source-list")
      );
      for (const node of Array.from(box.children)) {
        if (node !== summary && node !== sourceBox) node.remove();
      }
      summary.after(fragment(prose(historyPublicText(chain.narrative))));
      box.dataset.publicNarrative = "done";
    }
  }
'''
if old_rewrite not in js:
    raise SystemExit('rewriteHistoryChains source block not found')
js = js.replace(old_rewrite, new_rewrite, 1)
js_path.write_text(js, encoding='utf-8', newline='\n')

css = css_path.read_text(encoding='utf-8')
css_add = r'''

/* Historical-impact reading flow: dimension cards are navigation, evidence is dimension-first. */
.impact-dimension-card {
  padding: 0 !important;
  overflow: hidden;
}

.impact-dimension-card > a {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 2px 10px;
  align-items: center;
  min-height: 68px;
  padding: 10px 11px;
  color: inherit;
  text-decoration: none;
}

.impact-dimension-card > a:hover {
  background: color-mix(in srgb, var(--red) 6%, transparent);
}

.impact-dimension-card > a:focus-visible {
  outline-offset: -3px;
}

.impact-dimension-card > a b {
  float: none;
  width: auto;
}

.impact-dimension-card > a small {
  grid-column: 1 / -1;
  color: var(--muted);
  font-size: 11px;
}

.impact-core-chains {
  margin-top: 22px;
}

.impact-core-chains > h3,
.impact-dimension-head > h3 {
  margin: 0;
  font: 20px/1.45 "SimSun", serif;
}

.impact-dimension-section {
  scroll-margin-top: 70px;
  margin-top: 28px;
  padding-top: 22px;
  border-top: 1px solid var(--line);
}

.impact-dimension-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 3px;
}

.impact-dimension-head .badge {
  flex: 0 0 auto;
  color: var(--red);
  font: 18px/1.35 Georgia, serif;
}

.impact-dimension-section > .label {
  margin-top: 18px;
}

.impact-source-list {
  margin-top: 12px;
  padding-top: 10px;
  opacity: .9;
}

.impact-source-list > summary {
  color: var(--green);
  font-size: 13px;
}

.impact-source-list ul {
  margin: 9px 0 0;
  padding-left: 1.3em;
}

.impact-source-list li {
  margin: 8px 0;
  line-height: 1.6;
}

.impact-source-list .subline {
  margin-top: 2px;
}

.impact-boundary {
  color: color-mix(in srgb, var(--ink) 86%, var(--muted));
}

.impact-reading-links {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 24px;
}

@media (max-width: 700px) {
  .impact-dimension-card > a {
    min-height: 62px;
    padding: 9px 10px;
  }

  .impact-dimension-section {
    margin-top: 23px;
    padding-top: 18px;
  }

  .impact-dimension-head > h3 {
    font-size: 19px;
  }
}
'''
marker = '/* Historical-impact reading flow: dimension cards are navigation, evidence is dimension-first. */'
if marker not in css:
    css += css_add
css_path.write_text(css, encoding='utf-8', newline='\n')

tests = test_path.read_text(encoding='utf-8')
test_add = r'''


def test_history_impact_reader_uses_dimension_navigation_without_audit_panel():
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    template = (root / "reader" / "index.template.html").read_text(encoding="utf-8")
    public_js = (root / "reader" / "person-readability.js").read_text(encoding="utf-8")

    for target in (
        "history-dimension-scope",
        "history-dimension-depth_duration",
        "history-dimension-personal_causality",
        "history-dimension-paradigm",
    ):
        assert target in template

    assert 'data-section="history-dimension-${k}"' in template
    assert "历史影响 · 来源与核对范围" not in template
    assert "${prose(r.impact.historical_source_notes)}" not in template
    assert "source_review_scope" in template
    assert "source_trace?.limit" in template
    assert "impact-source-list" in template
    assert "IMPORTED_ADJUDICATION" in template
    assert 'node !== summary && node !== sourceBox' in public_js
'''
if 'test_history_impact_reader_uses_dimension_navigation_without_audit_panel' not in tests:
    tests += test_add
test_path.write_text(tests, encoding='utf-8', newline='\n')
