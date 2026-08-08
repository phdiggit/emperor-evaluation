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
    assert by_name["柴荣"]["rank"] == 5
    assert by_name["柴荣"]["axes"]["D"] == "D-3"
    assert by_name["柴荣"]["D_score_points"] == 28.1
    assert by_name["李忱"]["rank"] == 4
    assert by_name["朱友贞"]["rank"] == 111
    assert by_name["李煜"]["rank"] == 113
    assert by_name["杨广"]["rank"] == 118

    binding_counts = Counter(
        phase["ruler_binding"]["status"] for phase in phases
    )
    assert binding_counts["UNRESOLVED_WINDOW_OVERLAP"] == 0
    assert binding_counts["OUTSIDE_FORMAL_REIGN_FOUNDING_PHASE"] == 6
    assert binding_counts["BOUND_REVIEWED_TRANSITION_SLICE"] == 21

    d_by_name = {row["ruler_name"]: row for row in formal["D"]["records"]}
    c_by_name = {row["ruler_name"]: row for row in formal["C"]["records"]}
    ab_by_name = {row["ruler_name"]: row for row in formal["AB"]["records"]}
    assert d_by_name["柴荣"]["D_portfolio_metrics"]["material_cycle_count"] == 6
    assert d_by_name["柴荣"]["D_portfolio_metrics"]["exceptional_national_recovery_gate"] == "NOT_APPLICABLE"
    assert d_by_name["柴荣"]["D_portfolio_metrics"]["top_tier_high_return_refs"] == []
    assert len(d_by_name["柴荣"]["D_portfolio_metrics"]["national_negative_return_refs"]) == 1
    assert len(d_by_name["柴荣"]["cycle_merge_adjudications"]) == 2
    assert len(d_by_name["李存勖"]["cycle_merge_adjudications"]) == 1
    assert len(d_by_name["石敬瑭"]["cycle_merge_adjudications"]) == 2
    assert len(d_by_name["李昪"]["cycle_merge_adjudications"]) == 1
    assert len(d_by_name["刘龑"]["cycle_merge_adjudications"]) == 1
    assert d_by_name["石敬瑭"]["D_grade"] == "D-3"
    assert d_by_name["李昪"]["D_grade"] == "D-3"
    assert d_by_name["王建"]["D_score_points"] == 28.3
    assert c_by_name["柴荣"]["independent_task_count"] == 12
    assert ab_by_name["柴荣"]["defense_event_count"] == 12
    assert (
        ab_by_name["柴荣"]["parent_cycle_merge_adjudications"]
        == c_by_name["柴荣"]["parent_cycle_merge_adjudications"]
    )
    for row in formal["C"]["records"]:
        assert set(row["major_system_failure_refs"]) <= set(row["independent_task_groups"])
        assert set(row.get("major_system_success_refs") or []) <= set(row["independent_task_groups"])
        if row["C_overall_grade"] in {"C-4", "C-5"}:
            assert len(row["major_system_success_refs"]) >= max(
                1, len(row["major_system_failure_refs"])
            )
        assert ab_by_name[row["ruler_name"]]["defense_event_count"] == row["independent_task_count"]
        assert ab_by_name[row["ruler_name"]]["parent_cycle_refs"] == row["independent_task_groups"]


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
    assert by_name["赵恒"]["axes"]["D"] == "D-3"
    assert by_name["赵恒"]["D_score_points"] == 27.9
    assert by_name["赵祯"]["D_score_points"] == 28.9
    assert by_name["赵顼"]["D_score_points"] == 27.9
    assert all("confidence" not in row for row in formal["C"]["records"])
    assert by_name["赵匡胤"]["axes"]["C_overall"] == "C-3"

    d_by_name = {row["ruler_name"]: row for row in formal["D"]["records"]}
    c_by_name = {row["ruler_name"]: row for row in formal["C"]["records"]}
    ab_by_name = {row["ruler_name"]: row for row in formal["AB"]["records"]}
    for ruler_name, c_row in c_by_name.items():
        if not str(c_row["ruler_id"]).startswith("RULER-NS-"):
            continue
        assert ab_by_name[ruler_name]["defense_event_count"] == c_row["independent_task_count"]
        assert (
            ab_by_name[ruler_name]["parent_cycle_merge_adjudications"]
            == c_row["parent_cycle_merge_adjudications"]
        )
    assert d_by_name["赵祯"]["D_portfolio_metrics"]["usable_cycle_count"] == 36
    assert d_by_name["赵祯"]["D_portfolio_metrics"]["material_cycle_count"] == 12
    assert len(d_by_name["赵祯"]["D_portfolio_metrics"]["major_high_return_refs"]) == 1
    assert d_by_name["赵顼"]["D_portfolio_metrics"]["usable_cycle_count"] == 26
    assert d_by_name["赵顼"]["D_portfolio_metrics"]["material_cycle_count"] == 9
    assert len(d_by_name["赵顼"]["D_portfolio_metrics"]["major_high_return_refs"]) == 1
    assert len(d_by_name["赵祯"]["cycle_merge_adjudications"]) == 1
    assert len(d_by_name["赵顼"]["cycle_merge_adjudications"]) == 4
    assert len(d_by_name["赵光义"]["cycle_merge_adjudications"]) == 2
    assert len(d_by_name["赵恒"]["cycle_merge_adjudications"]) == 1
    assert len(d_by_name["赵煦"]["cycle_merge_adjudications"]) == 2
    assert len(d_by_name["赵佶"]["cycle_merge_adjudications"]) == 5
    assert len(d_by_name["赵桓"]["cycle_merge_adjudications"]) == 3
    assert d_by_name["高滔滔"]["excluded_non_attributable_cycle_refs"] == [
        "XZTJ-SONG-XIA-LVHUIQING-YANAN-BORDER-RETRO",
        "XZTJ-SONG-XINING-YUANFENG-EXPANSION-AGGREGATE-RETRO",
    ]
    for row in formal["D"]["records"]:
        if row["D_grade"] not in {"D-4", "D-5"}:
            continue
        metrics = row["D_portfolio_metrics"]
        assert len(metrics["top_tier_high_return_refs"]) >= max(
            1, len(metrics["national_negative_return_refs"])
        )


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


def test_d4_rejects_more_than_one_non_national_negative_return() -> None:
    from emperor_v4.evaluation.five_dynasties_third_item import _d_grade_and_score

    cycles = []
    for index, return_class in enumerate(
        ["HIGH_RETURN"] * 5 + ["PROPORTIONATE_RETURN"] * 5 + ["NEGATIVE_RETURN"] * 2
    ):
        cycles.append({
            "campaign_group_ref": f"TEST-D4-GATE-{index}",
            "return_class": return_class,
            "material": True,
            "national_negative": False,
            "major_high_return": return_class == "HIGH_RETURN",
            "top_high_return": False,
        })

    grade, score, metrics = _d_grade_and_score(cycles)

    assert metrics["return_class_counts"]["NEGATIVE_RETURN"] == 2
    assert grade == "D-3"
    assert 22.0 <= score <= 29.9

    for cycle in cycles[-2:]:
        cycle["material"] = False
    grade, score, metrics = _d_grade_and_score(cycles)

    assert metrics["return_class_counts"]["NEGATIVE_RETURN"] == 2
    assert metrics["material_negative_return_refs"] == []
    assert metrics["material_return_class_counts"] == {
        "HIGH_RETURN": 5,
        "PROPORTIONATE_RETURN": 5,
    }
    assert grade == "D-3"

    cycles[0]["top_high_return"] = True
    cycles[-2]["material"] = True
    grade, score, metrics = _d_grade_and_score(cycles)
    assert grade == "D-4"
    assert 30.0 <= score <= 35.9


def test_d5_requires_every_material_return_to_be_closed() -> None:
    from emperor_v4.evaluation.five_dynasties_third_item import _d_grade_and_score

    cycles = [
        {
            "campaign_group_ref": f"TEST-D5-CLOSED-{index}",
            "return_class": "HIGH_RETURN" if index < 3 else "PROPORTIONATE_RETURN",
            "material": True,
            "national_negative": False,
            "major_high_return": index < 2,
            "top_high_return": index == 0,
        }
        for index in range(4)
    ]
    grade, _, metrics = _d_grade_and_score(cycles)
    assert grade == "D-5"
    assert metrics["material_return_closure_rate"] == 1.0

    cycles.append({
        "campaign_group_ref": "TEST-D5-UNKNOWN",
        "return_class": "UNKNOWN",
        "material": True,
        "national_negative": False,
        "major_high_return": False,
        "top_high_return": False,
    })
    grade, _, metrics = _d_grade_and_score(cycles)
    assert grade == "D-4"
    assert metrics["material_unknown_cycle_refs"] == ["TEST-D5-UNKNOWN"]
    assert metrics["material_return_closure_rate"] == 0.8


def test_d4_national_negative_requires_thick_independent_counterevidence() -> None:
    from emperor_v4.evaluation.five_dynasties_third_item import _d_grade_and_score

    cycles = [
        {
            "campaign_group_ref": f"TEST-D4-EXCEPTION-HIGH-{index}",
            "return_class": "HIGH_RETURN",
            "material": True,
            "national_negative": False,
            "major_high_return": index < 2,
            "top_high_return": False,
        }
        for index in range(5)
    ]
    cycles[0]["top_high_return"] = True
    cycles.append({
        "campaign_group_ref": "TEST-D4-EXCEPTION-NATIONAL",
        "return_class": "NEGATIVE_RETURN",
        "material": True,
        "national_negative": True,
        "major_high_return": False,
        "top_high_return": False,
    })

    grade, _, metrics = _d_grade_and_score(
        cycles, allow_exceptional_national_recovery=False
    )
    assert grade == "D-3"
    assert metrics["exceptional_national_recovery_gate"] == "NOT_APPLICABLE"

    grade, score, metrics = _d_grade_and_score(
        cycles, allow_exceptional_national_recovery=True
    )
    assert grade == "D-4"
    assert score <= 34.3
    assert metrics["exceptional_national_recovery_gate"] == "PASSED_STRONG_COUNTEREVIDENCE"


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


def test_current_third_item_thick_thin_evidence_gates_are_globally_consistent() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    base = repo_root / "docs/评分结算/第三项军事与边疆净收益"
    c_rows = json.loads(
        (base / "军事体系有效性/01-皇帝C项正式结算.json").read_text(encoding="utf-8")
    )["records"]
    d_rows = json.loads(
        (base / "军事成本收益比/01-皇帝D项正式结算.json").read_text(encoding="utf-8")
    )["records"]

    assert len(c_rows) == len(d_rows) == 118
    for row in c_rows:
        grades = [
            int(str(row[key]).rsplit("-", 1)[-1])
            for key in (
                "combat_delivery_grade",
                "operational_sustainability_cap",
                "system_reliability_cap",
            )
        ]
        overall = int(str(row["C_overall_grade"]).rsplit("-", 1)[-1])
        tasks = int(row["independent_task_count"])
        assert overall == min(grades)
        assert not (tasks <= 1 and (grades[0] > 3 or grades[2] > 3))
        assert not (tasks == 2 and (grades[0] > 4 or grades[2] > 4))
        assert "confidence" not in row
        if row["C_overall_grade"] in {"C-4", "C-5"}:
            assert len(row.get("major_system_success_refs") or []) >= max(
                1, len(row.get("major_system_failure_refs") or [])
            )

    d4_caps = {2: 33.0, 3: 34.6, 4: 35.0, 5: 35.4}
    for row in d_rows:
        metrics = row.get("D_portfolio_metrics") or {}
        material = int(metrics.get("material_cycle_count") or 0)
        known_material = int(metrics.get("known_material_cycle_count") or 0)
        expected_status = (
            "UNDER_TESTED" if known_material <= 1
            else "LIMITED_EXPOSURE" if known_material <= 3
            else "SUFFICIENT_EXPOSURE"
        )
        assert metrics.get("evidence_status") == expected_status
        if row["D_grade"] == "D-4":
            major = len(metrics.get("major_high_return_refs") or [])
            cap = d4_caps.get(material, 35.9)
            if material == 2 and major >= 2:
                cap = 34.0
            elif material == 3 and major >= 2:
                cap = 34.8
            assert row["D_score_points"] <= cap
            national = metrics.get("national_negative_return_refs") or []
            if national:
                assert len(national) == 1
                assert metrics.get("exceptional_national_recovery_gate") == "PASSED_STRONG_COUNTEREVIDENCE"
            assert len(metrics.get("top_tier_high_return_refs") or []) >= max(
                1, len(national)
            )
        if row["D_grade"] == "D-5":
            assert material >= 4
            assert not (metrics.get("national_negative_return_refs") or [])

    by_name = {row["ruler_name"]: row for row in d_rows}
    assert by_name["李雄"]["D_score_points"] == 27.1
    assert by_name["陈蒨"]["D_score_points"] == 28.3
    assert by_name["柴荣"]["D_score_points"] > by_name["苻健"]["D_score_points"]
    assert by_name["拓跋焘"]["D_grade"] == "D-3"
    assert by_name["拓跋焘"]["D_score_points"] == 28.3
    assert by_name["拓跋焘"]["D_score_points"] > by_name["柴荣"]["D_score_points"]
    assert by_name["李忱"]["D_grade"] == "D-3"
    assert by_name["李忱"]["D_score_points"] == 28.7
    assert by_name["李忱"]["D_score_points"] > by_name["司马曜"]["D_score_points"]
    assert by_name["李忱"]["D_score_points"] > by_name["李雄"]["D_score_points"]
    assert by_name["李忱"]["D_score_points"] > by_name["王建"]["D_score_points"]
    assert by_name["拓跋焘"]["D_score_points"] > by_name["柴荣"]["D_score_points"]
    li_shimin = by_name["李世民"]
    assert li_shimin["D_grade"] == "D-4"
    assert li_shimin["D_score_points"] == 35.1
    assert li_shimin["D_portfolio_metrics"]["material_cycle_count"] == 8
    assert li_shimin["D_portfolio_metrics"]["material_return_class_counts"] == {
        "HIGH_RETURN": 4,
        "NEGATIVE_RETURN": 1,
        "PROPORTIONATE_RETURN": 3,
    }
    for row in d_rows:
        metrics = row["D_portfolio_metrics"]
        counts = metrics["material_return_class_counts"]
        assert sum(counts.values()) == metrics["material_cycle_count"]
        assert metrics["return_class_counts"].get("UNKNOWN", 0) == 0
        assert counts.get("UNKNOWN", 0) == 0
        assert metrics["known_material_cycle_count"] == metrics["material_cycle_count"]
        assert metrics["material_return_closure_rate"] in {0.0, 1.0}
    return_unknown_exclusions = {
        item["campaign_group_ref"]
        for row in d_rows
        for item in row.get("excluded_cycle_adjudications") or []
        if "不进入D回报组合" in item["reason"]
        or "不构成D军事投资周期" in item["reason"]
        or "不进入徽宗D回报组合" in item["reason"]
    }
    assert return_unknown_exclusions == {
        "ZZTJ-270-LIANG-YANZHOU-ZHANGWANJIN-0918",
        "XZTJ-SONG-LIAO-SOUTHERN-INVASION-1003-1004",
        "XZTJ-SONG-QINZHOU-TRIBAL-SKIRMISH-1014",
        "XZTJ-SONG-LIAO-YINFANG-BORDER-1045",
        "XZTJ-SONG-ZHUYA-HUANGYING-1076",
        "XZTJ-JIN-SONG-ZHONGSHAN-SIEGE-1125-1126",
        "XZTJ-JIN-SONG-QINGYUAN-1125",
    }
    assert all(
        row.get("binding_source") == "QIN_TANG_PARENT_CYCLE_CURRENT_RECALCULATION"
        for row in d_rows
        if not str(row["ruler_id"]).startswith(("RULER-FD-", "RULER-NS-"))
    )
    same_polity_owners: dict[str, list[dict]] = {}
    for row in d_rows:
        if str(row["ruler_id"]).startswith(("RULER-FD-", "RULER-NS-")):
            continue
        full_overrides = {
            item["war_event_id"]
            for item in row.get("ruler_event_class_overrides", [])
            if (item.get("values") or {}).get("d_cost_axes")
            and (item.get("values") or {}).get("return_class")
        }
        for cycle in row["D_portfolio_metrics"]["material_cycle_adjudications"]:
            same_polity_owners.setdefault(cycle["campaign_group_ref"], []).append({
                "polity": row["polity"],
                "full_override": cycle["campaign_group_ref"] in full_overrides,
                "cycle": cycle,
            })
    for owners in same_polity_owners.values():
        polities = [owner["polity"] for owner in owners]
        if len(polities) == len(set(polities)):
            continue
        for owner in owners:
            if polities.count(owner["polity"]) > 1 and not owner["full_override"]:
                assert owner["cycle"]["material"] is False



def test_third_item_formal_markdown_uses_one_cross_dynasty_ranking_table() -> None:
    from emperor_v4.evaluation.five_dynasties_third_item import (
        AB_PATH,
        C_PATH,
        D_PATH,
        FORMAL_PATH,
        _render_combined_markdown,
        _render_formal_markdown,
    )

    repo_root = Path(__file__).resolve().parents[1]
    expectations = {
        "AB": (AB_PATH, "# 秦至北宋第三项A/B国防安全正式结算", "A/B总分/160"),
        "C": (C_PATH, "# 秦至北宋第三项C军事体系有效性正式结算", "C/50"),
        "D": (D_PATH, "# 秦至北宋第三项D军事成本收益比正式结算", "D/40"),
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
        assert "所有分值统一显示一位小数" in rendered
        assert "| 李世民 | 唐 |" in rendered
        assert "| 柴荣 | 后周 |" in rendered
        assert "| 赵恒 | 北宋 |" in rendered
        table_lines = [line for line in rendered.splitlines() if line.startswith("|")]
        assert len(table_lines) == 120
        assert "结算依据" not in table_lines[0]
        column_count = len(table_lines[0].split("|"))
        assert all(len(line.split("|")) == column_count for line in table_lines)
        assert rendered.count("\n### ") == 118
        assert ". 赵恒（" in rendered
        if kind == "C":
            assert "置信度" not in rendered
            assert all("confidence" not in row for row in payload["records"])
        if kind == "D":
            assert "| 实质周期 | 高收益 | 相称收益 | 低收益 | 负收益 | 回报未知 | 重大高收益 | 顶尖高收益 | 国家级负收益 |" in rendered
            assert "| 柴荣 | 后周 | 954-959 | D-3 | 28.1 | 充分检验 | 6 | 4 | 1 | 0 | 1 | 0 | 2 | 0 | 1 |" in rendered
            assert "| 李世民 | 唐 | 626-649 | D-4 | 35.1 | 充分检验 | 8 | 4 | 3 | 0 | 1 | 0 | 3 | 2 | 0 |" in rendered
            assert all(
                len(
                    (row.get("D_portfolio_metrics") or {}).get(
                        "material_negative_return_refs"
                    )
                    or []
                )
                <= 1
                for row in payload["records"]
                if row.get("D_grade") in {"D-4", "D-5"}
            )
            broken = deepcopy(payload["records"])
            del broken[0]["D_portfolio_metrics"]["material_return_class_counts"]
            with pytest.raises(ValueError, match="缺少实质周期回报分布"):
                _render_formal_markdown("D", broken)

    combined_payload = json.loads((repo_root / FORMAL_PATH).read_text(encoding="utf-8"))
    combined_rendered = _render_combined_markdown(combined_payload["records"])
    assert (
        repo_root / FORMAL_PATH.with_suffix(".md")
    ).read_text(encoding="utf-8") == combined_rendered
    assert "结算依据" in combined_rendered
    assert "A1-2→A1-4" in combined_rendered
    assert "C为C1-3／C2-3／C3-3→C-3" in combined_rendered
    combined_table_lines = [
        line for line in combined_rendered.splitlines() if line.startswith("|")
    ]
    assert "结算依据" not in combined_table_lines[0]
    assert combined_rendered.count("\n### ") == 118


def test_high_grade_gates_require_major_or_top_tier_counterevidence() -> None:
    from emperor_v4.evaluation.five_dynasties_third_item import (
        _apply_c_major_victory_gate,
        _axis_numbers,
        _d_grade_and_score,
        _qin_tang_subject_axis_lines,
    )

    assert _axis_numbers("P3估；上限约P4。", "P") == [3]
    selected, basis = _qin_tang_subject_axis_lines(
        ["战争成本影子定位（北齐）：P4/S0/M3/A3"], "萧绎", "梁"
    )
    assert selected == []
    assert basis == "NO_SUBJECT_AXIS_LINE"

    c_row = {
        "combat_delivery_grade": "C1-4",
        "operational_sustainability_cap": "C2-4",
        "system_reliability_cap": "C3-4",
        "C_overall_grade": "C-4",
        "C_score_rate": 75.0,
        "C_score_points": 37.5,
        "C_score_support_surplus": 0,
        "C_score_band": {"lower_rate": 75, "upper_rate": 89},
        "major_system_failure_refs": ["FAIL"],
        "major_system_success_refs": [],
        "cap_reasons": [],
    }
    _apply_c_major_victory_gate(c_row)
    assert c_row["C_overall_grade"] == "C-3"
    assert c_row["major_victory_gate"]["status"] == "CAPPED_TO_C3"

    def cycle(ref: str, return_class: str, *, national: bool = False, top: bool = False) -> dict:
        return {
            "campaign_group_ref": ref,
            "return_class": return_class,
            "material": True,
            "unknown_axes": [],
            "national_negative": national,
            "major_high_return": return_class == "HIGH_RETURN",
            "top_high_return": top,
        }

    portfolio = [
        cycle("N", "NEGATIVE_RETURN", national=True),
        cycle("H1", "HIGH_RETURN"),
        cycle("H2", "HIGH_RETURN"),
        cycle("R1", "PROPORTIONATE_RETURN"),
        cycle("R2", "PROPORTIONATE_RETURN"),
        cycle("R3", "PROPORTIONATE_RETURN"),
    ]
    grade, _, metrics = _d_grade_and_score(
        portfolio, allow_exceptional_national_recovery=True
    )
    assert grade == "D-3"
    assert metrics["exceptional_national_recovery_gate"] == "NOT_APPLICABLE"
    portfolio[1]["top_high_return"] = True
    grade, _, metrics = _d_grade_and_score(
        portfolio, allow_exceptional_national_recovery=True
    )
    assert grade == "D-4"
    assert metrics["exceptional_national_recovery_gate"] == "PASSED_STRONG_COUNTEREVIDENCE"


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
    c_by_id = {row["ruler_id"]: row for row in c_rows}
    for row in d_rows:
        excluded = set(row.get("excluded_unification_cycle_refs") or [])
        if excluded:
            assert not excluded & set(
                c_by_id[row["ruler_id"]].get("independent_task_groups") or []
            )


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
