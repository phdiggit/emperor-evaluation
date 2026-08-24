from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest

from emperor_v4.adapters.chronicle_source_summary import (
    SCHEMA_VERSION,
    SummaryValidationError,
    main,
    render_markdown,
    validate_summary,
)
from emperor_v4.evaluation.battle_registry_store import load_battle_registry
from emperor_v4.evaluation.post_tang_canonical_battle_promotion import (
    build_post_tang_canonical_binding_audit,
    build_post_tang_canonical_phase_records,
    promote_post_tang_canonical_phase_records,
)
from emperor_v4.evaluation.post_tang_third_item_readiness import (
    build_post_tang_third_item_readiness,
)
from emperor_v4.evaluation.post_tang_third_item_consumption import (
    build_post_tang_third_item_consumption_audit,
)
from emperor_v4.evaluation.south_song_third_item import (
    build_south_song_abc_preview,
    build_south_song_cycle_admission_audit,
    build_south_song_d_preview,
    build_south_song_formal_payloads,
    build_south_song_parent_cycle_audit,
)


SOURCE = """---
work_title: 測試史
volume: 001
source_unit_id: SRC-TEST-001-1
source_url: https://example.invalid/1
revision_ref: 1
raw_sha256: abc
paragraph_count: 2
---

[SRC-TEST-001-1-P0001]
甲軍擊乙軍，乙軍敗走。
[SRC-TEST-001-1-P0002]
州民輸錢修城。
"""


def test_south_song_to_ming_third_item_readiness_only_consumes_public_registry() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = build_post_tang_third_item_readiness(repo_root)
    assert payload["direct_chronicle_card_consumption_allowed"] is False
    assert payload["registered_record_count"] == 5695
    assert payload["public_outcome_count"] == 495
    assert payload["person_result_count"] == 562
    assert payload["canonical_phase_container_count"] == 3795
    assert payload["canonical_subject_phase_count"] == 8116
    assert payload["canonical_bound_phase_count"] == 3384
    assert payload["readiness_status"] == "PUBLIC_REGISTERED_NOT_SCORE_READY"
    assert [row["partition"] for row in payload["partitions"]] == [
        "south_song",
        "yuan",
        "ming",
    ]
    assert all(row["public_registration_ready"] for row in payload["partitions"])
    assert all(
        row["canonical_phase_registration_ready"] for row in payload["partitions"]
    )
    assert not any(row["ruler_window_binding_ready"] for row in payload["partitions"])
    assert not any(row["third_ab_axes_ready"] for row in payload["partitions"])
    assert not any(row["third_d_axes_ready"] for row in payload["partitions"])


def test_post_tang_canonical_cards_promote_to_third_item_phase_containers() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = build_post_tang_canonical_phase_records(repo_root)
    assert payload["record_count"] == 3795
    assert payload["subject_phase_count"] == 8116
    assert payload["withheld_invalid_card_count"] == 31
    assert payload["withheld_incompatible_file_count"] == 0
    assert payload["normalized_legacy_file_count"] == 4
    assert payload["semantic_fingerprint"] == (
        "110a7558423a48c69650b6cc91fe7f04e80abd662b0f1372389ff32797eef986"
    )
    assert all(
        record["third_item_phase_container"]
        and record["public_outcome_registered"] is False
        for record in payload["records"]
    )

    audit = build_post_tang_canonical_binding_audit(
        {"records": payload["records"]}
    )
    assert audit["duplicate_phase_id_count"] == 0
    assert audit["bound_phase_count"] == 3384
    assert audit["binding_status_counts"] == {
        "BOUND_EXCLUSIVE_GOVERNING_WINDOW": 3384,
        "OUTSIDE_SELECTED_RULER_WINDOWS": 344,
        "OUTSIDE_TARGET_POLITIES": 4215,
        "UNRESOLVED_WINDOW_OVERLAP": 157,
        "UNRESOLVED_YEAR": 16,
    }


def test_post_tang_phase_promotion_preserves_public_outcome_consumption() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    registry = load_battle_registry(repo_root / "docs/公共成果/军事/01-战役登记.json")
    public_count = sum(
        bool(record.get("public_outcome_registered"))
        for record in registry["records"]
    )
    promoted = promote_post_tang_canonical_phase_records(registry, repo_root)
    assert promoted["public_outcome_count"] == public_count
    target_partitions = set(
        promoted["post_tang_canonical_phase_promotion"]["source_partitions"]
    )
    preserved_count = sum(
        not record.get("third_item_phase_container")
        or record.get("dynasty_partition") not in target_partitions
        for record in registry["records"]
    )
    assert len(promoted["records"]) == preserved_count + 3795
    assert len({record["war_event_id"] for record in promoted["records"]}) == len(
        promoted["records"]
    )


def test_post_tang_third_item_consumption_starts_from_public_bound_phases() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = build_post_tang_third_item_consumption_audit(repo_root)
    assert payload["direct_chronicle_card_consumption_allowed"] is False
    assert payload["campaign_group_is_final_d_parent_cycle"] is False
    assert payload["ruler_count"] == 30
    assert payload["ruler_with_bound_phase_count"] == 27
    assert payload["provisional_parent_cycle_count"] == 2002
    assert payload["consumed_phase_count"] == 3384
    assert payload["duplicate_consumed_phase_id_count"] == 0
    assert payload["missing_required_raw_axis_phase_count"] == 0
    assert payload["unknown_raw_axis_phase_count"] == 207
    assert payload["founding_flagged_phase_count"] == 786
    assert payload["semantic_fingerprint"] == (
        "56ea0061f68e0530282a7e89f2b458f319d0d8beb690c56c576aae0650fa0aa6"
    )


def test_south_song_cross_item_admission_uses_actual_first_item_score() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = build_south_song_cycle_admission_audit(repo_root)
    assert payload["raw_bound_cycle_count"] == 582
    assert payload["admitted_cycle_count"] == 304
    assert payload["excluded_first_item_founding_cycle_count"] == 278
    assert payload["retained_founding_flag_cycle_count"] == 1
    assert payload["internal_restoration_candidate_count"] == 35
    assert payload["material_cycle_count"] == 149
    assert payload["unknown_axis_cycle_count"] == 82
    by_name = {row["ruler_name"]: row for row in payload["rulers"]}
    assert by_name["赵构"]["excluded_first_item_founding_cycle_count"] == 278
    assert by_name["赵扩"]["retained_founding_flag_cycle_count"] == 1


def test_south_song_parent_cycles_deduplicate_continuous_investments() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = build_south_song_parent_cycle_audit(repo_root)
    assert payload["raw_bound_cycle_count"] == 582
    assert payload["reviewed_parent_cycle_count"] == sum(
        row["reviewed_parent_cycle_count"] for row in payload["rulers"]
    )
    assert payload["reviewed_parent_cycle_count"] < payload["raw_bound_cycle_count"]
    assert payload["material_parent_cycle_count"] <= payload[
        "reviewed_parent_cycle_count"
    ]
    assert payload["unknown_axis_parent_cycle_count"] == 52
    assert payload["unknown_axis_parent_cycle_count"] <= payload[
        "reviewed_parent_cycle_count"
    ]
    assert payload["duplicate_consumed_phase_id_count"] == 0


def test_south_song_d_preview_reads_public_linear_q_cycles() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = build_south_song_d_preview(repo_root)
    assert payload["formal_score_write"] is False
    assert payload["source_path"].endswith("03-军事行动成本和收益登记.json")
    by_name = {row["ruler_name"]: row for row in payload["records"]}
    for row in by_name.values():
        metrics = row["D_portfolio_metrics"]
        assert metrics["T"] == len(metrics["cycle_q_adjudications"])
        assert metrics["Q"] == sum(
            cycle["q_contribution"] for cycle in metrics["cycle_q_adjudications"]
        )


def test_south_song_abc_preview_consumes_reviewed_parent_cycles() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    payload = build_south_song_abc_preview(repo_root)
    assert payload["formal_score_write"] is False
    assert payload["score_ceiling_points"] == 250
    by_name = {row["ruler_name"]: row for row in payload["rulers"]}
    assert by_name["赵构"]["C_preview_grade"] == "C-4"
    assert by_name["赵昚"]["C_preview_grade"] == "C-2"
    assert by_name["赵惇"]["control_contribution_type"] == "INHERITED_ONLY"
    assert by_name["赵扩"]["C_preview_grade"] == "C-1"
    assert by_name["赵昀"]["D_preview_score_points"] is None
    assert by_name["赵昀"]["D_preview_status"] == (
        "PUBLIC_LINEAR_Q_CURRENT_SCORE_MAPPING_PENDING"
    )


def test_south_song_formal_payloads_join_global_current_ranking() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    registry = load_battle_registry(
        repo_root / "docs/公共成果/军事/01-战役登记.json"
    )
    payload = build_south_song_formal_payloads(repo_root, registry)
    assert payload["combined"]["record_count"] == len(
        payload["combined"]["records"]
    ) == 201
    assert payload["combined"]["south_song_ready_count"] == 0
    assert payload["combined"]["south_song_pending_count"] == 5
    by_name = {row["ruler_name"]: row for row in payload["partition_records"]}
    assert all(row["third_item_score_points"] is None for row in by_name.values())
    assert all(row["rank"] is None for row in by_name.values())
    assert all(row["D_linear_Q"] is not None for row in by_name.values())


def _summary() -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "work_title": "測試史",
            "volume": "001",
            "source_unit_id": "SRC-TEST-001-1",
            "source_url": "https://example.invalid/1",
            "revision_ref": "1",
            "raw_sha256": "abc",
            "read_range": {
                "first_anchor": "SRC-TEST-001-1-P0001",
                "last_anchor": "SRC-TEST-001-1-P0002",
            },
            "paragraph_count": 2,
            "complete_linear_read": True,
            "previous_boundary_consumed": "无",
            "next_boundary": "无",
            "extraction_limits": "无",
        },
        "events": [
            {
                "event_id": "EVT-001-001",
                "type": "WAR",
                "title": "甲乙交战",
                "time_location": "unknown",
                "action": "甲军攻击乙军。",
                "result": "乙军败走。",
                "impact": "两军与当地居民。",
                "source_refs": [
                    {"anchor": "SRC-TEST-001-1-P0001", "quote": "乙軍敗走"},
                ],
                "relations": "新开，本卷闭合。",
                "uncertainty": "兵额与伤亡未知。",
                "fiscal_works_note": "无独立财政或工程事实。",
                "war_details": {
                    "parties_and_chain": "甲军对乙军，指挥者未载。",
                    "personnel_by_side": {"甲军": "unknown", "乙军": "unknown"},
                    "threat_control_by_side": {"甲军": "威胁推进", "乙军": "战败退走"},
                    "mobilization_transport": "unknown",
                    "assets": "unknown",
                    "region_production": "unknown",
                    "security_control": "甲军取得暂时优势。",
                    "acquisitions": "unknown",
                    "ruler_window": "unknown",
                },
            },
            {
                "event_id": "EVT-001-002",
                "type": "WORKS",
                "title": "输钱修城",
                "time_location": "unknown",
                "action": "州民输钱修城。",
                "result": "修城已实施。",
                "impact": "州民与城防。",
                "source_refs": [
                    {"anchor": "SRC-TEST-001-1-P0002", "quote": "州民輸錢修城"},
                ],
                "relations": "新开，本卷闭合。",
                "uncertainty": "金额与役期未知。",
                "fiscal_works_note": "独立 WORKS；财政投入与工程实施不可省略。",
                "war_details": None,
            },
        ],
        "boundaries": [],
        "coverage": {
            "sensitive_anchors_reviewed": True,
            "fiscal_works_reviewed": True,
            "unregistered_substantive_actions": "无",
            "unverifiable_quotes": "无",
        },
    }


def test_valid_summary_is_rendered_deterministically() -> None:
    summary = _summary()

    report = validate_summary(summary, SOURCE)
    rendered = render_markdown(summary)

    assert report["valid"] is True
    assert report["event_count_by_type"]["WAR"] == 1
    assert "### EVT-001-002｜输钱修城" in rendered
    assert "各方人员损害：甲军：unknown；乙军：unknown" in rendered


def test_render_command_writes_utf8_markdown(tmp_path) -> None:
    source_path = tmp_path / "卷001.md"
    summary_path = tmp_path / "volume-001.source-summary.json"
    output_path = tmp_path / "volume-001.source-summary.md"
    source_path.write_text(SOURCE, encoding="utf-8", newline="\n")
    summary_path.write_text(json.dumps(_summary(), ensure_ascii=False), encoding="utf-8", newline="\n")

    result = main([
        "render", "--summary", str(summary_path), "--source", str(source_path), "--output", str(output_path),
    ])

    assert result == 0
    assert output_path.read_bytes().startswith(b"# ")
    assert "卷001原文通读总结" in output_path.read_text(encoding="utf-8")


def test_repository_keeps_source_cache_and_review_expansions_out_of_git() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo_root,
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8").split("\0")

    forbidden = [
        path
        for path in tracked
        if path.startswith("docs/原始史料/")
        or path.startswith("docs/史料通读产物/唐以后编年/")
        or "战役成本收益补证-" in path
    ]
    assert forbidden == []

    for local_cache_path in (
        ".cache/source-text/测试史料/卷001.md",
        "docs/原始史料/测试史料/卷001.md",
        "docs/史料通读产物/唐以后编年/测试史料/volume-001.events.json",
    ):
        ignored = subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", local_cache_path],
            cwd=repo_root,
            check=False,
        )
        assert ignored.returncode == 0


def test_five_dynasties_scoring_products_are_complete_paired_inputs() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    product_root = repo_root / "docs/史料通读产物/五代十国/资治通鉴"
    expected_volumes = set(range(263, 295))
    summaries = {
        int(path.name.split(".", 1)[0].split("-", 1)[1]): path
        for path in product_root.glob("volume-*.source-summary.md")
    }
    adjudications = {
        int(path.name.split(".", 1)[0].split("-", 1)[1]): path
        for path in product_root.glob("volume-*.battle-adjudications.json")
    }

    assert set(summaries) == expected_volumes
    assert set(adjudications) == expected_volumes
    for volume in sorted(expected_volumes):
        summary_bytes = summaries[volume].read_bytes()
        adjudication_bytes = adjudications[volume].read_bytes()
        assert not summary_bytes.startswith(b"\xef\xbb\xbf")
        assert not adjudication_bytes.startswith(b"\xef\xbb\xbf")
        summary = summary_bytes.decode("utf-8")
        adjudication = json.loads(adjudication_bytes.decode("utf-8"))
        identity = adjudication["source_identity"]
        assert adjudication["schema_version"] == "chronicle-battle-adjudication-v2"
        for key in ("source_unit_id", "revision_ref", "raw_sha256"):
            value = identity[key]
            assert f"{key}：{value}" in summary or f"{key}：`{value}`" in summary


def test_five_dynasties_third_item_promotes_subject_phases_and_settles_all_rulers() -> None:
    from emperor_v4.evaluation.five_dynasties_third_item import (
        SOURCE_SET_FINGERPRINT,
        build_five_dynasties_formal_payloads,
        promote_five_dynasties_battle_registry,
    )

    repo_root = Path(__file__).resolve().parents[1]
    registry_path = repo_root / "docs/公共成果/军事/01-战役登记.json"
    current = load_battle_registry(registry_path)
    promoted = promote_five_dynasties_battle_registry(current, repo_root)
    partition = [
        row for row in promoted["records"]
        if row.get("dynasty_partition") == "five_dynasties"
    ]
    card_records = [row for row in partition if row["record_level"] == "chronicle_battle_card"]
    supplements = [
        row for row in partition
        if row["record_level"] == "targeted_primary_source_supplement"
    ]
    phases = [phase for row in card_records for phase in row["subject_phase_views"]]

    assert len(card_records) == 521
    assert len(supplements) == 2
    assert len(phases) == 1434
    assert len({phase["phase_id"] for phase in phases}) == 1434
    assert len({row["campaign_group_ref"] for row in card_records}) == 406
    assert promoted["five_dynasties_promotion"]["source_set_declared_fingerprint"] == SOURCE_SET_FINGERPRINT
    assert promoted["five_dynasties_promotion"]["retired_stale_record_count"] == 433
    assert all(row["wc_grade"] is None and row["security_grade"] is None for row in partition)
    for phase in phases:
        assert set(phase["cost_axes"]) >= {"P", "S", "M", "A", "WC"}
        assert set(phase["border_control"]) >= {"BCP", "BCN"}
        assert phase["strategic_security"]
        assert phase["material_return"]
        assert phase["phase_return_class"]
        assert phase["source_anchor_refs"]

    formal = build_five_dynasties_formal_payloads(repo_root, promoted)
    rows = formal["partition_records"]
    assert len(rows) == 12
    assert formal["combined"]["five_dynasties_ready_count"] == 0
    assert formal["combined"]["five_dynasties_pending_count"] == 12
    assert all(row["third_item_score_points"] is None for row in rows)
    assert {row["ruler_name"] for row in rows} == {
        "朱温", "朱友贞", "李存勖", "李嗣源", "石敬瑭", "郭威",
        "柴荣", "李昪", "李煜", "王建", "孟昶", "刘龑",
    }
    combined = formal["combined"]
    assert combined["record_count"] == len(combined["records"]) == 201
    assert combined["global_ranking_enabled"] is False
    assert all(row["rank"] is None for row in rows)
    assert all(row["D_linear_Q"] is not None for row in rows)

    binding_counts = Counter(
        phase["ruler_binding"]["status"] for phase in phases
    )
    assert binding_counts["UNRESOLVED_WINDOW_OVERLAP"] == 0
    assert binding_counts["OUTSIDE_FORMAL_REIGN_FOUNDING_PHASE"] == 6
    assert binding_counts["BOUND_REVIEWED_TRANSITION_SLICE"] == 21


def test_north_song_third_item_replaces_legacy_registry_and_settles_complete_windows() -> None:
    from emperor_v4.evaluation.north_song_third_item import (
        SOURCE_SET_FINGERPRINT,
        build_north_song_formal_payloads,
        promote_north_song_battle_registry,
    )

    repo_root = Path(__file__).resolve().parents[1]
    current = load_battle_registry(
        repo_root / "docs/公共成果/军事/01-战役登记.json"
    )
    promoted = promote_north_song_battle_registry(current, repo_root)
    promoted_twice = promote_north_song_battle_registry(promoted, repo_root)
    partition = [
        row for row in promoted["records"]
        if row.get("dynasty_partition") == "north_song"
    ]
    phases = [phase for row in partition for phase in row["subject_phase_views"]]

    assert len(partition) == 716
    assert len(phases) == 1586
    assert len({phase["phase_id"] for phase in phases}) == 1586
    assert len({row["campaign_group_ref"] for row in partition}) == 398
    assert promoted["north_song_promotion"]["source_set_fingerprint"] == SOURCE_SET_FINGERPRINT
    assert promoted["north_song_promotion"]["retired_stale_record_count"] == 801
    assert promoted["post_tang_partition_summaries"]["north_song"]["candidate_count"] == 716
    assert promoted["post_tang_partition_summaries"]["north_song"]["public_outcome_count"] == 716
    assert promoted_twice["semantic_fingerprint"] == promoted["semantic_fingerprint"]
    assert all(
        "docs/史料通读产物/唐以后编年/续资治通鉴-北宋" not in source_file
        for row in partition
        for source_file in row["source_lineage"]["source_files"]
    )
    assert all(not row["war_event_id"].startswith("WAR-POST-") for row in partition)

    status_counts = Counter(
        phase["ruler_binding"]["status"] for phase in phases
    )
    assert status_counts["BOUND_EXCLUSIVE_GOVERNING_WINDOW"] == 560
    assert status_counts["BOUND_REVIEWED_ABDICATION_ANCHOR"] == 3
    assert status_counts["BOUND_REVIEWED_TRANSITION_SLICE"] == 8
    assert status_counts["BOUND_REVIEWED_TERMINAL_COLLAPSE"] == 4
    assert status_counts["BOUND_REVIEWED_VOLUME_FALLBACK"] == 9
    assert status_counts["UNRESOLVED_WINDOW_OVERLAP"] == 0
    assert sum(
        count for status, count in status_counts.items()
        if status.startswith("BOUND_")
    ) == 584

    formal = build_north_song_formal_payloads(repo_root, promoted)
    rows = formal["partition_records"]
    assert len(rows) == 11
    assert formal["combined"]["record_count"] == len(
        formal["combined"]["records"]
    ) == 201
    assert formal["combined"]["north_song_ready_count"] == 0
    assert formal["combined"]["north_song_pending_count"] == 11
    assert {row["ruler_name"] for row in rows} == {
        "赵匡胤", "赵光义", "赵恒", "刘娥", "赵祯", "赵曙", "赵顼", "高滔滔", "赵煦", "赵佶", "赵桓",
    }
    assert all(row["third_item_score_points"] is None for row in rows)
    assert all(row["rank_status"] == "PENDING_D_SCORE_MAPPING" for row in rows)
    assert formal["combined"]["north_song_partial_exclusions"] == []
    by_name = {row["ruler_name"]: row for row in rows}
    assert all("confidence" not in row for row in formal["C"]["records"])
    assert by_name["刘娥"]["axes"]["D"] == "PUBLIC_LINEAR_Q"
    assert by_name["刘娥"]["D_score_points"] is None
    assert by_name["刘娥"]["third_item_score_points"] is None



def test_parent_cycle_unknown_axes_are_auditable_not_negative_returns() -> None:
    from emperor_v4.evaluation.five_dynasties_third_item import (
        _aggregate_parent_cycle_audit,
    )

    phase = {
        "phase_id": "P-UNKNOWN", "evaluation_subject_phase": "宋测试阶段",
        "actual_process": "史料未载结果。",
        "cost_axes": {"P": "UNKNOWN", "S": "S0", "M": "UNKNOWN", "A": "A0", "WC": "WC0"},
        "strategic_security": "UNKNOWN", "material_return": "UNKNOWN",
        "border_control": {"BCP": "UNKNOWN", "BCN": "UNKNOWN"},
        "phase_return_class": "UNKNOWN", "founding_startup_ledger": {"is_founding_process": False},
    }
    aggregated = _aggregate_parent_cycle_audit({
        "campaign_group_ref": "TEST-UNKNOWN", "war_event_refs": ["WAR-TEST"],
        "phase_ids": ["P-UNKNOWN"], "phases": [phase],
    })

    assert aggregated["return_class"] == "UNKNOWN"
    assert aggregated["unknown_axes"] == ["BCN", "BCP", "M", "P", "SB", "SN", "WR"]
    assert aggregated["material"] is False
    assert aggregated["national_negative"] is False


def test_parent_cycle_rollup_parses_combined_axis_strings() -> None:
    from emperor_v4.evaluation.five_dynasties_third_item import _aggregate_parent_cycle_audit

    phase = {
        "phase_id": "P-COMBINED-AXES",
        "evaluation_subject_phase": "组合轴合法样本",
        "actual_process": "大规模出兵未遇主力，边民与转输受损后班师。",
        "cost_axes": {"P": "P3估", "S": "S3", "M": "M4", "A": "A4", "WC": "WC4"},
        "strategic_security": "SB0/SN2",
        "material_return": "WR2",
        "border_control": {"BCP": "BCP0", "BCN": "BCN0"},
        "phase_return_class": "NEGATIVE_RETURN",
        "founding_startup_ledger": {"is_founding_process": False},
    }
    aggregated = _aggregate_parent_cycle_audit({
        "campaign_group_ref": "TEST-COMBINED-AXES",
        "war_event_refs": ["WAR-TEST-COMBINED"],
        "phase_ids": ["P-COMBINED-AXES"],
        "phases": [phase],
    })

    assert aggregated["unknown_axes"] == []
    assert aggregated["benefit_axes"] == {
        "SB": 0, "SN": 2, "BCP": 0, "BCN": 0, "WR": 2
    }
    assert aggregated["return_class"] == "NEGATIVE_RETURN"


def test_parent_cycle_all_zero_axes_remain_unknown() -> None:
    from emperor_v4.evaluation.five_dynasties_third_item import (
        _parent_cycle_return_class,
    )

    result, rationale = _parent_cycle_return_class(
        {"P": 0, "S": 0, "M": 0, "A": 0},
        {"SB": 0, "SN": 0, "BCP": 0, "BCN": 0, "WR": 0},
        s_attributable=True,
        route="D_INTERNAL_RESTORATION",
    )

    assert result == "UNKNOWN"
    assert "裁为UNKNOWN" in rationale


def test_five_dynasties_and_north_song_parent_cycle_reviews_cover_every_ruler() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    for config_name, expected_count in (
        ("five-dynasties-third-item-adjudications.json", 12),
        ("north-song-third-item-adjudications.json", 11),
    ):
        payload = json.loads(
            (repo_root / "config" / config_name).read_text(encoding="utf-8")
        )
        review = payload["parent_cycle_review"]
        ruler_ids = [row["ruler_id"] for row in payload["adjudications"]]
        assert review["status"] == "REVIEWED_ALL_RULERS"
        assert review["reviewed_ruler_ids"] == ruler_ids
        assert len(ruler_ids) == expected_count


@pytest.mark.parametrize("axis_index", [0, 1, 2])
@pytest.mark.parametrize("axis_grade", range(6))
def test_each_c_atomic_axis_has_a_reachable_zero_to_five_grade(
    axis_index: int, axis_grade: int
) -> None:
    from emperor_v4.evaluation.five_dynasties_third_item import _c_score

    axes = [5, 5, 5]
    axes[axis_index] = axis_grade
    overall, rate, points, _ = _c_score(*axes)

    assert overall == f"C-{axis_grade}"
    assert 0 <= rate <= 100
    assert points == round(rate / 2, 1)
    if axis_grade == 5:
        assert (overall, rate, points) == ("C-5", 100.0, 50.0)


@pytest.mark.parametrize("axis", ["A1", "A2"])
@pytest.mark.parametrize("end_grade", range(6))
def test_each_a_atomic_axis_has_a_reachable_zero_to_five_end_state(
    axis: str, end_grade: int
) -> None:
    from emperor_v4.evaluation.five_dynasties_third_item import _axis_a

    result = _axis_a(
        axis,
        {"start": end_grade, "end": end_grade, "reason": "reachability"},
    )
    assert result["end"].startswith(f"{axis}S{end_grade}_")


@pytest.mark.parametrize("axis", ["B1", "B2", "B4"])
@pytest.mark.parametrize("grade", range(6))
def test_each_b_atomic_axis_has_a_reachable_zero_to_five_grade(
    axis: str, grade: int
) -> None:
    from emperor_v4.evaluation.five_dynasties_third_item import _axis_b

    decision = {"grade": grade, "position": "MID", "reason": "reachability"}
    if axis == "B1":
        decision.update({"start_equivalent": 0.0, "end_equivalent": 10.0})
    result = _axis_b(axis, decision)
    assert result["grade"] == f"{axis}-{grade}"
    assert 0 <= result["score_rate"] <= 100
















def test_five_dynasties_subject_binding_never_uses_opponent_process_text() -> None:
    from emperor_v4.evaluation.five_dynasties_third_item import _bind_ruler

    binding = _bind_ruler(
        {
            "evaluation_subject_phase": "契丹进攻军×进攻阶段",
            "actual_process": "柴荣亲自统军迎战并取胜。",
        },
        (954, 954),
    )

    assert binding["ruler_id"] is None
    assert binding["status"] == "OUTSIDE_CONFIGURED_RULER_WINDOWS"


def test_current_third_item_d_uses_public_linear_q_only() -> None:
    from emperor_v4.evaluation.third_item_d_cycle_registry import (
        PUBLIC_REGISTRY_PATH,
        load_third_item_d_cycle_registry,
    )
    from emperor_v4.evaluation.third_item_d_settlement import (
        build_public_cycle_linear_q_analysis,
        linear_q_from_formal_cycle,
    )

    repo_root = Path(__file__).resolve().parents[1]
    registry = load_third_item_d_cycle_registry(repo_root / PUBLIC_REGISTRY_PATH)
    analysis = build_public_cycle_linear_q_analysis(registry)

    assert analysis["canonical_audit"]["legacy_fallback_count"] == 0
    assert analysis["canonical_audit"]["unknown_q_count"] == 0
    assert analysis["canonical_audit"]["subject_count"] == len(analysis["records"])
    for row in analysis["records"]:
        assert "D_grade" not in row
        assert "D_score_points" not in row
        metrics = row["D_portfolio_metrics"]
        cycles = metrics["cycle_q_adjudications"]
        assert metrics["T"] == len(cycles)
        assert metrics["Q"] == sum(cycle["q_contribution"] for cycle in cycles)
        assert all(
            cycle["q_contribution"] == linear_q_from_formal_cycle(cycle)
            for cycle in cycles
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("parent_group", "阶段与容器父级不一致"),
        ("missing_identity", "已绑定阶段身份字段不完整"),
        ("formal_identity", "主体/政权/统治窗口与正式对象不一致"),
        ("duplicate_owner", "同一主体阶段轴被复制给不同统治窗口"),
    ],
)
def test_public_registry_to_formal_d_identity_chain_rejects_drift(
    mutation: str,
    message: str,
) -> None:
    from emperor_v4.evaluation.post_tang_third_item_consumption import (
        iter_post_tang_bound_cycles,
    )

    phase = {
        "phase_id": "PHASE-1",
        "campaign_group_ref": "GROUP-1",
        "evaluation_subject_phase": "测试主体阶段",
        "subject_role": "DEFENDER",
        "actual_process": "测试过程。",
        "cost_axes": {"P": "P1", "S": "S1", "M": "M1", "A": "A1"},
        "strategic_security": "SB1",
        "material_return": "WR0",
        "border_control": {"BCP": "BCP0", "BCN": "BCN0"},
        "phase_return_class": "PROPORTIONATE_RETURN",
        "founding_startup_ledger": {"is_founding_process": False},
        "ruler_binding": {
            "status": "BOUND_EXCLUSIVE_GOVERNING_WINDOW",
            "ruler_id": "RULER-1",
            "ruler_name": "甲",
            "polity": "测试政权",
        },
    }
    registry = {
        "records": [{
            "war_event_id": "WAR-1",
            "campaign_group_ref": "GROUP-1",
            "third_item_phase_container": True,
            "subject_phase_views": [phase],
        }]
    }
    expected_name = "甲"
    if mutation == "parent_group":
        phase["campaign_group_ref"] = "GROUP-2"
    elif mutation == "missing_identity":
        phase["ruler_binding"]["polity"] = ""
    elif mutation == "formal_identity":
        expected_name = "乙"
    else:
        copied = deepcopy(phase)
        copied["phase_id"] = "PHASE-2"
        copied["ruler_binding"] = {
            **copied["ruler_binding"],
            "ruler_id": "RULER-2",
            "ruler_name": "乙",
        }
        registry["records"][0]["subject_phase_views"].append(copied)

    with pytest.raises(ValueError, match=message):
        iter_post_tang_bound_cycles(
            registry,
            "RULER-1",
            ruler_name=expected_name,
            polity="测试政权",
        )



def test_third_item_formal_markdown_uses_one_cross_dynasty_ranking_table() -> None:
    from emperor_v4.evaluation.five_dynasties_third_item import (
        AB_PATH,
        C_PATH,
        FORMAL_PATH,
        _render_combined_markdown,
        _render_formal_markdown,
    )

    repo_root = Path(__file__).resolve().parents[1]
    expectations = {
        "AB": (AB_PATH, "# 秦至清第三项A/B国防安全正式结算", "A+B/200"),
        "C": (C_PATH, "# 秦至清第三项C军事体系有效性正式结算", "C/50"),
    }
    for kind, (path, title, score_heading) in expectations.items():
        payload = json.loads((repo_root / path).read_text(encoding="utf-8"))
        rendered = _render_formal_markdown(kind, payload["records"])
        assert (repo_root / path.with_suffix(".md")).read_text(encoding="utf-8") == rendered
        assert rendered.startswith(title)
        assert score_heading in rendered
        assert "五代十国当前正式结算" not in rendered
        assert "北宋当前正式结算" not in rendered
        assert "FORMAL_START" not in rendered
        assert "结算依据" in rendered
        assert (
            "当前总值统一显示两位小数" in rendered
            if kind == "AB"
            else "所有分值统一显示一位小数" in rendered
        )
        assert "| 李世民 | 唐 |" in rendered
        assert "| 柴荣 | 后周 |" in rendered
        assert "| 赵恒 | 北宋 |" in rendered
        table_lines = [line for line in rendered.splitlines() if line.startswith("|")]
        assert len(table_lines) >= 3
        assert "结算依据" not in table_lines[0]
        table_blocks = [rendered]
        for block in table_blocks:
            table_groups: list[list[str]] = []
            current_group: list[str] = []
            for line in block.splitlines():
                if line.startswith("|"):
                    current_group.append(line)
                elif current_group:
                    table_groups.append(current_group)
                    current_group = []
            if current_group:
                table_groups.append(current_group)
            assert table_groups
            for group in table_groups:
                column_count = len(group[0].split("|"))
                assert all(len(line.split("|")) == column_count for line in group)
        score_field = {"AB": "AB200_score_points", "C": "C_score_points"}[kind]
        expected_detail_count = sum(
            row.get(score_field) is not None for row in payload["records"]
        )
        assert rendered.count("\n### ") == expected_detail_count
        assert ". 赵恒（" in rendered
        if kind == "C":
            assert "置信度" not in rendered
            assert all("confidence" not in row for row in payload["records"])
    combined_payload = json.loads((repo_root / FORMAL_PATH).read_text(encoding="utf-8"))
    from emperor_v4.evaluation.third_item_current_settlement import (
        _render_current_weighted_markdown,
    )

    combined_rendered = _render_current_weighted_markdown(combined_payload["records"])
    assert (
        repo_root / FORMAL_PATH.with_suffix(".md")
    ).read_text(encoding="utf-8") == combined_rendered
    assert "结算依据" in combined_rendered
    assert "A非成本锚" in combined_rendered
    assert "D局部成本" in combined_rendered
    assert "全局成果信用成本" in combined_rendered
    combined_table_lines = [
        line for line in combined_rendered.splitlines() if line.startswith("|")
    ]
    assert "结算依据" not in combined_table_lines[0]
    assert combined_rendered.count("\n### ") == len(combined_payload["records"])


def test_current_third_item_settlement_uses_component_union_deterministically() -> None:
    from emperor_v4.evaluation.five_dynasties_third_item import FORMAL_PATH
    from emperor_v4.evaluation.third_item_current_settlement import (
        build_current_third_item_settlement,
    )

    repo_root = Path(__file__).resolve().parents[1]
    first = build_current_third_item_settlement(repo_root)
    second = build_current_third_item_settlement(repo_root)
    assert first == second
    assert json.loads((repo_root / FORMAL_PATH).read_text(encoding="utf-8")) == first
    assert first["component_coverage_counts"] == {
        "AB": 201,
        "C": 201,
        "D": 201,
        "result_credit": 201,
        "union": 201,
        "ready": 201,
        "pending": 0,
    }
    by_name = {row["ruler_name"]: row for row in first["records"]}
    closed_names = {
        "刘盈", "刘玄", "司马懿", "海山",
        "努尔哈赤", "李元昊", "完颜阿骨打",
        "孟知祥", "耶律大石", "耶律宗真", "耶律贤", "耶律阮", "耶律隆绪",
    }
    assert all(by_name[name]["component_join_status"] == "READY" for name in closed_names)
    assert all(by_name[name]["rank"] is not None for name in closed_names)
    assert all(
        by_name[name][field] is not None
        for name in closed_names
        for field in (
            "A120_score_points",
            "A120_non_cost_anchor_points",
            "A120_positive_result_credit_points",
            "B80_score_points",
            "C50_score_points",
            "D_local_cost_profile",
            "global_cost_credit_profile",
            "cost_credit_factor",
        )
    )
    ready = [
        row for row in first["records"]
        if row["third_item_score_points"] is not None
    ]
    assert all(
        row["third_item_score_points"] == round(
            row["A120_non_cost_anchor_points"]
            + row["cost_credit_factor"]
            * (
                row["A120_positive_result_credit_points"]
                + row["B80_score_points"]
            )
            + row["C50_score_points"]
            + row["military_net_loss_penalty"],
            2,
        )
        for row in ready
    )
    assert first["schema_id"] == "emperor-v4-third-item-formal-settlement-v6-current-only"
    assert first["score_contract"]["D_cost_role"] == "GLOBAL_COST_CREDIT_FACTOR_SOURCE_NOT_ADDITIVE"
    assert first["score_recalculation_policy"] == "A120_CURRENT_PLUS_B80_COST_CREDIT_PLUS_C50_PLUS_MILITARY_NET_LOSS"
    stale_fields = {
        "A_score_points",
        "B_score_points",
        "AB_score_points",
        "C_score_points",
        "D_score_points",
        "D_score_status",
        "axes",
        "military_long_term_debt",
    }
    assert all(stale_fields.isdisjoint(row) for row in first["records"])
    assert by_name["李世民"]["global_cost_credit_profile"]["cost_band"] == "C4"
    assert by_name["刘彻"]["global_cost_credit_profile"]["cost_band"] == "C6"
    assert by_name["李雄"]["D_local_cost_profile"]["cost_band"] == "C0"
    assert by_name["李雄"]["global_cost_credit_profile"]["cost_band"] == "C5"

    c_payload = json.loads(
        (
            repo_root
            / "docs/评分结算/第三项军事与边疆净收益/军事体系有效性/01-皇帝C项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    liu_ying = next(row for row in c_payload["records"] if row["ruler_name"] == "刘盈")
    assert liu_ying["C_overall_grade"] == "C-N"
    assert liu_ying["C_score_points"] == 0.0
    assert liu_ying["score_status"] == "CONFIRMED_NOT_APPLICABLE_NO_SYSTEM_STRESS"
    assert liu_ying["no_system_stress_disposition"] == "CONFIRMED_NOT_APPLICABLE"
    assert liu_ying["independent_task_groups"] == []
    for row in c_payload["records"]:
        profile = row.get("task_outcome_profile") or {}
        current_refs = list(row.get("current_item_task_refs") or [])
        assert row.get("current_item_task_count", 0) == len(current_refs)
        assert profile.get("selected_task_count", 0) == len(current_refs)
        counts = profile.get("return_class_counts") or {}
        profile_refs = profile.get("return_class_refs") or {}
        assert sum(counts.values()) == len(current_refs)
        assert {
            ref for refs in profile_refs.values() for ref in refs
        } == set(current_refs)
        assert all(
            counts[outcome] == len(profile_refs[outcome])
            for outcome in counts
        )
        assert profile.get("known_outcome_count", 0) == sum(
            count for outcome, count in counts.items() if outcome != "UNKNOWN"
        )
    assert c_payload["shared_parent_ruler_binding_contract"] == {
        "status": "CLOSED",
        "shared_parent_count": 44,
        "binding_count": 88,
        "source": "config/third-item-c-outcome-adjudications.json",
        "rule": "同一父任务按显式ruler_id与CURRENT/CAPABILITY_ONLY范围分别消费，不复制另一人物行动、结果或成本。",
    }
    c_by_name = {row["ruler_name"]: row for row in c_payload["records"]}
    invalid_southern_qi_refs = {
        "NC-V142-LEAD-142-01",
        "NC-V142-LEAD-142-03",
        "NC-V142-LEAD-142-05",
        "NC-QI-LIANG-TRANSITION-500-502",
    }
    for name, expected_count in (("萧道成", 3), ("萧鸾", 4)):
        row = c_by_name[name]
        assert row["current_item_task_count"] == expected_count
        assert invalid_southern_qi_refs.isdisjoint(row["current_item_task_refs"])
        assert set(row["excluded_out_of_window_parent_refs"]) == invalid_southern_qi_refs
    assert c_by_name["司马睿"]["cross_item_independent_information_refs"] == [
        "WAR-LEAD-HANMIAN-317"
    ]

    ab_payload = json.loads(
        (
            repo_root
            / "docs/评分结算/第三项军事与边疆净收益/国防安全/01-皇帝AB项正式结算.json"
        ).read_text(encoding="utf-8")
    )
    ab_by_name = {row["ruler_name"]: row for row in ab_payload["records"]}
    assert ab_by_name["杨坚"]["primary_threat_refs"] == ["SUI-TURK-581-587"]
    assert set(ab_by_name["朱翊钧"]["primary_threat_refs"]) == {
        "MTJ-MING-KOREA-IMJIN-1592-1598",
        "MTJ-MING-QING-SARHU-1619",
    }
    assert set(ab_by_name["朱由校"]["primary_threat_refs"]) == {
        "MTJ-MING-QING-LIAOYANG-1621",
        "MTJ-MING-QING-GUANGNING-1622",
        "MTJ-MING-QING-NINGYUAN-1626",
        "MTJ-MING-DUTCH-PENGHU-1622-1624",
    }




def test_founder_unification_accounts_are_absent_from_third_item_consumption() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    first_item = json.loads(
        (repo_root / "config/first-item-c-acquisition-windows.json").read_text(
            encoding="utf-8"
        )
    )
    excluded_by_name = {
        item["ruler_name"]: set(item.get("campaign_refs") or [])
        for item in first_item.get("manual_windows") or []
    }
    excluded_by_name.setdefault("杨坚", set()).add("WAR-LEAD-SUI-ABSORB-LIANG-587")
    excluded_by_name.setdefault("沮渠蒙逊", set()).add("WAR-LEAD-112-MENGXUN-401")
    excluded_by_name.setdefault("拓跋珪", set()).update(
        {"WAR-LEAD-112-WEI-MOYIGAN-402", "WAR-LEAD-115-WEI-SUCCESSION-409"}
    )
    excluded_by_name.setdefault("李雄", set()).add(
        "CAMPAIGN-JIN-YIZHOU-LI-300-OPEN"
    )
    excluded_by_name.setdefault("李渊", set()).update(
        {
            "CAMPAIGN-TANG-XUYUANLANG-621-623",
            "CAMPAIGN-TANG-LIUHEITA-621-623",
            "CAMPAIGN-TANG-FUGONGSHI-623-624",
        }
    )
    base = repo_root / "docs/评分结算/第三项军事与边疆净收益"
    payloads = (
        (base / "国防安全/01-皇帝AB项正式结算.json", "evidence_event_refs"),
        (base / "军事体系有效性/01-皇帝C项正式结算.json", "settled_event_refs"),
        (base / "军事成本收益比/01-皇帝D项正式结算.json", "included_d_cycle_refs"),
    )
    for path, field in payloads:
        rows = json.loads(path.read_text(encoding="utf-8"))["records"]
        for row in rows:
            assert not (
                set(row.get(field) or [])
                & excluded_by_name.get(row["ruler_name"], set())
            )

    c_rows = json.loads(payloads[1][0].read_text(encoding="utf-8"))["records"]
    d_rows = json.loads(payloads[2][0].read_text(encoding="utf-8"))["records"]
    ab_rows = json.loads(payloads[0][0].read_text(encoding="utf-8"))["records"]
    c_by_id = {row["ruler_id"]: row for row in c_rows}
    ab_by_name = {row["ruler_name"]: row for row in ab_rows}
    c_by_name = {row["ruler_name"]: row for row in c_rows}
    d_by_name = {row["ruler_name"]: row for row in d_rows}

    def d_cycle_refs(row: dict) -> set[str]:
        refs = set(row.get("included_d_cycle_refs") or [])
        for field in ("external_strategic_chains", "strategic_internal_chains"):
            for chain in row.get(field) or []:
                refs.update(chain.get("member_cycle_refs") or [])
        return refs

    for ruler_name in ("李雄", "李渊"):
        excluded = excluded_by_name[ruler_name]
        assert not excluded & set(ab_by_name[ruler_name]["parent_cycle_refs"])
        assert not excluded & set(c_by_name[ruler_name]["independent_task_groups"])
        assert not excluded & d_cycle_refs(d_by_name[ruler_name])
    for row in d_rows:
        excluded = set(row.get("excluded_unification_cycle_refs") or [])
        if excluded:
            c_row = c_by_id[row["ruler_id"]]
            scoring_refs = set(c_row.get("independent_task_groups") or []) - set(
                c_row.get("capability_only_parent_refs") or []
            )
            assert not excluded & scoring_refs


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda value: value["events"][0]["source_refs"][0].update({"quote": "甲軍……敗走"}),
            "不得含省略号",
        ),
        (
            lambda value: value["events"][0]["war_details"]["personnel_by_side"].clear() or value["events"][0]["war_details"]["personnel_by_side"].update({"己方": "unknown"}),
            "不得使用未定义的己方/敌方",
        ),
        (
            lambda value: value["events"][1].update({"war_details": {}}),
            "非 WAR 必须为 null",
        ),
    ],
)
def test_summary_rejects_unconsumable_fields(mutate, expected: str) -> None:
    summary = deepcopy(_summary())
    mutate(summary)

    with pytest.raises(SummaryValidationError, match=expected):
        validate_summary(summary, SOURCE)
