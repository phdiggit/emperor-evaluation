"""Check local reader references with the same resolvers used by the source pages."""
from collections import defaultdict
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reader.build import ROOT, build, load_json
from reader.serve import document_page


class ArticleTree(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = None
        self.stack = []

    def handle_starttag(self, tag, attrs):
        if tag != 'article' and not self.stack:
            return
        node = {'tag': tag, 'attrs': dict(attrs), 'children': [], 'text': []}
        if self.stack:
            self.stack[-1]['children'].append(node)
            self.stack[-1]['text'].append(node)
        else:
            self.root = node
        if tag not in {'br', 'hr', 'img', 'input', 'meta', 'link', 'wbr'}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, -1, -1):
            if self.stack[i]['tag'] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.stack:
            self.stack[-1]['text'].append(data)

    def serialize(self):
        def emit(node):
            children = [emit(c) for c in node['children']]
            def text(n):
                return ''.join(x if isinstance(x, str) else text(x) for x in n['text'])
            return dict(tag=node['tag'], attrs=node['attrs'], children=children, textContent=text(node))
        return emit(self.root)


def runtime_source():
    json_template = (ROOT/'reader/json.template.html').read_text(encoding='utf-8')
    md_template = (ROOT/'reader/document.template.html').read_text(encoding='utf-8')
    functions = json_template.split('function findRecords', 1)[1].split('const params=', 1)[0]
    functions = 'function findRecords' + functions
    functions += 'function resolveFragment' + md_template.split('function resolveFragment', 1)[1].split('function fragmentTarget', 1)[0]
    return functions + r'''
const input=JSON.parse(require('fs').readFileSync(0,'utf8'));
function documentFor(tree){
 const all=[];
 function visit(n){all.push(n);n.dataset={};for(const [k,v] of Object.entries(n.attrs))if(k.startsWith('data-'))n.dataset[k.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=v;for(const c of n.children)visit(c);n.querySelectorAll=s=>select(descendants(n),s)}
 function descendants(n){return n.children.flatMap(c=>[c,...descendants(c)])}
 function select(nodes,selector){return nodes.filter(n=>selector.split(',').some(s=>{const part=s.trim().replace(/^article /,'');return part==='[data-source-line]'?Object.hasOwn(n.attrs,'data-source-line'):n.tag===part}))}
 visit(tree);return {getElementById:id=>all.find(n=>n.attrs.id===id)||null,querySelectorAll:s=>select(all,s),querySelector:s=>select(all,s)[0]};
}
const doc=input.kind==='md'?documentFor(input.data):null;
const missing=input.refs.filter(ref=>input.kind==='json'?findRecords(input.data,ref).length===0:!resolveFragment(ref,doc).target);
process.stdout.write(JSON.stringify(missing));
'''


def check_references():
    node = shutil.which('node')
    if not node:
        raise RuntimeError('Node.js is required to verify the browser reference resolvers')
    data = build(check=True)
    folder = ROOT/'.tmp/reader-reference-check'
    folder.mkdir(parents=True, exist_ok=True)
    runtime = folder/'runtime.cjs'
    runtime.write_text(runtime_source(), encoding='utf-8')
    groups = defaultdict(list)
    missing = []
    for ref, exists in data['source_availability'].items():
        if not exists:
            missing.append(ref)
            continue
        normalized = re.sub(r'\.md:(\d+)(?:-(\d+))?$', lambda m: '.md#L'+m[1]+('-L'+m[2] if m[2] else ''), ref)
        if '#' not in normalized:
            continue
        path, fragment = normalized.split('#', 1)
        if Path(path).suffix in {'.md', '.json'}:
            groups[path].append(unquote(fragment))
    for path, refs in sorted(groups.items()):
        if path.endswith('.json'):
            kind, payload = 'json', load_json(ROOT/path)
        else:
            parser = ArticleTree()
            parser.feed(document_page((ROOT/path).read_text(encoding='utf-8-sig')).decode('utf-8'))
            kind, payload = 'md', parser.serialize()
        process = subprocess.run([node, str(runtime)], input=json.dumps(dict(kind=kind, data=payload, refs=refs), ensure_ascii=False),
                                 capture_output=True, text=True, encoding='utf-8', check=True)
        missing.extend(path+'#'+fragment for fragment in json.loads(process.stdout))
    return dict(status='FAIL' if missing else 'PASS', files_checked=len(groups),
                references_checked=sum(map(len, groups.values())), unresolved=missing)


if __name__ == '__main__':
    result = check_references()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result['unresolved']))
