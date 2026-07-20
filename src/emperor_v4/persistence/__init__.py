"""V4 隔离 shadow persistence 边界。"""

from emperor_v4.persistence.core_registry import (
    CoreRegistryBatch,
    CoreRegistryWriteResult,
    EpisodeDispositionRecord,
    HistoricalOutcomeClusterRecord,
    HistoricalOutcomeMember,
    InMemoryCoreRegistry,
    RuleEvidenceUnitRecord,
    SourceDocumentRecord,
)
from emperor_v4.persistence.postgres import (
    G3ASchemaBootstrapResult,
    G3ASchemaStateError,
    bootstrap_g3a_schema,
    decide_schema_action,
)
from emperor_v4.persistence.postgres_registry import (
    PostgresCoreRegistry,
    historical_episode_packet_from_payload,
)
from emperor_v4.persistence.source_cache import (
    InMemorySourceCacheRepository,
    ShadowJsonSourceCacheRepository,
)
from emperor_v4.persistence.postgres_source_cache import (
    PostgresSourceCacheRepository,
    SourceCacheSchemaBootstrapResult,
    SourceCacheSchemaStateError,
    bootstrap_source_cache_schema,
    decide_source_cache_schema_action,
)
from emperor_v4.persistence.source_cache_jobs import (
    InMemorySourceCacheJobRepository,
    PostgresSourceCacheJobRepository,
)

__all__ = [
    "CoreRegistryBatch",
    "CoreRegistryWriteResult",
    "EpisodeDispositionRecord",
    "HistoricalOutcomeClusterRecord",
    "HistoricalOutcomeMember",
    "InMemoryCoreRegistry",
    "RuleEvidenceUnitRecord",
    "SourceDocumentRecord",
    "G3ASchemaBootstrapResult",
    "G3ASchemaStateError",
    "bootstrap_g3a_schema",
    "decide_schema_action",
    "PostgresCoreRegistry",
    "historical_episode_packet_from_payload",
    "InMemorySourceCacheRepository",
    "ShadowJsonSourceCacheRepository",
    "PostgresSourceCacheRepository",
    "SourceCacheSchemaBootstrapResult",
    "SourceCacheSchemaStateError",
    "bootstrap_source_cache_schema",
    "decide_source_cache_schema_action",
    "InMemorySourceCacheJobRepository",
    "PostgresSourceCacheJobRepository",
]
