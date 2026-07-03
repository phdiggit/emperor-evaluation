from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import i5b_source_pack_handoff as tool


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def write_pack(root: Path, name: str = "pack-a") -> Path:
    pack = root / name
    (pack / "pages").mkdir(parents=True)
    write_json(
        pack / "manifest.json",
        {
            "schema_version": 1,
            "pack_id": name,
            "created_at": "2026-07-03T00:00:00+08:00",
            "source_scope": "fixture",
            "status": "complete",
        },
    )
    (pack / "pages" / "a.txt").write_text("史料正文", encoding="utf-8")
    write_jsonl(
        pack / "src_docs.jsonl",
        [
            {
                "src_key": "SRC-A",
                "page_title": "史記/卷001",
                "title": "史记",
                "author": "司马迁",
                "dynasty": "西汉",
                "locator": "史記/卷001",
                "url": "https://zh.wikisource.org/zh-hans/史記/卷001",
                "text_path": "pages/a.txt",
                "fetch_status": "fetched",
                "review_status": "pending",
            }
        ],
    )
    write_jsonl(pack / "excerpts.jsonl", [])
    return pack


def init_batch(tmp_path: Path, *, persons: list[str] | None = None, workflow_code: str = "I5B", batch_id: str = "batch01") -> Path:
    return tool.init_handoff(
        handoff_root=tmp_path / "handoffs",
        batch_id=batch_id,
        persons=persons or ["甲"],
        owner="codex-a",
        workflow_code=workflow_code,
    )


def test_init_handoff_writes_contract_files(tmp_path: Path) -> None:
    handoff = init_batch(tmp_path, persons=["甲", "乙"])

    assert (handoff / "manifest.json").exists()
    assert (handoff / "acceptance.md").exists()
    manifest = json.loads((handoff / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["persons"] == ["甲", "乙"]
    assert manifest["workflow_code"] == "I5B"
    assert manifest["contract"] == "i5b_source_pack_handoff_v1"


def test_validate_handoff_accepts_ready_pack(tmp_path: Path) -> None:
    pack_root = tmp_path / "source-packs"
    write_pack(pack_root)
    handoff = init_batch(tmp_path)
    write_jsonl(
        handoff / "accepted_packs.jsonl",
        [
            {
                "person": "甲",
                "accepted_pack_path": "pack-a",
                "acceptance_status": "accepted",
                "usable_for_object_pool": True,
                "gap_summary": "暂无阻断缺口",
                "review_note": "可进入摘录池",
            }
        ],
    )
    write_jsonl(handoff / "next_stage_queue.jsonl", [{"person": "甲", "accepted_pack_path": "pack-a", "stage": "source_excerpt_pool", "ready": True}])

    report = tool.build_report(tmp_path / "handoffs", source_pack_root=pack_root)

    assert report["ok"] is True
    assert report["workflow_code"] == "I5B"
    assert report["ready_people"] == ["甲"]
    assert report["ready_queue"][0]["person"] == "甲"
    assert report["ready_queue"][0]["batch_id"] == "batch01"
    assert report["ready_queue"][0]["stage"] == "source_excerpt_pool"
    assert report["needs_more_profile_work"] == []
    assert report["batches"][0]["pack_audits"]["甲"]["ok"] is True


def test_validate_handoff_maps_server_absolute_pack_path_to_local_root(tmp_path: Path) -> None:
    pack_root = tmp_path / "source-packs"
    write_pack(pack_root)
    handoff = init_batch(tmp_path)
    server_pack_path = "/data2/backups/code/emperor-evaluation/source-packs/pack-a"
    write_jsonl(
        handoff / "accepted_packs.jsonl",
        [
            {
                "person": "甲",
                "accepted_pack_path": server_pack_path,
                "acceptance_status": "accepted",
                "usable_for_object_pool": True,
            }
        ],
    )
    write_jsonl(handoff / "next_stage_queue.jsonl", [{"person": "甲", "accepted_pack_path": server_pack_path, "stage": "source_excerpt_pool", "ready": True}])

    report = tool.build_report(tmp_path / "handoffs", source_pack_root=pack_root)

    assert report["ok"] is True
    assert report["ready_people"] == ["甲"]
    assert report["batches"][0]["pack_audits"]["甲"]["pack_path"] == str(pack_root / "pack-a")


def test_validate_handoff_blocks_next_stage_pack_mismatch_and_duplicate_queue(tmp_path: Path) -> None:
    pack_root = tmp_path / "source-packs"
    write_pack(pack_root, "pack-a")
    write_pack(pack_root, "pack-b")
    handoff = init_batch(tmp_path)
    write_jsonl(
        handoff / "accepted_packs.jsonl",
        [{"person": "甲", "accepted_pack_path": "pack-a", "acceptance_status": "accepted", "usable_for_object_pool": True}],
    )
    write_jsonl(
        handoff / "next_stage_queue.jsonl",
        [
            {"person": "甲", "accepted_pack_path": "pack-b", "stage": "source_excerpt_pool", "ready": True},
            {"person": "甲", "accepted_pack_path": "pack-b", "stage": "source_excerpt_pool", "ready": True},
        ],
    )

    report = tool.build_report(tmp_path / "handoffs", source_pack_root=pack_root)

    assert report["ok"] is False
    issue_codes = {issue["code"] for issue in report["batches"][0]["issues"]}
    assert "duplicate_next_stage_queue" in issue_codes
    assert "next_stage_pack_mismatch" in issue_codes


def test_validate_handoff_blocks_missing_accepted_pack(tmp_path: Path) -> None:
    handoff = init_batch(tmp_path)
    write_jsonl(
        handoff / "accepted_packs.jsonl",
        [{"person": "甲", "accepted_pack_path": "missing", "acceptance_status": "accepted", "usable_for_object_pool": True}],
    )
    write_jsonl(handoff / "next_stage_queue.jsonl", [{"person": "甲", "accepted_pack_path": "missing", "stage": "source_excerpt_pool", "ready": True}])

    report = tool.build_report(tmp_path / "handoffs", source_pack_root=tmp_path / "source-packs")

    assert report["ok"] is False
    assert any(issue["code"] == "accepted_pack_missing" for issue in report["batches"][0]["issues"])


def test_validate_handoff_blocks_not_ready_person_in_next_stage(tmp_path: Path) -> None:
    handoff = init_batch(tmp_path)
    write_jsonl(
        handoff / "accepted_packs.jsonl",
        [{"person": "甲", "accepted_pack_path": "", "acceptance_status": "needs_more_profile_work", "usable_for_object_pool": False}],
    )
    write_jsonl(handoff / "next_stage_queue.jsonl", [{"person": "甲", "accepted_pack_path": "", "stage": "source_excerpt_pool", "ready": True}])

    report = tool.build_report(tmp_path / "handoffs")

    assert report["ok"] is False
    assert any(issue["code"] == "not_ready_person_in_next_stage" for issue in report["batches"][0]["issues"])


def test_validate_handoff_blocks_ready_person_with_blocking_gap(tmp_path: Path) -> None:
    pack_root = tmp_path / "source-packs"
    write_pack(pack_root)
    handoff = init_batch(tmp_path)
    write_jsonl(
        handoff / "accepted_packs.jsonl",
        [{"person": "甲", "accepted_pack_path": "pack-a", "acceptance_status": "accepted_with_known_gaps", "usable_for_object_pool": True}],
    )
    write_jsonl(handoff / "unresolved_gaps.jsonl", [{"person": "甲", "object_name": "张三", "gap_type": "without_page_hits", "decision": "needs_profile_patch"}])
    write_jsonl(handoff / "next_stage_queue.jsonl", [{"person": "甲", "accepted_pack_path": "pack-a", "stage": "source_excerpt_pool", "ready": True}])

    report = tool.build_report(tmp_path / "handoffs", source_pack_root=pack_root)

    assert report["ok"] is False
    assert any(issue["code"] == "ready_person_has_blocking_gaps" for issue in report["batches"][0]["issues"])


def test_validate_handoff_accepts_workflow_neutral_gap_decision(tmp_path: Path) -> None:
    pack_root = tmp_path / "source-packs"
    write_pack(pack_root)
    handoff = init_batch(tmp_path)
    write_jsonl(
        handoff / "accepted_packs.jsonl",
        [{"person": "甲", "accepted_pack_path": "pack-a", "acceptance_status": "accepted_with_known_gaps", "usable_for_object_pool": True}],
    )
    write_jsonl(handoff / "unresolved_gaps.jsonl", [{"person": "甲", "object_name": "张三", "gap_type": "without_page_hits", "decision": "out_of_source_scope"}])
    write_jsonl(handoff / "next_stage_queue.jsonl", [{"person": "甲", "accepted_pack_path": "pack-a", "stage": "source_excerpt_pool", "ready": True}])

    report = tool.build_report(tmp_path / "handoffs", source_pack_root=pack_root)

    assert report["ok"] is True
    assert report["warning_count"] == 0


def test_validate_handoff_warns_for_legacy_i5b_gap_decision(tmp_path: Path) -> None:
    pack_root = tmp_path / "source-packs"
    write_pack(pack_root)
    handoff = init_batch(tmp_path)
    write_jsonl(
        handoff / "accepted_packs.jsonl",
        [{"person": "甲", "accepted_pack_path": "pack-a", "acceptance_status": "accepted_with_known_gaps", "usable_for_object_pool": True}],
    )
    write_jsonl(handoff / "unresolved_gaps.jsonl", [{"person": "甲", "object_name": "张三", "gap_type": "without_page_hits", "decision": "not_i5b_main"}])
    write_jsonl(handoff / "next_stage_queue.jsonl", [{"person": "甲", "accepted_pack_path": "pack-a", "stage": "source_excerpt_pool", "ready": True}])

    report = tool.build_report(tmp_path / "handoffs", source_pack_root=pack_root)

    assert report["ok"] is True
    assert report["warning_count"] == 1
    assert any(issue["code"] == "legacy_gap_decision" for issue in report["batches"][0]["issues"])


def test_handoff_accepts_non_i5b_workflow_metadata(tmp_path: Path) -> None:
    handoff = init_batch(tmp_path, workflow_code="I5A")

    manifest = json.loads((handoff / "manifest.json").read_text(encoding="utf-8"))
    acceptance = (handoff / "acceptance.md").read_text(encoding="utf-8")
    report = tool.build_report(tmp_path / "handoffs", audit_packs=False, workflow_code="I5A")
    text = tool.render_markdown(report)

    assert manifest["workflow_code"] == "I5A"
    assert manifest["contract"] == "i5a_source_pack_handoff_v1"
    assert acceptance.startswith("# I5A source pack batch acceptance")
    assert report["workflow_code"] == "I5A"
    assert text.startswith("# I5A source pack handoff validation")
    assert "- workflow_code: `I5A`" in text


def test_build_report_filters_batches_by_workflow_code_and_tracks_needs_work(tmp_path: Path) -> None:
    i5b = init_batch(tmp_path, batch_id="i5b_batch")
    write_jsonl(
        i5b / "accepted_packs.jsonl",
        [{"person": "甲", "accepted_pack_path": "", "acceptance_status": "needs_more_profile_work", "usable_for_object_pool": False}],
    )
    i5a = init_batch(tmp_path, workflow_code="I5A", batch_id="i5a_batch")
    write_jsonl(
        i5a / "accepted_packs.jsonl",
        [{"person": "甲", "accepted_pack_path": "", "acceptance_status": "blocked", "usable_for_object_pool": False}],
    )

    report = tool.build_report(tmp_path / "handoffs", audit_packs=False, workflow_code="I5B")

    assert report["batch_count"] == 1
    assert report["skipped_batch_count"] == 1
    assert report["batches"][0]["batch_id"] == "i5b_batch"
    assert report["needs_more_profile_work"][0]["person"] == "甲"
    assert report["needs_more_profile_work"][0]["batch_id"] == "i5b_batch"
