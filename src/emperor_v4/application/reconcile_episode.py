from __future__ import annotations

from collections.abc import Iterable

from emperor_v4.contracts.assertion import AssertionDraft
from emperor_v4.contracts.episode import HistoricalEpisodePacket
from emperor_v4.domain.episode import build_episode_packet, group_episode_candidates


def reconcile_episode_candidates(
    assertions: Iterable[AssertionDraft],
) -> tuple[HistoricalEpisodePacket, ...]:
    """纯内存纵向用例；不访问模型、网络或数据库。"""

    return tuple(
        build_episode_packet(group) for group in group_episode_candidates(assertions)
    )
