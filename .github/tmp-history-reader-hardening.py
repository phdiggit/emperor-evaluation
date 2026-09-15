from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]


def write(path, text):
    path.write_text(text, encoding="utf-8", newline="\n")


# 1) Reader template: consume the current formal fields, hide audit copy, make compare ids unique,
#    and explain the two historical-impact grade scales.
template_path = ROOT / "reader/index.template.html"
template = template_path.read_text(encoding="utf-8")

helper_marker = "function axisProse(t){"
if "function historyReaderText(value){" not in template:
    if helper_marker not in template:
        raise SystemExit("axisProse marker not found")
    helpers = r'''function historyReaderText(value){
 return readerText(String(value??''))
   .replace(/\bNEGATIVE\b/g,'负向')
   .replace(/\bPOSITIVE\b/g,'正向')
   .replace(/\bMIXED\b/g,'正负混合')
   .replace(/\bHIGH\b/g,'高')
   .replace(/\bMEDIUM\b/g,'中')
   .replace(/\bLOW\b/g,'低')
   .replace(/本轮扩搜/g,'现有材料复核')
   .replace(/本轮复核/g,'现有材料复核')
   .replace(/本次复核/g,'现有材料复核')
   .replace(/当前第三项控制账/g,'现有正式控制记录')
   .replace(/项目底账/g,'现有正式材料')
   .replace(/项目正式战役群/g,'正式战役材料')
   .replace(/项目重审明确把/g,'现有裁决将')
   .replace(/项目(?:M1|M2|M4|M5|C1|C2|C3|C4|C5)明确指出/g,'相关人物画像材料指出')
   .replace(/项目(?:M1|M2|M4|M5|C1|C2|C3|C4|C5)因此把这一链裁为/g,'相关人物画像材料将这一链认定为')
   .replace(/项目(?:M1|M2|M4|M5|C1|C2|C3|C4|C5)/g,'相关人物画像材料')
   .replace(/未闭合/g,'尚未充分证明')
   .replace(/闭合/g,'已有充分证据支持')
   .replace(/不重复消费/g,'不重复计算')
   .replace(/消费/g,'计入')
   .replace(/回填/g,'归入本人')
   .replace(/分账/g,'区分责任')
   .replace(/主证/g,'主要依据')
   .replace(/不加档/g,'不额外上调')
   .replace(/抬档/g,'上调等级')
   .replace(/冲顶/g,'达到最高档')
   .replace(/取基础([SABCDE](?:[+−-])?)/g,'共同足迹对应$1级基础量级')
   .replace(/上调至内部([SABCDE](?:[+−-])?)/g,'使综合判断上调为$1')
   .replace(/内部([SABCDE](?:[+−-])?)/g,'综合判断$1')
   .replace(/公众([SABCDE](?:[+−-])?)/g,'最终等级$1')
   .replace(/不增加第二份深度/g,'不重复计入深度')
   .replace(/抬升基础/g,'提高基础影响量级');
}
function historyProse(value){return prose(historyReaderText(value))}
function sameHistoryText(a,b){
 const norm=value=>historyReaderText(value).replace(/\s+/g,' ').trim();
 return Boolean(a&&b&&norm(a)===norm(b));
}
'''
    template = template.replace(helper_marker, helpers + helper_marker, 1)

start = template.index("function impactSourceList(")
end = template.index("\n\nconst format=", start)
new_history_block = r'''function impactSourceList(r,indices,labelText='本节依据'){
 const refs=r.impact?.source_refs||[];
 const selected=[...new Set((indices||[]).filter(Number.isInteger))].map(i=>refs[i]).filter(s=>s&&!impactAuditSource(s));
 if(!selected.length)return '';
 return `<details class="impact-source-list"><summary>${esc(labelText)}</summary><ul>${selected.map(s=>{const target=s.url||s.path||'';const title=impactSourceLabel(s);const head=target?link(target,title,r):`<span>${esc(title)}</span>`;return `<li>${head}</li>`}).join('')}</ul></details>`;
}
function historySections(r,idSuffix='',compact=false){
 const h=r.impact,chains=h.macro_chains||[];
 const scopeReview=h.scope_assessment||h.scope_review||{},depthReview=h.depth_review||{},causalReview=h.causal_review||{},paradigmReview=h.paradigm_review||{};
 const scopeIndices=[...(scopeReview.source_ref_indices||[]),...chains.flatMap(c=>c.source_ref_indices||[])];
 const depthIndices=depthReview.source_ref_indices||[];
 const causalIndices=causalReview.source_ref_indices||[];
 const paradigmIndices=paradigmReview.source_ref_indices||[];
 const scopeBasis=scopeReview.actual_changes||scopeReview.basis||scopeReview.overall_grade_reasoning||h.foundation?.joint_footprint_basis||h.grade_basis||chains.map(c=>c.narrative).join('\n\n');
 const scopeLimit=[scopeReview.baseline_and_exclusions,scopeReview.observation_window?`观察范围：${scopeReview.observation_window}`:'',scopeReview.limits,scopeReview.limit,h.dimensions?.scope?.boundary_note].filter(Boolean).join('\n\n');
 const depthBasis=depthReview.basis||h.grade_basis||h.foundation?.joint_footprint_basis||chains.map(c=>c.narrative).join('\n\n');
 const depthLimit=[depthReview.limits,depthReview.limit,h.dimensions?.depth_duration?.boundary_note].filter(Boolean).join('\n\n');
 const causalBasis=causalReview.basis||causalReview.decision||h.foundation?.causal_application||h.personal_causal_boundary||'';
 const counterfactual=h.nearest_feasible_counterfactual||h.counterfactual_entry?.functional_alternative||causalReview.strongest_alternative||'';
 const showCausalBasis=causalBasis&&!sameHistoryText(causalBasis,counterfactual)?causalBasis:'';
 const personalBoundary=h.personal_causal_boundary&&!sameHistoryText(h.personal_causal_boundary,counterfactual)&&!sameHistoryText(h.personal_causal_boundary,showCausalBasis)?h.personal_causal_boundary:'';
 const causalLimit=[causalReview.limit,h.dimensions?.personal_causality?.boundary_note].filter(Boolean).join('\n\n');
 const paradigmLimit=[paradigmReview.limitation,paradigmReview.depth_separation,h.dimensions?.paradigm?.boundary_note].filter(Boolean).join('\n\n');
 const evidenceBoundary=h.confidence_basis||'';
 const hid=base=>`${base}${idSuffix}`;
 const dimension=(key,title,question,body)=>`<details id="${hid(`history-dimension-${key}`)}" class="impact-dimension-section impact-evidence-fold"><summary><span>${esc(title)}</span><span class="badge">${esc(h.dimensions?.[key]?.grade||'—')}</span></summary><p class="subline">${esc(question)}</p>${body}</details>`;
 const scopeBody=`${historyProse(scopeBasis)}${scopeLimit?`<div class="label">范围边界</div>${historyProse(scopeLimit)}`:''}${impactSourceList(r,scopeIndices,'范围与主链依据')}`;
 const depthBody=`${historyProse(depthBasis)}${depthLimit?`<div class="label">持续边界与截断点</div>${historyProse(depthLimit)}`:''}${impactSourceList(r,depthIndices,'深度依据')}`;
 const causalBody=`${showCausalBasis?`<div class="label">因果判断</div>${historyProse(showCausalBasis)}`:''}${counterfactual?`<div class="label">如果没有这个人</div>${historyProse(counterfactual)}`:''}${personalBoundary?`<div class="label">本人、团队与时代如何分工</div>${historyProse(personalBoundary)}`:''}${causalLimit?`<div class="label">因果边界</div>${historyProse(causalLimit)}`:''}${impactSourceList(r,causalIndices,'因果依据')}`;
 const paradigmBody=`${historyProse(h.paradigm_analysis)}${paradigmLimit?`<div class="label">范式边界</div>${historyProse(paradigmLimit)}`:''}${impactSourceList(r,paradigmIndices,'范式依据')}`;
 return `${compact?'':'<h2 class="evidence-card-title">历史影响依据</h2>'}<details><summary>公众总档为什么这样定？</summary>${historyProse(h.grade_basis)}</details><details class="impact-core-chains impact-evidence-fold"><summary>核心历史主链</summary><p class="subline">先看真正改变了什么，再分别判断覆盖范围、持续深度、个人归责和后世范式。</p>${chains.map(c=>`<details id="${hid(`chain-${c.chain_id}`)}"><summary>${esc(c.title)}</summary>${historyProse(c.narrative)}${impactSourceList(r,c.source_ref_indices,'本链依据')}</details>`).join('')}</details>${dimension('scope','影响范围','回答“实际改变覆盖到多大政治空间，哪些部分不能继续外推”。',scopeBody)}${dimension('depth_duration','深度与持续','回答“本人退出后，哪些结构仍继续约束后继，延续到哪里为止”。',depthBody)}${dimension('personal_causality','个人因果','回答“这些变化有多少真正依赖本人，而不是前制、臣下、时代趋势或后继者”。',causalBody)}${dimension('paradigm','政治范式','回答“后世最高权力是否真的把这个人或其治道当作榜样、反例或现实政治参照”。',paradigmBody)}<details id="${hid('history-judgment-boundary')}" class="impact-dimension-section impact-boundary impact-evidence-fold"><summary><span>判断边界</span><span class="subline">置信度 ${conf(h.confidence)}</span></summary>${evidenceBoundary?historyProse(evidenceBoundary):'<p class="subline">当前正式记录未另列补充边界。</p>'}</details><p class="sources impact-reading-links">${link(DATA.sources.impact_reader,'历史影响完整阅读页 ↗')}${link(DATA.sources.impact,'正式记录入口 ↗')}</p>`;
}'''
template = template[:start] + new_history_block + template[end:]

grade_start = template.index("function gradeHelp(kind){")
grade_end = template.index("\n}\n\nfunction comparePicker", grade_start) + 2
new_grade_help = r'''function gradeHelp(kind){
 if(kind==='impact')return `<details class="grade-help"><summary>影响等级怎样读？</summary><p>公众总档和四个维度使用两套不同的发布刻度。公众总档更粗，四维保留S−与A+等中间档；两者都表示影响量级，不是能力或功绩，也不能按字母直接一一换算或求平均。</p><p><b>公众总档</b> · ${DATA.impact_grades.join(' → ')}</p><p><b>四维档位</b> · ${(DATA.impact_dimension_grades||[]).join(' → ')}</p>${DATA.impact_grades.map(g=>`<p><b>${esc(g)}</b> · ${esc(impactMeaning[g])}</p>`).join('')}</details>`;
 return `<details class="grade-help"><summary>画像等级怎样读？</summary><p>各轴从E−到S+分18级，−／无符号／+分别表示档内下沿、中位、上沿。字母是本轴正式档位的展示，不与历史影响字母换算。</p><p>八个能力轴各看自己的行为证据；C5只评价权力运用风格与克制，不解释为能力高低。不适用、待补证、待重裁分别标明，不补零。M2经终局核对仍无可证能力者列E，并保留范围说明。</p></details>`;
}'''
template = template[:grade_start] + new_grade_help + template[grade_end:]

old_row = " const row=(label,fn)=>{const left=fn(a),right=fn(b);if(state.differences&&left===right)return '';return `<tr><td>${label}</td><td>${left}</td><td>${right}</td></tr>`};"
new_row = " const row=(label,fn)=>{const left=fn(a,0),right=fn(b,1);if(state.differences&&left===right)return '';return `<tr><td>${label}</td><td>${left}</td><td>${right}</td></tr>`};"
if old_row not in template:
    raise SystemExit("compare row helper not found")
template = template.replace(old_row, new_row, 1)

old_history_compare = "${row('主链与归责依据',r=>`<details><summary>展开历史影响依据</summary>${historySections(r)}</details>`)}"
new_history_compare = "${row('主链与归责依据',(r,i)=>`<details><summary>展开历史影响依据</summary>${historySections(r,`-compare-${i}`,true)}</details>`)}"
if old_history_compare not in template:
    raise SystemExit("compare history row not found")
template = template.replace(old_history_compare, new_history_compare, 1)
write(template_path, template)


# 2) Reader JS: use the central public-history text sanitizer and remove the now-unneeded
#    post-render section-to-details conversion.
js_path = ROOT / "reader/person-readability.js"
js = js_path.read_text(encoding="utf-8")
hs = js.index("  const historyPublicText = value =>")
he = js.index("\n\n  const netPublicText", hs)
js = js[:hs] + "  const historyPublicText = value => historyReaderText(value);" + js[he:]
fold_start = js.find("\n  function foldHistoricalImpact()")
if fold_start != -1:
    fold_end = js.index("\n  function openHistoricalImpactTarget", fold_start)
    js = js[:fold_start] + js[fold_end:]
js = js.replace("    foldHistoricalImpact();\n", "")
write(js_path, js)


# 3) Browser bootstrap needs the formal four-dimension grade order as a separate scale.
build_path = ROOT / "reader/build.py"
build = build_path.read_text(encoding="utf-8")
needle = '                  impact_grades=impact_config["public_grade_order"],\n'
replacement = needle + '                  impact_dimension_grades=impact_config["dimension_grade_order"],\n'
count = build.count(needle)
if count != 2:
    raise SystemExit(f"unexpected impact_grades occurrences: {count}")
build = build.replace(needle, replacement)
write(build_path, build)


# 4) Tests: guard the formal field mapping, audit-copy exclusion, native folding and compare ids.
test_path = ROOT / "tests/test_reader_person_readability.py"
test = test_path.read_text(encoding="utf-8")
marker = "def test_history_impact_reader_uses_dimension_navigation_without_audit_panel():"
idx = test.index(marker)
new_test = r'''def test_history_impact_reader_uses_formal_dimension_fields_without_audit_copy():
    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    template = (root / "reader" / "index.template.html").read_text(encoding="utf-8")
    public_js = (root / "reader" / "person-readability.js").read_text(encoding="utf-8")
    build = (root / "reader" / "build.py").read_text(encoding="utf-8")

    assert "h.scope_assessment||h.scope_review" in template
    assert "scopeReview.actual_changes" in template
    assert "scopeReview.baseline_and_exclusions" in template
    assert "source_review_scope" not in template
    assert "source_trace?.limit" not in template
    assert "${prose(r.impact.historical_source_notes)}" not in template
    assert "s.evidence_note" not in template
    assert "impact_dimension_grades" in template
    assert "impact_dimension_grades=impact_config" in build
    assert "historySections(r,idSuffix='',compact=false)" in template
    assert "historySections(r,`-compare-${i}`,true)" in template
    assert "impact-evidence-fold" in template
    assert "foldHistoricalImpact" not in public_js
    assert "historyReaderText(value)" in public_js


def test_historical_impact_contract_version_metadata_matches_current_contract():
    import json
    import yaml

    root = __import__("pathlib").Path(__file__).resolve().parents[1]
    project = yaml.safe_load((root / "config" / "project.yml").read_text(encoding="utf-8"))
    router = json.loads((root / "docs" / "评分结算" / "历史影响" / "01-历史影响正式结算.json").read_text(encoding="utf-8"))

    assert project["historical_impact_assessment"]["contract_version"] == "FORMAL-V1.4"
    assert router["payload_metadata"]["contract_version"] == "FORMAL-V1.4"
'''
test = test[:idx] + new_test
write(test_path, test)


# 5) Current contract version metadata was stale in the project entry and routed formal payload.
project_path = ROOT / "config/project.yml"
project = project_path.read_text(encoding="utf-8")
ps = project.index("historical_impact_assessment:")
pe = project.index("\nprofile_assessment:", ps)
segment = project[ps:pe]
if "contract_version: FORMAL-V1.2" not in segment:
    raise SystemExit("historical impact project contract version is not FORMAL-V1.2")
segment = segment.replace("contract_version: FORMAL-V1.2", "contract_version: FORMAL-V1.4", 1)
project = project[:ps] + segment + project[pe:]
write(project_path, project)

router_path = ROOT / "docs/评分结算/历史影响/01-历史影响正式结算.json"
router = json.loads(router_path.read_text(encoding="utf-8"))
if router.get("payload_metadata", {}).get("contract_version") != "FORMAL-V1.2":
    raise SystemExit("historical impact router contract version is not FORMAL-V1.2")
router["payload_metadata"]["contract_version"] = "FORMAL-V1.4"
write(router_path, json.dumps(router, ensure_ascii=False, indent=2) + "\n")


# 6) Make browser JS parsing a permanent reader-build gate, including inline scripts.
workflow_path = ROOT / ".github/workflows/reader-build.yml"
workflow = workflow_path.read_text(encoding="utf-8")
if "Check browser JavaScript syntax" not in workflow:
    behavior_marker = "      - name: Run behavior tests\n"
    if behavior_marker not in workflow:
        raise SystemExit("reader workflow behavior-test marker not found")
    syntax_step = r'''      - name: Check browser JavaScript syntax
        shell: bash
        run: |
          python - <<'PY'
          from pathlib import Path
          import re
          html = Path('reader/index.html').read_text(encoding='utf-8')
          scripts = re.findall(r'<script([^>]*)>(.*?)</script>', html, flags=re.S)
          executable = [body for attrs, body in scripts if 'application/json' not in attrs]
          if not executable:
              raise SystemExit('no executable browser scripts found')
          out = Path('.tmp/reader-js-check')
          out.mkdir(parents=True, exist_ok=True)
          for i, body in enumerate(executable):
              (out / f'{i}.js').write_text(body, encoding='utf-8')
          print('executable scripts:', len(executable))
          PY
          for file in .tmp/reader-js-check/*.js; do node --check "$file"; done
          rm -rf .tmp/reader-js-check

'''
    workflow = workflow.replace(behavior_marker, syntax_step + behavior_marker, 1)
write(workflow_path, workflow)

print("history reader hardening patch applied")
