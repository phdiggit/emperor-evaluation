from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v2_bootstrap import import_psycopg, load_env_file, resolve_dsn  # noqa: E402
from scripts.dev.retrieval_v2_pg_schema import DEFAULT_V3_DSN_ENV, schema_cursor  # noqa: E402
from scripts.dev import retrieval_v2_alias_pretag as alias_pretag  # noqa: E402
from scripts.dev.retrieval_v2_target_alias_backfill import (  # noqa: E402
    DEFAULT_ALIAS_FILE,
    DEFAULT_EMPEROR_LIST,
    alias_payload,
    alias_rows_for_emperors,
    load_alias_seed,
    load_emperor_names,
)


DEFAULT_DSN_ENV = DEFAULT_V3_DSN_ENV
RULER_ACTION_TYPES = {"任命", "授权", "处置", "收权", "制度高压"}
CONTEXT_ONLY_OWNER_RELATION_TERMS = ("亲礼", "所亲", "亲待", "礼遇")
DEFAULT_INVENTORY_SAMPLE_LIMIT = 20
OWNER_REBIND_HIGH_RISK_ALIASES = {"高祖", "高宗", "太宗", "文帝", "惠帝", "汉王", "武周"}
OWNER_REBIND_BARE_TITLE_RULES = {"same_dynasty_bare_title_scope", "source_title_dynasty_bare_title"}


class ClaimOwnerAuditError(RuntimeError):
    pass


@dataclass(frozen=True)
class OwnerAliasBook:
    aliases_by_owner: dict[str, list[str]]
    scoped_aliases_by_requested: dict[str, dict[str, list[str]]]
    source: str
    resolver: alias_pretag.AliasResolver


@dataclass(frozen=True)
class OwnerMatch:
    owner_name: str
    alias: str
    source: str
    mention: dict[str, Any]


def text(value: Any) -> str:
    return str(value or "").strip()


def as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def unique_strings(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        item = text(value)
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8", newline="\n")


def owner_alias_book_from_rows(rows: Sequence[Mapping[str, Any]], *, source: str) -> OwnerAliasBook:
    aliases: dict[str, list[str]] = defaultdict(list)
    scoped: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        owner_name = text(row.get("emperor_name"))
        alias = text(row.get("alias"))
        if not owner_name or not alias:
            continue
        payload = as_mapping(row.get("alias_payload"))
        scopes = payload.get("scopes") or []
        if isinstance(scopes, str):
            scopes = [scopes]
        clean_scopes = unique_strings([text(scope) for scope in scopes if text(scope)])
        if clean_scopes:
            for requested_owner in clean_scopes:
                scoped[requested_owner][owner_name] = unique_strings([*scoped[requested_owner][owner_name], alias])
        else:
            aliases[owner_name] = unique_strings([*aliases[owner_name], alias])
    return OwnerAliasBook(
        aliases_by_owner={owner: unique_strings(values) for owner, values in sorted(aliases.items())},
        scoped_aliases_by_requested={
            requested: {owner: unique_strings(values) for owner, values in sorted(owner_map.items())}
            for requested, owner_map in sorted(scoped.items())
        },
        source=source,
        resolver=alias_pretag.alias_resolver_from_rows(rows, source=source),
    )


def load_owner_aliases(path: Path | None = None) -> OwnerAliasBook:
    if path is None:
        emperor_names = load_emperor_names(DEFAULT_EMPEROR_LIST)
        alias_seed = load_alias_seed(DEFAULT_ALIAS_FILE)
        rows = [
            {**row, "alias_payload": alias_payload(row)}
            for row in alias_rows_for_emperors(emperor_names, alias_seed)
        ]
        return owner_alias_book_from_rows(rows, source="yaml_seed")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ClaimOwnerAuditError("--owner-aliases-json must contain an object keyed by canonical owner name")
    rows: list[dict[str, Any]] = []
    for owner_name, raw_aliases in payload.items():
        if isinstance(raw_aliases, str):
            incoming = [raw_aliases]
        elif isinstance(raw_aliases, list):
            incoming = [text(item) for item in raw_aliases]
        else:
            raise ClaimOwnerAuditError(f"owner aliases for {owner_name!r} must be a string or list")
        for alias in unique_strings([text(owner_name), *incoming]):
            rows.append({"emperor_name": text(owner_name), "alias": alias, "alias_payload": {}})
    return owner_alias_book_from_rows(rows, source=str(path))


def fetch_owner_alias_book(cur: Any) -> OwnerAliasBook:
    cur.execute(
        """
        select
            t.emperor_name,
            a.alias,
            a.alias_type,
            a.alias_payload
          from retrieval_v2.retrieval_targets t
          join retrieval_v2.target_aliases a on a.target_id = t.id
         where a.status = 'active'
         order by t.emperor_name, a.alias_type, a.alias
        """
    )
    return owner_alias_book_from_rows([dict(row) for row in cur.fetchall()], source="target_aliases")


def scoped_aliases_by_owner(requested_emperor_name: str, alias_book: OwnerAliasBook) -> dict[str, list[str]]:
    scoped: dict[str, list[str]] = {name: list(values) for name, values in alias_book.aliases_by_owner.items()}
    for owner_name, aliases in (alias_book.scoped_aliases_by_requested.get(text(requested_emperor_name)) or {}).items():
        scoped[text(owner_name)] = unique_strings([*scoped.get(text(owner_name), []), *aliases])
    return scoped


def registered_owner_names(alias_book: OwnerAliasBook) -> set[str]:
    names = set(alias_book.aliases_by_owner)
    for owner_map in alias_book.scoped_aliases_by_requested.values():
        names.update(owner_map)
    return {name for name in names if name}


def alias_context_valid(text_value: str, alias: str, index: int) -> bool:
    if alias == "吕后" and index > 0 and text_value[index - 1] == "诸":
        return False
    suffix = text_value[index + len(alias) : index + len(alias) + 4]
    if suffix.startswith(("崩后", "崩後", "卒后", "卒後", "死后", "死後")):
        return False
    return True


def alias_matches(
    text_value: str,
    aliases_by_owner: Mapping[str, Sequence[str]],
    *,
    requested_owner_name: str = "",
    alias_book: OwnerAliasBook | None = None,
    source_title: str = "",
) -> list[OwnerMatch]:
    if alias_book is not None:
        matches: list[OwnerMatch] = []
        for mention in alias_pretag.alias_mentions_in_text(
            text_value,
            requested_owner_name=requested_owner_name,
            source_title=source_title,
            resolver=alias_book.resolver,
        ):
            if text(mention.get("resolution_status")) != "resolved":
                continue
            if mention.get("owner_anchor_eligible") is False:
                continue
            alias = text(mention.get("alias"))
            start = int(mention.get("start") or 0)
            if not alias or not alias_context_valid(text_value, alias, start):
                continue
            matches.append(
                OwnerMatch(
                    owner_name=text(mention.get("resolved_owner_name")),
                    alias=alias,
                    source="structured_mention",
                    mention=dict(mention),
                )
            )
        matches.sort(key=lambda item: (-len(item.alias), item.owner_name, item.alias))
        return matches

    matches: list[OwnerMatch] = []
    for owner_name, aliases in sorted(aliases_by_owner.items()):
        for alias in aliases:
            term = text(alias)
            if not term:
                continue
            start = 0
            while True:
                index = text_value.find(term, start)
                if index < 0:
                    break
                if alias_context_valid(text_value, term, index):
                    matches.append(OwnerMatch(owner_name=text(owner_name), alias=term, source="text", mention={}))
                    break
                start = index + max(1, len(term))
    matches.sort(key=lambda item: (-len(item.alias), item.owner_name, item.alias))
    return matches


def unique_match_owners(matches: Sequence[OwnerMatch]) -> list[str]:
    return unique_strings([match.owner_name for match in matches])


def claim_search_text(row: Mapping[str, Any]) -> str:
    payload = as_mapping(row.get("fact_payload"))
    parts = [
        text(row.get("claim_summary")),
        text(row.get("outcome")),
        text(row.get("office_or_domain")),
        text(payload.get("actor")),
        text(payload.get("outcome")),
    ]
    return " ".join(part for part in parts if part)


def claim_source_title(row: Mapping[str, Any]) -> str:
    payload = as_mapping(row.get("fact_payload"))
    return text(row.get("source_title") or payload.get("source_title"))


def claim_evidence_text(row: Mapping[str, Any]) -> str:
    return text(row.get("evidence_text"))


def requested_owner_context_only(row: Mapping[str, Any], requested_matches: Sequence[OwnerMatch]) -> bool:
    aliases = unique_strings([match.alias for match in requested_matches])
    if not aliases:
        return False
    searchable = claim_search_text(row)
    for alias in aliases:
        for relation in CONTEXT_ONLY_OWNER_RELATION_TERMS:
            if f"受{alias}{relation}" in searchable or f"为{alias}{relation}" in searchable or f"为{alias}所{relation}" in searchable:
                return True
    return False


def owner_review_class(
    *,
    owner_status: str,
    risk_kind: str,
    target_owner_mentioned: bool,
    target_owner_context_only: bool,
    other_owner_mentions: Sequence[Mapping[str, Any]],
) -> str:
    status = text(owner_status)
    risk = text(risk_kind)
    if status == "matched":
        return "target_owner_actor_matched"
    if status == "non_active":
        return "non_active_already_gated"
    if status == "rebind_candidate":
        return "rebind_candidate"
    if status == "person_material":
        return "person_material_without_owner_anchor"
    if target_owner_context_only:
        return "target_context_only_review"
    if risk == "ruler_action_without_requested_owner_mention":
        return "ruler_action_without_owner_anchor"
    if risk == "other_owner_or_reign_mentioned":
        other_owner_names = unique_strings([text(row.get("owner_name")) for row in other_owner_mentions])
        if len(other_owner_names) > 1:
            return "multi_owner_timeline_review"
        return "other_owner_mentioned_review"
    if risk == "minister_actor_requested_context_review" and target_owner_mentioned:
        return "minister_actor_target_context_ok"
    if risk == "minister_actor_requested_context_review":
        return "minister_actor_without_target_anchor_review"
    return risk or status or "unknown"


def classify_claim_owner(row: Mapping[str, Any], alias_book: OwnerAliasBook) -> dict[str, Any]:
    requested = text(row.get("emperor_name"))
    scoped_aliases = scoped_aliases_by_owner(requested, alias_book)
    payload = as_mapping(row.get("fact_payload"))
    actor = text(payload.get("actor"))
    action_type = text(row.get("action_type") or payload.get("action_type"))
    status = text(row.get("status"))
    searchable = claim_search_text(row)
    source_title = claim_source_title(row)
    actor_matches = alias_matches(
        actor,
        scoped_aliases,
        requested_owner_name=requested,
        alias_book=alias_book,
        source_title=source_title,
    )
    fact_object_matches = alias_matches(
        text(payload.get("object")),
        scoped_aliases,
        requested_owner_name=requested,
        alias_book=alias_book,
        source_title=source_title,
    )
    text_matches = alias_matches(
        searchable,
        scoped_aliases,
        requested_owner_name=requested,
        alias_book=alias_book,
        source_title=source_title,
    )
    requested_actor_matches = [match for match in actor_matches if match.owner_name == requested]
    requested_text_matches = [match for match in text_matches if match.owner_name == requested]
    requested_context_only = bool(requested_text_matches) and requested_owner_context_only(row, requested_text_matches)
    other_actor_matches = [match for match in actor_matches if match.owner_name != requested]
    other_fact_object_matches = [match for match in fact_object_matches if match.owner_name != requested]
    other_text_matches = [match for match in text_matches if match.owner_name != requested]
    other_fact_object_owner_names = unique_match_owners(other_fact_object_matches)
    other_text_owner_names = unique_match_owners(other_text_matches)
    suggested_owner = ""
    matched_alias = ""
    owner_status = "matched"
    risk_kind = "actor_matches_requested"
    if status != "active":
        owner_status = "non_active"
        risk_kind = "non_active_already_gated"
    elif requested_actor_matches:
        suggested_owner = requested
        matched_alias = requested_actor_matches[0].alias
        owner_status = "matched"
        risk_kind = "actor_matches_requested"
    elif other_actor_matches and action_type in RULER_ACTION_TYPES:
        suggested_owner = other_actor_matches[0].owner_name
        matched_alias = other_actor_matches[0].alias
        owner_status = "rebind_candidate"
        risk_kind = "ruler_action_actor_matches_other_owner"
    elif (not requested_text_matches or requested_context_only) and len(other_fact_object_owner_names) == 1 and other_fact_object_owner_names[0] in other_text_owner_names:
        suggested_owner = other_fact_object_owner_names[0]
        matched_alias = next((match.alias for match in other_fact_object_matches if match.owner_name == suggested_owner), "")
        owner_status = "rebind_candidate"
        risk_kind = "fact_object_owner_context_without_requested_owner"
    elif (not requested_text_matches or requested_context_only) and len(other_text_owner_names) == 1:
        suggested_owner = other_text_owner_names[0]
        matched_alias = next((match.alias for match in other_text_matches if match.owner_name == suggested_owner), "")
        owner_status = "rebind_candidate"
        risk_kind = "single_other_owner_context_with_requested_owner_context_only" if requested_context_only else "single_other_owner_context_without_requested_owner"
    elif other_text_matches:
        suggested_owner = other_text_matches[0].owner_name
        matched_alias = other_text_matches[0].alias
        owner_status = "needs_review"
        risk_kind = "other_owner_or_reign_mentioned"
    elif action_type in RULER_ACTION_TYPES and not requested_text_matches:
        owner_status = "needs_review"
        risk_kind = "ruler_action_without_requested_owner_mention"
    elif not requested_text_matches:
        owner_status = "person_material"
        risk_kind = "person_material_without_requested_owner_mention"
    else:
        owner_status = "needs_review"
        risk_kind = "minister_actor_requested_context_review"
    other_owner_mentions = [
        {"owner_name": match.owner_name, "alias": match.alias}
        for match in other_text_matches[:6]
    ]
    review_class = owner_review_class(
        owner_status=owner_status,
        risk_kind=risk_kind,
        target_owner_mentioned=bool(requested_text_matches),
        target_owner_context_only=requested_context_only,
        other_owner_mentions=other_owner_mentions,
    )
    return {
        "claim_key": text(row.get("claim_key")),
        "requested_emperor_name": requested,
        "object_name": text(row.get("object_name")),
        "status": status,
        "owner_status": owner_status,
        "owner_risk_kind": risk_kind,
        "suggested_owner_name": suggested_owner,
        "matched_owner_alias": matched_alias,
        "action_type": action_type,
        "actor": actor,
        "fact_object": text(payload.get("object")),
        "time_context": text(row.get("time_context") or payload.get("time_context")),
        "claim_summary": text(row.get("claim_summary")),
        "target_owner_mentioned": bool(requested_text_matches),
        "target_owner_context_only": requested_context_only,
        "owner_review_class": review_class,
        "other_owner_mentions": other_owner_mentions,
    }


def fetch_claim_rows(
    cur: Any,
    *,
    emperor_names: Sequence[str],
    statuses: Sequence[str],
) -> list[dict[str, Any]]:
    emperor_filter = [text(name) for name in emperor_names if text(name)]
    status_filter = [text(status) for status in statuses if text(status)]
    where: list[str] = []
    params: list[Any] = []
    if emperor_filter:
        where.append("f.emperor_name = any(%s)")
        params.append(emperor_filter)
    if status_filter:
        where.append("f.status::text = any(%s)")
        params.append(status_filter)
    cur.execute(
        f"""
        select
            f.claim_key,
            f.emperor_name,
            f.object_name,
            f.status::text as status,
            f.action_type,
            f.office_or_domain,
            f.time_context,
            f.outcome,
            f.claim_summary,
            f.fact_payload,
            coalesce(ev.evidence_text, '') as evidence_text
          from retrieval_v2.claim_atomic_facts f
          left join (
                select
                    e.claim_key,
                    string_agg(
                        distinct concat_ws(' ', e.quote_preview, s.source_title, s.slice_text_preview),
                        ' '
                    ) as evidence_text
                  from retrieval_v2.claim_evidence e
                  left join retrieval_v2.claim_source_slices s on s.slice_hash = e.slice_hash
                 group by e.claim_key
          ) ev on ev.claim_key = f.claim_key
          {'where ' + ' and '.join(where) if where else ''}
         order by f.emperor_name, f.object_name, f.claim_key
        """,
        params,
    )
    return [dict(row) for row in cur.fetchall()]


def summarize_findings(findings: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_emperor_status: Counter[tuple[str, str]] = Counter()
    by_emperor_kind: Counter[tuple[str, str]] = Counter()
    by_emperor_owner_status: Counter[tuple[str, str]] = Counter()
    by_emperor_review_class: Counter[tuple[str, str]] = Counter()
    by_suggested_owner: Counter[tuple[str, str]] = Counter()
    for row in findings:
        emperor = text(row.get("requested_emperor_name"))
        by_emperor_status[(emperor, text(row.get("status")))] += 1
        by_emperor_kind[(emperor, text(row.get("owner_risk_kind")))] += 1
        by_emperor_owner_status[(emperor, text(row.get("owner_status")))] += 1
        by_emperor_review_class[(emperor, text(row.get("owner_review_class")))] += 1
        suggested = text(row.get("suggested_owner_name"))
        if suggested:
            by_suggested_owner[(emperor, suggested)] += 1
    return {
        "total_claims": len(findings),
        "by_emperor_status": counter_pairs(by_emperor_status, ("requested_emperor_name", "status")),
        "by_emperor_owner_status": counter_pairs(by_emperor_owner_status, ("requested_emperor_name", "owner_status")),
        "by_emperor_risk_kind": counter_pairs(by_emperor_kind, ("requested_emperor_name", "owner_risk_kind")),
        "by_emperor_review_class": counter_pairs(by_emperor_review_class, ("requested_emperor_name", "owner_review_class")),
        "by_suggested_owner": counter_pairs(by_suggested_owner, ("requested_emperor_name", "suggested_owner_name")),
    }


def sample_finding(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "claim_key": text(row.get("claim_key")),
        "requested_emperor_name": text(row.get("requested_emperor_name")),
        "object_name": text(row.get("object_name")),
        "status": text(row.get("status")),
        "owner_status": text(row.get("owner_status")),
        "owner_risk_kind": text(row.get("owner_risk_kind")),
        "owner_review_class": text(row.get("owner_review_class")),
        "suggested_owner_name": text(row.get("suggested_owner_name")),
        "matched_owner_alias": text(row.get("matched_owner_alias")),
        "action_type": text(row.get("action_type")),
        "actor": text(row.get("actor")),
        "fact_object": text(row.get("fact_object")),
        "time_context": text(row.get("time_context")),
        "claim_summary": text(row.get("claim_summary")),
    }


def append_sample(target: list[dict[str, Any]], row: Mapping[str, Any], *, sample_limit: int) -> None:
    if len(target) < sample_limit:
        target.append(sample_finding(row))


def owner_pool_status(owner_name: str, registered_owners: set[str]) -> str:
    owner = text(owner_name)
    if not owner:
        return "blank_owner"
    if owner in registered_owners:
        return "registered_target_owner"
    return "external_or_unregistered_owner"


def owner_binding_inventory(
    findings: Sequence[Mapping[str, Any]],
    alias_book: OwnerAliasBook,
    *,
    sample_limit: int = DEFAULT_INVENTORY_SAMPLE_LIMIT,
) -> dict[str, Any]:
    registered_owners = registered_owner_names(alias_book)
    pool_counts: Counter[str] = Counter()
    external_owner_counts: Counter[str] = Counter()
    suggested_external_counts: Counter[str] = Counter()
    anomaly_counts: Counter[str] = Counter()
    review_class_counts: Counter[str] = Counter()
    samples: dict[str, list[dict[str, Any]]] = {
        "external_or_unregistered_owner_claims": [],
        "rebind_candidates": [],
        "ambiguous_owner_reviews": [],
        "multi_owner_timeline_reviews": [],
        "ruler_action_without_owner_anchor": [],
        "minister_actor_target_context_ok": [],
        "person_material_without_requested_owner": [],
        "target_context_only_claims": [],
    }
    for row in findings:
        requested = text(row.get("requested_emperor_name"))
        status = owner_pool_status(requested, registered_owners)
        pool_counts[status] += 1
        if status == "external_or_unregistered_owner":
            external_owner_counts[requested] += 1
            anomaly_counts["external_or_unregistered_owner"] += 1
            append_sample(samples["external_or_unregistered_owner_claims"], row, sample_limit=sample_limit)
        owner_status = text(row.get("owner_status"))
        risk_kind = text(row.get("owner_risk_kind"))
        review_class = text(row.get("owner_review_class"))
        if review_class:
            review_class_counts[review_class] += 1
        suggested = text(row.get("suggested_owner_name"))
        if owner_status == "rebind_candidate":
            anomaly_counts["rebind_candidate"] += 1
            append_sample(samples["rebind_candidates"], row, sample_limit=sample_limit)
        if owner_status == "needs_review":
            anomaly_counts["needs_review"] += 1
        if risk_kind == "other_owner_or_reign_mentioned":
            anomaly_counts["other_owner_or_reign_mentioned"] += 1
            append_sample(samples["ambiguous_owner_reviews"], row, sample_limit=sample_limit)
        if review_class == "multi_owner_timeline_review":
            append_sample(samples["multi_owner_timeline_reviews"], row, sample_limit=sample_limit)
        if review_class == "ruler_action_without_owner_anchor":
            append_sample(samples["ruler_action_without_owner_anchor"], row, sample_limit=sample_limit)
        if review_class == "minister_actor_target_context_ok":
            append_sample(samples["minister_actor_target_context_ok"], row, sample_limit=sample_limit)
        if owner_status == "person_material":
            anomaly_counts["person_material_without_requested_owner"] += 1
            append_sample(samples["person_material_without_requested_owner"], row, sample_limit=sample_limit)
        if bool(row.get("target_owner_context_only")):
            anomaly_counts["target_owner_context_only"] += 1
            append_sample(samples["target_context_only_claims"], row, sample_limit=sample_limit)
        if suggested and owner_pool_status(suggested, registered_owners) == "external_or_unregistered_owner":
            suggested_external_counts[suggested] += 1
    return {
        "registered_owner_count": len(registered_owners),
        "registered_owner_source": alias_book.source,
        "claim_count_by_owner_pool_status": dict(sorted(pool_counts.items())),
        "external_or_unregistered_owners": [
            {"owner_name": owner, "claim_count": count}
            for owner, count in sorted(external_owner_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "suggested_external_or_unregistered_owners": [
            {"owner_name": owner, "claim_count": count}
            for owner, count in sorted(suggested_external_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "anomaly_counts": dict(sorted(anomaly_counts.items())),
        "review_class_counts": dict(sorted(review_class_counts.items())),
        "samples": samples,
    }


def owner_rebind_payload(row: Mapping[str, Any]) -> dict[str, Any]:
    return as_mapping(as_mapping(row.get("fact_payload")).get("owner_rebind_payload"))


def owner_rebind_payload_aliases(payload: Mapping[str, Any]) -> list[str]:
    aliases = payload.get("matched_aliases")
    if isinstance(aliases, list):
        return unique_strings([text(alias) for alias in aliases])
    return unique_strings([text(payload.get("matched_alias"))])


def owner_rebind_payload_rules(payload: Mapping[str, Any]) -> list[str]:
    rules = payload.get("resolution_rules")
    if isinstance(rules, list):
        return unique_strings([text(rule) for rule in rules])
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), list) else []
    return unique_strings([text(as_mapping(row).get("resolution_rule")) for row in evidence])


def alias_mentions_for_payload(
    row: Mapping[str, Any],
    alias_book: OwnerAliasBook,
    *,
    alias: str,
    requested_owner_name: str,
    include_suppressed: bool,
) -> list[dict[str, Any]]:
    return [
        dict(mention)
        for mention in alias_pretag.alias_mentions_in_text(
            claim_search_text(row),
            requested_owner_name=requested_owner_name,
            source_title=claim_source_title(row),
            resolver=alias_book.resolver,
            include_suppressed=include_suppressed,
        )
        if text(mention.get("alias")) == text(alias)
    ]


def owner_rebind_payload_risk_flags(row: Mapping[str, Any], alias_book: OwnerAliasBook) -> list[str]:
    payload = owner_rebind_payload(row)
    if not payload:
        return []
    aliases = owner_rebind_payload_aliases(payload)
    rules = owner_rebind_payload_rules(payload)
    from_owner = text(payload.get("from_emperor_name"))
    to_owner = text(payload.get("to_emperor_name"))
    requested_owner = from_owner or text(row.get("emperor_name"))
    claim_text = claim_search_text(row)
    evidence_text = claim_evidence_text(row)
    time_context = text(row.get("time_context") or as_mapping(row.get("fact_payload")).get("time_context"))
    flags: list[str] = []
    if to_owner and text(row.get("emperor_name")) != to_owner:
        flags.append("payload_to_owner_mismatch")
    if set(rules) & OWNER_REBIND_BARE_TITLE_RULES:
        flags.append("bare_title_rebind_payload")
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), list) else []
    if evidence and not any("owner_anchor_eligible" in as_mapping(item) for item in evidence):
        flags.append("payload_evidence_lacks_owner_anchor_fields")
    for alias in aliases:
        if alias in OWNER_REBIND_HIGH_RISK_ALIASES:
            flags.append("high_risk_matched_alias")
        if 0 < len(alias) <= 2:
            flags.append("short_matched_alias")
        if alias and alias in claim_text:
            suppressed_mentions = [
                mention
                for mention in alias_mentions_for_payload(
                    row,
                    alias_book,
                    alias=alias,
                    requested_owner_name=requested_owner,
                    include_suppressed=True,
                )
                if text(mention.get("resolution_status")) == "suppressed"
            ]
            resolved_mentions = [
                mention
                for mention in alias_mentions_for_payload(
                    row,
                    alias_book,
                    alias=alias,
                    requested_owner_name=requested_owner,
                    include_suppressed=False,
                )
                if text(mention.get("resolution_status")) == "resolved"
                and text(mention.get("resolved_owner_name")) == to_owner
                and mention.get("owner_anchor_eligible") is not False
            ]
            if suppressed_mentions:
                flags.append("current_mechanism_suppresses_matched_alias")
                reasons = unique_strings([text(mention.get("suppression_reason")) for mention in suppressed_mentions])
                flags.extend(f"current_suppression.{reason}" for reason in reasons)
            if not resolved_mentions:
                flags.append("current_mechanism_does_not_reproduce_rebind_anchor")
        elif alias and alias in time_context:
            flags.append("time_context_only_matched_alias")
            if from_owner and text(as_mapping(row.get("fact_payload")).get("actor")) == from_owner:
                flags.append("time_context_only_actor_matches_from_owner")
        else:
            flags.append("matched_alias_not_in_current_claim_text")
            if alias and alias in evidence_text:
                flags.append("matched_alias_in_evidence_text_only")
            if set(rules) & OWNER_REBIND_BARE_TITLE_RULES:
                flags.append("bare_title_rule_without_current_alias")
            if "source_title_dynasty_bare_title" in rules:
                flags.append("source_title_rule_without_current_alias")
                if not alias or alias not in evidence_text:
                    flags.append("source_title_rule_without_claim_or_evidence_alias")
    return unique_strings(flags)


def sample_owner_rebind_payload(row: Mapping[str, Any], flags: Sequence[str]) -> dict[str, Any]:
    payload = owner_rebind_payload(row)
    return {
        "claim_key": text(row.get("claim_key")),
        "emperor_name": text(row.get("emperor_name")),
        "object_name": text(row.get("object_name")),
        "status": text(row.get("status")),
        "from_emperor_name": text(payload.get("from_emperor_name")),
        "to_emperor_name": text(payload.get("to_emperor_name")),
        "reason": text(payload.get("reason")),
        "matched_aliases": owner_rebind_payload_aliases(payload),
        "resolution_rules": owner_rebind_payload_rules(payload),
        "risk_flags": list(flags),
        "action_type": text(row.get("action_type") or as_mapping(row.get("fact_payload")).get("action_type")),
        "actor": text(as_mapping(row.get("fact_payload")).get("actor")),
        "time_context": text(row.get("time_context") or as_mapping(row.get("fact_payload")).get("time_context")),
        "claim_summary": text(row.get("claim_summary")),
    }


def owner_rebind_payload_inventory(
    rows: Sequence[Mapping[str, Any]],
    alias_book: OwnerAliasBook,
    *,
    sample_limit: int = DEFAULT_INVENTORY_SAMPLE_LIMIT,
) -> dict[str, Any]:
    by_reason: Counter[str] = Counter()
    by_alias: Counter[str] = Counter()
    by_rule: Counter[str] = Counter()
    risk_counts: Counter[str] = Counter()
    samples: dict[str, list[dict[str, Any]]] = defaultdict(list)
    inventory_rows: list[dict[str, Any]] = []
    payload_claim_count = 0
    for row in rows:
        payload = owner_rebind_payload(row)
        if not payload:
            continue
        payload_claim_count += 1
        by_reason[text(payload.get("reason")) or "<blank>"] += 1
        aliases = owner_rebind_payload_aliases(payload)
        rules = owner_rebind_payload_rules(payload)
        for alias in aliases or ["<blank>"]:
            by_alias[alias] += 1
        for rule in rules or ["<blank>"]:
            by_rule[rule] += 1
        flags = owner_rebind_payload_risk_flags(row, alias_book)
        if not flags:
            flags = ["no_risk_flags"]
        sample = sample_owner_rebind_payload(row, flags)
        inventory_rows.append(sample)
        for flag in flags:
            risk_counts[flag] += 1
            if len(samples[flag]) < sample_limit:
                samples[flag].append(sample)
    return {
        "payload_claim_count": payload_claim_count,
        "by_reason": dict(sorted(by_reason.items())),
        "by_matched_alias": dict(sorted(by_alias.items())),
        "by_resolution_rule": dict(sorted(by_rule.items())),
        "risk_counts": dict(sorted(risk_counts.items())),
        "rows": inventory_rows,
        "samples": dict(sorted(samples.items())),
    }


def counter_pairs(counter: Counter[tuple[str, str]], keys: tuple[str, str]) -> list[dict[str, Any]]:
    first_key, second_key = keys
    return [
        {first_key: first, second_key: second, "count": count}
        for (first, second), count in sorted(counter.items(), key=lambda item: (item[0][0], item[0][1]))
    ]


def rebind_plan(findings: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in findings
        if text(row.get("owner_status")) in {"rebind_candidate", "person_material", "needs_review"}
    ]


def executable_rebind_plan(findings: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in findings
        if text(row.get("owner_status")) == "rebind_candidate"
        and text(row.get("suggested_owner_name"))
        and text(row.get("suggested_owner_name")) != text(row.get("requested_emperor_name"))
    ]


def executable_review_status_plan(findings: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in findings
        if text(row.get("owner_status")) == "needs_review"
        and text(row.get("owner_risk_kind")) == "other_owner_or_reign_mentioned"
        and not bool(row.get("target_owner_mentioned"))
    ]


def apply_rebind_plan(cur: Any, rows: Sequence[Mapping[str, Any]]) -> int:
    updated = 0
    for row in rows:
        payload = {
            "from_emperor_name": text(row.get("requested_emperor_name")),
            "to_emperor_name": text(row.get("suggested_owner_name")),
            "reason": text(row.get("owner_risk_kind")),
            "matched_alias": text(row.get("matched_owner_alias")),
            "actor": text(row.get("actor")),
            "source": "retrieval_v2_claim_owner_audit",
        }
        cur.execute(
            """
            update retrieval_v2.claim_cache
               set emperor_name = %s,
                   fact_payload = fact_payload || %s::jsonb,
                   updated_at = now()
             where claim_key = %s
               and emperor_name = %s
               and status::text = 'active'
            """,
            (
                payload["to_emperor_name"],
                json.dumps({"owner_rebind_payload": payload}, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                text(row.get("claim_key")),
                payload["from_emperor_name"],
            ),
        )
        updated += int(getattr(cur, "rowcount", 0) or 0)
    return updated


def apply_review_status_plan(cur: Any, rows: Sequence[Mapping[str, Any]]) -> int:
    updated = 0
    for row in rows:
        payload = {
            "from_emperor_name": text(row.get("requested_emperor_name")),
            "reason": text(row.get("owner_risk_kind")),
            "matched_alias": text(row.get("matched_owner_alias")),
            "suggested_owner_name": text(row.get("suggested_owner_name")),
            "actor": text(row.get("actor")),
            "source": "retrieval_v2_claim_owner_audit",
        }
        cur.execute(
            """
            update retrieval_v2.claim_cache
               set status = 'needs_review'::retrieval_v2.rv2_claim_cache_status,
                   fact_payload = fact_payload || %s::jsonb,
                   updated_at = now()
             where claim_key = %s
               and emperor_name = %s
               and status::text = 'active'
            """,
            (
                json.dumps({"owner_review_payload": payload}, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                text(row.get("claim_key")),
                payload["from_emperor_name"],
            ),
        )
        updated += int(getattr(cur, "rowcount", 0) or 0)
    return updated


def audit_claim_owners(
    *,
    env_file: Path | None,
    dsn_env: str,
    schema_name: str,
    emperor_names: Sequence[str],
    statuses: Sequence[str],
    owner_aliases_json: Path | None = None,
    execute_rebind: bool = False,
    execute_review_status: bool = False,
    inventory_sample_limit: int = DEFAULT_INVENTORY_SAMPLE_LIMIT,
) -> dict[str, Any]:
    if env_file is not None:
        load_env_file(env_file)
    psycopg, dict_row = import_psycopg()
    dsn = resolve_dsn(dsn_env)
    executed_count = 0
    review_status_count = 0
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        with conn.cursor() as raw_cur:
            cur = schema_cursor(raw_cur, schema_name=schema_name)
            aliases = load_owner_aliases(owner_aliases_json) if owner_aliases_json is not None else fetch_owner_alias_book(cur)
            rows = fetch_claim_rows(cur, emperor_names=emperor_names, statuses=statuses)
            findings = [classify_claim_owner(row, aliases) for row in rows]
            inventory = owner_binding_inventory(findings, aliases, sample_limit=max(0, int(inventory_sample_limit)))
            rebind_payload_inventory = owner_rebind_payload_inventory(
                rows,
                aliases,
                sample_limit=max(0, int(inventory_sample_limit)),
            )
            executable_plan = executable_rebind_plan(findings)
            review_status_plan = executable_review_status_plan(findings)
            if execute_rebind:
                executed_count = apply_rebind_plan(cur, executable_plan)
            if execute_review_status:
                review_status_count = apply_review_status_plan(cur, review_status_plan)
            if execute_rebind or execute_review_status:
                conn.commit()
            else:
                conn.rollback()
    return {
        "ok": True,
        "generated_by": "scripts/dev/retrieval_v2_claim_owner_audit.py",
        "mode": "execute_owner_repair" if execute_rebind or execute_review_status else "dry_run_owner_audit",
        "write_db": execute_rebind or execute_review_status,
        "schema_name": schema_name,
        "filters": {
            "emperor_names": [text(name) for name in emperor_names if text(name)],
            "statuses": [text(status) for status in statuses if text(status)],
        },
        "owner_alias_policy": {
            "source": aliases.source,
            "canonical_owner_names": sorted(aliases.aliases_by_owner),
            "scoped_requested_owner_names": sorted(aliases.scoped_aliases_by_requested),
            "note": "suggested_owner_name is always a canonical personal name; matched_owner_alias records the title/name that triggered the match.",
        },
        "summary": summarize_findings(findings),
        "owner_binding_inventory": inventory,
        "owner_rebind_payload_inventory": rebind_payload_inventory,
        "findings": findings,
        "rebind_plan": rebind_plan(findings),
        "executable_rebind_plan": executable_plan,
        "executable_review_status_plan": review_status_plan,
        "executed_counts": (
            {"claim_cache_rebound": executed_count, "claim_cache_marked_needs_review": review_status_count}
            if execute_rebind or execute_review_status
            else {}
        ),
    }


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "claim_key",
        "requested_emperor_name",
        "object_name",
        "status",
        "owner_status",
        "owner_risk_kind",
        "owner_review_class",
        "suggested_owner_name",
        "matched_owner_alias",
        "action_type",
        "actor",
        "fact_object",
        "time_context",
        "claim_summary",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_owner_rebind_payload_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "claim_key",
        "emperor_name",
        "object_name",
        "status",
        "from_emperor_name",
        "to_emperor_name",
        "reason",
        "matched_aliases",
        "resolution_rules",
        "risk_flags",
        "action_type",
        "actor",
        "time_context",
        "claim_summary",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            output = dict(row)
            for key in ("matched_aliases", "resolution_rules", "risk_flags"):
                output[key] = ";".join(text(item) for item in output.get(key) or [])
            writer.writerow(output)


def markdown_report(payload: Mapping[str, Any]) -> str:
    summary = as_mapping(payload.get("summary"))
    inventory = as_mapping(payload.get("owner_binding_inventory"))
    rebind_inventory = as_mapping(payload.get("owner_rebind_payload_inventory"))
    lines = [
        "# Claim Owner Audit",
        "",
        f"- ok: `{str(payload.get('ok')).lower()}`",
        f"- schema_name: `{payload.get('schema_name')}`",
        f"- write_db: `{str(payload.get('write_db')).lower()}`",
        f"- total_claims: `{summary.get('total_claims', 0)}`",
        f"- registered_owner_count: `{inventory.get('registered_owner_count', 0)}`",
        f"- owner_rebind_payload_claims: `{rebind_inventory.get('payload_claim_count', 0)}`",
        "",
        "## Owner Status",
        "",
        "| requested_emperor_name | owner_status | count |",
        "| --- | --- | ---: |",
    ]
    for row in summary.get("by_emperor_owner_status") or []:
        lines.append(f"| {row.get('requested_emperor_name')} | {row.get('owner_status')} | {row.get('count')} |")
    lines.extend(["", "## Owner Review Class", "", "| requested_emperor_name | owner_review_class | count |", "| --- | --- | ---: |"])
    for row in summary.get("by_emperor_review_class") or []:
        lines.append(f"| {row.get('requested_emperor_name')} | {row.get('owner_review_class')} | {row.get('count')} |")
    lines.extend(["", "## Review Class Totals", "", "| owner_review_class | count |", "| --- | ---: |"])
    for review_class, count in (inventory.get("review_class_counts") or {}).items():
        lines.append(f"| {review_class} | {count} |")
    lines.extend(["", "## Owner Pool", "", "| owner_pool_status | count |", "| --- | ---: |"])
    for status, count in (inventory.get("claim_count_by_owner_pool_status") or {}).items():
        lines.append(f"| {status} | {count} |")
    lines.extend(["", "## External Or Unregistered Owners", "", "| owner_name | claim_count |", "| --- | ---: |"])
    for row in inventory.get("external_or_unregistered_owners") or []:
        lines.append(f"| {row.get('owner_name')} | {row.get('claim_count')} |")
    lines.extend(["", "## Risk Kind", "", "| requested_emperor_name | owner_risk_kind | count |", "| --- | --- | ---: |"])
    for row in summary.get("by_emperor_risk_kind") or []:
        lines.append(f"| {row.get('requested_emperor_name')} | {row.get('owner_risk_kind')} | {row.get('count')} |")
    lines.extend(["", "## Suggested Rebind Owners", "", "| requested_emperor_name | suggested_owner_name | count |", "| --- | --- | ---: |"])
    for row in summary.get("by_suggested_owner") or []:
        lines.append(f"| {row.get('requested_emperor_name')} | {row.get('suggested_owner_name')} | {row.get('count')} |")
    lines.extend(["", "## Existing Owner Rebind Payload Risk", "", "| risk_flag | count |", "| --- | ---: |"])
    for flag, count in (rebind_inventory.get("risk_counts") or {}).items():
        lines.append(f"| {flag} | {count} |")
    lines.extend(["", "## Existing Owner Rebind Payload Aliases", "", "| matched_alias | count |", "| --- | ---: |"])
    for alias, count in (rebind_inventory.get("by_matched_alias") or {}).items():
        lines.append(f"| {alias} | {count} |")
    lines.extend(["", "## Existing Owner Rebind Payload Reasons", "", "| reason | count |", "| --- | ---: |"])
    for reason, count in (rebind_inventory.get("by_reason") or {}).items():
        lines.append(f"| {reason} | {count} |")
    lines.extend(
        [
            "",
            "## Rebind Plan Sample",
            "",
            "| claim_key | requested | owner_status | suggested_owner_name | matched_alias | action_type | actor | summary |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in (payload.get("rebind_plan") or [])[:80]:
        lines.append(
            "| {claim_key} | {requested} | {owner_status} | {suggested} | {alias} | {action_type} | {actor} | {summary} |".format(
                claim_key=row.get("claim_key", ""),
                requested=row.get("requested_emperor_name", ""),
                owner_status=row.get("owner_status", ""),
                suggested=row.get("suggested_owner_name", ""),
                alias=row.get("matched_owner_alias", ""),
                action_type=row.get("action_type", ""),
                actor=row.get("actor", ""),
                summary=text(row.get("claim_summary")).replace("|", " / "),
            )
        )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit claim owner binding and produce a dry-run rebind/material plan.")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--pg-schema", default="retrieval_v3")
    parser.add_argument("--emperor-name", action="append", default=[])
    parser.add_argument("--status", action="append", default=["active"])
    parser.add_argument("--owner-aliases-json", type=Path)
    parser.add_argument("--execute-rebind", action="store_true", help="Apply deterministic rebind_candidate rows to claim_cache.")
    parser.add_argument("--execute-review-status", action="store_true", help="Mark ambiguous non-target owner context rows as needs_review.")
    parser.add_argument("--inventory-sample-limit", type=int, default=DEFAULT_INVENTORY_SAMPLE_LIMIT)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-md", type=Path)
    parser.add_argument("--output-csv", type=Path)
    parser.add_argument("--output-rebind-payload-csv", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = audit_claim_owners(
        env_file=args.env_file,
        dsn_env=args.dsn_env,
        schema_name=args.pg_schema,
        emperor_names=args.emperor_name or [],
        statuses=args.status or [],
        owner_aliases_json=args.owner_aliases_json,
        execute_rebind=bool(args.execute_rebind),
        execute_review_status=bool(args.execute_review_status),
        inventory_sample_limit=max(0, int(args.inventory_sample_limit)),
    )
    write_json(args.output_json, payload)
    if args.output_md is not None:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(markdown_report(payload), encoding="utf-8", newline="\n")
    if args.output_csv is not None:
        write_csv(args.output_csv, payload.get("rebind_plan") or [])
    if args.output_rebind_payload_csv is not None:
        rebind_inventory = as_mapping(payload.get("owner_rebind_payload_inventory"))
        write_owner_rebind_payload_csv(args.output_rebind_payload_csv, rebind_inventory.get("rows") or [])
    print(json.dumps({"ok": payload["ok"], "summary": payload["summary"]}, ensure_ascii=False, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
