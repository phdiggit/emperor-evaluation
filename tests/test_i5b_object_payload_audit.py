from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import i5b_object_payload_audit as tool


def valid_payload() -> dict:
    return {
        "item_code": "I5B",
        "subitem": "第五项B",
        "emperor": {
            "period": "唐",
            "name": "李世民",
            "title": "唐太宗",
            "note": "唐朝第二位皇帝，贞观时期用人纳谏材料较多。",
        },
        "sources": [
            {
                "src_key": "SRC-JTS-FANGXUANLING",
                "title": "旧唐书",
                "author": "刘昫等",
                "dynasty": "后晋",
                "volume": "卷六十六",
                "locator": "房玄龄传",
                "url": "https://example.invalid/jts66",
                "note": "房玄龄辅佐太宗处理政务的传记材料。",
            }
        ],
        "objects": [
            {
                "obj_type": "person",
                "period": "唐",
                "name": "房玄龄",
                "note": "唐初宰相，长期参与贞观政务与制度建设。",
                "links": [
                    {
                        "src_key": "SRC-JTS-FANGXUANLING",
                        "rule_code": "team_building",
                        "direction": "positive",
                        "note": "材料说明房玄龄长期辅政，可作为团队建设与核心臣僚材料。",
                    }
                ],
                "attrs": [
                    {
                        "attr_code": "talent_quality",
                        "src_key": "SRC-JTS-FANGXUANLING",
                        "value_text": "顶级人才",
                        "confidence": 0.9,
                        "note": "房玄龄为贞观核心宰相，人才质量高。",
                    }
                ],
            }
        ],
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_audit_payload_file_accepts_payload_without_todo(tmp_path: Path) -> None:
    path = tmp_path / "payload.json"
    write_json(path, valid_payload())

    report = tool.audit_payload_file(path)

    assert report["ok"] is True
    assert report["block_count"] == 0
    assert report["payloads"][0]["todo_counts"]["TODO"] == 0


def test_audit_payload_file_blocks_todo_markers(tmp_path: Path) -> None:
    path = tmp_path / "payload.json"
    payload = valid_payload()
    payload["objects"][0]["links"][0]["rule_code"] = "TODO_RULE_CODE"
    payload["objects"][0]["attrs"][0]["value_text"] = "TODO_TALENT_QUALITY"
    write_json(path, payload)

    report = tool.audit_payload_file(path)

    assert report["ok"] is False
    assert any(issue["code"] == "todo_marker_present" for issue in report["issues"])
    counts = report["payloads"][0]["todo_counts"]
    assert counts["TODO_RULE_CODE"] == 1
    assert counts["TODO_TALENT_QUALITY"] == 1


def test_audit_payload_file_reports_importer_schema_error(tmp_path: Path) -> None:
    path = tmp_path / "payload.json"
    payload = valid_payload()
    payload["objects"][0]["links"] = []
    write_json(path, payload)

    report = tool.audit_payload_file(path)

    assert report["ok"] is False
    assert any(issue["code"] == "payload_schema_error" for issue in report["issues"])


def test_cli_writes_markdown_and_fails_on_block(tmp_path: Path) -> None:
    path = tmp_path / "payload.json"
    output = tmp_path / "audit.md"
    payload = valid_payload()
    payload["objects"][0]["note"] = "TODO: 待补。"
    write_json(path, payload)

    exit_code = tool.main(["--input", str(path), "--format", "markdown", "--output", str(output), "--fail-on-block"])

    assert exit_code == 1
    text = output.read_text(encoding="utf-8")
    assert text.startswith("# I5B object payload audit")
    assert "todo_marker_present" in text
