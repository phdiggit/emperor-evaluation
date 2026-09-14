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
    r"(?:^|[：，；。、])(?P<anchor>[^，；。：、\s]{2,32}?)(?P<result>S\+|S-|S−|S|A|B|C)/(?P<difficulty>D[0-4])"
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
AGGREGATE_MARKERS = (
    "多次", "多个", "多项", "大量", "两次", "诸战", "等方向", "等有", "等形成", "等达到",
)
NONSPECIFIC_ANCHORS = {
    "多次", "多个", "多项", "大量", "旧c按", "旧登记", "旧登记为", "形成", "只有", "缺少",
    "只支持", "人物结果只有", "人物级只消费",
}


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

    # Formal settlement prose often wraps the battle name in structural wording such
    # as “第一项创业链内有…” or “第一项窗口内可确认…”. Strip only when the left
    # side clearly describes a window/chain rather than a historical place or battle.
    structural = re.match(
        r"^.*(?:链|窗口|主线|创业|统一|建国)(?:内|中)(?:已有|有|可确认|可用)?(?P<tail>.{2,})$",
        text,
    )
    if structural:
        text = structural.group("tail")

    text = re.sub(r"^(?:并有|并以|又有|又以|有|以|在|由|如|但)", "", text)
    text = re.sub(r"(?:的)$", "", text)
    text = re.sub(
        r"(?:均有|存在一项|有多个|有多次|等有多个|等有多次|等多次|等多个|等多项|"
        r"形成多次|形成两次|持续形成|形成|相关|达到|存在|可作|仅为|为)$",
        "",
        text,
    )
    text = re.sub(r"(?:等|一役)$", "", text)
    return text.strip(" ：，；。、")


def _anchor_kind(raw_anchor: str, clean_anchor: str) -> str:
    raw = str(raw_anchor or "")
    clean = str(clean_anchor or "")
    compact = _compact_text(clean)
    if not compact or compact in NONSPECIFIC_ANCHORS or len(compact) < 2:
        return "nonspecific"
    if any(marker in raw for marker in AGGREGATE_MARKERS):
        return "aggregate"
    if "及" in clean and any(token in clean for token in ("终局", "战", "侵", "方向")):
        return "aggregate"
    return "atomic"


def _anchor_variants(anchor: str) -> list[str]:
    clean = _clean_anchor_name(anchor)
    values = [clean]
    for suffix in ("终局", "方向", "相关", "之战", "战役", "大战", "决战", "围城", "主战线"):
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
            raw_anchor = match.group("anchor").strip(" ：，；。、")
            anchor = _clean_anchor_name(raw_anchor)
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
                "raw_anchor": raw_anchor,
                "anchor_kind": _anchor_kind(raw_anchor, anchor),
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
        if index.get("basis"):
            text_parts.append(str(index["basis"]))

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
    stats = {
        "resolved_unique": 0,
        "resolved_registry_ref": 0,
        "resolved_battle_text": 0,
        "search_only_aggregate": 0,
        "search_only_nonspecific": 0,
        "ambiguous": 0,
        "unresolved_atomic": 0,
    }
    for anchor in anchors:
        kind = anchor.get("anchor_kind") or "atomic"
        if kind != "atomic":
            status = f"search_only_{kind}"
            stats[status] += 1
            resolved.append({
                **anchor,
                "battle_id": None,
                "status": status,
                "resolution_mode": None,
                "candidate_count": 0,
            })
            continue

        ruler = anchor["ruler"]
        wanted_pair = (anchor["result_grade"], anchor["difficulty_grade"])
        scored: list[tuple[int, int, str, str]] = []
        for row in match_rows:
            member_pairs = row.get("member_pairs", {}).get(ruler, set())
            parent_pair = (row["result_grade"], row["difficulty_grade"])
            if wanted_pair != parent_pair and wanted_pair not in member_pairs:
                continue
            if ruler not in row["members"] and _compact_text(ruler) not in _compact_text(row["search_text"]):
                continue
            score = _anchor_score(anchor["anchor"], row["search_text"])
            if score:
                scored.append((
                    int(row.get("priority") or 1),
                    score,
                    row["id"],
                    str(row.get("resolution_mode") or "battle_text"),
                ))
        scored.sort(reverse=True)
        battle_id = None
        status = "unresolved_atomic"
        resolution_mode = None
        if scored:
            top_priority, top_score = scored[0][0], scored[0][1]
            top_rows = [item for item in scored if item[0] == top_priority and item[1] == top_score]
            top_ids = sorted({item[2] for item in top_rows})
            if len(top_ids) == 1:
                battle_id = top_ids[0]
                status = "resolved_unique"
                resolution_mode = "registry_ref" if any(item[3] == "registry_ref" for item in top_rows) else "battle_text"
            else:
                status = "ambiguous"
        stats[status] += 1
        if status == "resolved_unique":
            stats[f"resolved_{resolution_mode}"] += 1
        resolved.append({
            **anchor,
            "battle_id": battle_id,
            "status": status,
            "resolution_mode": resolution_mode,
            "candidate_count": len(scored),
        })
    return resolved, stats


def _anchor_lookup(resolved: list[dict[str, Any]]) -> dict[str, str]:
    targets: dict[str, set[str]] = {}
    for item in resolved:
        if item["status"] != "resolved_unique" or not item["battle_id"]:
            continue
        for key in _anchor_variants(item["anchor"]):
            targets.setdefault(key, set()).add(item["battle_id"])
    return {
        key: next(iter(battle_ids))
        for key, battle_ids in sorted(targets.items())
        if len(battle_ids) == 1
    }


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
                "priority": 1,
                "resolution_mode": "battle_text",
            })

    expected_battles = int(battle_manifest.get("record_count") or len(battle_rows))
    if len(battle_rows) != expected_battles:
        raise ValueError(f"battle registry count mismatch: {len(battle_rows)} != {expected_battles}")

    anchors = _parse_first_item_c_anchors(root / FIRST_ITEM_C_SETTLEMENT)

    battle_rows.sort(key=lambda row: (str(row["dynasty"]), str(row["period"]), str(row["name"]), row["id"]))
    battle_index = {
        "schema_version": "reader-military-battle-index-v3",
        "source_manifest": BATTLE_MANIFEST.as_posix(),
        "first_item_c_source": FIRST_ITEM_C_SETTLEMENT.as_posix(),
        "record_count": len(battle_rows),
        "records": battle_rows,
        "result_ref_to_battle": dict(sorted(result_ref_to_battle.items())),
    }

    commander_manifest = _load(root / COMMANDER_MANIFEST)
    commander_rows: list[dict[str, Any]] = []
    achievement_match_rows: list[dict[str, Any]] = []
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
            profile_names = {
                str(name).strip()
                for name in [profile.get("person"), *(profile.get("name_aliases") or [])]
                if str(name or "").strip()
            }
            for achievement in profile.get("consumed_achievements") or []:
                if not isinstance(achievement, dict):
                    continue
                ref = str(achievement.get("campaign_ref") or achievement.get("capability_episode_ref") or "").strip()
                battle_id = result_ref_to_battle.get(ref)
                if not battle_id or not profile_names:
                    continue
                result_grade = _normalize_grade(achievement.get("campaign_tier") or achievement.get("parent_campaign_tier"))
                difficulty_grade = str(
                    achievement.get("combat_difficulty")
                    or achievement.get("parent_combat_difficulty")
                    or ""
                ).strip()
                if not result_grade or not difficulty_grade:
                    continue
                achievement_match_rows.append({
                    "id": battle_id,
                    "result_grade": result_grade,
                    "difficulty_grade": difficulty_grade,
                    "members": profile_names,
                    "member_pairs": {},
                    "search_text": " ".join(
                        str(achievement.get(key) or "")
                        for key in ("canonical_label", "basis")
                    ),
                    "priority": 2,
                    "resolution_mode": "registry_ref",
                })

    payload_meta = commander_manifest.get("payload_metadata") or {}
    expected_profiles = int(commander_manifest.get("profile_count") or payload_meta.get("profile_count") or len(commander_rows))
    if len(commander_rows) != expected_profiles:
        raise ValueError(f"commander registry count mismatch: {len(commander_rows)} != {expected_profiles}")

    first_item_anchors, anchor_stats = _resolve_first_item_c_anchors(
        anchors,
        [*match_rows, *achievement_match_rows],
    )
    anchor_lookup = _anchor_lookup(first_item_anchors)
    battle_index["first_item_c_anchors"] = first_item_anchors
    battle_index["first_item_c_anchor_stats"] = anchor_stats
    battle_index["first_item_c_anchor_lookup"] = anchor_lookup
    battle_index["first_item_c_anchor_lookup_count"] = len(anchor_lookup)

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
        f"(registry-ref={stats['resolved_registry_ref']}, battle-text={stats['resolved_battle_text']}) "
        f"aggregate-search={stats['search_only_aggregate']} "
        f"nonspecific-search={stats['search_only_nonspecific']} "
        f"ambiguous={stats['ambiguous']} unresolved-atomic={stats['unresolved_atomic']}"
    )


if __name__ == "__main__":
    main()
