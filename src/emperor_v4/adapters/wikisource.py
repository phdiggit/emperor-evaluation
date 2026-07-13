from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote, urlencode, urljoin
from urllib.request import Request, urlopen


DEFAULT_API_ENDPOINT = "https://zh.wikisource.org/w/api.php"
DEFAULT_PAGE_BASE = "https://zh.wikisource.org/wiki/"
DEFAULT_USER_AGENT = "emperor-v4-source-qualification/0.1"


@dataclass(frozen=True, slots=True)
class WikisourcePageSnapshot:
    page_code: str
    requested_title: str
    canonical_title: str
    canonical_url: str
    revision_id: int
    revision_timestamp: str
    retrieved_at: str
    raw_text: str
    content_hash: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.page_code,
                self.requested_title,
                self.canonical_title,
                self.canonical_url,
                self.revision_timestamp,
                self.retrieved_at,
                self.raw_text,
                self.content_hash,
            )
        ) or self.revision_id <= 0:
            raise ValueError("Wikisource snapshot 缺少页面身份、版本或正文")
        if sha256(self.raw_text.encode("utf-8")).hexdigest() != self.content_hash:
            raise ValueError("Wikisource snapshot content_hash 与 raw_text 不一致")


def snapshot_from_api_payload(
    *,
    page_code: str,
    requested_title: str,
    payload: Mapping[str, Any],
    retrieved_at: str,
) -> WikisourcePageSnapshot:
    pages = tuple((payload.get("query") or {}).get("pages") or ())
    if len(pages) != 1 or pages[0].get("missing") is True:
        raise ValueError(f"Wikisource 页面不存在或响应不唯一: {requested_title}")
    page = pages[0]
    revisions = tuple(page.get("revisions") or ())
    if len(revisions) != 1:
        raise ValueError(f"Wikisource 页面缺少唯一 revision: {requested_title}")
    raw_text = str(page.get("extract") or "").strip()
    canonical_title = str(page.get("title") or "")
    if not raw_text or not canonical_title:
        raise ValueError(f"Wikisource 页面缺少 plain text: {requested_title}")
    revision = revisions[0]
    canonical_url = urljoin(
        DEFAULT_PAGE_BASE,
        quote(canonical_title.replace(" ", "_")),
    )
    return WikisourcePageSnapshot(
        page_code=page_code,
        requested_title=requested_title,
        canonical_title=canonical_title,
        canonical_url=canonical_url,
        revision_id=int(revision["revid"]),
        revision_timestamp=str(revision["timestamp"]),
        retrieved_at=retrieved_at,
        raw_text=raw_text,
        content_hash=sha256(raw_text.encode("utf-8")).hexdigest(),
    )


def fetch_wikisource_plaintext(
    *,
    page_code: str,
    page_title: str,
    expected_revision_id: int | None = None,
    api_endpoint: str = DEFAULT_API_ENDPOINT,
    timeout_seconds: float = 30.0,
) -> WikisourcePageSnapshot:
    params = {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "prop": "extracts|revisions",
        "explaintext": "1",
        "redirects": "1",
        "rvprop": "ids|timestamp",
        "titles": page_title,
    }
    request = Request(
        api_endpoint + "?" + urlencode(params),
        headers={"User-Agent": DEFAULT_USER_AGENT},
    )
    retrieved_at = datetime.now(UTC).isoformat()
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = json.load(response)
    snapshot = snapshot_from_api_payload(
        page_code=page_code,
        requested_title=page_title,
        payload=payload,
        retrieved_at=retrieved_at,
    )
    if expected_revision_id is not None and snapshot.revision_id != expected_revision_id:
        raise ValueError(
            f"Wikisource revision 已变化: {page_title} "
            f"expected={expected_revision_id} actual={snapshot.revision_id}"
        )
    return snapshot


def write_wikisource_snapshot(
    snapshot: WikisourcePageSnapshot, output_path: Path
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(asdict(snapshot), ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def read_wikisource_snapshot(path: Path) -> WikisourcePageSnapshot:
    return WikisourcePageSnapshot(
        **json.loads(path.read_text(encoding="utf-8"))
    )
