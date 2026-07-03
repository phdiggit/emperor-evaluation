from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "i5b_query_profile_refiner.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_query_profile_refiner_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sample_profile() -> dict:
    return {
        "person": "武则天",
        "query_profile_id": "QRY-WZT",
        "source_targets": ["旧唐书 / 新唐书 狄仁杰传、张易之传", "资治通鉴 唐纪"],
        "object_layers": {
            "core_positive_objects": ["姚崇早期"],
            "negative_or_reversal_objects": ["张易之"],
        },
        "query_bundles": ["武则天 张易之 旧唐书 近幸 任用"],
        "object_search_aliases": {},
    }


def write_pack(pack_dir: Path) -> None:
    pack_dir.mkdir(parents=True)
    (pack_dir / "fetch_report.json").write_text(
        json.dumps(
            {
                "person": "武则天",
                "status": "complete",
                "written_pages": 1,
                "excerpts": 0,
                "errors": [],
                "object_coverage": {
                    "objects_without_page_hits": ["姚崇早期"],
                    "objects_without_excerpts": ["张易之"],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (pack_dir / "src_docs.jsonl").write_text(
        json.dumps(
            {
                "src_key": "old_tang_183",
                "page_title": "舊唐書/卷183",
                "object_names": ["张易之"],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def test_refiner_generates_review_only_patch_from_pack_gaps(tmp_path) -> None:
    tool = load_tool()
    pack_dir = tmp_path / "pack"
    write_pack(pack_dir)
    row = {
        "person": "武则天",
        "action_status": "fetched_needs_profile_work",
        "objects_without_page_hits": ["姚崇早期"],
        "objects_without_excerpts": ["张易之"],
        "pack_path": str(pack_dir),
    }

    report = tool.build_refinement_report(profiles={"武则天": sample_profile()}, status_rows=[row])

    assert report["workflow_code"] == "I5B"
    assert report["review_required"] is True
    assert report["totals"]["persons"] == 1
    refinement = report["refinements"][0]
    patch = refinement["profile_patch_candidate"]
    assert patch["merge_object_search_aliases"]["姚崇早期"] == ["姚崇"]
    assert any("舊唐書/卷183" in target for target in patch["append_source_targets"])
    assert any("武则天 姚崇" in query for query in patch["append_query_bundles"])
    assert refinement["requires_review"] is True


def test_load_profile_rows_filters_by_workflow_code(tmp_path: Path) -> None:
    tool = load_tool()
    profile_path = tmp_path / "profiles.jsonl"
    rows = [
        {**sample_profile(), "query_profile_id": "QRY-I5B"},
        {**sample_profile(), "workflow_code": "I5A", "query_profile_id": "QRY-I5A"},
    ]
    profile_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")

    assert tool.load_profile_rows(profile_path)["武则天"]["query_profile_id"] == "QRY-I5B"
    assert tool.load_profile_rows(profile_path, workflow_code="I5A")["武则天"]["query_profile_id"] == "QRY-I5A"


def test_load_profile_rows_rejects_duplicate_person_in_same_workflow(tmp_path: Path) -> None:
    tool = load_tool()
    profile_path = tmp_path / "profiles.jsonl"
    rows = [sample_profile(), sample_profile()]
    profile_path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")

    try:
        tool.load_profile_rows(profile_path)
    except tool.ExcerptPoolError as exc:
        assert "multiple profiles found for person: 武则天 workflow_code=I5B" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("duplicate workflow profiles should be rejected")


def test_load_status_rows_rejects_status_report_workflow_mismatch(tmp_path: Path) -> None:
    tool = load_tool()
    status_path = tmp_path / "status.json"
    status_path.write_text(json.dumps({"workflow_code": "I5B", "rows": []}, ensure_ascii=False), encoding="utf-8")

    try:
        tool.load_status_rows(
            status_report=status_path,
            profile_path=tmp_path / "profiles.jsonl",
            source_pack_root=tmp_path / "packs",
            all_list=tmp_path / "all.yml",
            jobs_dir=tmp_path / "jobs",
            logs_dir=tmp_path / "logs",
            workflow_code="I5A",
        )
    except tool.ExcerptPoolError as exc:
        assert "status report workflow_code mismatch: expected I5A, got I5B" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("workflow-mismatched status reports should be rejected")


def test_load_status_rows_filters_legacy_report_rows_by_workflow_fields(tmp_path: Path) -> None:
    tool = load_tool()
    status_path = tmp_path / "status.json"
    status_path.write_text(
        json.dumps(
            {
                "rows": [
                    {"person": "甲", "action_status": "profile_needs_work", "profile_workflow_code": "I5A"},
                    {"person": "乙", "action_status": "profile_needs_work", "profile_workflow_code": "I5B"},
                    {"person": "丙", "action_status": "profile_needs_work"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rows = tool.load_status_rows(
        status_report=status_path,
        profile_path=tmp_path / "profiles.jsonl",
        source_pack_root=tmp_path / "packs",
        all_list=tmp_path / "all.yml",
        jobs_dir=tmp_path / "jobs",
        logs_dir=tmp_path / "logs",
        workflow_code="I5A",
    )

    assert [row["person"] for row in rows] == ["甲", "丙"]


def test_refiner_cli_writes_markdown_without_touching_profile(tmp_path) -> None:
    tool = load_tool()
    pack_dir = tmp_path / "pack"
    write_pack(pack_dir)
    profile_path = tmp_path / "profiles.jsonl"
    original_profile = json.dumps({**sample_profile(), "workflow_code": "I5A"}, ensure_ascii=False) + "\n"
    profile_path.write_text(original_profile, encoding="utf-8")
    status_path = tmp_path / "status.json"
    status_path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "person": "武则天",
                        "action_status": "fetched_needs_profile_work",
                        "objects_without_page_hits": ["姚崇早期"],
                        "objects_without_excerpts": ["张易之"],
                        "pack_path": str(pack_dir),
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "refiner.md"

    assert tool.main(
        [
            "--profile",
            str(profile_path),
            "--status-report",
            str(status_path),
            "--workflow-code",
            "I5A",
            "--output",
            str(output_path),
        ]
    ) == 0

    text = output_path.read_text(encoding="utf-8")
    assert "I5A 检索包补强候选" in text
    assert "- workflow_code: `I5A`" in text
    assert "姚崇早期" in text
    assert profile_path.read_text(encoding="utf-8") == original_profile
