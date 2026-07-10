from __future__ import annotations

from scripts.dev import retrieval_v2_claim_shard_planner as planner
from scripts.dev import retrieval_v2_judge_shards as judge_shards


def candidates() -> dict:
    return {
        "task_identity": {"emperor_name": "目标君主", "rule_code": "i5b_item_wide"},
        "target_profile": {"primary_name": "目标君主"},
        "object_seeds": [{"name": "甲"}, {"name": "乙"}, {"name": "丙"}, {"name": "丁"}],
        "source_documents": [
            {"document_code": "DOC-1", "title": "正史/卷一"},
            {"document_code": "DOC-2", "title": "正史/卷二"},
        ],
        "candidate_slices": [
            {"slice_code": "A-1", "document_code": "DOC-1", "object_name": "甲", "text": "目标君主命甲镇守。"},
            {"slice_code": "B-1", "document_code": "DOC-1", "object_name": "乙", "text": "乙奉命出征，克城而还。"},
            {"slice_code": "C-1", "document_code": "DOC-2", "object_name": "丙", "text": "丙少有志操。"},
            {"slice_code": "D-1", "document_code": "DOC-2", "object_name": "丁", "text": "导航文字。"},
        ],
    }


def test_owner_aware_plan_classifies_and_excludes_audit_only_rows(monkeypatch) -> None:
    def fake_mentions(text_value: str, **_kwargs):
        if "目标君主" not in text_value:
            return []
        return [
            {
                "alias": "目标君主",
                "resolution_status": "resolved",
                "resolved_owner_name": "目标君主",
                "owner_anchor_eligible": True,
                "resolution_rule": "exact_owner_name",
            }
        ]

    monkeypatch.setattr(planner.alias_pretag, "alias_mentions_in_text", fake_mentions)
    monkeypatch.setattr(planner.alias_pretag, "load_alias_resolver", lambda: object())
    monkeypatch.setattr(
        planner.claim_quality,
        "slice_claim_eligibility",
        lambda row: {"claim_eligible": row["slice_code"] != "D-1", "reasons": ["navigation_header"] if row["slice_code"] == "D-1" else []},
    )
    monkeypatch.setattr(planner.claim_quality, "biography_like_source", lambda row: row["slice_code"] in {"B-1", "C-1"})

    planned, manifest = planner.apply_owner_aware_shard_plan(candidates(), max_objects_per_shard=1)

    assert [row["owner_anchor_class"] for row in planned["candidate_slices"]] == ["A", "B", "C"]
    assert manifest["classification"]["class_counts"] == {"A": 1, "B": 1, "C": 1, "D": 1}
    assert manifest["summary"] == {"input_slice_count": 4, "prompt_slice_count": 3, "audit_only_slice_count": 1, "shard_count": 3}
    assert [row["shard_code"] for row in manifest["shards"]] == ["CSH-A-01", "CSH-B-01", "CSH-C-01"]
    assert manifest["audit_only_slices"][0]["slice_code"] == "D-1"
    assert planned["stats"]["owner_aware_audit_only_slices"] == 1


def test_judge_shards_consumes_owner_aware_manifest_without_repacking() -> None:
    payload = candidates()
    payload["claim_shard_plan"] = {
        "mode": "owner_aware",
        "shards": [
            {"shard_code": "CSH-A-01", "owner_anchor_class": "A", "object_names": ["甲"], "slice_codes": ["A-1"], "estimated_slice_chars": 200},
            {"shard_code": "CSH-B-01", "owner_anchor_class": "B", "object_names": ["乙"], "slice_codes": ["B-1"], "estimated_slice_chars": 200},
        ],
    }

    shards = judge_shards.build_judge_shards(payload, max_objects_per_shard=0, round_index=0)

    assert [shard["shard_code"] for shard in shards] == ["CSH-A-01", "CSH-B-01"]
    assert [row["slice_code"] for row in shards[0]["payload"]["candidate_slices"]] == ["A-1"]
    assert shards[1]["payload"]["judge_shard"]["owner_anchor_class"] == "B"


def test_owner_aware_plan_keeps_one_object_in_its_highest_priority_bundle(monkeypatch) -> None:
    payload = candidates()
    payload["candidate_slices"].append(
        {"slice_code": "A-2", "document_code": "DOC-1", "object_name": "乙", "text": "目标君主任命乙。"}
    )

    monkeypatch.setattr(planner.alias_pretag, "load_alias_resolver", lambda: object())
    monkeypatch.setattr(
        planner.alias_pretag,
        "alias_mentions_in_text",
        lambda text_value, **_kwargs: [{"resolution_status": "resolved", "resolved_owner_name": "目标君主", "owner_anchor_eligible": True}]
        if "目标君主" in text_value
        else [],
    )
    monkeypatch.setattr(planner.claim_quality, "slice_claim_eligibility", lambda _row: {"claim_eligible": True, "reasons": []})
    monkeypatch.setattr(planner.claim_quality, "biography_like_source", lambda _row: True)

    planned, manifest = planner.apply_owner_aware_shard_plan(payload, max_objects_per_shard=1)

    beta_rows = [row for row in planned["candidate_slices"] if row["object_name"] == "乙"]
    assert {row["object_bundle_class"] for row in beta_rows} == {"A"}
    assert any("object_bundle_promoted_to_A" in row["selection_reason_codes"] for row in beta_rows)
    assert sum("乙" in shard["object_names"] for shard in manifest["shards"]) == 1
