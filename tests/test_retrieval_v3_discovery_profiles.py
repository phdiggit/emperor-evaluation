from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v3_discovery_profiles as tool


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

    assert tool.select_profile(loaded, sample_context("team_building")) is None
    assert tool.select_profile(loaded, sample_context("team_building"), allow_cross_rule=True) is not None


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
    except tool.RetrievalV3DiscoveryProfileError as exc:
        assert "invalid discovery profile" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected invalid profile error")


def test_recall_term_delta_preview_adds_rule_terms_without_writing_profile(tmp_path: Path) -> None:
    profile = tool.profile_from_task(sample_task())
    profile["rule_terms"] = ["命"]
    delta = {
        "version": "recall_term_profile_delta_v0_1",
        "report_type": "recall_term_profile_delta",
        "proposed_updates": [
            {
                "profile_scope": "personnel_political_wide",
                "target_location": "source_discovery_profile",
                "target_field": "rule_terms",
                "operation": "append_unique",
                "add_terms": ["命", "专擅", "威福"],
            }
        ],
    }

    preview = tool.profile_recall_delta_preview(profile, delta)

    assert profile["rule_terms"] == ["命"]
    assert preview["rule_terms"] == ["命", "专擅", "威福"]
    assert preview["recall_term_overlays"][0]["add_terms"] == ["命", "专擅", "威福"]
    assert preview["preview_metadata"]["writes_profile"] is False
    assert preview["preview_metadata"]["appended_rule_term_count"] == 3
    assert preview["preview_metadata"]["conditional_term_not_injected_count"] == 0


def test_recall_term_delta_task_preview_adds_top_level_rule_terms() -> None:
    task = sample_task()
    delta = {
        "version": "recall_term_profile_delta_v0_1",
        "report_type": "recall_term_profile_delta",
        "proposed_updates": [
            {
                "target_location": "source_discovery_profile",
                "target_field": "rule_terms",
                "operation": "append_unique",
                "add_terms": ["谋反", "伏诛"],
            }
        ],
    }

    preview = tool.task_recall_delta_preview(task, delta)

    assert "rule_terms" not in task
    assert preview["rule_terms"] == ["谋反", "伏诛"]
    assert preview["recall_term_overlays"][0]["target_location"] == "task.rule_terms"
    assert preview["preview_metadata"]["writes_task"] is False
    assert preview["preview_metadata"]["appended_rule_term_count"] == 2


def test_cli_recall_term_delta_writes_preview_only(tmp_path: Path, capsys) -> None:
    profile_path = tmp_path / "profile.json"
    delta_path = tmp_path / "delta.json"
    preview_path = tmp_path / "preview.json"
    profile_path.write_text(json.dumps(tool.profile_from_task(sample_task()), ensure_ascii=False), encoding="utf-8")
    delta_path.write_text(
        json.dumps(
            {
                "version": "recall_term_profile_delta_v0_1",
                "report_type": "recall_term_profile_delta",
                "proposed_updates": [
                    {
                        "target_location": "source_discovery_profile",
                        "target_field": "rule_terms",
                        "operation": "append_unique",
                        "add_terms": ["谋反", "伏诛"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert (
        tool.main(
            [
                "--profile",
                str(profile_path),
                "--recall-term-delta",
                str(delta_path),
                "--output-preview",
                str(preview_path),
            ]
        )
        == 0
    )

    out = json.loads(capsys.readouterr().out)
    preview = json.loads(preview_path.read_text(encoding="utf-8"))
    source_profile = json.loads(profile_path.read_text(encoding="utf-8"))
    assert out["writes_profile"] is False
    assert out["appended_rule_term_count"] == 2
    assert preview["rule_terms"] == ["谋反", "伏诛"]
    assert "rule_terms" not in source_profile


def test_cli_recall_term_delta_writes_task_preview_only(tmp_path: Path, capsys) -> None:
    task_path = tmp_path / "task.json"
    delta_path = tmp_path / "delta.json"
    preview_path = tmp_path / "task_preview.json"
    task_path.write_text(json.dumps(sample_task(), ensure_ascii=False), encoding="utf-8")
    delta_path.write_text(
        json.dumps(
            {
                "version": "recall_term_profile_delta_v0_1",
                "report_type": "recall_term_profile_delta",
                "proposed_updates": [
                    {
                        "target_location": "source_discovery_profile",
                        "target_field": "rule_terms",
                        "operation": "append_unique",
                        "add_terms": ["谋反", "伏诛"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert (
        tool.main(
            [
                "--from-task",
                str(task_path),
                "--recall-term-delta",
                str(delta_path),
                "--output-task-preview",
                str(preview_path),
            ]
        )
        == 0
    )

    out = json.loads(capsys.readouterr().out)
    preview = json.loads(preview_path.read_text(encoding="utf-8"))
    source_task = json.loads(task_path.read_text(encoding="utf-8"))
    assert out["writes_task"] is False
    assert out["writes_profile"] is False
    assert out["appended_rule_term_count"] == 2
    assert preview["rule_terms"] == ["谋反", "伏诛"]
    assert "rule_terms" not in source_task


def test_guarded_recall_term_delta_preview_does_not_inject_rule_terms() -> None:
    task = sample_task()
    delta = {
        "version": "recall_term_profile_delta_v0_1",
        "report_type": "recall_term_profile_delta",
        "proposed_updates": [
            {
                "target_location": "source_discovery_profile",
                "target_field": "conditional_rule_terms",
                "operation": "append_guarded_terms",
                "conditional_terms": [
                    {
                        "term": "谋反",
                        "profile_action": "conditional_term",
                        "policy_group": "disposition_risk",
                        "risk_level": "high",
                        "guard": {"requires_near_any": ["丞相", "中书"]},
                    }
                ],
            }
        ],
    }

    preview = tool.task_recall_delta_preview(task, delta)

    assert preview["rule_terms"] == []
    assert preview["recall_term_overlays"][0]["conditional_terms_not_injected"][0]["term"] == "谋反"
    assert preview["preview_metadata"]["appended_rule_term_count"] == 0
    assert preview["preview_metadata"]["conditional_term_not_injected_count"] == 1
