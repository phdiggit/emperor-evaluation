"""Build the offline reading prototype from registered settlements; never adjudicate."""
from pathlib import Path
import json
import sys
import argparse
import re
from urllib.parse import unquote

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.profile_parent_schema import parent_chains


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


def axis_projection(row, fields):
    result = pick(row, fields)
    result["source_refs"] = list(dict.fromkeys(
        ref for owner in [row, *parent_chains(row)]
        for ref in owner.get("source_refs", []) if isinstance(ref, str)
    ))
    counter = row.get("counterpattern")
    if isinstance(counter, dict):
        ids = {ref for values in counter.values() if isinstance(values, list) for ref in values if isinstance(ref, str)}
        result["context_lookup"] = {
            p["parent_id"]: pick(p, ["parent_id", "cycle_basis", "basis", "source_refs", "direction"])
            for p in parent_chains(row) if p.get("parent_id") in ids
        }
        missing = ids - result["context_lookup"].keys()
        if missing:
            raise ValueError(f"Unresolved context references: {sorted(missing)}")
    return result


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
        record.update(net=pick(net[rid], net_fields) if rid in net else None,
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
    data = dict(records=records, main_count=len(main), ranked_count=len(net),
                weight_sensitivity=ranking.get("weight_sensitivity", {}),
                supplementary_count=len(records)-len(main), formula=ranking["formula"],
                capability_axes=profile["capability_axes"], independent_axes=profile["independent_profile_axes"],
                axis_order=profile["axis_order"],
                axis_specs={k: pick(v, ["name", "json", "markdown", "contract"]) for k,v in profile["settled_axes"].items()},
                impact_grades=impact_config["public_grade_order"],
                impact_labels=impact["public_label_mapping"],
                sources=dict(net=scoring["composite_ranking_json"], impact=impact_config["json"],
                             net_reader=scoring["composite_ranking_markdown"], impact_reader=impact_config["markdown"]))
    data["source_availability"] = {
        ref: (ROOT / source_file(ref)).exists()
        for ref in sorted(local_sources(data))
    }
    # HTML script embedding must not allow source prose to terminate its data element.
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    template = (ROOT / "reader/index.template.html").read_text(encoding="utf-8")
    template = apply_public_copy(template)
    link_effects = (ROOT / "reader/link-effects.css").read_text(encoding="utf-8").strip()
    if "</style>" not in template:
        raise ValueError("Reader template must contain a style block")
    template = template.replace("</style>", f"\n{link_effects}\n</style>", 1)
    output = ROOT / "reader/index.html"
    if template.count("__READER_DATA__") != 1:
        raise ValueError("Reader template must contain exactly one data placeholder")
    rendered = template.replace("__READER_DATA__", payload)
    if check:
        if not output.exists() or output.read_bytes() != rendered.encode("utf-8"):
            raise ValueError("Reader is stale; run python reader/build.py")
    elif write:
        output.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"Reader built: main={len(main)}, ranked={len(net)}, supplementary={len(records)-len(main)}")
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check current data/template parity without writing")
    build(check=parser.parse_args().check)
