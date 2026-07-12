from __future__ import annotations

import email.utils
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterable

from .cache import FetchContext
from .common import (
    DEFAULT_USER_AGENT,
    RETRY_HTTP_STATUS_CODES,
    WIKISOURCE_API,
    CacheMissError,
    TimeBudgetExceeded,
    compact_text,
)
from .profile import title_matches_source_filters


def strip_html(value: str) -> str:
    without_scripts = re.sub(r"<(script|style)\b.*?</\1>", " ", value, flags=re.IGNORECASE | re.DOTALL)
    without_tags = re.sub(r"<[^>]+>", " ", without_scripts)
    return compact_text(without_tags)


def retry_after_seconds(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    cleaned = value.strip()
    try:
        parsed = float(cleaned)
    except ValueError:
        try:
            parsed_date = email.utils.parsedate_to_datetime(cleaned)
        except (TypeError, ValueError):
            return None
        if parsed_date is None:
            return None
        seconds = parsed_date.timestamp() - time.time()
        return max(0.0, seconds)
    return max(0.0, parsed)


def retry_wait_seconds(exc: BaseException, *, attempt_index: int, retry_backoff_seconds: float) -> float:
    if isinstance(exc, urllib.error.HTTPError):
        retry_after = retry_after_seconds(exc.headers.get("Retry-After") if exc.headers else None)
        if retry_after is not None:
            return retry_after
    return retry_backoff_seconds * (2**attempt_index)


def capped_retry_wait_seconds(
    exc: BaseException,
    *,
    attempt_index: int,
    retry_backoff_seconds: float,
    max_retry_wait_seconds: float | None,
) -> tuple[float, bool]:
    wait_seconds = retry_wait_seconds(
        exc,
        attempt_index=attempt_index,
        retry_backoff_seconds=retry_backoff_seconds,
    )
    if max_retry_wait_seconds is None or wait_seconds <= max_retry_wait_seconds:
        return wait_seconds, False
    return max_retry_wait_seconds, True


def should_retry_exception(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in RETRY_HTTP_STATUS_CODES
    return isinstance(exc, urllib.error.URLError)


def _fetch_json(
    url: str,
    *,
    timeout: int,
    fetch_context: FetchContext | None = None,
    stage: str = "api",
    label: str = "",
    user_agent: str = DEFAULT_USER_AGENT,
) -> dict[str, Any]:
    api_cache = fetch_context.api_cache if fetch_context is not None else None
    if api_cache is not None:
        cached_payload = api_cache.read(stage=stage, label=label, url=url)
        if cached_payload is not None:
            return cached_payload
    if fetch_context is not None and fetch_context.cache_only:
        raise CacheMissError(f"{stage} {label}: cache miss")

    attempt_index = 0
    while True:
        if fetch_context is not None:
            fetch_context.assert_time_budget(stage=stage, label=label)
            fetch_context.wait_for_slot()
        request_user_agent = fetch_context.user_agent if fetch_context is not None else user_agent
        request = urllib.request.Request(url, headers={"User-Agent": request_user_agent})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
            value = json.loads(payload)
            if not isinstance(value, dict):
                raise ExcerptPoolError(f"unexpected JSON response from {url}")
            if api_cache is not None:
                api_cache.write(stage=stage, label=label, url=url, payload=value)
            return value
        except Exception as exc:
            if fetch_context is None or attempt_index >= fetch_context.max_retries or not should_retry_exception(exc):
                raise
            wait_seconds, wait_capped = capped_retry_wait_seconds(
                exc,
                attempt_index=attempt_index,
                retry_backoff_seconds=fetch_context.retry_backoff_seconds,
                max_retry_wait_seconds=fetch_context.max_retry_wait_seconds,
            )
            fetch_context.record_retry(
                stage=stage,
                label=label,
                url=url,
                attempt=attempt_index + 1,
                wait_seconds=wait_seconds,
                reason=repr(exc),
                status_code=exc.code if isinstance(exc, urllib.error.HTTPError) else None,
            )
            if wait_capped:
                fetch_context.retry_events[-1]["wait_capped"] = True
            time.sleep(wait_seconds)
            attempt_index += 1


def _api_url(params: dict[str, str]) -> str:
    query = urllib.parse.urlencode(params)
    return f"{WIKISOURCE_API}?{query}"


def wikisource_page_url(title: str) -> str:
    quoted = urllib.parse.quote(title.replace(" ", "_"), safe="/")
    return f"https://zh.wikisource.org/zh-hans/{quoted}"


def search_wikisource(
    query: str,
    *,
    limit: int,
    timeout: int,
    title_filters: Iterable[str] = (),
    fetch_context: FetchContext | None = None,
) -> list[dict[str, str]]:
    search_limit = max(limit, min(50, limit * 5))
    payload = _fetch_json(
        _api_url(
            {
                "action": "query",
                "list": "search",
                "srnamespace": "0",
                "srlimit": str(search_limit),
                "srsearch": query,
                "format": "json",
                "utf8": "1",
            }
        ),
        timeout=timeout,
        fetch_context=fetch_context,
        stage="search",
        label=query,
    )
    results = payload.get("query", {}).get("search", [])
    if not isinstance(results, list):
        return []
    pages: list[dict[str, str]] = []
    for result in results:
        if not isinstance(result, dict):
            continue
        title = str(result.get("title", "")).strip()
        if not title:
            continue
        if not title_matches_source_filters(title, title_filters):
            continue
        pages.append(
            {
                "title": title,
                "url": wikisource_page_url(title),
                "snippet": strip_html(str(result.get("snippet", ""))),
            }
        )
        if len(pages) >= limit:
            break
    return pages


def fetch_wikisource_plain_text(
    title: str,
    *,
    timeout: int,
    fetch_context: FetchContext | None = None,
) -> str:
    page_text_cache = fetch_context.page_text_cache if fetch_context is not None else None
    if page_text_cache is not None:
        cached_text = page_text_cache.read(title=title)
        if cached_text is not None:
            return cached_text

    payload = _fetch_json(
        _api_url(
            {
                "action": "parse",
                "page": title,
                "prop": "text",
                "format": "json",
                "utf8": "1",
                "redirects": "1",
                "uselang": "zh-hans",
                "variant": "zh-hans",
            }
        ),
        timeout=timeout,
        fetch_context=fetch_context,
        stage="fetch_page",
        label=title,
    )
    html_text = payload.get("parse", {}).get("text", {}).get("*", "")
    if not isinstance(html_text, str) or not html_text:
        return ""
    text = strip_html(html_text)
    if page_text_cache is not None:
        page_text_cache.write(title=title, page_url=wikisource_page_url(title), text=text)
    return text
