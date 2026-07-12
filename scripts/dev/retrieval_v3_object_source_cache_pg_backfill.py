from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v3_import_plan import ImportPlanError, json_param, stable_hash, write_json  # noqa: E402
from scripts.dev.retrieval_v3_intake_manifest import text  # noqa: E402
from scripts.dev.retrieval_v3_pg_schema import DEFAULT_V3_DSN_ENV, pg_schema_name, schema_cursor, table_label  # noqa: E402


SOURCE = "retrieval_v3_object_source_cache_pg_backfill"
PERSON_OBJECT_TYPES = {"person"}
PERSON_STAGE_SUFFIX_RE = re.compile(r"(?:早期|中期|晚期)$")

TARGET_SQL = """
select
    id as target_id,
    target_code,
    emperor_name,
    item_code
from retrieval_v3.retrieval_targets
where target_status = 'active'
  and emperor_name = any(%s)
  and (%s = '' or item_code = %s)
order by item_code, emperor_name, id
"""


class ObjectSourceCacheBackfillError(RuntimeError):
    pass


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ObjectSourceCacheBackfillError(f"{path}:{line_no}: expected JSON object")
        rows.append(row)
    return rows


def seed_paths(cache_root: Path) -> list[Path]:
    seed_dir = cache_root / "seeds"
    if not seed_dir.exists():
        return []
    return sorted(seed_dir.glob("*.jsonl"))


def load_cache_rows(cache_root: Path) -> dict[str, list[dict[str, Any]]]:
    seeds: list[dict[str, Any]] = []
    for path in seed_paths(cache_root):
        seeds.extend(read_jsonl(path))
    return {
        "seeds": seeds,
        "coverage": read_jsonl(cache_root / "person_coverage.jsonl"),
        "source_documents": read_jsonl(cache_root / "source_documents.jsonl"),
        "mention_slices": read_jsonl(cache_root / "mention_slices.jsonl"),
    }


def normalized_name(value: Any) -> str:
    return "".join(str(value or "").split())


def canonical_person_name(value: Any) -> str:
    name = text(value)
    canonical = PERSON_STAGE_SUFFIX_RE.sub("", name).strip()
    return canonical or name


def list_texts(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in value:
        name = text(item)
        if name and name not in seen:
            seen.add(name)
            out.append(name)
    return out


def raw_object_identity(seed: Mapping[str, Any]) -> str:
    raw_code = text(seed.get("object_code"))
    if raw_code.startswith("raw_obj:"):
        return f"raw_obj|{raw_code.split(':', 1)[1]}"
    return "|".join(
        [
            "object_source_cache",
            "type",
            text(seed.get("object_type") or "person"),
            "period",
            text(seed.get("period")),
            "name",
            normalized_name(seed.get("normalized_name") or seed.get("name")),
        ]
    )


def object_code(identity_key: str) -> str:
    return "OBJ-" + stable_hash(["object_source_cache", identity_key], length=16)


def object_name_code(*, identity_key: str, normalized: str, name_kind: str) -> str:
    return "ONM-" + stable_hash([identity_key, normalized, name_kind], length=16)


def profile_code(identity_key: str) -> str:
    return "PRF-" + stable_hash(["object_source_cache_profile", identity_key], length=16)


def affiliation_key(identity_key: str, period: str) -> str:
    return "|".join([identity_key, "affiliation", "dynasty", period])


def affiliation_code(key: str) -> str:
    return "PAF-" + stable_hash(key, length=16)


def target_object_code(*, target_code: str, identity_key: str, scope_code: str = "item") -> str:
    return "TOB-" + stable_hash([target_code, identity_key, scope_code, SOURCE], length=16)


def coverage_by_person(rows: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        name = text(row.get("person_name"))
        if name:
            indexed[name] = row
    return indexed


def rows_by_person(rows: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    indexed: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        name = text(row.get("person_name"))
        if name:
            indexed[name].append(row)
    return dict(indexed)


def alias_rows(seed: Mapping[str, Any]) -> list[dict[str, str]]:
    canonical = text(seed.get("name"))
    expanded = set(list_texts(seed.get("expanded_aliases")))
    rows: list[dict[str, str]] = []
    for item in seed.get("object_pool_aliases") or []:
        if not isinstance(item, Mapping):
            continue
        name = text(item.get("alias"))
        if not name:
            continue
        raw_kind = text(item.get("alias_kind"))
        kind = "canonical" if raw_kind == "canonical" or name == canonical else "alias"
        rows.append({"name_text": name, "name_kind": kind, "source_alias_kind": raw_kind})
        expanded.discard(name)
    for name in list_texts(seed.get("aliases")):
        if name not in {row["name_text"] for row in rows}:
            kind = "canonical" if name == canonical else "alias"
            rows.append({"name_text": name, "name_kind": kind, "source_alias_kind": "aliases"})
        expanded.discard(name)
    for name in sorted(expanded):
        if name != canonical:
            rows.append({"name_text": name, "name_kind": "script_variant", "source_alias_kind": "expanded_aliases"})
    if canonical and canonical not in {row["name_text"] for row in rows}:
        rows.insert(0, {"name_text": canonical, "name_kind": "canonical", "source_alias_kind": "seed_name"})

    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = (normalized_name(row["name_text"]), row["name_kind"])
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    return deduped


def compact_doc_summary(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []
    for row in rows[:20]:
        summary.append(
            {
                "document_cache_code": text(row.get("document_cache_code")),
                "source_key": text(row.get("source_key")),
                "source_title": text(row.get("source_title") or row.get("title")),
                "source_role": text(row.get("source_role")),
                "source_shape": text(row.get("source_shape")),
                "mention_slice_count": row.get("mention_slice_count"),
            }
        )
    return summary


def seed_payload(
    seed: Mapping[str, Any],
    *,
    coverage: Mapping[str, Any],
    documents: Sequence[Mapping[str, Any]],
    mention_slices: Sequence[Mapping[str, Any]],
    cache_root: Path,
) -> dict[str, Any]:
    return {
        "source": SOURCE,
        "cache_root": str(cache_root),
        "person_cache_code": text(seed.get("person_cache_code") or coverage.get("person_cache_code")),
        "object_pool_code": text(seed.get("object_code")),
        "seed_sources": list_texts(seed.get("seed_sources")),
        "period": text(seed.get("period")),
        "target_emperors": list_texts(seed.get("target_emperors")),
        "source_hints": list_texts(seed.get("source_hints")),
        "source_document_hints": seed.get("source_document_hints") or [],
        "coverage": {
            "has_source_document": bool(coverage.get("has_source_document")),
            "has_biography_source": bool(coverage.get("has_biography_source")),
            "has_emperor_context_source": bool(coverage.get("has_emperor_context_source")),
            "needs_agent_review": bool(coverage.get("needs_agent_review")),
            "claim_closure_risk": text(coverage.get("claim_closure_risk")),
            "source_document_count": coverage.get("source_document_count"),
            "mention_slice_count": coverage.get("mention_slice_count"),
            "source_roles": coverage.get("source_roles") or [],
            "source_shapes": coverage.get("source_shapes") or [],
        },
        "cache_documents": compact_doc_summary(documents),
        "cache_document_count": len(documents),
        "cache_mention_slice_count": len(mention_slices),
    }


def build_object_rows(
    *,
    cache_root: Path,
    cache_rows: Mapping[str, Sequence[Mapping[str, Any]]],
    target_rows: Sequence[Mapping[str, Any]] = (),
    item_code: str = "",
    schema_name: str | None = None,
) -> dict[str, Any]:
    schema = pg_schema_name(schema_name)
    coverage_index = coverage_by_person(cache_rows.get("coverage") or [])
    docs_index = rows_by_person(cache_rows.get("source_documents") or [])
    slices_index = rows_by_person(cache_rows.get("mention_slices") or [])
    targets_by_emperor: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in target_rows:
        emperor = text(row.get("emperor_name"))
        if emperor:
            targets_by_emperor[emperor].append(row)

    objects: list[dict[str, Any]] = []
    names: list[dict[str, Any]] = []
    target_objects: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    affiliations: list[dict[str, Any]] = []
    review_needed: dict[str, list[dict[str, Any]]] = {
        "unsupported_object_type": [],
        "missing_target": [],
        "missing_period": [],
    }
    seen_identity: set[str] = set()
    seen_name_keys: set[tuple[str, str, str]] = set()

    for seed in cache_rows.get("seeds") or []:
        object_type = text(seed.get("object_type") or "person")
        source_name = text(seed.get("name"))
        if not source_name:
            continue
        name = canonical_person_name(source_name)
        if object_type not in PERSON_OBJECT_TYPES:
            review_needed["unsupported_object_type"].append({"name": name, "object_type": object_type})
            continue
        identity_key = raw_object_identity(seed)
        obj_code = object_code(identity_key)
        identity_names = sorted(
            {
                normalized_name(canonical_person_name(row["name_text"]))
                for row in alias_rows(seed)
                if normalized_name(canonical_person_name(row["name_text"]))
            }
        )
        coverage = coverage_index.get(source_name) or {}
        documents = docs_index.get(source_name) or []
        mention_slices = slices_index.get(source_name) or []
        payload = seed_payload(
            seed,
            coverage=coverage,
            documents=documents,
            mention_slices=mention_slices,
            cache_root=cache_root,
        )
        if identity_key not in seen_identity:
            seen_identity.add(identity_key)
            objects.append(
                {
                    "object_code": obj_code,
                    "object_identity_key": identity_key,
                    "canonical_name": name,
                    "normalized_name": normalized_name(name),
                    "object_type": "person",
                    "identity_status": "active",
                    "curator_note": "",
                    "identity_payload": payload,
                    "identity_aliases": identity_names,
                    "identity_period": text(seed.get("period")),
                }
            )
            profiles.append(
                {
                    "person_profile_code": profile_code(identity_key),
                    "object_code": obj_code,
                    "talent_grade": None,
                    "talent_grade_basis": "",
                    "review_status": "pending",
                    "profile_payload": payload,
                }
            )
            period = text(seed.get("period"))
            if period:
                key = affiliation_key(identity_key, period)
                affiliations.append(
                    {
                        "person_affiliation_code": affiliation_code(key),
                        "person_affiliation_key": key,
                        "object_code": obj_code,
                        "affiliation_kind": "dynasty",
                        "dynasty_label": period,
                        "polity_label": "",
                        "affiliation_label": "",
                        "period_label": "",
                        "period_start_year": None,
                        "period_end_year": None,
                        "affiliation_basis": f"{name}，对象源缓存种子标记时期为{period}。",
                        "review_status": "pending",
                        "affiliation_payload": payload,
                    }
                )
            else:
                review_needed["missing_period"].append({"name": name, "object_code": obj_code})

        for alias in alias_rows(seed):
            alias_text = canonical_person_name(alias.get("name_text"))
            kind = text(alias.get("name_kind"))
            norm = normalized_name(alias_text)
            name_key = (identity_key, norm, kind)
            if not alias_text or not norm or name_key in seen_name_keys:
                continue
            seen_name_keys.add(name_key)
            names.append(
                {
                    "object_name_code": object_name_code(identity_key=identity_key, normalized=norm, name_kind=kind),
                    "object_code": obj_code,
                    "name_text": alias_text,
                    "normalized_name": norm,
                    "name_kind": kind,
                    "script_variant_group_key": normalized_name(name),
                    "source": SOURCE,
                    "review_status": "pending",
                    "name_payload": {**payload, "source_alias_kind": text(alias.get("source_alias_kind"))},
                }
            )

        matched_targets = []
        for emperor in list_texts(seed.get("target_emperors")):
            matched = targets_by_emperor.get(emperor) or []
            if not matched:
                review_needed["missing_target"].append(
                    {"name": name, "target_emperor": emperor, "item_code": item_code, "object_code": obj_code}
                )
            matched_targets.extend(matched)
        for target in matched_targets:
            target_code = text(target.get("target_code"))
            target_objects.append(
                {
                    "target_object_code": target_object_code(target_code=target_code, identity_key=identity_key),
                    "target_id": int(target.get("target_id")),
                    "object_code": obj_code,
                    "scope_code": "item",
                    "object_role": "source_cache_object",
                    "review_status": "pending",
                    "target_object_payload": {
                        **payload,
                        "target_code": target_code,
                        "target_emperor": text(target.get("emperor_name")),
                        "item_code": text(target.get("item_code")),
                    },
                }
            )

    operation_counts = {
        table_label("objects", schema_name=schema): len(objects),
        table_label("object_names", schema_name=schema): len(names),
        table_label("target_objects", schema_name=schema): len(target_objects),
        table_label("person_profiles", schema_name=schema): len(profiles),
        table_label("person_affiliations", schema_name=schema): len(affiliations),
    }
    return {
        "generated_by": f"scripts/dev/{Path(__file__).name}",
        "mode": "dry_run_object_source_cache_pg_backfill",
        "schema_name": schema,
        "cache_root": str(cache_root),
        "write_db": False,
        "executed": False,
        "ok": True,
        "item_code": item_code,
        "totals": {
            "seed_rows": len(cache_rows.get("seeds") or []),
            "coverage_rows": len(cache_rows.get("coverage") or []),
            "source_document_rows": len(cache_rows.get("source_documents") or []),
            "mention_slice_rows": len(cache_rows.get("mention_slices") or []),
            "target_rows": len(target_rows),
            "object_rows": len(objects),
            "object_name_rows": len(names),
            "target_object_rows": len(target_objects),
            "profile_rows": len(profiles),
            "affiliation_rows": len(affiliations),
        },
        "operation_counts": operation_counts,
        "review_needed": {key: rows for key, rows in review_needed.items() if rows},
        "object_rows": objects,
        "object_name_rows": names,
        "target_object_rows": target_objects,
        "profile_rows": profiles,
        "affiliation_rows": affiliations,
        "executed_counts": {},
    }


def fetch_target_rows(cur: Any, *, emperor_names: Sequence[str], item_code: str = "") -> list[dict[str, Any]]:
    names = sorted({text(name) for name in emperor_names if text(name)})
    if not names:
        return []
    cur.execute(TARGET_SQL, (names, item_code, item_code))
    return [dict(row) for row in cur.fetchall()]


def fetch_one_id(cur: Any) -> int:
    row = cur.fetchone()
    if not row or row.get("id") is None:
        raise ImportPlanError("expected statement to return id")
    return int(row["id"])


def upsert_object(cur: Any, row: Mapping[str, Any]) -> int:
    aliases = [text(value) for value in row.get("identity_aliases") or [] if text(value)]
    period = text(row.get("identity_period"))
    if aliases and period:
        cur.execute(
            """
            select o.id, bool_or(pa.dynasty_label=%s) as period_match
              from retrieval_v3.objects o
              join retrieval_v3.object_names n on n.object_id=o.id
              left join retrieval_v3.person_affiliations pa
                on pa.object_id=o.id and pa.review_status in ('pending','accepted')
             where o.identity_status='active'
               and o.object_type='person'
               and n.normalized_name=any(%s)
             group by o.id
             order by o.id
            """,
            (period, aliases),
        )
        match_rows = cur.fetchall()
        matches = [int(match["id"] if isinstance(match, Mapping) else match[0]) for match in match_rows]
        if len(matches) > 1:
            period_matches = [
                int(match["id"] if isinstance(match, Mapping) else match[0])
                for match in match_rows
                if bool(match.get("period_match") if isinstance(match, Mapping) else match[1])
            ]
            if len(period_matches) == 1:
                matches = period_matches
        if len(matches) > 1:
            raise ObjectSourceCacheBackfillError(f"ambiguous active object aliases for {row.get('canonical_name')}: {matches}")
        if matches:
            cur.execute(
                """update retrieval_v3.objects set identity_payload=identity_payload||%s::jsonb,updated_at=now() where id=%s returning id""",
                (json_param(row.get("identity_payload") or {}), matches[0]),
            )
            return fetch_one_id(cur)
    cur.execute(
        """
        insert into retrieval_v3.objects (
            object_code, object_identity_key, canonical_name, normalized_name,
            object_type, identity_status, curator_note, identity_payload
        )
        values (%s, %s, %s, %s, %s::retrieval_v3.rv3_object_type, %s::retrieval_v3.rv3_object_identity_status, %s, %s::jsonb)
        on conflict on constraint rv3_objects_identity_key_uk do update set
            canonical_name = excluded.canonical_name,
            normalized_name = excluded.normalized_name,
            object_type = excluded.object_type,
            identity_status = case
                when retrieval_v3.objects.identity_status in ('merged', 'rejected', 'retired') then retrieval_v3.objects.identity_status
                else excluded.identity_status
            end,
            curator_note = case
                when btrim(retrieval_v3.objects.curator_note) <> '' then retrieval_v3.objects.curator_note
                else excluded.curator_note
            end,
            identity_payload = retrieval_v3.objects.identity_payload || excluded.identity_payload,
            updated_at = now()
        returning id
        """,
        (
            text(row.get("object_code")),
            text(row.get("object_identity_key")),
            text(row.get("canonical_name")),
            text(row.get("normalized_name")),
            text(row.get("object_type")),
            text(row.get("identity_status")),
            text(row.get("curator_note")),
            json_param(row.get("identity_payload") or {}),
        ),
    )
    return fetch_one_id(cur)


def upsert_object_name(cur: Any, row: Mapping[str, Any], *, object_id: int) -> int:
    cur.execute(
        """
        insert into retrieval_v3.object_names (
            object_name_code, object_id, name_text, normalized_name, name_kind,
            script_variant_group_key, source, review_status, name_payload
        )
        values (%s, %s, %s, %s, %s::retrieval_v3.rv3_object_name_kind, %s, %s, %s::retrieval_v3.rv3_review_status, %s::jsonb)
        on conflict on constraint rv3_object_names_name_uk do update set
            name_text = excluded.name_text,
            script_variant_group_key = excluded.script_variant_group_key,
            review_status = case
                when retrieval_v3.object_names.review_status in ('rejected', 'retired') then retrieval_v3.object_names.review_status
                else excluded.review_status
            end,
            name_payload = retrieval_v3.object_names.name_payload || excluded.name_payload
        returning id
        """,
        (
            text(row.get("object_name_code")),
            object_id,
            text(row.get("name_text")),
            text(row.get("normalized_name")),
            text(row.get("name_kind")),
            text(row.get("script_variant_group_key")),
            text(row.get("source")),
            text(row.get("review_status")),
            json_param(row.get("name_payload") or {}),
        ),
    )
    return fetch_one_id(cur)


def upsert_target_object(cur: Any, row: Mapping[str, Any], *, object_id: int) -> int:
    cur.execute(
        """
        insert into retrieval_v3.target_objects (
            target_object_code, target_id, object_id, scope_code, object_role,
            review_status, target_object_payload
        )
        values (%s, %s, %s, %s::retrieval_v3.rv3_target_object_scope, %s, %s::retrieval_v3.rv3_review_status, %s::jsonb)
        on conflict on constraint rv3_target_objects_scope_uk do update set
            object_role = case
                when btrim(retrieval_v3.target_objects.object_role) <> '' then retrieval_v3.target_objects.object_role
                else excluded.object_role
            end,
            review_status = case
                when retrieval_v3.target_objects.review_status in ('rejected', 'retired') then retrieval_v3.target_objects.review_status
                else excluded.review_status
            end,
            target_object_payload = retrieval_v3.target_objects.target_object_payload || excluded.target_object_payload,
            updated_at = now()
        returning id
        """,
        (
            text(row.get("target_object_code")),
            int(row.get("target_id")),
            object_id,
            text(row.get("scope_code")),
            text(row.get("object_role")),
            text(row.get("review_status")),
            json_param(row.get("target_object_payload") or {}),
        ),
    )
    return fetch_one_id(cur)


def upsert_profile(cur: Any, row: Mapping[str, Any], *, object_id: int) -> int:
    cur.execute(
        """
        insert into retrieval_v3.person_profiles (
            person_profile_code, object_id, talent_grade, talent_grade_basis,
            review_status, profile_payload
        )
        values (%s, %s, %s::retrieval_v3.rv3_person_talent_grade, %s, %s::retrieval_v3.rv3_review_status, %s::jsonb)
        on conflict on constraint rv3_person_profiles_object_uk do update set
            person_profile_code = retrieval_v3.person_profiles.person_profile_code,
            talent_grade = coalesce(retrieval_v3.person_profiles.talent_grade, excluded.talent_grade),
            talent_grade_basis = case
                when btrim(retrieval_v3.person_profiles.talent_grade_basis) <> ''
                    then retrieval_v3.person_profiles.talent_grade_basis
                else excluded.talent_grade_basis
            end,
            review_status = case
                when retrieval_v3.person_profiles.review_status in ('rejected', 'retired') then retrieval_v3.person_profiles.review_status
                else excluded.review_status
            end,
            profile_payload = retrieval_v3.person_profiles.profile_payload || excluded.profile_payload,
            updated_at = now()
        returning id
        """,
        (
            text(row.get("person_profile_code")),
            object_id,
            row.get("talent_grade"),
            text(row.get("talent_grade_basis")),
            text(row.get("review_status")),
            json_param(row.get("profile_payload") or {}),
        ),
    )
    return fetch_one_id(cur)


def upsert_affiliation(cur: Any, row: Mapping[str, Any], *, object_id: int) -> int:
    cur.execute(
        """
        select id
          from retrieval_v3.person_affiliations
         where object_id=%s
           and affiliation_kind=%s::retrieval_v3.rv3_person_affiliation_kind
           and dynasty_label=%s
           and polity_label=%s
           and affiliation_label=%s
           and period_label=%s
           and review_status in ('pending','accepted')
         order by id
         limit 1
        """,
        (
            object_id,
            text(row.get("affiliation_kind")),
            text(row.get("dynasty_label")),
            text(row.get("polity_label")),
            text(row.get("affiliation_label")),
            text(row.get("period_label")),
        ),
    )
    existing = cur.fetchone()
    if existing and existing.get("id") is not None:
        cur.execute(
            """
            update retrieval_v3.person_affiliations
               set affiliation_payload=affiliation_payload||%s::jsonb, updated_at=now()
             where id=%s
         returning id
            """,
            (json_param(row.get("affiliation_payload") or {}), int(existing["id"])),
        )
        return fetch_one_id(cur)
    cur.execute(
        """
        insert into retrieval_v3.person_affiliations (
            person_affiliation_code, person_affiliation_key, object_id, affiliation_kind,
            dynasty_label, polity_label, affiliation_label, period_label,
            period_start_year, period_end_year, affiliation_basis, review_status,
            affiliation_payload
        )
        values (
            %s, %s, %s, %s::retrieval_v3.rv3_person_affiliation_kind,
            %s, %s, %s, %s,
            %s, %s, %s, %s::retrieval_v3.rv3_review_status,
            %s::jsonb
        )
        on conflict on constraint rv3_person_affiliations_key_uk do update set
            dynasty_label = excluded.dynasty_label,
            polity_label = excluded.polity_label,
            affiliation_label = excluded.affiliation_label,
            period_label = excluded.period_label,
            period_start_year = excluded.period_start_year,
            period_end_year = excluded.period_end_year,
            affiliation_basis = case
                when btrim(retrieval_v3.person_affiliations.affiliation_basis) <> ''
                    then retrieval_v3.person_affiliations.affiliation_basis
                else excluded.affiliation_basis
            end,
            review_status = case
                when retrieval_v3.person_affiliations.review_status in ('rejected', 'retired') then retrieval_v3.person_affiliations.review_status
                else excluded.review_status
            end,
            affiliation_payload = retrieval_v3.person_affiliations.affiliation_payload || excluded.affiliation_payload,
            updated_at = now()
        returning id
        """,
        (
            text(row.get("person_affiliation_code")),
            text(row.get("person_affiliation_key")),
            object_id,
            text(row.get("affiliation_kind")),
            text(row.get("dynasty_label")),
            text(row.get("polity_label")),
            text(row.get("affiliation_label")),
            text(row.get("period_label")),
            row.get("period_start_year"),
            row.get("period_end_year"),
            text(row.get("affiliation_basis")),
            text(row.get("review_status")),
            json_param(row.get("affiliation_payload") or {}),
        ),
    )
    return fetch_one_id(cur)


def execute_upserts(cur: Any, payload: Mapping[str, Any]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    object_ids: dict[str, int] = {}
    for row in payload.get("object_rows") or []:
        object_ids[text(row.get("object_code"))] = upsert_object(cur, row)
        counts["objects"] += 1
    for row in payload.get("object_name_rows") or []:
        upsert_object_name(cur, row, object_id=object_ids[text(row.get("object_code"))])
        counts["object_names"] += 1
    for row in payload.get("target_object_rows") or []:
        upsert_target_object(cur, row, object_id=object_ids[text(row.get("object_code"))])
        counts["target_objects"] += 1
    for row in payload.get("profile_rows") or []:
        upsert_profile(cur, row, object_id=object_ids[text(row.get("object_code"))])
        counts["person_profiles"] += 1
    for row in payload.get("affiliation_rows") or []:
        upsert_affiliation(cur, row, object_id=object_ids[text(row.get("object_code"))])
        counts["person_affiliations"] += 1
    schema = text(payload.get("schema_name")) or pg_schema_name()
    return {table_label(name, schema_name=schema): count for name, count in sorted(counts.items())}


def execute_backfill(
    *,
    cache_root: Path,
    env_file: Path | None,
    dsn_env: str,
    schema_name: str,
    item_code: str,
    execute: bool,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    cache_rows = load_cache_rows(cache_root)
    emperor_names = sorted(
        {
            name
            for seed in cache_rows.get("seeds") or []
            for name in list_texts(seed.get("target_emperors"))
        }
    )
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            target_rows = fetch_target_rows(cur, emperor_names=emperor_names, item_code=item_code)
            payload = build_object_rows(
                cache_root=cache_root,
                cache_rows=cache_rows,
                target_rows=target_rows,
                item_code=item_code,
                schema_name=schema_name,
            )
            payload["mode"] = "execute" if execute else "dry_run_object_source_cache_pg_backfill"
            payload["write_db"] = execute
            if not execute:
                conn.rollback()
                return payload
            payload["executed_counts"] = execute_upserts(cur, payload)
            payload["executed"] = True
        conn.commit()
    return payload


def markdown_report(payload: Mapping[str, Any]) -> str:
    totals = payload.get("totals") or {}
    lines = [
        "# retrieval_v3 object source cache PG backfill report",
        "",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- schema_name: `{payload.get('schema_name')}`",
        f"- write_db: `{str(payload.get('write_db')).lower()}`",
        f"- executed: `{str(payload.get('executed')).lower()}`",
        f"- seed_rows: `{totals.get('seed_rows', 0)}`",
        f"- object_rows: `{totals.get('object_rows', 0)}`",
        f"- object_name_rows: `{totals.get('object_name_rows', 0)}`",
        f"- target_object_rows: `{totals.get('target_object_rows', 0)}`",
        f"- profile_rows: `{totals.get('profile_rows', 0)}`",
        f"- affiliation_rows: `{totals.get('affiliation_rows', 0)}`",
        "",
        "## Operation Counts",
        "",
        "| table | rows |",
        "| --- | ---: |",
    ]
    for table, count in (payload.get("operation_counts") or {}).items():
        lines.append(f"| {table} | {count} |")
    review_needed = payload.get("review_needed") or {}
    if review_needed:
        lines.extend(["", "## Review Needed", ""])
        for key, rows in review_needed.items():
            lines.append(f"- {key}: `{len(rows)}`")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill retrieval_v3 object pool/profile base tables from object source cache artifacts."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    apply = subparsers.add_parser("apply", help="Plan or apply object source cache base-table backfill.")
    apply.add_argument("--cache-root", type=Path, required=True)
    apply.add_argument("--output-json", type=Path, required=True)
    apply.add_argument("--output-md", type=Path, required=True)
    apply.add_argument("--env-file", type=Path)
    apply.add_argument("--dsn-env", default=DEFAULT_V3_DSN_ENV)
    apply.add_argument("--pg-schema", default="retrieval_v3")
    apply.add_argument("--item-code", default="")
    apply.add_argument("--execute", action="store_true", help="Actually commit PG upserts. Omit for dry-run.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "apply":
        raise ObjectSourceCacheBackfillError(f"unsupported command: {args.command}")
    payload = execute_backfill(
        cache_root=args.cache_root,
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        schema_name=args.pg_schema,
        item_code=args.item_code,
        execute=args.execute,
    )
    write_json(args.output_json, payload)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(markdown_report(payload), encoding="utf-8", newline="\n")
    print(json.dumps({"ok": payload["ok"], "write_db": payload["write_db"], "totals": payload["totals"]}, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
