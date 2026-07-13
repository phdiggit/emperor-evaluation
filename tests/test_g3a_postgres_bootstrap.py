from __future__ import annotations

from pathlib import Path

import pytest

from emperor_v4.persistence.postgres import (
    G3A_TABLES,
    G3ASchemaStateError,
    decide_schema_action,
    migration_path,
)


def test_empty_schema_is_the_only_apply_state() -> None:
    assert decide_schema_action(set()) == "apply"


def test_complete_g3a_schema_is_reused_without_writes() -> None:
    assert decide_schema_action(G3A_TABLES) == "reuse"


@pytest.mark.parametrize(
    "tables",
    [
        G3A_TABLES - {"assertions"},
        G3A_TABLES | {"episode_relations"},
        {"unrelated_table"},
    ],
)
def test_partial_or_unexpected_schema_fails_closed(tables: set[str]) -> None:
    with pytest.raises(G3ASchemaStateError, match="不是空库或完整合同"):
        decide_schema_action(tables)


def test_packaged_migration_path_is_stable() -> None:
    path = migration_path()

    assert isinstance(path, Path)
    assert path.name == "001_g3a_episode_core.sql"
    assert path.is_file()
