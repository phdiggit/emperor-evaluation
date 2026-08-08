from __future__ import annotations

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
        or path.endswith(".battle-adjudications.json")
        or "战役成本收益补证-" in path
    ]
    assert forbidden == []

    for local_cache_path in (
        ".cache/source-text/测试史料/卷001.md",
        "docs/原始史料/测试史料/卷001.md",
    ):
        ignored = subprocess.run(
            ["git", "check-ignore", "--quiet", "--no-index", local_cache_path],
            cwd=repo_root,
            check=False,
        )
        assert ignored.returncode == 0


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
