from __future__ import annotations

from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from scripts.source_ingest.models import ParsedPassage, ParseResult, SourceSnapshot
from scripts.source_ingest.normalizer import NORMALIZER_VERSION, normalize_text, token_text


PARSER_VERSION = "wikisource-fixture-parser-v1"
SOURCE_HOST = "zh.wikisource.org"
NOISE_TOKENS = {
    "contentSub",
    "footer",
    "metadata",
    "mw-editsection",
    "navbox",
    "printfooter",
    "reference",
    "references",
    "reflist",
    "toc",
}


class _WikisourceFixtureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.passages: list[str] = []
        self._capture_title = False
        self._capture_paragraph = False
        self._inside_body = False
        self._noise_depth = 0
        self._paragraph_parts: list[str] = []
        self._parser_output_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_values = _joined_attr_values(attrs)
        if self._noise_depth or _is_noise(attr_values):
            self._noise_depth += 1

        if tag == "h1" and not self._noise_depth:
            self._capture_title = True

        if _has_parser_output(attr_values):
            self._parser_output_depth += 1
            self._inside_body = True
        elif self._inside_body and tag in {"div", "section", "article", "main"}:
            self._parser_output_depth += 1

        if tag == "p" and self._inside_body and not self._noise_depth:
            self._capture_paragraph = True
            self._paragraph_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "h1":
            self._capture_title = False

        if tag == "p" and self._capture_paragraph:
            raw_text = _clean_raw_text("".join(self._paragraph_parts))
            if raw_text:
                self.passages.append(raw_text)
            self._capture_paragraph = False
            self._paragraph_parts = []

        if self._inside_body and tag in {"div", "section", "article", "main"}:
            self._parser_output_depth -= 1
            if self._parser_output_depth <= 0:
                self._parser_output_depth = 0
                self._inside_body = False

        if self._noise_depth:
            self._noise_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._noise_depth:
            return
        if self._capture_title:
            self.title_parts.append(data)
        if self._capture_paragraph:
            self._paragraph_parts.append(data)


def parse_wikisource_fixture(
    fixture_path: Path | str,
    *,
    source_url: str,
    captured_at: str,
    source_title: str | None = None,
) -> ParseResult:
    path = Path(fixture_path)
    raw = path.read_text(encoding="utf-8")
    parser = _WikisourceFixtureParser()
    parser.feed(raw)

    title = source_title or _clean_raw_text("".join(parser.title_parts)) or path.stem
    raw_hash = _hash_text(raw)
    normalized_texts = [normalize_text(text) for text in parser.passages]
    normalized_hash = _hash_text("\n".join(normalized_texts))

    passages = [
        ParsedPassage(
            passage_code=f"{path.stem}-p{seq:04d}",
            seq=seq,
            location=f"p[{seq}]",
            raw_text=raw_text,
            norm_text=norm_text,
            token_text=token_text(norm_text),
            source_title=title,
            source_url=source_url,
        )
        for seq, (raw_text, norm_text) in enumerate(zip(parser.passages, normalized_texts), start=1)
        if norm_text
    ]

    snapshot = SourceSnapshot(
        source_host=SOURCE_HOST,
        source_title=title,
        source_url=source_url,
        source_path=path.as_posix(),
        captured_at=captured_at,
        raw_hash=raw_hash,
        parser_version=PARSER_VERSION,
        normalizer_version=NORMALIZER_VERSION,
    )
    return ParseResult(snapshot=snapshot, passages=passages, normalized_hash=normalized_hash)


def _joined_attr_values(attrs: list[tuple[str, str | None]]) -> str:
    return " ".join(value for _, value in attrs if value)


def _has_parser_output(attr_values: str) -> bool:
    return "mw-parser-output" in attr_values


def _is_noise(attr_values: str) -> bool:
    tokens = set(attr_values.replace("-", " ").replace("_", " ").split())
    compact = attr_values.replace("-", "").replace("_", "")
    return bool(tokens & NOISE_TOKENS) or any(token.replace("-", "") in compact for token in NOISE_TOKENS)


def _clean_raw_text(text: str) -> str:
    return " ".join(unescape(text).split()).strip()


def _hash_text(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()
