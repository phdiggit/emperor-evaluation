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
    current = json.loads(registry_path.read_text(encoding="utf-8"))
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
    assert formal["combined"]["five_dynasties_ready_count"] == 12
    assert formal["combined"]["five_dynasties_pending_count"] == 0
    assert all(row["third_item_score_points"] is not None for row in rows)
    assert {row["ruler_name"] for row in rows} == {
        "朱温", "朱友贞", "李存勖", "李嗣源", "石敬瑭", "郭威",
        "柴荣", "李昪", "李煜", "王建", "孟昶", "刘龑",
    }
    combined = formal["combined"]
    assert combined["record_count"] == 118
    assert combined["global_ranking_enabled"] is True
    by_name = {row["ruler_name"]: row for row in combined["records"]}
    assert by_name["刘肇"]["rank"] == by_name["柴荣"]["rank"] == 3
    assert by_name["李忱"]["rank"] == 5
    assert by_name["朱友贞"]["rank"] == 110
    assert by_name["李煜"]["rank"] == 114
    assert by_name["杨广"]["rank"] == 118


def test_north_song_third_item_replaces_legacy_registry_and_settles_complete_windows() -> None:
    from emperor_v4.evaluation.north_song_third_item import (
        SOURCE_SET_FINGERPRINT,
        build_north_song_formal_payloads,
        promote_north_song_battle_registry,
    )

    repo_root = Path(__file__).resolve().parents[1]
    current = json.loads(
        (repo_root / "docs/公共成果/军事/01-战役登记.json").read_text(encoding="utf-8")
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
    assert formal["combined"]["record_count"] == 118
    assert formal["combined"]["north_song_ready_count"] == 11
    assert formal["combined"]["north_song_pending_count"] == 0
    assert {row["ruler_name"] for row in rows} == {
        "赵匡胤", "赵光义", "赵恒", "刘娥", "赵祯", "赵曙", "赵顼", "高滔滔", "赵煦", "赵佶", "赵桓",
    }
    assert all(row["third_item_score_points"] is not None for row in rows)
    assert all(row["rank_status"] == "GLOBAL_CURRENT" for row in rows)
    assert formal["combined"]["north_song_partial_exclusions"] == []
    by_name = {row["ruler_name"]: row for row in rows}
    assert by_name["赵桓"]["AB_score_points"] == 0.0
    assert by_name["赵桓"]["axes"]["C_overall"] == "C-0"


def test_north_song_d_unknown_axes_are_auditable_not_negative_returns() -> None:
    from emperor_v4.evaluation.north_song_third_item import (
        _aggregate_d_cycle,
    )

    phase = {
        "phase_id": "P-UNKNOWN", "evaluation_subject_phase": "宋测试阶段",
        "actual_process": "史料未载结果。",
        "cost_axes": {"P": "UNKNOWN", "S": "S0", "M": "UNKNOWN", "A": "A0", "WC": "WC0"},
        "strategic_security": "UNKNOWN", "material_return": "UNKNOWN",
        "border_control": {"BCP": "UNKNOWN", "BCN": "UNKNOWN"},
        "phase_return_class": "UNKNOWN", "founding_startup_ledger": {"is_founding_process": False},
    }
    aggregated = _aggregate_d_cycle({
        "campaign_group_ref": "TEST-UNKNOWN", "war_event_refs": ["WAR-TEST"],
        "phase_ids": ["P-UNKNOWN"], "phases": [phase],
    })

    assert aggregated["return_class"] == "UNKNOWN"
    assert aggregated["unknown_axes"] == ["BCN", "BCP", "M", "P", "return", "security"]
    assert aggregated["material"] is False
    assert aggregated["national_negative"] is False


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
