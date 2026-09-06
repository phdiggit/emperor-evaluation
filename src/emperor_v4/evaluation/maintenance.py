"""Current-snapshot navigation, change impact and focused validation.

No adjudication or historical state is stored by this command. A selected record
is a read scope, not permission to claim full-pool or semantic acceptance.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import yaml

from emperor_v4.evaluation.formal_json_store import load_json, json_read_session, ROUTER_SCHEMA
from emperor_v4.evaluation.formal_settlements import SECOND_ITEM_COMPONENT_PATHS


# Deterministic consumers and semantic projections have different write rules.
DERIVED = {
    "I1": ("composite",), "I2": ("pool", "composite"),
    "I3.D": ("I3",), "I3": ("composite",), "I4": ("composite",),
    "pool": ("composite",),
    **{f"I2.{axis}": ("I2",) for axis in SECOND_ITEM_COMPONENT_PATHS},
}
REVIEW = {
    "I2.A": ("profile.C3", "profile.C5"),
    "I2.B1": ("profile.C3", "profile.C5"),
    "I2.B2": ("profile.C2", "profile.C5"),
    **{f"I2.{axis}": ("profile.M3",) for axis in ("C1", "C2", "C3", "C4")},
    "I1": ("profile.M1", "profile.C1", "profile.M4"),
    "I3": ("profile.M1", "profile.C1"),
    "I4": ("profile.M4",), "I5": ("profile.C5", "profile.M4"),
    "profile.C2": ("profile.C5", "profile.M4"),
    "profile.C5": ("profile.C2", "profile.C3", "profile.M4"),
    **{f"profile.{axis}": ("profile.M4",) for axis in ("M1", "M2", "M3", "C1", "C3")},
}
CHECKS = {
    "I1": "first-item-cost-verify", "I2.A": "second-item-a-verify",
    "I2.B1": "second-item-b1-verify", "I2.B2": "second-item-b2-verify",
    "I3.D": "third-item-d-verify", "I3": "third-item-current-settlement",
    "I4": "fourth-item-a-verify",
    **{f"profile.{axis}": f"profile-{axis.lower()}-verify" for axis in ("M1", "M3", "M4", "C1", "C2", "C3", "C5")},
}
CHECKS.update({
    "I1": "formal-settlements-verify --item first_item",
    "I2": "formal-settlements-verify --item second_item",
    "I4": "formal-settlements-verify --item fourth_item",
    "I5": "formal-settlements-verify --item fifth_item",
    "pool": "canonical-ruler-pool-verify", "composite": "composite-ranking-verify",
    "profile.M2": "profile-current-verify --axis M2",
})
for _axis in SECOND_ITEM_COMPONENT_PATHS:
    CHECKS.setdefault(f"I2.{_axis}", "formal-settlements-verify --item second_item")


def current_entries(root: Path) -> dict[str, Path]:
    project = yaml.safe_load((root / "config/project.yml").read_text(encoding="utf-8"))
    entries = {
        code: root / project["formal_settlements"][key].get("json", project["formal_settlements"][key]["markdown"])
        for code, key in zip(("I1", "I2", "I3", "I4", "I5"), ("first_item", "second_item", "third_item", "fourth_item", "fifth_item"))
    }
    entries.update({f"I2.{axis}": root / path for axis, path in SECOND_ITEM_COMPONENT_PATHS.items()})
    entries["I3.D"] = root / project["formal_settlements"]["third_item"]["d_json"]
    entries.update({f"profile.{axis}": root / entry["json"] for axis, entry in project["profile_assessment"]["settled_axes"].items()})
    entries["pool"] = root / project["canonical_ruler_pool"]["json"]
    entries["composite"] = root / project["scoring_contract"]["composite_ranking_json"]
    return entries


def _rows(payload: dict) -> list[dict]:
    return payload.get("records", payload.get("scores", []))


def _material_ids(row: dict) -> set[str]:
    return {
        str(mid) for key in ("M_positive_profile", "M_mixed_profile", "M_negative_profile")
        for profile in row.get(key, [])
        for mid in (profile.get("material_ids") or [profile.get("material_id")]) if mid
    }


def selected_rulers(root: Path, ruler_ids: list[str], polities: list[str]) -> tuple[set[str], set[str]]:
    pool = load_json(root / "config/common/canonical-ruler-pool.json")
    rows = pool["records"] + pool.get("first_item_outside_candidate_pool", [])
    aliases = {}
    for row in rows:
        ids = {row["ruler_id"], *(row.get("source_item_ids") or {}).values(),
               *((row.get("identity_resolution") or {}).get("legacy_id_refs") or [])}
        for identifier in ids - {None, ""}:
            aliases[identifier] = row
    unknown = set(ruler_ids) - aliases.keys()
    if unknown:
        raise ValueError(f"Unknown ruler IDs: {sorted(unknown)}")
    available = {r["polity"] for r in rows}
    if set(polities) - available:
        raise ValueError(f"Unknown polities: {sorted(set(polities) - available)}")
    chosen = [r for r in rows if (not ruler_ids or r["ruler_id"] in {aliases[i]["ruler_id"] for i in ruler_ids}) and (not polities or r["polity"] in polities)]
    if not chosen:
        raise ValueError("The ruler and polity filters have no intersection")
    selected_ids = {identifier for identifier, r in aliases.items() if r in chosen}
    return selected_ids, {r["polity"] for r in chosen}


def _load_selected(path: Path, ids: set[str], polities: set[str], scoped: bool) -> list[dict]:
    if path.suffix != ".json":
        from emperor_v4.evaluation.first_item_markdown_settlement import load_first_item_markdown_settlement
        root = path.parents[3]
        pool = load_json(root / "config/common/canonical-ruler-pool.json")
        by_name = {}
        for row in pool["records"] + pool.get("first_item_outside_candidate_pool", []):
            for name in {row["ruler_name"], (row.get("source_item_names") or {}).get("first_item")} - {None}:
                by_name[name] = row
        rows = []
        for source in load_first_item_markdown_settlement(root, validate_cost=False):
            identity = by_name[source["name"]]
            if not scoped or identity["ruler_id"] in ids:
                rows.append({**source, "ruler_id": identity["ruler_id"], "ruler_name": identity["ruler_name"]})
        return rows
    raw = json.loads(path.read_text(encoding="utf-8"))
    if scoped and raw.get("schema_version") == ROUTER_SCHEMA:
        available = {r["polity"] for r in raw["routes"]}
        selected = sorted(available & polities)
        if not selected:
            return []
        payload = load_json(path, polities=selected)
    else:
        payload = load_json(path)
    return [row for row in _rows(payload) if not scoped or row.get("ruler_id") in ids]


@json_read_session()
def inspect(root: Path, components: list[str], ruler_ids: list[str], polities: list[str]) -> dict[str, Any]:
    entries = current_entries(root)
    if set(components) - entries.keys():
        raise ValueError(f"Unknown components: {sorted(set(components) - entries.keys())}")
    ids, selected_polities = selected_rulers(root, ruler_ids, polities)
    scoped = bool(ruler_ids or polities)
    derived = set()
    pending = list(components)
    while pending:
        for target in DERIVED.get(pending.pop(), ()):
            if target not in derived:
                derived.add(target)
                pending.append(target)
    review = {target for source in set(components) | derived for target in REVIEW.get(source, ())}
    affected = set(components) | derived | review
    selected = {key: _load_selected(entries[key], ids, selected_polities, scoped) for key in sorted(affected)}
    gaps = []
    if "profile.C2" in affected:
        b2 = {r["ruler_id"]: r for r in _load_selected(entries["I2.B2"], ids, selected_polities, scoped)}
        high_path = entries["profile.C2"].parent / "21-C2高档学习周期与横向校准复核.json"
        high = load_json(high_path)
        for row in high["candidate_reviews"]:
            if row["ruler_id"] not in b2:
                continue
            reviewed = {d["material_id"] for d in row["b2_material_disposition_review"]}
            missing = _material_ids(b2[row["ruler_id"]]) - reviewed
            if missing:
                gaps.append({"component": "profile.C2", "ruler_id": row["ruler_id"], "missing_material_ids": sorted(missing)})
    check_components = sorted(set(components))
    commands = list(dict.fromkeys(CHECKS[key] for key in check_components if key in CHECKS))
    return {
        "status": "REVIEW_REQUIRED" if gaps else "PLAN_READY",
        "scope": {"components": components, "ruler_ids": ruler_ids, "polities": polities},
        "selected_records": {key: [{"ruler_id": r.get("ruler_id"), "ruler_name": r.get("ruler_name")} for r in rows] for key, rows in selected.items()},
        "formal_sources": {key: entries[key].relative_to(root).as_posix() for key in sorted(affected)},
        "derived_consumers": sorted(derived),
        "semantic_review_consumers": sorted(review),
        "current_link_gaps": gaps,
        "validation_commands": commands,
        "related_validation_commands": list(dict.fromkeys(CHECKS[key] for key in sorted(review) if key in CHECKS)),
        "downstream_validation_commands": list(dict.fromkeys(CHECKS[key] for key in sorted(derived) if key in CHECKS)),
        "validation_granularity": "B2 and M3 support selected-record contracts and reading-view equality. Other existing validators check their complete component, including global ranking and coverage.",
        "unmapped_component_checks": [key for key in check_components if key not in CHECKS],
        "full_acceptance_command": "formal-settlements-verify",
        "write_policy": "Patch adjudications and their source views locally; use the listed deterministic refresh commands for consumers. Semantic review never changes a grade automatically.",
        "refresh_commands": list(dict.fromkeys(
            (["second-item-totals --write"] if "I2" in derived else [])
            + (["third-item-current-settlement --write"] if "I3" in derived else [])
            + (["canonical-ruler-pool --write"] if "pool" in derived else [])
            + (["composite-ranking --write"] if "composite" in derived else [])
            + [f"profile-markdown --axis {key.split('.')[1]} --write" for key in components if key.startswith("profile.")]
        )),
    }


def verify_profile_current(root: Path, axis: str) -> dict:
    """Common profile contracts; axis-specific semantics use their own verifiers."""
    from emperor_v4.evaluation.profile_markdown import render_profile_markdown
    from emperor_v4.evaluation.profile_m4_settlement import SCORES
    path = current_entries(root)[f"profile.{axis}"]
    payload = load_json(path)
    records = payload["records"]
    pool = load_json(root / "config/common/canonical-ruler-pool.json")
    expected = {r["ruler_id"] for r in pool["records"] if r["pool_status"] == "INCLUDED"}
    if len(records) != len(expected) or {r["ruler_id"] for r in records} != expected:
        raise ValueError(f"Profile {axis} pool coverage mismatch")
    for row in records:
        if row["radar_value"] != row["score_100"] or row["radar_value"] != SCORES[row["axis_grade"]][row["position"]]:
            raise ValueError(f"Profile projection mismatch: {row['ruler_id']}")
        if not row["grade_basis"] or not row["position_basis"] or row["formal_status"] != "FORMAL_CURRENT":
            raise ValueError(f"Profile formal adjudication missing: {row['ruler_id']}")
    if path.with_suffix(".md").read_text(encoding="utf-8") != render_profile_markdown(payload):
        raise ValueError(f"Profile {axis} reading view differs from JSON")
    return {"status": "PASS", "validation_scope": "COMMON_PROFILE_CONTRACTS_NOT_SEMANTIC_ACCEPTANCE", "record_count": len(records)}
