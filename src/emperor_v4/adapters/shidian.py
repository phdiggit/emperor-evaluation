from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import json
import re
from typing import Any, Mapping, Sequence
from urllib.request import Request, urlopen


DEFAULT_USER_AGENT = "emperor-v4-source-qualification/0.1"
_CN_DIGITS = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def _fetch_router_data(url: str, *, timeout_seconds: float) -> Mapping[str, Any]:
    request = Request(url, headers={"User-Agent": DEFAULT_USER_AGENT})
    with urlopen(request, timeout=timeout_seconds) as response:
        html = response.read().decode("utf-8")
    prefix = "window._ROUTER_DATA = "
    start = html.index(prefix) + len(prefix)
    end = html.index("</script>", start)
    source = html[start:end].strip().removesuffix(";")
    payload = json.loads(source)
    if not isinstance(payload, Mapping):
        raise ValueError("识典古籍 router data 不是对象")
    return payload


def _book_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    loader = payload.get("loaderData")
    if not isinstance(loader, Mapping):
        raise ValueError("识典古籍响应缺少 loaderData")
    book = loader.get("__session/(lang$)/book/$")
    if not isinstance(book, Mapping):
        raise ValueError("识典古籍响应缺少 book payload")
    return book


def _chapter_name(chapter: Mapping[str, Any]) -> str:
    values = chapter.get("chapterName") or ()
    return "".join(
        str(item.get("content") or "")
        for item in values
        if isinstance(item, Mapping)
    )


def _chinese_number(value: str) -> int:
    total = 0
    number = 0
    for char in value:
        if char in _CN_DIGITS:
            number = _CN_DIGITS[char]
        elif char == "十":
            total += (number or 1) * 10
            number = 0
        elif char == "百":
            total += (number or 1) * 100
            number = 0
    result = total + number
    if result <= 0:
        raise ValueError(f"无法解析中文卷号: {value}")
    return result


def discover_shidian_chapters(
    *,
    catalog_url: str,
    work_title: str,
    chapter_name_contains: str,
    first_volume: int,
    last_volume: int,
    timeout_seconds: float = 60.0,
) -> dict[str, dict[str, Any]]:
    book = _book_payload(
        _fetch_router_data(catalog_url, timeout_seconds=timeout_seconds)
    )
    info = book.get("bookInfo")
    catalog = info.get("catalog") if isinstance(info, Mapping) else None
    chapters = catalog.get("chapters") if isinstance(catalog, Mapping) else None
    if not isinstance(chapters, Sequence):
        raise ValueError("识典古籍目录缺少 chapters")
    rows: dict[str, dict[str, Any]] = {}
    for chapter in chapters:
        if not isinstance(chapter, Mapping):
            continue
        name = _chapter_name(chapter)
        if chapter_name_contains not in name:
            continue
        match = re.search(r"卷之?([一二三四五六七八九十百]+)([上下]?)", name)
        if match is None:
            continue
        volume = _chinese_number(match.group(1))
        if not first_volume <= volume <= last_volume:
            continue
        part = match.group(2)
        title = f"{work_title}/卷{volume:03d}"
        row = rows.setdefault(title, {"volume": volume, "chapters": []})
        row["chapters"].append(
            {
                "chapter_id": str(chapter["chapterId"]),
                "chapter_name": name,
                "part": part,
                "volume_version": int(chapter["volumeVersion"]),
            }
        )
    for row in rows.values():
        row["chapters"].sort(key=lambda item: str(item["part"]))
    covered = {int(row["volume"]) for row in rows.values()}
    expected = set(range(first_volume, last_volume + 1))
    if covered != expected:
        raise ValueError(
            "识典古籍目录卷次不完整: "
            + json.dumps(
                {
                    "missing": sorted(expected - covered),
                    "extra": sorted(covered - expected),
                },
                ensure_ascii=False,
            )
        )
    return rows


def fetch_shidian_plaintext_batch(
    *,
    page_titles: Sequence[str],
    page_metadata: Mapping[str, Mapping[str, Any]],
    book_id: str,
    chapter_url_format: str,
    timeout_seconds: float = 60.0,
) -> dict[str, dict[str, Any]]:
    snapshots = {}
    for title in page_titles:
        metadata = page_metadata[title]
        lines = []
        identities = []
        urls = []
        for chapter in metadata["chapters"]:
            chapter_id = str(chapter["chapter_id"])
            source_url = chapter_url_format.format(chapter_id=chapter_id)
            urls.append(source_url)
            book = _book_payload(
                _fetch_router_data(source_url, timeout_seconds=timeout_seconds)
            )
            paragraphs = book.get("paragraphList")
            if not isinstance(paragraphs, Sequence) or not paragraphs:
                raise ValueError(f"识典古籍章节缺少段落: {title}")
            for paragraph in paragraphs:
                if not isinstance(paragraph, Mapping):
                    continue
                content = paragraph.get("content")
                if not isinstance(content, str) or not content:
                    continue
                value = json.loads(content)
                lines.extend(
                    str(line.get("content") or "").strip()
                    for line in value.get("lines") or ()
                    if isinstance(line, Mapping)
                    and str(line.get("content") or "").strip()
                )
            identities.append(
                f"{chapter_id}:v{chapter['volume_version']}"
            )
        raw_text = "\n".join(lines).strip()
        if len(raw_text) < 50:
            raise ValueError(f"识典古籍章节正文过短: {title}")
        content_hash = sha256(raw_text.encode("utf-8")).hexdigest()
        snapshots[title] = {
            "requested_title": title,
            "canonical_title": title,
            "canonical_url": urls[0],
            "revision_ref": (
                f"shidian:{book_id}:{'+'.join(identities)}:"
                f"sha256:{content_hash}"
            ),
            "retrieved_at": datetime.now(UTC).isoformat(),
            "raw_text": raw_text,
            "content_hash": content_hash,
        }
    return snapshots
