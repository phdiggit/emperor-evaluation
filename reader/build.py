"""Build the static reading layer from registered settlements; never adjudicate."""
from pathlib import Path
from copy import deepcopy
import json
import os
import sys
import argparse
import re
from urllib.parse import unquote

import yaml

ROOT = Path(__file__).resolve().parents[1]
DETAILS_DIR = ROOT / "reader/data/people"
SECOND_ITEM_READER_SUMMARIES = "reader/second-item-summaries.json"
SOURCE_IDENTITY_PATH = ROOT / "reader/source-revision.json"
PERSON_NOTES_SOURCE = ROOT / "reader/person-reading-notes.json"
PERSON_NOTES_SNAPSHOT = ROOT / "reader/data/person-reading-notes.json"
READER_RUNTIME_SCRIPTS = (
    "second-item-public-alias.js",
    "second-item-a-public.js",
    "second-item-b1-public.js",
    "second-item-public-labels.js",
    "person-reading-notes.js",
)
sys.path.insert(0, str(ROOT / "src"))
from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.first_item_public_outcomes import (
    load_first_item_public_outcomes,
    public_outcome_for_name,
)
from emperor_v4.evaluation.profile_parent_schema import parent_chains, representative_parent_chains
from emperor_v4.evaluation.first_item_c_public import (
    load_first_item_c_public, public_commander_for_name,
    SOURCE_MARKDOWN_PATH as FIRST_C_SOURCE,
)
from emperor_v4.evaluation.first_item_b1_cost_public import (
    load_first_item_b1_cost_public, B1_SOURCE as FIRST_B1_SOURCE, COST_SOURCE as FIRST_COST_SOURCE,
)
from emperor_v4.evaluation.composite_details import load_detail_sources, SECOND

NET_READER_EXTRA_SOURCES = {
    "D1": SECOND + "政权交接稳定/01-D1继任行政连续性方向卡.json",
    "D3": SECOND + "政权交接稳定/02-D3政权交接稳定方向卡.json",
    "ML": "config/third-item/third-item-military-net-loss-penalties.json",
}
HANDOFF_PUBLIC_GRADE = {0: "E", 1: "D", 2: "C", 3: "B", 4: "A", 5: "S"}


def handoff_public_grade(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "未定"
    if not number.is_integer():
        return "未定"
    return HANDOFF_PUBLIC_GRADE.get(int(number), "未定")


def reader_source_identity(*, write=False):
    """Pin reader source links to the source commit that passed validation."""
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    revision = os.environ.get("GITHUB_SHA", "").strip().lower()
    if repository and revision:
        if not re.fullmatch(r"[^/\\s]+/[^/\\s]+", repository):
            raise ValueError("Invalid GITHUB_REPOSITORY for reader source identity")
        if not re.fullmatch(r"[0-9a-f]{40,64}", revision):
            raise ValueError("Invalid GITHUB_SHA for reader source identity")
        identity = {"repository": repository, "revision": revision}
        if write:
            SOURCE_IDENTITY_PATH.write_text(
                json.dumps(identity, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
                newline="\n",
            )
        return identity
    if SOURCE_IDENTITY_PATH.exists():
        identity = json.loads(SOURCE_IDENTITY_PATH.read_text(encoding="utf-8"))
        repository = str(identity.get("repository") or "").strip()
        revision = str(identity.get("revision") or "").strip().lower()
        if repository and revision:
            return {"repository": repository, "revision": revision}
    return {"repository": "", "revision": ""}


def person_notes_snapshot(*, check=False, write=True):
    content = PERSON_NOTES_SOURCE.read_text(encoding="utf-8")
    expected = content if content.endswith("\n") else content + "\n"
    if check:
        if not PERSON_NOTES_SNAPSHOT.exists() or PERSON_NOTES_SNAPSHOT.read_text(encoding="utf-8") != expected:
            raise ValueError("Reader person-reading-notes snapshot is stale")
    elif write:
        PERSON_NOTES_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        PERSON_NOTES_SNAPSHOT.write_text(expected, encoding="utf-8", newline="\n")


def index(rows):
    result = {r["ruler_id"]: r for r in rows}
    if len(result) != len(rows):
        raise ValueError("Duplicate ruler_id")
    return result


def pick(row, fields):
    return {k: row[k] for k in fields if k in row}


def local_sources(value):
    """Resolve local reference availability without inventing replacement evidence."""
    if isinstance(value, dict):
        return {p for child in value.values() for p in local_sources(child)}
    if isinstance(value, list):
        return {p for child in value for p in local_sources(child)}
    if isinstance(value, str) and value.startswith(("docs/", "config/", "archive/")) and "\n" not in value:
        return {value}
    return set()


def source_file(ref):
    """Accept both Markdown fragments and existing path:line citations."""
    return re.sub(r":\d+(?:-\d+)?$", "", unquote(ref.split("#", 1)[0]))


def apply_public_copy(template):
    """Apply reader-only wording without changing any settlement payload."""
    path = ROOT / "reader/public-copy.json"
    replacements = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(replacements, list):
        raise ValueError("Reader public copy must be a list")
    for i, item in enumerate(replacements):
        if not isinstance(item, dict) or not isinstance(item.get("from"), str) or not isinstance(item.get("to"), str):
            raise ValueError(f"Invalid reader public copy entry: {i}")
        old, new = item["from"], item["to"]
        if old not in template:
            raise ValueError(f"Reader public copy source is stale: {old}")
        template = template.replace(old, new)
    return template


FORMAL_CONTEXT_FIELDS = [
    "parent_id",
    "parent_ref",
    "title",
    "mechanism",
    "mechanisms",
    "cycle_basis",
    "basis",
    "source_refs",
    "cycle_anchor_refs",
    "direct_process_refs",
    "direction",
    "intensity",
    "material_intensity",
    "attribution",
    "attribution_basis",
    "role_attribution",
    "limitations",
    "limitation",
    "intensity_and_role_basis",
]


def inline_runtime_scripts(template):
    """Freeze runtime JS into the generated page after all validations pass.

    GitHub Pages currently publishes this branch directly. Keeping the browser
    runtime inside the generated artifact means an unvalidated source commit can
    only republish the last validated reader/index.html, not new source JS.
    """
    for filename in READER_RUNTIME_SCRIPTS:
        marker = f'<script defer src="{filename}"></script>'
        if template.count(marker) != 1:
            raise ValueError(f"Reader runtime script marker missing or duplicated: {filename}")
        source = (ROOT / "reader" / filename).read_text(encoding="utf-8")
        source = source.replace("</script>", r"<\/script>")
        template = template.replace(marker, f"<script>\n{source}\n</script>", 1)
    return template


def _formal_context_projection(context):
    # Public reading may only expose fields that already exist in the formal
    # record. Never synthesize direction, strength, attribution or limits here.
    return pick(context, FORMAL_CONTEXT_FIELDS)


def axis_projection(row, fields):
    result = pick(row, fields)
    chains = parent_chains(row)
    result["source_refs"] = list(dict.fromkeys(
        ref for owner in [row, *chains]
        for ref in owner.get("source_refs", []) if isinstance(ref, str)
    ))
    counter = row.get("counterpattern")
    if isinstance(counter, dict):
        ids = {ref for values in counter.values() if isinstance(values, list) for ref in values if isinstance(ref, str)}
        result["context_lookup"] = {
            p["parent_id"]: _formal_context_projection(p)
            for p in chains if p.get("parent_id") in ids
        }
        missing = ids - result["context_lookup"].keys()
        if missing:
            raise ValueError(f"Unresolved context references: {sorted(missing)}")

    # Only project explicitly declared representative material. The helper can
    # fall back to all parent chains for legacy callers, so do not call it when
    # the formal record has not declared representatives.
    declared_representatives = (
        row.get("representative_parent_ids") is not None
        or isinstance(row.get("representative_parent_contexts"), list)
    )
    if declared_representatives:
        result["representative_contexts"] = [
            _formal_context_projection(context)
            for context in representative_parent_chains(row)
            if isinstance(context, dict)
        ]

    if row.get("axis_code") == "C5" and isinstance(row.get("public_evidence_points"), list):
        result["public_evidence_points"] = [
            pick(point, ["title", "details"])
            for point in row["public_evidence_points"] if isinstance(point, dict)
        ]
    return result

def _clean_text(value):
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _first_text(*values):
    for value in values:
        text = _clean_text(value)
        if text:
            return text
    return ""


def _unique_texts(values, limit=4):
    result = []
    seen = set()
    for value in values:
        text = _clean_text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if limit is not None and len(result) >= limit:
            break
    return result


def _formal_source_refs(record, *extra):
    refs = []
    for ref in extra:
        if isinstance(ref, str) and ref.startswith(("docs/", "config/", "archive/")):
            refs.append(ref)
    if isinstance(record, dict):
        refs.extend(sorted(local_sources(record)))
    return list(dict.fromkeys(refs))[:8]


def _attach_reader(item, *, kind, summary="", how="", boundary="", source_refs=(), highlights=()):
    """Attach explicitly supplied display fields; never infer prose from records."""
    result = dict(item)
    result["reader_kind"] = kind
    for key, value in (("reader_summary", summary), ("reader_boundary", boundary), ("reader_how", how)):
        if value:
            result[key] = value
    if highlights:
        result["reader_highlights"] = _unique_texts(highlights, limit=None)
    refs = _formal_source_refs(None, item.get("source"), item.get("applied_source"), *source_refs)
    if refs:
        result["reader_source_refs"] = refs
    return result


def _attach_b2_public_reader(item, *, record, how="", source_refs=()):
    """Project B2's explicit public fields without semantic fallback guessing."""

    if not isinstance(record, dict):
        raise ValueError("B2 reader projection requires a formal record")
    summary = record.get("public_adjudication_summary")
    evidence = record.get("public_evidence_items")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError(f"B2 formal public summary is missing: {record.get('ruler_name')}")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError(f"B2 formal public evidence is missing: {record.get('ruler_name')}")
    result = dict(item)
    result["reader_kind"] = "judgment"
    result["reader_summary"] = summary
    result["public_adjudication_summary"] = summary
    result["public_evidence_items"] = deepcopy(evidence)
    result["reader_public_evidence_items"] = deepcopy(evidence)
    result["reader_highlights"] = _unique_texts(
        [
            f"{entry.get('public_label')}：{entry.get('public_basis')}"
            for entry in evidence
            if isinstance(entry, dict)
        ],
        limit=None,
    )
    boundaries = _unique_texts(
        [entry.get("public_boundary") for entry in evidence if isinstance(entry, dict)],
        limit=None,
    )
    if boundaries:
        result["reader_boundary"] = "；".join(boundaries)
    if how:
        result["reader_how"] = how
    refs = _formal_source_refs(record, item.get("source"), item.get("applied_source"), *source_refs)
    if refs:
        result["reader_source_refs"] = refs
    return result


def _attach_method_public_reader(item, *, axis, record, how=""):
    """A/B1 overviews consume the same declared public prose as detail cards."""
    summary = record.get("public_adjudication_summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError(f"{axis} formal public summary is missing: {record.get('ruler_name')}")
    if axis == "A":
        nodes = record.get("public_institution_nodes")
        if not isinstance(nodes, list):
            raise ValueError("A formal public nodes are missing")
        evidence = [dict(
            public_label=node["public_label"], public_direction=node.get("public_direction", ""),
            public_basis="\n\n".join(node[key] for key in ("public_adjudication_basis", "public_scope", "public_reception") if node.get(key)),
            public_boundary=node.get("public_boundary", ""),
        ) for node in nodes]
    elif axis == "B1":
        evidence = [dict(
            public_label=node["public_label"],
            public_basis=node["adjudication_basis"],
            public_boundary=node.get("adjudication_boundary", ""),
        ) for key in ("M_positive_profile", "M_mixed_profile", "M_negative_profile") for node in record.get(key, [])]
    else:
        raise ValueError(f"Unsupported method axis: {axis}")
    result = dict(item)
    result.update(reader_kind="judgment", reader_summary=summary,
                  public_adjudication_summary=summary, reader_public_evidence_items=evidence,
                  reader_how=how, reader_source_refs=_formal_source_refs(record, item.get("source"), item.get("applied_source")))
    boundaries = _unique_texts([node["public_boundary"] for node in evidence], limit=None)
    if boundaries:
        result["reader_boundary"] = "\n\n".join(boundaries)
    return result


def _attach_second_item_c_public_reader(item, *, axis, record, how="", source_refs=()):
    """Project C1-C4 explicit public fields without reader-side adjudication."""

    if not isinstance(record, dict):
        raise ValueError(f"{axis} reader projection requires a formal record")
    summary = record.get("public_adjudication_summary")
    evidence = record.get("public_evidence_items")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError(f"{axis} formal public summary is missing: {record.get('ruler_name')}")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError(f"{axis} formal public evidence is missing: {record.get('ruler_name')}")
    result = dict(item)
    result["reader_kind"] = "judgment"
    result["reader_summary"] = summary
    result["public_adjudication_summary"] = summary
    result["public_evidence_items"] = deepcopy(evidence)
    result["reader_public_evidence_items"] = deepcopy(evidence)
    result["reader_highlights"] = _unique_texts(
        [
            f"{entry.get('public_label')}：{entry.get('public_basis')}"
            for entry in evidence
            if isinstance(entry, dict)
        ],
        limit=None,
    )
    boundaries = _unique_texts(
        [entry.get("public_boundary") for entry in evidence if isinstance(entry, dict)],
        limit=None,
    )
    if boundaries:
        result["reader_boundary"] = "；".join(boundaries)
    if how:
        result["reader_how"] = how
    refs = _formal_source_refs(record, item.get("source"), item.get("applied_source"), *source_refs)
    if refs:
        result["reader_source_refs"] = refs
    return result


def _attach_d1_d3_public_reader(item, *, record, axis, how="", source_refs=()):
    """Project D1/D3's explicit public fields without generic fallback guessing."""

    if not isinstance(record, dict):
        raise ValueError(f"{axis} reader projection requires a formal record")
    summary = record.get("public_adjudication_summary")
    evidence = record.get("public_evidence_items")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError(f"{axis} formal public summary is missing: {record.get('ruler_name')}")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError(f"{axis} formal public evidence is missing: {record.get('ruler_name')}")
    result = dict(item)
    result["reader_kind"] = "judgment"
    result["reader_summary"] = summary
    result["public_adjudication_summary"] = summary
    result["public_evidence_items"] = deepcopy(evidence)
    result["reader_public_evidence_items"] = deepcopy(evidence)
    result["reader_highlights"] = _unique_texts(
        [
            f"{entry.get('public_role')}：{entry.get('public_basis')}"
            for entry in evidence
            if isinstance(entry, dict)
        ],
        limit=None,
    )
    boundaries = _unique_texts(
        [entry.get("public_boundary") for entry in evidence if isinstance(entry, dict)],
        limit=None,
    )
    if boundaries:
        result["reader_boundary"] = "；".join(boundaries)
    if how:
        result["reader_how"] = how
    refs = _formal_source_refs(record, item.get("source"), item.get("applied_source"), *source_refs)
    if refs:
        result["reader_source_refs"] = refs
    return result


def _attach_formal_public_reader(item, *, record, axis="", how="", source_refs=(), public_label=""):
    """Consume an Item 3/4 public projection without translating formal codes."""

    if not isinstance(record, dict):
        raise ValueError(f"{axis or 'formal'} reader projection requires a formal record")
    projection = record
    projections = record.get("public_axis_projections")
    if axis and isinstance(projections, dict) and isinstance(projections.get(axis), dict):
        projection = projections[axis]
    summary = projection.get("public_adjudication_summary")
    evidence = projection.get("public_evidence_items")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError(f"{axis or 'formal'} formal public summary is missing: {record.get('ruler_name')}" )
    if not isinstance(evidence, list) or not evidence:
        raise ValueError(f"{axis or 'formal'} formal public evidence is missing: {record.get('ruler_name')}" )
    result = dict(item)
    result["reader_kind"] = "judgment"
    result["reader_summary"] = summary
    result["public_adjudication_summary"] = summary
    result["public_evidence_items"] = deepcopy(evidence)
    result["reader_public_evidence_items"] = deepcopy(evidence)
    result["public_component_label"] = public_label or projection.get("public_component_label") or record.get("public_component_label")
    result["public_level_label"] = projection.get("public_level_label") or record.get("public_level_label")
    result["reader_highlights"] = _unique_texts(
        [
            f"{entry.get('public_label') or entry.get('public_role')}：{entry.get('public_basis')}"
            for entry in evidence
            if isinstance(entry, dict)
        ],
        limit=None,
    )
    boundaries = _unique_texts(
        [entry.get("public_boundary") for entry in evidence if isinstance(entry, dict)],
        limit=None,
    )
    boundary = projection.get("public_boundary") or record.get("public_boundary")
    if boundary:
        boundaries.insert(0, boundary)
    if boundaries:
        result["reader_boundary"] = "；".join(_unique_texts(boundaries, limit=None))
    if how:
        result["reader_how"] = how
    refs = _formal_source_refs(record, item.get("source"), item.get("applied_source"), *source_refs)
    if refs:
        result["reader_source_refs"] = refs
    return result


def load_net_reader_sources(root):
    """Load formal subitem evidence for reader-only explanations."""
    sources = load_detail_sources(root)
    sources['first_c_public'] = load_first_item_c_public(root)
    sources['first_b1_public'], sources['first_cost_public'] = load_first_item_b1_cost_public(root)
    for key, path in NET_READER_EXTRA_SOURCES.items():
        payload = load_json(root / path)
        rows = payload["records"]
        sources[key] = index(rows)
        sources[f"{key}_path"] = path
    return sources


def load_second_item_reader_summaries(root, eligible_ids):
    """Load persisted reader-only conclusions for the currently ranked pool."""
    path = root / SECOND_ITEM_READER_SUMMARIES
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Missing reader-only Second Item summaries: {path}") from exc
    if not isinstance(payload, dict) or payload.get("schema_id") != "reader-second-item-conclusion-v1":
        raise ValueError("Invalid reader-only Second Item summary schema")
    summaries = payload.get("summaries")
    if not isinstance(summaries, dict):
        raise ValueError("Reader-only Second Item summaries must be an object")
    eligible = set(eligible_ids)
    outside = sorted(set(summaries) - eligible)
    if outside:
        raise ValueError(f"Reader-only Second Item summaries reference unranked rulers: {outside}")
    result = {}
    for ruler_id, summary in summaries.items():
        if not isinstance(ruler_id, str) or not ruler_id:
            raise ValueError("Reader-only Second Item summary has an invalid ruler_id")
        if not isinstance(summary, str):
            raise ValueError(f"Reader-only Second Item summary is not text: {ruler_id}")
        summary = _clean_text(summary)
        if not 35 <= len(summary) <= 120:
            raise ValueError(f"Reader-only Second Item summary length is outside 35-120: {ruler_id}")
        if any(mark in summary for mark in ("<", ">")):
            raise ValueError(f"Reader-only Second Item summary must be plain text: {ruler_id}")
        if re.search(r"\d|\b(?:A|B1|B2|C[1-4]|D[13]|G[0-5]|DA[0-4])\b", summary):
            raise ValueError(f"Reader-only Second Item summary exposes internal scoring language: {ruler_id}")
        if re.search(r"推动|带来|因而|使(?:生产|财政|民生|社会|家庭|普通|秩序|行政)|让(?:生产|财政|民生|社会|家庭|普通|秩序|行政)|令(?:生产|财政|民生|社会|家庭|普通|秩序|行政)", summary):
            raise ValueError(f"Reader-only Second Item summary asserts an unqualified method-result causality: {ruler_id}")
        if re.search(r"缺少高风险检验|压力检验不足|风险检验不足|没有经历.*风险|缺乏高风险|评分门槛|相对最强|相对最弱|最强|最弱", summary):
            raise ValueError(f"Reader-only Second Item summary contains a forbidden reader conclusion: {ruler_id}")
        if re.search(r"军事|边疆|边防|统一功业|北伐|远征|军队|军费|军粮|兵变|战争|战乱|战后", summary):
            raise ValueError(f"Reader-only Second Item summary crosses into the military/unification item: {ruler_id}")
        result[ruler_id] = summary
    skipped = payload.get("skipped", [])
    if not isinstance(skipped, list):
        raise ValueError("Reader-only Second Item skipped must be a list")
    skipped_ids = set()
    for item in skipped:
        if not isinstance(item, dict) or not isinstance(item.get("ruler_id"), str) or not isinstance(item.get("reason"), str):
            raise ValueError("Reader-only Second Item skipped entries need ruler_id and reason")
        if not item["reason"].strip():
            raise ValueError(f"Reader-only Second Item skipped entry has an empty reason: {item['ruler_id']}")
        if item["ruler_id"] in result:
            raise ValueError(f"Reader-only Second Item ruler is both summarized and skipped: {item['ruler_id']}")
        if item["ruler_id"] in eligible:
            raise ValueError(f"Reader-only Second Item eligible ruler is skipped: {item['ruler_id']}")
        if item["ruler_id"] in skipped_ids:
            raise ValueError(f"Reader-only Second Item ruler is skipped more than once: {item['ruler_id']}")
        skipped_ids.add(item["ruler_id"])
    return result


def project_net_explanations(person, row, sources, first_item_public_outcomes=None):
    """Add reader-only explanation metadata without changing any scoring value."""
    details = deepcopy(row.get("component_details", {}))
    if not details:
        return details
    ids = person["source_item_ids"]
    name = row["ruler_name"]
    sid, tid, fid = (ids[k] for k in ("second_item", "third_item", "fourth_item"))

    first = {item["label"]: item for item in details.get("first", [])}
    for label, item in list(first.items()):
        if label == "A统一贡献":
            first[label] = _attach_reader(
                item, kind="judgment",
                summary="只评价本人在建国、复国或统一主链中最终留下的稳定控制成果；起点、对手强弱和完成速度不在这里重复计分。",
                how=f"{item.get('note') or '按正式A项控制信用与项目归属'}；单人项目按统一贡献曲线计算，共同项目先生成项目A池再按正式个人信用分账，最终为 {item.get('value')} 分。",
            )
            if item.get("value") is not None:
                if first_item_public_outcomes is None:
                    raise ValueError("第一项A缺少正式公开成果投影")
                first[label]["reader_public_outcome"] = public_outcome_for_name(
                    first_item_public_outcomes, name
                )
        elif label == "B1创业难度与效率":
            if item.get('value') is None:
                first[label] = _attach_reader(item, kind='judgment')
                continue
            public = public_commander_for_name(sources['first_b1_public'], name)
            first[label] = _attach_reader(
                item, kind="judgment",
                summary='\n\n'.join(public[key] for key in ('public_start_basis','public_opponent_basis','public_efficiency_basis')),
                how=public['public_calculation'],
                source_refs=(FIRST_B1_SOURCE.as_posix(),),
            )
            first[label]['reader_public_b1'] = deepcopy(public)
        elif label == "B2组织与整合":
            first[label] = _attach_reader(
                item, kind="judgment",
                summary="评价创业或统一过程中同时处理多线任务、覆盖关键区域并完成组织整合的能力。",
                how=f"{item.get('grade', '')}；{item.get('note', '')}，合计 {item.get('value')} 分。",
            )
        elif label == "C军事统帅与战争解题":
            if item.get('value') is None:
                first[label] = _attach_reader(item, kind='judgment')
                continue
            commander = public_commander_for_name(sources['first_c_public'], name)
            first[label] = _attach_reader(
                item, kind="judgment",
                summary=commander['public_basis'],
                boundary=commander['public_boundary'],
                source_refs=(FIRST_C_SOURCE.as_posix(),),
                how=f"正式能力档与归责路线共同换算为 {item.get('value')} 分；{item.get('note', '')}",
            )
            first[label]['reader_public_commander'] = deepcopy(commander)
        elif label == "军事成本扣分":
            if item.get('value') is None:
                first[label] = _attach_reader(item, kind='judgment')
                continue
            cost = sources["first_cost"].get(name, {})
            public = public_commander_for_name(sources['first_cost_public'], name)
            first[label] = _attach_reader(
                item, kind="judgment", summary=public['public_basis'],
                how=f"正式军事成本档与档内位置按成本表换算为扣 {item.get('value')} 分。",
                boundary=public['public_responsibility_window'],
                source_refs=(FIRST_COST_SOURCE.as_posix(), *cost.get('source_refs',[])),
            )
            first[label]['reader_public_cost'] = deepcopy(public)
        else:
            first[label] = _attach_reader(item, kind="calculation")
    if first:
        values = {label: item.get("value") for label, item in first.items()}
        if "四轴合计" in first:
            first["四轴合计"]["reader_how"] = (
                f"A统一贡献 + B1创业难度与效率 + B2组织与整合 + C军事统帅与战争解题 = {values.get('四轴合计')} 分。"
            )
        if "第一项净分" in first:
            first["第一项净分"]["reader_how"] = (
                f"四轴合计 {values.get('四轴合计')} − 军事成本扣分 {values.get('军事成本扣分')}，最低按0计，得到 {values.get('第一项净分')} 分。"
            )
        if "附加F" in first:
            first["附加F"]["reader_how"] = (
                f"第一项净分再按总榜附加F曲线折算，得到 {values.get('附加F')} 分。"
            )
        details["first"] = [first[item["label"]] for item in details["first"]]

    method_records = {"A制度建设": "A", "B1官僚治理": "B1", "B2反馈与约束": "B2"}
    method = {item["label"]: item for item in details.get("method", [])}
    for label, key in method_records.items():
        if label in method:
            item = method[label]
            record = sources[key][sid]
            how = f"正式方向指数为 {item.get('value')}；该指数随后进入治理手段合成公式。"
            if key == "B2":
                method[label] = _attach_b2_public_reader(item, record=record, how=how)
            else:
                method[label] = _attach_method_public_reader(item, axis=key, record=record, how=how)
    if method:
        values = {label: item.get("value") for label, item in method.items()}
        for label in ("AB计分块", "B2折算", "治理手段"):
            if label in method:
                method[label] = _attach_reader(method[label], kind="calculation")
        if "AB计分块" in method:
            method["AB计分块"]["reader_how"] = (
                f"0.8 × [max(A制度建设, B1官僚治理) + 0.5 × min(A制度建设, B1官僚治理)] = {values.get('AB计分块')} 分。"
            )
        if "B2折算" in method:
            method["B2折算"]["reader_how"] = f"45 / 80 × B2反馈与约束指数 = {values.get('B2折算')} 分。"
        if "治理手段" in method:
            method["治理手段"]["reader_how"] = (
                f"AB计分块 {values.get('AB计分块')} + B2折算 {values.get('B2折算')} = {values.get('治理手段')} 分。"
            )
        details["method"] = [method[item["label"]] for item in details["method"]]

    finance_keys = {"C1民生": "C1", "C2经济财政": "C2", "C3社会安全": "C3", "C4恢复与成本": "C4"}
    finance = {item["label"]: item for item in details.get("finance", [])}
    for label, key in finance_keys.items():
        if label not in finance:
            continue
        item = finance[label]
        record = sources[key][sid]
        if key == "C4" and item.get("note"):
            how = f"正向保留 − 恶化扣分 − 破坏放大扣分 = {item.get('note')} = {item.get('value')} 分。"
        else:
            how = f"正式状态判断与损失修正按本轴合同换算为 {item.get('value')} 分。"
        finance[label] = _attach_second_item_c_public_reader(
            item, axis=key, record=record, how=how
        )
    if "治理结果" in finance:
        values = {label: item.get("value") for label, item in finance.items()}
        finance["治理结果"] = _attach_reader(
            finance["治理结果"], kind="calculation",
            how=(
                f"C1民生 {values.get('C1民生')} + C2经济财政 {values.get('C2经济财政')} + "
                f"C3社会安全 {values.get('C3社会安全')} + C4恢复与成本 {values.get('C4恢复与成本')} "
                f"= {values.get('治理结果')} 分。"
            ),
        )
    if finance:
        details["finance"] = [finance[item["label"]] for item in details["finance"]]

    handoff = {item["label"]: item for item in details.get("handoff", [])}
    for label, key in (("D1继任行政连续性", "D1"), ("D3政权交接稳定", "D3")):
        if label in handoff:
            item = handoff[label]
            record = sources[key][sid]
            handoff[label] = _attach_d1_d3_public_reader(
                item, record=record, axis=key,
                how=f"公开档位为 {handoff_public_grade(item.get('value'))}档；该档位参与政权交接得分计算，本项不会重复单独加分。",
                source_refs=(sources[f"{key}_path"],),
            )
    if handoff:
        values = {label: item.get("value") for label, item in handoff.items()}
        for label in ("低侧封顶", "交接得分", "第二项合计"):
            if label in handoff:
                handoff[label] = _attach_reader(handoff[label], kind="calculation")
        if "低侧封顶" in handoff:
            handoff["低侧封顶"]["reader_how"] = (
                f"交接短板决定本项最高可得 {values.get('低侧封顶')} 分；这是上限，不是额外得分。"
            )
        if "交接得分" in handoff:
            handoff["交接得分"]["reader_how"] = (
                f"行政连续性 {handoff_public_grade(values.get('D1继任行政连续性'))}档，"
                f"交接稳定 {handoff_public_grade(values.get('D3政权交接稳定'))}档；"
                f"两项按 E=0、D=1、C=2、B=3、A=4、S=5 换算后合计并乘2，"
                f"同时受交接短板上限 {values.get('低侧封顶')} 分约束，最终为 {values.get('交接得分')} 分。"
            )
        if "第二项合计" in handoff:
            method_score = next((x.get("value") for x in details.get("method", []) if x.get("label") == "治理手段"), None)
            result_score = next((x.get("value") for x in details.get("finance", []) if x.get("label") == "治理结果"), None)
            handoff["第二项合计"]["reader_how"] = (
                f"治理手段 {method_score} + 治理结果 {result_score} + 交接得分 {values.get('交接得分')} "
                f"= {values.get('第二项合计')} 分。"
            )
        details["handoff"] = [handoff[item["label"]] for item in details["handoff"]]

    credit = sources["credit"][tid]
    ab = sources["AB"][tid]
    strategic = {item["label"]: item for item in details.get("strategic", [])}
    for key in ("A1", "A2"):
        if key in strategic:
            strategic[key] = _attach_formal_public_reader(
                strategic[key], record=credit, axis=key,
                how=f"起点、终点和本人责任共同换算为 {strategic[key].get('value')} 分。",
            )
    for key in ("B1", "B2", "B4"):
        if key in strategic:
            rate = credit["B80_adjudication"][f"adjudicated_{key}_rate"]
            strategic[key] = _attach_formal_public_reader(
                strategic[key], record=ab, axis=key,
                how=f"当前结果先得到 {strategic[key].get('value')}% 的得分率，合成时采用 {rate:g}%。",
            )
    for label in ("A120", "B80"):
        if label in strategic:
            strategic[label] = _attach_reader(strategic[label], kind="calculation")
            strategic[label]["public_component_label"] = {
                "A120": "战略安全成果合计",
                "B80": "控制成果合成",
            }[label]
    if "A120" in strategic:
        strategic["A120"]["reader_how"] = (
            f"两项战略安全状态结果 {strategic.get('A1', {}).get('value')} + {strategic.get('A2', {}).get('value')} = "
            f"{strategic['A120'].get('value')} 分。"
        )
    if "B80" in strategic:
        strategic["B80"]["reader_how"] = (
            "B1控制规模与B2战略价值按55%/45%合成，再由B4交班成熟度修正，"
            f"得到 {strategic['B80'].get('value')} 分。"
        )
    if strategic:
        details["strategic"] = [strategic[item["label"]] for item in details["strategic"]]

    c_record = sources["C"][tid]
    third = sources["third"][tid]
    military = {item["label"]: item for item in details.get("military", [])}
    specific_reason_keys = {
        "C1实战交付": ("combat_delivery_basis", "C1_basis"),
        "C2持续作战": ("operational_sustainability_basis", "C2_basis"),
        "C3体系可靠性": ("system_reliability_basis", "C3_basis"),
    }
    for label, keys in specific_reason_keys.items():
        if label in military:
            axis = label[:2]
            military[label] = _attach_formal_public_reader(
                military[label], record=c_record, axis=axis,
                how="这是军事体系结果的组成方面，不单独加分；三方面共同确定军事体系结果。",
            )
    if "C50" in military:
        military["C50"] = _attach_formal_public_reader(
            military["C50"], record=c_record,
            how=f"三方面军事体系表现共同换算为 {military['C50'].get('value')} 分。",
        )
        military["C50"]["reader_kind"] = "calculation"
    if "普通成本扣分" in military:
        cost_profile = third.get("global_cost_credit_profile", {})
        military["普通成本扣分"] = _attach_formal_public_reader(
            military["普通成本扣分"], record=cost_profile,
            how=f"普通军事代价按固定换算表折算为扣 {military['普通成本扣分'].get('value')} 分。",
        )
    if "ML扣分" in military:
        ml_record = sources["ML"].get(person["ruler_id"]) or third.get("public_military_net_loss", {})
        military["ML扣分"] = _attach_formal_public_reader(
            military["ML扣分"], record=ml_record,
            how=f"重大军事净毁损按固定换算表折算为扣 {military['ML扣分'].get('value')} 分。",
            source_refs=(sources["ML_path"],),
        )
    for label in ("实际扣分", "第三项合计"):
        if label in military:
            military[label] = _attach_reader(military[label], kind="calculation")
            military[label]["public_component_label"] = {
                "实际扣分": "实际军事代价",
                "第三项合计": "第三项军事与边疆净收益",
            }[label]
    if "实际扣分" in military:
        military["实际扣分"]["reader_how"] = (
            f"普通军事代价扣减 {military.get('普通成本扣分', {}).get('value')} 与重大军事净毁损扣减 "
            f"{military.get('ML扣分', {}).get('value')} 取较高值 = {military['实际扣分'].get('value')} 分。"
        )
    if "第三项合计" in military:
        a120 = strategic.get("A120", {}).get("value")
        b80 = strategic.get("B80", {}).get("value")
        c50 = military.get("C50", {}).get("value")
        debit = military.get("实际扣分", {}).get("value")
        military["第三项合计"]["reader_how"] = (
            f"战略安全成果 {a120} + 控制成果合成 {b80} + 军事体系结果 {c50} − 实际军事代价 {debit} "
            f"= {military['第三项合计'].get('value')} 分。"
        )
    if military:
        details["military"] = [military[item["label"]] for item in details["military"]]

    fourth = sources["fourth"][fid]
    fourth_axes = {axis["axis"]: axis for axis in fourth.get("axis_results", [])}
    civilization = {item["label"]: item for item in details.get("civilization", [])}
    label_to_axis = {"A国家共同体": "A", "B教育与人才": "B", "C文化知识": "C"}
    civ_names = {"A": "国家共同体与社会整合", "B": "教育可及与人才流动", "C": "知识生产与文化生态"}
    for label, key in label_to_axis.items():
        if label not in civilization:
            continue
        item = civilization[label]
        axis = fourth_axes.get(key, {})
        civilization[label] = _attach_formal_public_reader(
            item, record=fourth, axis=key,
            how=f"按正式方向、影响幅度和本级位置换算为 {item.get('value')} 分调整。",
        )
    if "第四项调整" in civilization:
        values = [civilization[label].get("value") for label in label_to_axis if label in civilization]
        civilization["第四项调整"] = _attach_reader(
            civilization["第四项调整"], kind="calculation",
            how=f"国家共同体、教育与人才、知识与文化生态三轴调整相加：{' + '.join(str(v) for v in values)} = {civilization['第四项调整'].get('value')} 分。",
        )
        civilization["第四项调整"]["public_component_label"] = "第四项文明与国家整合调整"
    if civilization:
        details["civilization"] = [civilization[item["label"]] for item in details["civilization"]]

    return details


def detail_ref(ruler_id):
    """Use stable ruler ids as deterministic static shard names."""
    if not ruler_id or any(x in ruler_id for x in ("/", "\\")) or ruler_id in {".", ".."}:
        raise ValueError(f"Unsafe ruler_id for reader detail shard: {ruler_id!r}")
    return f"data/people/{ruler_id}.json"


def axis_summary(axis):
    """Keep only fields needed by overview grade rendering before detail fetch."""
    return pick(axis, [
        "axis_grade", "position", "output_mode", "applicability_status",
        "adjudication_state", "display_point_only",
    ])


def record_summary(record):
    """Project a small, self-sufficient overview row without evidence prose."""
    net = record.get("net")
    impact = record["impact"]
    summary_impact = pick(impact, [
        "identity_label", "public_grade", "impact_nature", "confidence", "reading_start_year",
    ])
    summary_impact["dimensions"] = {
        key: pick(value, ["grade"])
        for key, value in impact.get("dimensions", {}).items()
        if isinstance(value, dict)
    }
    summary = pick(record, [
        "ruler_id", "ruler_name", "polity", "actual_power_window",
        "settlement_readiness", "supplementary",
    ])
    summary["net"] = pick(net, [
        "rank", "total_score", "first_item_status", "first_item_raw_score", "first_item_add_on",
        "second_item_score", "third_item_score", "fourth_item_adjustment",
    ]) if net else None
    summary["impact"] = summary_impact
    summary["axes"] = {code: axis_summary(axis) for code, axis in record.get("axes", {}).items()}
    summary["detail_ref"] = detail_ref(record["ruler_id"])
    summary["detail_loaded"] = False
    return summary


def source_availability(value):
    return {
        ref: (ROOT / source_file(ref)).exists()
        for ref in sorted(local_sources(value))
    }


def detail_payload(record):
    """Full per-person data fetched only when a person or comparison is opened."""
    return {
        "record": record,
        "source_availability": source_availability(record),
    }


def serialized_json(value, *, html_safe=False):
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if html_safe:
        text = text.replace("<", "\\u003c")
    return text


def build(*, check=False, write=True):
    config = yaml.safe_load((ROOT / "config/project.yml").read_text(encoding="utf-8"))
    pool = load_json(ROOT / config["canonical_ruler_pool"]["json"])
    main = [r for r in pool["records"] if r["pool_status"] == "INCLUDED"]
    main_ids = set(index(main))
    scoring = config["scoring_contract"]
    ranking = load_json(ROOT / scoring["composite_ranking_json"])
    net = index(ranking["records"])
    ready = {r["ruler_id"] for r in main if r["settlement_readiness"] == "COMPOSITE_READY"}
    if set(net) != ready:
        raise ValueError("Composite ranking does not match current ready pool")
    second_item_reader_summaries = load_second_item_reader_summaries(ROOT, ready)
    net_reader_sources = load_net_reader_sources(ROOT)
    first_item_public_outcomes = load_first_item_public_outcomes(ROOT)
    impact_config = config["historical_impact_assessment"]
    impact = load_json(ROOT / impact_config["json"])
    history = index(impact["records"])
    if set(history) != main_ids:
        raise ValueError("Historical impact coverage differs from included pool")
    profile = config["profile_assessment"]
    groups = profile["capability_axes"] + profile["independent_profile_axes"]
    if len(groups) != len(set(groups)) or set(groups) != set(profile["axis_order"]):
        raise ValueError("Profile display groups must partition the registered axes")
    axes = {}
    for code in profile["axis_order"]:
        spec = profile["settled_axes"][code]
        rows = index(load_json(ROOT / spec["json"])["records"])
        if set(rows) != main_ids:
            raise ValueError(f"{code}: coverage differs from included pool")
        axes[code] = rows
    axis_fields = ["axis_grade", "position", "radar_value", "output_mode", "confidence",
                   "applicability_status", "not_applicable_reason", "grade_basis", "typical_pattern",
                   "counterpattern", "limitations", "person_type", "score_status", "axis_evidence_level",
                   "adjudication_state", "display_point_only", "formal_status", "no_grade_closure",
                   "position_basis", "applicability_basis", "evidence_assessment_basis",
                   "assessment_basis", "final_capability_review"]
    net_fields = ["rank", "total_score", "first_item_status", "first_item_raw_score", "first_item_add_on",
                  "second_item_score", "third_item_score", "fourth_item_adjustment", "component_details",
                  "weight_sensitivity"]
    records = []
    for person in main:
        rid = person["ruler_id"]
        record = pick(person, ["ruler_id", "ruler_name", "polity", "actual_power_window", "settlement_readiness"])
        projected_net = pick(net[rid], net_fields) if rid in net else None
        if projected_net:
            projected_net["component_details"] = project_net_explanations(
                person,
                net[rid],
                net_reader_sources,
                first_item_public_outcomes,
            )
            reader_summary = second_item_reader_summaries.get(rid)
            if reader_summary:
                projected_net["reader_governance_summary"] = reader_summary
        record.update(net=projected_net,
                      impact=history[rid], axes={code: axis_projection(rows[rid], axis_fields) for code, rows in axes.items()},
                      supplementary=False)
        records.append(record)
    for row in impact.get("supplementary_records", []):
        if row["ruler_id"] in main_ids:
            raise ValueError("Supplementary sample overlaps main pool")
        records.append(dict(ruler_id=row["ruler_id"], ruler_name=row["ruler_name"], polity=row["polity"],
                            actual_power_window=row.get("reference_power_window", ""),
                            settlement_readiness="SUPPLEMENTARY", net=None, axes={}, impact=row, supplementary=True))
    index(records)

    source_identity = reader_source_identity(write=write and not check)
    person_notes_snapshot(check=check, write=write)
    common = dict(main_count=len(main), ranked_count=len(net),
                  source_repository=source_identity["repository"],
                  source_revision=source_identity["revision"],
                  weight_sensitivity=ranking.get("weight_sensitivity", {}),
                  supplementary_count=len(records)-len(main), formula=ranking["formula"],
                  capability_axes=profile["capability_axes"], independent_axes=profile["independent_profile_axes"],
                  axis_order=profile["axis_order"],
                  axis_specs={k: pick(v, ["name", "json", "markdown", "contract"]) for k,v in profile["settled_axes"].items()},
                  impact_grades=impact_config["public_grade_order"],
                  impact_dimension_grades=impact_config["dimension_grade_order"],
                  impact_labels=impact["public_label_mapping"],
                  sources=dict(net=scoring["composite_ranking_json"], impact=impact_config["json"],
                               net_reader=scoring["composite_ranking_markdown"], impact_reader=impact_config["markdown"]))

    # Full return value preserves build/test semantics. Only the browser bootstrap is slimmed.
    data = dict(records=records, **common)
    data["source_availability"] = source_availability(data)

    index_data = dict(records=[record_summary(record) for record in records], **common)
    index_data["detail_schema_version"] = "reader-person-detail-v1"
    index_data["source_availability"] = source_availability(common)

    detail_files = {}
    for record in records:
        relative = detail_ref(record["ruler_id"])
        detail_files[Path(relative).name] = serialized_json(detail_payload(record)) + "\n"

    payload = serialized_json(index_data, html_safe=True)
    template = (ROOT / "reader/index.template.html").read_text(encoding="utf-8")
    template = apply_public_copy(template)
    template = inline_runtime_scripts(template)
    link_effects = (ROOT / "reader/link-effects.css").read_text(encoding="utf-8").strip()
    readability_css = (ROOT / "reader/readability.css").read_text(encoding="utf-8").strip()
    lazy_details = (ROOT / "reader/lazy-details.js").read_text(encoding="utf-8").strip()
    home_interactions = (ROOT / "reader/home-interactions.js").read_text(encoding="utf-8").strip()
    readability_js = (ROOT / "reader/readability.js").read_text(encoding="utf-8").strip()
    person_readability_js = (ROOT / "reader/person-readability.js").read_text(encoding="utf-8").strip()
    if "</style>" not in template:
        raise ValueError("Reader template must contain a style block")
    template = template.replace("</style>", f"\n{link_effects}\n{readability_css}\n</style>", 1)
    if "</body>" not in template:
        raise ValueError("Reader template must contain a body close tag")
    template = template.replace(
        "</body>",
        f"<script>\n{lazy_details}\n</script>\n<script>\n{home_interactions}\n</script>\n<script>\n{readability_js}\n</script>\n<script>\n{person_readability_js}\n</script>\n</body>",
        1,
    )
    output = ROOT / "reader/index.html"
    if template.count("__READER_DATA__") != 1:
        raise ValueError("Reader template must contain exactly one data placeholder")
    rendered = template.replace("__READER_DATA__", payload)

    expected_detail_names = set(detail_files)
    actual_detail_names = {p.name for p in DETAILS_DIR.glob("*.json")} if DETAILS_DIR.exists() else set()
    if check:
        if not output.exists() or output.read_bytes() != rendered.encode("utf-8"):
            raise ValueError("Reader is stale; run python reader/build.py")
        if actual_detail_names != expected_detail_names:
            missing = sorted(expected_detail_names - actual_detail_names)
            extra = sorted(actual_detail_names - expected_detail_names)
            raise ValueError(f"Reader detail shards are stale: missing={missing}, extra={extra}")
        for name, content in detail_files.items():
            if (DETAILS_DIR / name).read_bytes() != content.encode("utf-8"):
                raise ValueError(f"Reader detail shard is stale: {name}")
    elif write:
        output.write_text(rendered, encoding="utf-8", newline="\n")
        DETAILS_DIR.mkdir(parents=True, exist_ok=True)
        for stale in DETAILS_DIR.glob("*.json"):
            if stale.name not in expected_detail_names:
                stale.unlink()
        for name, content in detail_files.items():
            (DETAILS_DIR / name).write_text(content, encoding="utf-8", newline="\n")

    index_kib = len(rendered.encode("utf-8")) / 1024
    detail_mib = sum(len(content.encode("utf-8")) for content in detail_files.values()) / (1024 * 1024)
    print(
        f"Reader built: main={len(main)}, ranked={len(net)}, supplementary={len(records)-len(main)}, "
        f"index={index_kib:.0f}KiB, details={len(detail_files)} files/{detail_mib:.1f}MiB"
    )
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check current data/template/detail parity without writing")
    build(check=parser.parse_args().check)
