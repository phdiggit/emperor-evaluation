from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_claim_cache as tool


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sample_claim(summary: str = "朱元璋命汤和镇守常州。") -> dict:
    return {
        "claim_code": "CLM-001",
        "emperor_name": "朱元璋",
        "object_name": "汤和",
        "object_type": "person",
        "claim_kind": "material_claim",
        "claim_summary": summary,
        "confidence": 0.9,
        "source_slice_refs": ["SLI-001"],
        "fact_payload": {
            "fact_schema": "political_action_v1",
            "actor": "朱元璋",
            "object": "汤和",
            "action_type": "授权",
            "event_scope": "军事",
            "office_or_domain": "常州镇守",
            "outcome": "守常州",
            "time_context": "洪武初",
            "source_span_refs": ["SLI-001"],
            "confidence": 0.9,
            "completeness": {
                "has_actor": True,
                "has_object": True,
                "has_action": True,
                "has_outcome": True,
                "same_event_chain": True,
                "needs_source_extension": False,
            },
        },
        "evidence_spans": [
            {"span_type": "action", "source_slice_ref": "SLI-001", "text": "命汤和守常州"},
            {"span_type": "outcome", "source_slice_ref": "SLI-001", "text": "常州安辑"},
        ],
    }


def sample_candidates() -> dict:
    return {
        "task_identity": {"emperor_name": "朱元璋", "rule_code": "i5b_item_wide"},
        "candidate_slices": [
            {
                "slice_code": "SLI-001",
                "document_code": "DOC-001",
                "object_name": "汤和",
                "text": "帝命汤和守常州，常州安辑。",
            },
            {
                "slice_code": "SLI-002",
                "document_code": "DOC-001",
                "object_name": "常遇春",
                "text": "帝命常遇春进兵。",
            },
        ],
    }


def test_cleanup_runs_is_dry_run_then_removes_cascaded_rows(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    paths = tool.cache_paths(cache_root)
    tool.write_jsonl(paths["claims"], [
        {"claim_key": "CLMK-DROP", "last_run_code": "RUN-DROP"},
        {"claim_key": "CLMK-KEEP", "last_run_code": "RUN-KEEP"},
    ])
    tool.write_jsonl(paths["evidence"], [
        {"evidence_key": "EVD-DROP", "claim_key": "CLMK-DROP", "slice_hash": "SLH-DROP"},
        {"evidence_key": "EVD-KEEP", "claim_key": "CLMK-KEEP", "slice_hash": "SLH-KEEP"},
    ])
    tool.write_jsonl(paths["slices"], [
        {"slice_hash": "SLH-DROP", "first_run_code": "RUN-DROP"},
        {"slice_hash": "SLH-KEEP", "first_run_code": "RUN-KEEP"},
    ])
    tool.write_jsonl(paths["runs"], [{"run_code": "RUN-DROP"}, {"run_code": "RUN-KEEP"}])

    dry_run = tool.cleanup_runs(cache_root, ["RUN-DROP"])
    assert dry_run["planned"] == {"claims": 1, "evidence": 1, "slices": 1, "runs": 1}
    assert len(tool.read_jsonl(paths["claims"])) == 2

    executed = tool.cleanup_runs(cache_root, ["RUN-DROP"], execute=True)
    assert executed["executed"] is True
    assert [row["claim_key"] for row in tool.read_jsonl(paths["claims"])] == ["CLMK-KEEP"]
    assert [row["slice_hash"] for row in tool.read_jsonl(paths["slices"])] == ["SLH-KEEP"]


def write_run(
    tmp_path: Path,
    *,
    claim: dict | None = None,
    candidates: dict | None = None,
    clean_policy: dict | None = None,
) -> Path:
    run_root = tmp_path / "run"
    person_dir = run_root / "TGT-I5B-ZYZ"
    candidates_path = person_dir / "candidates.final.json"
    judge_path = person_dir / "judge_result.final.json"
    write_json(candidates_path, candidates or sample_candidates())
    write_json(
        judge_path,
        {
            "status": "succeeded",
            "claims": [claim or sample_claim()],
            "primary_bindings": [],
            "secondary_binding_candidates": [],
        },
    )
    write_json(
        run_root / "summary.json",
        {
            "elapsed_seconds": 1.0,
            "targets": ["朱元璋"],
            "clean_policy": clean_policy or {"judge_mode": "claim_extraction_only"},
            "people": [
                {
                    "name": "朱元璋",
                    "files": {
                        "final_candidates": str(candidates_path),
                        "final_judge_result": str(judge_path),
                    },
                }
            ],
        },
    )
    return run_root


def test_claim_key_is_stable_for_same_fact_payload() -> None:
    first = tool.claim_key(sample_claim())
    second = tool.claim_key({**sample_claim("白话摘要不同。"), "claim_code": "CLM-OTHER"})

    assert first != second
    assert first == tool.claim_key(sample_claim())


def test_import_run_dedupes_claims_slices_and_evidence(tmp_path: Path) -> None:
    run_root = write_run(tmp_path)
    cache_root = tmp_path / "claim_cache"

    first = tool.import_run(run_root, cache_root)
    second = tool.import_run(run_root, cache_root)

    assert first["stats"]["new_claim_count"] == 1
    assert first["stats"]["new_slice_count"] == 1
    assert first["stats"]["new_evidence_count"] == 2
    assert second["stats"]["duplicate_claim_count"] == 1
    assert second["total_cached_claims"] == 1
    claims = tool.read_jsonl(cache_root / "claims.jsonl")
    assert len(claims) == 1
    assert claims[0]["canonical_event_key"].startswith("CEK-")
    assert claims[0]["claim_grain"] == "event_chain"
    assert claims[0]["near_duplicate_group_payload"]["object_name"] == "汤和"
    assert claims[0]["source_slice_refs"] == ["SLI-001"]
    assert len(tool.read_jsonl(cache_root / "source_slices.jsonl")) == 1


def test_import_run_drops_cross_object_source_refs(tmp_path: Path) -> None:
    claim = sample_claim()
    claim["source_slice_refs"] = ["SLI-001", "SLI-002"]
    claim["fact_payload"]["source_span_refs"] = ["SLI-001", "SLI-002"]
    claim["evidence_spans"].append({"span_type": "action", "source_slice_ref": "SLI-002", "text": "命常遇春进兵"})
    run_root = write_run(tmp_path, claim=claim)
    cache_root = tmp_path / "claim_cache"

    report = tool.import_run(run_root, cache_root)

    claims = tool.read_jsonl(cache_root / "claims.jsonl")
    evidence = tool.read_jsonl(cache_root / "claim_evidence.jsonl")
    assert report["stats"]["cross_object_source_ref_dropped"] == 1
    assert report["stats"]["new_claim_count"] == 1
    assert claims[0]["object_name"] == "汤和"
    assert claims[0]["source_slice_refs"] == ["SLI-001"]
    assert claims[0]["fact_payload"]["source_span_refs"] == ["SLI-001"]
    assert {row["source_slice_ref"] for row in evidence} == {"SLI-001"}
    assert {row["object_name"] for row in evidence} == {"汤和"}


def test_import_run_skips_claim_with_only_cross_object_refs(tmp_path: Path) -> None:
    claim = sample_claim()
    claim["source_slice_refs"] = ["SLI-002"]
    claim["fact_payload"]["source_span_refs"] = ["SLI-002"]
    claim["evidence_spans"] = [{"span_type": "action", "source_slice_ref": "SLI-002", "text": "命常遇春进兵"}]
    run_root = write_run(tmp_path, claim=claim)
    cache_root = tmp_path / "claim_cache"

    report = tool.import_run(run_root, cache_root)

    assert report["stats"]["cross_object_source_ref_dropped"] == 1
    assert report["stats"]["claims_skipped_cross_object_only"] == 1
    assert report["total_cached_claims"] == 0
    assert tool.read_jsonl(cache_root / "claim_evidence.jsonl") == []


def test_import_run_rebinds_claim_owner_from_resolved_actor_alias(tmp_path: Path) -> None:
    candidates = {
        "task_identity": {"emperor_name": "李世民", "rule_code": "i5b_item_wide"},
        "candidate_slices": [
            {
                "slice_code": "SLI-CSL",
                "document_code": "DOC-CSL",
                "object_name": "褚遂良",
                "text": "高宗欲废王皇后，褚遂良固谏，左授潭州都督。",
            }
        ],
    }
    claim = {
        "claim_code": "CLM-CSL",
        "emperor_name": "李世民",
        "object_name": "褚遂良",
        "object_type": "person",
        "claim_kind": "material_claim",
        "claim_summary": "高宗因褚遂良固谏废后而左授其潭州都督。",
        "confidence": 0.9,
        "source_slice_refs": ["SLI-CSL"],
        "fact_payload": {
            "fact_schema": "political_action_v1",
            "actor": "高宗",
            "object": "褚遂良",
            "action_type": "处置",
            "source_span_refs": ["SLI-CSL"],
        },
        "evidence_spans": [{"span_type": "action", "source_slice_ref": "SLI-CSL", "text": "左授潭州都督"}],
    }
    run_root = write_run(tmp_path, claim=claim, candidates=candidates)
    cache_root = tmp_path / "claim_cache"

    report = tool.import_run(run_root, cache_root)

    claims = tool.read_jsonl(cache_root / "claims.jsonl")
    assert report["stats"]["claims_rebound_by_alias_mentions"] == 1
    assert report["stats"]["claims_rebound_by_alias_mentions.claim_actor_matches_resolved_owner_alias"] == 1
    assert claims[0]["emperor_name"] == "李治"
    assert claims[0]["fact_payload"]["owner_rebind_payload"]["from_emperor_name"] == "李世民"
    assert claims[0]["fact_payload"]["owner_rebind_payload"]["to_emperor_name"] == "李治"
    evidence = claims[0]["fact_payload"]["owner_rebind_payload"]["evidence"][0]
    assert evidence["resolution_status"] == "resolved"
    assert evidence["owner_anchor_eligible"] is True
    assert evidence["mention_role"] == "owner_anchor"


def test_import_run_rebinds_owner_from_unique_other_context_when_target_is_context_only(tmp_path: Path) -> None:
    text = "隐太子忌惮房玄龄、杜如晦受李世民亲礼，向高祖谮毁二人，使房玄龄与杜如晦被驱斥。"
    candidates = {
        "task_identity": {"emperor_name": "李世民", "rule_code": "i5b_item_wide"},
        "candidate_slices": [
            {
                "slice_code": "SLI-FXL",
                "document_code": "DOC-FXL",
                "object_name": "房玄龄",
                "text": text,
            }
        ],
    }
    claim = {
        "claim_code": "CLM-FXL",
        "emperor_name": "李世民",
        "object_name": "房玄龄",
        "object_type": "person",
        "claim_kind": "material_claim",
        "claim_summary": text,
        "confidence": 0.9,
        "source_slice_refs": ["SLI-FXL"],
        "fact_payload": {
            "fact_schema": "political_action_v1",
            "actor": "隐太子",
            "object": "房玄龄",
            "action_type": "处置",
            "outcome": "被驱斥",
            "source_span_refs": ["SLI-FXL"],
        },
        "evidence_spans": [{"span_type": "action", "source_slice_ref": "SLI-FXL", "text": "向高祖谮毁"}],
    }
    run_root = write_run(tmp_path, claim=claim, candidates=candidates)
    cache_root = tmp_path / "claim_cache"

    report = tool.import_run(run_root, cache_root)

    claims = tool.read_jsonl(cache_root / "claims.jsonl")
    assert report["stats"]["claims_rebound_by_alias_mentions"] == 1
    assert report["stats"]["claims_rebound_by_alias_mentions.claim_context_unique_resolved_owner_with_requested_owner_context_only"] == 1
    assert claims[0]["emperor_name"] == "李渊"
    assert claims[0]["fact_payload"]["owner_rebind_payload"]["reason"] == "claim_context_unique_resolved_owner_with_requested_owner_context_only"


def test_import_run_rejects_when_source_owner_anchor_contradicts_requested_owner_alias(tmp_path: Path) -> None:
    source_text = (
        "高宗天皇大圣大弘孝皇帝中之上麟德二年，"
        "上语及隋炀帝，谓侍臣曰：朕常以为戒，虚心求谏；而竟无谏者，何也？"
        "李绩对曰：陛下所为尽善，群臣无得而谏。"
    )
    candidates = {
        "task_identity": {"emperor_name": "李世民", "rule_code": "i5b_item_wide"},
        "candidate_slices": [
            {
                "slice_code": "SLI-LINDE",
                "document_code": "DOC-ZZTJ-201",
                "object_name": "李绩",
                "text": source_text,
            }
        ],
    }
    claim = {
        "claim_code": "CLM-LINDE",
        "emperor_name": "李世民",
        "object_name": "李绩",
        "object_type": "person",
        "claim_kind": "material_claim",
        "claim_summary": "太宗问为何无人进谏时，李绩回答陛下所为尽善，群臣无得而谏。",
        "confidence": 0.8,
        "source_slice_refs": ["SLI-LINDE"],
        "fact_payload": {
            "fact_schema": "political_action_v1",
            "actor": "李绩",
            "object": "李世民求谏",
            "action_type": "拒谏",
            "time_context": "麟德二年二月",
            "source_span_refs": ["SLI-LINDE"],
        },
        "evidence_spans": [{"span_type": "action", "source_slice_ref": "SLI-LINDE", "text": "无得而谏"}],
    }
    run_root = write_run(tmp_path, claim=claim, candidates=candidates)
    cache_root = tmp_path / "claim_cache"

    report = tool.import_run(run_root, cache_root)

    claims = tool.read_jsonl(cache_root / "claims.jsonl")
    assert report["stats"]["claims_rejected_by_owner_alias_policy"] == 1
    assert (
        report["stats"][
            "claims_rejected_by_owner_alias_policy.source_unique_owner_anchor_rejects_unsupported_requested_owner_alias"
        ]
        == 1
    )
    assert claims == []


def test_import_run_rebinds_when_source_owner_anchor_is_omitted_from_claim(tmp_path: Path) -> None:
    source_text = (
        "高宗天皇大圣大弘孝皇帝中之上麟德二年，"
        "上语及隋炀帝，谓侍臣曰：朕常以为戒，虚心求谏；而竟无谏者，何也？"
        "李绩对曰：陛下所为尽善，群臣无得而谏。"
    )
    candidates = {
        "task_identity": {"emperor_name": "李世民", "rule_code": "i5b_item_wide"},
        "candidate_slices": [
            {
                "slice_code": "SLI-LINDE",
                "document_code": "DOC-ZZTJ-201",
                "object_name": "李绩",
                "text": source_text,
            }
        ],
    }
    claim = {
        "claim_code": "CLM-LINDE",
        "emperor_name": "李世民",
        "object_name": "李绩",
        "object_type": "person",
        "claim_kind": "material_claim",
        "claim_summary": "皇帝问为何无人进谏时，李绩回答陛下所为尽善，群臣无得而谏。",
        "confidence": 0.8,
        "source_slice_refs": ["SLI-LINDE"],
        "fact_payload": {
            "fact_schema": "political_action_v1",
            "actor": "李绩",
            "object": "皇帝求谏",
            "action_type": "其他",
            "time_context": "麟德二年二月",
            "source_span_refs": ["SLI-LINDE"],
        },
        "evidence_spans": [{"span_type": "action", "source_slice_ref": "SLI-LINDE", "text": "无得而谏"}],
    }
    run_root = write_run(tmp_path, claim=claim, candidates=candidates)
    cache_root = tmp_path / "claim_cache"

    report = tool.import_run(run_root, cache_root)

    claims = tool.read_jsonl(cache_root / "claims.jsonl")
    assert report["stats"]["claims_rebound_by_alias_mentions"] == 1
    assert (
        report["stats"]["claims_rebound_by_alias_mentions.source_unique_owner_anchor_without_requested_owner_in_claim"]
        == 1
    )
    assert claims[0]["emperor_name"] == "李治"
    assert claims[0]["fact_payload"]["owner_rebind_payload"]["matched_aliases"] == ["高宗"]


def test_import_run_normalizes_full_owner_alias_before_rebind(tmp_path: Path) -> None:
    candidates = {
        "task_identity": {"emperor_name": "李世民", "rule_code": "i5b_item_wide"},
        "candidate_slices": [
            {
                "slice_code": "SLI-QTT",
                "document_code": "DOC-SUI-53",
                "object_name": "屈突通",
                "source_title": "隋书/卷五十三",
                "text": "炀帝即位后遣屈突通持诏召汉王谅，谅验书无符，通占对无屈。",
            }
        ],
    }
    claim = {
        "claim_code": "CLM-QTT",
        "emperor_name": "隋炀帝",
        "object_name": "屈突通",
        "object_type": "person",
        "claim_kind": "material_claim",
        "claim_summary": "炀帝即位后遣屈突通持诏召汉王谅。",
        "confidence": 0.8,
        "source_slice_refs": ["SLI-QTT"],
        "fact_payload": {
            "fact_schema": "political_action_v1",
            "actor": "隋炀帝",
            "object": "屈突通",
            "action_type": "授权",
            "time_context": "炀帝即位",
            "source_span_refs": ["SLI-QTT"],
        },
        "evidence_spans": [{"span_type": "action", "source_slice_ref": "SLI-QTT", "text": "遣屈突通持诏召汉王谅"}],
    }
    run_root = write_run(tmp_path, claim=claim, candidates=candidates)
    cache_root = tmp_path / "claim_cache"

    report = tool.import_run(run_root, cache_root)

    claims = tool.read_jsonl(cache_root / "claims.jsonl")
    assert report["stats"]["claims_owner_normalized_by_alias"] == 1
    assert report["stats"]["claims_owner_normalized_by_alias.隋炀帝->杨广"] == 1
    assert claims[0]["emperor_name"] == "杨广"


def test_plan_candidates_reports_cached_and_uncovered_slices(tmp_path: Path) -> None:
    run_root = write_run(tmp_path)
    cache_root = tmp_path / "claim_cache"
    tool.import_run(run_root, cache_root)
    candidates_path = run_root / "TGT-I5B-ZYZ" / "candidates.final.json"
    uncovered_path = tmp_path / "uncovered_candidates.json"

    report = tool.plan_candidates(candidates_path, cache_root, uncovered_path)
    uncovered = json.loads(uncovered_path.read_text(encoding="utf-8"))

    assert report["candidate_slice_count"] == 2
    assert report["cached_slice_count"] == 1
    assert report["uncovered_slice_count"] == 1
    assert report["by_object"]["汤和"]["cached"] == 1
    assert report["by_object"]["常遇春"]["uncovered"] == 1
    assert [row["slice_code"] for row in uncovered["candidate_slices"]] == ["SLI-002"]


def test_plan_candidates_can_require_current_extractor_version(tmp_path: Path) -> None:
    run_root = write_run(
        tmp_path,
        clean_policy={"judge_mode": "claim_extraction_only", "extractor_version": "claim_extraction_only:v1"},
    )
    cache_root = tmp_path / "claim_cache"
    tool.import_run(run_root, cache_root)
    candidates_path = run_root / "TGT-I5B-ZYZ" / "candidates.final.json"
    uncovered_path = tmp_path / "uncovered_candidates.json"

    report = tool.plan_candidates(
        candidates_path,
        cache_root,
        uncovered_path,
        required_extractor_version="claim_extraction_only:v2_budgeted",
    )
    uncovered = json.loads(uncovered_path.read_text(encoding="utf-8"))

    assert report["required_extractor_version"] == "claim_extraction_only:v2_budgeted"
    assert report["cached_slice_count"] == 0
    assert report["uncovered_slice_count"] == 2
    assert [row["slice_code"] for row in uncovered["candidate_slices"]] == ["SLI-001", "SLI-002"]


def test_plan_candidates_ignores_non_active_cached_claims(tmp_path: Path) -> None:
    run_root = write_run(tmp_path)
    cache_root = tmp_path / "claim_cache"
    tool.import_run(run_root, cache_root)
    paths = tool.cache_paths(cache_root)
    claims = tool.read_jsonl(paths["claims"])
    claims[0]["status"] = "rejected"
    tool.write_jsonl(paths["claims"], claims)
    candidates_path = run_root / "TGT-I5B-ZYZ" / "candidates.final.json"
    uncovered_path = tmp_path / "uncovered_candidates.json"

    report = tool.plan_candidates(candidates_path, cache_root, uncovered_path)
    cached = tool.cached_claims_for_candidates(sample_candidates(), cache_root)
    uncovered = json.loads(uncovered_path.read_text(encoding="utf-8"))

    assert report["cached_slice_count"] == 0
    assert report["uncovered_slice_count"] == 2
    assert cached["claim_count"] == 0
    assert [row["slice_code"] for row in uncovered["candidate_slices"]] == ["SLI-001", "SLI-002"]


def test_cache_inventory_reports_objects_and_candidate_plan(tmp_path: Path) -> None:
    run_root = write_run(tmp_path)
    cache_root = tmp_path / "claim_cache"
    tool.import_run(run_root, cache_root)
    candidates_path = run_root / "TGT-I5B-ZYZ" / "candidates.final.json"

    report = tool.cache_inventory(cache_root, candidates_path)

    assert report["totals"]["claim_count"] == 1
    assert report["totals"]["slice_count"] == 1
    assert report["totals"]["object_count"] == 1
    assert report["by_object"]["汤和"]["claim_count"] == 1
    assert report["by_object"]["汤和"]["action_type_counts"] == {"授权": 1}
    assert report["candidate_plan"]["cached_slice_count"] == 1
    assert report["candidate_plan"]["uncovered_slice_count"] == 1
    assert "cached_claim_keys" not in report["candidate_plan"]
    assert report["candidate_cached_claim_count"] == 1


def test_cached_claims_for_candidates_remaps_slice_refs(tmp_path: Path) -> None:
    run_root = write_run(tmp_path)
    cache_root = tmp_path / "claim_cache"
    tool.import_run(run_root, cache_root)
    candidates = sample_candidates()
    candidates["candidate_slices"][0]["slice_code"] = "SLI-CURRENT"

    report = tool.cached_claims_for_candidates(candidates, cache_root)

    assert report["claim_count"] == 1
    assert report["matched_slice_count"] == 1
    assert report["claims"][0]["cache_status"] == "cached"
    assert report["claims"][0]["source_slice_refs"] == ["SLI-CURRENT"]
    assert report["claims"][0]["fact_payload"]["source_span_refs"] == ["SLI-CURRENT"]


def test_claim_cache_plan_reuses_overlapping_same_document_slice(tmp_path: Path) -> None:
    old_text = (
        "太祖召汤和入见，命汤和守常州，常州安辑，军民帖服。"
        "汤和因城守有方，转调粮饷无乏，诸将皆以为可任边防。"
        "其后巡视诸营，申明约束，修缮城池，百姓得安，士卒无扰。"
    )
    candidates = sample_candidates()
    candidates["candidate_slices"][0]["text"] = old_text
    run_root = write_run(tmp_path, candidates=candidates)
    cache_root = tmp_path / "claim_cache"
    tool.import_run(run_root, cache_root)
    candidates["candidate_slices"][0] = {
        "slice_code": "SLI-WIDER",
        "document_code": "DOC-001",
        "object_name": "汤和",
        "text": f"洪武初，朱元璋召诸将议事。{old_text}又命诸军修城池以备守御。",
    }
    candidates_path = tmp_path / "candidates.json"
    uncovered_path = tmp_path / "uncovered.json"
    write_json(candidates_path, candidates)

    report = tool.plan_candidates(candidates_path, cache_root, uncovered_path)
    hydrated = tool.cached_claims_for_candidates(candidates, cache_root)

    assert report["cached_slice_count"] == 1
    assert report["uncovered_slice_count"] == 1
    assert report["by_object"]["汤和"]["cached_text_overlap"] == 1
    assert hydrated["claim_count"] == 1
    assert hydrated["claims"][0]["source_slice_refs"] == ["SLI-WIDER"]
    assert json.loads(uncovered_path.read_text(encoding="utf-8"))["candidate_slices"][0]["object_name"] == "常遇春"


def test_merge_cached_claims_prepends_cached_claims_and_updates_counts(tmp_path: Path) -> None:
    run_root = write_run(tmp_path)
    cache_root = tmp_path / "claim_cache"
    tool.import_run(run_root, cache_root)
    cached = tool.cached_claims_for_candidates(sample_candidates(), cache_root)

    merged = tool.merge_cached_claims(
        {
            "status": "succeeded",
            "claims": [
                {
                    "claim_code": "CLM-NEW",
                    "emperor_name": "朱元璋",
                    "object_name": "常遇春",
                    "object_type": "person",
                    "claim_kind": "material_claim",
                    "claim_summary": "朱元璋命常遇春进兵。",
                    "source_slice_refs": ["SLI-002"],
                    "fact_payload": {"actor": "朱元璋", "object": "常遇春"},
                }
            ],
            "coverage": {},
        },
        cached,
    )

    assert [row["object_name"] for row in merged["claims"]] == ["汤和", "常遇春"]
    assert merged["coverage"]["claim_count"] == 2
    assert merged["_claim_cache_hydrated"]["merged_cached_claim_count"] == 1


def test_emit_pg_schema_contains_hot_index_tables() -> None:
    assert "retrieval_v3.claim_cache" in tool.PGSQL_SCHEMA_DRAFT
    assert "retrieval_v3.claim_source_slices" in tool.PGSQL_SCHEMA_DRAFT
    assert "retrieval_v3.claim_evidence" in tool.PGSQL_SCHEMA_DRAFT
    assert "retrieval_v3.claim_route_cache" in tool.PGSQL_SCHEMA_DRAFT
    assert "retrieval_v3.person_profile_claim_links" in tool.PGSQL_SCHEMA_DRAFT
    assert "rv3_claim_cache_type" in tool.PGSQL_SCHEMA_DRAFT
    assert "comment on column retrieval_v3.claim_cache.claim_type is" in tool.PGSQL_SCHEMA_DRAFT


def test_emit_pg_schema_command_returns_success(capsys) -> None:
    assert tool.main(["emit-pg-schema"]) == 0
    assert "retrieval_v3.claim_cache" in capsys.readouterr().out


def test_inventory_command_returns_success(tmp_path: Path, capsys) -> None:
    run_root = write_run(tmp_path)
    cache_root = tmp_path / "claim_cache"
    tool.import_run(run_root, cache_root)

    assert tool.main(["inventory", "--cache-root", str(cache_root), "--sample-limit", "0"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["totals"]["claim_count"] == 1
    assert payload["by_object"]["汤和"]["sample_claims"] == []
