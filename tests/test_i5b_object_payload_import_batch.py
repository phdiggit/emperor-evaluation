from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import i5b_object_payload_import_batch as tool


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
                "attrs": [],
            }
        ],
    }


def write_control_board(path: Path, candidates: list[Path]) -> None:
    write_json(
        path,
        {
            "schema_version": 1,
            "summary": {"ok": True, "blocked": 0},
            "ready_for_import_payloads": [str(candidate) for candidate in candidates],
        },
    )


def test_import_batch_skips_receipted_payload_and_appends_new_receipt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    write_json(first, valid_payload("甲"))
    write_json(second, valid_payload("乙"))
    board = tmp_path / "board.json"
    write_control_board(board, [first, second])
    receipt_log = tmp_path / "receipts.jsonl"
    receipt_log.write_text(
        json.dumps(
            {
                "person": "甲",
                "payload_sha256": tool.payload_sha256(first),
                "dry_run": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    imported_people: list[str] = []

    def fake_import_payloads(payloads, dsn: str, *, dry_run: bool = False):
        assert dsn == "postgres://example"
        assert dry_run is False
        imported_people.extend(payload.emperor.name for payload in payloads)
        return {
            "dry_run": dry_run,
            "payloads": [
                {
                    "emperor": {"name": payload.emperor.name, "id": index + 1},
                    "counts": {"sources": 1, "objects": 1, "obj_srcs": 1, "obj_attrs": 0},
                }
                for index, payload in enumerate(payloads)
            ],
            "unsourced": [],
        }

    monkeypatch.setattr(tool.importer, "resolve_dsn", lambda env_name: "postgres://example")
    monkeypatch.setattr(tool.importer, "import_payloads", fake_import_payloads)

    report = tool.import_ready_payloads(
        control_board=board,
        receipt_log=receipt_log,
        dsn_env="TEST_DSN",
        dry_run=False,
    )

    assert imported_people == ["乙"]
    assert report["ready_count"] == 2
    assert report["pending_count"] == 1
    assert report["imported_count"] == 1
    assert report["skipped"][0]["person"] == "甲"
    assert report["skipped"][0]["reason"] == "already_imported"
    receipt_rows = [json.loads(line) for line in receipt_log.read_text(encoding="utf-8").splitlines()]
    assert [row["person"] for row in receipt_rows] == ["甲", "乙"]
    assert receipt_rows[1]["import_report"]["counts"]["objects"] == 1


def test_import_batch_dry_run_does_not_write_receipt(tmp_path: Path, monkeypatch) -> None:
    candidate = tmp_path / "candidate.json"
    write_json(candidate, valid_payload("甲"))
    board = tmp_path / "board.json"
    write_control_board(board, [candidate])
    receipt_log = tmp_path / "receipts.jsonl"

    monkeypatch.setattr(tool.importer, "resolve_dsn", lambda env_name: "postgres://example")
    monkeypatch.setattr(
        tool.importer,
        "import_payloads",
        lambda payloads, dsn, *, dry_run=False: {
            "dry_run": dry_run,
            "payloads": [{"counts": {"sources": 1, "objects": 1, "obj_srcs": 1, "obj_attrs": 0}}],
            "unsourced": [],
        },
    )

    report = tool.import_ready_payloads(
        control_board=board,
        receipt_log=receipt_log,
        dsn_env="TEST_DSN",
        dry_run=True,
    )

    assert report["dry_run"] is True
    assert report["imported_count"] == 1
    assert not receipt_log.exists()
