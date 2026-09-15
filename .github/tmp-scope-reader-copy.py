from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write(path, text):
    path.write_text(text, encoding="utf-8", newline="\n")


template_path = ROOT / "reader/index.template.html"
template = template_path.read_text(encoding="utf-8")

# Explain scope grades in audience language, using the already-settled grade and formal main-chain titles.
impact_anchor = "const impactMeaning={'S+':'文明／国家主路径重塑',S:'超重大历史影响',A:'重大长期历史影响',B:'重大历史影响',C:'显著历史影响',D:'有限但真实影响',E:'弱历史影响'};\n"
if "const scopeGradeMeaning=" not in template:
    if impact_anchor not in template:
        raise SystemExit("impactMeaning anchor not found")
    scope_maps = r'''const scopeGradeMeaning={
 'S+':'主体核心与多个主要外围政治空间共同发生极大规模重组，属于本体系可以由史实证明的最高覆盖量级。',
 S:'全国国家整体转型并伴随重要外部空间变化，或多个大型政治空间发生广泛重组。',
 'S-':'中国核心政治空间或同量级政治空间的大部发生实质变化；已经明显超过单一政策、单一集团或局部区域。',
 'A+':'多个大区域或全国重要领域出现实质变化，但尚未达到核心政治空间大部重组的量级。',
 A:'大型王朝关键中枢、重要部分或多个重要区域发生实质变化。',
 B:'重要区域、制度领域或精英政治圈层发生真实变化，但覆盖仍有限。',
 C:'变化主要局限于局部地区、单一集团或短窄领域。'
};
const scopeUpperMeaning={
 'S+':'S+已经是范围最高档。仍然只计算本人窗口内实际改变的政治空间，不把后世继续沿用、制度寿命或未被改变的外围空间追加进来。',
 S:'再上到S+，需要主体核心与多个主要外围政治空间共同发生极大规模重组；仅有全国整体转型或若干外围变化还不够。',
 'S-':'再上到S，必须证明全国整体转型还伴随重要外部空间变化，或多个大型政治空间发生广泛重组。后世沿用多久属于“深度”，不能拿来抬高“范围”。',
 'A+':'再上到S-，必须达到核心政治空间大部实质变化，或跨多个大型区域国家达到同量级重组；全国实施一个重要领域本身不够。',
 A:'再上到A+，必须证明变化实际扩展到多个大区域或全国重要领域；仅因身处最高中枢、涉及帝位或最高官员并不自动升级。',
 B:'再上到A，需要达到大型王朝关键中枢、主要区域国家或多个重要区域的实质变化。',
 C:'再上到B，需要影响至少扩展到重要区域、制度领域或精英政治圈层。'
};
function scopeGradeReason(h,chains){
 const grade=h.dimensions?.scope?.grade||'—';
 const titles=chains.map(c=>c.title).filter(Boolean);
 const footprint=titles.length?`正式主链包括：${titles.join('；')}。`:'';
 const meaning=scopeGradeMeaning[grade]||'';
 return `${footprint}${grade}档的范围门槛是：${meaning}`;
}
'''
    template = template.replace(impact_anchor, impact_anchor + scope_maps, 1)

# Remove revision/version/batch language from all public historical-impact prose.
old_process = "   .replace(/本轮扩搜/g,'现有材料复核')\n   .replace(/本轮复核/g,'现有材料复核')\n   .replace(/本次复核/g,'现有材料复核')\n"
new_process = r"""   .replace(/V\d+(?:\.\d+)?(?:补证与边界|补证|复核|重审|修订|更新)[：:]\s*/g,'')
   .replace(/(?:^|[。\n])\s*(?:本轮|本次)(?:扩搜|复核|重审|修订)[^。]*。?/g,'$1')
   .replace(/项目重审明确把/g,'')
"""
if old_process not in template:
    raise SystemExit("history process sanitizer anchor not found")
template = template.replace(old_process, new_process, 1)

# Rebuild the scope subsection as: actual changes -> why this grade -> why not higher -> observation window.
old_scope_calc = r""" const scopeBasis=scopeReview.actual_changes||scopeReview.basis||scopeReview.overall_grade_reasoning||h.foundation?.joint_footprint_basis||h.grade_basis||chains.map(c=>c.narrative).join('\
\
');
 const scopeLimit=[scopeReview.baseline_and_exclusions,scopeReview.observation_window?`观察范围：${scopeReview.observation_window}`:'',scopeReview.limits,scopeReview.limit,h.dimensions?.scope?.boundary_note].filter(Boolean).join('\
\
');
"""
new_scope_calc = r""" const scopeGrade=h.dimensions?.scope?.grade||'—';
 const scopeActual=scopeReview.actual_changes||chains.map(c=>c.title).filter(Boolean).join('；')||h.foundation?.joint_footprint_basis||h.grade_basis||'';
 const scopeWhy=scopeReview.overall_grade_reasoning||scopeReview.basis||scopeGradeReason(h,chains);
 const scopeCeiling=[scopeReview.baseline_and_exclusions,scopeReview.limits,scopeReview.limit,h.dimensions?.scope?.boundary_note,scopeUpperMeaning[scopeGrade]].filter(Boolean).join('\
\
');
 const scopeWindow=scopeReview.observation_window||'';
"""
if old_scope_calc not in template:
    raise SystemExit("scope calculation block not found")
template = template.replace(old_scope_calc, new_scope_calc, 1)

old_scope_body = " const scopeBody=`${historyProse(scopeBasis)}${scopeLimit?`<div class=\\\"label\\\">范围边界</div>${historyProse(scopeLimit)}`:''}${impactSourceList(r,scopeIndices,'范围与主链依据')}`;\n"
new_scope_body = " const scopeBody=`<div class=\\\"label\\\">实际改变了什么</div>${historyProse(scopeActual)}<div class=\\\"label\\\">为什么是 ${esc(scopeGrade)}</div>${historyProse(scopeWhy)}${scopeCeiling?`<div class=\\\"label\\\">为什么没有更高</div>${historyProse(scopeCeiling)}`:''}${scopeWindow?`<div class=\\\"label\\\">判断采用的时间窗口</div>${historyProse(scopeWindow)}`:''}${impactSourceList(r,scopeIndices,'范围依据')}`;\n"
if old_scope_body not in template:
    raise SystemExit("scope body line not found")
template = template.replace(old_scope_body, new_scope_body, 1)

write(template_path, template)

# Update implementation tests: public reader must explain scope grade and strip revision-process labels.
test_path = ROOT / "tests/test_reader_person_readability.py"
test = test_path.read_text(encoding="utf-8")
old_assertions = '''    assert "source_review_scope" not in template\n    assert "source_trace?.limit" not in template\n    assert "scope_assessment||h.scope_review" in template\n    assert "impact_dimension_grades" in template\n'''
new_assertions = '''    assert "source_review_scope" not in template\n    assert "source_trace?.limit" not in template\n    assert "scope_assessment||h.scope_review" in template\n    assert "impact_dimension_grades" in template\n    assert "scopeGradeMeaning" in template\n    assert "scopeUpperMeaning" in template\n    assert "为什么是 ${esc(scopeGrade)}" in template\n    assert "为什么没有更高" in template\n    assert "V\\\\d+(?:\\\\.\\\\d+)?(?:补证与边界|补证|复核|重审|修订|更新)" in template\n'''
if old_assertions not in test:
    raise SystemExit("test assertion block not found")
test = test.replace(old_assertions, new_assertions, 1)
write(test_path, test)

print("scope/public-copy reader patch applied")
