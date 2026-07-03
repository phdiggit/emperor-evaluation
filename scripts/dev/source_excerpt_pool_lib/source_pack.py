from __future__ import annotations

import json
import hashlib
import re
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from .common import ExcerptPoolError, compact_text, read_jsonl


SOURCE_PACK_SCHEMA_VERSION = 1
SOURCE_PACK_MANIFEST = "manifest.json"
SOURCE_PACK_DOCS = "src_docs.jsonl"
SOURCE_PACK_EXCERPTS = "excerpts.jsonl"
TEXT_PATH_FIELDS = ("text_path", "page_text_path")
TEXT_FIELDS = ("text", "raw_text", "normalized_text")
KNOWN_FETCH_STATUSES = {"fetched", "cached", "manual", "missing", "error"}
KNOWN_REVIEW_STATUSES = {"pending", "accepted", "rejected", "needs_review"}


@dataclass(frozen=True)
class SourcePackIssue:
    severity: str
    code: str
    path: str
    line: int | None
    src_key: str
    message: str
    detail: dict[str, Any]


@dataclass(frozen=True)
class SourcePackDocument:
    src_key: str
    page_title: str
    page_url: str
    text: str


@dataclass(frozen=True)
class SourcePackExcerpt:
    object_name: str
    layer: str
    query: str
    page_title: str
    page_url: str
    matched_term: str
    text: str
    src_key: str


class SourcePackPageCache:
    enabled = True
    refresh = False

    def __init__(self, docs: Iterable[SourcePackDocument]):
        self._pages: dict[str, str] = {}
        for doc in docs:
            self._pages.setdefault(doc.page_title, doc.text)

    def iter_pages(self) -> Iterable[tuple[str, str]]:
        for title in sorted(self._pages):
            yield title, self._pages[title]


def source_key_from_page_title(page_title: str) -> str:
    digest = hashlib.sha1(page_title.encode("utf-8")).hexdigest()[:10].upper()
    return f"SRC-WS-{digest}"


def split_page_title(page_title: str) -> tuple[str, str]:
    parts = re.split(r"[/／]", page_title, maxsplit=1)
    title = parts[0].strip()
    volume = parts[1].strip() if len(parts) > 1 else ""
    return title, volume


def wikisource_title_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if not parsed.netloc.endswith("wikisource.org"):
        return ""
    path = urllib.parse.unquote(parsed.path).strip("/")
    for prefix in ("zh-hans/", "zh-hant/", "zh/", "wiki/"):
        if path.startswith(prefix):
            return path.removeprefix(prefix)
    return path


def page_title_from_doc(row: dict[str, Any]) -> str:
    for key in ("page_title", "wikisource_title", "locator"):
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return wikisource_title_from_url(str(row.get("url") or ""))


def _issue(
    severity: str,
    code: str,
    *,
    path: Path,
    line: int | None = None,
    src_key: str = "",
    message: str,
    **detail: Any,
) -> SourcePackIssue:
    return SourcePackIssue(
        severity=severity,
        code=code,
        path=str(path),
        line=line,
        src_key=src_key,
        message=message,
        detail={key: value for key, value in detail.items() if value not in (None, "", [])},
    )


def _read_json(path: Path, issues: list[SourcePackIssue]) -> dict[str, Any]:
    if not path.exists():
        issues.append(_issue("block", "missing_manifest", path=path, message="source pack manifest.json is missing"))
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        issues.append(_issue("block", "invalid_manifest_json", path=path, message="manifest.json is not valid JSON", error=str(exc)))
        return {}
    if not isinstance(value, dict):
        issues.append(_issue("block", "invalid_manifest_type", path=path, message="manifest.json must be a JSON object"))
        return {}
    return value


def _read_jsonl_for_audit(path: Path, issues: list[SourcePackIssue], *, required: bool) -> list[tuple[int, dict[str, Any]]]:
    if not path.exists():
        if required:
            issues.append(_issue("block", "missing_jsonl", path=path, message=f"{path.name} is missing"))
        return []
    rows: list[tuple[int, dict[str, Any]]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(
                _issue("block", "invalid_jsonl", path=path, line=line_number, message="line is not valid JSON", error=str(exc))
            )
            continue
        if not isinstance(value, dict):
            issues.append(_issue("block", "invalid_jsonl_type", path=path, line=line_number, message="line must be a JSON object"))
            continue
        rows.append((line_number, value))
    return rows


def _safe_relative_path(pack_dir: Path, raw_path: str, *, label: str) -> Path:
    path = Path(raw_path)
    candidate = path if path.is_absolute() else pack_dir / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(pack_dir.resolve())
    except ValueError as exc:
        raise ExcerptPoolError(f"{label} escapes source pack directory: {raw_path}") from exc
    return resolved


def _inline_text(row: dict[str, Any]) -> str:
    for key in TEXT_FIELDS:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def read_doc_text(pack_dir: Path, row: dict[str, Any]) -> str:
    inline = _inline_text(row)
    if inline:
        return inline
    for key in TEXT_PATH_FIELDS:
        value = str(row.get(key) or "").strip()
        if not value:
            continue
        path = _safe_relative_path(pack_dir, value, label=key)
        if not path.exists():
            raise ExcerptPoolError(f"{key} does not exist: {value}")
        return path.read_text(encoding="utf-8")
    return ""


def load_source_pack_documents(pack_dir: Path) -> list[SourcePackDocument]:
    pack_dir = pack_dir.resolve()
    rows = read_jsonl(pack_dir / SOURCE_PACK_DOCS)
    docs: list[SourcePackDocument] = []
    for row in rows:
        src_key = str(row.get("src_key") or "").strip()
        page_title = page_title_from_doc(row)
        if not src_key or not page_title:
            raise ExcerptPoolError(f"{SOURCE_PACK_DOCS}: src_key and page_title/locator/url are required")
        text = compact_text(read_doc_text(pack_dir, row))
        if not text:
            raise ExcerptPoolError(f"{SOURCE_PACK_DOCS}: {src_key} has no local text")
        docs.append(
            SourcePackDocument(
                src_key=src_key,
                page_title=page_title,
                page_url=str(row.get("url") or ""),
                text=text,
            )
        )
    return docs


def load_source_pack_excerpts(pack_dir: Path) -> list[SourcePackExcerpt]:
    pack_dir = pack_dir.resolve()
    if not (pack_dir / SOURCE_PACK_EXCERPTS).exists():
        return []
    docs_by_key = {
        row.get("src_key"): row
        for row in read_jsonl(pack_dir / SOURCE_PACK_DOCS)
        if isinstance(row.get("src_key"), str) and row.get("src_key")
    }
    excerpts: list[SourcePackExcerpt] = []
    for row in read_jsonl(pack_dir / SOURCE_PACK_EXCERPTS):
        object_name = str(row.get("object_name") or "").strip()
        text = str(row.get("quote") or row.get("text") or "").strip()
        src_key = str(row.get("src_key") or "").strip()
        if not object_name or not text:
            continue
        src_doc = docs_by_key.get(src_key, {})
        page_title = str(row.get("page_title") or page_title_from_doc(src_doc) or "").strip()
        if not page_title:
            continue
        excerpts.append(
            SourcePackExcerpt(
                object_name=object_name,
                layer=str(row.get("layer") or "").strip(),
                query=str(row.get("query") or "").strip(),
                page_title=page_title,
                page_url=str(row.get("page_url") or src_doc.get("url") or "").strip(),
                matched_term=str(row.get("matched_term") or object_name).strip(),
                text=compact_text(text),
                src_key=src_key,
            )
        )
    return excerpts


def audit_source_pack(pack_dir: Path) -> dict[str, Any]:
    pack_dir = pack_dir.resolve()
    issues: list[SourcePackIssue] = []
    if not pack_dir.exists() or not pack_dir.is_dir():
        issues.append(_issue("block", "missing_pack_dir", path=pack_dir, message="source pack directory does not exist"))
        return _build_report(pack_dir, {}, [], [], issues)

    manifest = _read_json(pack_dir / SOURCE_PACK_MANIFEST, issues)
    schema_version = manifest.get("schema_version")
    if schema_version != SOURCE_PACK_SCHEMA_VERSION:
        issues.append(
            _issue(
                "block",
                "unsupported_schema_version",
                path=pack_dir / SOURCE_PACK_MANIFEST,
                message=f"schema_version must be {SOURCE_PACK_SCHEMA_VERSION}",
                actual=schema_version,
            )
        )
    for key in ("pack_id", "created_at", "source_scope", "status"):
        if not str(manifest.get(key) or "").strip():
            issues.append(_issue("warning", "missing_manifest_field", path=pack_dir / SOURCE_PACK_MANIFEST, message=f"manifest.{key} is empty", field=key))

    doc_rows = _read_jsonl_for_audit(pack_dir / SOURCE_PACK_DOCS, issues, required=True)
    excerpt_rows = _read_jsonl_for_audit(pack_dir / SOURCE_PACK_EXCERPTS, issues, required=False)
    if not doc_rows and not any(issue.code == "missing_jsonl" for issue in issues):
        issues.append(_issue("block", "empty_src_docs", path=pack_dir / SOURCE_PACK_DOCS, message="src_docs.jsonl has no rows"))

    src_keys: set[str] = set()
    page_titles: set[str] = set()
    for line_number, row in doc_rows:
        src_key = str(row.get("src_key") or "").strip()
        src_path = pack_dir / SOURCE_PACK_DOCS
        if not src_key:
            issues.append(_issue("block", "missing_src_key", path=src_path, line=line_number, message="src_doc.src_key is empty"))
        elif src_key in src_keys:
            issues.append(_issue("block", "duplicate_src_key", path=src_path, line=line_number, src_key=src_key, message="duplicate src_key in source pack"))
        else:
            src_keys.add(src_key)
        if src_key.startswith("TODO"):
            issues.append(_issue("block", "todo_src_key", path=src_path, line=line_number, src_key=src_key, message="src_key is still a TODO placeholder"))

        page_title = page_title_from_doc(row)
        if not page_title:
            issues.append(_issue("block", "missing_page_title", path=src_path, line=line_number, src_key=src_key, message="page_title/locator/url cannot identify a page"))
        elif page_title in page_titles:
            issues.append(_issue("warning", "duplicate_page_title", path=src_path, line=line_number, src_key=src_key, message="multiple src_docs share one page title", page_title=page_title))
        else:
            page_titles.add(page_title)

        for field in ("title", "author", "dynasty", "url"):
            if not str(row.get(field) or "").strip():
                issues.append(_issue("warning", f"missing_{field}", path=src_path, line=line_number, src_key=src_key, message=f"src_doc.{field} is empty"))
        fetch_status = str(row.get("fetch_status") or "").strip()
        if fetch_status and fetch_status not in KNOWN_FETCH_STATUSES:
            issues.append(_issue("warning", "unknown_fetch_status", path=src_path, line=line_number, src_key=src_key, message="fetch_status is not in the known status set", fetch_status=fetch_status))
        review_status = str(row.get("review_status") or "").strip()
        if review_status and review_status not in KNOWN_REVIEW_STATUSES:
            issues.append(_issue("warning", "unknown_review_status", path=src_path, line=line_number, src_key=src_key, message="review_status is not in the known status set", review_status=review_status))

        try:
            text = compact_text(read_doc_text(pack_dir, row))
        except ExcerptPoolError as exc:
            issues.append(_issue("block", "source_text_unreadable", path=src_path, line=line_number, src_key=src_key, message=str(exc)))
            continue
        if not text:
            issues.append(_issue("block", "missing_source_text", path=src_path, line=line_number, src_key=src_key, message="source doc has neither inline text nor a readable text_path"))

    for line_number, row in excerpt_rows:
        src_key = str(row.get("src_key") or "").strip()
        excerpt_path = pack_dir / SOURCE_PACK_EXCERPTS
        if not src_key:
            issues.append(_issue("block", "excerpt_missing_src_key", path=excerpt_path, line=line_number, message="excerpt.src_key is empty"))
        elif src_key not in src_keys:
            issues.append(_issue("block", "excerpt_unknown_src_key", path=excerpt_path, line=line_number, src_key=src_key, message="excerpt references a src_key not present in src_docs"))
        quote = str(row.get("quote") or row.get("text") or "").strip()
        if not quote:
            issues.append(_issue("warning", "excerpt_missing_text", path=excerpt_path, line=line_number, src_key=src_key, message="excerpt has no quote/text"))

    return _build_report(pack_dir, manifest, doc_rows, excerpt_rows, issues)


def _build_report(
    pack_dir: Path,
    manifest: dict[str, Any],
    doc_rows: list[tuple[int, dict[str, Any]]],
    excerpt_rows: list[tuple[int, dict[str, Any]]],
    issues: list[SourcePackIssue],
) -> dict[str, Any]:
    blocks = [issue for issue in issues if issue.severity == "block"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    workflow_code = str(manifest.get("workflow_code") or "").strip()
    pack_id = str(manifest.get("pack_id") or "").strip()
    if not workflow_code and (pack_id.upper().startswith("I5B-") or pack_id.lower().startswith("i5b")):
        workflow_code = "I5B"
    return {
        "ok": not blocks,
        "pack_path": str(pack_dir),
        "pack_id": manifest.get("pack_id", ""),
        "workflow_code": workflow_code,
        "schema_version": manifest.get("schema_version"),
        "doc_count": len(doc_rows),
        "excerpt_count": len(excerpt_rows),
        "block_count": len(blocks),
        "warning_count": len(warnings),
        "issues": [asdict(issue) for issue in issues],
    }


def load_source_pack_page_cache(pack_dir: Path) -> tuple[SourcePackPageCache, dict[str, Any]]:
    report = audit_source_pack(pack_dir)
    if report["block_count"]:
        first = report["issues"][0]["message"] if report["issues"] else "unknown source pack issue"
        raise ExcerptPoolError(f"source pack has blocking issues: {first}")
    docs = load_source_pack_documents(pack_dir)
    return SourcePackPageCache(docs), {
        "enabled": True,
        "pack_path": report["pack_path"],
        "pack_id": report["pack_id"],
        "doc_count": report["doc_count"],
        "excerpt_count": report["excerpt_count"],
        "page_count": len({doc.page_title for doc in docs}),
        "warning_count": report["warning_count"],
    }


def render_audit_markdown(report: dict[str, Any]) -> str:
    workflow_code = str(report.get("workflow_code") or "").strip()
    title = f"# {workflow_code} offline source pack audit" if workflow_code else "# Source pack audit"
    lines = [
        title,
        "",
        f"- ok: `{report['ok']}`",
        f"- pack_id: `{report.get('pack_id', '')}`",
        f"- workflow_code: `{workflow_code}`",
        f"- docs: `{report.get('doc_count', 0)}`",
        f"- excerpts: `{report.get('excerpt_count', 0)}`",
        f"- blocks: `{report.get('block_count', 0)}`",
        f"- warnings: `{report.get('warning_count', 0)}`",
        "",
        "| 级别 | 代码 | 文件 | 行 | src_key | 说明 |",
        "|---|---|---|---:|---|---|",
    ]
    for issue in report.get("issues", []):
        line = "" if issue.get("line") is None else str(issue.get("line"))
        lines.append(
            "| {severity} | {code} | {path} | {line} | {src_key} | {message} |".format(
                severity=issue.get("severity", ""),
                code=issue.get("code", ""),
                path=issue.get("path", ""),
                line=line,
                src_key=issue.get("src_key", ""),
                message=issue.get("message", ""),
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def write_audit_report(path: Path, report: dict[str, Any], *, output_format: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return
    if output_format == "markdown":
        path.write_text(render_audit_markdown(report), encoding="utf-8")
        return
    raise ExcerptPoolError(f"unknown output format: {output_format}")
