from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from urllib.parse import urlparse


def _router_data(html_text: str) -> Mapping[str, object] | None:
    marker = "window._ROUTER_DATA"
    marker_at = html_text.find(marker)
    if marker_at < 0:
        return None
    value_at = html_text.find("=", marker_at + len(marker))
    if value_at < 0:
        return None
    value_at += 1
    while value_at < len(html_text) and html_text[value_at].isspace():
        value_at += 1
    try:
        value, _ = json.JSONDecoder().raw_decode(html_text, value_at)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, Mapping) else None


def _paragraph_text(paragraph: object) -> list[str]:
    if not isinstance(paragraph, Mapping):
        return []
    content = paragraph.get("content")
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except json.JSONDecodeError:
            return [content.strip()] if content.strip() else []
    if not isinstance(content, Mapping):
        return []
    lines = content.get("lines")
    if not isinstance(lines, Sequence) or isinstance(lines, (str, bytes)):
        return []
    result: list[str] = []
    for line in lines:
        if not isinstance(line, Mapping):
            continue
        value = line.get("content")
        if isinstance(value, str) and value.strip():
            result.append(value.strip())
    return result


def extract_shidian_text(html_text: str) -> str:
    router = _router_data(html_text)
    loader = router.get("loaderData") if isinstance(router, Mapping) else None
    if not isinstance(loader, Mapping):
        return ""
    candidates: list[tuple[int, list[str]]] = []
    for route in loader.values():
        if not isinstance(route, Mapping):
            continue
        paragraphs = route.get("paragraphList")
        if not isinstance(paragraphs, Sequence) or isinstance(paragraphs, (str, bytes)):
            continue
        lines = [line for paragraph in paragraphs for line in _paragraph_text(paragraph)]
        candidates.append((len(lines), lines))
    if not candidates:
        return ""
    return "\n".join(max(candidates, key=lambda item: item[0])[1])


def extract_public_ocr_text(url: str, html_text: str) -> tuple[str, str]:
    host = (urlparse(url).hostname or "").lower()
    if host == "shidianguji.com" or host.endswith(".shidianguji.com"):
        text = extract_shidian_text(html_text)
        return text, "shidianguji_router_data" if text else "shidianguji_router_data_empty"
    return "", ""
