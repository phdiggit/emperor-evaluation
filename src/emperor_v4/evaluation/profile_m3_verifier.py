from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from emperor_v4.evaluation.profile_m3_settlement import (
    GRADE_PROJECTION,
    M3_CONTRACT,
    M3_MARKDOWN,
    M3_SETTLEMENT,
    POOL,
    ROOT,
)
from emperor_v4.evaluation.profile_markdown import render_profile_markdown


PROJECT = ROOT / "config/project.yml"
MANIFEST = ROOT / "docs/评分结算/皇帝人物画像/00-已结算轴正式入口.json"
FINANCE_ROOT = ROOT / "docs/评分结算/第二项治国净收益/财政民生"
C_PATHS = {
    "C1": FINANCE_ROOT / "01-C1正式结算.json",
    "C2": FINANCE_ROOT / "02-C2正式结算.json",
    "C3": FINANCE_ROOT / "03-C3正式结算.json",
    "C4": FINANCE_ROOT / "04-C4正式结算.json",
}
READER_MACHINE_TERMS = (
    "JSON",
    "机器",
    "审计",
    "SOURCE_GAP",
    "source_ref",
    "material_id",
    "正式归责链",
)
SCALE_SCHEMA_VERSION = "m3-governance-scale-adjudication-v1"
SCALE_CLASS_TO_GATE = {
    "FULL_OR_MAJOR_ACTUAL_SCALE": "FULL_OR_MAJOR_REGIONAL",
    "LIMITED_ACTUAL_SCALE": "LIMITED_REGIONAL",
    "MATERIAL_SCOPE_LIMIT_ONLY": "UNRESOLVED_NOT_HIGH_GRADE_GATE",
    "UNRESOLVED": "UNRESOLVED_NOT_HIGH_GRADE_GATE",
}
SOURCE_ORIGINS = {
    "C4_FORMAL_PUBLIC_SOURCE",
    "C4_FORMAL_LINEAGE_EXPANDED_QUOTATION",
    "M3_SUPPLEMENT",
}


def _da_labels(value: Any) -> set[str]:
    """Return every DA label carried by a formal record or reader rationale."""
    if isinstance(value, str):
        return set(re.findall(r"DA[0-4]", value))
    if isinstance(value, dict):
        return set().union(*(_da_labels(item) for item in value.values())) if value else set()
    if isinstance(value, list):
        return set().union(*(_da_labels(item) for item in value)) if value else set()
    return set()


def _c4_public_source(ref: Any) -> tuple[str, str] | None:
    text = str(ref or "").strip()
    if "：" not in text or "《" not in text or "》" not in text:
        return None
    title, quote = text.split("：", 1)
    title = title.strip()
    quote = " ".join(quote.split())
    if not quote:
        return None
    if not title.startswith("《"):
        author, book = title.split("《", 1)
        title = f"《{book}（{author.strip()}）"
    return title, quote


def _load(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"UTF-8 BOM forbidden: {path}")
    return json.loads(raw.decode("utf-8"))


def _band(value: Any) -> int:
    match = re.search(r"(\d+)$", str(value))
    if not match:
        raise ValueError(f"cannot parse upstream band: {value!r}")
    return int(match.group(1))


def _expected_trajectory(upstream: dict[str, dict[str, Any]], ruler_id: str) -> dict[str, Any]:
    anchors: list[tuple[int, int, int]] = []
    peaks: list[int] = []
    for axis in ("C1", "C2", "C3"):
        source = upstream[axis][ruler_id]
        state = source["state_anchors"]
        main_key = "S_main" if axis == "C3" else "S_avg"
        start = _band(state["S0"])
        main = _band(state[main_key])
        end = _band(state["S_end"])
        explicit = [
            _band(source[key])
            for key in ("peak_band", "formal_peak_band", "raw_peak_band")
            if source.get(key) is not None
        ]
        anchors.append((start, main, end))
        peaks.append(max(main, end, *explicit))
    start = [item[0] for item in anchors]
    main = [item[1] for item in anchors]
    end = [item[2] for item in anchors]
    peak_improvement = [max(high - initial, 0) for high, initial in zip(peaks, start)]
    retained_change = [final - initial for final, initial in zip(end, start)]
    rollback = [max(high - final, 0) for high, final in zip(peaks, end)]
    return {
        "start_vector": start,
        "main_vector": main,
        "peak_vector": peaks,
        "end_vector": end,
        "peak_improvement_vector": peak_improvement,
        "retained_change_vector": retained_change,
        "rollback_vector": rollback,
        "improved_axis_count": sum(value > 0 for value in peak_improvement),
        "deep_improvement_axis_count": sum(value >= 2 for value in peak_improvement),
        "retained_improvement_axis_count": sum(value > 0 for value in retained_change),
        "rollback_axis_count": sum(value > 0 for value in rollback),
        "start_tier": sorted(start)[1],
        "peak_tier": sorted(peaks)[1],
        "end_tier": sorted(end)[1],
    }


def verify_payload(settlement: dict[str, Any]) -> dict[str, Any]:
    included = {
        row["ruler_id"]
        for row in _load(POOL)["records"]
        if row["pool_status"] == "INCLUDED"
    }
    records = settlement["records"]
    if settlement["schema_version"] != "profile-m3-livelihood-finance-formal-settlement-v3":
        raise ValueError("M3 schema mismatch")
    if settlement.get("contract_version") != "FORMAL-V3.4":
        raise ValueError("M3 contract version mismatch")
    contract_text = M3_CONTRACT.read_text(encoding="utf-8")
    required_contract_clauses = (
        "同档结构建设的待建边界",
        "C2绝对状态保留四档",
        "实现表现下限的待建硬门",
        "本人自造部分",
        "M3不重新定义DA0—DA4",
    )
    if any(clause not in contract_text for clause in required_contract_clauses):
        raise ValueError("M3 checklist contract clause missing")
    if settlement["canonical_status"] != "FORMAL_CURRENT":
        raise ValueError("M3 is not formal current")
    if settlement.get("authority_mode") != "FORMAL_SETTLEMENT_PATCH_SOURCE":
        raise ValueError("M3 formal settlement is not the declared patch authority")
    if any(key in settlement for key in ("adjudication_source", "supplement_adjudication_source")):
        raise ValueError("M3 still declares a generated adjudication authority")
    if settlement["record_count"] != len(records) or len(records) != 184:
        raise ValueError("M3 record count mismatch")
    ids = [row["ruler_id"] for row in records]
    if len(set(ids)) != len(ids) or set(ids) != included:
        raise ValueError("M3 canonical pool coverage mismatch")
    if records != sorted(records, key=lambda row: (-row["radar_value"], row["ruler_id"])):
        raise ValueError("M3 stable order mismatch")

    expected_task_codes = {f"PROFILE-M3-{ruler_id}" for ruler_id in included}
    if {row["task_code"] for row in records} != expected_task_codes:
        raise ValueError("M3 task code coverage mismatch")
    upstream_payloads = {axis: _load(path) for axis, path in C_PATHS.items()}
    upstream = {
        axis: {row["ruler_id"]: row for row in payload["scores"]}
        for axis, payload in upstream_payloads.items()
    }
    scale_contract = upstream_payloads["C4"].get("m3_governance_scale_adjudication_contract") or {}
    if scale_contract.get("schema_version") != SCALE_SCHEMA_VERSION:
        raise ValueError("C4 unified M3 scale adjudication contract missing")
    if scale_contract.get("record_count") != len(upstream_payloads["C4"]["scores"]):
        raise ValueError("C4 unified M3 scale adjudication coverage mismatch")
    upstream_scale_counts = Counter(
        row.get("m3_governance_scale_adjudication", {}).get("classification")
        for row in upstream_payloads["C4"]["scores"]
    )
    if scale_contract.get("classification_distribution") != dict(upstream_scale_counts):
        raise ValueError("C4 unified M3 scale adjudication distribution mismatch")
    for c4_row in upstream_payloads["C4"]["scores"]:
        k_basis = c4_row.get("stability_k_basis") or {}
        if set(k_basis) != {"C1", "C2", "C3"}:
            raise ValueError(f"C4 structured K coverage missing: {c4_row['ruler_id']}")
        if any(
            item.get("K_grade") not in {"K0", "K1", "K2", "K3", "K4"}
            or not isinstance(item.get("factor"), (int, float))
            for item in k_basis.values()
        ):
            raise ValueError(f"C4 structured K is invalid: {c4_row['ruler_id']}")
        expected_positive = min(
            float(c4_row["recovery_score"]) + float(c4_row["stability_score"]),
            float(c4_row["terminal_cap"]),
        )
        if abs(float(c4_row["positive_score_retained"]) - expected_positive) > 0.11:
            raise ValueError(f"C4 positive-score identity failed: {c4_row['ruler_id']}")
    scale_distribution: Counter[str] = Counter()
    reader_source_count_distribution: Counter[str] = Counter()
    c4_reader_modes: Counter[str] = Counter()
    k_structure_distribution: Counter[str] = Counter()
    for row in records:
        key = (row["axis_grade"], row["position"])
        if key not in GRADE_PROJECTION:
            raise ValueError(f"illegal M3 grade: {row['ruler_id']}")
        expected = GRADE_PROJECTION[key]
        if row["score_100"] != expected or row["radar_value"] != expected:
            raise ValueError(f"M3 score projection mismatch: {row['ruler_id']}")
        if row["formal_status"] != "FORMAL_CURRENT":
            raise ValueError(f"non-formal M3 record: {row['ruler_id']}")
        if row["axis_evidence_level"] not in {"E1", "E2", "E3"}:
            raise ValueError(f"illegal M3 evidence level: {row['ruler_id']}")
        if row["output_mode"] not in {"EPISODE_TAG", "BOUNDED_PROFILE", "FULL_GRADE"}:
            raise ValueError(f"illegal M3 output mode: {row['ruler_id']}")
        if not row["limitations"] or not row["public_adjudication"].strip():
            raise ValueError(f"incomplete M3 adjudication: {row['ruler_id']}")
        if not isinstance(row["parents"], list) or not isinstance(row["source_refs"], list):
            raise ValueError(f"invalid M3 lineage shape: {row['ruler_id']}")
        reader_sources = row.get("source_evidence") or []
        if not reader_sources:
            raise ValueError(f"invalid M3 reader source count: {row['ruler_id']}")
        reader_source_count_distribution[str(len(reader_sources))] += 1
        reader_source_keys: set[tuple[str, str]] = set()
        c4_public_source_keys: set[tuple[str, str]] = set()
        c4_lineage_expanded_count = 0
        for source in reader_sources:
            title = str(source.get("source_title") or "")
            quote = " ".join(str(source.get("quote") or "").split())
            if not title.startswith("《") or "》" not in title or not quote.strip():
                raise ValueError(f"invalid M3 reader source: {row['ruler_id']}")
            if re.search(r"(?:https?://|docs/|\\|material_id|source_ref)", title + quote, re.I):
                raise ValueError(f"non-reader M3 source locator: {row['ruler_id']}")
            origin = source.get("source_origin")
            if origin not in SOURCE_ORIGINS:
                raise ValueError(f"missing M3 reader source origin: {row['ruler_id']}")
            source_key = (title, quote)
            if source_key in reader_source_keys:
                raise ValueError(f"duplicated M3 reader source: {row['ruler_id']}")
            reader_source_keys.add(source_key)
            if origin == "C4_FORMAL_PUBLIC_SOURCE":
                c4_public_source_keys.add(source_key)
            elif origin == "C4_FORMAL_LINEAGE_EXPANDED_QUOTATION":
                c4_lineage_expanded_count += 1
        c4_row = upstream["C4"][row["ruler_id"]]
        expected_c4_public_sources = {
            parsed
            for ref in c4_row.get("public_source_refs") or []
            if (parsed := _c4_public_source(ref)) is not None
        }
        if expected_c4_public_sources:
            if c4_public_source_keys != expected_c4_public_sources:
                raise ValueError(f"M3 reader omits C4 public source: {row['ruler_id']}")
            c4_reader_modes["C4_FORMAL_PUBLIC_SOURCE"] += 1
        elif c4_lineage_expanded_count < 1:
            raise ValueError(f"M3 reader does not expand C4 legacy lineage: {row['ruler_id']}")
        else:
            c4_reader_modes["C4_FORMAL_LINEAGE_EXPANDED_QUOTATION"] += 1
        costs = row["costs_and_consequences"].strip()
        behavior = row["behavior_chain"].strip()
        if not costs or not behavior or costs in behavior or behavior in costs:
            raise ValueError(f"duplicated M3 reader rationale: {row['ruler_id']}")
        if len(costs) > 240 or len(behavior) > 360:
            raise ValueError(f"overlong M3 reader rationale: {row['ruler_id']}")
        if any(term.lower() in (costs + behavior).lower() for term in READER_MACHINE_TERMS):
            raise ValueError(f"machine term in M3 reader rationale: {row['ruler_id']}")
        if "adjudication_ref" in row:
            raise ValueError(f"M3 record still delegates authority: {row['ruler_id']}")
        for axis in C_PATHS:
            source = upstream[axis][row["ruler_id"]]
            expected_component = {"band": source["main_band"], "score": source["score"]}
            if row["components"][axis] != expected_component:
                raise ValueError(f"M3 upstream component drift: {row['ruler_id']} {axis}")
        evidence = row.get("ability_evidence") or {}
        sync = evidence.get("upstream_sync") or {}
        if sync.get("status") != "SYNCED_TO_FORMAL_C1_C4_2026_09_01":
            raise ValueError(f"M3 upstream sync status missing: {row['ruler_id']}")
        gate = evidence.get("governance_scale_gate") or {}
        scale_status = gate.get("status")
        if scale_status not in {
            "LIMITED_REGIONAL",
            "FULL_OR_MAJOR_REGIONAL",
            "UNRESOLVED_NOT_HIGH_GRADE_GATE",
        }:
            raise ValueError(f"M3 scale gate status invalid: {row['ruler_id']}")
        if evidence.get("governance_scale_class") != scale_status:
            raise ValueError(f"M3 scale gate class mismatch: {row['ruler_id']}")
        upstream_scale = upstream["C4"][row["ruler_id"]].get("m3_governance_scale_adjudication") or {}
        classification = upstream_scale.get("classification")
        if upstream_scale.get("schema_version") != SCALE_SCHEMA_VERSION or classification not in SCALE_CLASS_TO_GATE:
            raise ValueError(f"missing unified C4 scale adjudication: {row['ruler_id']}")
        if upstream_scale.get("name_or_polity_inference_used") is not False:
            raise ValueError(f"name/polity scale inference used: {row['ruler_id']}")
        if gate.get("classification") != classification or gate.get("dimension") != upstream_scale.get("dimension"):
            raise ValueError(f"M3/C4 scale classification drift: {row['ruler_id']}")
        if scale_status != SCALE_CLASS_TO_GATE[classification] or gate.get("basis") != upstream_scale.get("basis"):
            raise ValueError(f"M3/C4 scale gate drift: {row['ruler_id']}")
        if classification == "LIMITED_ACTUAL_SCALE" and upstream_scale.get("dimension") not in {
            "ACTUAL_GOVERNANCE_SCALE",
            "FRAGMENTED_ACTUAL_CONTROL",
        }:
            raise ValueError(f"limited scale uses invalid dimension: {row['ruler_id']}")
        if classification == "MATERIAL_SCOPE_LIMIT_ONLY" and scale_status == "LIMITED_REGIONAL":
            raise ValueError(f"material scope was converted to limited scale: {row['ruler_id']}")
        sources = gate.get("formal_subitem_sources") or []
        if len(sources) != 1 or sources[0].get("axis") != "C4" or sources[0].get("field_path") != "m3_governance_scale_adjudication":
            raise ValueError(f"M3 scale gate does not read unified C4 field: {row['ruler_id']}")
        if row["axis_grade"] in {"G4", "G5"} and scale_status == "UNRESOLVED_NOT_HIGH_GRADE_GATE":
            raise ValueError(f"M3 high grade has unresolved scale gate: {row['ruler_id']}")
        if scale_status == "LIMITED_REGIONAL" and not evidence.get("six_band_main_state"):
            if row["axis_grade"] == "G5" or (row["axis_grade"] == "G4" and row["position"] != "LOW"):
                raise ValueError(f"M3 limited-scale cap broken: {row['ruler_id']}")
        scale_distribution[scale_status] += 1

        trajectory = evidence.get("trajectory") or {}
        expected_trajectory = _expected_trajectory(upstream, row["ruler_id"])
        for field, expected_value in expected_trajectory.items():
            if trajectory.get(field) != expected_value:
                raise ValueError(f"M3 upstream trajectory drift: {row['ruler_id']} {field}")
        c4 = upstream["C4"][row["ruler_id"]]
        c4_numeric = {
            "recovery_score_27": c4["recovery_score"],
            "stability_score_18": c4["stability_score"],
        }
        for field, expected_value in c4_numeric.items():
            if float(trajectory.get(field)) != float(expected_value):
                raise ValueError(f"M3 upstream C4 numeric drift: {row['ruler_id']} {field}")
        if float(evidence.get("deterioration_penalty")) != float(c4["deterioration_penalty"]):
            raise ValueError(f"M3 upstream deterioration drift: {row['ruler_id']}")
        if evidence.get("destructive_amplification_grade") != c4["destructive_amplification_grade"]:
            raise ValueError(f"M3 upstream DA grade drift: {row['ruler_id']}")
        if float(evidence.get("destructive_amplification_penalty")) != float(c4["destructive_amplification_penalty"]):
            raise ValueError(f"M3 upstream DA penalty drift: {row['ruler_id']}")
        expected_da = c4["destructive_amplification_grade"]
        if _da_labels(c4) - {expected_da}:
            raise ValueError(f"C4 stale DA reader label: {row['ruler_id']}")
        if _da_labels(row) - {expected_da}:
            raise ValueError(f"M3 stale DA reader label: {row['ruler_id']}")
        expected_k_basis = c4.get("stability_k_basis") or {}
        if evidence.get("stability_k_basis") != expected_k_basis:
            raise ValueError(f"M3 upstream K basis drift: {row['ruler_id']}")
        if evidence.get("weighted_K") != c4.get("weighted_K"):
            raise ValueError(f"M3 upstream weighted K drift: {row['ruler_id']}")
        expected_k_status = "STRUCTURED_C4_FORMAL" if expected_k_basis else "C4_FORMAL_PROSE_ONLY"
        if evidence.get("stability_k_structure_status") != expected_k_status:
            raise ValueError(f"M3 K structure status drift: {row['ruler_id']}")
        if evidence.get("stability_k_public_basis") != c4.get("recovery_and_absorption", ""):
            raise ValueError(f"M3 K public basis drift: {row['ruler_id']}")
        k_structure_distribution[expected_k_status] += 1
        start = trajectory["start_vector"]
        main = trajectory["main_vector"]
        peak = trajectory["peak_vector"]
        end = trajectory["end_vector"]
        if any(highest < max(main_state, end_state) for highest, main_state, end_state in zip(peak, main, end)):
            raise ValueError(f"M3 highest-achieved vector invariant failed: {row['ruler_id']}")
        if row["axis_grade"] == "G4":
            recovery = float(trajectory["recovery_score_27"])
            stability = float(trajectory["stability_score_18"])
            retained = int(trajectory["retained_improvement_axis_count"])
            improved = int(trajectory["improved_axis_count"])
            end_tier = int(trajectory["end_tier"])
            strong_build = recovery >= 15 and improved >= 2 and retained >= 2 and end_tier >= 3 and stability >= 6
            complete_a4 = min(end) >= 4 and recovery >= 10 and stability >= 8 and retained >= 2
            high_stewardship = evidence.get("route") == "HIGH_LEVEL_STEWARDSHIP"
            a5_floor = end_tier >= 5 and float(evidence["deterioration_penalty"]) < 8 and float(evidence["destructive_amplification_penalty"]) < 18
            if not (strong_build or complete_a4 or high_stewardship or a5_floor):
                raise ValueError(f"M3 G4 admission gate failed: {row['ruler_id']}")

    distribution = Counter(row["axis_grade"] for row in records)
    declared = settlement["summary"]["grade_distribution"]
    expected_distribution = {
        grade: distribution.get(grade, 0) for grade in ("G0", "G1", "G2", "G3", "G4", "G5")
    }
    if declared != expected_distribution:
        raise ValueError("M3 grade distribution mismatch")
    reader_contract = settlement.get("reader_source_contract") or {}
    if reader_contract.get("record_count") != len(records):
        raise ValueError("M3 reader source contract coverage mismatch")
    if reader_contract.get("c4_direct_public_source_records") != c4_reader_modes["C4_FORMAL_PUBLIC_SOURCE"]:
        raise ValueError("M3 C4 direct reader-source count mismatch")
    if reader_contract.get("c4_legacy_lineage_expanded_records") != c4_reader_modes["C4_FORMAL_LINEAGE_EXPANDED_QUOTATION"]:
        raise ValueError("M3 C4 legacy reader-source count mismatch")
    if reader_contract.get("source_count_distribution") != dict(reader_source_count_distribution):
        raise ValueError("M3 reader source-count distribution mismatch")
    yinzhen = next(row for row in records if row["ruler_name"] == "胤禛")
    yinzhen_review = yinzhen["ability_evidence"].get("same_band_structural_build_review") or {}
    if yinzhen["components"]["C2"]["band"] != "C2-4":
        raise ValueError("M3 Yinzhen C2 disposition drift")
    if (yinzhen["axis_grade"], yinzhen["position"]) != ("G3", "MID"):
        raise ValueError("M3 Yinzhen pending adjudication drift")
    if yinzhen_review.get("status") != "PENDING_RULE_NOT_SCORE_ACTIVE":
        raise ValueError("M3 Yinzhen same-band review status missing")
    if yinzhen_review.get("m3_disposition") != "G3-MID_RETAINED_PENDING_RULE":
        raise ValueError("M3 Yinzhen same-band disposition drift")
    upstream_summary = settlement["summary"].get("upstream_sync") or {}
    if upstream_summary.get("k_structure_distribution") != dict(k_structure_distribution):
        raise ValueError("M3 K structure distribution mismatch")
    return {
        "status": "PASS",
        "record_count": len(records),
        "grade_distribution": expected_distribution,
        "evidence_limited_count": sum(
            row["score_status"] == "EVIDENCE_LIMITED" for row in records
        ),
        "scale_gate_distribution": dict(scale_distribution),
        "k_structure_distribution": dict(k_structure_distribution),
    }


def verify() -> dict[str, Any]:
    settlement = _load(M3_SETTLEMENT)
    result = verify_payload(settlement)
    markdown = M3_MARKDOWN.read_text(encoding="utf-8")
    if markdown != render_profile_markdown(settlement):
        raise ValueError("M3 Markdown differs from formal JSON")
    adjudications = markdown.split("## 逐人裁决依据", 1)[1]
    if any(term.lower() in adjudications.lower() for term in READER_MACHINE_TERMS):
        raise ValueError("machine audit term remains in M3 reader adjudications")
    source_lines = [line for line in adjudications.splitlines() if line.startswith("  - 《")]
    expected_sources = sum(len(row["source_evidence"]) for row in settlement["records"])
    if len(source_lines) != expected_sources:
        raise ValueError("M3 reader source lines are not one quote per line")

    project = yaml.safe_load(PROJECT.read_text(encoding="utf-8"))["profile_assessment"]
    entry = project["settled_axes"]["M3"]
    if ROOT / entry["json"] != M3_SETTLEMENT or ROOT / entry["markdown"] != M3_MARKDOWN:
        raise ValueError("M3 project entry mismatch")

    manifest = _load(MANIFEST)
    axis = next(row for row in manifest["axes"] if row["axis_code"] == "M3")
    return result


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
