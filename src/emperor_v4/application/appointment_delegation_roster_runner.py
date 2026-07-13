from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from emperor_v4.adapters import (
    adapt_claim_extractor_snapshot,
    adapt_source_cache_snapshot,
)
from emperor_v4.application.appointment_delegation_shadow_runner import (
    run_appointment_delegation_shadow_manifest,
)
from emperor_v4.application.reconcile_episode import reconcile_episode_candidates
from emperor_v4.evaluation.appointment_delegation_scoring import canonical_hash


ROSTER_RUN_POLICY_VERSION = "appointment-delegation-roster-offline-v1"


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(repo_root: Path, configured: object) -> Path:
    path = (repo_root / str(configured)).resolve()
    try:
        path.relative_to(repo_root)
    except ValueError as exc:
        raise ValueError("roster runner 输入路径越出仓库") from exc
    if not path.is_file():
        raise ValueError(f"roster runner 输入不存在: {configured}")
    return path


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    if (
        manifest.get("schema_version") != 1
        or manifest.get("status") != "frozen_roster_shadow_input"
        or manifest.get("rule_code") != "appointment_delegation"
        or manifest.get("policy_version") != ROSTER_RUN_POLICY_VERSION
        or manifest.get("cache_mode") not in {"ensure", "supplement", "refresh"}
    ):
        raise ValueError("roster manifest 身份、规则、策略或 cache_mode 非法")
    runtime = manifest.get("runtime_policy") or {}
    if (
        runtime.get("offline") is not True
        or runtime.get("service_calls_allowed") is not False
        or runtime.get("model_calls_allowed") is not False
        or runtime.get("database_writes_allowed") is not False
        or runtime.get("formal_acceptance_allowed") is not False
    ):
        raise ValueError("roster runner 只允许离线缓存、零模型、零写入 shadow")
    if manifest.get("cache_mode") != "ensure":
        raise ValueError("离线 roster demo 只执行 cache_mode=ensure")
    roster = tuple(manifest.get("roster") or ())
    pairs = [
        (str(row.get("ruler") or ""), str(person))
        for row in roster
        for person in row.get("people") or ()
    ]
    if not pairs or any(not all(pair) for pair in pairs) or len(pairs) != len(set(pairs)):
        raise ValueError("roster 人物身份缺失或重复")


def run_appointment_delegation_roster_shadow(
    manifest_path: Path | str,
    *,
    prior_record_path: Path | str | None = None,
) -> dict[str, Any]:
    path = Path(manifest_path)
    manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
    _validate_manifest(manifest)
    repo_root = path.resolve().parents[2]
    inputs = manifest.get("service_inputs") or {}
    source_paths = [
        _resolve(repo_root, item) for item in inputs.get("source_cache_snapshots") or ()
    ]
    claim_paths = [
        _resolve(repo_root, item) for item in inputs.get("claim_extractor_snapshots") or ()
    ]
    scored_manifest_path = _resolve(repo_root, inputs.get("scored_manifest"))
    if not source_paths or not claim_paths:
        raise ValueError("roster runner 缺少 Source Cache 或 Claim Extractor snapshot")
    file_hashes = {
        str(item.relative_to(repo_root)).replace("\\", "/"): _file_hash(item)
        for item in [*source_paths, *claim_paths, scored_manifest_path]
    }
    input_fingerprint = canonical_hash(
        {
            "manifest": manifest,
            "file_hashes": file_hashes,
            "policy_version": ROSTER_RUN_POLICY_VERSION,
        }
    )

    prior_record = None
    if prior_record_path is not None:
        prior_path = Path(prior_record_path)
        prior_record = json.loads(prior_path.read_text(encoding="utf-8"))
        if prior_record.get("input_fingerprint") == input_fingerprint:
            unsigned = dict(prior_record)
            stored_hash = unsigned.pop("run_record_sha256", None)
            if stored_hash != canonical_hash(unsigned):
                raise ValueError("prior roster run record hash 非法")
            return prior_record

    source_snapshots = [json.loads(item.read_text(encoding="utf-8")) for item in source_paths]
    claim_snapshots = [json.loads(item.read_text(encoding="utf-8")) for item in claim_paths]
    adapted_sources = [adapt_source_cache_snapshot(item) for item in source_snapshots]
    adapted_assertions = tuple(
        assertion
        for snapshot in claim_snapshots
        for assertion in adapt_claim_extractor_snapshot(snapshot)
    )
    assertion_codes = [item.assertion_code for item in adapted_assertions]
    if len(assertion_codes) != len(set(assertion_codes)):
        raise ValueError("roster runner 合并后的 Assertion identity 重复")
    episode_packets = reconcile_episode_candidates(adapted_assertions)

    roster_pairs = {
        (str(row["ruler"]), str(person))
        for row in manifest["roster"]
        for person in row["people"]
    }
    source_pairs = {
        (str(person.get("ruler") or ""), str(item.get("object_name") or ""))
        for snapshot in source_snapshots
        for person in snapshot.get("people") or ()
        for item in (person.get("payload") or {}).get("candidate_slices") or ()
    }
    assertion_pairs = {
        (
            str(assertion.qualifiers.get("evaluation_context") or ""),
            str(assertion.qualifiers.get("focal_person_ref") or ""),
        )
        for assertion in adapted_assertions
    }
    if not roster_pairs <= assertion_pairs:
        raise ValueError("roster 人物未被 Claim Extractor snapshots 完整覆盖")
    direct_source_pairs = roster_pairs & source_pairs
    supplemented_source_pairs = roster_pairs - source_pairs

    scored_manifest = yaml.safe_load(scored_manifest_path.read_text(encoding="utf-8"))
    scored_pairs = {
        (str(unit["ruler"]), str(unit["person"]))
        for unit in scored_manifest.get("rule_evidence_units") or ()
    }
    if scored_pairs != roster_pairs:
        raise ValueError("roster 与 scored manifest 评分人物集合不一致")
    scored_assertion_refs = {
        str(ref)
        for unit in scored_manifest["rule_evidence_units"]
        for observation in unit["factor_observations"].values()
        for ref in observation.get("assertion_refs") or ()
    }
    if not scored_assertion_refs <= set(assertion_codes):
        raise ValueError("scored manifest Assertion 未被 Claim Extractor snapshots 覆盖")

    units_by_pair: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for unit in scored_manifest["rule_evidence_units"]:
        units_by_pair.setdefault((str(unit["ruler"]), str(unit["person"])), []).append(unit)
    entry_hashes = {
        f"{ruler}/{person}": canonical_hash(
            {
                "ruler": ruler,
                "person": person,
                "assertions": sorted(
                    (
                        asdict(assertion)
                        for assertion in adapted_assertions
                        if (
                            assertion.qualifiers.get("evaluation_context"),
                            assertion.qualifiers.get("focal_person_ref"),
                        )
                        == (ruler, person)
                    ),
                    key=lambda row: row["assertion_code"],
                ),
                "score_units": units_by_pair[(ruler, person)],
            }
        )
        for ruler, person in sorted(roster_pairs)
    }
    prior_entry_hashes = (prior_record or {}).get("roster_entry_hashes") or {}
    changed_people = sorted(
        ref for ref, value in entry_hashes.items() if prior_entry_hashes.get(ref) != value
    )
    changed_pairs = {tuple(ref.split("/", 1)) for ref in changed_people}
    rebuild_unit_refs = {
        str(unit["unit_ref"])
        for unit in scored_manifest["rule_evidence_units"]
        if (str(unit["ruler"]), str(unit["person"])) in changed_pairs
    }
    prior_scored_report = (prior_record or {}).get("scored_report")
    if prior_record is None:
        rebuild_unit_refs = {
            str(unit["unit_ref"]) for unit in scored_manifest["rule_evidence_units"]
        }
    scored_report = run_appointment_delegation_shadow_manifest(
        scored_manifest,
        scored_manifest_path,
        prior_report=prior_scored_report,
        rebuild_unit_refs=rebuild_unit_refs,
    )
    unit_refs = {
        str(unit["unit_ref"]) for unit in scored_manifest["rule_evidence_units"]
    }
    report: dict[str, Any] = {
        "schema_version": 1,
        "status": "appointment_delegation_roster_shadow_complete",
        "run_code": manifest["run_code"],
        "policy_version": ROSTER_RUN_POLICY_VERSION,
        "input_fingerprint": input_fingerprint,
        "cache_mode": manifest["cache_mode"],
        "roster_entry_hashes": entry_hashes,
        "delta": {
            "changed_person_refs": changed_people,
            "rebuilt_rule_evidence_unit_refs": sorted(rebuild_unit_refs),
            "reused_rule_evidence_unit_refs": sorted(unit_refs - rebuild_unit_refs),
        },
        "stages": {
            "source_cache_adapter": {
                "status": "cache_hit",
                "snapshot_count": len(source_paths),
                "document_count": sum(len(item.documents) for item in adapted_sources),
                "passage_count": sum(len(item.passages) for item in adapted_sources),
                "direct_roster_coverage_count": len(direct_source_pairs),
                "supplemented_via_claim_snapshot_count": len(
                    supplemented_source_pairs
                ),
                "supplemented_person_refs": sorted(
                    f"{ruler}/{person}" for ruler, person in supplemented_source_pairs
                ),
            },
            "claim_extractor_adapter": {
                "status": "cache_hit",
                "snapshot_count": len(claim_paths),
                "assertion_count": len(adapted_assertions),
            },
            "episode_kernel": {
                "status": "completed_offline",
                "candidate_packet_count": len(episode_packets),
            },
            "scored_shadow": {
                "status": scored_report["status"],
                "rebuilt_count": len(rebuild_unit_refs),
                "reused_count": len(unit_refs - rebuild_unit_refs),
            },
        },
        "file_hashes": file_hashes,
        "scored_report": scored_report,
        "resume": {
            "prior_record_supplied": prior_record is not None,
            "resumed_after_input_change": prior_record is not None,
            "exact_record_reuse_supported": True,
            "failed_stage_resume_supported": False,
        },
        "side_effect_audit": {
            "offline": True,
            "service_call_count": 0,
            "model_call_count": 0,
            "database_write_count": 0,
            "formal_acceptance_performed": False,
        },
    }
    report["run_record_sha256"] = canonical_hash(report)
    return report
