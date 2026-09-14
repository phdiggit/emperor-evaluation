#!/usr/bin/env python3
"""Build lightweight reader indexes over the canonical military registries.

The indexes contain lookup/search metadata only. Battle and commander detail pages
fetch the original public-registry shard at read time, so the reader never owns a
second copy of the adjudication payload.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BATTLE_MANIFEST = Path("docs/公共成果/军事/01-战役登记.json")
BATTLE_DIR = Path("docs/公共成果/军事/01-战役登记")
COMMANDER_MANIFEST = Path("docs/公共成果/军事/02-武将人才等级.json")
COMMANDER_DIR = Path("docs/公共成果/军事/02-武将人才等级")
FIRST_ITEM_C_SETTLEMENT = Path("docs/评分结算/净收益/第一项政权奠基与统一贡献及能力/04-第一项C本人军事统帅与战争解题能力正式结算.md")
OUTPUT_DIR = Path("reader/data/military")

ANCHOR_RE = re.compile(
    r"(?:^|[：，；。、])(?P<anchor>[^，；。：、\s]{2,28}?)(?P<result>S\+|S-|S−|S|A|B|C)/(?P<difficulty>D[0-4])"
)
SECTION_RE = re.compile(r"^###\s+\d+\.\s*(?P<name>.+?)\s*$")
ANCHOR_PREFIXES = (
    "第一项主链内已有",
    "第一项建国统一链内",
    "现场与败责复验",
    "统帅证据",
    "核心前线峰值",
    "最高前线峰值",
    "前线峰值",
    "另有",
    "已有",
    "包括",
    "其中",
    "以及",
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=False) + "\n"
    path.write_text(text, encoding="utf-8")


def _period(record: dict[str, Any]) -> str:
    period = record.get("period") or {}
    if not isinstance(period, dict):
        return str(period).strip()
    start = str(period.get("start") or "").strip()
    end = str(period.get("end") or "").strip()
    if start and end and end != start:
        return f"{start}—{end}"
    return start or end


def _normalize_grade(value: Any) -> str:
    return str(value or "").strip().replace("S−", "S-")


def _compact_text(value: Any) -> str:
    return re.sub(r"[\s·，。；：、（）()《》“”\"'—－\-_/]+", "", str(value or "")).lower()


def _clean_anchor_name(value: str) -> str:
    text = str(value or "").strip(" ：，；。、")
    for prefix in ANCHOR_PREFIXES:
        if prefix in text:
            text = text.rsplit(prefix, 1)[-1]
    text = re.sub(r"^(?:并有|并以|又有|又以|有|以|在|由|如)", "", text)
    text = re.sub(r"(?:等|一役)$", "", text)
    return text.strip(" ：，；。、")


def _anchor_variants(anchor: str) -> list[str]:
    clean = _clean_anchor_name(anchor)
    values = [clean]
    for suffix in ("终局", "之战", "战役", "大战", "决战"):
        if clean.endswith(suffix) and len(clean) > len(suffix) + 1:
            values.append(clean[: -len(suffix)])
    if "—" in clean or "－" in clean or "-" in clean:
        values.extend(re.split(r"[—－-]+", clean))
    out: list[str] = []
    for value in values:
        compact = _compact_text(value)
        if len(compact) >= 2 and compact not in out:
            out.append(compact)
    return out


def _anchor_score(anchor: str, search_text: str) -> int:
    haystack = _compact_text(search_text)
    variants = _anchor_variants(anchor)
    if not variants:
        return 0
    exact = [value for value in variants if value in haystack]
    if exact:
        return 1000 + max(len(value) for value in exact)

    main = variants[0]
    if len(main) < 3:
        return 0
    grams = {main[index:index + 2] for index in range(len(main) - 1)}
    if not grams:
        return 0
    hits = sum(1 for gram in grams if gram in haystack)
    coverage = hits / len(grams)
    return int(coverage * 100) if coverage >= 0.6 else 0


def _parse_first_item_c_anchors(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    ruler = ""
    found: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        heading = SECTION_RE.match(line)
        if heading:
            ruler = heading.group("name").strip()
            continue
        if not ruler or "结算依据" not in line:
            continue
        for match in ANCHOR_RE.finditer(line):
            anchor = _clean_anchor_name(match.group("anchor"))
            if len(_compact_text(anchor)) < 2:
                continue
            result = _normalize_grade(match.group("result"))
            difficulty = match.group("difficulty")
            key = (ruler, anchor, result, difficulty)
            if key in seen:
                continue
            seen.add(key)
            found.append({
                "ruler": ruler,
                "anchor": anchor,
                "result_grade": result,
                "difficulty_grade": difficulty,
            })
    return found


def _member_result_rows(member: dict[str, Any]) -> tuple[set[tuple[str, str]], list[str], list[str]]:
    pairs: set[tuple[str, str]] = set()
    refs: list[str] = []
    text_parts: list[str] = []
    index = member.get("person_command_index") or {}
    if isinstance(index, dict):
        result = _normalize_grade(index.get("projected_result_tier"))
        difficulty = str(index.get("projected_combat_difficulty") or "").strip()
        if result and difficulty:
            pairs.add((result, difficulty))
        for key in ("basis",):
            if index.get(key):
                text_parts.append(str(index[key]))

    results = member.get("person_command_result") or []
    if isinstance(results, dict):
        results = [results]
    if not isinstance(results, list):
        results = []
    for result in results:
        if not isinstance(result, dict):
            continue
        grade = _normalize_grade(result.get("result_tier"))
        difficulty = str(result.get("combat_difficulty") or "").strip()
        if grade and difficulty:
            pairs.add((grade, difficulty))
        ref = str(result.get("result_ref") or "").strip()
        if ref:
            refs.append(ref)
        for key in ("result_label", "basis"):
            if result.get(key):
                text_parts.append(str(result[key]))
    return pairs, refs, text_parts


def _resolve_first_item_c_anchors(
    anchors: list[dict[str, str]],
    match_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    resolved: list[dict[str, Any]] = []
    stats = {"resolved_unique": 0, "ambiguous": 0, "unresolved": 0}
    for anchor in anchors:
        ruler = anchor["ruler"]
        wanted_pair = (anchor["result_grade"], anchor["difficulty_grade"])
        scored: list[tuple[int, str]] = []
        for row in match_rows:
            member_pairs = row["member_pairs"].get(ruler, set())
            parent_pair = (row["result_grade"], row["difficulty_grade"])
            if wanted_pair != parent_pair and wanted_pair not in member_pairs:
                continue
            if ruler not in row["members"] and _compact_text(ruler) not in _compact_text(row["search_text"]):
                continue
            score = _anchor_score(anchor["anchor"], row["search_text"])
            if score:
                scored.append((score, row["id"]))
        scored.sort(reverse=True)
        battle_id = None
        status = "unresolved"
        if scored:
            top = scored[0][0]
            top_ids = sorted({battle for score, battle in scored if score == top})
            if len(top_ids) == 1:
                battle_id = top_ids[0]
                status = "resolved_unique"
            else:
                status = "ambiguous"
        stats[status] += 1
        resolved.append({
            **anchor,
            "battle_id": battle_id,
            "status": status,
            "candidate_count": len(scored),
        })
    return resolved, stats


def build_indexes(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    battle_manifest = _load(root / BATTLE_MANIFEST)
    battle_rows: list[dict[str, Any]] = []
    match_rows: list[dict[str, Any]] = []
    result_ref_to_battle: dict[str, str] = {}
    seen_battles: set[str] = set()

    for shard in sorted((root / BATTLE_DIR).glob("*.json")):
        payload = _load(shard)
        for record in payload.get("records", []):
            if not isinstance(record, dict):
                continue
            battle_id = record.get("war_event_id")
            if not battle_id or battle_id in seen_battles:
                raise ValueError(f"duplicate or missing battle id in {shard}: {battle_id}")
            seen_battles.add(battle_id)
            members = record.get("members") or []
            member_names: list[str] = []
            member_pairs: dict[str, set[tuple[str, str]]] = {}
            result_refs: list[str] = []
            search_parts = [
                record.get("canonical_label"),
                record.get("observable_result"),
                record.get("source_target_ref"),
            ]
            for member in members:
                if not isinstance(member, dict):
                    continue
                name = str(member.get("actor_name") or "").strip()
                if name and name not in member_names:
                    member_names.append(name)
                pairs, refs, result_text = _member_result_rows(member)
                if name and pairs:
                    member_pairs.setdefault(name, set()).update(pairs)
                for ref in refs:
                    prior = result_ref_to_battle.get(ref)
                    if prior and prior != battle_id:
                        raise ValueError(f"person result ref maps to two battles: {ref}: {prior}, {battle_id}")
                    result_ref_to_battle[ref] = battle_id
                    result_refs.append(ref)
                search_parts.extend(result_text)
                if member.get("contribution_scope"):
                    search_parts.append(member["contribution_scope"])

            result_grade = _normalize_grade(record.get("campaign_tier"))
            difficulty_grade = str(record.get("combat_difficulty") or "").strip()
            battle_rows.append({
                "id": battle_id,
                "name": record.get("canonical_label") or record.get("observable_result") or battle_id,
                "dynasty": record.get("dynasty") or "",
                "period": _period(record),
                "result_grade": result_grade or None,
                "difficulty_grade": difficulty_grade or None,
                "direction": record.get("result_direction"),
                "members": member_names,
                "result_refs": result_refs,
                "source": shard.relative_to(root).as_posix(),
            })
            match_rows.append({
                "id": battle_id,
                "result_grade": result_grade,
                "difficulty_grade": difficulty_grade,
                "members": set(member_names),
                "member_pairs": member_pairs,
                "search_text": " ".join(str(part) for part in search_parts if part),
            })

    expected_battles = int(battle_manifest.get("record_count") or len(battle_rows))
    if len(battle_rows) != expected_battles:
        raise ValueError(f"battle registry count mismatch: {len(battle_rows)} != {expected_battles}")

    anchors = _parse_first_item_c_anchors(root / FIRST_ITEM_C_SETTLEMENT)
    first_item_anchors, anchor_stats = _resolve_first_item_c_anchors(anchors, match_rows)

    anchor_targets: dict[str, set[str]] = {}
    for item in first_item_anchors:
        if item["status"] != "resolved_unique" or not item["battle_id"]:
            continue
        key = _compact_text(_clean_anchor_name(item["anchor"]))
        if key:
            anchor_targets.setdefault(key, set()).add(item["battle_id"])
    anchor_lookup = {
        key: next(iter(targets))
        for key, targets in sorted(anchor_targets.items())
        if len(targets) == 1
    }

    battle_rows.sort(key=lambda row: (str(row["dynasty"]), str(row["period"]), str(row["name"]), row["id"]))
    battle_index = {
        "schema_version": "reader-military-battle-index-v2",
        "source_manifest": BATTLE_MANIFEST.as_posix(),
        "first_item_c_source": FIRST_ITEM_C_SETTLEMENT.as_posix(),
        "record_count": len(battle_rows),
        "records": battle_rows,
        "result_ref_to_battle": dict(sorted(result_ref_to_battle.items())),
        "first_item_c_anchors": first_item_anchors,
        "first_item_c_anchor_stats": anchor_stats,
        "first_item_c_anchor_lookup": anchor_lookup,
        "first_item_c_anchor_lookup_count": len(anchor_lookup),
    }

    commander_manifest = _load(root / COMMANDER_MANIFEST)
    commander_rows: list[dict[str, Any]] = []
    seen_profiles: set[str] = set()
    for shard in sorted((root / COMMANDER_DIR).glob("*.json")):
        payload = _load(shard)
        for profile in payload.get("profiles", []):
            if not isinstance(profile, dict):
                continue
            profile_ref = profile.get("profile_ref")
            if not profile_ref or profile_ref in seen_profiles:
                raise ValueError(f"duplicate or missing commander profile ref in {shard}: {profile_ref}")
            seen_profiles.add(profile_ref)
            commander_rows.append({
                "profile_ref": profile_ref,
                "person_ref": profile.get("person_ref"),
                "name": profile.get("person") or profile_ref,
                "aliases": profile.get("name_aliases") or [],
                "dynasty": profile.get("dynasty") or "",
                "grade": profile.get("military_grade"),
                "grade_status": profile.get("grade_status"),
                "stability_status": profile.get("stability_status"),
                "actor_refs": profile.get("actor_ref_aliases") or [],
                "source": shard.relative_to(root).as_posix(),
            })

    payload_meta = commander_manifest.get("payload_metadata") or {}
    expected_profiles = int(commander_manifest.get("profile_count") or payload_meta.get("profile_count") or len(commander_rows))
    if len(commander_rows) != expected_profiles:
        raise ValueError(f"commander registry count mismatch: {len(commander_rows)} != {expected_profiles}")
    commander_rows.sort(key=lambda row: (str(row["dynasty"]), str(row["name"]), row["profile_ref"]))
    commander_index = {
        "schema_version": "reader-military-commander-index-v1",
        "source_manifest": COMMANDER_MANIFEST.as_posix(),
        "profile_count": len(commander_rows),
        "records": commander_rows,
    }
    return battle_index, commander_index


def main() -> None:
    battle_index, commander_index = build_indexes(ROOT)
    out = ROOT / OUTPUT_DIR
    _write(out / "battles-index.json", battle_index)
    _write(out / "commanders-index.json", commander_index)
    stats = battle_index["first_item_c_anchor_stats"]
    print(
        "military archive indexes: "
        f"{battle_index['record_count']} battles, {commander_index['profile_count']} commanders; "
        f"first-item C anchors resolved={stats['resolved_unique']} "
        f"ambiguous={stats['ambiguous']} unresolved={stats['unresolved']}"
    )


if __name__ == "__main__":
    main()
