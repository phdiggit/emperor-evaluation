from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence
import unicodedata

from emperor_v4.contracts.person_snapshot import (
    PersonProfileSnapshot,
    RulerTeamWindowMember,
    RulerTeamWindowSnapshot,
)


SCHEMA_VERSION = "v3-team-window-promotion-package-v1"
PROMOTION_POLICY_VERSION = "v3-team-window-promotion-v1"


def _stable_hash(value: object) -> str:
    rendered = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return sha256(rendered.encode("utf-8")).hexdigest()


def _text(value: object) -> str:
    return str(value or "").strip()


def _worklists(
    value: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, (str, bytes)) or any(
        not isinstance(item, Mapping) for item in value
    ):
        raise ValueError("team worklists 必须是对象或对象数组")
    return list(value)


def _profile(value: PersonProfileSnapshot | Mapping[str, Any]) -> PersonProfileSnapshot:
    if isinstance(value, PersonProfileSnapshot):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("人物画像必须是 PersonProfileSnapshot 或对象")
    fields = PersonProfileSnapshot.__dataclass_fields__
    payload = {name: value[name] for name in fields if name in value}
    for name in ("capability_domains", "lineage_refs"):
        if name in payload:
            payload[name] = tuple(payload[name])
    return PersonProfileSnapshot(**payload)


def _split_window(value: object) -> tuple[str, str]:
    rendered = _text(value)
    for separator in ("—", "–", "至", "~", "～"):
        if separator in rendered:
            start, end = rendered.split(separator, 1)
            if _text(start) and _text(end):
                return _text(start), _text(end)
    raise ValueError(f"evaluation_window 无法解析: {rendered or '<empty>'}")


def _candidate_ruler_ref(ruler: str) -> str:
    normalized = "".join(unicodedata.normalize("NFKC", ruler).split()).casefold()
    return "RULER-NAME-CANDIDATE-" + sha256(normalized.encode("utf-8")).hexdigest()[:12].upper()


def _profile_index(
    profiles_by_name: Mapping[str, PersonProfileSnapshot | Mapping[str, Any]],
) -> tuple[dict[str, PersonProfileSnapshot], dict[str, str]]:
    profiles: dict[str, PersonProfileSnapshot] = {}
    invalid: dict[str, str] = {}
    seen_keys: dict[tuple[str, str], str] = {}
    for raw_name, value in profiles_by_name.items():
        name = _text(raw_name)
        if not name:
            raise ValueError("profiles_by_name 不得包含空姓名")
        try:
            profile = _profile(value)
        except (KeyError, TypeError, ValueError) as exc:
            invalid[name] = str(exc)
            continue
        key = (profile.profile_ref, profile.snapshot_version)
        previous = seen_keys.get(key)
        if previous is not None and previous != profile.semantic_fingerprint:
            invalid[name] = "同一 profile_ref + snapshot_version 对应不同内容"
            continue
        seen_keys[key] = profile.semantic_fingerprint
        profiles[name] = profile
    return profiles, invalid


def build_v3_team_window_promotion_package(
    team_worklists: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    profiles_by_name: Mapping[str, PersonProfileSnapshot | Mapping[str, Any]],
    *,
    ruler_refs_by_name: Mapping[str, str] | None = None,
    window_policy_version: str = PROMOTION_POLICY_VERSION,
    roster_version: str = "team-worklist-roster-v1",
) -> dict[str, Any]:
    """Promote frozen team worklist rosters into report-only window snapshots.

    A task is blocked as a whole when any named member lacks a valid, human-frozen
    profile.  Legacy ``person_ref`` and ``profile_ref`` values are deliberately
    replaced by the accepted profile identity; roles, evidence and activity dates
    remain those of the frozen worklist.
    """

    if not _text(window_policy_version) or not _text(roster_version):
        raise ValueError("window_policy_version 与 roster_version 不得为空")
    worklists = _worklists(team_worklists)
    profiles, invalid_profiles = _profile_index(profiles_by_name)
    ruler_refs = ruler_refs_by_name or {}
    items: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()

    for worklist in worklists:
        if worklist.get("rule_code") != "team_building":
            raise ValueError("只允许晋级 team_building worklist")
        tasks = worklist.get("tasks")
        if not isinstance(tasks, Sequence) or isinstance(tasks, (str, bytes)):
            raise ValueError("team worklist tasks 必须是数组")
        task_code = _text(worklist.get("task_code"))
        worklist_sha = _text(worklist.get("worklist_sha256")) or _stable_hash(worklist)
        for task in tasks:
            if not isinstance(task, Mapping):
                raise ValueError("team worklist task 必须是对象")
            unit_ref = _text(task.get("unit_ref"))
            ruler = _text(task.get("ruler"))
            members = task.get("member_set")
            if not unit_ref or not ruler:
                raise ValueError("team task 缺少 unit_ref 或 ruler")
            if not isinstance(members, Sequence) or isinstance(members, (str, bytes)):
                raise ValueError(f"{unit_ref} member_set 必须是数组")
            if any(not isinstance(member, Mapping) for member in members):
                raise ValueError(f"{unit_ref} member_set 只能包含对象")

            member_names = [_text(member.get("person")) for member in members]
            missing = sorted({name for name in member_names if name not in profiles})
            invalid = {
                name: invalid_profiles[name]
                for name in member_names
                if name in invalid_profiles
            }
            if missing:
                status = "blocked_missing_member_profile"
                status_counts[status] += 1
                items.append(
                    {
                        "unit_ref": unit_ref,
                        "ruler": ruler,
                        "gate_status": status,
                        "missing_profile_names": missing,
                        "invalid_profile_reasons": invalid,
                        "team_window_snapshot": None,
                    }
                )
                continue

            capability_not_assessed = sorted(
                {
                    name
                    for name in member_names
                    if not profiles[name].capability_domains
                }
            )
            if capability_not_assessed:
                status = "blocked_missing_member_capability_review"
                status_counts[status] += 1
                items.append(
                    {
                        "unit_ref": unit_ref,
                        "ruler": ruler,
                        "gate_status": status,
                        "missing_profile_names": [],
                        "capability_not_assessed_names": capability_not_assessed,
                        "invalid_profile_reasons": {},
                        "team_window_snapshot": None,
                    }
                )
                continue

            try:
                start, end = _split_window(task.get("evaluation_window"))
                promoted_members = tuple(
                    RulerTeamWindowMember(
                        person_ref=profiles[
                            _text(member.get("person"))
                        ].canonical_person_ref,
                        profile_ref=profiles[_text(member.get("person"))].profile_ref,
                        active_from=_text(member.get("active_from")),
                        active_to=_text(member.get("active_to")),
                        role_families=tuple(member.get("role_families") or ()),
                        evidence_refs=tuple(member.get("evidence_refs") or ()),
                    )
                    for member in members
                )
                profile_versions = sorted(
                    {profiles[name].snapshot_version for name in member_names}
                )
                profile_set_version = "profile-set@" + _stable_hash(profile_versions)[:16]
                ruler_ref = _text(ruler_refs.get(ruler)) or _candidate_ruler_ref(ruler)
                window = RulerTeamWindowSnapshot(
                    window_ref=f"TEAM-WINDOW-{unit_ref}@{window_policy_version}",
                    ruler_ref=ruler_ref,
                    start=start,
                    end=end,
                    date_precision=_text(task.get("date_precision")) or "year",
                    window_policy_version=window_policy_version,
                    roster_version=roster_version,
                    profile_snapshot_version=profile_set_version,
                    members=promoted_members,
                    lineage={
                        "source_task_code": task_code,
                        "source_unit_ref": unit_ref,
                        "source_worklist_sha256": worklist_sha,
                        "promotion_policy_version": PROMOTION_POLICY_VERSION,
                        "profile_versions_sha256": _stable_hash(profile_versions),
                    },
                )
            except (KeyError, TypeError, ValueError) as exc:
                status = "blocked_invalid_window_contract"
                status_counts[status] += 1
                items.append(
                    {
                        "unit_ref": unit_ref,
                        "ruler": ruler,
                        "gate_status": status,
                        "missing_profile_names": [],
                        "invalid_profile_reasons": {"window": str(exc)},
                        "team_window_snapshot": None,
                    }
                )
                continue

            status = "promoted_report_only"
            status_counts[status] += 1
            items.append(
                {
                    "unit_ref": unit_ref,
                    "ruler": ruler,
                    "gate_status": status,
                    "missing_profile_names": [],
                    "invalid_profile_reasons": {},
                    "ruler_ref_is_name_candidate": ruler not in ruler_refs,
                    "team_window_snapshot": asdict(window),
                }
            )

    promoted_count = status_counts["promoted_report_only"]
    package: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "status": (
            "team_windows_promoted_report_only"
            if promoted_count == len(items)
            else "team_window_promotion_partially_blocked"
        ),
        "promotion_policy_version": PROMOTION_POLICY_VERSION,
        "summary": {
            "worklist_count": len(worklists),
            "window_count": len(items),
            "promoted_window_count": promoted_count,
            "blocked_window_count": len(items) - promoted_count,
            "gate_status_counts": dict(sorted(status_counts.items())),
            "database_write_count": 0,
            "model_call_count": 0,
        },
        "items": items,
        "declarations": {
            "mode": "offline_report_only_shadow",
            "formal_v4_fact": False,
            "formal_scoring_allowed": False,
            "legacy_person_or_profile_refs_reused": False,
            "missing_member_profile_allows_partial_window": False,
        },
    }
    package["package_sha256"] = _stable_hash(package)
    return package


def promote_v3_team_windows(
    team_worklists: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    profiles_by_name: Mapping[str, PersonProfileSnapshot | Mapping[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    """Compatibility alias for the pure promotion package builder."""

    return build_v3_team_window_promotion_package(
        team_worklists, profiles_by_name, **kwargs
    )
