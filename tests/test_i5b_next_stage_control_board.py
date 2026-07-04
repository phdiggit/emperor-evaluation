from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import i5b_next_stage_control_board as tool


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_next_stage_report(path: Path, people: list[str]) -> None:
    write_json(
        path,
        {
            "ok": True,
            "items": [
                {
                    "person": person,
                    "batch_id": "batch-a",
                    "status": "ok",
                    "accepted_pack_path": f"source-packs/{person}",
                    "excerpt_output": str(path.parent / person / "source_excerpt_pool.json"),
                    "payload_output": str(path.parent / person / "object_payload_skeleton.json"),
                }
                for person in people
            ],
        },
    )


def valid_payload(person: str) -> dict:
    return {
        "item_code": "I5B",
        "subitem": "第五项B",
        "emperor": {
            "period": "唐",
            "name": person,
            "title": f"{person}测试称号",
            "note": "测试人物说明。",
        },
        "sources": [
            {
                "src_key": f"SRC-{person}-001",
                "title": "旧唐书",
                "author": "刘昫等",
                "dynasty": "后晋",
                "volume": "卷一",
                "locator": "测试传",
                "url": "https://example.invalid/source",
                "note": "可回源的测试史料。",
            }
        ],
        "objects": [
            {
                "obj_type": "person",
                "period": "唐",
                "name": f"{person}对象",
                "note": "测试对象说明。",
                "links": [
                    {
                        "src_key": f"SRC-{person}-001",
                        "rule_code": "team_building",
                        "direction": "positive",
                        "note": "史料说明该对象可以承载团队建设方向。",
                    }
                ],
                "attrs": [
                    {
                        "attr_code": "talent_quality",
                        "src_key": f"SRC-{person}-001",
                        "value_text": "重要人才",
                        "confidence": 0.8,
                        "note": "测试属性说明。",
                    }
                ],
            }
        ],
    }


def write_candidate(root: Path, worker: str, person: str, *, todo: bool = False, review: bool = True) -> Path:
    person_dir = root / worker / person
    payload = valid_payload(person)
    if todo:
        payload["objects"][0]["links"][0]["rule_code"] = "TODO_RULE_CODE"
    path = person_dir / "object_payload_candidate.json"
    write_json(path, payload)
    if review:
        (person_dir / "review_report.md").write_text(f"# {person}\n\nreviewed\n", encoding="utf-8")
    return path


def test_control_board_maps_ready_payloads_and_missing_worker_assignments(tmp_path: Path) -> None:
    report_path = tmp_path / "next-stage.json"
    candidate_root = tmp_path / "candidates"
    write_next_stage_report(report_path, ["甲", "乙"])
    ready_candidate = write_candidate(candidate_root, "object-payload-01", "甲")

    board = tool.build_control_board(
        next_stage_report=report_path,
        handoff_root=tmp_path / "handoffs",
        source_pack_root=tmp_path / "source-packs",
        profile_path=tmp_path / "profiles.jsonl",
        next_stage_output_root=tmp_path / "next-stage",
        candidate_root=candidate_root,
        worker_count=2,
        assignment_run_id="run-test",
    )

    assert board["summary"]["ok"] is True
    assert board["summary"]["complete"] is False
    assert board["summary"]["ready_for_import_dry_run"] == 1
    assert board["summary"]["needs_object_payload_worker"] == 1
    assert board["ready_for_import_payloads"] == [str(ready_candidate)]
    missing = board["missing_people"][0]
    assert missing["person"] == "乙"
    assignment = board["agent_plan"]["assignments"][0]
    assert assignment["people"][0]["person"] == "乙"
    assert "object_payload_candidate.json" in assignment["audit_command"]
    assert assignment["target_dir"].endswith("assignments\\run-test\\object-payload-01") or assignment["target_dir"].endswith(
        "assignments/run-test/object-payload-01"
    )


def test_control_board_blocks_duplicate_candidate_payloads(tmp_path: Path) -> None:
    report_path = tmp_path / "next-stage.json"
    candidate_root = tmp_path / "candidates"
    write_next_stage_report(report_path, ["甲"])
    write_candidate(candidate_root, "object-payload-01", "甲")
    write_candidate(candidate_root, "object-payload-02", "甲")

    board = tool.build_control_board(
        next_stage_report=report_path,
        handoff_root=tmp_path / "handoffs",
        source_pack_root=tmp_path / "source-packs",
        profile_path=tmp_path / "profiles.jsonl",
        next_stage_output_root=tmp_path / "next-stage",
        candidate_root=candidate_root,
        assignment_run_id="run-test",
    )

    assert board["summary"]["ok"] is False
    assert board["summary"]["blocked"] == 1
    assert board["blocked_people"][0]["status"] == "blocked_duplicate_candidate"


def test_control_board_filters_loaded_next_stage_report(tmp_path: Path) -> None:
    report_path = tmp_path / "next-stage.json"
    candidate_root = tmp_path / "candidates"
    write_next_stage_report(report_path, ["甲", "乙", "丙"])

    board = tool.build_control_board(
        next_stage_report=report_path,
        handoff_root=tmp_path / "handoffs",
        source_pack_root=tmp_path / "source-packs",
        profile_path=tmp_path / "profiles.jsonl",
        next_stage_output_root=tmp_path / "next-stage",
        candidate_root=candidate_root,
        people={"甲", "乙", "丙"},
        exclude_people={"乙"},
        assignment_run_id="run-test",
    )

    assert [row["person"] for row in board["people"]] == ["甲", "丙"]
    assert board["summary"]["queue_count"] == 2


def test_cli_writes_markdown_and_fails_on_payload_block(tmp_path: Path) -> None:
    report_path = tmp_path / "next-stage.json"
    candidate_root = tmp_path / "candidates"
    output = tmp_path / "board.md"
    write_next_stage_report(report_path, ["甲"])
    write_candidate(candidate_root, "object-payload-01", "甲", todo=True)

    exit_code = tool.main(
        [
            "--next-stage-report",
            str(report_path),
            "--candidate-root",
            str(candidate_root),
            "--output",
            str(output),
            "--assignment-run-id",
            "run-test",
            "--fail-on-block",
        ]
    )

    assert exit_code == 1
    text = output.read_text(encoding="utf-8")
    assert text.startswith("# I5B next-stage control board")
    assert "blocked_payload_audit" in text
    assert "todo_marker_present" in text
