#!/usr/bin/env python3
"""Reader military archive facade with public-registry evidence reconciliation.

The long-standing archive builder lives in ``_build_military_archive_core.py``.
This facade keeps that implementation stable and performs one narrow second pass:
First Item C anchors that the core could not bind may consume positive *or negative*
commander records, but only through existing public-registry evidence.  When an
otherwise exact commander result has no direct battle ref, a source-lineage bridge
may bind it to one public battle dossier only if volume/revision and quoted source
fragments uniquely identify that dossier.  Otherwise it stays a search fallback.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
from pathlib import Path
from typing import Any

_CORE_PATH = Path(__file__).with_name("_build_military_archive_core.py")
_SPEC = importlib.util.spec_from_file_location("_build_military_archive_core", _CORE_PATH)
_CORE = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(_CORE)

# Preserve the historical module API: tests and helper scripts import constants and
# parser helpers from reader/build_military_archive.py directly.
for _name in dir(_CORE):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_CORE, _name)


_SOURCE_REF_RE = re.compile(r"卷(?P<volume>\d+)@(?P<revision>[^#\s]+)(?:#(?P<fragment>.*))?")
_SOURCE_FILE_RE = re.compile(r"volume-(?P<volume>\d+)\.")
_SOURCE_CARD_RE = re.compile(r"SRC-[^-]+-(?P<volume>\d+)-(?P<revision>[^#-]+)")


def _registry_fallback_score(anchor: str, search_text: str) -> int:
    """Conservative paraphrase matching inside already-routed registry rows only."""
    variants = _CORE._anchor_variants(anchor)
    if not variants:
        return 0
    main = variants[0]
    if len(main) < 5:
        return 0
    haystack = _CORE._compact_text(search_text)
    grams = {main[index:index + 2] for index in range(len(main) - 1)}
    if not grams:
        return 0
    hits = sum(1 for gram in grams if gram in haystack)
    coverage = hits / len(grams)
    if hits < 3 or coverage < 0.3:
        return 0
    return 100 + hits + int(coverage * 100)


def _bind_route(mapping: dict[str, str], ref: Any, battle_id: str) -> None:
    text = str(ref or "").strip()
    if not text:
        return
    prior = mapping.get(text)
    if prior and prior != battle_id:
        raise ValueError(f"public registry ref maps to two battles: {text}: {prior}, {battle_id}")
    mapping[text] = battle_id


def _collect_registry_routes(root: Path) -> tuple[dict[str, str], dict[str, set[str]]]:
    routes: dict[str, str] = {}
    group_candidates: dict[str, set[str]] = {}

    def remember_group(ref: Any, battle_id: str) -> None:
        text = str(ref or "").strip()
        if text:
            group_candidates.setdefault(text, set()).add(battle_id)

    for shard in sorted((root / _CORE.BATTLE_DIR).glob("*.json")):
        payload = _CORE._load(shard)
        for record in payload.get("records", []):
            if not isinstance(record, dict):
                continue
            battle_id = str(record.get("war_event_id") or "").strip()
            if not battle_id:
                continue
            _bind_route(routes, battle_id, battle_id)
            remember_group(record.get("campaign_group_ref"), battle_id)

            members = record.get("members") or []
            if isinstance(members, dict):
                members = [members]
            if isinstance(members, list):
                for member in members:
                    if not isinstance(member, dict):
                        continue
                    results = member.get("person_command_result") or []
                    if isinstance(results, dict):
                        results = [results]
                    if isinstance(results, list):
                        for result in results:
                            if isinstance(result, dict):
                                _bind_route(routes, result.get("result_ref"), battle_id)

            phases = record.get("subject_phase_views") or []
            if isinstance(phases, dict):
                phases = [phases]
            if isinstance(phases, list):
                for phase in phases:
                    if not isinstance(phase, dict):
                        continue
                    _bind_route(routes, phase.get("phase_id"), battle_id)
                    remember_group(phase.get("campaign_group_ref"), battle_id)

    for ref, battle_ids in group_candidates.items():
        if len(battle_ids) == 1:
            _bind_route(routes, ref, next(iter(battle_ids)))
    return routes, group_candidates


def _source_lineage_from_refs(refs: Any) -> tuple[set[tuple[str, str]], set[str]]:
    keys: set[tuple[str, str]] = set()
    fragments: set[str] = set()
    if isinstance(refs, str):
        refs = [refs]
    if not isinstance(refs, list):
        return keys, fragments
    for raw in refs:
        text = str(raw or "").strip()
        match = _SOURCE_REF_RE.search(text)
        if not match:
            continue
        keys.add((match.group("volume"), match.group("revision")))
        fragment = _CORE._compact_text(match.group("fragment") or "")
        if len(fragment) >= 4:
            fragments.add(fragment)
    return keys, fragments


def _record_lineage_keys(record: dict[str, Any]) -> set[tuple[str, str]]:
    lineage = record.get("source_lineage") or {}
    if not isinstance(lineage, dict):
        lineage = {}
    volumes = {
        match.group("volume")
        for raw in lineage.get("source_files") or []
        for match in [_SOURCE_FILE_RE.search(str(raw or ""))]
        if match
    }
    revisions = {
        str(value).strip()
        for value in lineage.get("source_revision_refs") or []
        if str(value or "").strip()
    }

    # Older cards sometimes expose the pair only through source card ids.
    for raw in lineage.get("source_card_ids") or []:
        match = _SOURCE_CARD_RE.search(str(raw or ""))
        if match:
            volumes.add(match.group("volume"))
            revisions.add(match.group("revision"))

    return {(volume, revision) for volume in volumes for revision in revisions}


def _public_battle_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for shard in sorted((root / _CORE.BATTLE_DIR).glob("*.json")):
        payload = _CORE._load(shard)
        for record in payload.get("records", []):
            if not isinstance(record, dict):
                continue
            battle_id = str(record.get("war_event_id") or "").strip()
            if not battle_id:
                continue
            text_parts: list[Any] = [
                record.get("canonical_label"),
                record.get("observable_result"),
                record.get("campaign_group_ref"),
                *(record.get("source_quotes") or []),
            ]
            phases = record.get("subject_phase_views") or []
            if isinstance(phases, dict):
                phases = [phases]
            if isinstance(phases, list):
                for phase in phases:
                    if not isinstance(phase, dict):
                        continue
                    for key in (
                        "evaluation_subject_phase",
                        "actual_process",
                        "carry_in",
                        "carry_out",
                        "campaign_group_ref",
                    ):
                        if phase.get(key):
                            text_parts.append(phase[key])
            rows.append({
                "id": battle_id,
                "dynasty": str(record.get("dynasty") or "").strip(),
                "lineage_keys": _record_lineage_keys(record),
                "search_text": " ".join(str(part) for part in text_parts if part),
            })
    return rows


def _achievement_battle_id_from_routes(achievement: dict[str, Any], routes: dict[str, str]) -> str | None:
    for key in ("person_command_result_ref", "capability_episode_ref", "campaign_ref"):
        ref = str(achievement.get(key) or "").strip()
        battle_id = routes.get(ref)
        if battle_id:
            return battle_id
    return None


def _commander_evidence_rows(
    root: Path,
    routes: dict[str, str],
    group_candidates: dict[str, set[str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str | None, str, str, str, tuple[str, ...]]] = set()
    for shard in sorted((root / _CORE.COMMANDER_DIR).glob("*.json")):
        payload = _CORE._load(shard)
        for profile in payload.get("profiles", []):
            if not isinstance(profile, dict):
                continue
            names = tuple(sorted({
                str(name).strip()
                for name in [profile.get("person"), *(profile.get("name_aliases") or [])]
                if str(name or "").strip()
            }))
            dynasties = {
                str(name).strip()
                for name in [profile.get("dynasty"), *(profile.get("dynasty_aliases") or [])]
                if str(name or "").strip()
            }
            if not names:
                continue
            for collection in ("consumed_achievements", "negative_or_mixed_command_records"):
                for achievement in profile.get(collection) or []:
                    if not isinstance(achievement, dict):
                        continue
                    grade = _CORE._normalize_grade(
                        achievement.get("campaign_tier") or achievement.get("parent_campaign_tier")
                    )
                    difficulty = str(
                        achievement.get("combat_difficulty")
                        or achievement.get("parent_combat_difficulty")
                        or ""
                    ).strip()
                    if not grade or not difficulty:
                        continue
                    battle_id = _achievement_battle_id_from_routes(achievement, routes)
                    refs = {
                        str(achievement.get(key) or "").strip()
                        for key in ("person_command_result_ref", "capability_episode_ref", "campaign_ref")
                        if str(achievement.get(key) or "").strip()
                    }
                    if not battle_id and any(
                        ref in group_candidates and len(group_candidates[ref]) > 1
                        for ref in refs
                    ):
                        # A known multi-dossier campaign group is intentionally not a
                        # single-battle omission. Keep the core unresolved/searchable.
                        continue
                    search_text = " ".join(
                        str(achievement.get(key) or "")
                        for key in ("canonical_label", "basis")
                    )
                    signature = (battle_id, grade, difficulty, _CORE._compact_text(search_text), names)
                    if signature in seen:
                        continue
                    seen.add(signature)
                    source_keys, source_fragments = _source_lineage_from_refs(achievement.get("source_refs"))
                    rows.append({
                        "id": battle_id,
                        "result_grade": grade,
                        "difficulty_grade": difficulty,
                        "members": set(names),
                        "dynasties": dynasties,
                        "search_text": search_text,
                        "source_keys": source_keys,
                        "source_fragments": source_fragments,
                    })
    return rows


def _lineage_parent_battle(
    anchor: dict[str, Any],
    evidence_row: dict[str, Any],
    public_rows: list[dict[str, Any]],
) -> str | None:
    source_keys = evidence_row.get("source_keys") or set()
    fragments = evidence_row.get("source_fragments") or set()
    if not source_keys or not fragments:
        return None

    dynasties = evidence_row.get("dynasties") or set()
    scored: list[tuple[int, int, str]] = []
    for row in public_rows:
        if not source_keys.intersection(row.get("lineage_keys") or set()):
            continue
        if dynasties and row.get("dynasty") and row["dynasty"] not in dynasties:
            continue
        haystack = _CORE._compact_text(row.get("search_text") or "")
        fragment_hits = sum(1 for fragment in fragments if fragment in haystack)
        if fragment_hits < 1:
            continue
        anchor_score = _CORE._anchor_score(anchor["anchor"], row.get("search_text") or "")
        if anchor_score <= 0:
            continue
        scored.append((fragment_hits, anchor_score, str(row["id"])))

    if not scored:
        return None
    scored.sort(reverse=True)
    top_hits, top_anchor_score = scored[0][0], scored[0][1]
    top_ids = sorted({
        battle_id
        for hits, anchor_score, battle_id in scored
        if hits == top_hits and anchor_score == top_anchor_score
    })
    return top_ids[0] if len(top_ids) == 1 else None


def _resolve_registry_evidence(
    anchor: dict[str, Any],
    rows: list[dict[str, Any]],
    public_rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    ruler = str(anchor.get("ruler") or "")
    wanted = (anchor.get("result_grade"), anchor.get("difficulty_grade"))
    routed: list[tuple[int, str]] = []
    weak_routed: list[tuple[int, str]] = []
    unbound_rows: list[tuple[int, dict[str, Any]]] = []

    for row in rows:
        if ruler not in row["members"]:
            continue
        if wanted != (row["result_grade"], row["difficulty_grade"]):
            continue
        battle_id = row.get("id")
        score = _CORE._anchor_score(anchor["anchor"], row["search_text"])
        if score:
            if battle_id:
                routed.append((score, str(battle_id)))
            else:
                unbound_rows.append((score, row))
        elif battle_id:
            weak = _registry_fallback_score(anchor["anchor"], row["search_text"])
            if weak:
                weak_routed.append((weak, str(battle_id)))

    # Safety ordering is strict: exact routable evidence; exact facade evidence with
    # a unique public source-lineage parent; exact but still unbound evidence; then
    # weak paraphrase disambiguation among already-routed rows.
    if routed:
        routed.sort(reverse=True)
        top_score = routed[0][0]
        top_ids = sorted({battle_id for score, battle_id in routed if score == top_score})
        if len(top_ids) == 1:
            return {
                "status": "resolved_unique",
                "resolution_mode": "registry_ref",
                "battle_id": top_ids[0],
                "candidate_count": len(routed),
            }
        return {
            "status": "ambiguous",
            "resolution_mode": None,
            "battle_id": None,
            "candidate_count": len(routed),
        }

    if unbound_rows:
        unbound_rows.sort(key=lambda item: item[0], reverse=True)
        top_score = unbound_rows[0][0]
        top_rows = [row for score, row in unbound_rows if score == top_score]
        lineage_ids = sorted({
            battle_id
            for row in top_rows
            for battle_id in [_lineage_parent_battle(anchor, row, public_rows)]
            if battle_id
        })
        if len(lineage_ids) == 1:
            return {
                "status": "resolved_unique",
                "resolution_mode": "registry_lineage",
                "battle_id": lineage_ids[0],
                "candidate_count": len(top_rows),
            }
        return {
            "status": "search_only_unbound_registry",
            "resolution_mode": "unbound_registry",
            "battle_id": None,
            "candidate_count": len(unbound_rows),
        }

    if weak_routed:
        weak_routed.sort(reverse=True)
        top_score = weak_routed[0][0]
        top_ids = sorted({battle_id for score, battle_id in weak_routed if score == top_score})
        if len(top_ids) == 1:
            return {
                "status": "resolved_unique",
                "resolution_mode": "registry_ref",
                "battle_id": top_ids[0],
                "candidate_count": len(weak_routed),
            }
        return {
            "status": "ambiguous",
            "resolution_mode": None,
            "battle_id": None,
            "candidate_count": len(weak_routed),
        }
    return None


def _recount_anchor_stats(anchors: list[dict[str, Any]]) -> dict[str, int]:
    stats = {
        "resolved_unique": 0,
        "resolved_registry_ref": 0,
        "resolved_registry_lineage": 0,
        "resolved_battle_text": 0,
        "search_only_aggregate": 0,
        "search_only_strategic": 0,
        "search_only_nonspecific": 0,
        "search_only_unbound_registry": 0,
        "ambiguous": 0,
        "unresolved_atomic": 0,
    }
    for anchor in anchors:
        status = str(anchor.get("status") or "unresolved_atomic")
        if status in stats:
            stats[status] += 1
        if status == "resolved_unique":
            mode = str(anchor.get("resolution_mode") or "battle_text")
            key = f"resolved_{mode}"
            if key in stats:
                stats[key] += 1
    return stats


def _reconcile_first_item_c(root: Path, battle_index: dict[str, Any]) -> None:
    anchors = battle_index.get("first_item_c_anchors") or []
    if not any(item.get("status") == "unresolved_atomic" for item in anchors if isinstance(item, dict)):
        # Still normalize the expanded diagnostics schema for downstream readers.
        battle_index["first_item_c_anchor_stats"] = _recount_anchor_stats(anchors)
        return
    routes, group_candidates = _collect_registry_routes(root)
    evidence = _commander_evidence_rows(root, routes, group_candidates)
    public_rows = _public_battle_rows(root)
    for anchor in anchors:
        if not isinstance(anchor, dict) or anchor.get("status") != "unresolved_atomic":
            continue
        decision = _resolve_registry_evidence(anchor, evidence, public_rows)
        if decision:
            anchor.update(decision)
    battle_index["first_item_c_anchor_stats"] = _recount_anchor_stats(anchors)
    lookup = _CORE._anchor_lookup(anchors)
    battle_index["first_item_c_anchor_lookup"] = lookup
    battle_index["first_item_c_anchor_lookup_count"] = len(lookup)


def _reader_evidence(root: Path, battle_index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Project existing source cards and personal results; never infer grades."""
    by_id = {row["id"]: row for row in battle_index["records"]}
    routes = battle_index["result_ref_to_battle"]
    outputs: dict[str, dict[str, Any]] = {}
    details: dict[str, dict[str, Any]] = {}
    sources: dict[str, Any] = {}
    for shard in sorted((root / _CORE.BATTLE_DIR).glob("*.json")):
        for record in _CORE._load(shard).get("records", []):
            row = by_id[record["war_event_id"]]
            phases = record.get("subject_phase_views") or []
            parts = []
            for phase in phases:
                parts.extend(str(phase.get(key) or "") for key in ("evaluation_subject_phase", "actual_process", "carry_in", "carry_out"))
                parts.append(str((phase.get("ruler_binding") or {}).get("ruler_name") or ""))
            row["search_text"] = " ".join(parts)
            if not phases:
                continue
            filename = "evidence/" + shard.name
            row["evidence_source"] = "data/military/" + filename
            detail = {"source_cards": [], "personal_results": []}
            details[row["id"]] = detail
            outputs.setdefault(filename, {})[row["id"]] = detail
            phase_groups = {str(phase.get("campaign_group_ref") or "") for phase in phases}
            phase_refs = {str(ref) for phase in phases for ref in phase.get("source_anchor_refs") or []}
            for ref in row.get("source_files", []):
                if not ref.endswith(".json"):
                    continue
                if ref not in sources:
                    sources[ref] = _CORE._load(root / ref)
                source = sources[ref]
                for card in source.get("cards", source.get("battles", [])):
                    anchors = list(dict.fromkeys(card.get("source_anchor_refs") or card.get("source_refs") or []))
                    if card.get("campaign_group") not in phase_groups and not phase_refs.intersection(anchors):
                        continue
                    identity = source.get("source_identity") or {}
                    detail["source_cards"].append({
                        "title": card.get("battle_label"),
                        "source_volume": source.get("source_volume") or (str(source.get("chronicle") or "") + "/卷" + str(source.get("volume") or "")),
                        "source_url": identity.get("source_url") or source.get("source_url"),
                        "revision": identity.get("revision_ref") or source.get("revision_ref"),
                        "source": ref,
                        "group": card.get("campaign_group"),
                        "refs": anchors,
                        "quotes": [quote for quote in card.get("source_quotes") or [] if isinstance(quote, str)],
                    })
            if not detail["source_cards"] and record.get("source_quotes"):
                identity = (record.get("source_lineage") or {}).get("source_identity") or {}
                refs = list(dict.fromkeys([*(record.get("source_refs") or []), *sorted(phase_refs)]))
                book_ref = next((ref.split("@", 1)[0] for ref in refs if "/" in ref and "@" in ref), "")
                detail["source_cards"].append({
                    "title": record.get("canonical_label"), "source_volume": book_ref or identity.get("work_title"),
                    "source_url": identity.get("source_url"), "revision": identity.get("revision_ref"),
                    "source": row["source"], "group": "", "refs": refs,
                    "quotes": [quote for quote in record["source_quotes"] if isinstance(quote, str)],
                })
    seen = set()
    lineage_anchors = [anchor for anchor in battle_index.get("first_item_c_anchors", []) if anchor.get("status") == "resolved_unique" and anchor.get("resolution_mode") == "registry_lineage"]
    public_rows = _public_battle_rows(root) if lineage_anchors else []
    for shard in sorted((root / _CORE.COMMANDER_DIR).glob("*.json")):
        for profile in _CORE._load(shard).get("profiles", []):
            for collection in ("consumed_achievements", "negative_or_mixed_command_records", "failure_accountability"):
                for item in profile.get(collection) or []:
                    battle_id = _achievement_battle_id_from_routes(item, routes)
                    if not battle_id and lineage_anchors:
                        keys, fragments = _source_lineage_from_refs(item.get("source_refs"))
                        evidence_row = {"source_keys": keys, "source_fragments": fragments, "dynasties": {profile.get("dynasty"), *(profile.get("dynasty_aliases") or [])}}
                        names = {profile.get("person"), *(profile.get("name_aliases") or [])}
                        linked = set()
                        for anchor in lineage_anchors:
                            if anchor.get("ruler") not in names or (item.get("campaign_tier"), item.get("combat_difficulty")) != (anchor.get("result_grade"), anchor.get("difficulty_grade")):
                                continue
                            if not _CORE._anchor_score(anchor["anchor"], str(item.get("canonical_label") or "") + " " + str(item.get("basis") or "")):
                                continue
                            candidate = _lineage_parent_battle(anchor, evidence_row, public_rows)
                            if candidate == anchor.get("battle_id"):
                                linked.add(candidate)
                        if len(linked) == 1:
                            battle_id = next(iter(linked))
                            for key in ("person_command_result_ref", "capability_episode_ref", "campaign_ref"):
                                if item.get(key):
                                    routes[item[key]] = battle_id
                    if battle_id not in details:
                        continue
                    ref = item.get("person_command_result_ref") or item.get("capability_episode_ref") or item.get("campaign_ref")
                    signature = (battle_id, profile.get("profile_ref"), ref, item.get("result_direction"))
                    if signature in seen:
                        continue
                    seen.add(signature)
                    details[battle_id]["personal_results"].append({
                        "person": profile.get("person"), "profile_ref": profile.get("profile_ref"),
                        "source": shard.relative_to(root).as_posix(), "record": item,
                    })
                    names = [profile.get("person"), *(profile.get("name_aliases") or [])]
                    by_id[battle_id]["search_text"] += " " + " ".join(str(name) for name in names if name)
    return outputs


def _build_outputs(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    battle_index, commander_index = _CORE.build_indexes(root)
    _reconcile_first_item_c(root, battle_index)
    # All published reference types must work for dossier links, including a
    # direct war_event_id rather than only a personal result reference.
    routes, _ = _collect_registry_routes(root)
    battle_index["result_ref_to_battle"].update(routes)
    contexts: dict[str, dict[str, Any]] = {}
    context_path = root / "config/military/unification-campaign-tier-adjudications.json"
    adjudications = _CORE._load(context_path) if context_path.is_file() else {}
    for portfolio in adjudications.get("adjudications", []):
        for group in portfolio.get("campaign_groups", []):
            payload = group.get("payload") or {}
            contexts[group["campaign_group_id"]] = {
                "prewar": payload.get("prewar_context", ""),
                "objective": payload.get("strategic_objective", ""),
                "actions": [
                    {"person": member.get("actor_name", ""), "text": member["military_capability_contribution"]["basis"]}
                    for member in group.get("members", [])
                    if isinstance(member.get("military_capability_contribution"), dict)
                    and member["military_capability_contribution"].get("basis")
                ],
                "sources": ["config/military/unification-campaign-tier-adjudications.json", *group.get("source_refs", [])],
            }
    notes_path = root / "reader/military-reading-notes.json"
    notes = _CORE._load(notes_path).get("records", {}) if notes_path.is_file() else {}
    by_id = {row["id"]: row for row in battle_index["records"]}
    for row in battle_index["records"]:
        context = dict(contexts.get(row["id"], {}))
        note = notes.get(row["id"], {})
        for source in note.get("sources", []):
            if source.startswith(("docs/", "config/")) and not (root / source.split("#", 1)[0]).is_file():
                raise ValueError(f"missing reading-note source: {source}")
        context.update(note)
        if context:
            row["reading_context"] = context
        row["context"] = context.get("prewar", "")
        row["aliases"] = []
    for anchor in battle_index.get("first_item_c_anchors", []):
        row = by_id.get(anchor.get("battle_id"))
        if row is not None and anchor.get("status") == "resolved_unique":
            alias = anchor.get("anchor")
            if alias and alias not in row["aliases"]:
                row["aliases"].append(alias)
    for shard in sorted((root / _CORE.BATTLE_DIR).glob("*.json")):
        for record in _CORE._load(shard).get("records", []):
            row = by_id.get(record.get("war_event_id"))
            if row is not None:
                row["disposition"] = record.get("disposition")
                row["public_outcome_registered"] = record.get("public_outcome_registered")
                row["phase_count"] = len(record.get("subject_phase_views") or [])
                row["source_files"] = [ref for ref in record.get("source_lineage", {}).get("source_files", []) if (root / ref.split("#", 1)[0]).is_file()]
    evidence = _reader_evidence(root, battle_index)
    return battle_index, commander_index, evidence


def build_indexes(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    battle_index, commander_index, _ = _build_outputs(root)
    return battle_index, commander_index


def _build_military_page(root: Path = ROOT) -> None:
    """Build the served military page from a source template and freeze its JS."""
    template_path = root / "reader/military.template.html"
    output_path = root / "reader/military.html"
    script_path = root / "reader/military-archive.js"
    template = template_path.read_text(encoding="utf-8")
    marker = '<script src="military-archive.js"></script>'
    if template.count(marker) != 1:
        raise ValueError("military template must contain exactly one runtime script marker")
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    revision = os.environ.get("GITHUB_SHA", "").strip().lower()
    identity_path = root / "reader/source-revision.json"
    if (not repository or not revision) and identity_path.exists():
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        repository = str(identity.get("repository") or "").strip()
        revision = str(identity.get("revision") or "").strip().lower()
    prefix = (
        "const READER_SOURCE_REPOSITORY=" + json.dumps(repository, ensure_ascii=False) + ";\n"
        + "const READER_SOURCE_REVISION=" + json.dumps(revision, ensure_ascii=False) + ";\n"
    )
    script = prefix + script_path.read_text(encoding="utf-8")
    script = script.replace("</script>", r"<\/script>")
    rendered = template.replace(marker, f"<script>\n{script}\n</script>", 1)
    output_path.write_text(rendered, encoding="utf-8", newline="\n")


def main() -> None:
    battle_index, commander_index, evidence = _build_outputs(ROOT)
    out = ROOT / OUTPUT_DIR
    _CORE._write(out / "battles-index.json", battle_index)
    _CORE._write(out / "commanders-index.json", commander_index)
    for filename, payload in evidence.items():
        _CORE._write(out / filename, payload)
    _build_military_page(ROOT)
    stats = battle_index["first_item_c_anchor_stats"]
    print(
        "military archive indexes: "
        f"{battle_index['record_count']} battles, {commander_index['profile_count']} commanders; "
        f"first-item C anchors resolved={stats['resolved_unique']} "
        f"(registry-ref={stats['resolved_registry_ref']}, "
        f"registry-lineage={stats['resolved_registry_lineage']}, "
        f"battle-text={stats['resolved_battle_text']}) "
        f"aggregate-search={stats['search_only_aggregate']} "
        f"strategic-search={stats['search_only_strategic']} "
        f"nonspecific-search={stats['search_only_nonspecific']} "
        f"unbound-registry-search={stats['search_only_unbound_registry']} "
        f"ambiguous={stats['ambiguous']} unresolved-atomic={stats['unresolved_atomic']}"
    )


if __name__ == "__main__":
    main()
