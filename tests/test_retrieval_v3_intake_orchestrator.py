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
