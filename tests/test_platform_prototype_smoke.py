from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform import platform_prototype_smoke


EXPECTED_CONTRACT_TOOLS = [
    "jsonl_staging_mapper",
    "jsonl_unknown_field_triage",
    "jsonl_staging_resolver_contract",
    "jsonl_query_search_target_mapper",
    "jsonl_sources_target_mapper",
    "jsonl_evidence_cards_target_mapper",
    "jsonl_evidence_clusters_resolver",
    "anchors_schema_proposal",
    "anchors_resolver_contract",
    "jsonl_anchors_target_mapper",
]
EXPECTED_APPLY_TOOLS = [
    "jsonl_query_search_target_mapper",
    "jsonl_sources_target_mapper",
    "jsonl_evidence_cards_target_mapper",
    "jsonl_evidence_clusters_resolver",
    "jsonl_anchors_target_mapper",
]
BLOCKED_REPORT_TERMS = ("score", "rank", "final_score", "leaderboard")
FORBIDDEN_PATHS = [
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "db" / "schema.sql",
    ROOT / "db" / "postgres" / "001_init.sql",
    ROOT / "exports" / "markdown_views",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]


def test_contract_matrix_is_offline_and_contains_all_prototype_reports(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in prototype smoke contract matrix")

    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError("contract matrix must not read .env")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(socket, "socket", fail_socket)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = platform_prototype_smoke.build_contract_matrix()

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["mode"] == "contract-matrix"
    assert report["tool_count"] == len(EXPECTED_CONTRACT_TOOLS)
    assert [tool["name"] for tool in report["tools"]] == EXPECTED_CONTRACT_TOOLS
    assert report["passed"] == EXPECTED_CONTRACT_TOOLS
    assert report["failed"] == []
    assert report["skipped"] == []
    assert report["reports_checked"] == len(EXPECTED_CONTRACT_TOOLS)
    assert report["blocked_terms_checked"] == {"count": 4, "passed": True}


def test_contract_matrix_output_contains_no_blocked_report_terms() -> None:
    text = platform_prototype_smoke.report_as_json(platform_prototype_smoke.build_contract_matrix()).lower()

    for term in BLOCKED_REPORT_TERMS:
        assert term not in text


def test_apply_matrix_without_dsn_skips_safely_and_uses_only_primary_dsn(monkeypatch) -> None:
    monkeypatch.delenv(platform_prototype_smoke.PRIMARY_ENV_DSN, raising=False)
    monkeypatch.setenv("PG_SEARCH_BENCH_DSN", "postgresql://legacy/db")

    report = platform_prototype_smoke.build_apply_matrix(schema_prefix="emperor_eval_smoke")

    assert report["mode"] == "apply-matrix"
    assert report["dsn_present"] is False
    assert [tool["name"] for tool in report["tools"]] == EXPECTED_APPLY_TOOLS
    assert report["passed"] == []
    assert report["failed"] == []
    assert [item["tool"] for item in report["skipped"]] == EXPECTED_APPLY_TOOLS
    assert report["all_schemas_dropped"] is True


def test_apply_matrix_schema_names_are_random_and_isolated() -> None:
    first = platform_prototype_smoke.build_schema_name("emperor_eval_smoke", "jsonl_sources_target_mapper")
    second = platform_prototype_smoke.build_schema_name("emperor_eval_smoke", "jsonl_sources_target_mapper")

    assert first != second
    assert first.startswith("emperor_eval_smoke_jsonl_sources_target_mapper_")
    assert second.startswith("emperor_eval_smoke_jsonl_sources_target_mapper_")


def test_apply_matrix_cli_prints_json_without_dsn(monkeypatch, capsys) -> None:
    monkeypatch.delenv(platform_prototype_smoke.PRIMARY_ENV_DSN, raising=False)

    assert (
        platform_prototype_smoke.main(
            ["--apply-matrix", "--schema-prefix", "emperor_eval_smoke", "--drop-schema-after"]
        )
        == 0
    )
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "apply-matrix"
    assert payload["dsn_present"] is False
    assert payload["failed"] == []


def test_smoke_source_uses_python_driver_path_not_psql_subprocess_or_legacy_dsn() -> None:
    source = (ROOT / "scripts" / "platform" / "platform_prototype_smoke.py").read_text(encoding="utf-8")

    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert platform_prototype_smoke.PRIMARY_ENV_DSN in source


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
