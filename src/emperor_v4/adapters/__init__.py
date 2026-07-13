"""外部服务输出到 V4 contract 的薄适配器。"""

from emperor_v4.adapters.claim_extractor import adapt_claim_extractor_snapshot
from emperor_v4.adapters.source_cache import (
    adapt_source_cache_snapshot,
    adapt_source_cache_v2_response,
)
from emperor_v4.adapters.wikisource import (
    WikisourcePageSnapshot,
    fetch_wikisource_plaintext,
    read_wikisource_snapshot,
    snapshot_from_api_payload,
    write_wikisource_snapshot,
)

__all__ = [
    "adapt_claim_extractor_snapshot",
    "adapt_source_cache_snapshot",
    "adapt_source_cache_v2_response",
    "WikisourcePageSnapshot",
    "fetch_wikisource_plaintext",
    "read_wikisource_snapshot",
    "snapshot_from_api_payload",
    "write_wikisource_snapshot",
]
