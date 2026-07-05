from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_discovery_profiles as tool


def sample_task() -> dict:
    return {
        "emperor_name": "赵匡胤",
        "item_code": "I5B",
        "rule_code": "delegation",
        "target_profile": {"primary_name": "赵匡胤", "aliases": ["赵匡胤", "宋太祖"]},
        "object_seeds": [{"name": "吕余庆", "aliases": [{"alias": "呂餘慶", "strength": "strong"}]}],
        "source_documents": [{"document_code": "DOC-SH-001", "title": "宋史/fixture", "text": "太祖命吕余庆。"}],
        "generation_notes": ["fixture"],
    }


def sample_context(rule_code: str = "delegation") -> dict:
    return {"emperor_name": "赵匡胤", "item_code": "I5B", "rule_code": rule_code}


def test_write_scan_and_select_profile(tmp_path: Path) -> None:
    profile = tool.profile_from_task(sample_task())

    output = tool.write_profile(profile, tmp_path)
    loaded = tool.load_profiles(roots=[tmp_path])
    selected = tool.select_profile(loaded, sample_context())

    assert output.exists()
    assert len(loaded) == 1
    assert selected is not None
    assert selected["emperor_name"] == "赵匡胤"
    assert selected["object_seeds"][0]["name"] == "吕余庆"


def test_select_profile_requires_same_rule_unless_opted_in(tmp_path: Path) -> None:
    profile = tool.profile_from_task(sample_task())
    tool.write_profile(profile, tmp_path)
    loaded = tool.load_profiles(roots=[tmp_path])

    assert tool.select_profile(loaded, sample_context("appointment_trust")) is None
    assert tool.select_profile(loaded, sample_context("appointment_trust"), allow_cross_rule=True) is not None


def test_cli_from_task_writes_profile_root(tmp_path: Path, capsys) -> None:
    task_path = tmp_path / "task.json"
    profile_root = tmp_path / "profiles"
    task_path.write_text(json.dumps(sample_task(), ensure_ascii=False), encoding="utf-8")

    assert tool.main(["--from-task", str(task_path), "--profile-root", str(profile_root)]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert Path(payload["output"]).exists()
    assert payload["profile"]["profile_fingerprint"]
    assert payload["profile"]["object_seed_count"] == 1
    assert "full_profile" not in payload


def test_cli_from_task_verbose_includes_full_profile(tmp_path: Path, capsys) -> None:
    task_path = tmp_path / "task.json"
    profile_root = tmp_path / "profiles"
    task_path.write_text(json.dumps(sample_task(), ensure_ascii=False), encoding="utf-8")

    assert tool.main(["--from-task", str(task_path), "--profile-root", str(profile_root), "--verbose"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["full_profile"]["profile_fingerprint"] == payload["profile"]["profile_fingerprint"]


def test_invalid_explicit_profile_reports_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{}", encoding="utf-8")

    try:
        tool.load_profiles(paths=[path])
    except tool.RetrievalV2DiscoveryProfileError as exc:
        assert "invalid discovery profile" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected invalid profile error")
