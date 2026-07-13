"""外部服务输出到 V4 contract 的薄适配器。"""

from emperor_v4.adapters.claim_extractor import adapt_claim_extractor_snapshot
from emperor_v4.adapters.source_cache import (
    adapt_source_cache_snapshot,
    adapt_source_cache_v2_response,
)

__all__ = [
    "adapt_claim_extractor_snapshot",
    "adapt_source_cache_snapshot",
    "adapt_source_cache_v2_response",
]
