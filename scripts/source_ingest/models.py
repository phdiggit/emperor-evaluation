from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceSnapshot:
    source_host: str
    source_title: str
    source_url: str
    source_path: str
    captured_at: str
    raw_hash: str
    parser_version: str
    normalizer_version: str


@dataclass(frozen=True)
class ParsedPassage:
    passage_code: str
    seq: int
    location: str
    raw_text: str
    norm_text: str
    token_text: str
    source_title: str
    source_url: str


@dataclass(frozen=True)
class ParseResult:
    snapshot: SourceSnapshot
    passages: list[ParsedPassage]
    normalized_hash: str
