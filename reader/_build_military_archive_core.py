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
STRUCTURED_C_BATTLE_RE = re.compile(
    r"^\s*(?P<anchor>.+?)\s*[｜|]\s*(?P<role>前线作战|战略统筹)\s*[｜|]\s*"
    r"(?P<result>S\+|S-|S−|S|A|B|C)\s*[｜|]\s*(?P<difficulty>D[0-4]|[—-])\s*$"
)
SECTION_RE = re.compile(r"^###\s+\d+\.\s*(?P<name>.+?)\s*$", re.MULTILINE)
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
    "多次", "多个", "多项", "大量", "两次", "诸战", "连续亲征", "连续作战", "清剿",
    "等方向", "等有", "等形成", "等达到", "创业竞争中", "成果中",
)
NONSPECIFIC_ANCHORS = {
    "多次", "多个", "多项", "大量", "旧c按", "旧登记", "旧登记为", "形成", "只有", "缺少",
    "只支持", "人物结果只有", "人物级只消费",
}
NARRATIVE_PREFIX_RE = re.compile(
    r"^(?:随后|早期|公共人才表(?:最强的|虽有)|"
    r"本人.*?后立即在|"
    r".*?(?:本人可用前线成果主要是|前线成果主要是)(?:取得|攻取)?|"
    r"\d{3,4}年)"
)
ACTION_PREFIX_RE = re.compile(r"^(?:直取|攻取|夺取|取得|攻下|拿下|平定|灭|终结)")
VARIANT_SPLIT_RE = re.compile(
    r"(?:方向|右军|左军|主力|亲督|长围|整军|接战|反败为胜|伏击|围攻|渡河|并|至政权|至其|后迫|后击|后破)"
)
NAMED_BATTLE_PREFIX_RE = re.compile(
    r"^(.+?(?:之战|战役|战争|大战|决战|会战|之围|围城|攻城))"
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

    structural = re.match(
        r"^.*(?:链|窗口|主线|创业|统一|建国)(?:内|中)(?:已有|有|可确认|可用)?(?P<tail>.{2,})$",
        text,
    )
    if structural:
        text = structural.group("tail")

    previous = None
    while text != previous:
        previous = text
        text = NARRATIVE_PREFIX_RE.sub("", text).strip(" ：，；。、")
    text = ACTION_PREFIX_RE.sub("", text).strip(" ：，；。、")
    text = re.sub(r"^(?:并有|并以|又有|又以|有|以|在|由|如|但)", "", text)
    text = re.sub(r"(?:的)$", "", text)
    text = re.sub(
        r"(?:均有|均|存在一项|有多个|有多次|等有多个|等有多次|等多次|等多个|等多项|"
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

    raw_compact = _compact_text(raw)
    if re.search(r"旧c.*(?:闭合|支持|按)", raw_compact):
        return "nonspecific"
    if "同窗口" in clean or clean.endswith(("主链中", "窗口中", "主线中")):
        return "nonspecific"

    if any(marker in raw for marker in AGGREGATE_MARKERS):
        return "aggregate"
    if "及" in clean and any(token in clean for token in ("终局", "战", "侵", "方向", "成果")):
        return "aggregate"

    # Direction-only, state-building and founding-war phrases describe a strategic
    # phase rather than one addressable battle dossier. Keep them searchable instead
    # of forcing a guessed battle_id.
    if re.fullmatch(r".{2,20}方向", clean):
        return "strategic"
    if clean.startswith("建立"):
        return "strategic"
    if "创业战争" in clean:
        return "strategic"
    if re.search(r"并建立.{1,20}(?:核心|政权|基础|根基)?$", clean):
        return "strategic"

    return "atomic"


def _anchor_variants(anchor: str) -> list[str]:
    clean = _clean_anchor_name(anchor)
    values = [clean]
    for suffix in (
        "终局", "方向", "相关", "之战", "战役", "战争", "大战", "决战", "会战", "之围",
        "围城", "解围", "主战线", "政权", "作战", "逆转",
    ):
        if clean.endswith(suffix) and len(clean) > len(suffix) + 1:
            values.append(clean[: -len(suffix)])
    if "—" in clean or "－" in clean or "-" in clean:
        values.extend(re.split(r"[—－-]+", clean))

    named_battle = NAMED_BATTLE_PREFIX_RE.match(clean)
    if named_battle and named_battle.group(1) != clean:
        values.append(named_battle.group(1))

    head = VARIANT_SPLIT_RE.split(clean, maxsplit=1)[0].strip(" ：，；。、")
    if head and head != clean:
        values.append(head)
    if "的" in clean:
        values.append(clean.split("的", 1)[0])

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
    found: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    text = path.read_text(encoding="utf-8-sig")
    sections = list(SECTION_RE.finditer(text))

    def add_anchor(
        ruler: str,
        raw_anchor: str,
        result: str,
        difficulty: str,
        role: str | None = None,
        preserve_name: bool = False,
    ) -> None:
        raw_anchor = raw_anchor.strip(" ：，；。、")
        anchor = raw_anchor if preserve_name else _clean_anchor_name(raw_anchor)
        if len(_compact_text(anchor)) < 2:
            return
        key = (ruler, anchor, result, difficulty)
        if key in seen:
            return
        seen.add(key)
        found.append({
            "ruler": ruler,
            "anchor": anchor,
            "raw_anchor": raw_anchor,
            "anchor_kind": "strategic" if role == "战略统筹" else _anchor_kind(raw_anchor, anchor),
            "role": role or ("战略统筹" if "统筹" in raw_anchor else "前线作战"),
            "result_grade": result,
            "difficulty_grade": difficulty,
        })

    for index, heading in enumerate(sections):
        ruler = heading.group("name").strip()
        end = sections[index + 1].start() if index + 1 < len(sections) else len(text)
        block = text[heading.end():end]
        structured_lines = [line for line in block.splitlines() if "统一链战役清单" in line]
        if structured_lines:
            for line in structured_lines:
                value = line.split("统一链战役清单**：", 1)[-1].rstrip("。")
                for raw_item in value.split("；"):
                    structured = STRUCTURED_C_BATTLE_RE.match(raw_item)
                    if not structured:
                        continue
                    difficulty = structured.group("difficulty")
                    if difficulty == "-":
                        difficulty = "—"
                    add_anchor(
                        ruler,
                        structured.group("anchor"),
                        _normalize_grade(structured.group("result")),
                        difficulty,
                        structured.group("role"),
                        True,
                    )
            continue

        for line in block.splitlines():
            if "结算依据" not in line:
                continue
            for match in ANCHOR_RE.finditer(line):
                add_anchor(
                    ruler,
                    match.group("anchor"),
                    _normalize_grade(match.group("result")),
                    match.group("difficulty"),
                )
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
        "search_only_strategic": 0,
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


def _bind_ref(mapping: dict[str, str], ref: Any, battle_id: str, label: str) -> None:
    ref_text = str(ref or "").strip()
    if not ref_text:
        return
    prior = mapping.get(ref_text)
    if prior and prior != battle_id:
        raise ValueError(f"{label} maps to two battles: {ref_text}: {prior}, {battle_id}")
    mapping[ref_text] = battle_id


def _remember_ref_candidate(candidates: dict[str, set[str]], ref: Any, battle_id: str) -> None:
    ref_text = str(ref or "").strip()
    if ref_text:
        candidates.setdefault(ref_text, set()).add(battle_id)


def _achievement_battle_id(
    achievement: dict[str, Any],
    registry_ref_to_battle: dict[str, str],
) -> str | None:
    # Prefer the most specific public reference. `or` is intentionally not used:
    # a broad campaign_ref can coexist with an exact person/capability reference.
    for key in ("person_command_result_ref", "capability_episode_ref", "campaign_ref"):
        ref = str(achievement.get(key) or "").strip()
        battle_id = registry_ref_to_battle.get(ref)
        if battle_id:
            return battle_id
    return None


def build_indexes(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    battle_manifest = _load(root / BATTLE_MANIFEST)
    battle_rows: list[dict[str, Any]] = []
    match_rows: list[dict[str, Any]] = []
    # Public payload keeps the historical name for compatibility; internally the
    # registry map also knows canonical war_event_id and uniquely addressable
    # campaign_group_ref values.
    result_ref_to_battle: dict[str, str] = {}
    registry_ref_to_battle: dict[str, str] = {}
    group_ref_candidates: dict[str, set[str]] = {}
    seen_battles: set[str] = set()

    for shard in sorted((root / BATTLE_DIR).glob("*.json")):
        payload = _load(shard)
        for record in payload.get("records", []):
            if not isinstance(record, dict):
                continue
            battle_id = str(record.get("war_event_id") or "").strip()
            if not battle_id or battle_id in seen_battles:
                raise ValueError(f"duplicate or missing battle id in {shard}: {battle_id}")
            seen_battles.add(battle_id)
            _bind_ref(registry_ref_to_battle, battle_id, battle_id, "war event ref")
            _remember_ref_candidate(group_ref_candidates, record.get("campaign_group_ref"), battle_id)

            members = record.get("members") or []
            if isinstance(members, dict):
                members = [members]
            if not isinstance(members, list):
                members = []
            member_names: list[str] = []
            member_pairs: dict[str, set[tuple[str, str]]] = {}
            result_refs: list[str] = []
            search_parts = [
                record.get("canonical_label"),
                record.get("observable_result"),
                record.get("source_target_ref"),
                record.get("campaign_group_ref"),
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
                    _bind_ref(result_ref_to_battle, ref, battle_id, "person result ref")
                    _bind_ref(registry_ref_to_battle, ref, battle_id, "person result ref")
                    if ref not in result_refs:
                        result_refs.append(ref)
                search_parts.extend(result_text)
                if member.get("contribution_scope"):
                    search_parts.append(member["contribution_scope"])

            phase_views = record.get("subject_phase_views") or []
            if isinstance(phase_views, dict):
                phase_views = [phase_views]
            if not isinstance(phase_views, list):
                phase_views = []
            for phase in phase_views:
                if not isinstance(phase, dict):
                    continue
                phase_ref = str(phase.get("phase_id") or "").strip()
                if phase_ref:
                    _bind_ref(result_ref_to_battle, phase_ref, battle_id, "subject phase ref")
                    _bind_ref(registry_ref_to_battle, phase_ref, battle_id, "subject phase ref")
                    if phase_ref not in result_refs:
                        result_refs.append(phase_ref)
                _remember_ref_candidate(group_ref_candidates, phase.get("campaign_group_ref"), battle_id)
                for key in ("evaluation_subject_phase", "actual_process", "carry_in", "carry_out", "campaign_group_ref"):
                    if phase.get(key):
                        search_parts.append(phase[key])

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

    # A campaign-group reference is safe for exact routing only when the public
    # registry has one parent dossier for that group. Multi-dossier groups remain
    # deliberately unbound and therefore fall back to search.
    for ref, battle_ids in group_ref_candidates.items():
        if len(battle_ids) == 1:
            battle_id = next(iter(battle_ids))
            _bind_ref(registry_ref_to_battle, ref, battle_id, "unique campaign group ref")

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
                battle_id = _achievement_battle_id(achievement, registry_ref_to_battle)
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
    expected_profiles = int(
        commander_manifest.get("profile_count")
        or payload_meta.get("profile_count")
        or len(commander_rows)
    )
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
        f"strategic-search={stats['search_only_strategic']} "
        f"nonspecific-search={stats['search_only_nonspecific']} "
        f"ambiguous={stats['ambiguous']} unresolved-atomic={stats['unresolved_atomic']}"
    )


if __name__ == "__main__":
    main()
