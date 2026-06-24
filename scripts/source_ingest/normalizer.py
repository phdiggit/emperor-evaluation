from __future__ import annotations

import re


NORMALIZER_VERSION = "wikisource-fixture-normalizer-v1"

_FOOTNOTE_RE = re.compile(r"(?:\[\s*\d+\s*\]|［\s*\d+\s*］)")
_SPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Keep source script intact while removing fixture-level spacing and notes."""
    normalized = text.replace("\u3000", " ").replace("\xa0", " ")
    normalized = _FOOTNOTE_RE.sub("", normalized)
    normalized = _SPACE_RE.sub("", normalized)
    return normalized.strip()


def token_text(text: str) -> str:
    return " ".join(char for char in text if not char.isspace())
