from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable

import psycopg


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import object_pool_importer as importer  # noqa: E402
from scripts.dev import source_excerpt_pool as excerpts  # noqa: E402


@dataclass(frozen=True)
class AuditIssue:
    severity: str
    code: str
    emperor: str
    object_name: str
    src_key: str
    message: str
    detail: dict[str, Any]


def wikisource_title_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if not parsed.netloc.endswith("wikisource.org"):
        return ""
    path = urllib.parse.unquote(parsed.path).strip("/")
    for prefix in ("zh-hans/", "zh/", "wiki/"):
        if path.startswith(prefix):
            return path.removeprefix(prefix)
    return path


def _issue(
    severity: str,
    code: str,
    *,
    emperor: str,
    object_name: str = "",
    src_key: str = "",
    message: str,
    **detail: Any,
) -> AuditIssue:
    return AuditIssue(
        severity=severity,
        code=code,
        emperor=emperor,
        object_name=object_name,
        src_key=src_key,
        message=message,
        detail={key: value for key, value in detail.items() if value is not None},
    )


def _source_lookup(payload: importer.ImportPayload) -> dict[str, importer.SourceRow]:
    lookup: dict[str, importer.SourceRow] = {}
    for source in payload.sources:
        lookup[source.src_key] = source
    return lookup


def audit_payload_sources(
    payloads: tuple[importer.ImportPayload, ...],
    *,
    online: bool = False,
    fetch_text: Callable[[str], str] | None = None,
    dsn: str | None = None,
) -> dict[str, Any]:
    issues: list[AuditIssue] = []
    fetched_text: dict[str, str] = {}

    for payload in payloads:
        emperor_name = payload.emperor.name
        sources = _source_lookup(payload)
        seen_source_keys: set[str] = set()
        for source in payload.sources:
            if source.src_key in seen_source_keys:
                issues.append(
                    _issue(
                        "block",
                        "duplicate_src_key",
                        emperor=emperor_name,
                        src_key=source.src_key,
                        message="payload contains duplicate src_key",
                    )
                )
            seen_source_keys.add(source.src_key)
            if source.src_key.startswith("TODO") or source.src_key == "TODO-SRC-1":
                issues.append(
                    _issue(
                        "block",
                        "todo_src_key",
                        emperor=emperor_name,
                        src_key=source.src_key,
                        message="source key is still a TODO placeholder",
                    )
                )
            if not source.url:
                issues.append(
                    _issue(
                        "warning",
                        "missing_source_url",
                        emperor=emperor_name,
                        src_key=source.src_key,
                        message="source has no URL; online source-key audit cannot verify page text",
                    )
                )

        for obj in payload.objects:
            object_source_keys = {link.src_key for link in obj.links}
            for link in obj.links:
                source = sources.get(link.src_key)
                if source is None:
                    issues.append(
                        _issue(
                            "block",
                            "missing_source_definition",
                            emperor=emperor_name,
                            object_name=obj.name,
                            src_key=link.src_key,
                            message="object link references a source not defined in payload.sources",
                            rule_code=link.rule_code,
                            direction=link.direction,
                        )
                    )
                    continue
                title = wikisource_title_from_url(source.url)
                if source.url and not title:
                    issues.append(
                        _issue(
                            "warning",
                            "non_wikisource_url",
                            emperor=emperor_name,
                            object_name=obj.name,
                            src_key=source.src_key,
                            message="source URL is not a recognized Wikisource page",
                            url=source.url,
                        )
                    )
                if online and title and obj.obj_type == "person":
                    if title not in fetched_text:
                        try:
                            if fetch_text is None:
                                raise importer.ImportErrorWithContext("fetch_text is required for online audit")
                            fetched_text[title] = fetch_text(title)
                        except Exception as exc:  # pragma: no cover - live network path.
                            issues.append(
                                _issue(
                                    "warning",
                                    "source_fetch_failed",
                                    emperor=emperor_name,
                                    object_name=obj.name,
                                    src_key=source.src_key,
                                    message="failed to fetch Wikisource page text",
                                    page_title=title,
                                    error=repr(exc),
                                )
                            )
                            continue
                    terms = excerpts.derive_search_terms(obj.name) or (obj.name,)
                    if not any(term in fetched_text[title] for term in terms):
                        issues.append(
                            _issue(
                                "warning",
                                "object_terms_not_found",
                                emperor=emperor_name,
                                object_name=obj.name,
                                src_key=source.src_key,
                                message="object terms were not found in the linked Wikisource page text",
                                page_title=title,
                                terms=list(terms),
                            )
                        )
            for attr in obj.attrs:
                if attr.attr_code == "talent_quality" and attr.src_key not in object_source_keys:
                    issues.append(
                        _issue(
                            "block",
                            "talent_quality_source_not_linked",
                            emperor=emperor_name,
                            object_name=obj.name,
                            src_key=attr.src_key,
                            message="talent_quality source must also be linked on the same object",
                        )
                    )

    if dsn:
        issues.extend(_audit_db_source_conflicts(payloads, dsn=dsn))

    blocks = [issue for issue in issues if issue.severity == "block"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    return {
        "ok": not blocks,
        "block_count": len(blocks),
        "warning_count": len(warnings),
        "online": online,
        "issues": [asdict(issue) for issue in issues],
    }


def _audit_db_source_conflicts(payloads: tuple[importer.ImportPayload, ...], *, dsn: str) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            for payload in payloads:
                for obj in payload.objects:
                    for link in obj.links:
                        cur.execute(
                            """
                            select sd.src_key, os.id
                              from obj_srcs os
                              join emp_objs eo on eo.id = os.emp_obj_id
                              join emps e on e.id = eo.emp_id
                              join raw_objs ro on ro.id = eo.obj_id
                              join src_docs sd on sd.id = os.doc_id
                              join eval_rules er on er.id = os.rule_id
                             where e.name = %s
                               and ro.name = %s
                               and er.rule_code = %s
                               and os.direction = %s
                               and sd.src_key <> %s
                             order by os.id
                            """,
                            (payload.emperor.name, obj.name, link.rule_code, link.direction, link.src_key),
                        )
                        conflicts = [{"src_key": row[0], "obj_src_id": row[1]} for row in cur.fetchall()]
                        if conflicts:
                            issues.append(
                                _issue(
                                    "block",
                                    "existing_different_source_edge",
                                    emperor=payload.emperor.name,
                                    object_name=obj.name,
                                    src_key=link.src_key,
                                    message="database already has same object/rule/direction linked to different source key",
                                    rule_code=link.rule_code,
                                    direction=link.direction,
                                    conflicts=conflicts,
                                )
                            )
    return issues


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# I5B source-key audit",
        "",
        f"- ok: `{report['ok']}`",
        f"- online: `{report['online']}`",
        f"- blocks: `{report['block_count']}`",
        f"- warnings: `{report['warning_count']}`",
        "",
        "| 级别 | 代码 | 皇帝 | 对象 | src_key | 说明 |",
        "|---|---|---|---|---|---|",
    ]
    for issue in report["issues"]:
        lines.append(
            "| {severity} | {code} | {emperor} | {object_name} | {src_key} | {message} |".format(
                severity=issue["severity"],
                code=issue["code"],
                emperor=issue["emperor"],
                object_name=issue["object_name"],
                src_key=issue["src_key"],
                message=issue["message"],
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def write_report(path: Path, report: dict[str, Any], *, output_format: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return
    if output_format == "markdown":
        path.write_text(render_markdown(report), encoding="utf-8")
        return
    raise importer.ImportErrorWithContext(f"unknown output format: {output_format}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit I5B object payload source keys before import.")
    parser.add_argument("--input", type=Path, required=True, help="UTF-8 object payload JSON or payload batch.")
    parser.add_argument("--dsn-env", default=importer.DEFAULT_DSN_ENV, help="Environment variable name for PostgreSQL DSN.")
    parser.add_argument("--check-db", action="store_true", help="Check existing DB source edges for same object/rule/direction.")
    parser.add_argument("--online", action="store_true", help="Fetch linked Wikisource pages and check person terms.")
    parser.add_argument("--timeout", type=int, default=10, help="Network timeout in seconds for --online.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on-block", action="store_true")
    parser.add_argument("--fail-on-warning", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payloads = importer.load_payloads(args.input)
    dsn = importer.resolve_dsn(args.dsn_env) if args.check_db else None

    fetch_context: excerpts.FetchContext | None = None
    cache_store = None
    if args.online:
        cache_config = excerpts.load_source_excerpt_cache_config()
        api_cache, page_text_cache, cache_store, _report_config = excerpts.make_cache_backends(
            cache_config=cache_config,
            cache_dir=None,
            cache_enabled=None,
            cache_refresh=False,
        )
        fetch_context = excerpts.FetchContext(
            request_delay_seconds=excerpts.DEFAULT_REQUEST_DELAY_SECONDS,
            max_retries=1,
            retry_backoff_seconds=excerpts.DEFAULT_RETRY_BACKOFF_SECONDS,
            retry_events=[],
            api_cache=api_cache,
            page_text_cache=page_text_cache,
            max_retry_wait_seconds=5,
        )

    def fetch_text(title: str) -> str:
        return excerpts.fetch_wikisource_plain_text(title, timeout=args.timeout, fetch_context=fetch_context)

    try:
        report = audit_payload_sources(payloads, online=args.online, fetch_text=fetch_text if args.online else None, dsn=dsn)
    finally:
        if cache_store is not None:
            cache_store.close()

    if args.output:
        write_report(args.output, report, output_format=args.format)
    elif args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_markdown(report), end="")

    if args.fail_on_block and report["block_count"]:
        return 1
    if args.fail_on_warning and report["warning_count"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
