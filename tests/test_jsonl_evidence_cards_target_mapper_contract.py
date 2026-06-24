from __future__ import annotations

import json
import socket
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.platform.jsonl_evidence_cards_target_mapper import (
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
        raise AssertionError("network access is forbidden in evidence_cards target mapper contract tests")

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
        raise AssertionError("network access is forbidden in evidence_cards target mapper contract tests")

    original_read_text = Path.read_text

    def guarded_read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self.name == ".env":
            raise AssertionError("contract report must not read .env")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(socket, "socket", fail_socket)
    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    report = build_contract_report(source_root=fixture_root)

    assert report["mode"] == "contract-report"
    assert report["target_tables"] == ["evd_cards"]
    assert report["source_files"] == ["data/evidence_cards.jsonl"]
    assert report["rows_by_source_file"]["data/evidence_cards.jsonl"] == 2
    assert report["candidate_rows_by_target"] == {"evd_cards": 2}


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
        raise AssertionError("network access is forbidden in evidence_cards target mapper contract tests")

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    monkeypatch.setattr(socket, "socket", fail_socket)
    before = {path: _mtime(path) for path in FORBIDDEN_PATHS}

    report = build_contract_report(source_root=ROOT)

    after = {path: _mtime(path) for path in FORBIDDEN_PATHS}
    assert after == before
    assert report["source_files"] == ["data/evidence_cards.jsonl"]
    assert report["candidate_rows_by_target"]["evd_cards"] > 0


def test_evidence_id_enters_evd_cards_code_plan(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))

    plan = report["direct_field_plan"]["evidence_id"]
    assert plan["target_column"] == "evd_cards.code"
    assert plan["present"] is True


def test_person_item_and_subitem_do_not_write_fks_or_relationships(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))

    blocked = {item["field"]: item for item in report["resolver_blocked_fields"]["data/evidence_cards.jsonl"]}
    assert blocked["person"]["blocked_action"] == "direct_person_id_write"
    assert blocked["item"]["blocked_action"] == "subitem_fk_or_evidence_relationship_write"
    assert blocked["subitem"]["blocked_action"] == "subitem_fk_or_evidence_relationship_write"


def test_source_id_and_linked_sources_do_not_write_source_links(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))

    assert report["source_link_plan"]["source_id_is_passage_id"] is False
    assert report["source_link_plan"]["candidate_passage_status"] == "unreviewed_candidate"
    assert report["source_link_plan"]["blocked_action"] == "evd_src_links_write"
    blocked = {item["target_table"]: item for item in report["blocked_relationship_writes"]}
    assert blocked["evd_src_links"]["line_numbers"] == [1, 2]


def test_quote_candidate_does_not_prove_evidence_source_relationship(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))

    assert report["source_link_plan"]["quote_candidate_rows"] == [1]
    blocked = {item["target_table"]: item for item in report["blocked_relationship_writes"]}
    assert blocked["evd_src_links"]["allowed_action"] == "report_only_until_reviewed_passage_span_exists"


def test_cluster_fields_do_not_write_cluster_evd(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))

    assert report["cluster_link_plan"]["blocked_action"] == "cluster_evd_write"
    blocked = {item["target_table"]: item for item in report["blocked_relationship_writes"]}
    assert blocked["cluster_evd"]["line_numbers"] == [1, 2]


def test_object_anchor_does_not_write_anchors_or_anchor_links(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))

    assert report["anchor_link_plan"]["blocked_action"] == "anchors_or_anchor_links_write"
    blocked = {item["target_table"]: item for item in report["blocked_relationship_writes"]}
    assert blocked["anchors_or_anchor_links"]["line_numbers"] == [1]


def test_cluster_role_and_evidence_role_remain_manual_review(tmp_path: Path) -> None:
    report = build_contract_report(source_root=_write_fixture_root(tmp_path))

    manual = {item["field"]: item for item in report["manual_review_fields_by_file"]["data/evidence_cards.jsonl"]}
    assert manual["cluster_role"]["reason"].startswith("manual_review required")
    assert manual["evidence_role"]["reason"].startswith("manual_review required")


def test_contract_report_contains_no_scoring_or_ranking_terms(tmp_path: Path) -> None:
    text = report_as_json(build_contract_report(source_root=_write_fixture_root(tmp_path)))

    for term in BLOCKED_REPORT_TERMS:
        assert term not in text


def test_contract_report_cli_prints_json_without_connecting(monkeypatch, capsys, tmp_path: Path) -> None:
    fixture_root = _write_fixture_root(tmp_path)

    def fail_socket(*args: object, **kwargs: object) -> socket.socket:
        raise AssertionError("network access is forbidden in evidence_cards target mapper contract tests")

    monkeypatch.setattr(socket, "socket", fail_socket)

    assert main(["--contract-report", "--source-root", str(fixture_root)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["mode"] == "contract-report"
    assert payload["candidate_rows_by_target"] == {"evd_cards": 2}


def test_target_mapper_uses_python_driver_not_psql_subprocess_or_legacy_dsn() -> None:
    source = (ROOT / "scripts" / "platform" / "jsonl_evidence_cards_target_mapper.py").read_text(encoding="utf-8")

    assert "import subprocess" not in source
    assert "subprocess.run" not in source
    assert '"psql"' not in source
    assert "PG_SEARCH_BENCH_DSN" not in source
    assert "import psycopg" in source


def _write_fixture_root(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_jsonl(
        data_dir / "evidence_cards.jsonl",
        [
            {
                "evidence_id": "EVD-CARDS-TARGET-001",
                "person": "测试皇帝",
                "item": "第五项",
                "subitem": "第五项B",
                "source_id": "SRC-CARDS-TARGET-001",
                "linked_source_ids": ["SRC-CARDS-TARGET-001"],
                "quote_short": "帝召见群臣。",
                "polarity": "positive",
                "verification_status": "source_verified",
                "adjudication_status": "pending_human_adjudication",
                "notes": "只作 payload。",
                "object_anchor": "测试锚点",
                "cluster_role": "core",
                "evidence_role": "primary",
                "linked_cluster_ids": ["CLUSTER-CARDS-TARGET-001"],
                "trigger_family": "测试触发",
                "trigger_terms": ["召见"],
                "mitigation_flag": "",
                "upper_bound_flag": "diagnostic",
            },
            {
                "evidence_id": "EVD-CARDS-TARGET-002",
                "person": "测试皇帝",
                "item": "第五项",
                "subitem": "第五项B",
                "source_id": "SRC-CARDS-TARGET-002",
                "linked_source_ids": ["SRC-CARDS-TARGET-002"],
                "polarity": "negative",
                "verification_status": "source_verified",
                "adjudication_status": "pending_human_adjudication",
                "cluster_candidate_id": "CLUSTER-CARDS-TARGET-002",
                "case_classification": "测试分类",
                "risk_status": "candidate",
                "mitigating_factors": [],
                "aggravating_factors": [],
                "reversal_or_rehabilitation": "",
            },
        ],
    )
    _write_jsonl(data_dir / "sources.jsonl", [{"source_id": "SRC-IGNORED-001"}])
    return tmp_path


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def _mtime(path: Path) -> int | None:
    if not path.exists():
        return None
    return path.stat().st_mtime_ns
