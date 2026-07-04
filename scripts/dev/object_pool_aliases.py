from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Protocol

from scripts.dev.i5b_finite_values import (
    FiniteValueError,
    OBJECT_ALIAS_KINDS,
    OBJECT_ALIAS_SCOPES,
    require_choice,
)


ALIAS_SPACE_RE = re.compile(r"[\s　]+")


class ObjectAliasError(ValueError):
    pass


class ObjectRowLike(Protocol):
    obj_type: str
    period: str
    name: str
    note: str
    aliases: tuple["ObjectAliasRow", ...]


@dataclass(frozen=True)
class ObjectAliasRow:
    alias_text: str
    alias_kind: str
    scope: str
    confidence: float
    note: str


def _require_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ObjectAliasError(f"{path}: expected object")
    return value


def _require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ObjectAliasError(f"{path}: expected list")
    return value


def _optional_text(row: dict[str, Any], key: str) -> str:
    value = row.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ObjectAliasError(f"{key}: expected string when present")
    return value.strip()


def _optional_float(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    raise ObjectAliasError(f"{key}: expected number when present")


def normalize_object_alias(value: Any) -> str:
    text = str(value or "").strip()
    return ALIAS_SPACE_RE.sub("", text)


def parse_object_alias(value: Any, path: str) -> ObjectAliasRow:
    if isinstance(value, str):
        alias_text = value.strip()
        if not alias_text:
            raise ObjectAliasError(f"{path}: expected non-empty alias")
        return ObjectAliasRow(alias_text=alias_text, alias_kind="alias", scope="global", confidence=1.0, note="")

    row = _require_mapping(value, path)
    alias_text = _optional_text(row, "alias_text") or _optional_text(row, "alias")
    if not alias_text:
        raise ObjectAliasError(f"{path}.alias: expected non-empty string")
    try:
        alias_kind = require_choice(
            row.get("alias_kind", "alias"),
            choices=OBJECT_ALIAS_KINDS,
            field_name=f"{path}.alias_kind",
        )
        scope = require_choice(
            row.get("scope", "global"),
            choices=OBJECT_ALIAS_SCOPES,
            field_name=f"{path}.scope",
        )
    except FiniteValueError as exc:
        raise ObjectAliasError(str(exc)) from exc
    confidence = _optional_float(row, "confidence")
    if confidence is None:
        confidence = 1.0
    if confidence < 0 or confidence > 1:
        raise ObjectAliasError(f"{path}.confidence: expected value from 0 to 1")
    return ObjectAliasRow(
        alias_text=alias_text,
        alias_kind=alias_kind,
        scope=scope,
        confidence=confidence,
        note=_optional_text(row, "note"),
    )


def parse_object_aliases(row: dict[str, Any], path: str) -> tuple[ObjectAliasRow, ...]:
    raw_aliases = row.get("aliases", [])
    if raw_aliases is None:
        raw_aliases = []
    aliases = tuple(
        parse_object_alias(alias, f"{path}.aliases[{alias_index}]")
        for alias_index, alias in enumerate(_require_list(raw_aliases, f"{path}.aliases"))
    )
    seen: set[tuple[str, str]] = set()
    duplicates: list[str] = []
    for alias in aliases:
        normalized = normalize_object_alias(alias.alias_text)
        if not normalized:
            raise ObjectAliasError(f"{path}.aliases: expected non-empty normalized alias")
        key = (normalized, alias.scope)
        if key in seen:
            duplicates.append(alias.alias_text)
        seen.add(key)
    if duplicates:
        raise ObjectAliasError(f"{path}.aliases: duplicate alias(es): {', '.join(duplicates)}")
    return aliases


def ensure_object_alias_schema(cur: Any) -> None:
    alias_kinds = ", ".join(f"'{kind}'" for kind in OBJECT_ALIAS_KINDS)
    cur.execute(
        f"""
        create table if not exists raw_obj_aliases (
            id bigserial primary key,
            obj_id bigint not null references raw_objs(id) on delete cascade,
            alias_text text not null,
            normalized_alias text not null,
            alias_kind text not null default 'alias'
                check (alias_kind in ({alias_kinds})),
            period text not null default '',
            scope_emp_id bigint references emps(id) on delete cascade,
            confidence numeric(5,4) not null default 1.0
                check (confidence >= 0 and confidence <= 1),
            active boolean not null default true,
            note text not null default '',
            created_at timestamptz not null default now(),
            updated_at timestamptz not null default now()
        )
        """
    )
    cur.execute(
        """
        create unique index if not exists raw_obj_aliases_active_uk
            on raw_obj_aliases (normalized_alias, period, coalesce(scope_emp_id, 0))
            where active
        """
    )
    cur.execute(
        """
        create index if not exists raw_obj_aliases_obj_idx
            on raw_obj_aliases (obj_id)
        """
    )


def _upsert_object(cur: Any, row: ObjectRowLike) -> int:
    cur.execute(
        """
        insert into raw_objs (obj_type, period, name, note)
        values (%s, %s, %s, %s)
        on conflict (obj_type, period, name) do update set
            note = excluded.note,
            updated_at = now()
        returning id
        """,
        (row.obj_type, row.period, row.name, row.note),
    )
    return int(cur.fetchone()[0])


def _alias_scope_emp_id(alias: ObjectAliasRow, emp_id: int) -> int | None:
    return emp_id if alias.scope == "emperor" else None


def _canonical_alias(name: str) -> ObjectAliasRow:
    return ObjectAliasRow(
        alias_text=name,
        alias_kind="canonical",
        scope="global",
        confidence=1.0,
        note="",
    )


def _object_alias_rows(row: ObjectRowLike, *, canonical_name: str) -> tuple[ObjectAliasRow, ...]:
    aliases: list[ObjectAliasRow] = [_canonical_alias(canonical_name)]
    if normalize_object_alias(row.name) != normalize_object_alias(canonical_name):
        aliases.append(
            ObjectAliasRow(
                alias_text=row.name,
                alias_kind="alias",
                scope="global",
                confidence=1.0,
                note="payload object name resolved to canonical object",
            )
        )
    aliases.extend(row.aliases)

    deduped: list[ObjectAliasRow] = []
    seen: set[tuple[str, str]] = set()
    for alias in aliases:
        key = (normalize_object_alias(alias.alias_text), alias.scope)
        if not key[0] or key in seen:
            continue
        seen.add(key)
        deduped.append(alias)
    return tuple(deduped)


def resolve_object_alias(cur: Any, row: ObjectRowLike, *, emp_id: int) -> dict[str, Any] | None:
    terms = sorted(
        {
            normalize_object_alias(term)
            for term in [row.name, *(alias.alias_text for alias in row.aliases)]
            if normalize_object_alias(term)
        }
    )
    if not terms:
        return None
    cur.execute(
        """
        select distinct a.obj_id, ro.name, a.alias_text
          from raw_obj_aliases a
          join raw_objs ro on ro.id = a.obj_id
         where a.active
           and a.period = %s
           and ro.obj_type = %s
           and ro.period = %s
           and a.normalized_alias = any(%s)
           and (a.scope_emp_id is null or a.scope_emp_id = %s)
         order by a.obj_id
        """,
        (row.period, row.obj_type, row.period, terms, emp_id),
    )
    rows = cur.fetchall()
    if not rows:
        return None
    object_ids = {int(item[0]) for item in rows}
    if len(object_ids) > 1:
        labels = ", ".join(f"{item[1]}#{item[0]} via {item[2]}" for item in rows)
        raise ObjectAliasError(f"{row.name}: ambiguous object alias; matched {labels}")
    first = rows[0]
    return {
        "obj_id": int(first[0]),
        "canonical_name": str(first[1]),
        "matched_alias": str(first[2]),
    }


def upsert_object_alias(
    cur: Any,
    *,
    obj_id: int,
    period: str,
    emp_id: int,
    alias: ObjectAliasRow,
) -> int:
    normalized = normalize_object_alias(alias.alias_text)
    if not normalized:
        raise ObjectAliasError("object alias: expected non-empty normalized alias")
    scope_emp_id = _alias_scope_emp_id(alias, emp_id)
    cur.execute(
        """
        select id, obj_id, alias_kind
          from raw_obj_aliases
         where active
           and normalized_alias = %s
           and period = %s
           and scope_emp_id is not distinct from %s
         order by id
         limit 1
        """,
        (normalized, period, scope_emp_id),
    )
    existing = cur.fetchone()
    if existing is not None and int(existing[1]) != obj_id:
        raise ObjectAliasError(f"object alias conflict: {alias.alias_text} already points to obj_id={existing[1]}")
    if existing is not None:
        existing_kind = str(existing[2] or "")
        alias_kind = existing_kind if existing_kind == "canonical" else alias.alias_kind
        cur.execute(
            """
            update raw_obj_aliases
               set alias_text = %s,
                   alias_kind = %s,
                   confidence = greatest(confidence, %s),
                   note = case
                       when %s = '' then note
                       when note = '' then %s
                       else note
                   end,
                   updated_at = now()
             where id = %s
             returning id
            """,
            (
                alias.alias_text,
                alias_kind,
                alias.confidence,
                alias.note,
                alias.note,
                int(existing[0]),
            ),
        )
        return int(cur.fetchone()[0])

    cur.execute(
        """
        insert into raw_obj_aliases (
            obj_id, alias_text, normalized_alias, alias_kind,
            period, scope_emp_id, confidence, note
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        returning id
        """,
        (
            obj_id,
            alias.alias_text,
            normalized,
            alias.alias_kind,
            period,
            scope_emp_id,
            alias.confidence,
            alias.note,
        ),
    )
    return int(cur.fetchone()[0])


def upsert_object_aliases(
    cur: Any,
    *,
    obj_id: int,
    row: ObjectRowLike,
    emp_id: int,
    canonical_name: str,
) -> list[dict[str, Any]]:
    alias_rows: list[dict[str, Any]] = []
    for alias in _object_alias_rows(row, canonical_name=canonical_name):
        alias_id = upsert_object_alias(cur, obj_id=obj_id, period=row.period, emp_id=emp_id, alias=alias)
        alias_rows.append(
            {
                "id": alias_id,
                "object_id": obj_id,
                "alias_text": alias.alias_text,
                "normalized_alias": normalize_object_alias(alias.alias_text),
                "alias_kind": alias.alias_kind,
                "scope": alias.scope,
            }
        )
    return alias_rows


def resolve_or_upsert_object(cur: Any, row: ObjectRowLike, *, emp_id: int) -> dict[str, Any]:
    resolved = resolve_object_alias(cur, row, emp_id=emp_id)
    if resolved is not None:
        obj_id = int(resolved["obj_id"])
        canonical_name = str(resolved["canonical_name"])
        alias_rows = upsert_object_aliases(cur, obj_id=obj_id, row=row, emp_id=emp_id, canonical_name=canonical_name)
        return {
            "obj_id": obj_id,
            "canonical_name": canonical_name,
            "resolved_by_alias": True,
            "matched_alias": resolved["matched_alias"],
            "aliases": alias_rows,
        }

    obj_id = _upsert_object(cur, row)
    alias_rows = upsert_object_aliases(cur, obj_id=obj_id, row=row, emp_id=emp_id, canonical_name=row.name)
    return {
        "obj_id": obj_id,
        "canonical_name": row.name,
        "resolved_by_alias": False,
        "matched_alias": "",
        "aliases": alias_rows,
    }
