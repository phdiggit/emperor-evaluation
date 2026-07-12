from __future__ import annotations

import json

import pytest

from scripts.dev import retrieval_v3_intake_orchestrator as tool


SEEDS = [
    {"object_code": "OBJ-LSM", "name": "李世民", "aliases": ["唐太宗"], "is_emperor": True, "target_emperors": ["李世民"]},
    {"object_code": "OBJ-SDF", "name": "苏定方", "aliases": [], "is_emperor": False, "target_emperors": ["李世民", "李治"]},
    {"object_code": "OBJ-FXL", "name": "房玄龄", "aliases": [], "is_emperor": False, "target_emperors": ["李世民"]},
    {"object_code": "OBJ-XD", "name": "徐达", "aliases": [], "is_emperor": False, "target_emperors": ["朱元璋"]},
]


def test_object_intake_selects_only_requested_person() -> None:
    rows, report = tool.select_intake_seeds(SEEDS, object_names=["苏定方"], emperor_names=[])
    assert [row["name"] for row in rows] == ["苏定方"]
    assert report["requires_related_object_discovery"] is False


def test_emperor_intake_selects_emperor_and_all_current_related_objects() -> None:
    rows, report = tool.select_intake_seeds(SEEDS, object_names=[], emperor_names=["唐太宗"])
    assert {row["name"] for row in rows} == {"李世民", "苏定方", "房玄龄"}
    assert report["requires_related_object_discovery"] is True
    assert "related_object_discovery" in report["next_stages"]


def test_intake_rejects_unresolved_names() -> None:
    with pytest.raises(tool.IntakeOrchestratorError, match="unresolved intake names"):
        tool.select_intake_seeds(SEEDS, object_names=["不存在"], emperor_names=[])


def test_intake_can_create_stable_seed_for_new_person() -> None:
    rows, report = tool.select_intake_seeds(
        SEEDS, object_names=["朱橚"], emperor_names=[], allow_new=True, target_emperors=["朱元璋"]
    )
    assert rows == [tool.new_person_seed("朱橚", target_emperors=["朱元璋"])]
    assert report["selected_objects"] == ["朱橚"]


def test_intake_can_create_new_emperor_seed() -> None:
    rows, report = tool.select_intake_seeds(SEEDS, object_names=[], emperor_names=["李治"], allow_new=True)
    emperor = next(row for row in rows if row["name"] == "李治")
    assert emperor["is_emperor"] is True
    assert emperor["target_emperors"] == ["李治"]
    assert report["requires_related_object_discovery"] is True


def test_ensure_mode_is_stable_and_does_not_refresh_cache() -> None:
    first, first_key = tool.intake_build_options(mode="ensure")
    second, second_key = tool.intake_build_options(mode="ensure")
    assert first == second == {"intake_mode": "ensure", "cache_refresh": False}
    assert first_key == second_key == ""


def test_supplement_mode_uses_explicit_retry_key_without_cache_refresh() -> None:
    options, request_key = tool.intake_build_options(mode="supplement", request_key="SUP-1")
    assert request_key == "SUP-1"
    assert options == {
        "intake_mode": "supplement",
        "intake_request_key": "SUP-1",
        "cache_refresh": False,
    }


def test_refresh_mode_generates_request_key_and_refreshes_cache() -> None:
    options, request_key = tool.intake_build_options(mode="refresh")
    assert request_key
    assert options["intake_request_key"] == request_key
    assert options["cache_refresh"] is True


def test_supplement_request_key_changes_worker_job_identity(tmp_path) -> None:
    seed_path = tmp_path / "seed.jsonl"
    seed_path.write_text(json.dumps(SEEDS[1], ensure_ascii=False) + "\n", encoding="utf-8")
    ensure_options, _ = tool.intake_build_options(mode="ensure")
    supplement_options, _ = tool.intake_build_options(mode="supplement", request_key="SUP-1")
    ensure_job = tool.worker.job_from_seed(seed_jsonl=seed_path, build_options=ensure_options)
    supplement_job = tool.worker.job_from_seed(seed_jsonl=seed_path, build_options=supplement_options)
    repeated_job = tool.worker.job_from_seed(seed_jsonl=seed_path, build_options=supplement_options)
    assert ensure_job["idem_key"] != supplement_job["idem_key"]
    assert repeated_job["idem_key"] == supplement_job["idem_key"]


def test_apply_worker_runtime_root_persists_linux_native_paths() -> None:
    job = tool.apply_worker_runtime_root(
        {"job_code": "OSCACHE-ABC", "output_root": "E:/tmp/run", "page_cache_root": "E:/tmp/pages", "seed_jsonl_path": "E:/tmp/seed.jsonl"},
        runtime_root="/data1/emperor-evaluation/runtime/active",
    )
    assert job["output_root"] == "/data1/emperor-evaluation/runtime/active/object_source_runs/oscache-abc"
    assert job["page_cache_root"] == "/data1/emperor-evaluation/runtime/active/source_pages"
    assert job["seed_jsonl_path"] == "/data1/emperor-evaluation/runtime/active/embedded_seeds/oscache-abc.jsonl"


def test_merge_query_profile_source_hints_connects_object_to_biography(tmp_path) -> None:
    profile = tmp_path / "profiles.jsonl"
    profile.write_text(json.dumps({
        "query_profile_id": "Q-1", "person": "朱元璋",
        "source_targets": ["明史 冯胜传、傅友德传"],
        "object_layers": {"negative_or_reversal_objects": ["冯胜"]},
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    rows, report = tool.merge_query_profile_source_hints(
        [{"name": "冯胜", "target_emperors": ["朱元璋"], "source_hints": []}], profile_path=profile
    )
    assert report["matched_objects"] == ["冯胜"]
    assert rows[0]["source_hints"]
    assert rows[0]["query_profile_id"] == "Q-1"
