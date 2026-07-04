from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.dev import i5b_source_pack_pipeline_daemon as tool


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def sample_profile(person: str = "甲", *, workflow_code: str | None = None) -> dict:
    row = {
        "person": person,
        "query_profile_id": f"QRY-{person}",
        "source_group": "historical_seed",
        "source_targets": ["旧唐书"],
        "object_layers": {"core_positive_objects": ["张三"], "negative_or_reversal_objects": []},
        "query_bundles": [f"{person} 张三 旧唐书 任用"],
        "object_search_aliases": {},
    }
    if workflow_code:
        row["workflow_code"] = workflow_code
    return row


def write_gap_pack(root: Path, *, person: str = "甲", workflow_code: str = "I5B") -> None:
    pack = root / "pack-a"
    write_json(pack / "manifest.json", {"schema_version": 1, "status": "complete", "person": person, "workflow_code": workflow_code})
    write_json(
        pack / "fetch_report.json",
        {
            "person": person,
            "workflow_code": workflow_code,
            "status": "complete",
            "written_pages": 1,
            "excerpts": 0,
            "errors": [],
            "object_coverage": {"objects_without_page_hits": [], "objects_without_excerpts": ["张三"]},
        },
    )
    write_jsonl(pack / "src_docs.jsonl", [{"page_title": "舊唐書/卷1", "object_names": ["张三"]}])


def args_for(tmp_path: Path, *, submit_prepared: bool = False, submit_refinements: bool = True) -> argparse.Namespace:
    return argparse.Namespace(
        profile=tmp_path / "profiles.jsonl",
        all_list=tmp_path / "all.yml",
        source_pack_root=tmp_path / "source-packs",
        jobs_dir=tmp_path / "jobs",
        logs_dir=tmp_path / "logs",
        output_dir=tmp_path / "logs",
        state_file=None,
        derived_profile_dir=None,
        workflow_code="I5B",
        status=[],
        submit_prepared=submit_prepared,
        submit_seeds=False,
        seed_report=None,
        seed_derived_source_group="",
        submit_refinements=submit_refinements,
        max_jobs_per_run=0,
        max_seed_rounds_per_person=1,
        max_refine_rounds_per_person=2,
        include_adjacent=False,
        refine_max_queries_per_object=3,
        fetch_max_queries_per_object=4,
        pages_per_query=6,
        context_chars=420,
        max_passages_per_page=4,
        request_delay=1.0,
        max_retries=4,
        retry_backoff=3.0,
        max_retry_wait=30,
        max_consecutive_errors=8,
        max_wall_seconds=3600,
        no_cache=False,
    )


def half_baked_profile(person: str = "己") -> dict:
    return {
        "person": person,
        "query_profile_id": f"QRY-{person}",
        "source_group": "all_monarch_backfill",
        "source_targets": ["晋书"],
        "object_layers": {
            "core_positive_objects": ["任用授权待识别对象"],
            "negative_or_reversal_objects": ["功臣安全与处置对象"],
        },
        "query_bundles": [f"{person} 晋书 任用 授权"],
        "object_search_aliases": {},
    }


def test_pipeline_applies_refinement_to_derived_profile_and_submits_job(tmp_path: Path) -> None:
    write_jsonl(tmp_path / "profiles.jsonl", [sample_profile()])
    write_gap_pack(tmp_path / "source-packs")

    report = tool.run_once(args_for(tmp_path))

    assert report["submitted_jobs"] == 1
    assert report["workflow_code"] == "I5B"
    assert report["control_summary"]["submitted_people"] == ["甲"]
    assert report["control_summary"]["action_counts"] == {"submitted": 1}
    action = report["actions"][0]
    assert action["status"] == "submitted"
    assert action["kind"] == "refine"
    derived_profile = Path(action["profile_path"])
    job_path = Path(action["job_path"])
    assert derived_profile.exists()
    assert job_path.exists()
    profile = json.loads(derived_profile.read_text(encoding="utf-8").splitlines()[0])
    assert any("舊唐書/卷1" in target for target in profile["source_targets"])
    job = json.loads(job_path.read_text(encoding="utf-8"))
    assert job["profile"] == str(derived_profile)
    assert job["workflow_code"] == "I5B"
    assert job["pipeline"]["kind"] == "refine"


def test_pipeline_does_not_resubmit_same_effective_patch(tmp_path: Path) -> None:
    write_jsonl(tmp_path / "profiles.jsonl", [sample_profile()])
    write_gap_pack(tmp_path / "source-packs")
    args = args_for(tmp_path)

    first = tool.run_once(args)
    second = tool.run_once(args)

    assert first["submitted_jobs"] == 1
    assert second["submitted_jobs"] == 0
    assert second["actions"] == []
    assert second["status_control_summary"]["queues"]["refinement_candidates"] == []
    assert second["status_control_summary"]["queues"]["in_flight"] == ["甲"]
    assert second["refinement_totals"]["patch_suggestions"] == 0
    assert len(list((tmp_path / "jobs").glob("*.json"))) == 1


def test_pipeline_submits_prepared_profile_without_derived_profile(tmp_path: Path) -> None:
    write_jsonl(tmp_path / "profiles.jsonl", [sample_profile("乙")])
    args = args_for(tmp_path, submit_prepared=True, submit_refinements=False)

    report = tool.run_once(args)

    assert report["submitted_jobs"] == 1
    job_path = Path(report["actions"][0]["job_path"])
    job = json.loads(job_path.read_text(encoding="utf-8"))
    assert job["person"] == "乙"
    assert job["profile"] == str(tmp_path / "profiles.jsonl")
    assert job["workflow_code"] == "I5B"
    assert job["pipeline"]["kind"] == "initial"


def test_pipeline_applies_reviewed_seed_patch_to_derived_profile(tmp_path: Path) -> None:
    write_jsonl(tmp_path / "profiles.jsonl", [half_baked_profile()])
    seed_report = tmp_path / "seed_report.json"
    write_json(
        seed_report,
        {
            "seeds": [
                {
                    "person": "己",
                    "accepted_for_profile": True,
                    "review_status": "accepted",
                    "seed_profile_patch_candidate": {
                        "replace_object_layers": {
                            "core_positive_objects": ["陈群", "司马懿"],
                            "negative_or_reversal_objects": ["曹洪"],
                        },
                        "append_query_bundles": ["己 陈群 晋书 任用", "己 曹洪 晋书 处置"],
                        "merge_object_search_aliases": {"司马懿": ["仲达"]},
                    },
                }
            ]
        },
    )
    args = args_for(tmp_path, submit_prepared=False, submit_refinements=False)
    args.submit_seeds = True
    args.seed_report = seed_report

    report = tool.run_once(args)

    assert report["submitted_jobs"] == 1
    assert report["seed_totals"] == {"seeds": 1, "accepted": 1}
    action = report["actions"][0]
    assert action["kind"] == "seed"
    assert action["status"] == "submitted"
    derived_profile = Path(action["profile_path"])
    profile = json.loads(derived_profile.read_text(encoding="utf-8").splitlines()[0])
    assert profile["source_group"] == "i5b_seed_derived"
    assert profile["query_profile_id"].startswith("QRY-己-SEED-")
    assert profile["object_layers"]["core_positive_objects"] == ["陈群", "司马懿"]
    assert profile["object_layers"]["negative_or_reversal_objects"] == ["曹洪"]
    assert "任用授权待识别对象" not in json.dumps(profile["object_layers"], ensure_ascii=False)
    assert profile["object_search_aliases"]["司马懿"] == ["仲达"]
    job = json.loads(Path(action["job_path"]).read_text(encoding="utf-8"))
    assert job["profile"] == str(derived_profile)
    assert job["pipeline"]["kind"] == "seed"


def test_pipeline_skips_unreviewed_seed_patch(tmp_path: Path) -> None:
    write_jsonl(tmp_path / "profiles.jsonl", [half_baked_profile()])
    seed_report = tmp_path / "seed_report.json"
    write_json(
        seed_report,
        {
            "seeds": [
                {
                    "person": "己",
                    "seed_profile_patch_candidate": {
                        "replace_object_layers": {"core_positive_objects": ["陈群"]},
                        "append_query_bundles": ["己 陈群 晋书 任用"],
                    },
                }
            ]
        },
    )
    args = args_for(tmp_path, submit_prepared=False, submit_refinements=False)
    args.submit_seeds = True
    args.seed_report = seed_report

    report = tool.run_once(args)

    assert report["submitted_jobs"] == 0
    assert report["seed_totals"] == {"seeds": 1, "accepted": 0}
    assert report["actions"] == [{"person": "己", "kind": "seed", "status": "skip_unreviewed"}]
    assert not (tmp_path / "jobs").exists()


def test_pipeline_uses_workflow_code_for_non_i5b_outputs(tmp_path: Path) -> None:
    write_jsonl(tmp_path / "profiles.jsonl", [sample_profile("丙", workflow_code="I5A")])
    args = args_for(tmp_path, submit_prepared=True, submit_refinements=False)
    args.workflow_code = "I5A"

    report = tool.run_once(args)

    assert report["workflow_code"] == "I5A"
    assert report["submitted_jobs"] == 1
    assert Path(report["state_file"]).name == "i5a_source_pack_pipeline_state.json"
    report_path = tmp_path / "logs" / "i5a_source_pack_pipeline_report.json"
    assert report_path.exists()
    action = report["actions"][0]
    assert action["output_name"].startswith("i5a_pipeline_initial_")
    job = json.loads(Path(action["job_path"]).read_text(encoding="utf-8"))
    assert job["workflow_code"] == "I5A"


def test_pipeline_uses_workflow_code_for_non_i5b_refinements(tmp_path: Path) -> None:
    write_jsonl(tmp_path / "profiles.jsonl", [sample_profile("丁", workflow_code="I5A")])
    write_gap_pack(tmp_path / "source-packs", person="丁", workflow_code="I5A")
    args = args_for(tmp_path, submit_prepared=False, submit_refinements=True)
    args.workflow_code = "I5A"

    report = tool.run_once(args)

    assert report["workflow_code"] == "I5A"
    assert report["submitted_jobs"] == 1
    assert Path(report["state_file"]).name == "i5a_source_pack_pipeline_state.json"
    action = report["actions"][0]
    assert action["kind"] == "refine"
    assert action["output_name"].startswith("i5a_pipeline_refine_")
    job = json.loads(Path(action["job_path"]).read_text(encoding="utf-8"))
    assert job["workflow_code"] == "I5A"
    assert job["pipeline"]["kind"] == "refine"


def test_pipeline_shared_state_keeps_workflow_submissions_separate(tmp_path: Path) -> None:
    state_file = tmp_path / "shared_state.json"
    write_jsonl(tmp_path / "profiles.jsonl", [sample_profile("戊"), sample_profile("戊", workflow_code="I5A")])

    args_i5b = args_for(tmp_path, submit_prepared=True, submit_refinements=False)
    args_i5b.state_file = state_file
    first = tool.run_once(args_i5b)

    args_i5a = args_for(tmp_path, submit_prepared=True, submit_refinements=False)
    args_i5a.workflow_code = "I5A"
    args_i5a.state_file = state_file
    second = tool.run_once(args_i5a)

    assert first["submitted_jobs"] == 1
    assert second["submitted_jobs"] == 1
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert [item["workflow_code"] for item in state["submissions"]] == ["I5B", "I5A"]
