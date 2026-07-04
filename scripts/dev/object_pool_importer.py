from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg

from scripts.dev.i5b_finite_values import (
    ALLOWED_DIRECTIONS,
    CANONICAL_TALENT_QUALITY_VALUES,
    FiniteValueError,
    I5B_ITEM_CODES,
    I5B_RULE_CODES,
    I5B_SUBITEMS,
    NEGATIVE_TALENT_QUALITY_VALUES,
    OBJECT_ATTR_CODES,
    TALENT_QUALITY_RANKS,
    require_choice,
    require_canonical_period,
    require_direction,
    require_talent_quality,
)
from scripts.dev.object_pool_aliases import (
    ObjectAliasError,
    ObjectAliasRow,
    ensure_object_alias_schema,
    parse_object_aliases,
    resolve_or_upsert_object,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DSN_ENV = "EMPEROR_EVAL_PG_DSN"
RAW_NOTE_FORBIDDEN_TERMS = (
    "第五项",
    "I5B",
    "评分",
    "规则",
    "正向",
    "负向",
    "另切",
    "切分",
)
GENERIC_OBJ_SRC_NOTE_FRAGMENTS = (
    "该记录是对象池",
    "支撑规则维度",
    "事实方向为",
    "I5B回源关联",
)
AMBIGUOUS_OBJ_SRC_NOTE_TERMS = (
    "另切",
    "不入",
    "不加",
    "不计",
    "回填",
    "额外收益",
    "结果反馈",
    "授权合理性",
    "只作",
    "只作为",
    "只计",
    "只保留",
    "不得直接",
    "不能充分验证",
)
SOURCE_BIBLIO_BY_TITLE = {
    "史记": ("司马迁", "西汉"),
    "汉书": ("班固", "东汉"),
    "后汉书": ("范晔", "南朝宋"),
    "后汉书二十八将传论": ("范晔", "南朝宋"),
    "旧唐书": ("刘昫等", "后晋"),
    "新唐书": ("欧阳修、宋祁等", "北宋"),
    "资治通鉴": ("司马光", "北宋"),
    "宋史": ("脱脱等", "元"),
    "明史": ("张廷玉等", "清"),
    "清史稿": ("赵尔巽等", "民国"),
}
HARMED_TALENT_RULE_CODE = "tolerate_talent"


class ImportErrorWithContext(ValueError):
    pass


@dataclass(frozen=True)
class EmperorRow:
    period: str
    name: str
    title: str
    note: str
    sort_no: int | None = None


@dataclass(frozen=True)
class SourceRow:
    src_key: str
    title: str
    author: str
    dynasty: str
    volume: str
    locator: str
    url: str
    note: str


@dataclass(frozen=True)
class ObjectAttrRow:
    attr_code: str
    src_key: str
    note: str
    value_text: str
    value_num: float | None
    value_unit: str
    period_start: int | None
    period_end: int | None
    region: str
    confidence: float
    obj_name: str


@dataclass(frozen=True)
class ObjectSourceLink:
    src_key: str
    rule_code: str
    direction: str
    note: str


@dataclass(frozen=True)
class ObjectRow:
    obj_type: str
    period: str
    name: str
    note: str
    aliases: tuple[ObjectAliasRow, ...]
    links: tuple[ObjectSourceLink, ...]
    attrs: tuple[ObjectAttrRow, ...]


@dataclass(frozen=True)
class ImportPayload:
    item_code: str
    subitem: str
    emperor: EmperorRow
    sources: tuple[SourceRow, ...]
    objects: tuple[ObjectRow, ...]


def _require_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ImportErrorWithContext(f"{path}: expected object")
    return value


def _require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ImportErrorWithContext(f"{path}: expected list")
    return value


def _text(row: dict[str, Any], key: str, path: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ImportErrorWithContext(f"{path}.{key}: expected non-empty string")
    return value.strip()


def _optional_text(row: dict[str, Any], key: str) -> str:
    value = row.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ImportErrorWithContext(f"{key}: expected string when present")
    return value.strip()


def _optional_int(row: dict[str, Any], key: str) -> int | None:
    value = row.get(key)
    if value is None:
        return None
    if not isinstance(value, int):
        raise ImportErrorWithContext(f"{key}: expected integer when present")
    return value


def _optional_float(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    raise ImportErrorWithContext(f"{key}: expected number when present")


def _optional_bool(row: dict[str, Any], key: str) -> bool | None:
    value = row.get(key)
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ImportErrorWithContext(f"{key}: expected boolean when present")
    return value


def _assert_no_terms(value: str, terms: tuple[str, ...], path: str) -> None:
    offenders = [term for term in terms if term in value]
    if offenders:
        joined = ", ".join(offenders)
        raise ImportErrorWithContext(f"{path}: forbidden term(s) in note: {joined}")


def source_biblio_for_title(title: str) -> tuple[str, str]:
    return SOURCE_BIBLIO_BY_TITLE.get(title.strip(), ("", ""))


def _parse_emperor(row: dict[str, Any]) -> EmperorRow:
    try:
        period = require_canonical_period(_text(row, "period", "emperor"), field_name="emperor.period")
    except FiniteValueError as exc:
        raise ImportErrorWithContext(str(exc)) from exc
    return EmperorRow(
        period=period,
        name=_text(row, "name", "emperor"),
        title=_optional_text(row, "title"),
        sort_no=_optional_int(row, "sort_no"),
        note=_text(row, "note", "emperor"),
    )


def _parse_source(row: dict[str, Any], index: int) -> SourceRow:
    path = f"sources[{index}]"
    title = _text(row, "title", path)
    default_author, default_dynasty = source_biblio_for_title(title)
    return SourceRow(
        src_key=_text(row, "src_key", path),
        title=title,
        author=_optional_text(row, "author") or default_author,
        dynasty=_optional_text(row, "dynasty") or default_dynasty,
        volume=_optional_text(row, "volume"),
        locator=_optional_text(row, "locator"),
        url=_optional_text(row, "url"),
        note=_text(row, "note", path),
    )


def _parse_link(row: dict[str, Any], path: str) -> ObjectSourceLink:
    try:
        direction = require_direction(_text(row, "direction", path), field_name=f"{path}.direction")
        rule_code = require_choice(_text(row, "rule_code", path), choices=I5B_RULE_CODES, field_name=f"{path}.rule_code")
    except FiniteValueError as exc:
        raise ImportErrorWithContext(str(exc)) from exc
    note = _text(row, "note", path)
    _assert_no_terms(note, GENERIC_OBJ_SRC_NOTE_FRAGMENTS, f"{path}.note")
    _assert_no_terms(note, AMBIGUOUS_OBJ_SRC_NOTE_TERMS, f"{path}.note")
    return ObjectSourceLink(
        src_key=_text(row, "src_key", path),
        rule_code=rule_code,
        direction=direction,
        note=note,
    )


def _parse_attr(row: dict[str, Any], path: str, *, default_region: str, default_obj_name: str) -> ObjectAttrRow:
    try:
        attr_code = require_choice(_text(row, "attr_code", path), choices=OBJECT_ATTR_CODES, field_name=f"{path}.attr_code")
    except FiniteValueError as exc:
        raise ImportErrorWithContext(str(exc)) from exc
    value_text = _optional_text(row, "value_text")
    value_num = _optional_float(row, "value_num")
    if not value_text and value_num is None:
        raise ImportErrorWithContext(f"{path}: expected value_text or value_num")
    if attr_code == "talent_quality":
        try:
            value_text = require_talent_quality(value_text, field_name=f"{path}.talent_quality")
        except FiniteValueError as exc:
            raise ImportErrorWithContext(str(exc)) from exc
    confidence = _optional_float(row, "confidence")
    if confidence is None:
        confidence = 0.85
    if confidence < 0 or confidence > 1:
        raise ImportErrorWithContext(f"{path}.confidence: expected value from 0 to 1")
    return ObjectAttrRow(
        attr_code=attr_code,
        src_key=_text(row, "src_key", path),
        value_text=value_text,
        value_num=value_num,
        value_unit=_optional_text(row, "value_unit"),
        period_start=_optional_int(row, "period_start"),
        period_end=_optional_int(row, "period_end"),
        region=_optional_text(row, "region") or default_region,
        confidence=confidence,
        note=_text(row, "note", path),
        obj_name=_optional_text(row, "obj_name") or default_obj_name,
    )


def _has_negative_talent_quality(attrs: tuple[ObjectAttrRow, ...]) -> bool:
    return any(
        attr.attr_code == "talent_quality" and attr.value_text in NEGATIVE_TALENT_QUALITY_VALUES
        for attr in attrs
    )


def _assert_harmed_talent_links_allowed(
    *,
    obj_name: str,
    attrs: tuple[ObjectAttrRow, ...],
    links: tuple[ObjectSourceLink, ...],
    path: str,
) -> None:
    if not _has_negative_talent_quality(attrs):
        return
    if any(link.rule_code == HARMED_TALENT_RULE_CODE for link in links):
        raise ImportErrorWithContext(
            f"{path}.links: {HARMED_TALENT_RULE_CODE} cannot link negative talent object {obj_name}"
        )


def _parse_object(row: dict[str, Any], index: int) -> ObjectRow:
    path = f"objects[{index}]"
    note = _text(row, "note", path)
    _assert_no_terms(note, RAW_NOTE_FORBIDDEN_TERMS, f"{path}.note")
    try:
        obj_period = require_canonical_period(_text(row, "period", path), field_name=f"{path}.period")
    except FiniteValueError as exc:
        raise ImportErrorWithContext(str(exc)) from exc
    link_rows = _require_list(row.get("links"), f"{path}.links")
    if not link_rows:
        raise ImportErrorWithContext(f"{path}.links: object must have at least one source link")
    links = tuple(
        _parse_link(_require_mapping(link, f"{path}.links[{link_index}]"), f"{path}.links[{link_index}]")
        for link_index, link in enumerate(link_rows)
    )
    attr_rows = row.get("attrs", [])
    if attr_rows is None:
        attr_rows = []
    attrs = tuple(
        _parse_attr(
            _require_mapping(attr, f"{path}.attrs[{attr_index}]"),
            f"{path}.attrs[{attr_index}]",
            default_region=obj_period,
            default_obj_name=_text(row, "name", path),
        )
        for attr_index, attr in enumerate(_require_list(attr_rows, f"{path}.attrs"))
    )
    obj_name = _text(row, "name", path)
    _assert_harmed_talent_links_allowed(obj_name=obj_name, attrs=attrs, links=links, path=path)
    try:
        aliases = parse_object_aliases(row, path)
    except ObjectAliasError as exc:
        raise ImportErrorWithContext(str(exc)) from exc
    return ObjectRow(
        obj_type=_text(row, "obj_type", path),
        period=obj_period,
        name=obj_name,
        note=note,
        aliases=aliases,
        links=links,
        attrs=attrs,
    )


def parse_payload(raw: dict[str, Any]) -> ImportPayload:
    payload = _require_mapping(raw, "payload")
    try:
        item_code = require_choice(_text(payload, "item_code", "payload"), choices=I5B_ITEM_CODES, field_name="payload.item_code")
        subitem = require_choice(_text(payload, "subitem", "payload"), choices=I5B_SUBITEMS, field_name="payload.subitem")
    except FiniteValueError as exc:
        raise ImportErrorWithContext(str(exc)) from exc
    raw_emperor = _require_mapping(payload.get("emperor"), "emperor")
    emperor = _parse_emperor(raw_emperor)

    sources = tuple(
        _parse_source(_require_mapping(row, f"sources[{index}]"), index)
        for index, row in enumerate(_require_list(payload.get("sources"), "sources"))
    )
    objects = tuple(
        _parse_object(_require_mapping(row, f"objects[{index}]"), index)
        for index, row in enumerate(_require_list(payload.get("objects"), "objects"))
    )
    if not sources:
        raise ImportErrorWithContext("sources: expected at least one source")
    if not objects:
        raise ImportErrorWithContext("objects: expected at least one object")

    source_keys = [source.src_key for source in sources]
    duplicate_sources = sorted({key for key in source_keys if source_keys.count(key) > 1})
    if duplicate_sources:
        raise ImportErrorWithContext(f"sources: duplicate src_key(s): {', '.join(duplicate_sources)}")

    known_sources = set(source_keys)
    for obj in objects:
        object_sources = {link.src_key for link in obj.links}
        for link in obj.links:
            if link.src_key not in known_sources:
                raise ImportErrorWithContext(f"{obj.name}: link references unknown src_key {link.src_key}")
        for attr in obj.attrs:
            if attr.src_key not in known_sources:
                raise ImportErrorWithContext(f"{obj.name}: attr references unknown src_key {attr.src_key}")
            if attr.src_key not in object_sources:
                raise ImportErrorWithContext(f"{obj.name}: attr source must also be linked on the object")

    return _attach_raw_emperor(
        ImportPayload(
            item_code=item_code,
            subitem=subitem,
            emperor=emperor,
            sources=sources,
            objects=objects,
        ),
        raw_emperor,
    )


def load_payload(path: Path) -> ImportPayload:
    return load_payloads(path)[0]


def load_payloads(path: Path) -> tuple[ImportPayload, ...]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        rows = raw
    elif isinstance(raw, dict) and "payloads" in raw:
        rows = _require_list(raw.get("payloads"), "payloads")
    else:
        rows = [raw]
    payloads = tuple(parse_payload(_require_mapping(row, f"payloads[{index}]")) for index, row in enumerate(rows))
    if not payloads:
        raise ImportErrorWithContext("payloads: expected at least one payload")
    return payloads


def load_env(path: Path = ROOT / ".env") -> dict[str, str]:
    if not path.exists():
        return {}
    env: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def resolve_dsn(env_name: str) -> str:
    if os.environ.get(env_name):
        return str(os.environ[env_name])
    env_file = load_env()
    if env_name not in env_file:
        raise ImportErrorWithContext(f"missing PostgreSQL DSN env var {env_name}")
    return env_file[env_name]


def _upsert_emperor(cur: psycopg.Cursor, row: EmperorRow, meta: dict[str, Any] | None = None) -> int:
    meta = meta or {}
    meta_fields = (("is_founder", _optional_bool), ("succession_mode", _optional_text), ("power_origin", _optional_text))
    cur.execute("select id, sort_no from emps where name = %s order by sort_no nulls last, id limit 1", (row.name,))
    existing = cur.fetchone()
    if existing is not None:
        emp_id = int(existing[0])
        assignments: list[tuple[str, Any]] = [("note", row.note)]
        if existing[1] is None and row.sort_no is not None:
            assignments.extend([("period", row.period), ("title", row.title), ("sort_no", row.sort_no)])
        assignments.extend((key, parser(meta, key)) for key, parser in meta_fields if key in meta)
        updates = [f"{key} = %s" for key, _ in assignments] + ["updated_at = now()"]
        values = [value for _, value in assignments] + [emp_id]
        cur.execute(f"update emps set {', '.join(updates)} where id = %s", tuple(values))
        return emp_id

    columns = ["period", "name", "title", "sort_no", "note"]
    values: list[Any] = [row.period, row.name, row.title, row.sort_no, row.note]
    updates = [
        "title = excluded.title",
        "sort_no = excluded.sort_no",
        "note = excluded.note",
    ]
    if "is_founder" in meta:
        columns.append("is_founder")
        values.append(_optional_bool(meta, "is_founder"))
    if "succession_mode" in meta:
        columns.append("succession_mode")
        values.append(_optional_text(meta, "succession_mode"))
    if "power_origin" in meta:
        columns.append("power_origin")
        values.append(_optional_text(meta, "power_origin"))
    updates.extend(f"{key} = excluded.{key}" for key, _ in meta_fields if key in meta)
    updates.append("updated_at = now()")
    placeholders = ", ".join(["%s"] * len(columns))
    sql = (
        f"insert into emps ({', '.join(columns)}) values ({placeholders}) "
        f"on conflict (period, name) do update set {', '.join(updates)} returning id"
    )
    cur.execute(sql, tuple(values))
    return int(cur.fetchone()[0])


def _update_emperor_meta(cur: psycopg.Cursor, emp_id: int, row: dict[str, Any]) -> None:
    updates: list[str] = []
    values: list[Any] = []
    if "is_founder" in row:
        updates.append("is_founder = %s")
        values.append(_optional_bool(row, "is_founder"))
    if "succession_mode" in row:
        updates.append("succession_mode = %s")
        values.append(_optional_text(row, "succession_mode"))
    if "power_origin" in row:
        updates.append("power_origin = %s")
        values.append(_optional_text(row, "power_origin"))
    if not updates:
        return
    updates.append("updated_at = now()")
    values.append(emp_id)
    cur.execute(f"update emps set {', '.join(updates)} where id = %s", tuple(values))


def _upsert_source(cur: psycopg.Cursor, row: SourceRow) -> int:
    cur.execute(
        """
        insert into src_docs (src_key, title, author, dynasty, volume, locator, url, note)
        values (%s, %s, %s, %s, %s, %s, %s, %s)
        on conflict (src_key) do update set
            title = excluded.title,
            author = excluded.author,
            dynasty = excluded.dynasty,
            volume = excluded.volume,
            locator = excluded.locator,
            url = excluded.url,
            note = excluded.note,
            updated_at = now()
        returning id
        """,
        (row.src_key, row.title, row.author, row.dynasty, row.volume, row.locator, row.url, row.note),
    )
    return int(cur.fetchone()[0])


def _upsert_emp_object(cur: psycopg.Cursor, emp_id: int, obj_id: int, subitem: str, obj_name: str) -> int:
    cur.execute(
        """
        insert into emp_objs (emp_id, obj_id, subitem, note)
        values (%s, %s, %s, %s)
        on conflict (emp_id, obj_id, subitem) do update set
            note = excluded.note,
            updated_at = now()
        returning id
        """,
        (emp_id, obj_id, subitem, obj_name),
    )
    return int(cur.fetchone()[0])


def _load_rule_ids(cur: psycopg.Cursor, item_code: str) -> tuple[int, dict[str, int]]:
    cur.execute("select id from eval_items where item_code = %s", (item_code,))
    row = cur.fetchone()
    if row is None:
        raise ImportErrorWithContext(f"eval_items missing item_code {item_code}")
    item_id = int(row[0])
    cur.execute("select rule_code, id from eval_rules where item_id = %s", (item_id,))
    rule_ids = {rule_code: int(rule_id) for rule_code, rule_id in cur.fetchall()}
    return item_id, rule_ids


def _upsert_obj_source(
    cur: psycopg.Cursor,
    *,
    obj_id: int,
    emp_obj_id: int,
    doc_id: int,
    item_id: int,
    rule_id: int,
    link: ObjectSourceLink,
) -> int:
    cur.execute(
        """
        insert into obj_srcs (obj_id, emp_obj_id, doc_id, item_id, rule_id, direction, note)
        values (%s, %s, %s, %s, %s, %s, %s)
        on conflict (emp_obj_id, doc_id, item_id, rule_id, direction) do update set
            obj_id = excluded.obj_id,
            note = excluded.note,
            updated_at = now()
        returning id
        """,
        (obj_id, emp_obj_id, doc_id, item_id, rule_id, link.direction, link.note),
    )
    return int(cur.fetchone()[0])


def _insert_object_attr(
    cur: psycopg.Cursor,
    *,
    obj_id: int,
    doc_id: int,
    obj_src_id: int | None,
    attr: ObjectAttrRow,
) -> int:
    cur.execute(
        """
        insert into obj_attrs (
            obj_id, attr_code, value_text, value_num, value_unit,
            period_start, period_end, region, doc_id, obj_src_id,
            confidence, note, obj_name
        )
        values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        returning id
        """,
        (
            obj_id,
            attr.attr_code,
            attr.value_text,
            attr.value_num,
            attr.value_unit,
            attr.period_start,
            attr.period_end,
            attr.region,
            doc_id,
            obj_src_id,
            attr.confidence,
            attr.note,
            attr.obj_name,
        ),
    )
    return int(cur.fetchone()[0])


def _fetch_existing_object_attr(cur: psycopg.Cursor, *, obj_id: int, attr: ObjectAttrRow) -> dict[str, Any] | None:
    cur.execute(
        """
        select id, value_text, value_num, confidence
          from obj_attrs
         where obj_id = %s
           and attr_code = %s
           and period_start is not distinct from %s
           and period_end is not distinct from %s
           and region = %s
        """,
        (obj_id, attr.attr_code, attr.period_start, attr.period_end, attr.region),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return {"id": int(row[0]), "value_text": row[1], "value_num": row[2], "confidence": float(row[3])}


def _should_replace_existing_attr(existing: dict[str, Any], attr: ObjectAttrRow) -> bool:
    existing_confidence = float(existing["confidence"] or 0)
    incoming_confidence = float(attr.confidence)
    if attr.attr_code == "talent_quality":
        existing_rank = TALENT_QUALITY_RANKS.get(str(existing.get("value_text") or ""))
        incoming_rank = TALENT_QUALITY_RANKS.get(attr.value_text)
        if existing_rank is not None and incoming_rank is not None:
            if incoming_rank < existing_rank:
                return False
            if incoming_rank > existing_rank:
                return incoming_confidence >= existing_confidence
    return incoming_confidence >= existing_confidence


def _update_object_attr(
    cur: psycopg.Cursor,
    *,
    attr_id: int,
    doc_id: int,
    obj_src_id: int | None,
    attr: ObjectAttrRow,
) -> int:
    cur.execute(
        """
        update obj_attrs
           set value_text = %s,
               value_num = %s,
               value_unit = %s,
               doc_id = %s,
               obj_src_id = %s,
               confidence = %s,
               note = %s,
               obj_name = %s,
               updated_at = now()
         where id = %s
        returning id
        """,
        (
            attr.value_text,
            attr.value_num,
            attr.value_unit,
            doc_id,
            obj_src_id,
            attr.confidence,
            attr.note,
            attr.obj_name,
            attr_id,
        ),
    )
    return int(cur.fetchone()[0])


def _upsert_object_attr(
    cur: psycopg.Cursor,
    *,
    obj_id: int,
    doc_id: int,
    obj_src_id: int | None,
    attr: ObjectAttrRow,
) -> tuple[int, str]:
    existing = _fetch_existing_object_attr(cur, obj_id=obj_id, attr=attr)
    if existing is None:
        return _insert_object_attr(cur, obj_id=obj_id, doc_id=doc_id, obj_src_id=obj_src_id, attr=attr), "inserted"
    if not _should_replace_existing_attr(existing, attr):
        return int(existing["id"]), "preserved_existing"
    return _update_object_attr(
        cur,
        attr_id=int(existing["id"]),
        doc_id=doc_id,
        obj_src_id=obj_src_id,
        attr=attr,
    ), "updated"


def _find_unsourced(cur: psycopg.Cursor) -> list[dict[str, Any]]:
    cur.execute(
        """
        select ro.id, ro.name
        from raw_objs ro
        where not exists (
            select 1 from obj_srcs os where os.obj_id = ro.id
        )
        order by ro.id
        """
    )
    return [{"id": int(obj_id), "name": name} for obj_id, name in cur.fetchall()]


def _import_payload_in_cursor(
    cur: psycopg.Cursor,
    payload: ImportPayload,
    *,
    emperor_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item_id, rule_ids = _load_rule_ids(cur, payload.item_code)
    missing_rules = sorted(
        {
            link.rule_code
            for obj in payload.objects
            for link in obj.links
            if link.rule_code not in rule_ids
        }
    )
    if missing_rules:
        raise ImportErrorWithContext(f"eval_rules missing rule_code(s): {', '.join(missing_rules)}")

    emp_id = _upsert_emperor(cur, payload.emperor, emperor_meta)
    source_ids = {source.src_key: _upsert_source(cur, source) for source in payload.sources}

    object_rows: list[dict[str, Any]] = []
    link_rows: list[dict[str, Any]] = []
    attr_rows: list[dict[str, Any]] = []
    alias_rows: list[dict[str, Any]] = []
    for obj in payload.objects:
        try:
            object_result = resolve_or_upsert_object(cur, obj, emp_id=emp_id)
        except ObjectAliasError as exc:
            raise ImportErrorWithContext(str(exc)) from exc
        obj_id = int(object_result["obj_id"])
        canonical_name = str(object_result["canonical_name"])
        alias_rows.extend(object_result["aliases"])
        emp_obj_id = _upsert_emp_object(cur, emp_id, obj_id, payload.subitem, canonical_name)
        object_rows.append(
            {
                "id": obj_id,
                "emp_obj_id": emp_obj_id,
                "name": obj.name,
                "canonical_name": canonical_name,
                "resolved_by_alias": object_result["resolved_by_alias"],
                "matched_alias": object_result["matched_alias"],
                "link_count": len(obj.links),
                "attr_count": len(obj.attrs),
                "alias_count": len(object_result["aliases"]),
            }
        )

        obj_src_by_src_key: dict[str, int] = {}
        for link_item in obj.links:
            obj_src_id = _upsert_obj_source(
                cur,
                obj_id=obj_id,
                emp_obj_id=emp_obj_id,
                doc_id=source_ids[link_item.src_key],
                item_id=item_id,
                rule_id=rule_ids[link_item.rule_code],
                link=link_item,
            )
            obj_src_by_src_key.setdefault(link_item.src_key, obj_src_id)
            link_rows.append(
                {
                    "id": obj_src_id,
                    "emp_obj_id": emp_obj_id,
                    "object": canonical_name,
                    "src_key": link_item.src_key,
                    "rule_code": link_item.rule_code,
                    "direction": link_item.direction,
                }
            )

        if obj.attrs:
            for attr in obj.attrs:
                attr_id, attr_action = _upsert_object_attr(
                    cur,
                    obj_id=obj_id,
                    doc_id=source_ids[attr.src_key],
                    obj_src_id=obj_src_by_src_key.get(attr.src_key),
                    attr=attr,
                )
                attr_rows.append(
                    {
                        "id": attr_id,
                        "object": canonical_name,
                        "attr_code": attr.attr_code,
                        "value_text": attr.value_text,
                        "value_num": attr.value_num,
                        "action": attr_action,
                    }
                )

    return {
        "emperor": {"id": emp_id, "name": payload.emperor.name},
        "sources": sorted(source_ids),
        "objects": object_rows,
        "object_aliases": alias_rows,
        "obj_srcs": link_rows,
        "obj_attrs": attr_rows,
        "counts": {
            "sources": len(source_ids),
            "objects": len(object_rows),
            "object_aliases": len(alias_rows),
            "obj_srcs": len(link_rows),
            "obj_attrs": len(attr_rows),
        },
    }


def import_payload(payload: ImportPayload, dsn: str, *, dry_run: bool = False) -> dict[str, Any]:
    report = import_payloads((payload,), dsn, dry_run=dry_run)
    single = report["payloads"][0]
    single["dry_run"] = dry_run
    single["unsourced"] = report["unsourced"]
    return single


def import_payloads(payloads: tuple[ImportPayload, ...], dsn: str, *, dry_run: bool = False) -> dict[str, Any]:
    if not dry_run and os.environ.get("I5B_OBJECT_POOL_IMPORT_UNFREEZE") != "1":
        raise ImportErrorWithContext("object pool import frozen; set I5B_OBJECT_POOL_IMPORT_UNFREEZE=1 to write.")
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            ensure_object_alias_schema(cur)
            reports = [
                _import_payload_in_cursor(cur, payload, emperor_meta=_raw_emperor_meta(payload))
                for payload in payloads
            ]
            unsourced = _find_unsourced(cur)
            if unsourced:
                raise ImportErrorWithContext(f"unsourced raw_objs after import: {unsourced}")

            report = {
                "dry_run": dry_run,
                "payloads": reports,
                "unsourced": unsourced,
            }

        if dry_run:
            conn.rollback()
        else:
            conn.commit()

    return report


def _raw_emperor_meta(payload: ImportPayload) -> dict[str, Any]:
    raw = getattr(payload, "_raw_emperor", None)
    return raw if isinstance(raw, dict) else {}


def _attach_raw_emperor(payload: ImportPayload, raw: dict[str, Any]) -> ImportPayload:
    object.__setattr__(payload, "_raw_emperor", raw)
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ImportErrorWithContext(f"{path}:{line_number}: invalid JSON") from exc
        rows.append(_require_mapping(row, f"{path}:{line_number}"))
    return rows


def load_query_profile(path: Path, person: str) -> dict[str, Any]:
    matches = [row for row in read_jsonl(path) if row.get("person") == person]
    if not matches:
        raise ImportErrorWithContext(f"profile not found for person: {person}")
    if len(matches) > 1:
        raise ImportErrorWithContext(f"multiple profiles found for person: {person}")
    return matches[0]


def _guess_object_type(name: str) -> str:
    if re.search(r"(案|事件|牵连|疑云|兵变)$", name):
        return "case"
    if re.search(r"(制度|兵制|机制|体系)$", name):
        return "mechanism"
    if re.search(r"(外戚|功臣|群体|集团|团队)$", name):
        return "group"
    return "person"


def _guess_direction(layer: str) -> str:
    if "negative" in layer or "reversal" in layer:
        return "negative"
    if "positive" in layer or "supplemental" in layer or "core" in layer:
        return "positive"
    return "mixed"


def build_template_payload(
    profile: dict[str, Any],
    *,
    item_code: str = "I5B",
    subitem: str = "第五项B",
    include_adjacent: bool = False,
) -> dict[str, Any]:
    person = _text(profile, "person", "profile")
    object_layers = _require_mapping(profile.get("object_layers"), "profile.object_layers")
    objects: list[dict[str, Any]] = []
    for layer, names in object_layers.items():
        if layer == "adjacent_split_objects" and not include_adjacent:
            continue
        for name in _require_list(names, f"profile.object_layers.{layer}"):
            if not isinstance(name, str) or not name.strip():
                raise ImportErrorWithContext(f"profile.object_layers.{layer}: expected non-empty string")
            cleaned = name.strip()
            objects.append(
                {
                    "obj_type": _guess_object_type(cleaned),
                    "period": "TODO",
                    "name": cleaned,
                    "retrieval_layer": layer,
                    "note": f"TODO: {cleaned} 的原始对象说明，只写身份或事件事实，不写评分方向。",
                    "links": [
                        {
                            "src_key": "TODO-SRC-1",
                            "rule_code": "TODO_RULE_CODE",
                            "direction": _guess_direction(layer),
                            "note": "TODO: 写清史料事实、对应维度和事实方向。",
                        }
                    ],
                    "attrs": [],
                }
            )
    return {
        "item_code": item_code,
        "subitem": subitem,
        "profile_person": person,
        "source_targets": profile.get("source_targets", []),
        "query_bundles": profile.get("query_bundles", []),
        "emperor": {
            "period": "TODO",
            "name": person,
            "title": "TODO",
            "sort_no": None,
            "is_founder": None,
            "succession_mode": "TODO",
            "power_origin": "TODO",
            "note": f"TODO: {person} 的皇帝表说明。",
        },
        "sources": [
            {
                "src_key": "TODO-SRC-1",
                "title": "TODO",
                "author": "",
                "dynasty": "",
                "volume": "",
                "locator": "TODO",
                "url": "",
                "note": "TODO: 史源说明。",
            }
        ],
        "objects": objects,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import sourced object-pool rows into PostgreSQL.")
    parser.add_argument("--input", type=Path, help="UTF-8 JSON import payload or payload batch.")
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV, help="Environment variable name for PostgreSQL DSN.")
    parser.add_argument("--dry-run", action="store_true", help="Run import in a rolled-back transaction.")
    parser.add_argument("--template-from-profile", type=Path, help="Build a review payload skeleton from query profile JSONL.")
    parser.add_argument("--person", help="Person name to select from --template-from-profile.")
    parser.add_argument("--include-adjacent", action="store_true", help="Include adjacent_split_objects in generated template.")
    parser.add_argument("--output", type=Path, help="Write generated template JSON here instead of stdout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.template_from_profile:
        if not args.person:
            parser.error("--person is required with --template-from-profile")
        profile = load_query_profile(args.template_from_profile, args.person)
        template = build_template_payload(profile, include_adjacent=args.include_adjacent)
        text = json.dumps(template, ensure_ascii=False, indent=2, sort_keys=True)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text + "\n", encoding="utf-8")
        else:
            print(text)
        return 0
    if not args.input:
        parser.error("--input is required unless --template-from-profile is used")
    payloads = load_payloads(args.input)
    report = import_payloads(payloads, resolve_dsn(args.dsn_env), dry_run=args.dry_run)
    if len(payloads) == 1:
        single = report["payloads"][0]
        single["dry_run"] = report["dry_run"]
        single["unsourced"] = report["unsourced"]
        report = single
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
