from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import i5b_source_pack_status as tool


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def profile(person: str, *, source_group: str = "historical_seed", objects: list[str] | None = None) -> dict:
    return {
        "person": person,
        "query_profile_id": f"QRY-{person}",
        "source_group": source_group,
        "object_layers": {"core_positive_objects": objects or [f"{person}臣"]},
    }


def write_pack(root: Path, name: str, *, person: str, gaps: bool = False) -> None:
    pack = root / name
    pack.mkdir(parents=True)
    write_json(pack / "manifest.json", {"schema_version": 1, "status": "complete", "person": person})
    write_json(
        pack / "fetch_report.json",
        {
            "person": person,
            "status": "complete",
            "written_pages": 2,
            "excerpts": 3,
            "errors": [{"stage": "fetch_page"}] if gaps else [],
            "object_coverage": {
                "objects_without_page_hits": ["缺页对象"] if gaps else [],
                "objects_without_excerpts": ["缺摘录对象"] if gaps else [],
            },
        },
    )


def test_build_source_pack_status_report_classifies_pipeline_states(tmp_path: Path) -> None:
    profile_path = tmp_path / "profiles.jsonl"
    write_jsonl(
        profile_path,
        [
            profile("半成品", source_group="all_monarch_backfill", objects=["待识别对象"]),
            profile("未投"),
            profile("排队"),
            profile("运行"),
            profile("失败"),
            profile("成功无包"),
            profile("需完善"),
            profile("完成"),
        ],
    )
    profiles = tool.load_profiles(profile_path)

    jobs_dir = tmp_path / "jobs"
    logs_dir = tmp_path / "logs"
    write_json(jobs_dir / "queued.json", {"person": "排队", "output_name": "queued"})
    write_json(jobs_dir / "running.json.running", {"person": "运行", "output_name": "running"})
    write_json(logs_dir / "running.json.status.json", {"status": "running", "started_at": "2026-07-03T00:00:00+08:00"})
    write_json(jobs_dir / "failed.json.failed", {"person": "失败", "output_name": "failed"})
    write_json(logs_dir / "failed.json.status.json", {"status": "failed", "returncode": 1})
    write_json(jobs_dir / "success-missing.json.done", {"person": "成功无包", "output_name": "success-missing"})
    write_json(logs_dir / "success-missing.json.status.json", {"status": "complete", "returncode": 0})
    jobs = tool.load_jobs(jobs_dir, logs_dir)

    pack_root = tmp_path / "source-packs"
    write_pack(pack_root, "needs_work_pack", person="需完善", gaps=True)
    write_pack(pack_root, "complete_pack", person="完成", gaps=False)
    packs = tool.load_packs(pack_root)

    report = tool.build_status_report(
        persons=["缺包", "半成品", "未投", "排队", "运行", "失败", "成功无包", "需完善", "完成"],
        profiles=profiles,
        jobs=jobs,
        packs=packs,
    )

    by_person = {row["person"]: row for row in report["rows"]}
    assert by_person["缺包"]["action_status"] == "missing_query_profile"
    assert by_person["半成品"]["action_status"] == "profile_needs_work"
    assert by_person["未投"]["action_status"] == "prepared_not_submitted"
    assert by_person["排队"]["action_status"] == "fetch_queued"
    assert by_person["运行"]["action_status"] == "fetch_running"
    assert by_person["失败"]["action_status"] == "fetch_failed"
    assert by_person["成功无包"]["action_status"] == "fetch_success_pack_missing"
    assert by_person["需完善"]["action_status"] == "fetched_needs_profile_work"
    assert by_person["完成"]["action_status"] == "fetched_ok"
    assert report["totals"]["by_action_status"]["fetch_failed"] == 1


def test_source_pack_status_cli_writes_markdown(tmp_path: Path) -> None:
    all_list = tmp_path / "all.yml"
    all_list.write_text("- 甲\n- 乙\n", encoding="utf-8")
    profile_path = tmp_path / "profiles.jsonl"
    write_jsonl(profile_path, [profile("甲"), profile("乙", source_group="all_monarch_backfill", objects=["待识别对象"])])
    output = tmp_path / "report.md"

    assert (
        tool.main(
            [
                "--all-list",
                str(all_list),
                "--profile",
                str(profile_path),
                "--source-pack-root",
                str(tmp_path / "source-packs"),
                "--jobs-dir",
                str(tmp_path / "jobs"),
                "--format",
                "markdown",
                "--output",
                str(output),
            ]
        )
        == 0
    )

    text = output.read_text(encoding="utf-8")
    assert "I5B 抓包状态台账" in text
    assert "成品但尚未投入" in text
    assert "检索包半成品" in text
