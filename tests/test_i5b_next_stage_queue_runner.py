from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from scripts.dev import i5b_source_pack_handoff as handoff_tool


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "i5b_next_stage_queue_runner.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_next_stage_queue_runner_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + ("\n" if rows else ""), encoding="utf-8")


def write_profile(path: Path) -> None:
    write_jsonl(
        path,
        [
            {
                "person": "武则天",
                "workflow_code": "I5B",
                "query_profile_id": "QRY-WZT",
                "source_targets": ["旧唐书/卷109"],
                "object_layers": {
                    "core_positive_objects": ["姚崇"],
                    "negative_or_reversal_objects": ["来俊臣"],
                },
                "query_bundles": ["武则天 姚崇 旧唐书 任用", "武则天 来俊臣 旧唐书 酷吏"],
            }
        ],
    )


def write_pack(root: Path) -> Path:
    pack = root / "wuzetian-pack"
    (pack / "pages").mkdir(parents=True)
    write_json(
        pack / "manifest.json",
        {
            "schema_version": 1,
            "pack_id": "I5B-WZT-PACK",
            "workflow_code": "I5B",
            "created_at": "2026-07-03T00:00:00+08:00",
            "source_scope": "fixture",
            "status": "complete",
        },
    )
    (pack / "pages" / "jts109.txt").write_text("武则天任用姚崇，又有来俊臣用事。", encoding="utf-8")
    write_jsonl(
        pack / "src_docs.jsonl",
        [
            {
                "src_key": "SRC-JTS-109",
                "page_title": "旧唐书/卷109",
                "title": "旧唐书",
                "author": "刘昫等",
                "dynasty": "后晋",
                "locator": "旧唐书/卷109",
                "url": "https://zh.wikisource.org/zh-hans/旧唐书/卷109",
                "text_path": "pages/jts109.txt",
                "fetch_status": "cached",
                "review_status": "pending",
            }
        ],
    )
    write_jsonl(pack / "excerpts.jsonl", [])
    return pack


def write_ready_handoff(root: Path, pack: Path) -> Path:
    handoff = handoff_tool.init_handoff(
        handoff_root=root / "handoffs",
        batch_id="batch01",
        persons=["武则天"],
        owner="codex-batch",
        workflow_code="I5B",
    )
    write_jsonl(
        handoff / "accepted_packs.jsonl",
        [
            {
                "person": "武则天",
                "acceptance_status": "accepted",
                "usable_for_object_pool": True,
                "accepted_pack_path": pack.name,
            }
        ],
    )
    write_jsonl(handoff / "next_stage_queue.jsonl", [{"person": "武则天", "stage": "source_excerpt_pool", "ready": True, "accepted_pack_path": pack.name}])
    return handoff


def test_run_queue_generates_excerpt_and_payload_skeleton(tmp_path: Path) -> None:
    tool = load_tool()
    profile = tmp_path / "profiles.jsonl"
    pack_root = tmp_path / "source-packs"
    output_root = tmp_path / "out"
    write_profile(profile)
    pack = write_pack(pack_root)
    write_ready_handoff(tmp_path, pack)

    report = tool.run_queue(
        workflow_code="I5B",
        handoff_root=tmp_path / "handoffs",
        source_pack_root=pack_root,
        profile_path=profile,
        output_root=output_root,
    )

    assert report["ok"] is True
    assert report["queue_count"] == 1
    item = report["items"][0]
    assert item["person"] == "武则天"
    assert item["status"] == "ok"
    assert item["excerpt_count"] >= 1
    assert item["object_count"] == 2
    assert item["todo_markers"] > 0
    payload = json.loads(Path(item["payload_output"]).read_text(encoding="utf-8"))
    assert payload["review"]["excerpt_status"] == "offline_source_pack"
    assert {source["title"] for source in payload["sources"]} >= {"旧唐书"}


def test_run_queue_stops_when_handoff_validation_blocks(tmp_path: Path) -> None:
    tool = load_tool()
    profile = tmp_path / "profiles.jsonl"
    pack_root = tmp_path / "source-packs"
    write_profile(profile)
    handoff = handoff_tool.init_handoff(
        handoff_root=tmp_path / "handoffs",
        batch_id="batch01",
        persons=["武则天"],
        owner="codex-batch",
        workflow_code="I5B",
    )
    write_jsonl(handoff / "next_stage_queue.jsonl", [{"person": "武则天", "stage": "source_excerpt_pool", "ready": True, "accepted_pack_path": "missing"}])

    report = tool.run_queue(
        workflow_code="I5B",
        handoff_root=tmp_path / "handoffs",
        source_pack_root=pack_root,
        profile_path=profile,
        output_root=tmp_path / "out",
    )

    assert report["ok"] is False
    assert report["items"] == []
    assert report["handoff"]["blocks"] > 0


def test_cli_dry_run_writes_report(tmp_path: Path, capsys) -> None:
    tool = load_tool()
    profile = tmp_path / "profiles.jsonl"
    pack_root = tmp_path / "source-packs"
    report_path = tmp_path / "report.json"
    write_profile(profile)
    pack = write_pack(pack_root)
    write_ready_handoff(tmp_path, pack)

    rc = tool.main(
        [
            "--workflow-code",
            "I5B",
            "--handoff-root",
            str(tmp_path / "handoffs"),
            "--source-pack-root",
            str(pack_root),
            "--profile",
            str(profile),
            "--report",
            str(report_path),
            "--dry-run",
        ]
    )

    out = json.loads(capsys.readouterr().out)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert rc == 0
    assert out["ok"] is True
    assert report["dry_run"] is True
    assert report["items"][0]["status"] == "planned"
