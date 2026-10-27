"""Build the static reading layer from registered settlements; never adjudicate."""
from pathlib import Path
from copy import deepcopy
import json
import os
import sys
import argparse
import hashlib
from html.parser import HTMLParser
import re
from html import escape
from urllib.parse import unquote, quote

import yaml

ROOT = Path(__file__).resolve().parents[1]
DETAILS_DIR = ROOT / "reader/data/people"
SECOND_ITEM_READER_SUMMARIES = "reader/second-item-summaries.json"
SOURCE_IDENTITY_PATH = ROOT / "reader/source-revision.json"
PERSON_NOTES_SOURCE = ROOT / "reader/person-reading-notes.json"
PERSON_NOTES_SNAPSHOT = ROOT / "reader/data/person-reading-notes.json"
READER_RUNTIME_SCRIPTS = (
    "second-item-display.js",
    "fourth-item-a-public.js",
    "fourth-item-b-public.js",
    "fourth-item-c-public.js",
    "third-item-c-public.js",
    "third-item-b-public.js",
    "third-item-a-public.js",
    "second-item-public-alias.js",
    "second-item-c-public.js",
    "second-item-a-public.js",
    "second-item-b1-public.js",
    "second-item-public-labels.js",
    "person-reading-notes.js",
)
sys.path.insert(0, str(ROOT / "src"))
from emperor_v4.json_format import json_text
from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.first_item_public_outcomes import (
    load_first_item_public_outcomes,
    public_outcome_for_name,
    SOURCE_MARKDOWN_PATH as FIRST_A_SOURCE,
    _parse_source_sections as parse_first_a_source,
)
from emperor_v4.evaluation.profile_parent_schema import parent_chains, representative_parent_chains
from emperor_v4.evaluation.profile_m1_evidence import verify_evidence_scope
from emperor_v4.evaluation.historical_impact import SOURCE_DISPLAY
from emperor_v4.evaluation.first_item_c_public import (
    load_first_item_c_public, public_commander_for_name,
    SOURCE_MARKDOWN_PATH as FIRST_C_SOURCE,
)
from emperor_v4.evaluation.first_item_b1_cost_public import (
    load_first_item_b1_cost_public, B1_SOURCE as FIRST_B1_SOURCE, COST_SOURCE as FIRST_COST_SOURCE,
)
from emperor_v4.evaluation.first_item_b2_public import load_first_item_b2_public, SOURCE as FIRST_B2_SOURCE
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
                json_text(identity),
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


def write_generated_text(path, content):
    if path.exists() and path.read_bytes() == content.encode('utf-8'):
        return
    import tempfile
    temporary_dir = ROOT / '.tmp' / 'reader-writes'
    temporary_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                     dir=temporary_dir, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def person_notes_snapshot(*, check=False, write=True):
    content = PERSON_NOTES_SOURCE.read_text(encoding="utf-8")
    expected = content if content.endswith("\n") else content + "\n"
    if check:
        if not PERSON_NOTES_SNAPSHOT.exists() or PERSON_NOTES_SNAPSHOT.read_text(encoding="utf-8") != expected:
            raise ValueError("Reader person-reading-notes snapshot is stale")
    elif write:
        PERSON_NOTES_SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        write_generated_text(PERSON_NOTES_SNAPSHOT, expected)


def person_note_reference_issues(records, notes):
    """Report missing editorial anchors against the actual public projection."""
    by_id = {record['ruler_id']: record for record in records}
    issues = []
    expected_ids = {record['ruler_id'] for record in records if not record.get('supplementary')}
    for rid in sorted(expected_ids ^ notes.get('records', {}).keys()):
        issues.append((rid, 'coverage', []))
    for rid, entry in notes.get('records', {}).items():
        for section in sorted({'outcome', 'profile', 'impact'} - entry.get('overview', {}).keys()):
            issues.append((rid, section, []))
        for section, block in entry.get('overview', {}).items():
            if not block.get('text') or not block.get('evidence'):
                issues.append((rid, section, []))
            for reference in block.get('evidence', []):
                value = by_id.get(rid)
                for key in reference['path']:
                    if isinstance(value, dict):
                        value = value.get(key)
                    elif isinstance(value, list) and isinstance(key, int) and 0 <= key < len(value):
                        value = value[key]
                    else:
                        value = None
                        break
                if not isinstance(value, str) or reference['quote'] not in value:
                    issues.append((rid, section, reference['path']))
    return issues


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
    "process_narrative",
    "basis",
    "source_refs",
    "cycle_anchor_refs",
    "direct_process_refs",
    "direction",
    "consumption_status",
    "intensity",
    "material_intensity",
    "attribution",
    "attribution_basis",
    "role_attribution",
    "limitations",
    "limitation",
    "intensity_and_role_basis",
    "evidence_title",
    "evidence_detail",
    "lifecycle_narrative",
    "coalition_task",
    "group_structure",
    "interests_and_security_expectations",
    "personal_choice",
    "status_and_resource_configuration",
    "political_credit_and_delivery",
    "feedback_and_conflict_handling",
    "exit_result",
    "counterevidence",
    "lifecycle_reasoning",
    "boundary_review",
]


def runtime_script_blocks():
    """Freeze validated runtime JS directly into the generated reader artifact."""
    blocks = []
    for filename in READER_RUNTIME_SCRIPTS:
        source = (ROOT / "reader" / filename).read_text(encoding="utf-8")
        source = source.replace("</script>", r"<\/script>")
        blocks.append(f"<script>\n{source}\n</script>")
    return "\n".join(blocks)


def _formal_context_projection(context):
    # Public reading may only expose fields that already exist in the formal
    # record. Never synthesize direction, strength, attribution or limits here.
    return pick(context, FORMAL_CONTEXT_FIELDS)


def axis_projection(row, fields, m1_archive_context=None):
    result = pick(row, fields)
    if (row.get('public_reading') or {}).get('schema_version') == 'profile-m1-authored-reading-v1' and (row['public_reading'].get('career_review') or row['public_reading'].get('comparisons')):
        from emperor_v4.evaluation.profile_m1_public import archive_projection
        result['m1_archive_links'] = archive_projection(row, ROOT, m1_archive_context)
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
    refs = _formal_source_refs(record, item.get("source"), item.get("applied_source"), *source_refs,
                               *(ref["path"] for entry in evidence for ref in entry.get("source_refs", [])))
    if refs:
        result["reader_source_refs"] = refs
    return result


def _attach_method_public_reader(item, *, axis, record, how=""):
    """A/B1 overviews consume the same declared public prose as detail cards."""
    summary = record.get("public_adjudication_summary")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError(f"{axis} formal public summary is missing: {record.get('ruler_name')}")
    if axis == "A":
        evidence = record.get("public_evidence_items")
        if not isinstance(evidence, list):
            raise ValueError(f"A formal public evidence is missing: {record.get('ruler_name')}")
        if not isinstance(record.get("public_story"), str) or not record["public_story"].strip():
            raise ValueError(f"A formal public story is missing: {record.get('ruler_name')}")
        evidence = deepcopy(evidence)
    elif axis == "B1":
        evidence = record.get("public_evidence_items")
        if not isinstance(evidence, list) or not evidence:
            raise ValueError(f"B1 formal public evidence is missing: {record.get('ruler_name')}")
        evidence = deepcopy(evidence)
    else:
        raise ValueError(f"Unsupported method axis: {axis}")
    result = dict(item)
    result.update(reader_kind="judgment", reader_summary=summary,
                  public_adjudication_summary=summary, reader_public_evidence_items=evidence,
                  reader_how=how, reader_source_refs=_formal_source_refs(record, item.get("source"), item.get("applied_source")))
    if axis == "A":
        result["reader_story"] = record["public_story"]
    elif axis == "B1":
        for source_key, reader_key in (
            ("public_story", "reader_story"),
            ("public_responsibility", "reader_responsibility"),
            ("public_index_calculation", "reader_index_calculation"),
        ):
            value = record.get(source_key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"B1 formal {source_key} is missing: {record.get('ruler_name')}")
            result[reader_key] = value
        result["reader_how"] = record["public_index_calculation"] + "\n\n" + how
    declared_boundary = record.get("public_boundary")
    if isinstance(declared_boundary, str) and declared_boundary.strip():
        result["reader_boundary"] = declared_boundary
    else:
        boundaries = _unique_texts([node.get("public_boundary") for node in evidence], limit=None)
        if boundaries:
            result["reader_boundary"] = "\n\n".join(boundaries)
    return result


def _attach_second_item_c_public_reader(item, *, axis, record, how="", source_refs=()):
    """Project C1-C4 explicit public fields without reader-side adjudication."""

    if not isinstance(record, dict):
        raise ValueError(f"{axis} reader projection requires a formal record")
    if axis == 'C4':
        from emperor_v4.evaluation.second_item_c_reading import recovery_public_record
        record = recovery_public_record(record)
    summary = record.get("public_adjudication_summary")
    evidence = record.get("public_evidence_items")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError(f"{axis} formal public summary is missing: {record.get('ruler_name')}")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError(f"{axis} formal public evidence is missing: {record.get('ruler_name')}")
    result = dict(item)
    result["reader_kind"] = "judgment"
    result["public_component_label"] = {"C1":"民生", "C2":"经济财政", "C3":"社会安全", "C4":"恢复与额外代价"}[axis]
    result["reader_public_c"] = {key: deepcopy(record[key]) for key in (
        "public_story", "public_adjudication_summary", "public_evidence_items",
        "public_boundary", "public_loss_label", "public_calculation",
        "public_related_source_refs", "public_source_note",
    )}
    result["public_loss_label"] = record["public_loss_label"]
    if axis == 'C4':
        result['reader_public_c']['public_reading_sections'] = deepcopy(record['public_reading_sections'])
    result["reader_story"] = record["public_story"]
    result["reader_summary"] = summary
    result["public_adjudication_summary"] = summary
    result["reader_boundary"] = record["public_boundary"]
    result["reader_how"] = record["public_calculation"]
    refs = _formal_source_refs(record, item.get("source"), item.get("applied_source"), *source_refs)
    if refs:
        result["reader_source_refs"] = refs
    return result


def _attach_d1_d3_public_reader(item, *, record, axis, how="", source_refs=()):
    """Project D1/D3's explicit public fields without generic fallback guessing."""

    if not isinstance(record, dict):
        raise ValueError(f"{axis} reader projection requires a formal record")
    from emperor_v4.evaluation.second_item_d1_d3_public import public_record
    record = public_record(record)
    summary = record.get("public_adjudication_summary")
    evidence = record.get("public_evidence_items")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError(f"{axis} formal public summary is missing: {record.get('ruler_name')}")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError(f"{axis} formal public evidence is missing: {record.get('ruler_name')}")
    result = dict(item)
    result["reader_kind"] = "judgment"
    result["public_component_label"] = {"D1": "行政连续性", "D3": "交接稳定"}[axis]
    result["reader_summary"] = summary
    result["public_adjudication_summary"] = summary
    result["public_evidence_items"] = deepcopy(evidence)
    result["reader_public_evidence_items"] = deepcopy(evidence)
    result["reader_public_d"] = {
        key: deepcopy(record[key]) for key in (
            "public_story", "public_adjudication_summary", "public_window",
            "public_responsibility", "public_boundary", "public_evidence_items",
        )
    }
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
    if axis and isinstance(record.get("axes"), dict):
        projection = record["axes"][axis]
    elif axis and isinstance(record.get("axis_results"), list):
        matches = [entry for entry in record["axis_results"] if entry.get("axis") == axis]
        if len(matches) != 1:
            raise ValueError(f"{axis} formal public axis must have one authoritative record")
        projection = matches[0]
    elif axis and isinstance(projections, dict) and isinstance(projections.get(axis), dict):
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
    from emperor_v4.evaluation.second_item_c_reading import calculation_record
    for axis in ('C1', 'C2', 'C3', 'C4'):
        sources[axis] = {rid: calculation_record(axis, row) for rid, row in sources[axis].items()}
    from emperor_v4.evaluation.third_item_c_contract_reading import load_context
    sources['C_review_context'] = load_context(root)
    from emperor_v4.evaluation.third_fourth_item_public import FOURTH_PATH
    sources['fourth_packages'] = {p['package_code']: p for p in load_json(root / FOURTH_PATH)['accepted_packages']}
    sources['first_c_public'] = load_first_item_c_public(root)
    sources['first_b1_public'], sources['first_cost_public'] = load_first_item_b1_cost_public(root)
    sources['first_b2_public'] = load_first_item_b2_public(root)
    for key, path in NET_READER_EXTRA_SOURCES.items():
        payload = load_json(root / path)
        rows = payload["records"]
        sources[key] = index(rows)
        sources[f"{key}_path"] = path
    return sources


def load_second_item_reader_summaries(root, allowed_ids, eligible_ids):
    """Load persisted reader-only conclusions without coupling them to composite rank."""

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
    allowed = set(allowed_ids)
    eligible = set(eligible_ids)
    outside = sorted(set(summaries) - allowed)
    if outside:
        raise ValueError(f"Reader-only Second Item summaries reference rulers outside the formal pool: {outside}")
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
                outcome = first[label]["reader_public_outcome"]
                first[label]["reader_how"] = (
                    outcome["public_calculation_basis"]
                    + "\n本人的正式计算：" + outcome["public_calculation"]
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
            if item.get('value') is None:
                first[label] = _attach_reader(item, kind='judgment')
                continue
            public = public_commander_for_name(sources['first_b2_public'], name)
            if public['total_points'] != item['value']:
                raise ValueError(f'B2阅读投影与正式分数不同值：{name}')
            first[label] = _attach_reader(
                item, kind="judgment",
                summary=public['public_story'], boundary=public['public_window'],
                how=public['public_method'], source_refs=(FIRST_B2_SOURCE.as_posix(),),
            )
            first[label]['reader_public_b2'] = deepcopy(public)
        elif label == "C军事统帅与战争解题":
            if item.get('value') is None:
                first[label] = _attach_reader(item, kind='judgment')
                continue
            commander = public_commander_for_name(sources['first_c_public'], name)
            first[label] = _attach_reader(
                item, kind="judgment",
                summary=commander['public_story'],
                boundary=commander['public_boundary'],
                source_refs=tuple(commander['public_sources']),
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
            reading = deepcopy(credit['axes'][key]['public_reading'])
            strategic[key]['reader_public_a'] = reading
            strategic[key]['reader_how'] = reading['calculation']
            strategic[key]['reader_source_refs'] = [ref['path'] for ref in reading['sources']]
    from emperor_v4.evaluation.third_item_b_sources import expand_readings as expand_b_readings
    b_readings = expand_b_readings(ab)
    for key in ("B1", "B2", "B4"):
        if key in strategic:
            rate = credit["B80_adjudication"][f"adjudicated_{key}_rate"]
            strategic[key] = _attach_formal_public_reader(
                strategic[key], record=ab, axis=key,
                how=f"当前结果先得到 {strategic[key].get('value')}% 的得分率，合成时采用 {rate:g}%。",
            )
            reading = b_readings[key]
            if reading['raw_rate'] != strategic[key]['value'] or reading['adopted_rate'] != strategic[key]['applied_value']:
                raise ValueError(f'{tid} {key}原始率或实际采用率与正式来源不一致')
            strategic[key]['reader_public_b'] = reading
            strategic[key]['reader_how'] = reading['calculation'] + '\n\n' + reading['combination']
            strategic[key]['reader_source_refs'] = list(dict.fromkeys(ref['path'] for ref in reading['sources']))
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
        strategic['B80']['reader_how'] = ab['axes']['B1']['public_reading']['combination']
    if strategic:
        details["strategic"] = [strategic[item["label"]] for item in details["strategic"]]

    c_record = sources["C"][tid]
    from emperor_v4.evaluation.third_item_c_public import reading_projection as c_reading_projection
    from emperor_v4.evaluation.third_fourth_item_public import c_public_record, fourth_public_record
    c_reading = c_reading_projection(c_record, context=sources['C_review_context'])
    c_record = c_public_record(c_record, reading=c_reading)
    third = sources["third"][tid]
    military = {item["label"]: item for item in details.get("military", [])}
    specific_reason_keys = {
        "C1联合主评": ("joint_assessment",),
    }
    for label, keys in specific_reason_keys.items():
        if label in military:
            axis = label[:2]
            military[label] = _attach_formal_public_reader(
                military[label], record=c_record, axis=axis,
                how="以实战兑现为主评，保障、组织与恢复事实共同决定整体档位。",
            )
            if axis == 'C1':
                military[label]['reader_public_third_c'] = c_reading
                military[label]['public_component_label'] = '军事体系表现'
            else:
                military[label]['reader_kind'] = 'support'
    if "C50" in military:
        military["C50"] = _attach_formal_public_reader(
            military["C50"], record=c_record,
            how=c_reading['calculation']['grade_path'] + ' ' + c_reading['calculation']['formula'],
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
                "第三项合计": "军事与边疆总分",
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

    fourth = fourth_public_record(sources["fourth"][fid])
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
        if key == 'A':
            from emperor_v4.evaluation.fourth_item_a_public import axis_reading
            reading = axis_reading(fourth, axis, sources['fourth_packages'])
            civilization[label]['reader_public_fourth_a'] = reading
            civilization[label]['reader_how'] = reading['calculation']
        if key == 'B':
            from emperor_v4.evaluation.fourth_item_b_public import axis_reading
            reading = axis_reading(fourth, axis, sources['fourth_packages'])
            civilization[label]['reader_public_fourth_b'] = reading
            civilization[label]['reader_how'] = reading['calculation']
        if key == 'C':
            from emperor_v4.evaluation.fourth_item_c_public import axis_reading
            reading = axis_reading(fourth, axis, sources['fourth_packages'])
            civilization[label]['reader_public_fourth_c'] = reading
            civilization[label]['reader_c_collection_id'] = fourth['ruler_id']
            civilization[label]['reader_how'] = reading['calculation']
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


def public_power_window(value):
    """Turn structured-looking power windows into stable human-readable text."""
    if value is None:
        return ""
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    text = value.strip()
    if not text.startswith("["):
        return text
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return text
    if not isinstance(parsed, list) or not parsed:
        return text
    spans = []
    for span in parsed:
        if not isinstance(span, list) or len(span) != 2:
            return text
        start, end = span
        if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool):
            return text
        def year_label(year):
            return f"前{abs(year)}" if year < 0 else str(year)
        spans.append(f"{year_label(start)}—{year_label(end)}年")
    return "；".join(spans)


def public_governance_context(context):
    if not isinstance(context, dict):
        return context
    result = deepcopy(context)
    raw = result.get("actual_power_window")
    shown = public_power_window(raw)
    if raw is not None:
        result["actual_power_window"] = shown
    basis = result.get("basis")
    if isinstance(basis, str) and raw is not None and shown != str(raw):
        result["basis"] = basis.replace(str(raw), shown)
    return result


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
        "settlement_readiness", "supplementary", "fourth_c_collection_ref",
    ])
    summary["net"] = pick(net, [
        "rank", "total_score", "first_item_status", "first_item_raw_score", "first_item_add_on",
        "second_item_score", "third_item_score", "fourth_item_adjustment",
        "evidence_assessment", "prudent_score_interval", "prudent_rank_projection", "governance_context",
    ]) if net else None
    if summary["net"] and net.get('evidence_assessment'):
        summary["net"]['evidence_assessment'] = pick(net['evidence_assessment'],
            ['score_status','score_label','rank_status','rank_label'])
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


def collection_source_link(ref, label):
    if ref.startswith(('http://', 'https://')):
        return f"<a href='{escape(ref)}' target='_blank' rel='noopener'>{escape(label)}</a>"
    identity = reader_source_identity()
    if identity['repository'] and identity['revision']:
        href = 'https://github.com/' + identity['repository'] + '/blob/' + identity['revision'] + '/' + quote(ref, safe='/#=')
    else:
        href = '../' + quote(ref, safe='/#=')
    return f"<a href='{escape(href)}' data-local-source='{escape(ref)}' target='_blank' rel='noopener'>{escape(label)}</a>"


def render_first_a_collection(outcomes):
    """Publish every formal A reading entry, including people without a total score."""
    sections = parse_first_a_source(ROOT / FIRST_A_SOURCE)
    cards = []
    for name, outcome in outcomes.items():
        result = sections[name].get("结算结果", "")
        match = re.search(r"A为\s*([\d.]+)/120", result)
        if not match:
            raise ValueError(f"第一项A缺少可展示的正式分值：{name}")
        fields = (("起点", "public_outcome_basis"), ("成果范围", "public_scope"), ("具体范围说明", "public_boundary"))
        facts = "".join(f"<dt>{label}</dt><dd><p class='prose'>{escape(outcome[key])}</p></dd>" for label, key in fields if outcome[key])
        project = f"<p class='first-a-project'>共同项目：{escape(outcome['public_project'])}</p>" if outcome["public_project"] else ""
        method = "".join(f"<p class='prose'>{escape(text)}</p>" for text in (
            f"本人成果规模：约{outcome['public_share_percent']:g}%全国核心统一尺度。",
            outcome["public_scale_basis"], outcome["public_calculation_basis"], outcome["public_calculation"],
        ))
        source_link = collection_source_link(FIRST_A_SOURCE.as_posix(), '查看正式裁决与史料 ↗')
        cards.append(
            f"<article id='{escape(name)}' class='first-a-reading'>"
            f"<div class='first-a-eyebrow'><a href='#{escape(name)}'>{escape(name)}</a> · 奠基与统一成果</div>"
            f"<div class='first-a-heading'><h3>{escape(outcome['public_question'])}</h3><span class='first-a-score'>{escape(match[1])}<small> / 120</small></span></div>"
            f"<div class='first-a-story'><p class='prose'>{escape(outcome['public_story'])}</p></div>"
            f"<details class='first-a-attribution'><summary>展开成果与归属</summary>{project}<dl>{facts}</dl>"
            f"<details class='first-a-method'><summary>查看尺度、计算与史料</summary>{method}"
            f"<p class='sources'>{source_link}</p></details></details></article>"
        )
    template = (ROOT / "reader/first-item-a.template.html").read_text(encoding="utf-8")
    return template.replace("__A_COUNT__", str(len(cards))).replace("__A_ENTRIES__", "\n".join(cards))


def render_first_b1_collection(records):
    """Display every declared B1 reading entry; no judgment is made here."""
    cards = []
    for name, record in records.items():
        facts = ''.join(f"<dt>{label}</dt><dd><p class='prose'>{escape(record[key])}</p></dd>" for label, key in (
            ('当时的家底', 'public_start_basis'), ('实际对手', 'public_opponent_basis'), ('计时范围', 'public_efficiency_basis')))
        components = ''.join(f"<span>{label} <b>{record[key]:g}</b><small> / {cap}</small></span>" for label, key, cap in (
            ('起点难度', 'start_points', 15), ('对手压力', 'opponent_points', 15), ('成果效率', 'efficiency_points', 20)))
        sources = ' '.join(collection_source_link(ref, f'依据{i} ↗') for i, ref in enumerate(record['public_sources'], 1))
        cards.append(
            f"<article id='{escape(name)}' class='first-a-reading first-b1-reading'>"
            f"<div class='first-a-eyebrow'><a href='#{escape(name)}'>{escape(name)}</a> · 条件与效率</div>"
            f"<div class='first-a-heading'><h3>{escape(record['public_question'])}</h3><span class='first-a-score'>{record['total_points']:g}<small> / 50</small></span></div>"
            f"<div class='first-a-story'><p class='prose'>{escape(record['public_story'])}</p></div><div class='first-b1-components'>{components}</div>"
            f"<details class='first-b1-facts'><summary>展开家底、实际对手与计时</summary><dl>{facts}</dl>"
            f"<details class='first-b1-method'><summary>查看分数计算与史料</summary><p class='prose'>{escape(record['public_method'])}</p>"
            f"<p class='prose'>{escape(record['public_calculation'])}</p><p class='sources'>{sources}</p></details></details></article>"
        )
    template = (ROOT / 'reader/first-item-b1.template.html').read_text(encoding='utf-8')
    return template.replace('__B1_COUNT__', str(len(cards))).replace('__B1_ENTRIES__', '\n'.join(cards))


def render_first_b2_collection(records):
    """Display the complete upstream B2 pool, including people without a total."""
    cards = []
    for name, record in records.items():
        components = ''.join(f"<span>{escape(d['label'])} <b>{d['points']}</b><small> / 10</small></span>" for d in record['dimensions'])
        reasons = ''.join(f"<dt>{escape(d['label'])} · {d['points']}/10</dt><dd><p class='prose'>{escape(d['basis'])}</p></dd>" for d in record['dimensions'])
        sources = ' '.join(collection_source_link(ref, f'依据{i} ↗') for i, ref in enumerate(record['public_sources'], 1))
        cards.append(
            f"<article id='{escape(name)}' class='first-a-reading first-b2-reading'>"
            f"<div class='first-a-eyebrow'><a href='#{escape(name)}'>{escape(name)}</a> · 组织与协作</div>"
            f"<div class='first-a-heading'><h3>{escape(record['public_question'])}</h3><span class='first-a-score'>{record['total_points']}<small> / 30</small></span></div>"
            f"<div class='first-a-story'><p class='prose'>{escape(record['public_story'])}</p></div><div class='first-b1-components'>{components}</div>"
            f"<details class='first-b2-facts'><summary>展开当时的职责与本人作用</summary><dl><dt>评价时期</dt><dd><p class='prose'>{escape(record['public_window'])}</p></dd>"
            f"<dt>本人实际授权与调度</dt><dd><p class='prose'>{escape(record['public_control'])}</p></dd></dl>"
            f"<details class='first-b2-method'><summary>查看三项裁决、限制与史料</summary><p class='prose'>{escape(record['public_method'])}</p>"
            f"<dl>{reasons}</dl><p class='sources'>{sources}</p></details></details></article>"
        )
    template = (ROOT / 'reader/first-item-b2.template.html').read_text(encoding='utf-8')
    return template.replace('__B2_COUNT__', str(len(cards))).replace('__B2_ENTRIES__', '\n'.join(cards))


def render_first_c_collection(records):
    """Render every declared C story and its evidence without inventing prose."""
    cards = []
    for name, record in records.items():
        sources = ' '.join(collection_source_link(ref, f'依据{i} ↗') for i, ref in enumerate(record['public_sources'], 1))
        battles = ''.join(
            f"<li><strong>{escape(row['name'])}</strong> · {escape(row['role'])} · 战役成果：{escape(row['result'])} · "
            f"{escape('任务难度：' + row['difficulty'] if row['difficulty'] else '任务难度：未单列')} "
            + (f"<a href='{escape(row['archive_url'])}'>查看战役档案 ↗</a></li>" if row.get('archive_url')
             else collection_source_link(row['public_source'], '查看公共本人条目 ↗') + '</li>')
            for row in record['public_battles']
        )
        positive = f"<div class='first-c-positive'><h4>已定档的正向结果</h4><p class='subline'>字母刻度属于军事材料，不是人物画像等级；只表示该次正向结果，同场受挫在下方合看。</p><ul>{battles}</ul></div>" if battles else ''
        setbacks = ''.join(f"<div class='first-c-setback'><strong>{escape(row['name'])}</strong><span class='first-c-direction'>{escape(row['direction'])}</span><p class='prose'>{escape(row['process'])}</p>" + ' '.join(collection_source_link(ref, '核对公共登记 ↗') for ref in row['public_sources']) + '</div>' for row in record['public_setbacks'])
        negative = f"<div class='first-c-setbacks'><h4>同时保留的受挫与损失</h4>{setbacks}</div>" if setbacks else ''
        evidence_rows = []
        for row in record['public_evidence']:
            facts = ''.join(f"<dt>{escape(label)}</dt><dd><p class='prose'>{escape(value)}</p></dd>" for label, value in row['public_facts'])
            source_refs = '<br>'.join(escape(ref) for ref in row['source_refs'])
            evidence_rows.append(f"<article class='first-c-evidence-entry'><h4>{escape(row['label'])}</h4><span class='first-c-direction'>{escape(row['disposition'])}</span><p class='prose'>{escape(row['window_basis'])}</p><p class='prose'>{escape(row['reason'])}</p><dl>{facts}</dl>{collection_source_link(row['public_source'], '查看所在公共登记分片 ↗')}<p class='sources'>{source_refs}</p></article>")
        evidence = "<details class='first-c-registry'><summary>逐条对照公共战役登记</summary>" + ''.join(evidence_rows) + '</details>'
        cards.append(
            f"<article id='{escape(name)}' class='first-a-reading first-c-reading'>"
            f"<div class='first-a-eyebrow'><a href='#{escape(name)}'>{escape(name)}</a> · 本人统帅</div>"
            f"<div class='first-a-heading'><h3>{escape(record['public_question'])}</h3><span class='first-a-score'>{record['total_points']:g}<small> / 40</small></span></div>"
            f"<div class='first-a-story'><p class='prose'>{escape(record['public_story'])}</p></div>"
            f"<details class='first-c-facts'><summary>展开战争范围与本人指挥</summary><dl><dt>评价时期</dt><dd><p class='prose'>{escape(record['public_window'])}</p></dd>"
            f"<dt>本人责任与独立任务</dt><dd><p class='prose'>{escape(record['public_cases'])}</p></dd></dl>"
            f"<details class='first-c-method'><summary>查看评价、胜败依据、规则与史料</summary><h4>当前评价</h4><p class='prose'>{escape(record['public_basis'])}</p>"
            f"<h4>具体范围与责任边界</h4><p class='prose'>{escape(record['public_boundary'])}</p>{positive}{negative}{evidence}"
            f"<p class='prose'>{escape(record['public_method'])}</p><p class='sources'>{sources}</p></details></details></article>"
        )
    template = (ROOT / 'reader/first-item-c.template.html').read_text(encoding='utf-8')
    return template.replace('__C_COUNT__', str(len(cards))).replace('__C_ENTRIES__', '\n'.join(cards))


def render_second_b2_collection(root):
    from emperor_v4.evaluation.second_item_b2_public import B2_PATH, verify_public_projection
    payload = load_json(root / B2_PATH)
    verify_public_projection(root, payload)
    cards = []
    for row in payload['records']:
        window = row['reign_range']
        if isinstance(window, list):
            window = '、'.join(str(value) for value in window)
        items = []
        for item in row['public_evidence_items']:
            sources = []
            for ref in item['source_refs']:
                source_links = collection_source_link(ref['path'], '材料登记 ↗')
                if ref['source_url']:
                    source_links += ' ' + collection_source_link(ref['source_url'], '史源 ↗')
                sources.append(f"<p>{escape(ref['source_title'])} · {escape(ref['source_locator'])} {source_links}</p>" +
                               (f"<blockquote>{escape(ref['exact_quote'])}</blockquote>" if ref['exact_quote'] else ''))
            items.append(f"<li data-public-evidence-id='{escape(item['id'])}'><strong>{escape(item['public_label'])}</strong>"
                         f"<p class='meta'>{escape(item['public_direction'])} · {escape('、'.join(item['public_tags']))}</p>"
                         f"<p>{escape(item['public_basis'])}</p><details><summary>范围与边界</summary><p>{escape(item['public_boundary'])}</p></details>"
                         f"<details><summary>本条史料与归责依据</summary>{''.join(sources)}</details></li>")
        cards.append(f"<article id='{escape(row['ruler_id'])}'><h2>{escape(row['ruler_name'])}</h2>"
                     f"<p class='meta'>{escape(row['polity'])} · {escape(str(window))}</p>"
                     f"<h3>为什么是这个等级</h3><p class='b2-adjudication-summary'>{escape(row['public_adjudication_summary'])}</p>"
                     f"<details><summary>逐条事实、方向、边界与史料</summary><ul>{''.join(items)}</ul></details></article>")
    template = (root / 'reader/second-item-b2.template.html').read_text(encoding='utf-8')
    return template.replace('__COUNT__', str(len(cards))).replace('__ENTRIES__', '\n'.join(cards))


def render_second_c_collection(root):
    from emperor_v4.evaluation.second_item_c_public import FORMAL_PATHS, verify_public_projection
    verify_public_projection(root)
    payloads = {axis: load_json(root / path) for axis, path in FORMAL_PATHS.items()}
    from emperor_v4.evaluation.second_item_c_reading import calculation_record
    from emperor_v4.evaluation.second_item_c_source_notes import source_note_records
    indexed = {axis: {row['ruler_id']: calculation_record(axis, row) for row in source_note_records(payload)} for axis, payload in payloads.items()}
    cards = []
    names = {'C1': '民生', 'C2': '经济财政', 'C3': '社会安全', 'C4': '恢复与额外代价'}
    def paragraphs(value):
        return ''.join(f"<p class='prose'>{escape(text)}</p>" for text in value.split('\n\n'))
    def render_sources(refs):
        return ''.join(
            f"<section><p>{escape(ref['source_kind'])} · {escape(ref['source_title'])} · {escape(ref['source_locator'])}</p>"
            f"<blockquote>{escape(ref['exact_quote'])}</blockquote>{collection_source_link(ref['path'], '查看所引原记录 ↗')}"
            + (f" <a href='{escape(ref['source_url'])}' target='_blank' rel='noopener'>查看所引史源 ↗</a>" if ref.get('source_url') else '') + '</section>'
            for ref in refs)
    for person in payloads['C1']['scores']:
        sections = []
        for axis in FORMAL_PATHS:
            row = indexed[axis][person['ruler_id']]
            facts = []
            for item in row['public_evidence_items']:
                sources = render_sources(item['source_refs'])
                mode = {'DIRECT':'史料直接记载', 'INFERRED':'受约束推断', 'ASSESSMENT':'正式评价判断', 'BACKGROUND':'背景互证', 'EXCLUDED':'不采用的范围核对'}[item['evidence_mode']]
                relation = (f"<details><summary>本条史料与评价依据</summary>{sources}</details>" if item['source_binding_kind'] == 'CLAIM_SUPPORT'
                            else '<p class="meta">本条沿用正式裁决叙述；相关材料列于人物材料汇集，尚未建立逐条事实的支持关系。</p>')
                facts.append(f"<li data-public-evidence-id='{escape(item['id'])}'><h4>{escape(item['public_label'])}</h4>"
                             f"<p class='meta'>{mode}</p>{paragraphs(item['public_basis'])}{paragraphs('采用范围：' + item['public_scope'])}"
                             f"{paragraphs(item['public_boundary']) if item['public_boundary'] else ''}"
                             f"{relation}</li>")
            related = (f"<details><summary>相关材料汇集（不代表逐条事实已获证明）</summary>{render_sources(row['public_related_source_refs'])}</details>" if row['public_related_source_refs'] else '')
            story = (''.join(f"<section class='c-recovery-section' data-recovery-section='{escape(s['id'])}'>"
                             f"<h4>{escape(s['title'])}</h4>{paragraphs(s['body'])}</section>"
                             for s in row['public_reading_sections'])
                     if axis == 'C4' else paragraphs(row['public_story']))
            sections.append(
                f"<section class='c-axis' data-axis='{axis}'><h3>{names[axis]} · {row['score']:g}分</h3>"
                f"<div class='c-public-story'>{story}</div>"
                f"<details><summary>为什么这样评</summary>{paragraphs(row['public_adjudication_summary'])}{paragraphs(row['public_loss_label'])}</details>"
                f"<details><summary>裁决叙述与来源</summary>{paragraphs(row['public_source_note'])}<ul>{''.join(facts)}</ul>{related}</details>"
                f"<details><summary>评价范围与限制</summary>{paragraphs(row['public_boundary'])}</details>"
                f"<details><summary>这个分怎么算？</summary>{paragraphs(row['public_calculation'])}</details></section>"
            )
        cards.append(f"<article id='{escape(person['ruler_id'])}'><h2>{escape(person['ruler_name'])}</h2>"
                     f"<p class='meta'>{escape(person['polity'])}</p>{''.join(sections)}</article>")
    template = (root / 'reader/second-item-c.template.html').read_text(encoding='utf-8')
    return template.replace('__COUNT__', str(len(cards))).replace('__ENTRIES__', '\n'.join(cards))


def _render_fourth_ab_collection(root, axis_code, axis_reading, verify_readings):
    from emperor_v4.evaluation.third_fourth_item_public import FOURTH_PATH

    payload = load_json(root / FOURTH_PATH)
    verify_readings(payload, root)
    packages = {p['package_code']: p for p in payload['accepted_packages']}
    pool = index(load_json(root / 'config/common/canonical-ruler-pool.json')['records'])
    records = []
    for row in sorted(payload['records'], key=lambda r: (r['ruler_name'], r['ruler_id'])):
        axis = next(a for a in row['axis_results'] if a['axis'] == axis_code)
        scope = pool[row['ruler_id']]
        note = ('已具综合结算' if scope['settlement_readiness'] == 'COMPOSITE_READY' else
                '保留的池外单项记录，不纳入综合评价池' if scope['pool_status'] == 'EXCLUDED' else '其他分项待补，暂不进入综合总榜')
        records.append(dict(ruler_id=row['ruler_id'], ruler_name=row['ruler_name'], polity=row['polity'], pool_note=note,
                            item={f'reader_public_fourth_{axis_code.lower()}': axis_reading(row, axis, packages)}))
    template = (root / f'reader/fourth-item-{axis_code.lower()}.template.html').read_text(encoding='utf-8')
    return template.replace('__COUNT__', str(len(records))).replace('__PAYLOAD__', serialized_json(records, html_safe=True)).replace('__SOURCE_IDENTITY__', serialized_json(reader_source_identity(), html_safe=True))


def render_fourth_a_collection(root):
    from emperor_v4.evaluation.fourth_item_a_public import axis_reading, verify_readings

    return _render_fourth_ab_collection(root, 'A', axis_reading, verify_readings)


def render_fourth_b_collection(root):
    from emperor_v4.evaluation.fourth_item_b_public import axis_reading, verify_readings

    return _render_fourth_ab_collection(root, 'B', axis_reading, verify_readings)


def render_fourth_c_collection(root):
    from emperor_v4.evaluation.third_fourth_item_public import FOURTH_PATH
    from emperor_v4.evaluation.fourth_item_c_public import axis_reading, verify_readings
    payload = load_json(root / FOURTH_PATH)
    verify_readings(payload, root)
    packages = {p['package_code']: p for p in payload['accepted_packages']}
    pool = index(load_json(root / 'config/common/canonical-ruler-pool.json')['records'])
    included = {}
    for scope in pool.values():
        if scope['pool_status'] != 'INCLUDED':
            continue
        formal_id = scope.get('source_item_ids', {}).get('fourth_item', scope['ruler_id'])
        if formal_id in included:
            raise ValueError('Fourth-item C reader mapping is not unique')
        included[formal_id] = scope
    records = []
    for row in sorted(payload['records'], key=lambda r: (r['ruler_name'], r['ruler_id'])):
        axis = next(a for a in row['axis_results'] if a['axis'] == 'C')
        scope = included.get(row['ruler_id']) or pool[row['ruler_id']]
        available = row['ruler_id'] in included
        ready = available and scope['settlement_readiness'] == 'COMPOSITE_READY'
        person_id = quote(scope['ruler_id'], safe='')
        note = ('已具综合结算' if ready else '其他分项待补，暂不进入综合总榜' if available
                else '保留的池外单项记录，不纳入综合评价池')
        records.append(dict(ruler_id=row['ruler_id'], ruler_name=row['ruler_name'], polity=row['polity'], pool_note=note,
                            person_href=f'index.html#person/{person_id}' if available else '',
                            detail_href=f'index.html#net/{person_id}/fourth/c' if ready else '',
                            item=dict(reader_c_collection_id=row['ruler_id'], reader_public_fourth_c=axis_reading(row, axis, packages))))
    template = (root / 'reader/fourth-item-c.template.html').read_text(encoding='utf-8')
    return template.replace('__COUNT__', str(len(records))).replace('__PAYLOAD__', serialized_json(records, html_safe=True)).replace('__SOURCE_IDENTITY__', serialized_json(reader_source_identity(), html_safe=True))


def collection_search_text(markup):
    """Index every displayed passage once without adding a second evidence copy to the page."""
    class Text(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
        def handle_data(self, value):
            if value.strip():
                self.parts.append(value)
    parser = Text()
    parser.feed(markup)
    return '\n'.join(dict.fromkeys(parser.parts))


def third_c_grade_meaning(axis):
    """Read the existing axis scale; an unknown grade must never become grade zero."""
    return '证据不足，暂不定档' if axis['grade'] is None else axis['scale'][axis['grade']]


def render_third_c_grade_guide():
    from emperor_v4.evaluation.third_item_c_public import SCALES, METHOD
    from emperor_v4.evaluation.third_item_c_joint import BANDS
    meanings=''.join('<li>'+escape(t)+'</li>' for t in SCALES[0])
    bands=''.join(f'<tr><th>{g}档</th><td>{lo}%—{hi}%</td></tr>' for g,(lo,hi) in enumerate(BANDS))
    return ('<section class="third-c-grade-guide"><h2>档位与分数怎么读</h2><p>'+escape(METHOD)+'</p>'
            '<p>以实际作战为主，保障、组织和恢复事实共同决定整体判断。缺证暂不计分；继承保有能力最高三档。</p>'
            '<details><summary>0—5档含义</summary><ol start="0">'+meanings+'</ol></details>'
            '<details><summary>得分率区间</summary><table>'+bands+'</table></details></section>')


def build_third_c_collection(root):
    from emperor_v4.evaluation.third_item_c_commander_reading import commander_html
    from emperor_v4.evaluation.third_item_c_contract_reading import html_review, load_context
    from emperor_v4.evaluation.third_fourth_item_public import THIRD_C_PATH
    from emperor_v4.evaluation.third_item_c_public import COMBAT_GUIDE, reading_projection, verify_sources
    payload = load_json(root / THIRD_C_PATH)
    c_review_context = load_context(root)
    verify_sources(root, payload, context=c_review_context)
    def paragraphs(value):
        return ''.join(f"<p class='prose'>{escape(text)}</p>" for text in value.split('\n\n'))
    def c_material(e):
        excerpts = ''.join('<p class="meta">来源摘录（' + escape(p.get('kind', e['kind'])) + '）</p><blockquote>' + escape(p['quote']) + '</blockquote>' for p in e.get('source_passages', []))
        return (f"<li class='third-c-material' id='{escape(material_id(e['id']))}' tabindex='-1' data-c-evidence='{escape(e['id'])}'><details><summary>{escape(e['label'])}</summary>"
                + paragraphs(e['kind']) + paragraphs(e['text'])
                + (paragraphs('为什么影响判断：' + e['reason']) if e.get('reason') else '')
                + '<details><summary>本条的范围与原记录</summary>' + paragraphs(e['scope'])
                + ' '.join(collection_source_link(s['path'], s['label'] + ' ↗') for s in e['sources'])
                + excerpts
                + (paragraphs('原登记史源：' + '；'.join(map(str, e['historical_source_refs']))) if e.get('historical_source_refs') else '')
                + '</details></details></li>')
    cards, assets, search_rows = [], {}, {}
    for row in payload['records']:
        data = reading_projection(row, context=c_review_context)
        c = data['calculation']
        def material_id(evidence_id):
            return row['ruler_id'] + '--evidence--' + evidence_id
        evidence_by_id = {e['id']: e for e in data['evidence_items']}
        def material_link(ref):
            if ref not in evidence_by_id:
                raise ValueError(f'第三项C核查材料未绑定：{ref}')
            e = evidence_by_id[ref]
            return (f"<a href='#{quote(material_id(ref), safe='')}' data-c-material-ref='{escape(material_id(ref))}' title='原材料编号：{escape(ref)}'>"
                    + escape(e['label'] + ' · ' + e['kind']) + '</a>')
        def argument(e):
            return (f"<li><a href='#{quote(material_id(e['id']), safe='')}' data-c-material-ref='{escape(material_id(e['id']))}'>{escape(e['label'])} ↗</a>"
                    + (paragraphs(e['reason']) if e.get('reason') else '') + '</li>')
        axes = (paragraphs(c['grade_path']) + paragraphs(data['position_explanation'])
                + '<details><summary>各档含义与判断方法</summary><ol start="0">'
                + ''.join(f'<li>{escape(t)}</li>' for t in data['axes']['C1']['scale']) + '</ol>'
                + paragraphs(data['axes']['C1']['assessment_guide'])
                + paragraphs(data['assessment_scope_note']) + '</details>')
        evidence = ''.join(c_material(e) for e in data['evidence_items'])
        overview = ''.join(f"<div><span>{escape(a['label'])}</span><strong>{escape(a['grade_label'])}</strong><span class='third-c-grade-meaning'>{escape(third_c_grade_meaning(a))}</span><small class='third-c-review-status' data-review-status='{escape(a['review_status'])}'>分界论证：{escape(a['review_label'])}</small></div>" for a in data['axes'].values())
        detail = (f"<div class='third-c-person-body'><p class='meta'>评价时期：{escape(data['window'])}</p>"
                     + f"<div class='component'><strong>军事体系表现</strong><b>{escape(c['total_label'])}</b></div>"
                     + paragraphs(data['story'])
                     + '<details class="third-c-reasons"><summary>档位与档内位置</summary>' + axes + '</details>'
                     + '<details><summary>本人责任与评价范围</summary>' + paragraphs(data['responsibility']) + paragraphs(data['boundary']) + '</details>'
                     + commander_html(data['commander_profiles'])
                     + '<details class="third-c-evidence-list"><summary>战事摘要与来源</summary>' + paragraphs(data['source_note']) + '<ul>' + evidence + '</ul></details>'
                     + '<details class="third-c-audit"><summary>任务范围、对手与关键阶段</summary>' + html_review(data['contract_review'], collection_source_link, evidence_link=material_link) + '</details>'
                     + '<details class="third-c-calculation"><summary>分数怎样计算</summary>'
                     + ''.join(paragraphs(c[k]) for k in ('formula',))
                     + '<details><summary>共同计算规则</summary>' + paragraphs(c['method']) + '</details></details>'
                     + '</div>')
        detail_ref(row['ruler_id'])
        name = row['ruler_id'] + '.html'
        assets[name] = detail
        url = 'data/third-item-c/' + name + '?v=' + hashlib.sha256(detail.encode('utf-8')).hexdigest()[:16]
        overview_text = ' '.join((row['ruler_name'], row['polity'], data['window'], data['story']))
        cards.append(f"<article id='{escape(row['ruler_id'])}' data-formal-public-source data-detail-url='{escape(url)}' data-search='{escape(overview_text)}'><details class='third-c-person'>"
                     + f"<summary class='third-c-person-summary'><div class='third-c-person-title'><h2>{escape(row['ruler_name'])}</h2><span class='meta'>{escape(row['polity'])}</span></div>"
                     + f"<div class='third-c-overview' aria-label='整体正式判断'>{overview}</div></summary>"
                     + "<div class='third-c-detail-slot' aria-live='polite'><p>展开后加载完整正文与材料。</p></div></details></article>")
        search_rows[row['ruler_id']] = overview_text + '\n' + collection_search_text(detail)
    template = (root / 'reader/third-item-c.template.html').read_text(encoding='utf-8')
    template = template.replace('__THIRD_C_FORMAL_SOURCE_LINK__', collection_source_link(THIRD_C_PATH.as_posix(), '查看正式记录'))
    assets['search.json'] = json_text(search_rows)
    search_url = 'data/third-item-c/search.json?v=' + hashlib.sha256(assets['search.json'].encode('utf-8')).hexdigest()[:16]
    script = (root / 'reader/third-item-c-collection.js').read_text(encoding='utf-8')
    page = template.replace('__COUNT__', str(len(cards))).replace('__ENTRIES__', '\n'.join(cards)).replace('__COMBAT_GUIDE__', paragraphs(COMBAT_GUIDE)).replace('__GRADE_GUIDE__', render_third_c_grade_guide())
    return page.replace('__SEARCH_URL__', escape(search_url)).replace('__COLLECTION_SCRIPT__', script), assets


def third_c_asset_paths(directory):
    return {p.name: p for p in directory.iterdir()
            if p.is_file() and (p.name == 'search.json' or re.fullmatch(r'RULER-[\w-]+\.html', p.name))} if directory.exists() else {}


def verify_third_c_assets(directory, expected):
    actual = third_c_asset_paths(directory)
    if set(actual) != set(expected):
        raise ValueError('Third-item C detail/search asset coverage is stale')
    for name, content in expected.items():
        if actual[name].read_bytes() != content.encode('utf-8'):
            raise ValueError(f'Third-item C detail/search asset is stale: {name}')


def write_third_c_assets(directory, expected):
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in expected.items():
        write_generated_text(directory / name, content)
    for name, path in third_c_asset_paths(directory).items():
        if name not in expected:
            path.unlink()


def render_second_d_collection(root):
    from emperor_v4.evaluation.second_item_d1_d3_public import D1_PATH, D3_PATH, MODES, verify_public_projection, public_record
    verify_public_projection(root)
    payloads = {axis: load_json(root / path) for axis, path in (("D1", D1_PATH), ("D3", D3_PATH))}
    indexed = {axis: {row['ruler_id']: row for row in payload['records']} for axis, payload in payloads.items()}
    totals = {row['ruler_id']: row for row in load_json(root / D1_PATH.with_name('03-交接质量20分正式结算.json'))['records']}

    def paragraphs(value):
        return ''.join(f'<p class="prose">{escape(part)}</p>' for part in value.split('\n\n'))

    def sources(refs):
        blocks = []
        for ref in refs:
            local = ref['path']
            links = collection_source_link(local, '查看所引记录 ↗')
            if ref.get('source_url', '').startswith('https://'):
                links += f' · <a href="{escape(ref["source_url"], quote=True)}" target="_blank" rel="noopener">查看史源 ↗</a>'
            blocks.append(f'<section><p class="meta">{escape(ref["source_kind"])} · {escape(ref["source_title"])} · {escape(ref["source_locator"])}</p>'
                          + (paragraphs(ref['support_role']) if ref.get('support_role') else '')
                          + f'<blockquote>{escape(ref["public_excerpt"])}</blockquote><p>{links}</p></section>')
        return ''.join(blocks)

    cards = []
    for person in payloads['D1']['records']:
        sections = []
        for axis, title in (('D1', '行政连续性'), ('D3', '交接稳定')):
            row = public_record(indexed[axis][person['ruler_id']])
            level = row['handoff_level'] if axis == 'D1' else row['D3_grade']
            facts = ''.join(f'<li data-public-evidence-id="{escape(item["id"])}"><h4>{escape(item["public_label"])}</h4>'
                            f'<p class="meta">{MODES[item["evidence_mode"]]}</p>{paragraphs(item["public_basis"])}'
                            f'{paragraphs(item["public_boundary"])}<details><summary>本条史料与评价依据</summary>'
                            f'{sources(item["source_refs"])}</details></li>' for item in row['public_evidence_items'])
            sections.append(f'<section class="d-axis" data-axis="{axis}" data-formal-public-source><h3>{title} · {handoff_public_grade(level[-1])}档</h3>'
                            f'{paragraphs(row["public_story"])}<details><summary>为什么这样评</summary>{paragraphs(row["public_adjudication_summary"])}</details>'
                            f'<details><summary>观察范围与本人责任</summary>{paragraphs(row["public_window"])}{paragraphs(row["public_responsibility"])}{paragraphs(row["public_boundary"])}</details>'
                            f'<details><summary>逐条事实与史料</summary><ul>{facts}</ul></details></section>')
        total = totals[person['ruler_id']]
        cards.append(f'<article id="{escape(person["ruler_id"])}"><h2>{escape(person["ruler_name"])}</h2>'
                     f'<p class="meta">{escape(person["polity"])} · 政权交接 {total["score"]:g} / 20</p>{"".join(sections)}</article>')
    template = (root / 'reader/second-item-d.template.html').read_text(encoding='utf-8')
    return template.replace('__COUNT__', str(len(cards))).replace('__ENTRIES__', '\n'.join(cards))


def build(*, check=False, write=True):
    config = yaml.safe_load((ROOT / "config/project.yml").read_text(encoding="utf-8"))
    pool = load_json(ROOT / config["canonical_ruler_pool"]["json"])
    main = [r for r in pool["records"] if r["pool_status"] == "INCLUDED"]
    main_ids = set(index(main))
    scoring = config["scoring_contract"]
    ranking = load_json(ROOT / scoring["composite_ranking_json"])
    from emperor_v4.evaluation.composite_details import reading_records
    net = index(reading_records(ROOT, ranking["records"], pool["records"]))
    ready = {r["ruler_id"] for r in main if r["settlement_readiness"] == "COMPOSITE_READY"}
    if set(net) != ready:
        raise ValueError("Composite ranking does not match current ready pool")
    second_item_reader_summaries = load_second_item_reader_summaries(ROOT, main_ids, ready)
    net_reader_sources = load_net_reader_sources(ROOT)
    first_b1_collection = render_first_b1_collection(net_reader_sources['first_b1_public'])
    first_b1_output = ROOT / 'reader/first-item-b1.html'
    first_b2_collection = render_first_b2_collection(net_reader_sources['first_b2_public'])
    first_b2_output = ROOT / 'reader/first-item-b2.html'
    second_b2_collection = render_second_b2_collection(ROOT)
    second_b2_output = ROOT / 'reader/second-item-b2.html'
    second_c_collection = render_second_c_collection(ROOT)
    second_c_output = ROOT / 'reader/second-item-c.html'
    third_c_collection, third_c_assets = build_third_c_collection(ROOT)
    third_c_output = ROOT / 'reader/third-item-c.html'
    third_c_dir = ROOT / 'reader/data/third-item-c'
    fourth_a_collection = render_fourth_a_collection(ROOT)
    fourth_a_output = ROOT / 'reader/fourth-item-a.html'
    fourth_b_collection = render_fourth_b_collection(ROOT)
    fourth_b_output = ROOT / 'reader/fourth-item-b.html'
    fourth_c_collection = render_fourth_c_collection(ROOT)
    fourth_c_output = ROOT / 'reader/fourth-item-c.html'
    second_d_collection = render_second_d_collection(ROOT)
    second_d_output = ROOT / 'reader/second-item-d.html'
    first_c_collection = render_first_c_collection(net_reader_sources['first_c_public'])
    first_c_output = ROOT / 'reader/first-item-c.html'
    first_item_public_outcomes = load_first_item_public_outcomes(ROOT)
    first_a_collection = render_first_a_collection(first_item_public_outcomes)
    first_a_output = ROOT / "reader/first-item-a.html"
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
        if code == "M1":
            from emperor_v4.evaluation.profile_m1_public import validate_public_reading
            for row in rows.values():
                verify_evidence_scope(row)
                if not row.get('public_reading'):
                    raise ValueError('M1正式对象缺少直接维护的公开正文')
                validate_public_reading(row)
        axes[code] = rows
    axis_fields = ["axis_grade", "position", "radar_value", "output_mode", "confidence",
                   "applicability_status", "not_applicable_reason", "grade_basis", "typical_pattern",
                   "counterpattern", "limitations", "person_type", "score_status", "axis_evidence_level",
                   "adjudication_state", "display_point_only", "formal_status", "no_grade_closure",
                   "position_basis", "applicability_basis", "evidence_assessment_basis",
                   "assessment_basis", "final_capability_review", "evidence_scope", "m1_stability_review", "public_reading"]
    net_fields = ["rank", "total_score", "first_item_status", "first_item_raw_score", "first_item_add_on",
                  "second_item_score", "third_item_score", "fourth_item_adjustment", "component_details",
                  "weight_sensitivity", "evidence_assessment", "prudent_score_interval",
                  "prudent_rank_projection", "governance_context"]
    from emperor_v4.evaluation.profile_m1_public import load_archive_context
    m1_archive_context = load_archive_context(ROOT)
    records = []
    for person in main:
        rid = person["ruler_id"]
        record = pick(person, ["ruler_id", "ruler_name", "polity", "actual_power_window", "settlement_readiness"])
        fourth_id = person.get('source_item_ids', {}).get('fourth_item', rid)
        if fourth_id in net_reader_sources['fourth']:
            record['fourth_c_collection_ref'] = fourth_id
        record["actual_power_window"] = public_power_window(record.get("actual_power_window"))
        projected_net = pick(net[rid], net_fields) if rid in net else None
        if projected_net:
            projected_net['evidence_assessment'] = net[rid]['evidence_assessment']['public_projection']
            projected_net["governance_context"] = public_governance_context(projected_net.get("governance_context"))
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
                      impact=history[rid], axes={code: axis_projection(rows[rid], axis_fields, m1_archive_context) for code, rows in axes.items()},
                      supplementary=False)
        records.append(record)
    for row in impact.get("supplementary_records", []):
        if row["ruler_id"] in main_ids:
            raise ValueError("Supplementary sample overlaps main pool")
        records.append(dict(ruler_id=row["ruler_id"], ruler_name=row["ruler_name"], polity=row["polity"],
                            actual_power_window=public_power_window(row.get("reference_power_window", "")),
                            settlement_readiness="SUPPLEMENTARY", net=None, axes={}, impact=row, supplementary=True))
    index(records)

    source_identity = reader_source_identity(write=write and not check)
    note_issues = person_note_reference_issues(records, json.loads(PERSON_NOTES_SOURCE.read_text(encoding='utf-8')))
    if note_issues:
        affected = sorted({rid for rid, _, _ in note_issues})
        sample = '; '.join(f'{rid}/{section}/{path}' for rid, section, path in note_issues[:6])
        raise ValueError(f"Reader overview references need review: {len(note_issues)} issues / {len(affected)} people: {sample}")
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
                  impact_source_display=SOURCE_DISPLAY,
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
        detail_files[Path(relative).name] = json_text(detail_payload(record))

    payload = serialized_json(index_data, html_safe=True)
    template = (ROOT / "reader/index.template.html").read_text(encoding="utf-8")
    template = apply_public_copy(template)
    link_effects = (ROOT / "reader/link-effects.css").read_text(encoding="utf-8").strip()
    readability_css = (ROOT / "reader/readability.css").read_text(encoding="utf-8").strip()
    runtime_scripts = runtime_script_blocks()
    lazy_details = (ROOT / "reader/lazy-details.js").read_text(encoding="utf-8").strip()
    second_item_reading_js = (ROOT / "reader/second-item-reading.js").read_text(encoding="utf-8").strip()
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
        f"{runtime_scripts}\n<script>\n{lazy_details}\n</script>\n<script>\n{second_item_reading_js}\n</script>\n<script>\n{home_interactions}\n</script>\n<script>\n{readability_js}\n</script>\n<script>\n{person_readability_js}\n</script>\n</body>",
        1,
    )
    output = ROOT / "reader/index.html"
    if template.count("__READER_DATA__") != 1:
        raise ValueError("Reader template must contain exactly one data placeholder")
    rendered = template.replace("__READER_DATA__", payload)

    expected_detail_names = set(detail_files)
    actual_detail_names = {p.name for p in DETAILS_DIR.glob("*.json")} if DETAILS_DIR.exists() else set()
    if check:
        verify_third_c_assets(third_c_dir, third_c_assets)
        if not fourth_c_output.exists() or fourth_c_output.read_bytes() != fourth_c_collection.encode('utf-8'):
            raise ValueError('Fourth-item C full-pool reading collection is stale')
        if not fourth_b_output.exists() or fourth_b_output.read_bytes() != fourth_b_collection.encode('utf-8'):
            raise ValueError('Fourth-item B full-pool reading collection is stale')
        if not fourth_a_output.exists() or fourth_a_output.read_bytes() != fourth_a_collection.encode('utf-8'):
            raise ValueError('Fourth-item A full-pool reading collection is stale')
        if not third_c_output.exists() or third_c_output.read_bytes() != third_c_collection.encode('utf-8'):
            raise ValueError('Third-item C full-pool reading collection is stale')
        if not second_d_output.exists() or second_d_output.read_bytes() != second_d_collection.encode('utf-8'):
            raise ValueError('Second-item D full-pool reading collection is stale')
        if not second_b2_output.exists() or second_b2_output.read_bytes() != second_b2_collection.encode('utf-8'):
            raise ValueError('Second-item B2 full-pool reading collection is stale')
        if not second_c_output.exists() or second_c_output.read_bytes() != second_c_collection.encode('utf-8'):
            raise ValueError('Second-item C full-pool reading collection is stale')
        if not first_c_output.exists() or first_c_output.read_bytes() != first_c_collection.encode('utf-8'):
            raise ValueError('C collection is stale; run python reader/build.py')
        if not first_b2_output.exists() or first_b2_output.read_bytes() != first_b2_collection.encode('utf-8'):
            raise ValueError('B2 collection is stale')
        if not first_b1_output.exists() or first_b1_output.read_bytes() != first_b1_collection.encode('utf-8'):
            raise ValueError('First-item B1 reading collection is stale; run python reader/build.py')
        if not first_a_output.exists() or first_a_output.read_bytes() != first_a_collection.encode("utf-8"):
            raise ValueError("First-item A reading collection is stale; run python reader/build.py")
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
        write_third_c_assets(third_c_dir, third_c_assets)
        write_generated_text(fourth_a_output, fourth_a_collection)
        write_generated_text(fourth_b_output, fourth_b_collection)
        write_generated_text(fourth_c_output, fourth_c_collection)
        write_generated_text(third_c_output, third_c_collection)
        write_generated_text(second_d_output, second_d_collection)
        write_generated_text(second_b2_output, second_b2_collection)
        write_generated_text(second_c_output, second_c_collection)
        write_generated_text(first_c_output, first_c_collection)
        write_generated_text(first_b1_output, first_b1_collection)
        write_generated_text(first_b2_output, first_b2_collection)
        write_generated_text(first_a_output, first_a_collection)
        write_generated_text(output, rendered)
        DETAILS_DIR.mkdir(parents=True, exist_ok=True)
        for stale in DETAILS_DIR.glob("*.json"):
            if stale.name not in expected_detail_names:
                stale.unlink()
        for name, content in detail_files.items():
            write_generated_text(DETAILS_DIR / name, content)

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
