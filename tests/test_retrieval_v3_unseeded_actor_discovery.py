from __future__ import annotations

from pathlib import Path

from scripts.dev import retrieval_v3_unseeded_actor_discovery as tool


def passage(raw_text: str, *, owners: list[str] | None = None) -> dict:
    return {
        "emperor_name": "朱元璋",
        "target_code": "TGT-ZYZ",
        "source_pack_code": "SPK-ZYZ",
        "document_code": "DOC-MINGSHA",
        "source_title": "明史",
        "title": "李善长传",
        "passage_code": "PAS-LSC",
        "locator": "列传第十五",
        "raw_text": raw_text,
        "owner_names": owners or ["李善长"],
    }


def name_row(object_id: int, name: str, *aliases: str) -> dict:
    return {
        "object_id": object_id,
        "canonical_name": name,
        "identity_status": "active",
        "names": list(aliases),
    }


def target_row(object_id: int, *, period: str = "明") -> dict:
    return {"emperor_name": "朱元璋", "object_id": object_id, "dynasty_labels": [period]}


def test_discovers_unseeded_names_from_negative_enumeration_without_name_seed() -> None:
    rows = [
        passage(
            "太祖所任张昶、杨宪、汪广洋、胡惟庸皆获罪，善长事寄如故。"
        )
    ]

    result = tool.discover_candidates_from_rows(
        rows,
        [name_row(1, "李善长")],
        [target_row(1)],
    )

    assert [row["observed_name"] for row in result["candidates"]] == ["张昶", "杨宪", "汪广洋", "胡惟庸"]
    assert all(row["discovery_status"] == "unresolved_name_candidate" for row in result["candidates"])
    assert all(row["scoring_allowed"] is False for row in result["candidates"])
    assert all(row["lead_stages"] == ["appointment_disposition_lead"] for row in result["candidates"])
    assert all(row["target_period"] == "明" for row in result["candidates"])
    assert all(row["source_hints"] == ["明史", "明實錄"] for row in result["candidates"])


def test_known_global_object_is_classified_without_attaching_or_scoring() -> None:
    result = tool.discover_candidates_from_rows(
        [passage("太祖所任杨宪获罪。")],
        [name_row(1, "李善长"), name_row(2, "杨宪")],
        [target_row(1)],
    )

    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["resolved_object_id"] == 2
    assert result["candidates"][0]["discovery_status"] == "known_object_not_attached"
    assert result["candidates"][0]["next_action"] == "run_object_source_refiner_then_negative_chain_review"


def test_owner_and_existing_target_mentions_are_not_unseeded_candidates() -> None:
    result = tool.discover_candidates_from_rows(
        [passage("李善长获罪，胡惟庸亦伏诛。")],
        [name_row(1, "李善长"), name_row(2, "胡惟庸")],
        [
            target_row(1),
            target_row(2),
        ],
    )

    assert result["candidates"] == []
    assert result["counts"]["owner_mentions"] >= 1
    assert result["counts"]["existing_target_object_mentions"] >= 1


def test_same_name_on_multiple_object_rows_is_filtered_when_target_has_one_identity() -> None:
    result = tool.discover_candidates_from_rows(
        [passage("侯君集伏诛。", owners=["萧瑀"])],
        [name_row(1, "萧瑀"), name_row(2, "侯君集"), name_row(3, "侯君集")],
        [
            target_row(1),
            target_row(3),
        ],
    )

    assert result["candidates"] == []
    assert result["counts"]["existing_target_object_mentions"] >= 1


def test_context_sentence_does_not_create_false_appointment_signal() -> None:
    result = tool.discover_candidates_from_rows(
        [passage("遣使覆囚决狱。侯君集伏诛。立晋王为太子。", owners=["萧瑀"])],
        [name_row(1, "萧瑀"), name_row(2, "侯君集")],
        [target_row(1)],
    )

    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["appointment_signals"] == []
    assert result["candidates"][0]["lead_stages"] == ["disposition_lead_only"]


def test_disposition_lead_never_becomes_negative_score() -> None:
    report = tool.build_report(
        passage_rows=[passage("太祖所任张昶、杨宪皆获罪。")],
        name_rows=[name_row(1, "李善长")],
        target_rows=[target_row(1)],
        schema_name="retrieval_v3",
        contract_code=tool.DEFAULT_CONTRACT_CODE,
        emperors=["朱元璋"],
        min_confidence=0.7,
    )
    worklist = tool.build_judge_worklist(report)

    assert report["write_db"] is False
    assert worklist
    assert all(row["scoring_allowed"] is False for row in worklist)
    assert all(row["required_review"]["has_disposition_only"] is None for row in worklist)


def test_structured_claim_actor_discovers_unseeded_suspect_without_scoring() -> None:
    result = tool.discover_candidates_from_claim_actors(
        [
            {
                "claim_key": "CLMK-68E4582CE4336A12C8BB",
                "emperor_name": "朱元璋",
                "object_name": "蓝玉",
                "claim_summary": "洪武二十六年二月，蒋𤩽告蓝玉谋反。",
                "confidence": 0.9,
                "fact_payload": {
                    "actor": "蒋𤩽",
                    "object": "蓝玉",
                    "action_type": "处置",
                    "office_or_domain": "锦衣卫告发谋反",
                    "outcome": "蓝玉下吏鞫讯",
                },
                "evidence": [
                    {
                        "document_code": "DOC-MINGSHA",
                        "source_title": "明史",
                        "source_slice_ref": "OSS-001",
                        "slice_text_preview": "锦衣卫指挥蒋𤩽告玉谋反，下吏鞫讯。",
                    }
                ],
            }
        ],
        [name_row(1, "蓝玉")],
        [target_row(1)],
    )

    assert len(result["candidates"]) == 1
    candidate = result["candidates"][0]
    assert candidate["observed_name"] == "蒋𤩽"
    assert candidate["extraction_methods"] == ["claim_fact_actor"]
    assert candidate["lead_stages"] == ["claim_actor_adverse_relation_lead"]
    assert candidate["evidence_windows"][0]["claim_key"] == "CLMK-68E4582CE4336A12C8BB"
    assert candidate["scoring_allowed"] is False


def test_structured_claim_actor_skips_emperor_and_non_adverse_relation() -> None:
    rows = [
        {
            "claim_key": "CLMK-1",
            "emperor_name": "朱元璋",
            "object_name": "蓝玉",
            "claim_summary": "朱元璋任命蓝玉。",
            "confidence": 0.9,
            "fact_payload": {"actor": "朱元璋", "object": "蓝玉", "action_type": "任命"},
        },
        {
            "claim_key": "CLMK-2",
            "emperor_name": "朱元璋",
            "object_name": "蓝玉",
            "claim_summary": "傅友德协助蓝玉整军。",
            "confidence": 0.9,
            "fact_payload": {"actor": "傅友德", "object": "蓝玉", "action_type": "协助"},
        },
    ]

    result = tool.discover_candidates_from_claim_actors(rows, [name_row(1, "蓝玉")], [target_row(1)])

    assert result["candidates"] == []


def test_structured_claim_actor_marks_royal_clan_and_extracts_title_alias() -> None:
    result = tool.discover_candidates_from_claim_actors(
        [
            {
                "claim_key": "CLMK-ROYAL-1",
                "emperor_name": "朱元璋",
                "object_name": "受害军民",
                "claim_summary": "鲁王朱檀滥权害民。",
                "confidence": 0.9,
                "fact_payload": {"actor": "朱檀", "object": "受害军民", "action_type": "滥权", "outcome": "王府多人受害"},
                "evidence": [{"document_code": "DOC-JFL", "source_title": "御制纪非录", "source_slice_ref": "JFL-LU", "slice_text_preview": "鲁王朱檀滥权害民。"}],
            }
        ],
        [],
        [target_row(1)],
    )

    candidate = result["candidates"][0]
    assert candidate["actor_scope"] == "royal_clan"
    assert candidate["reference_aliases"] == ["鲁王"]


def test_script_does_not_hardcode_acceptance_name_or_connect_legacy_contract_tables() -> None:
    source = Path(tool.__file__).read_text(encoding="utf-8")

    assert "杨宪" not in source
    assert "target_rule_requirements" not in source
    assert "retrieval_intents" not in source
    assert "write_db" in source
