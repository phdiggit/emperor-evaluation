from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.jsonl_sources_target_mapper import (
    PRIMARY_ENV_DSN,
    ResolvedDsn,
    build_contract_report,
    check_environment,
    integration_skip_reason,
    main,
    report_as_json,
    resolve_dsn,
)


BLOCKED_REPORT_TERMS = ("score", "rank", "final_score", "leaderboard")
FORBIDDEN_PATHS = [
    ROOT / "data" / "batches",
    ROOT / "archive" / "data",
    ROOT / "db" / "schema.sql",
    ROOT / "exports" / "markdown_views",
    ROOT / "docs" / "皇帝综合评价体系评分标准.md",
    ROOT / "docs" / "分项规则",
    ROOT / "docs" / "证据规则",
]


def test_resolve_dsn_uses_only_primary_environment_value() -> None:
    assert resolve_dsn(env={PRIMARY_ENV_DSN: "postgresql://primary/db"}).source == f"env:{PRIMARY_ENV_DSN}"
    assert resolve_dsn(env={}).source == "skip"
    assert resolve_dsn(env={"PG_SEARCH_BENCH_DSN": "postgresql://legacy/db"}).source == "skip"


def test_check_without_dsn_or_driver_is_non_failing_and_does_not_connect(monkeypatch) -> None:
    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in sources target mapper contract tests")

    monkeypatch.setattr(socket, "socket", fail_socket)
    result = check_environment(ResolvedDsn(None, "skip"), driver_available=False)

    assert result["mode"] == "check"
    assert result["dsn_present"] is False
    assert result["dsn_source"] == "skip"
    assert result["driver"] == "psycopg"
    assert result["driver_available"] is False
    assert result["default_tests_require_postgres"] is False
    assert result["will_apply"] is False


def test_apply_skip_reason_requires_primary_dsn_and_python_driver() -> None:
    assert integration_skip_reason(ResolvedDsn(None, "skip"), driver_available=True) == f"{PRIMARY_ENV_DSN} is not set"
    assert integration_skip_reason(ResolvedDsn("postgresql://example/db", f"env:{PRIMARY_ENV_DSN}"), driver_available=False) == (
        "psycopg is not installed"
    )


def test_contract_report_is_offline_and_has_required_shape(monkeypatch, tmp_path: Path) -> None:
    fixture_root = _write_fixture_root(tmp_path)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in sources target mapper contract tests")

    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError("contract report must not read .env")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(socket, "socket", fail_socket)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    report = build_contract_report(source_root=fixture_root)

    assert report["mode"] == "contract-report"
    assert report["target_tables"] == ["src_hosts", "src_docs", "doc_revs", "passages"]
    assert report["source_files"] == ["data/sources.jsonl"]
    assert report["rows_by_source_file"]["data/sources.jsonl"] == 2
    assert report["candidate_rows_by_target"] == {
        "src_hosts": 1,
        "src_docs": 2,
        "doc_revs": 2,
        "passages": 1,
    }
    assert report["host_resolution_plan"]["inferred_host_candidate_rows"] == 1


def test_default_contract_paths_do_not_read_batches_archive_env_or_touch_forbidden_paths(monkeypatch) -> None:
    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        parts = tuple(self.parts)
        if "batches" in parts or ("archive" in parts and "data" in parts):
            raise AssertionError(f"forbidden path read: {self}")
        if self.name == ".env":
            raise AssertionError("contract report must not read .env")
        return original_read_text(self, *args, **kwargs)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in sources target mapper contract tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = build_contract_report(source_root=ROOT)

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["source_files"] == ["data/sources.jsonl"]
    assert report["candidate_rows_by_target"]["src_docs"] > 0
    assert report["candidate_rows_by_target"]["doc_revs"] > 0


def test_source_id_enters_document_plan_not_passage_fk(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))

    assert report["document_resolution_plan"]["source_id_target"] == "src_docs.code"
    assert report["document_resolution_plan"]["source_id_is_passage_id"] is False
    passage_plan = report["direct_field_plan"]["passages"]["source_id"]
    assert passage_plan["target_column"] == "source_document_resolver_input_only"
    blocked = {item["field"]: item for item in report["blocked_relationship_writes"]}
    assert blocked["source_id"]["blocked_action"] == "passage_id_write_or_evd_src_links_write"


def test_source_fields_enter_expected_target_plans(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))

    docs_plan = report["direct_field_plan"]["src_docs"]
    hosts_plan = report["direct_field_plan"]["src_hosts"]
    assert docs_plan["title"]["target_column"] == "src_docs.title"
    assert docs_plan["source_title"]["target_column"] == "src_docs.title"
    assert docs_plan["url"]["target_column"] == "src_docs.canon_url"
    assert docs_plan["source_url"]["target_column"] == "src_docs.canon_url"
    assert docs_plan["host"]["target_column"] == "src_docs.host_code candidate"
    assert docs_plan["source_host"]["target_column"] == "src_docs.host_code candidate"
    assert hosts_plan["host"]["target_column"] == "src_hosts.code"
    assert hosts_plan["source_host"]["target_column"] == "src_hosts.code"


def test_text_payload_behavior_is_locked_to_doc_rev_and_unreviewed_passage_candidate(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))

    assert report["payload_field_plan"]["doc_revs"] == ["raw_text", "excerpt", "quote", "context", "meta", "notes", "note"]
    assert report["passage_candidate_plan"]["text_fields"] == ["quote", "excerpt"]
    assert report["passage_candidate_plan"]["raw_text_behavior"] == "doc_revs_payload_only_unless_reviewed_later"
    assert report["passage_candidate_plan"]["passage_candidate_status"] == "unreviewed_candidate"
    blocked = {item["field"]: item for item in report["blocked_relationship_writes"]}
    assert blocked["quote/context/excerpt/raw_text"]["blocked_action"] == "evidence_relationship_write"


def test_report_never_targets_forbidden_business_tables(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))
    text = report_as_json(report)

    for table in (
        "query_profiles",
        "search_tasks",
        "search_hits",
        "cand_matches",
        "evd_cards",
        "evd_src_links",
        "clusters",
        "cluster_evd",
        "review_items",
        "anchors",
        "anchor_links",
        "score_records",
        "score_releases",
        "adjudications",
    ):
        assert table not in report["target_tables"]
    assert "evd_src_links" in text
    assert "passages" in report["target_tables"]


def test_contract_report_contains_no_scoring_or_ranking_terms(tmp_path: Path) -> None:
    text = report_as_json(build_contract_report(source_root=_write_fixture_root(tmp_path)))

    for term in BLOCKED_REPORT_TERMS:
        assert term not in text


def test_contract_report_cli_prints_json_without_connecting(monkeypatch, capsys, tmp_path: Path) -> None:
    fixture_root = _write_fixture_root(tmp_path)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in sources target mapper contract tests")

    monkeypatch.setattr(socket, "socket", fail_socket)

    assert main(["--contract-report", "--source-root", str(fixture_root)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "contract-report"
    assert payload["candidate_rows_by_target"] == {
        "src_hosts": 1,
        "src_docs": 2,
        "doc_revs": 2,
        "passages": 1,
    }


def test_target_mapper_uses_python_driver_not_psql_subprocess_or_legacy_dsn() -> None:
    source = (ROOT / "scripts" / "platform" / "jsonl_sources_target_mapper.py").read_text(encoding="utf-8")

    assert "import subprocess" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "import psycopg" in source


def _write_fixture_root(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_jsonl(
        data_dir / "sources.jsonl",
        [
            {
                "source_id": "SRC-SOURCES-TARGET-001",
                "title": "资治通鉴",
                "url": "https://zh.wikisource.org/wiki/example",
                "host": "wikisource",
                "quote": "帝召见群臣。",
                "context": "测试上下文",
                "raw_text": "帝召见群臣。旁文留作修订 payload。",
                "volume": "卷一",
                "location": "本纪",
            },
            {
                "source_id": "SRC-SOURCES-TARGET-002",
                "source_title": "后汉书",
                "source_url": "https://example.test/source",
                "raw_text": "只有 raw_text 的 source 不自动生成 passage。",
                "excerpt": "",
            },
        ],
    )
    _write_jsonl(data_dir / "query_profiles.jsonl", [{"query_profile_id": "QRY-IGNORED-001"}])
    return tmp_path


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
