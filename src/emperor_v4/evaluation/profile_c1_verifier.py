from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from emperor_v4.evaluation.formal_json_store import ROUTER_SCHEMA, load_json

from emperor_v4.evaluation.profile_markdown import render_profile_markdown


SETTLEMENT_NAME = "C1/15-C1战略判断与风险控制正式结算.json"
MARKDOWN_NAME = "C1/15-C1战略判断与风险控制正式结算.md"
UNIT_AUDIT_NAME = "C1/16-C1主要入口单元处置审计.json"
HIGH_REVIEW_NAME = "C1/17-C1高档能力剖面复核.json"


def _load(path: Path) -> dict:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"UTF-8 BOM is forbidden: {path}")
    return load_json(path)


def _contract_scores(contract: Path) -> dict[tuple[str, str], int]:
    scores: dict[tuple[str, str], int] = {}
    pattern = re.compile(r"^\| (G[0-5]) \| (\d+) \| (\d+) \| (\d+) \|$")
    for line in contract.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if match:
            grade, low, mid, high = match.groups()
            for position, value in zip(("LOW", "MID", "HIGH"), (low, mid, high), strict=True):
                scores[(grade, position)] = int(value)
    if len(scores) != 18:
        raise ValueError("C1 contract score table is incomplete")
    return scores


def _source_path(root: Path, ref: str) -> Path | None:
    source = re.split(r"#|:\d+(?::\d+)?$", ref, maxsplit=1)[0]
    if not source.startswith("docs/"):
        return None
    return root / source


def _cached_text(path: Path, cache: dict[Path, str]) -> str:
    text = cache.get(path)
    if text is None:
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            raw = json.loads(text)
            if isinstance(raw, dict) and raw.get("schema_version") == ROUTER_SCHEMA:
                text = json.dumps(load_json(path), ensure_ascii=False)
        cache[path] = text
    return text


def _is_direct_process_ref(root: Path, parent: dict, ref: str, cache: dict[Path, str]) -> bool:
    if ref.startswith("https://"):
        return True
    path = _source_path(root, ref)
    if path is not None:
        return path.is_file()
    if re.match(r"^[^/]+/卷\d+[@#].+", ref):
        return True
    if not (
        re.match(r"^(?:PCR|WAR|FIN|SRC|EVD|EM)-[A-Z0-9-]+$", ref)
        or re.match(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+){2,}$", ref)
    ):
        return False
    for source_ref in parent["source_refs"] + parent["direct_process_refs"]:
        source_file = _source_path(root, source_ref)
        if source_file is None or not source_file.is_file():
            continue
        text = _cached_text(source_file, cache)
        if ref in text:
            return True
    return False


def _audit_source_ref_is_traceable(root: Path, ref: str, cache: dict[Path, str]) -> bool:
    if not ref or "MISSING" in ref or ref.endswith(("#", "=")):
        return False
    if ref.startswith("https://"):
        return True
    path = _source_path(root, ref)
    if path is None or not path.is_file():
        return False
    if "#" not in ref:
        return True
    fragment = ref.split("#", 1)[1]
    if not fragment:
        return False
    text = _cached_text(path, cache)
    line_match = re.fullmatch(r"L(\d+)", fragment)
    if line_match:
        return 1 <= int(line_match.group(1)) <= len(text.splitlines())
    pointer_match = re.fullmatch(r"records/(\d+)", fragment)
    if pointer_match and path.suffix == ".json":
        payload = json.loads(text)
        rows = payload.get("records")
        return isinstance(rows, list) and int(pointer_match.group(1)) < len(rows)
    if "=" in fragment:
        value = fragment.split("=", 1)[1].split("/", 1)[0]
        return bool(value) and value in text
    return fragment in text


def verify(root: Path) -> dict[str, object]:
    profile_root = root / "docs" / "评分结算" / "皇帝人物画像"
    contract = root / "docs" / "项目总纲" / "皇帝人物画像评估体系合同.md"
    pool_path = root / "config" / "common" / "canonical-ruler-pool.json"
    settlement_path = profile_root / SETTLEMENT_NAME
    markdown_path = profile_root / MARKDOWN_NAME
    audit_path = profile_root / UNIT_AUDIT_NAME
    review_path = profile_root / HIGH_REVIEW_NAME
    manifest_path = profile_root / "00-已结算轴正式入口.json"
    config_path = root / "config" / "project.yml"

    for path in (contract, pool_path, settlement_path, markdown_path, audit_path, review_path, manifest_path, config_path):
        raw = path.read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            raise ValueError(f"UTF-8 BOM is forbidden: {path}")
        raw.decode("utf-8")

    settlement = _load(settlement_path)
    pool = _load(pool_path)
    audit = _load(audit_path)
    review = _load(review_path)
    manifest = _load(manifest_path)
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    records = settlement["records"]
    if markdown_path.read_text(encoding="utf-8") != render_profile_markdown(settlement):
        raise ValueError("C1 Markdown is not the deterministic JSON reading view")
    pool_records = [record for record in pool["records"] if record["pool_status"] == "INCLUDED"]
    pool_ids = {record["ruler_id"] for record in pool_records}

    if settlement["canonical_status"] != "FORMAL_CURRENT" or settlement["axis_code"] != "C1":
        raise ValueError("C1 settlement is not formal current")
    if settlement["record_count"] != len(records) or len(records) != len(pool_ids):
        raise ValueError("C1 record count differs from canonical included pool")
    if len({record["ruler_id"] for record in records}) != len(records):
        raise ValueError("C1 ruler IDs are not unique")
    if {record["ruler_id"] for record in records} != pool_ids:
        raise ValueError("C1 coverage differs from canonical included pool")
    if records != sorted(records, key=lambda record: (-record["radar_value"], record["ruler_id"])):
        raise ValueError("C1 records are not in formal stable order")
    manifest_axis = next((axis for axis in manifest["axes"] if axis["axis_code"] == "C1"), None)
    if manifest_axis is None or manifest_axis["json"] != SETTLEMENT_NAME:
        raise ValueError("C1 is absent from formal profile manifest")
    if not settlement.get("contract_version"):
        raise ValueError("C1 settlement lacks contract lineage")
    config_axis = config["profile_assessment"]["settled_axes"].get("C1")
    if config_axis is None or not config_axis["json"].endswith(SETTLEMENT_NAME):
        raise ValueError("C1 is absent from config project entry")

    scores = _contract_scores(contract)
    parent_ids: set[str] = set()
    scoring_parent_ids: set[str] = set()
    high_ids: set[str] = set()
    low_ids: set[str] = set()
    source_cache: dict[Path, str] = {}
    for record in records:
        expected_score = scores[(record["axis_grade"], record["position"])]
        if record["score_100"] != expected_score or record["radar_value"] != expected_score:
            raise ValueError(f"score mapping mismatch: {record['ruler_id']}")
        if record["axis_evidence_level"] == "E0":
            raise ValueError(f"E0 remains: {record['ruler_id']}")
        if record["formal_status"] != "FORMAL_CURRENT":
            raise ValueError(f"non-formal record: {record['ruler_id']}")
        if not record["limitations"] and record["score_status"] == "EVIDENCE_LIMITED":
            raise ValueError(f"evidence-limited record lacks limitation: {record['ruler_id']}")
        if record["axis_grade"] in {"G4", "G5"}:
            high_ids.add(record["ruler_id"])
        if record["axis_grade"] in {"G0", "G1"}:
            low_ids.add(record["ruler_id"])
            if record["reviews"]["low_grade_gate"]["status"] != "CLOSED":
                raise ValueError(f"low-grade bidirectional gate failed: {record['ruler_id']}")
        for parent in record["parents"]:
            parent_id = parent["parent_id"]
            if parent_id in parent_ids:
                raise ValueError(f"duplicate parent ID: {parent_id}")
            parent_ids.add(parent_id)
            if parent["consumption_status"] == "SCORING_PARENT":
                scoring_parent_ids.add(parent_id)
                if parent["direction"] == "LIMITATION":
                    raise ValueError(f"limitation consumed as score: {parent_id}")
                if not parent["mechanisms"]:
                    raise ValueError(f"scoring parent lacks mechanism: {parent_id}")
                if parent["intensity"] in {"MI3", "MI4"} and not parent["direct_process_refs"]:
                    raise ValueError(f"MI3/MI4 parent lacks direct process locator: {parent_id}")
            for ref in parent["source_refs"] + parent["direct_process_refs"]:
                source_path = ref.partition("#")[0]
                source_path = re.sub(r":\d+(?::\d+)?$", "", source_path)
                if source_path.startswith("docs/") and not (root / source_path).is_file():
                    raise ValueError(f"source path is not traceable: {parent_id}: {source_path}")
            for ref in parent["direct_process_refs"]:
                if not _is_direct_process_ref(root, parent, ref, source_cache):
                    raise ValueError(f"pseudo direct process locator: {parent_id}: {ref}")

    if len(high_ids) != review["current_high_grade_count"]:
        raise ValueError("high-grade profile count mismatch")
    profiles = review["profiles"]
    profile_by_id = {profile["ruler_id"]: profile for profile in profiles}
    if not high_ids <= profile_by_id.keys():
        raise ValueError("current high-grade ruler lacks capability profile")
    if len(profiles) != review["review_count"]:
        raise ValueError("C1 semantic reaudit profile count mismatch")
    if any(profile.get("ps") not in {"PS0", "PS1", "PS2", "PS3", "PS4"} for profile in profiles):
        raise ValueError("unknown positive diagnostic strength")
    if any(profile.get("dw") not in {"DW0", "DW1", "DW2", "DW3", "DW4"} for profile in profiles):
        raise ValueError("unknown negative diagnostic weight")
    allowed_mechanism_values = {"LIMITED", "MIXED", "MODERATE", "STRONG"}
    if any(
        set(profile.get("mechanism_profile", {})) != {"problem", "resource", "path", "risk_exit"}
        or not set(profile["mechanism_profile"].values()) <= allowed_mechanism_values
        for profile in profiles
    ):
        raise ValueError("capability mechanism profile is incomplete")
    if len({tuple(profile["mechanism_profile"].values()) for profile in profiles}) < 8:
        raise ValueError("capability profiles remain template-converged")
    profile_sequences = {profile["sequence"] for profile in profiles}
    for record in records:
        if record["sequence"] not in profile_sequences:
            continue
        profile = next(profile for profile in profiles if profile["sequence"] == record["sequence"])
        direct_refs = {
            ref
            for parent in record["parents"]
            if parent["consumption_status"] == "SCORING_PARENT"
            and parent["direction"] in {"POSITIVE", "MIXED_POSITIVE"}
            for ref in parent["direct_process_refs"]
        }
        if set(profile.get("cycle_anchor_refs", [])) != direct_refs:
            raise ValueError(f"cycle anchor aggregation mismatch: {record['ruler_id']}")
        if len(direct_refs) < profile["independent_cycles"]:
            raise ValueError(f"independent cycle lacks stable event anchor: {record['ruler_id']}")
        for parent in record["parents"]:
            role = parent.get("diagnostic_role")
            if role is None:
                raise ValueError(f"reaudited parent lacks PS/DW diagnosis: {parent['parent_id']}")
            if parent["direction"] in {"POSITIVE", "MIXED_POSITIVE"} and not role.startswith("PS"):
                raise ValueError(f"positive parent has non-PS diagnosis: {parent['parent_id']}")
            if parent["direction"] in {"NEGATIVE", "MIXED_NEGATIVE", "LIMITATION"} and not role.startswith("DW"):
                raise ValueError(f"negative/limitation parent has non-DW diagnosis: {parent['parent_id']}")
            if role == "DW0" and parent["consumption_status"] == "SCORING_PARENT":
                raise ValueError(f"DW0 parent is incorrectly score-bearing: {parent['parent_id']}")
            if parent["direction"] == "MIXED_POSITIVE" and profile["dw"] != "DW0":
                if parent.get("counter_diagnostic_role") != profile["dw"]:
                    raise ValueError(f"mixed parent lacks separate DW diagnosis: {parent['parent_id']}")
        negative_parents = [
            parent for parent in record["parents"]
            if parent["consumption_status"] == "SCORING_PARENT"
            and parent["direction"] in {"NEGATIVE", "MIXED_NEGATIVE"}
        ]
        if profile["dw"] == "DW0" and negative_parents:
            raise ValueError(f"DW0 profile has score-bearing negative parent: {record['ruler_id']}")
        if profile["dw"] != "DW0" and not negative_parents:
            raise ValueError(f"DW profile lacks independent negative parent: {record['ruler_id']}")
    for ruler_id in high_ids:
        profile = profile_by_id[ruler_id]
        record = next(record for record in records if record["ruler_id"] == ruler_id)
        if (profile["regrade"], profile["position"]) != (record["axis_grade"], record["position"]):
            raise ValueError(f"capability profile does not match formal grade: {ruler_id}")
        if profile.get("counterexample_review") not in {"COUNTEREVIDENCE_FOUND", "COVERAGE_CLOSED"}:
            raise ValueError(f"high-grade counterexample review failed: {ruler_id}")
        if profile.get("late_degradation_review") not in {"LATE_COUNTER_FOUND", "NO_PATTERN_BREAK", "SHORT_WINDOW_LIMITED"}:
            raise ValueError(f"high-grade late-degradation review failed: {ruler_id}")
        if record["axis_grade"] == "G5" and record["position"] == "LOW" and not profile.get("g5_low_justification"):
            raise ValueError(f"G5-LOW lacks specific non-routine justification: {ruler_id}")
        four_mechanisms = all(
            profile["mechanism_profile"][key] in {"STRONG", "MIXED"}
            for key in ("problem", "resource", "path", "risk_exit")
        )
        alternative_gate = profile["cross_domain"] and profile["cross_phase"] and four_mechanisms
        if profile["ps"] not in {"PS3", "PS4"}:
            raise ValueError(f"G4/G5 lacks PS3 body: {ruler_id}")
        if profile["independent_cycles"] < 2 and not alternative_gate:
            raise ValueError(f"G4/G5 structural gate failed: {ruler_id}")
        if record["axis_grade"] == "G5":
            if profile["ps"] != "PS4":
                raise ValueError(f"G5 lacks PS4: {ruler_id}")
            if profile["independent_cycles"] < 2:
                raise ValueError(f"G5 decision thickness failed: {ruler_id}")
            if not profile["cross_domain"] or not profile["cross_phase"]:
                raise ValueError(f"G5 transfer/stability gate failed: {ruler_id}")
            if profile["difficulty"] not in {"HIGH", "VERY_HIGH"}:
                raise ValueError(f"G5 difficulty gate failed: {ruler_id}")
            if profile["dw"] == "DW0" and profile["counterexample_review"] == "COVERAGE_CLOSED":
                bounded = profile.get("bounded_counterexample_review")
                if not isinstance(bounded, dict):
                    raise ValueError(f"G5 zero-counter coverage lacks audit trace: {ruler_id}")
                if set(bounded.get("major_entries_consumed", [])) != {
                    "FIRST_A", "SECOND_MAJOR_CHOICE", "THIRD_SECURITY_DECISION",
                    "FIFTH_A2", "M1_PARENT_PROJECTION", "M2_PARENT_PROJECTION",
                }:
                    raise ValueError(f"G5 zero-counter major-entry review incomplete: {ruler_id}")
                if not bounded.get("power_window") or not bounded.get("same_construct_refs"):
                    raise ValueError(f"G5 zero-counter window/construct review incomplete: {ruler_id}")
                if not bounded.get("chronicle_or_official_history_refs") or not bounded.get("conclusion"):
                    raise ValueError(f"G5 zero-counter historical counter-search incomplete: {ruler_id}")
                for ref in bounded["same_construct_refs"] + bounded["chronicle_or_official_history_refs"]:
                    if not _audit_source_ref_is_traceable(root, ref, source_cache):
                        raise ValueError(f"G5 zero-counter review ref is not traceable: {ruler_id}: {ref}")

    units = audit["units"]
    if audit["unit_count"] != len(units) or len({unit["unit_id"] for unit in units}) != len(units):
        raise ValueError("C1 unit audit is incomplete or has duplicate IDs")
    allowed_statuses = {"SCORING_PARENT", "BACKGROUND_VALIDATION", "AXIS_OUT_WITH_REASON", "UNRESOLVED_GAP"}
    if any(unit["status"] not in allowed_statuses for unit in units):
        raise ValueError("unknown unit disposition")
    if audit["unresolved_count"] != 0 or any(unit["status"] == "UNRESOLVED_GAP" for unit in units):
        raise ValueError("C1 unresolved gap remains")
    for unit in units:
        if not _audit_source_ref_is_traceable(root, unit.get("source_ref", ""), source_cache):
            raise ValueError(f"unit source ref is not traceable: {unit['unit_id']}: {unit.get('source_ref')}")
        if unit["entry"] == "M1_PARENT_PROJECTION" and not (
            "#stable_parent_ref=" in unit["source_ref"] or unit["unit_id"].endswith("-NONE")
        ):
            raise ValueError(f"M1 projection lacks stable parent anchor: {unit['unit_id']}")
    audit_scoring_ids = {unit["scoring_parent_id"] for unit in units if unit["status"] == "SCORING_PARENT"}
    if None in audit_scoring_ids or audit_scoring_ids != scoring_parent_ids:
        raise ValueError("unit audit scoring/background separation mismatch")

    markdown_rows = [line for line in markdown_path.read_text(encoding="utf-8").splitlines() if line.startswith("| ")][1:]
    if len(markdown_rows) != len(records):
        raise ValueError("C1 markdown row count differs from formal records")
    for row, record in zip(markdown_rows, records, strict=True):
        if f"| {record['radar_value']} | {record['axis_grade']} | {record['position']} | {record['ruler_name']} |" not in row:
            raise ValueError(f"markdown/JSON order mismatch: {record['ruler_id']}")

    return {
        "status": "PASS",
        "record_count": len(records),
        "high_grade_count": len(high_ids),
        "low_grade_count": len(low_ids),
        "parent_count": len(parent_ids),
        "scoring_parent_count": len(scoring_parent_ids),
        "unit_count": len(units),
        "unresolved_count": 0,
    }


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    print(json.dumps(verify(root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
