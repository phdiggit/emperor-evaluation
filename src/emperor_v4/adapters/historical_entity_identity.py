from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

from opencc import OpenCC
import yaml


SCHEMA_VERSION = "historical-entity-identities-current-v1"
_T2S = OpenCC("t2s")


def _normalized(value: str) -> str:
    return re.sub(r"\s+", "", _T2S.convert(value))


@dataclass(frozen=True, slots=True)
class HistoricalAlias:
    surface: str
    alias_type: str
    recall: bool
    contextual: bool


@dataclass(frozen=True, slots=True)
class HistoricalEntityIdentity:
    person_ref: str
    canonical_name: str
    dynasty: str
    aliases: tuple[HistoricalAlias, ...]


@dataclass(frozen=True, slots=True)
class IdentityResolution:
    status: str
    surface: str
    person_ref: str | None
    canonical_name: str | None
    candidate_refs: tuple[str, ...]


class HistoricalEntityResolver:
    """One identity boundary shared by recall, extraction, and projection.

    Script conversion is comparison-only. It never rewrites source quotations.
    Contextual one-character aliases may bind inside an already restricted subject
    set, but are deliberately excluded from source-page recall.
    """

    def __init__(self, entities: Iterable[HistoricalEntityIdentity]) -> None:
        rows = tuple(entities)
        self._by_ref = {row.person_ref: row for row in rows}
        self._by_name = {row.canonical_name: row for row in rows}
        if len(self._by_ref) != len(rows) or len(self._by_name) != len(rows):
            raise ValueError("历史实体 person_ref 或 canonical_name 重复")
        surface_index: dict[str, list[tuple[HistoricalEntityIdentity, HistoricalAlias]]] = {}
        for entity in rows:
            canonical = HistoricalAlias(entity.canonical_name, "canonical_name", True, False)
            for alias in (canonical, *entity.aliases):
                key = _normalized(alias.surface)
                if not key:
                    raise ValueError(f"{entity.canonical_name}: 空别名")
                surface_index.setdefault(key, []).append((entity, alias))
        self._surface_index = surface_index

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        source_pack: Mapping[str, Any] | None = None,
    ) -> "HistoricalEntityResolver":
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping) or raw.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("历史实体身份目录版本不支持")
        entities = []
        for row in raw.get("entities") or ():
            aliases = tuple(
                HistoricalAlias(
                    surface=str(alias["surface"]),
                    alias_type=str(alias["alias_type"]),
                    recall=bool(alias.get("recall", True)),
                    contextual=bool(alias.get("contextual", False)),
                )
                for alias in row.get("aliases") or ()
            )
            entities.append(
                HistoricalEntityIdentity(
                    person_ref=str(row["person_ref"]),
                    canonical_name=str(row["canonical_name"]),
                    dynasty=str(row["dynasty"]),
                    aliases=aliases,
                )
            )
        resolver = cls(entities)
        if source_pack is not None:
            expected = {
                str(source_pack["ruler"]): str(source_pack["ruler_ref"]),
                **{
                    str(row["person"]): str(row["person_ref"])
                    for row in source_pack.get("members") or ()
                },
            }
            missing = sorted(set(expected) - set(resolver._by_name))
            mismatched = sorted(
                name
                for name, person_ref in expected.items()
                if name in resolver._by_name
                and resolver._by_name[name].person_ref != person_ref
            )
            if missing or mismatched:
                raise ValueError(
                    f"历史实体身份目录未覆盖当前团队: missing={missing}, mismatched={mismatched}"
                )
        return resolver

    def entity_for_name(self, canonical_name: str) -> HistoricalEntityIdentity:
        try:
            return self._by_name[canonical_name]
        except KeyError as exc:
            raise ValueError(f"历史实体身份目录缺少: {canonical_name}") from exc

    def recall_terms(self, canonical_name: str) -> tuple[str, ...]:
        entity = self.entity_for_name(canonical_name)
        return tuple(
            dict.fromkeys(
                (
                    entity.canonical_name,
                    *(
                        alias.surface
                        for alias in entity.aliases
                        if alias.recall and len(_normalized(alias.surface)) >= 2
                    ),
                )
            )
        )

    def contextual_terms(self, canonical_name: str) -> tuple[str, ...]:
        entity = self.entity_for_name(canonical_name)
        return tuple(
            dict.fromkeys(
                alias.surface
                for alias in entity.aliases
                if alias.contextual
            )
        )

    def bindings(self, subject_refs: Sequence[str]) -> list[dict[str, Any]]:
        rows = []
        for person_ref in subject_refs:
            entity = self._by_ref.get(str(person_ref))
            if entity is None:
                continue
            rows.append(
                {
                    "subject_ref": entity.person_ref,
                    "canonical_name": entity.canonical_name,
                    "aliases": [
                        {
                            "surface": alias.surface,
                            "alias_type": alias.alias_type,
                            "contextual": alias.contextual,
                        }
                        for alias in entity.aliases
                    ],
                }
            )
        return rows

    def resolve(
        self,
        surface: str,
        *,
        allowed_subject_refs: Sequence[str],
        dynasty: str | None = None,
    ) -> IdentityResolution:
        allowed = {str(value) for value in allowed_subject_refs}
        candidates = []
        for entity, alias in self._surface_index.get(_normalized(surface), ()):
            if entity.person_ref not in allowed:
                continue
            if dynasty and entity.dynasty != dynasty:
                continue
            candidates.append(entity)
        unique = {row.person_ref: row for row in candidates}
        refs = tuple(sorted(unique))
        if len(refs) == 1:
            entity = unique[refs[0]]
            return IdentityResolution(
                "resolved", surface, entity.person_ref, entity.canonical_name, refs
            )
        return IdentityResolution(
            "ambiguous" if refs else "unresolved",
            surface,
            None,
            None,
            refs,
        )

    def resolve_any(
        self, surface: str, *, dynasty: str | None = None
    ) -> IdentityResolution:
        """Resolve an explicit source surface without preselecting a ruler roster."""

        return self.resolve(
            surface,
            allowed_subject_refs=sorted(self._by_ref),
            dynasty=dynasty,
        )
