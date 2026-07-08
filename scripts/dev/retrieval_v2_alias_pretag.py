from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]

from scripts.dev.retrieval_v2_target_alias_backfill import (  # noqa: E402
    DEFAULT_ALIAS_FILE,
    DEFAULT_EMPEROR_LIST,
    alias_payload,
    alias_rows_for_emperors,
    load_alias_seed,
    load_emperor_names,
)
from scripts.dev.retrieval_v2_intake_manifest import text  # noqa: E402


RULER_ACTION_TYPES = {"任命", "授权", "处置", "收权", "制度高压", "纳谏", "拒谏", "战役", "其他"}
BARE_TITLE_TYPES = {"temple_name", "posthumous_name"}
SOURCE_TITLE_DYNASTY_MARKERS = (
    ("旧唐书", "唐"),
    ("舊唐書", "唐"),
    ("新唐书", "唐"),
    ("新唐書", "唐"),
    ("唐书", "唐"),
    ("唐書", "唐"),
    ("宋史", "宋"),
    ("明史", "明"),
    ("清史稿", "清"),
    ("隋书", "隋"),
    ("隋書", "隋"),
    ("汉书", "汉"),
    ("漢書", "汉"),
    ("后汉书", "汉"),
    ("後漢書", "汉"),
)


@dataclass(frozen=True)
class AliasEntry:
    owner_name: str
    alias: str
    alias_type: str
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class AliasResolver:
    entries: tuple[AliasEntry, ...]
    source: str


def unique_texts(values: Sequence[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        item = text(value)
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def alias_resolver_from_rows(rows: Sequence[Mapping[str, Any]], *, source: str) -> AliasResolver:
    entries: list[AliasEntry] = []
    seen: set[tuple[str, str, str, tuple[str, ...]]] = set()
    for row in rows:
        owner_name = text(row.get("emperor_name"))
        alias = text(row.get("alias"))
        alias_type = text(row.get("alias_type")) or "alias"
        payload = row.get("alias_payload") if isinstance(row.get("alias_payload"), Mapping) else {}
        scopes = payload.get("scopes") if isinstance(payload, Mapping) else []
        if isinstance(scopes, str):
            scopes = [scopes]
        clean_scopes = tuple(unique_texts(scopes if isinstance(scopes, list) else []))
        if not owner_name or not alias:
            continue
        key = (owner_name, alias, alias_type, clean_scopes)
        if key in seen:
            continue
        seen.add(key)
        entries.append(AliasEntry(owner_name=owner_name, alias=alias, alias_type=alias_type, scopes=clean_scopes))
    entries.sort(key=lambda item: (-len(item.alias), item.alias, item.owner_name))
    return AliasResolver(entries=tuple(entries), source=source)


def load_alias_resolver(
    *,
    emperor_list: Path = DEFAULT_EMPEROR_LIST,
    alias_file: Path = DEFAULT_ALIAS_FILE,
) -> AliasResolver:
    emperor_names = load_emperor_names(emperor_list)
    alias_seed = load_alias_seed(alias_file)
    rows = [
        {**row, "alias_payload": alias_payload(row)}
        for row in alias_rows_for_emperors(emperor_names, alias_seed)
    ]
    return alias_resolver_from_rows(rows, source=str(alias_file))


def candidate_requested_owner(candidates: Mapping[str, Any]) -> str:
    task_identity = candidates.get("task_identity") if isinstance(candidates.get("task_identity"), Mapping) else {}
    target_profile = candidates.get("target_profile") if isinstance(candidates.get("target_profile"), Mapping) else {}
    return text(task_identity.get("emperor_name")) or text(target_profile.get("primary_name"))


def active_entries_for_alias(
    resolver: AliasResolver,
    alias: str,
    *,
    requested_owner_name: str,
    source_dynasty_prefixes: Sequence[str] = (),
) -> list[AliasEntry]:
    requested = text(requested_owner_name)
    dynasty_matched_owners = owners_for_dynasty_bare_alias(
        resolver,
        alias,
        source_dynasty_prefixes=source_dynasty_prefixes,
    )
    rows = [
        entry
        for entry in resolver.entries
        if entry.alias == alias
        and (
            not entry.scopes
            or requested in entry.scopes
            or entry.owner_name in dynasty_matched_owners
        )
    ]
    return sorted(rows, key=lambda item: (item.owner_name, item.alias_type))


def source_dynasty_prefixes_from_title(source_title: str) -> list[str]:
    title = text(source_title)
    return unique_texts([prefix for marker, prefix in SOURCE_TITLE_DYNASTY_MARKERS if marker in title])


def owners_for_dynasty_bare_alias(
    resolver: AliasResolver,
    alias: str,
    *,
    source_dynasty_prefixes: Sequence[str],
) -> set[str]:
    alias_text = text(alias)
    if len(alias_text) > 2 or not source_dynasty_prefixes:
        return set()
    full_aliases = {f"{prefix}{alias_text}" for prefix in source_dynasty_prefixes if prefix}
    return {entry.owner_name for entry in resolver.entries if entry.alias in full_aliases}


def resolution_rule(
    entry: AliasEntry,
    *,
    requested_owner_name: str,
    source_dynasty_prefixes: Sequence[str] = (),
    source_dynasty_owner_match: bool = False,
) -> str:
    if entry.alias_type == "name":
        return "canonical_name"
    if source_dynasty_prefixes and source_dynasty_owner_match:
        return "source_title_dynasty_bare_title"
    if entry.scopes and entry.alias_type in BARE_TITLE_TYPES and len(entry.alias) <= 2:
        return "same_dynasty_bare_title_scope"
    if entry.scopes:
        return "scoped_alias_by_requested_owner"
    return "unique_global_alias"


def iter_alias_positions(text_value: str, aliases: Sequence[str]) -> list[tuple[str, int, int]]:
    positions: list[tuple[str, int, int]] = []
    for alias in sorted(unique_texts(aliases), key=lambda item: (-len(item), item)):
        start = 0
        while alias:
            index = text_value.find(alias, start)
            if index < 0:
                break
            positions.append((alias, index, index + len(alias)))
            start = index + max(1, len(alias))
    positions.sort(key=lambda row: (row[1], -(row[2] - row[1]), row[0]))
    return positions


def overlap(span: tuple[int, int], used: Sequence[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < used_end and end > used_start for used_start, used_end in used)


def alias_mentions_in_text(
    text_value: str,
    *,
    requested_owner_name: str,
    source_title: str = "",
    resolver: AliasResolver | None = None,
) -> list[dict[str, Any]]:
    resolver = resolver or load_alias_resolver()
    requested = text(requested_owner_name)
    source_dynasty_prefixes = source_dynasty_prefixes_from_title(source_title)
    aliases = [entry.alias for entry in resolver.entries if entry.alias]
    mentions: list[dict[str, Any]] = []
    used_spans: list[tuple[int, int]] = []
    for alias, start, end in iter_alias_positions(text_value, aliases):
        if overlap((start, end), used_spans):
            continue
        active = active_entries_for_alias(
            resolver,
            alias,
            requested_owner_name=requested,
            source_dynasty_prefixes=source_dynasty_prefixes,
        )
        if not active:
            continue
        dynasty_owners = owners_for_dynasty_bare_alias(
            resolver,
            alias,
            source_dynasty_prefixes=source_dynasty_prefixes,
        )
        owners = sorted({entry.owner_name for entry in active})
        if len(owners) == 1:
            entry = active[0]
            mentions.append(
                {
                    "alias": alias,
                    "matched_text": text_value[start:end],
                    "resolved_owner_name": entry.owner_name,
                    "resolution_status": "resolved",
                    "resolution_rule": resolution_rule(
                        entry,
                        requested_owner_name=requested,
                        source_dynasty_prefixes=source_dynasty_prefixes,
                        source_dynasty_owner_match=entry.owner_name in dynasty_owners,
                    ),
                    "confidence": "deterministic",
                    "alias_type": entry.alias_type,
                    "start": start,
                    "end": end,
                    "owner_relation_to_requested": "target_owner" if entry.owner_name == requested else "other_owner",
                    "scopes": list(entry.scopes),
                    "source_dynasty_prefixes": source_dynasty_prefixes,
                }
            )
        else:
            mentions.append(
                {
                    "alias": alias,
                    "matched_text": text_value[start:end],
                    "resolved_owner_name": "",
                    "candidate_owner_names": owners,
                    "resolution_status": "ambiguous",
                    "resolution_rule": "ambiguous_alias",
                    "confidence": "review",
                    "start": start,
                    "end": end,
                    "owner_relation_to_requested": "ambiguous",
                    "scopes": sorted({scope for entry in active for scope in entry.scopes}),
                    "source_dynasty_prefixes": source_dynasty_prefixes,
                }
            )
        used_spans.append((start, end))
    return mentions


def slice_alias_mentions(
    row: Mapping[str, Any],
    *,
    requested_owner_name: str,
    resolver: AliasResolver | None = None,
    only_prompt_relevant: bool = False,
) -> list[dict[str, Any]]:
    mentions = alias_mentions_in_text(
        str(row.get("text") or row.get("raw_text") or ""),
        requested_owner_name=requested_owner_name,
        source_title=text(row.get("source_title") or row.get("title")),
        resolver=resolver,
    )
    if not only_prompt_relevant:
        return mentions
    return [
        mention
        for mention in mentions
        if mention.get("resolution_status") != "resolved"
        or text(mention.get("resolved_owner_name")) != text(requested_owner_name)
    ]


def alias_owner_index_for_slices(
    slices: Mapping[str, Mapping[str, Any]],
    *,
    requested_owner_name: str,
    resolver: AliasResolver | None = None,
) -> dict[str, list[dict[str, Any]]]:
    resolver = resolver or load_alias_resolver()
    return {
        source_ref: slice_alias_mentions(row, requested_owner_name=requested_owner_name, resolver=resolver)
        for source_ref, row in sorted(slices.items())
    }


def claim_actor_text(claim: Mapping[str, Any]) -> str:
    payload = claim.get("fact_payload") if isinstance(claim.get("fact_payload"), Mapping) else {}
    return text(payload.get("actor"))


def claim_action_type(claim: Mapping[str, Any]) -> str:
    payload = claim.get("fact_payload") if isinstance(claim.get("fact_payload"), Mapping) else {}
    return text(claim.get("action_type")) or text(payload.get("action_type"))


def claim_owner_rebind_from_alias_mentions(
    claim: Mapping[str, Any],
    *,
    source_refs: Sequence[str],
    alias_mentions_by_ref: Mapping[str, Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    current_owner = text(claim.get("emperor_name"))
    actor = claim_actor_text(claim)
    if not actor or claim_action_type(claim) not in RULER_ACTION_TYPES:
        return {}
    candidates: list[dict[str, Any]] = []
    for source_ref in source_refs:
        for mention in alias_mentions_by_ref.get(source_ref) or []:
            if text(mention.get("resolution_status")) != "resolved":
                continue
            owner = text(mention.get("resolved_owner_name"))
            alias = text(mention.get("alias"))
            if owner and owner != current_owner and alias and alias in actor:
                candidates.append(
                    {
                        "source_slice_ref": source_ref,
                        "alias": alias,
                        "from_emperor_name": current_owner,
                        "to_emperor_name": owner,
                        "resolution_rule": text(mention.get("resolution_rule")),
                        "confidence": text(mention.get("confidence")) or "deterministic",
                    }
                )
    owners = unique_texts([row["to_emperor_name"] for row in candidates])
    if len(owners) != 1:
        return {}
    return {
        "from_emperor_name": current_owner,
        "to_emperor_name": owners[0],
        "reason": "claim_actor_matches_resolved_owner_alias",
        "matched_aliases": unique_texts([row["alias"] for row in candidates]),
        "source_slice_refs": unique_texts([row["source_slice_ref"] for row in candidates]),
        "resolution_rules": unique_texts([row["resolution_rule"] for row in candidates]),
        "evidence": candidates,
    }


def apply_claim_owner_rebind(claim: Mapping[str, Any], rebind: Mapping[str, Any]) -> dict[str, Any]:
    to_owner = text(rebind.get("to_emperor_name"))
    if not to_owner:
        return dict(claim)
    result = dict(claim)
    result["emperor_name"] = to_owner
    payload = result.get("fact_payload") if isinstance(result.get("fact_payload"), Mapping) else {}
    result["fact_payload"] = dict(payload)
    result["owner_rebind_payload"] = dict(rebind)
    return result
