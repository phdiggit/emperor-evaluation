from __future__ import annotations

import argparse
from bisect import bisect_left
import bz2
from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Iterable, Iterator, Mapping, Sequence
from urllib.parse import quote
from uuid import uuid4
import xml.etree.ElementTree as ET

from opencc import OpenCC


INDEX_SCHEMA_VERSION = "local-source-text-index-v1"
_T2S = OpenCC("t2s")
_CJK = re.compile(r"[\u3400-\u9fff]{2,}")
_PAGE_VOLUME = re.compile(r"卷\s*0*(\d{1,4})")


@dataclass(frozen=True, slots=True)
class LocalSourceHit:
    page_title: str
    work_title: str
    source_url: str
    matched_terms: tuple[str, ...]
    score: int


@dataclass(frozen=True, slots=True)
class LocalSourceRecallHit:
    page_title: str
    work_title: str
    source_url: str
    matched_recall_terms: tuple[str, ...]
    matched_attribution_terms: tuple[str, ...]
    matched_priority_terms: tuple[str, ...]
    recall_score: int
    priority_score: int
    closest_priority_distance: int | None


@dataclass(frozen=True, slots=True)
class LocalSourcePage:
    page_title: str
    work_title: str
    source_url: str
    revision_ref: str
    raw_text: str


def _normalized(value: str) -> str:
    return re.sub(r"\s+", "", _T2S.convert(value))


def _work_key(value: str) -> str:
    return re.sub(r"[《》〈〉\s]", "", _T2S.convert(value))


def _page_in_ranges(
    page_title: str,
    work_title: str,
    page_ranges: Mapping[str, Sequence[int]],
) -> bool:
    normalized_ranges = {
        _work_key(work): tuple(int(bound) for bound in bounds)
        for work, bounds in page_ranges.items()
    }
    bounds = normalized_ranges.get(_work_key(work_title))
    if bounds is None:
        return True
    if len(bounds) != 2 or bounds[0] <= 0 or bounds[1] < bounds[0]:
        raise ValueError(f"本地全召回页面范围无效: {work_title}")
    match = _PAGE_VOLUME.search(page_title)
    return match is not None and bounds[0] <= int(match.group(1)) <= bounds[1]


def _fts_literal(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _term_positions(text: str, term: str) -> tuple[int, ...]:
    positions = []
    start = 0
    while (position := text.find(term, start)) >= 0:
        positions.append(position)
        start = position + 1
    return tuple(positions)


def _closest_distance(
    recall_positions: Sequence[int], priority_positions: Sequence[int]
) -> int | None:
    if not recall_positions or not priority_positions:
        return None
    closest = None
    for position in priority_positions:
        insertion = bisect_left(recall_positions, position)
        for candidate_index in (insertion - 1, insertion):
            if 0 <= candidate_index < len(recall_positions):
                distance = abs(position - recall_positions[candidate_index])
                closest = distance if closest is None else min(closest, distance)
    return closest


def _index_identity(rows: Sequence[Mapping[str, str]]) -> str:
    digest = sha256()
    digest.update(INDEX_SCHEMA_VERSION.encode("utf-8"))
    for row in sorted(rows, key=lambda item: str(item["page_title"])):
        for field in ("page_title", "work_title", "source_url", "revision_ref"):
            digest.update(str(row.get(field) or "").encode("utf-8"))
            digest.update(b"\0")
        digest.update(sha256(str(row["raw_text"]).encode("utf-8")).digest())
    return digest.hexdigest()


def build_local_source_index(
    rows: Iterable[Mapping[str, str]], output_path: Path
) -> dict[str, object]:
    """Build an immutable local discovery index; it is not a canonical source cache."""
    normalized_rows = []
    for raw in rows:
        row = {key: str(value or "").strip() for key, value in raw.items()}
        if not row.get("page_title") or not row.get("work_title") or not row.get("raw_text"):
            raise ValueError("本地史料索引记录缺少 page_title、work_title 或 raw_text")
        normalized_rows.append(row)
    if not normalized_rows:
        raise ValueError("本地史料索引没有可写入页面")
    titles = [row["page_title"] for row in normalized_rows]
    if len(titles) != len(set(titles)):
        raise ValueError("本地史料索引 page_title 重复")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.{uuid4().hex}.tmp")
    connection = sqlite3.connect(temporary)
    try:
        connection.executescript(
            """
            PRAGMA journal_mode=OFF;
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE pages (
                page_title TEXT PRIMARY KEY,
                work_title TEXT NOT NULL,
                work_key TEXT NOT NULL,
                source_url TEXT NOT NULL,
                revision_ref TEXT NOT NULL,
                raw_text TEXT NOT NULL,
                normalized_text TEXT NOT NULL
            );
            CREATE INDEX pages_work_key_idx ON pages(work_key);
            CREATE VIRTUAL TABLE pages_fts USING fts5(
                page_title,
                normalized_text,
                content='pages',
                content_rowid='rowid',
                tokenize='trigram'
            );
            """
        )
        connection.executemany(
            """
            INSERT INTO pages (
                page_title, work_title, work_key, source_url,
                revision_ref, raw_text, normalized_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["page_title"],
                    row["work_title"],
                    _work_key(row["work_title"]),
                    row.get("source_url", ""),
                    row.get("revision_ref", ""),
                    row["raw_text"],
                    _normalized(row["raw_text"]),
                )
                for row in normalized_rows
            ],
        )
        connection.execute("INSERT INTO pages_fts(pages_fts) VALUES ('rebuild')")
        identity = _index_identity(normalized_rows)
        connection.executemany(
            "INSERT INTO metadata(key, value) VALUES (?, ?)",
            (
                ("schema_version", INDEX_SCHEMA_VERSION),
                ("index_identity", identity),
                ("page_count", str(len(normalized_rows))),
            ),
        )
        connection.commit()
    finally:
        connection.close()
    os.replace(temporary, output_path)
    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "index_identity": identity,
        "page_count": len(normalized_rows),
        "output": str(output_path),
    }


class LocalSourceTextIndex:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise ValueError(f"本地史料索引不存在: {self.path}")
        with self._connect() as connection:
            metadata = dict(connection.execute("SELECT key, value FROM metadata"))
        if metadata.get("schema_version") != INDEX_SCHEMA_VERSION:
            raise ValueError("本地史料索引版本不支持")
        self.identity = metadata["index_identity"]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(f"file:{self.path.resolve()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def search(
        self,
        *,
        works: Sequence[str],
        terms: Sequence[str],
        limit: int = 5,
    ) -> tuple[LocalSourceHit, ...]:
        work_keys = tuple(dict.fromkeys(_work_key(item) for item in works if item))
        normalized_terms = tuple(
            dict.fromkeys(
                _normalized(term)
                for term in terms
                if len(_normalized(term)) >= 2
            )
        )
        if not work_keys or not normalized_terms or limit <= 0:
            return ()
        placeholders = ",".join("?" for _ in work_keys)
        candidates: dict[str, sqlite3.Row] = {}
        with self._connect() as connection:
            long_terms = tuple(term for term in normalized_terms[:16] if len(term) >= 3)
            if long_terms:
                rows = connection.execute(
                    f"""
                    SELECT p.* FROM pages_fts f
                    JOIN pages p ON p.rowid = f.rowid
                    WHERE pages_fts MATCH ? AND p.work_key IN ({placeholders})
                    ORDER BY bm25(pages_fts)
                    LIMIT 200
                    """,
                    (" OR ".join(_fts_literal(term) for term in long_terms), *work_keys),
                )
                for row in rows:
                    candidates[str(row["page_title"])] = row
            for term in (item for item in normalized_terms[:16] if len(item) == 2):
                rows = connection.execute(
                    f"""
                    SELECT * FROM pages
                    WHERE work_key IN ({placeholders}) AND normalized_text LIKE ?
                    ORDER BY (
                        length(normalized_text) - length(replace(normalized_text, ?, ''))
                    ) / ? DESC
                    LIMIT 100
                    """,
                    (*work_keys, f"%{term}%", term, len(term)),
                )
                for row in rows:
                    candidates[str(row["page_title"])] = row

        hits = []
        for row in candidates.values():
            text = str(row["normalized_text"])
            matched = tuple(term for term in normalized_terms if term in text)
            if not matched:
                continue
            score = sum(
                (len(term) ** 2) * (1 + min(text.count(term), 10))
                for term in normalized_terms
                if term in text
            )
            # The first term is normally the subject name.  A biography heading is
            # useful recall evidence, but it must not outrank a different volume
            # containing several concrete action/result anchors.
            score += 64 * max(0, len(matched) - 1)
            if normalized_terms and f"=={normalized_terms[0]}==" in text:
                score += 32
            hits.append(
                LocalSourceHit(
                    page_title=str(row["page_title"]),
                    work_title=str(row["work_title"]),
                    source_url=str(row["source_url"]),
                    matched_terms=matched,
                    score=score,
                )
            )
        return tuple(
            sorted(hits, key=lambda hit: (-hit.score, hit.page_title))[:limit]
        )

    def recall(
        self,
        *,
        works: Sequence[str],
        recall_terms: Sequence[str],
        attribution_terms: Sequence[str] = (),
        priority_terms: Sequence[str] = (),
        priority_window_chars: int = 200,
        page_ranges: Mapping[str, Sequence[int]] | None = None,
    ) -> tuple[LocalSourceRecallHit, ...]:
        """Return every page matching a recall term; priority terms never filter."""
        if priority_window_chars <= 0:
            raise ValueError("本地全召回主题邻近窗口必须为正数")
        work_keys = tuple(dict.fromkeys(_work_key(item) for item in works if item))
        normalized_recall = tuple(
            dict.fromkeys(
                _normalized(term)
                for term in recall_terms
                if len(_normalized(term)) >= 2
            )
        )
        normalized_priority = tuple(
            dict.fromkeys(
                _normalized(term)
                for term in priority_terms
                if len(_normalized(term)) >= 2
            )
        )
        normalized_attribution = tuple(
            dict.fromkeys(
                _normalized(term)
                for term in attribution_terms
                if len(_normalized(term)) >= 2
            )
        )
        if not work_keys or not normalized_recall:
            return ()
        work_placeholders = ",".join("?" for _ in work_keys)
        recall_predicate = " OR ".join(
            "normalized_text LIKE ?" for _ in normalized_recall
        )
        with self._connect() as connection:
            rows = tuple(
                connection.execute(
                    f"""
                    SELECT * FROM pages
                    WHERE work_key IN ({work_placeholders})
                      AND ({recall_predicate})
                    ORDER BY page_title
                    """,
                    (*work_keys, *(f"%{term}%" for term in normalized_recall)),
                )
            )

        hits = []
        for row in rows:
            if page_ranges and not _page_in_ranges(
                str(row["page_title"]), str(row["work_title"]), page_ranges
            ):
                continue
            text = str(row["normalized_text"])
            matched_recall = tuple(term for term in normalized_recall if term in text)
            matched_attribution = tuple(
                term for term in normalized_attribution if term in text
            )
            recall_positions = tuple(
                sorted(
                    position
                    for term in matched_recall
                    for position in _term_positions(text, term)
                )
            )
            priority_distances = {
                term: _closest_distance(recall_positions, _term_positions(text, term))
                for term in normalized_priority
                if term in text
            }
            matched_priority = tuple(
                term
                for term in normalized_priority
                if priority_distances.get(term) is not None
                and priority_distances[term] <= priority_window_chars
            )
            closest_priority_distance = min(
                (priority_distances[term] for term in matched_priority),
                default=None,
            )
            hits.append(
                LocalSourceRecallHit(
                    page_title=str(row["page_title"]),
                    work_title=str(row["work_title"]),
                    source_url=str(row["source_url"]),
                    matched_recall_terms=matched_recall,
                    matched_attribution_terms=matched_attribution,
                    matched_priority_terms=matched_priority,
                    recall_score=sum(
                        len(term) ** 2 * text.count(term) for term in matched_recall
                    ),
                    priority_score=sum(
                        len(term) ** 2
                        * (priority_window_chars + 1 - priority_distances[term])
                        for term in matched_priority
                    ),
                    closest_priority_distance=closest_priority_distance,
                )
            )
        return tuple(
            sorted(
                hits,
                key=lambda hit: (
                    -len(hit.matched_priority_terms),
                    -hit.priority_score,
                    -hit.recall_score,
                    hit.page_title,
                ),
            )
        )

    def read_page_text(self, page_title: str) -> str | None:
        """Read discovery text for offline pre-anchoring; never treat it as a revision."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT raw_text FROM pages WHERE page_title = ?",
                (page_title,),
            ).fetchone()
        return str(row["raw_text"]) if row is not None else None

    def iter_pages_matching_terms(
        self,
        *,
        works: Sequence[str],
        terms: Sequence[str],
    ) -> Iterator[LocalSourcePage]:
        """Yield pages containing any identity term without recall ranking work."""
        work_keys = tuple(dict.fromkeys(_work_key(item) for item in works if item))
        normalized_terms = tuple(
            dict.fromkeys(
                _normalized(term)
                for term in terms
                if len(_normalized(term)) >= 2
            )
        )
        if not work_keys or not normalized_terms:
            return
        work_placeholders = ",".join("?" for _ in work_keys)
        term_predicate = " OR ".join(
            "normalized_text LIKE ?" for _ in normalized_terms
        )
        with self._connect() as connection:
            rows = connection.execute(
                f"""
                SELECT page_title, work_title, source_url, revision_ref, raw_text
                FROM pages
                WHERE work_key IN ({work_placeholders})
                  AND ({term_predicate})
                ORDER BY page_title
                """,
                (*work_keys, *(f"%{term}%" for term in normalized_terms)),
            )
            for row in rows:
                yield LocalSourcePage(
                    page_title=str(row["page_title"]),
                    work_title=str(row["work_title"]),
                    source_url=str(row["source_url"]),
                    revision_ref=str(row["revision_ref"]),
                    raw_text=str(row["raw_text"]),
                )

    def iter_pages(
        self,
        *,
        works: Sequence[str],
        page_ranges: Mapping[str, Sequence[int]] | None = None,
        page_titles: Sequence[str] | None = None,
    ) -> Iterator[LocalSourcePage]:
        """Yield immutable discovery pages without exposing the SQLite layout."""
        work_keys = tuple(dict.fromkeys(_work_key(item) for item in works if item))
        if not work_keys:
            return
        selected_titles = tuple(
            sorted(dict.fromkeys(str(value) for value in page_titles or () if value))
        )
        if page_titles is not None and not selected_titles:
            return
        title_chunks: tuple[tuple[str, ...], ...] = (
            tuple(
                selected_titles[offset : offset + 400]
                for offset in range(0, len(selected_titles), 400)
            )
            if page_titles is not None
            else ((),)
        )
        work_placeholders = ",".join("?" for _ in work_keys)
        with self._connect() as connection:
            for title_chunk in title_chunks:
                title_filter = ""
                parameters: tuple[str, ...] = work_keys
                if title_chunk:
                    title_placeholders = ",".join("?" for _ in title_chunk)
                    title_filter = f" AND page_title IN ({title_placeholders})"
                    parameters = (*work_keys, *title_chunk)
                rows = connection.execute(
                    f"""
                    SELECT page_title, work_title, source_url, revision_ref, raw_text
                    FROM pages
                    WHERE work_key IN ({work_placeholders}){title_filter}
                    ORDER BY page_title
                    """,
                    parameters,
                )
                for row in rows:
                    if page_ranges and not _page_in_ranges(
                        str(row["page_title"]), str(row["work_title"]), page_ranges
                    ):
                        continue
                    yield LocalSourcePage(
                        page_title=str(row["page_title"]),
                        work_title=str(row["work_title"]),
                        source_url=str(row["source_url"]),
                        revision_ref=str(row["revision_ref"]),
                        raw_text=str(row["raw_text"]),
                    )


def iter_wikisource_dump(
    dump_path: Path, *, works: Sequence[str]
) -> Iterator[dict[str, str]]:
    """Stream selected works from an official MediaWiki XML or XML.BZ2 dump."""
    prefixes = tuple(dict.fromkeys(str(work).strip() for work in works if str(work).strip()))
    if not prefixes:
        raise ValueError("导入 Wikisource dump 必须指定至少一部书")
    opener = bz2.open if dump_path.suffix.lower() == ".bz2" else open
    with opener(dump_path, "rb") as stream:
        for _event, element in ET.iterparse(stream, events=("end",)):
            if not element.tag.endswith("}page"):
                continue
            title = next((child.text or "" for child in element if child.tag.endswith("}title")), "")
            namespace = next((child.text or "" for child in element if child.tag.endswith("}ns")), "")
            matched_work = next(
                (work for work in prefixes if title == work or title.startswith(work + "/")),
                None,
            )
            if namespace == "0" and matched_work is not None:
                revision = next((child for child in element if child.tag.endswith("}revision")), None)
                if revision is not None:
                    revision_ref = next(
                        (child.text or "" for child in revision if child.tag.endswith("}id")),
                        "",
                    )
                    text = next(
                        (child.text or "" for child in revision.iter() if child.tag.endswith("}text")),
                        "",
                    )
                    if text.strip():
                        yield {
                            "page_title": title,
                            "work_title": matched_work,
                            "source_url": "https://zh.wikisource.org/wiki/"
                            + quote(title.replace(" ", "_")),
                            "revision_ref": revision_ref,
                            "raw_text": text,
                        }
            element.clear()


def _jsonl_rows(path: Path) -> Iterator[Mapping[str, str]]:
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            payload = json.loads(line)
            if not isinstance(payload, Mapping):
                raise ValueError(f"JSONL 第 {line_number} 行必须是 object")
            yield payload


def build_local_recall_report(
    index: LocalSourceTextIndex,
    requests: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    subjects = []
    for raw in requests:
        subject_name = str(raw.get("subject_name") or "").strip()
        works = tuple(str(item).strip() for item in raw.get("works") or ())
        recall_terms = tuple(
            str(item).strip() for item in raw.get("recall_terms") or ()
        )
        attribution_terms = tuple(
            str(item).strip() for item in raw.get("attribution_terms") or ()
        )
        priority_terms = tuple(
            str(item).strip() for item in raw.get("priority_terms") or ()
        )
        priority_window_chars = int(raw.get("priority_window_chars") or 200)
        page_ranges = raw.get("page_ranges") or {}
        if not isinstance(page_ranges, Mapping):
            raise ValueError("本地全召回 page_ranges 必须是 object")
        if not subject_name or not works or not recall_terms:
            raise ValueError("本地全召回请求缺少 subject_name、works 或 recall_terms")
        hits = index.recall(
            works=works,
            recall_terms=recall_terms,
            attribution_terms=attribution_terms,
            priority_terms=priority_terms,
            priority_window_chars=priority_window_chars,
            page_ranges=page_ranges,
        )
        prioritized = sum(bool(hit.matched_priority_terms) for hit in hits)
        explicitly_attributed = sum(
            bool(hit.matched_attribution_terms) for hit in hits
        )
        subjects.append(
            {
                "subject_name": subject_name,
                "works": list(works),
                "recall_terms": list(recall_terms),
                "attribution_terms": list(attribution_terms),
                "priority_terms": list(priority_terms),
                "priority_window_chars": priority_window_chars,
                "page_ranges": {
                    str(work): [int(bound) for bound in bounds]
                    for work, bounds in page_ranges.items()
                },
                "hit_count": len(hits),
                "prioritized_hit_count": prioritized,
                "unprioritized_retained_count": len(hits) - prioritized,
                "explicit_attribution_hit_count": explicitly_attributed,
                "short_form_only_retained_count": len(hits) - explicitly_attributed,
                "hits": [
                    {
                        "page_title": hit.page_title,
                        "work_title": hit.work_title,
                        "source_url": hit.source_url,
                        "matched_recall_terms": list(hit.matched_recall_terms),
                        "matched_attribution_terms": list(
                            hit.matched_attribution_terms
                        ),
                        "matched_priority_terms": list(hit.matched_priority_terms),
                        "recall_score": hit.recall_score,
                        "priority_score": hit.priority_score,
                        "closest_priority_distance": hit.closest_priority_distance,
                    }
                    for hit in hits
                ],
            }
        )
    return {
        "schema_version": "local-source-recall-report-v1",
        "status": "shadow_only",
        "index_identity": index.identity,
        "subjects": subjects,
        "network_requests": 0,
        "formal_writes": 0,
        "database_writes": 0,
        "model_calls": 0,
    }


def _atomic_json(path: Path, payload: Mapping[str, object]) -> bool:
    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    if path.is_file() and path.read_bytes() == encoded:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(encoded)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
    return True


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="构建和查询本地古籍全文发现索引")
    sub = parser.add_subparsers(dest="command", required=True)
    build_dump = sub.add_parser("build-wikisource")
    build_dump.add_argument("--dump", type=Path, required=True)
    build_dump.add_argument("--output", type=Path, required=True)
    build_dump.add_argument("--work", action="append", required=True)
    build_jsonl = sub.add_parser("build-jsonl")
    build_jsonl.add_argument("--input", type=Path, required=True)
    build_jsonl.add_argument("--output", type=Path, required=True)
    search = sub.add_parser("search")
    search.add_argument("--index", type=Path, required=True)
    search.add_argument("--work", action="append", required=True)
    search.add_argument("--term", action="append", required=True)
    search.add_argument("--limit", type=int, default=5)
    recall_report = sub.add_parser("recall-report")
    recall_report.add_argument("--index", type=Path, required=True)
    recall_report.add_argument("--input", type=Path, required=True)
    recall_report.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build-wikisource":
        result = build_local_source_index(
            iter_wikisource_dump(args.dump, works=args.work), args.output
        )
    elif args.command == "build-jsonl":
        result = build_local_source_index(_jsonl_rows(args.input), args.output)
    elif args.command == "search":
        index = LocalSourceTextIndex(args.index)
        result = {
            "schema_version": INDEX_SCHEMA_VERSION,
            "index_identity": index.identity,
            "hits": [
                {
                    "page_title": hit.page_title,
                    "work_title": hit.work_title,
                    "source_url": hit.source_url,
                    "matched_terms": list(hit.matched_terms),
                    "score": hit.score,
                }
                for hit in index.search(works=args.work, terms=args.term, limit=args.limit)
            ],
        }
    else:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        requests = payload.get("subjects") if isinstance(payload, Mapping) else None
        if not isinstance(requests, Sequence) or isinstance(requests, (str, bytes)):
            raise ValueError("本地全召回输入缺少 subjects")
        result = build_local_recall_report(
            LocalSourceTextIndex(args.index), requests
        )
        _atomic_json(args.output, result)
        return 0
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
