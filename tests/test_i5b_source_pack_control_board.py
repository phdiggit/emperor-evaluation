from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import i5b_source_pack_control_board as tool
from scripts.dev import i5b_source_pack_handoff


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def init_batch(tmp_path: Path, batch_id: str, persons: list[str]) -> Path:
    return i5b_source_pack_handoff.init_handoff(
        handoff_root=tmp_path / "handoffs",
        batch_id=batch_id,
        persons=persons,
        owner="codex-worker",
    )


def test_control_board_builds_agent_plan_from_handoffs(tmp_path: Path) -> None:
    batch_a = init_batch(tmp_path, "batch-a", ["甲", "乙", "丙"])
    batch_b = init_batch(tmp_path, "batch-b", ["丁"])
    (tmp_path / "source-packs" / "pack-a").mkdir(parents=True)
    write_jsonl(
        batch_a / "accepted_packs.jsonl",
        [
            {
                "person": "甲",
                "accepted_pack_path": "pack-a",
                "acceptance_status": "accepted",
                "usable_for_object_pool": True,
            },
            {
                "person": "乙",
                "accepted_pack_path": "",
                "acceptance_status": "needs_more_profile_work",
                "usable_for_object_pool": False,
                "gap_summary": "缺核心对象",
            },
            {
                "person": "丙",
                "accepted_pack_path": "",
                "acceptance_status": "needs_more_profile_work",
                "usable_for_object_pool": False,
            },
        ],
    )
    write_jsonl(
        batch_a / "next_stage_queue.jsonl",
        [{"person": "甲", "accepted_pack_path": "pack-a", "stage": "source_excerpt_pool", "ready": True}],
    )
    write_jsonl(
        batch_b / "accepted_packs.jsonl",
        [{"person": "丁", "accepted_pack_path": "", "acceptance_status": "blocked", "usable_for_object_pool": False}],
    )

    board = tool.build_control_board(
        handoff_root=tmp_path / "handoffs",
        source_pack_root=tmp_path / "source-packs",
        audit_packs=False,
        include_status=False,
        source_pack_agents=2,
        next_stage_agents=1,
    )

    assert board["handoff_summary"]["ok"] is True
    assert [row["person"] for row in board["ready_queue"]] == ["甲"]
    assert [row["person"] for row in board["source_pack_followup_queue"]] == ["乙", "丙"]
    assert [row["person"] for row in board["blocked_queue"]] == ["丁"]
    plan = board["agent_plan"]
    assert plan["recommended_concurrency"] == 2
    assert plan["handoff_ready_release"] is True
    assert [item["people"] for item in plan["source_pack_followup_agents"]] == [["乙", "丙"]]
    assert plan["next_stage_agents"][0]["people"] == ["甲"]
    assert plan["blocked_people"] == ["丁"]


def test_control_board_does_not_release_ready_queue_when_handoff_has_block(tmp_path: Path) -> None:
    batch = init_batch(tmp_path, "batch-a", ["甲"])
    write_jsonl(
        batch / "accepted_packs.jsonl",
        [{"person": "甲", "accepted_pack_path": "missing-pack", "acceptance_status": "accepted", "usable_for_object_pool": True}],
    )
    write_jsonl(
        batch / "next_stage_queue.jsonl",
        [{"person": "甲", "accepted_pack_path": "missing-pack", "stage": "source_excerpt_pool", "ready": True}],
    )

    board = tool.build_control_board(
        handoff_root=tmp_path / "handoffs",
        source_pack_root=tmp_path / "source-packs",
        audit_packs=True,
        include_status=False,
    )

    assert board["handoff_summary"]["ok"] is False
    assert board["handoff_summary"]["blocks"] > 0
    assert [row["person"] for row in board["ready_queue"]] == ["甲"]
    assert board["agent_plan"]["handoff_ready_release"] is False
    assert board["agent_plan"]["next_stage_agents"] == []


def test_control_board_cli_writes_markdown(tmp_path: Path) -> None:
    batch = init_batch(tmp_path, "batch-a", ["甲"])
    write_jsonl(
        batch / "accepted_packs.jsonl",
        [{"person": "甲", "accepted_pack_path": "", "acceptance_status": "needs_more_profile_work", "usable_for_object_pool": False}],
    )
    output = tmp_path / "board.md"

    exit_code = tool.main(
        [
            "--handoff-root",
            str(tmp_path / "handoffs"),
            "--no-audit-packs",
            "--no-status",
            "--output",
            str(output),
        ]
    )

    text = output.read_text(encoding="utf-8")
    assert exit_code == 0
    assert text.startswith("# I5B source pack control board")
    assert "`source-pack-followup-01`: 甲" in text
