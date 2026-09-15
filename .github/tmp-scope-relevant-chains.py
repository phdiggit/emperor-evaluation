from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def write(path, text):
    path.write_text(text, encoding="utf-8", newline="\n")

path = ROOT / "reader/index.template.html"
text = path.read_text(encoding="utf-8")
old = r'''function scopeGradeReason(h,chains){
 const grade=h.dimensions?.scope?.grade||'—';
 const titles=chains.map(c=>c.title).filter(Boolean);
 const footprint=titles.length?`正式主链包括：${titles.join('；')}。`:'';
 const meaning=scopeGradeMeaning[grade]||'';
 return `${footprint}${grade}档的范围门槛是：${meaning}`;
}
'''
new = r'''function scopeRelevantChains(chains){
 return chains.filter(c=>scopeFactClauses(c.narrative).length);
}
function scopeGradeReason(h,chains){
 const grade=h.dimensions?.scope?.grade||'—';
 const titles=scopeRelevantChains(chains).map(c=>c.title).filter(Boolean);
 const footprint=titles.length?`与范围直接相关的正式主链：${titles.join('；')}。`:'';
 const meaning=scopeGradeMeaning[grade]||'';
 return `${footprint}${grade}档的范围门槛是：${meaning}`;
}
'''
if text.count(old) != 1:
    raise SystemExit(f"scopeGradeReason block count={text.count(old)}")
text = text.replace(old, new, 1)
old_indices = " const scopeIndices=[...(scopeReview.source_ref_indices||[]),...chains.flatMap(c=>c.source_ref_indices||[])];\n"
new_indices = " const scopeChains=scopeRelevantChains(chains);\n const scopeIndices=[...(scopeReview.source_ref_indices||[]),...scopeChains.flatMap(c=>c.source_ref_indices||[])];\n"
if text.count(old_indices) != 1:
    raise SystemExit(f"scopeIndices line count={text.count(old_indices)}")
text = text.replace(old_indices, new_indices, 1)
write(path, text)

test_path = ROOT / "tests/test_reader_person_readability.py"
test = test_path.read_text(encoding="utf-8")
anchor = '    assert "scopeCausalTerms" in template\n'
extra = ('    assert "scopeRelevantChains" in template\n'
         '    assert "scopeChains.flatMap(c=>c.source_ref_indices||[])" in template\n')
if extra not in test:
    if anchor not in test:
        raise SystemExit("test anchor missing")
    test = test.replace(anchor, anchor + extra, 1)
write(test_path, test)
print("scope relevant-chain isolation patched")
