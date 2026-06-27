from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import g10_script_asset_risk_governance as governance  # noqa: E402


FORBIDDEN_PATHS = [
    ROOT / ".env",
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "exports",
]


def test_script_delta_report_declares_g10_3_scope_and_boundaries() -> None:
    report = governance.build_script_delta_report()

    assert report["mode"] == "script-delta-report"
    assert report["package_version"] == "g10-script-asset-risk-governance-v1"
    assert report["roadmap_issue"] == 287
    assert report["epic_issue"] == 312
    assert report["plan_issue"] == 331
    assert report["script_governance_issue"] == 334
    assert report["prerequisite_pr"] == 338
    assert report["prerequisite_merge_commit"] == governance.PREREQUISITE_MERGE_COMMIT
    assert report["does_not_read_dotenv"] is True
    assert report["does_not_connect_database"] is True
    assert report["does_not_access_network"] is True
    assert report["does_not_read_batch_payloads"] is True
    assert report["does_not_read_generated_exports"] is True
    assert report["does_not_move_delete_or_archive_files"] is True
    assert report["does_not_publish_scores"] is True
    assert report["does_not_publish_rankings"] is True


def test_script_delta_current_state_records_acceptance_outcomes() -> None:
    state = governance.build_script_delta_report()["current_state"]

    assert state["current_phase"] == "g10_script_asset_risk_governance_ready"
    assert state["g10_3_script_asset_risk_governance_ready"] is True
    assert state["g10_script_asset_risk_governance_package"] == "g10-script-asset-risk-governance-v1"
    assert state["transitional_scripts_without_sunset"] == 0
    assert state["retired_scripts_in_default_validate_or_public_cli"] == 0
    assert state["duplicate_capability_groups_reviewed"] >= 5
    assert state["duplicate_capability_groups_without_reason"] == 0
    assert state["script_delta_ready_for_roadmap_comments"] is True
    assert state["outcome_verification_tests_added"] is True
    assert state["g10_destructive_cleanup_started"] is False
    assert state["stage_or_final_total_table_released"] is False
    assert state["cross_subitem_leaderboard_released"] is False


def test_registry_analysis_covers_lifecycle_default_routes_and_duplicate_reasons() -> None:
    analysis = governance.build_script_delta_report()["scripts_registry_analysis"]

    assert analysis["platform_module_count"] >= 80
    assert analysis["transitional_scripts_without_sunset"] == []
    assert analysis["default_validate_retired_script_references"] == []
    assert analysis["retired_public_cli_modules"] == []
    assert analysis["retired_scripts_in_default_validate_or_public_cli"] == 0
    assert analysis["platform_lifecycle_status_counts"]["transitional"] == 4
    assert analysis["platform_lifecycle_status_counts"].get("retired", 0) == 0
    assert analysis["public_cli_stable_count"] > 0

    reviews = {item["group_id"]: item for item in analysis["duplicate_capability_review"]}
    assert set(reviews) == {
        "gate_approval_preflight",
        "report_publication_packages",
        "redaction_fingerprint_helpers",
        "evidence_mapping_resolver_family",
        "schema_migration_seed_scaffolds",
    }
    assert all(item["retain_or_consolidation_reason"] for item in reviews.values())
    assert reviews["gate_approval_preflight"]["module_count"] > 1
    assert reviews["schema_migration_seed_scaffolds"]["decision"] == "retain_with_reason"
    assert reviews["redaction_fingerprint_helpers"]["decision"] == "already_consolidated"


def test_registry_analysis_flags_bad_fixture_outcomes() -> None:
    registry = {
        "platform_modules": [
            {
                "implementation": "scripts/platform/transitional_without_sunset.py",
                "capability": "temporary scaffold",
                "lifecycle_status": "transitional",
                "epic_owner": "Epic X",
                "risk_class": "medium",
                "replacement": "scripts/platform/replacement.py",
                "sunset_milestone": "",
                "last_required_by": "#0",
                "public_cli_stable": False,
            },
            {
                "implementation": "scripts/platform/retired_public.py",
                "capability": "old public cli",
                "lifecycle_status": "retired",
                "epic_owner": "Epic X",
                "risk_class": "high",
                "replacement": "scripts/platform/replacement.py",
                "sunset_milestone": None,
                "last_required_by": "#0",
                "public_cli_stable": True,
            },
        ],
        "retired_legacy_wrappers": {
            "scripts/old_wrapper.py": "old_wrapper",
        },
    }
    analysis = governance.analyze_scripts_registry(
        registry,
        {"scripts/validate/validate_all.py": "python scripts/old_wrapper.py"},
    )

    assert analysis["transitional_scripts_without_sunset"] == [
        "scripts/platform/transitional_without_sunset.py"
    ]
    assert analysis["retired_public_cli_modules"] == ["scripts/platform/retired_public.py"]
    assert analysis["default_validate_retired_script_references"] == [
        {
            "entrypoint": "scripts/validate/validate_all.py",
            "retired_path": "scripts/old_wrapper.py",
        }
    ]
    assert analysis["retired_scripts_in_default_validate_or_public_cli"] == 2


def test_outcome_verification_delta_tracks_issue_334_inventory_candidate() -> None:
    report = governance.build_script_delta_report()

    assert [item["asset_id"] for item in report["issue_334_inventory_candidates"]] == [
        "scripts_registry_lifecycle_entries",
        "mirror_and_report_text_tests",
    ]
    deltas = {item["asset_id"]: item for item in report["outcome_verification_delta"]}
    assert deltas["mirror_and_report_text_tests"]["outcome_verification_added"] is True
    assert deltas["mirror_and_report_text_tests"]["text_mirror_only"] is False
    assert "structured registry analysis" in deltas["mirror_and_report_text_tests"]["proof"]


def test_changed_paths_and_script_delta_targets_are_manifested() -> None:
    report = governance.build_script_delta_report()

    assert set(report["changed_paths_manifest"]) == set(governance.PACKAGE_CHANGED_PATHS)
    assert "scripts/platform/g10_script_asset_risk_governance.py" in report["changed_paths_manifest"]
    assert report["script_delta_targets"] == [287, 312, 331, 334]


def test_default_script_delta_report_is_side_effect_free(monkeypatch) -> None:
    original_read_text = Path.read_text
    allowed_reads = {
        governance.inventory_plan.SCRIPT_REGISTRY_PATH.resolve(),
        *(path.resolve() for path in governance.DEFAULT_VALIDATE_ENTRYPOINTS),
    }

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        path = self.resolve()
        parts = tuple(path.parts)
        if path not in allowed_reads:
            if (
                path.name == ".env"
                or "batches" in parts
                or ("archive" in parts and "data" in parts)
                or "exports" in parts
            ):
                raise AssertionError(f"forbidden payload/content read: {path}")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in G10-3 script governance tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = governance.build_script_delta_report()
    markdown = governance.render_script_delta_md()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["default_modes_side_effect_free"] is True
    assert "G10 Script Asset Risk Governance" in markdown
    assert "gate_approval_preflight" in markdown


def test_cli_modes_emit_expected_outputs(capsys) -> None:
    assert governance.main(["--script-delta-report"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["current_state"]["transitional_scripts_without_sunset"] == 0

    assert governance.main(["--script-delta-md"]) == 0
    markdown = capsys.readouterr().out
    assert "schema_migration_seed_scaffolds" in markdown
    assert "issue335_g10_completion_verification_and_roadmap_handoff" in markdown


def test_source_does_not_import_runtime_or_secret_clients() -> None:
    source = (ROOT / "scripts" / "platform" / "g10_script_asset_risk_governance.py").read_text(
        encoding="utf-8"
    )

    assert "import psycopg" not in source
    assert "import pika" not in source
    assert "aio_pika" not in source
    assert "import requests" not in source
    assert "subprocess.run" not in source
    assert "EMPEROR_EVAL_PG_DSN" not in source
    assert "PG_SEARCH_BENCH_DSN" not in source


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
