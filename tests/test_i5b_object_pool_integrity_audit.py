from __future__ import annotations

from scripts.dev import i5b_object_pool_integrity_common as audit
from scripts.dev import i5b_object_pool_integrity_core as core


def test_missing_required_alias_table_is_error() -> None:
    issues = audit._missing_table_issues({"raw_objs": 1, "emp_objs": 1, "obj_srcs": 1})

    alias_issue = next(issue for issue in issues if issue["table"] == "raw_obj_aliases")
    assert alias_issue["severity"] == "error"
    assert alias_issue["status"] == "missing_required_table"


def test_report_summarizes_table_issues() -> None:
    report = audit.build_report_from_counts(
        table_counts={"raw_objs": 3, "obj_srcs": 4},
        issues=[
            {
                "table": "raw_objs",
                "status": "raw_object_without_source_link",
                "severity": "error",
                "message": "missing source",
                "count": 1,
            },
            {
                "table": "obj_srcs",
                "status": "ambiguous_source_note",
                "severity": "warning",
                "message": "ambiguous note",
                "count": 2,
            },
        ],
        generated_at="2026-07-04T00:00:00+08:00",
    )

    assert report["ok"] is False
    assert report["error_count"] == 1
    assert report["warning_count"] == 1
    raw_summary = next(row for row in report["tables"] if row["table"] == "raw_objs")
    assert raw_summary["rows"] == 3
    assert raw_summary["errors"] == 1
    missing_alias = next(row for row in report["tables"] if row["table"] == "raw_obj_aliases")
    assert missing_alias["exists"] is False


def test_render_markdown_includes_samples() -> None:
    report = audit.build_report_from_counts(
        table_counts={"raw_objs": 1},
        issues=[
            {
                "table": "raw_objs",
                "status": "raw_note_contains_scoring_terms",
                "severity": "error",
                "message": "bad note",
                "count": 1,
                "sample_rows": [{"id": 10, "name": "甲臣", "note": "正向评分"}],
            }
        ],
        generated_at="2026-07-04T00:00:00+08:00",
    )

    markdown = audit.render_markdown(report)

    assert "# I5B 对象池完整性审计" in markdown
    assert "| error | raw_objs | raw_note_contains_scoring_terms | 1 | bad note |" in markdown
    assert "id=10; name=甲臣; note=正向评分" in markdown


def test_all_checks_excludes_alias_checks_when_table_missing() -> None:
    checks = audit.all_checks({"raw_objs": 1, "obj_srcs": 1})

    assert all(check.table != "raw_obj_aliases" for check in checks)
    assert any(check.status == "raw_object_without_source_link" for check in checks)


def test_raw_object_checks_include_pre_alias_conflict_gate() -> None:
    checks = core.raw_object_checks({"raw_objs": 1})

    conflict_check = next(check for check in checks if check.status == "canonical_alias_key_conflict")
    assert conflict_check.table == "raw_objs"
    assert conflict_check.severity == "error"
    assert "raw_obj_aliases" in conflict_check.hint
