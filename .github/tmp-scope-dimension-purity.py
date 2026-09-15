from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def write(path, text):
    path.write_text(text, encoding="utf-8", newline="\n")

path = ROOT / "reader/index.template.html"
text = path.read_text(encoding="utf-8")
old = r'''function scopeChainFacts(chains){
 return chains.map(c=>{
   const first=String(c.narrative||'').split(/\n\s*\n/)[0].trim();
   if(!first)return c.title||'';
   return c.title?`${c.title}：${first}`:first;
 }).filter(Boolean).join('\n\n');
}
'''
new = r'''const scopeFactTerms=/政治空间|全国|全国化|跨地域|区域|疆域|边疆|郡县|封国|政权|统一国家|国家结构|国家整体|政治主体|中央官僚|皇帝主权|标准化|控制关系|服从关系|对外秩序|合并|割据|重组|覆灭|新征服地区/;
const scopeCausalTerms=/归给|归责|不可替代|可替代|拍板|臣僚|团队|前制|功劳|信用|本人|个人因果|删除|反事实|替代者|共享归责|倒灌|最高权力|由谁|谁来/;
const scopeNonActualTerms=/是否|争论|方案|模板|概率|可能|未必|不足以|趋势|之前存在|既有|基础量级|门槛|档位/;
function scopeFactClauses(value){
 const sentences=String(value||'').match(/[^。！？]+[。！？]?/g)||[];
 const kept=[];
 for(const sentence of sentences){
   const clauses=sentence.replace(/[。！？]+$/,'').split(/[，；]/);
   for(let clause of clauses){
     clause=clause.trim()
       .replace(/^真正高不可替代性的部分，是/,'')
       .replace(/^真正[^，；。]{0,24}的部分，是/,'')
       .replace(/^(?:而)?[^，；。]{1,16}在[^，；。]{0,20}把/,'')
       .replace(/^(?:而)?[^，；。]{1,16}把/,'')
       .replace(/^(?:但|而|因此|所以)/,'')
       .trim();
     if(!clause||!scopeFactTerms.test(clause))continue;
     if(scopeCausalTerms.test(clause)||scopeNonActualTerms.test(clause))continue;
     kept.push(clause);
   }
 }
 return [...new Set(kept)];
}
function scopeChainFacts(chains){
 const rows=[];
 for(const c of chains){
   const facts=scopeFactClauses(c.narrative);
   if(!facts.length)continue;
   rows.push(c.title?`${c.title}：${facts.join('；')}。`:`${facts.join('；')}。`);
 }
 if(rows.length)return rows.join('\n\n');
 const titles=chains.map(c=>c.title).filter(Boolean);
 return titles.length?`正式主链涉及：${titles.join('；')}。`:'';
}
'''
if text.count(old) != 1:
    raise SystemExit(f"scopeChainFacts block count={text.count(old)}")
text = text.replace(old, new, 1)
write(path, text)

test_path = ROOT / "tests/test_reader_person_readability.py"
test = test_path.read_text(encoding="utf-8")
anchor = '    assert "scopeChainFacts" in template\n'
extra = ('    assert "scopeFactClauses" in template\n'
         '    assert "scopeCausalTerms" in template\n'
         '    assert "不可替代|可替代|拍板|臣僚|团队|前制" in template\n')
if extra not in test:
    if anchor not in test:
        raise SystemExit("test anchor missing")
    test = test.replace(anchor, anchor + extra, 1)
write(test_path, test)
print("scope dimension purity patch applied")
