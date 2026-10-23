"""Build and verify the formal public projection for Second Item C1-C4."""
from __future__ import annotations

import copy
import json
import re
import posixpath
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.formal_json_store import (
    load_json,
    load_ruler_polities,
    write_json,
)


FORMAL_PATHS = {
    "C1": Path("docs/评分结算/净收益/第二项治国净收益/财政民生/01-C1正式结算.json"),
    "C2": Path("docs/评分结算/净收益/第二项治国净收益/财政民生/02-C2正式结算.json"),
    "C3": Path("docs/评分结算/净收益/第二项治国净收益/财政民生/03-C3正式结算.json"),
    "C4": Path("docs/评分结算/净收益/第二项治国净收益/财政民生/04-C4正式结算.json"),
}
CONTRACT_PATH = Path("docs/分项规则/第二项治国净收益/财政民生/00-规则与结算合同.md")
PUBLIC_PROJECTION_SCHEMA = "second-item-c-authored-public-v3"
AXES = ("C1", "C2", "C3", "C4")
STATE_AXES = ("C1", "C2", "C3")

PUBLIC_EVIDENCE_FIELDS = (
    "id",
    "public_label",
    "public_role",
    "public_basis",
    "public_boundary",
    "source_refs",
    "evidence_mode",
    "public_scope",
    "source_binding_kind",
)
PUBLIC_ROLES = {
    "主要状态",
    "低谷",
    "边界",
    "恢复",
    "责任范围",
    "状态恶化",
    "额外代价",
}

AXIS_NAMES = {
    "C1": "民生",
    "C2": "经济财政",
    "C3": "社会安全",
}
STATE_LABELS = {
    "C1": {
        1: "崩溃",
        2: "广泛困顿",
        3: "基本维持",
        4: "普遍温饱",
        5: "富庶",
        6: "极盛",
    },
    "C2": {
        1: "失灵崩解",
        2: "汲取脆弱",
        3: "基本运行",
        4: "健康稳定",
        5: "富实强健",
        6: "结构顶峰",
    },
    "C3": {
        1: "广域失序",
        2: "持续脆弱",
        3: "可运行秩序",
        4: "总体稳定",
        5: "长期高位",
        6: "结构顶峰",
    },
}
LOSS_LABELS = {
    "L0": "未另证独立有效低谷",
    "L1": "已证损害，按已证范围作有限修正",
    "L2": "重要地区或群体出现明显损害",
    "L3": "严重且广泛或长期反复的本轴损害",
}
DA_LABELS = {
    "DA0": "未确认独立的额外民力成本",
    "DA1": "有限的额外民力成本",
    "DA2": "显著的额外民力成本",
    "DA3": "严重的额外民力成本",
    "DA4": "极重的额外民力成本",
    "DA5": "接近系统性汲取的额外民力成本",
    "DA6": "灾难级的额外民力成本",
}

AXIS_BOUNDARIES = {
    "C1": "这里只展示普通家庭的衣食、家庭负担与家庭形成结果；战争胜负、纯军事损失、制度设计和后续继任结果不在本轴重复计算。",
    "C2": "这里只展示生产、市场货币、常规税基与储备结果；家庭生活结果、治安司法、战争成本、恢复过程和制度设计不在本轴重复计算。",
    "C3": "这里只展示居民人身财产安全、基层秩序与司法救济结果；外部军事安全、粮价储备、制度设计和政权存续不在本轴重复计算。",
}
C4_BOUNDARY = "这里只展示本人责任期内的保留恢复、状态变化和独立额外民力成本；三个绝对状态轴、纯军事投入及同一已计后果不在本轴重复计算。"
RECOVERY_BOUNDARY = "只有任期结束时仍保留的改善进入恢复结果；短暂峰值、单纯止损和绝对状态本身不重复计算。"
RESPONSIBILITY_BOUNDARY = "恢复责任按实际权力分工判断，不从名义身份、结果好坏或继任结果反推。"
DETERIORATION_BOUNDARY = "只比较接手到任期结束的可比状态；灾害、失权后的新损害和他人责任不直接归入本人。"
COST_BOUNDARY = "只保留已证的独立民力、生产机会或民间财产负担；纯军事投入和同一已计后果不重复计算。"

PUBLIC_FORBIDDEN_RE = re.compile(
    r"(?:"
    r"(?<![A-Za-z0-9])(?:C[1-4](?:-[1-6])?|C4T-[1-6]|L[0-3]|DA[0-6]|"
    r"S_(?:0|main|end|avg)|FULL|SHARED|NONE|RAW|M3)(?![A-Za-z0-9])|"
    r"(?<![A-Za-z0-9])[A-Za-z]+_[A-Za-z0-9_]+(?![A-Za-z0-9])|"
    r"C1\s*[—/-]\s*C3|C1\s*[、/]\s*C2|"
    r"主档|主态|低谷修正|门槛|闭合|消费|净账|父链|版本史|归责|"
    r"审计|正式结算|重审|重裁|本轮|恢复原|净分|终局层级|"
    r"(?<![A-Za-z0-9])V[0-9]+(?![A-Za-z0-9])|"
    r"governance|review|basis|source|status"
    r")",
    flags=re.IGNORECASE,
)


def _clean(value: object) -> str:
    """Use explicit upstream wording without deleting facts or conditions."""
    from emperor_v4.evaluation.second_item_c_public_language import translate

    text = str(value or "").replace("`", "").replace("\r\n", "\n").replace("\r", "\n")
    text = translate(text, states=STATE_LABELS, losses=LOSS_LABELS, costs=DA_LABELS)
    text = text.replace("。；", "。\n\n").replace("。。", "。")
    return re.sub(r"[ \t]+", " ", text).strip()


def _records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("scores") or payload.get("records") or []
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("C1-C4正式公开投影的记录集合无效")
    return rows


def _projection_keys() -> set[str]:
    return {
        "public_source_note_catalog",
        "public_projection_schema_version",
        "public_projection_status",
        "public_projection_axis",
        "public_projection_record_count",
        "public_projection_evidence_item_count",
        "public_projection_source",
    }


def _scoring_signature(payload: dict[str, Any]) -> str:
    snapshot = copy.deepcopy(payload)
    rows = snapshot.get("scores") or snapshot.get("records") or []
    for row in rows:
        if isinstance(row, dict):
            for key in ("public_adjudication_summary", "public_evidence_items", "public_story",
                        "public_boundary", "public_loss_label", "public_calculation", "public_source_documents",
                        "public_related_source_refs", "public_source_note", "public_source_note_ref", "public_reading_sections"):
                row.pop(key, None)
    for key in _projection_keys():
        snapshot.pop(key, None)
    return json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _refresh_payload(axis: str, payload: dict[str, Any]) -> dict[str, Any]:
    before_signature = _scoring_signature(payload)
    rows = _records(payload)
    evidence_count = 0
    for row in rows:
        reading = row
        if axis == 'C4':
            from emperor_v4.evaluation.second_item_c_reading import recovery_public_record
            reading = recovery_public_record(row)
            row.pop('public_story', None)
        items = row.get("public_evidence_items")
        if not isinstance(items, list) or not items:
            raise ValueError(f"第二项{axis}缺少直接维护的逐条公开依据：{row.get('ruler_name')}")
        for field in ("public_story", "public_adjudication_summary", "public_boundary", "public_loss_label"):
            if not isinstance(reading.get(field), str) or not reading[field].strip():
                raise ValueError(f"第二项{axis}缺少直接维护的公开正文：{row.get('ruler_name')}/{field}")
        from emperor_v4.evaluation.second_item_c_reading import calculation
        calculation(axis, row)
        row.pop('public_calculation', None)
        evidence_count += len(items)
    if _scoring_signature(payload) != before_signature:
        raise ValueError(f"第二项{axis}公开字段迁移意外改变了正式评分字段")
    payload["public_projection_schema_version"] = PUBLIC_PROJECTION_SCHEMA
    payload["public_projection_status"] = "FORMAL_UPSTREAM_SOURCE"
    payload["public_projection_axis"] = axis
    payload["public_projection_record_count"] = len(rows)
    payload["public_projection_evidence_item_count"] = evidence_count
    payload["public_projection_source"] = {
        "formal_contract": CONTRACT_PATH.as_posix(),
        "identity": "正文、定档理由、范围与逐条史源直接维护在正式记录；刷新只同步计算说明、元数据及同值阅读视图",
        "reader_policy": "reader逐字展示正式公开字段；不改写句子、不猜史源、不重算分数",
    }
    from emperor_v4.evaluation.second_item_c_source_notes import compact_source_notes
    return compact_source_notes(payload)


def _verify_payload(axis: str, payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("public_projection_schema_version") != PUBLIC_PROJECTION_SCHEMA:
        raise ValueError(f"第二项{axis}缺少正式公开投影schema标记")
    if payload.get("public_projection_status") != "FORMAL_UPSTREAM_SOURCE":
        raise ValueError(f"第二项{axis}公开投影不是正式上游真源")
    if payload.get("public_projection_axis") != axis:
        raise ValueError(f"第二项{axis}公开投影轴标记不一致")
    from emperor_v4.evaluation.second_item_c_source_notes import source_note_records
    rows = source_note_records(payload)
    if payload.get("public_projection_record_count") != len(rows):
        raise ValueError(f"第二项{axis}公开投影人物计数不一致")
    all_ids: set[str] = set()
    evidence_count = 0
    for row in rows:
        name = str(row.get("ruler_name") or row.get("ruler_id"))
        from emperor_v4.evaluation.second_item_c_reading import calculation_record
        row = calculation_record(axis, row)
        if axis == 'C4':
            from emperor_v4.evaluation.second_item_c_reading import verify_recovery_reading, recovery_public_record
            if 'public_story' in row:
                raise ValueError('第二项C4只保存阅读分栏，不得另存拼接正文副本')
            verify_recovery_reading(row)
            row = recovery_public_record(row)
        actual = row.get("public_evidence_items")
        related = row.get('public_related_source_refs')
        if not isinstance(related, list) or not isinstance(row.get('public_source_note'), str) or not row['public_source_note'].strip():
            raise ValueError(f"第二项{axis}材料汇集与引用说明缺失：{name}")
        if not isinstance(actual, list) or not actual:
            raise ValueError(f"第二项{axis}公开条目数量不完整：{name}")
        ids = [str(item.get("id") or "") for item in actual if isinstance(item, dict)]
        if len(ids) != len(actual) or len(ids) != len(set(ids)) or any(not value for value in ids):
            raise ValueError(f"第二项{axis}公开条目ID不唯一或缺失：{name}")
        if all_ids & set(ids):
            raise ValueError(f"第二项{axis}公开条目ID跨人物重复：{name}")
        all_ids.update(ids)
        for item in actual:
            if not isinstance(item, dict) or set(item) != set(PUBLIC_EVIDENCE_FIELDS):
                raise ValueError(f"第二项{axis}公开条目字段不完整：{name}")
            if not str(item["id"]).startswith(f"{axis}-PUBLIC-"):
                raise ValueError(f"第二项{axis}公开条目ID不稳定：{name}")
            if item["public_role"] not in PUBLIC_ROLES:
                raise ValueError(f"第二项{axis}公开角色非法：{name}")
            if item['evidence_mode'] not in {'DIRECT', 'INFERRED', 'ASSESSMENT', 'BACKGROUND', 'EXCLUDED'}:
                raise ValueError(f"第二项{axis}公开证据性质缺失：{name}")
            if not isinstance(item['public_scope'], str) or not item['public_scope'].strip():
                raise ValueError(f"第二项{axis}逐条采用范围缺失：{name}")
            if item['evidence_mode'] == 'INFERRED' and not re.search('推断|推定', item['public_basis']):
                raise ValueError(f"第二项{axis}推断必须在正文明确说明：{name}")
            for field in ("public_label", "public_role", "public_basis"):
                value = item[field]
                if not isinstance(value, str) or not value.strip() or PUBLIC_FORBIDDEN_RE.search(value):
                    raise ValueError(f"第二项{axis}公开字段含空值或内部术语：{name}/{field}")
            boundary = item["public_boundary"]
            if boundary is not None and (not isinstance(boundary, str) or not boundary.strip() or PUBLIC_FORBIDDEN_RE.search(boundary)):
                raise ValueError(f"第二项{axis}条目边界无效：{name}")
            binding = item['source_binding_kind']
            if binding not in {'CLAIM_SUPPORT', 'MATERIAL_COLLECTION'}:
                raise ValueError(f"第二项{axis}来源关系非法：{name}")
            if not isinstance(item.get("source_refs"), list) or (binding == 'CLAIM_SUPPORT' and not item['source_refs']):
                raise ValueError(f"第二项{axis}逐条史源缺失：{name}/{item['id']}")
            if binding == 'MATERIAL_COLLECTION' and (item['source_refs'] or not related or item['evidence_mode'] == 'DIRECT'):
                raise ValueError(f"第二项{axis}材料汇集不能冒充逐条事实证明：{name}")
            for ref in item["source_refs"]:
                if not isinstance(ref, dict) or any(not isinstance(ref.get(k), str) or not ref[k].strip() for k in ("path", "source_title", "source_locator", "source_kind")):
                    raise ValueError(f"第二项{axis}逐条史源定位无效：{name}")
            if item['evidence_mode'] == 'DIRECT' and not any(ref['source_kind'] in {'史料原文', '现代研究原文'} for ref in item['source_refs']):
                raise ValueError(f"第二项{axis}直接史实不能仅引用裁决或摘要：{name}")
        summary = row.get("public_adjudication_summary")
        if not isinstance(summary, str) or not summary.strip() or PUBLIC_FORBIDDEN_RE.search(summary):
            raise ValueError(f"第二项{axis}人物级公开总结缺失或含内部术语：{name}")
        for field in ("public_story", "public_boundary", "public_loss_label"):
            value = row.get(field)
            if not isinstance(value, str) or not value.strip() or PUBLIC_FORBIDDEN_RE.search(value):
                raise ValueError(f"第二项{axis}公开正文无效：{name}/{field}")
        public_text = '\n'.join([row['public_story'], summary, row['public_boundary'],
                                 *[item['public_basis'] for item in actual]])
        if re.search(r"回写|硬承接|应撤销|已撤销|旧裁决|旧结算|旧理由|删除[“\"]|门未证实|军事成本恢复与额外代价", public_text):
            raise ValueError(f"第二项{axis}公开正文仍有修订过程或损坏术语：{name}")
        if row.get('loss_grade') == 'L1' and re.search(r"^(?:损害轻微|已证损害轻微|有界局部或短时损害|有局部或短时损害)", row['public_loss_label']):
            raise ValueError(f"第二项{axis}低谷标签不得把最低已证冒充损害轻微：{name}")
        evidence_count += len(actual)
    if payload.get("public_projection_evidence_item_count") != evidence_count:
        raise ValueError(f"第二项{axis}公开条目计数不一致")
    if _scoring_signature(payload) != _scoring_signature(_refresh_payload(axis, copy.deepcopy(payload))):
        raise ValueError(f"第二项{axis}公开投影改变了正式评分字段")
    return {
        "status": "PASS",
        "axis": axis,
        "record_count": len(rows),
        "public_evidence_item_count": evidence_count,
        "schema_version": PUBLIC_PROJECTION_SCHEMA,
        "validation_scope": "字段、引用定位与同值；不判定史源是否语义支撑正文",
        "claim_support_item_count": sum(item['source_binding_kind'] == 'CLAIM_SUPPORT' for row in rows for item in row['public_evidence_items']),
        "material_collection_item_count": sum(item['source_binding_kind'] == 'MATERIAL_COLLECTION' for row in rows for item in row['public_evidence_items']),
    }


def verify_public_projection(workspace_root: Path) -> dict[str, Any]:
    root = workspace_root.resolve()
    reports = {
        axis: _verify_payload(axis, load_json(root / path))
        for axis, path in FORMAL_PATHS.items()
    }
    id_sets = {
        axis: {str(row.get("ruler_id")) for row in _records(load_json(root / path))}
        for axis, path in FORMAL_PATHS.items()
    }
    if any(ids != id_sets["C1"] for ids in id_sets.values()):
        raise ValueError("第二项C1-C4公开投影人物集合不一致")
    payloads = {axis: load_json(root / path) for axis, path in FORMAL_PATHS.items()}
    source_count = verify_source_bindings(payloads)
    for axis, payload in payloads.items():
        markdown_path = (root / FORMAL_PATHS[axis]).with_suffix('.md')
        markdown = markdown_path.read_text(encoding='utf-8')
        if render_public_markdown(markdown, payload) != markdown:
            raise ValueError(f"第二项{axis}Markdown公开阅读视图未同步")
    return {
        "status": "PASS",
        "axis_reports": reports,
        "record_count": len(id_sets["C1"]),
        "source_reference_count": source_count,
        "validation_scope": "结构、摘录定位及阅读视图同值；不代表全池逐条语义复审完成",
        "schema_version": PUBLIC_PROJECTION_SCHEMA,
    }


def verify_source_bindings(payloads: dict[str, dict[str, Any]]) -> int:
    """Resolve authored source pointers; do not guess sources by prose similarity."""
    indexed = {axis: {row['ruler_id']: row for row in _records(payload)} for axis, payload in payloads.items()}
    count = 0
    for axis, payload in payloads.items():
        for row in _records(payload):
            groups = [item['source_refs'] for item in row['public_evidence_items']]
            groups.append(row['public_related_source_refs'])
            for refs in groups:
                for ref in refs:
                    source_axis = ref.get('axis')
                    if source_axis not in indexed or ref.get('ruler_id') != row['ruler_id']:
                        raise ValueError(f"第二项C逐条史源人物或轴引用无效：{row['ruler_name']}")
                    value = indexed[source_axis][row['ruler_id']]
                    try:
                        for part in ref['field_path']:
                            value = value[part]
                    except (KeyError, IndexError, TypeError) as exc:
                        raise ValueError(f"第二项C逐条史源字段失效：{row['ruler_name']}/{ref}") from exc
                    if ref.get('exact_quote') != value or not isinstance(value, str) or not value.strip():
                        raise ValueError(f"第二项C逐条史源摘录与原字段不一致：{row['ruler_name']}")
                    expected_path = FORMAL_PATHS[source_axis].as_posix() + '#ruler_id=' + row['ruler_id']
                    if ref['path'] != expected_path:
                        raise ValueError(f"第二项C逐条史源路径与对象不一致：{row['ruler_name']}")
                    count += 1
    return count


def render_public_markdown(markdown: str, payload: dict[str, Any]) -> str:
    """Keep the existing settlement table; append one current authored view."""
    start = '<!-- c-public-start -->'
    end = '<!-- c-public-end -->'
    core = re.sub(r'\n*' + re.escape(start) + r'.*?' + re.escape(end) + r'\n*', '\n', markdown, flags=re.S).rstrip()
    lines = [core, '', start, '', '## 人物正文、逐条依据与史源', '']
    from emperor_v4.evaluation.second_item_c_source_notes import source_note_records
    for row in source_note_records(payload):
        from emperor_v4.evaluation.second_item_c_reading import calculation_record
        row = calculation_record(payload['public_projection_axis'], row)
        story = ('\n\n'.join('#### ' + s['title'] + '\n\n' + s['body'] for s in row['public_reading_sections'])
                 if row.get('public_reading_sections') else row['public_story'])
        lines += [f"### {row['ruler_name']}", '', f"<a id=\"{row['ruler_id']}\"></a>", '', story, '',
                  '**来源说明：**' + row['public_source_note'], '',
                  '**定档理由：**' + row['public_adjudication_summary'], '', '**损害判断：**' + row['public_loss_label'], '',
                  '<details><summary>逐条事实与史源</summary>', '']
        for item in row['public_evidence_items']:
            mode = {'DIRECT':'史料直接记载', 'INFERRED':'受约束推断', 'ASSESSMENT':'正式评价判断', 'BACKGROUND':'背景互证', 'EXCLUDED':'不采用的范围核对'}[item['evidence_mode']]
            lines += [f"#### {item['public_label']}", '', f"**依据性质：**{mode}", '', item['public_basis'], '', '**采用范围：**' + item['public_scope'], '']
            if item['source_binding_kind'] == 'MATERIAL_COLLECTION':
                lines += ['本条沿用正式裁决叙述；相关材料列于人物材料汇集，尚未建立逐条事实的支持关系。', '']
            if item['public_boundary']:
                lines += ['**本条范围：**' + item['public_boundary'], '']
            for ref in item['source_refs']:
                target, _, anchor = ref['path'].partition('#')
                target = posixpath.relpath(target, FORMAL_PATHS[payload['public_projection_axis']].parent.as_posix()) + ('#' + anchor if anchor else '')
                lines += [f"- {ref['source_kind']}：{ref['source_title']}；{ref['source_locator']}；[原记录]({target})", '',
                          '> ' + ref['exact_quote'].replace('\n', '\n> '), '']
                if ref.get('source_url'):
                    lines += [f"[所引史源]({ref['source_url']})", '']
        if row['public_related_source_refs']:
            lines += ['#### 相关材料汇集（不代表逐条事实已获证明）', '']
            for ref in row['public_related_source_refs']:
                lines += [f"- {ref['source_kind']}：{ref['source_title']}；{ref['source_locator']}", '', '> ' + ref['exact_quote'].replace('\n', '\n> '), '']
        lines += ['</details>', '', '<details><summary>评价范围与计算</summary>', '', row['public_boundary'], '',
                  row['public_calculation'], '', '</details>', '']
    return '\n'.join([*lines, end, ''])


def run(workspace_root: Path, *, write: bool = False) -> dict[str, Any]:
    root = workspace_root.resolve()
    current = {axis: load_json(root / path) for axis, path in FORMAL_PATHS.items()}
    projected = {
        axis: _refresh_payload(axis, copy.deepcopy(payload))
        for axis, payload in current.items()
    }
    for axis, payload in projected.items():
        _verify_payload(axis, payload)
    verify_source_bindings(projected)
    if write:
        polities = load_ruler_polities(root)
        for axis, path in FORMAL_PATHS.items():
            write_json(root / path, projected[axis], ruler_polities=polities)
            markdown_path = (root / path).with_suffix('.md')
            markdown_path.write_text(render_public_markdown(markdown_path.read_text(encoding='utf-8'), projected[axis]), encoding='utf-8')
        report = verify_public_projection(root)
        report["status"] = "WRITTEN"
        return report
    if projected != current:
        raise ValueError("第二项C1-C4正式公开投影未同步；请运行second-item-c-public --write")
    return verify_public_projection(root)
