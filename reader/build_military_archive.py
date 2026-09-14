#!/usr/bin/env python3
"""Build lightweight reader indexes over the canonical military registries.

The indexes contain lookup/search metadata only. Battle and commander detail pages
fetch the original public-registry shard at read time, so the reader never owns a
second copy of the adjudication payload.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BATTLE_MANIFEST = Path("docs/公共成果/军事/01-战役登记.json")
BATTLE_DIR = Path("docs/公共成果/军事/01-战役登记")
COMMANDER_MANIFEST = Path("docs/公共成果/军事/02-武将人才等级.json")
COMMANDER_DIR = Path("docs/公共成果/军事/02-武将人才等级")
OUTPUT_DIR = Path("reader/data/military")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=False) + "\n"
    path.write_text(text, encoding="utf-8")


def _period(record: dict[str, Any]) -> str:
    period = record.get("period") or {}
    start = str(period.get("start") or "").strip()
    end = str(period.get("end") or "").strip()
    if start and end and end != start:
        return f"{start}—{end}"
    return start or end


def build_indexes(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    battle_manifest = _load(root / BATTLE_MANIFEST)
    battle_rows: list[dict[str, Any]] = []
    result_ref_to_battle: dict[str, str] = {}
    seen_battles: set[str] = set()

    for shard in sorted((root / BATTLE_DIR).glob("*.json")):
        payload = _load(shard)
        for record in payload.get("records", []):
            battle_id = record.get("war_event_id")
            if not battle_id or battle_id in seen_battles:
                raise ValueError(f"duplicate or missing battle id in {shard}: {battle_id}")
            seen_battles.add(battle_id)
            members = record.get("members") or []
            member_names: list[str] = []
            result_refs: list[str] = []
            for member in members:
                name = str(member.get("actor_name") or "").strip()
                if name and name not in member_names:
                    member_names.append(name)
                for result in member.get("person_command_result") or []:
                    ref = str(result.get("result_ref") or "").strip()
                    if not ref:
                        continue
                    prior = result_ref_to_battle.get(ref)
                    if prior and prior != battle_id:
                        raise ValueError(f"person result ref maps to two battles: {ref}: {prior}, {battle_id}")
                    result_ref_to_battle[ref] = battle_id
                    result_refs.append(ref)
            battle_rows.append({
                "id": battle_id,
                "name": record.get("canonical_label") or record.get("observable_result") or battle_id,
                "dynasty": record.get("dynasty") or "",
                "period": _period(record),
                "result_grade": record.get("campaign_tier"),
                "difficulty_grade": record.get("combat_difficulty"),
                "direction": record.get("result_direction"),
                "members": member_names,
                "result_refs": result_refs,
                "source": shard.relative_to(root).as_posix(),
            })

    expected_battles = int(battle_manifest.get("record_count") or len(battle_rows))
    if len(battle_rows) != expected_battles:
        raise ValueError(f"battle registry count mismatch: {len(battle_rows)} != {expected_battles}")
    battle_rows.sort(key=lambda row: (str(row["dynasty"]), str(row["period"]), str(row["name"]), row["id"]))
    battle_index = {
        "schema_version": "reader-military-battle-index-v1",
        "source_manifest": BATTLE_MANIFEST.as_posix(),
        "record_count": len(battle_rows),
        "records": battle_rows,
        "result_ref_to_battle": dict(sorted(result_ref_to_battle.items())),
    }

    commander_manifest = _load(root / COMMANDER_MANIFEST)
    commander_rows: list[dict[str, Any]] = []
    seen_profiles: set[str] = set()
    for shard in sorted((root / COMMANDER_DIR).glob("*.json")):
        payload = _load(shard)
        for profile in payload.get("profiles", []):
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
    print(f"military archive indexes: {battle_index['record_count']} battles, {commander_index['profile_count']} commanders")


if __name__ == "__main__":
    main()
