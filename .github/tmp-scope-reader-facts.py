from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "reader/index.template.html"
text = path.read_text(encoding="utf-8")

anchor = "function scopeGradeReason(h,chains){\n"
if "function scopeChainFacts(chains){" not in text:
    if anchor not in text:
        raise SystemExit("scopeGradeReason anchor not found")
    helper = r'''function scopeChainFacts(chains){
 return chains.map(c=>{
   const first=String(c.narrative||'').split(/\n\s*\n/)[0].trim();
   if(!first)return c.title||'';
   return c.title?`${c.title}：${first}`:first;
 }).filter(Boolean).join('\n\n');
}
'''
    text = text.replace(anchor, helper + anchor, 1)

old = " const scopeActual=scopeReview.actual_changes||chains.map(c=>c.title).filter(Boolean).join('；')||h.foundation?.joint_footprint_basis||h.grade_basis||'';"
new = " const scopeActual=scopeReview.actual_changes||scopeChainFacts(chains)||h.foundation?.joint_footprint_basis||h.grade_basis||'';"
if old not in text:
    raise SystemExit("scopeActual fallback not found")
text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8", newline="\n")

# Strengthen implementation test without fixing any ruler-specific outcome.
test_path = ROOT / "tests/test_reader_person_readability.py"
test = test_path.read_text(encoding="utf-8")
needle = '    assert "scopeUpperMeaning" in template\n'
if needle not in test:
    raise SystemExit("scope reader test anchor not found")
if '    assert "scopeChainFacts" in template\n' not in test:
    test = test.replace(needle, needle + '    assert "scopeChainFacts" in template\n    assert "scopeReview.actual_changes||scopeChainFacts(chains)" in template\n', 1)
test_path.write_text(test, encoding="utf-8", newline="\n")
print("scope factual fallback patched")
