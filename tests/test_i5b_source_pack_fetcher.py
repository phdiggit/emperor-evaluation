from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "i5b_source_pack_fetcher.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_source_pack_fetcher_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sample_profile() -> dict:
    return {
        "person": "武则天",
        "query_profile_id": "QRY-WZT",
        "source_targets": ["旧唐书 张易之传"],
        "object_layers": {
            "core_positive_objects": ["王孝杰"],
            "negative_or_reversal_objects": ["张易之"],
        },
        "query_bundles": ["武则天 王孝杰 旧唐书", "武则天 张易之 旧唐书"],
    }


def test_build_source_pack_writes_auditable_pack(tmp_path, monkeypatch) -> None:
    load_tool()
    fetcher = sys.modules["scripts.dev.source_excerpt_pool_lib.source_pack_fetcher"]
    source_pack = sys.modules["scripts.dev.source_excerpt_pool_lib.source_pack"]

    def fake_search(query, **kwargs):
        if "王孝杰" in query:
            return [
                {
                    "title": "舊唐書/卷109",
                    "url": "https://zh.wikisource.org/zh-hans/舊唐書/卷109",
                    "snippet": "王孝杰为清边道行军总管。",
                }
            ]
        if "张易之" in query:
            return [
                {
                    "title": "舊唐書/卷183",
                    "url": "https://zh.wikisource.org/zh-hans/舊唐書/卷183",
                    "snippet": "张易之兄弟幸于后。",
                }
            ]
        return []

    def fake_fetch(title, **kwargs):
        if title == "舊唐書/卷109":
            return "武则天命王孝杰为清边道行军总管。"
        if title == "舊唐書/卷183":
            return "张易之兄弟幸于后，势倾朝野。"
        return ""

    monkeypatch.setattr(fetcher, "search_wikisource", fake_search)
    monkeypatch.setattr(fetcher, "fetch_wikisource_plain_text", fake_fetch)

    output_dir = tmp_path / "pack"
    report = fetcher.build_source_pack(
        sample_profile(),
        output_dir=output_dir,
        cache_enabled=False,
        request_delay_seconds=0,
    )

    assert report["status"] == "complete"
    assert report["candidate_search_plans"] >= report["active_search_plans"] >= report["processed_searches"]
    assert report["skipped_search_plan_count"] == 0
    assert report["written_pages"] == 2
    assert report["excerpts"] >= 2
    assert report["started_at"]
    assert report["finished_at"]
    assert report["object_coverage"]["objects_without_excerpts"] == []
    assert (output_dir / "manifest.json").exists()
    assert (output_dir / "src_docs.jsonl").exists()
    assert (output_dir / "excerpts.jsonl").exists()
    rows = [json.loads(line) for line in (output_dir / "src_docs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {row["title"] for row in rows} == {"旧唐书"}
    assert {row["author"] for row in rows} == {"刘昫等"}
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["workflow_code"] == "I5B"
    assert manifest["source_scope"] == "I5B offline source pack for 武则天"
    assert manifest["generated_by"] == "scripts/dev/source_excerpt_pool_lib/source_pack_fetcher.py"
    excerpts = [json.loads(line) for line in (output_dir / "excerpts.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {row["extraction_method"] for row in excerpts} == {"source_pack_fetcher"}
    assert source_pack.audit_source_pack(output_dir)["ok"] is True


def test_build_source_pack_allows_non_i5b_manifest_metadata(tmp_path, monkeypatch) -> None:
    load_tool()
    fetcher = sys.modules["scripts.dev.source_excerpt_pool_lib.source_pack_fetcher"]
    source_pack = sys.modules["scripts.dev.source_excerpt_pool_lib.source_pack"]

    def fake_search(query, **kwargs):
        assert "勤政" in query
        return [
            {
                "title": "舊唐書/卷006",
                "url": "https://zh.wikisource.org/zh-hans/舊唐書/卷006",
                "snippet": "武则天勤于听政。",
            }
        ]

    def fake_fetch(title, **kwargs):
        assert title == "舊唐書/卷006"
        return "武则天勤于听政，日览奏章。"

    monkeypatch.setattr(fetcher, "search_wikisource", fake_search)
    monkeypatch.setattr(fetcher, "fetch_wikisource_plain_text", fake_fetch)

    profile = {
        "person": "武则天",
        "query_profile_id": "QRY-I5A-WZT",
        "object_layers": {"core_positive_objects": ["勤政"]},
        "query_bundles": ["武则天 勤政 旧唐书"],
    }
    output_dir = tmp_path / "pack"
    report = fetcher.build_source_pack(
        profile,
        output_dir=output_dir,
        workflow_code="I5A",
        source_scope="I5A fixture source pack",
        generated_by="scripts/dev/generic_source_pack_fetcher.py",
        extraction_method="generic_source_pack_fetcher",
        cache_enabled=False,
        request_delay_seconds=0,
    )

    assert report["status"] == "complete"
    assert report["workflow_code"] == "I5A"
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["pack_id"].startswith("I5A-SOURCE-PACK-QRY-I5A-WZT-武则天-")
    assert manifest["workflow_code"] == "I5A"
    assert manifest["source_scope"] == "I5A fixture source pack"
    assert manifest["generated_by"] == "scripts/dev/generic_source_pack_fetcher.py"
    excerpts = [json.loads(line) for line in (output_dir / "excerpts.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {row["extraction_method"] for row in excerpts} == {"generic_source_pack_fetcher"}
    assert source_pack.audit_source_pack(output_dir)["ok"] is True


def test_source_pack_fetcher_cli_defaults_output_under_tmp(monkeypatch, tmp_path, capsys) -> None:
    tool = load_tool()
    profile_path = tmp_path / "profiles.jsonl"
    profile_path.write_text(json.dumps(sample_profile(), ensure_ascii=False) + "\n", encoding="utf-8")
    output_dir = tmp_path / "pack"

    def fake_build_source_pack(profile, **kwargs):
        assert profile["person"] == "武则天"
        assert kwargs["output_dir"] == output_dir
        assert kwargs["workflow_code"] == "I5B"
        assert kwargs["source_scope"] == "I5B offline source pack"
        assert kwargs["generated_by"] == "scripts/dev/i5b_source_pack_fetcher.py"
        assert kwargs["extraction_method"] == "i5b_source_pack_fetcher"
        return {
            "status": "complete",
            "written_pages": 1,
            "excerpts": 1,
            "errors": [],
            "object_coverage": {"objects_without_excerpts": []},
        }

    monkeypatch.setattr(tool, "build_source_pack", fake_build_source_pack)

    assert tool.main(["--profile", str(profile_path), "--person", "武则天", "--output-dir", str(output_dir)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["output_dir"] == str(output_dir)
    assert payload["pages"] == 1
    assert payload["at"]
    assert payload["started_at"]
    assert payload["finished_at"]
    assert isinstance(payload["elapsed_seconds"], (int, float))


def test_source_pack_fetcher_cli_selects_profile_by_workflow_code(monkeypatch, tmp_path, capsys) -> None:
    tool = load_tool()
    profile_path = tmp_path / "profiles.jsonl"
    rows = [
        {**sample_profile(), "query_profile_id": "QRY-I5B"},
        {**sample_profile(), "workflow_code": "I5A", "query_profile_id": "QRY-I5A"},
    ]
    profile_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
    output_dir = tmp_path / "pack"

    def fake_build_source_pack(profile, **kwargs):
        assert profile["query_profile_id"] == "QRY-I5A"
        assert kwargs["workflow_code"] == "I5A"
        return {
            "status": "complete",
            "written_pages": 1,
            "excerpts": 1,
            "errors": [],
            "object_coverage": {"objects_without_excerpts": []},
        }

    monkeypatch.setattr(tool, "build_source_pack", fake_build_source_pack)

    assert (
        tool.main(
            [
                "--profile",
                str(profile_path),
                "--person",
                "武则天",
                "--workflow-code",
                "I5A",
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["output_dir"] == str(output_dir)
