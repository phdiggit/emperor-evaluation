from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

from emperor_v4.evaluation.battle_registry_store import (
    load_battle_registry,
    write_battle_registry,
)


CONFIG_PATH = Path("config/third-item/post-tang-third-item-ruler-windows.json")
REGISTRY_PATH = Path("docs/公共成果/军事/01-战役登记.json")
INPUT_SCHEMA = "chronicle-battle-adjudication-v2"
YEAR_RE = re.compile(r"(?<!\d)(1[12]\d{2}|13\d{2}|14\d{2}|15\d{2}|16\d{2})(?!\d)")
VOLUME_RE = re.compile(r"volume-(\d+)\.battle-adjudications(?:\(1\))?\.json$")


def _digest(value: Any) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _years(value: str) -> tuple[int, int] | None:
    years = [int(item) for item in YEAR_RE.findall(value)]
    return (min(years), max(years)) if years else None


def _load_config(workspace_root: Path) -> dict[str, Any]:
    payload = json.loads((workspace_root / CONFIG_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "post-tang-third-item-ruler-windows-v1":
        raise ValueError("南宋至明第三项统治者窗口配置schema错误")
    if payload.get("status") != "CURRENT":
        raise ValueError("南宋至明第三项统治者窗口配置不是当前值")
    return payload


def _source_paths(source_root: Path) -> tuple[list[Path], list[Path]]:
    cards = sorted(
        source_root.glob("volume-*.battle-adjudications*.json"),
        key=lambda path: path.name,
    )
    summaries = sorted(
        source_root.glob("volume-*.source-summary*.md"),
        key=lambda path: path.name,
    )
    return cards, summaries


def _summary_for_card(path: Path) -> Path:
    name = path.name.replace(".battle-adjudications", ".source-summary")
    return path.with_name(name[:-5] + ".md")


def _subject_polity(subject: str, years: tuple[int, int] | None) -> str | None:
    compact = subject.strip().replace(" ", "")
    if compact.startswith("宋江"):
        return None
    if compact.startswith(("南宋", "宋军", "宋方", "宋廷", "宋朝", "宋官军", "宋守军", "宋水军")):
        return "south_song"
    if any(name in compact for name in ("赵构", "赵昚", "赵惇", "赵扩", "赵昀")):
        return "south_song"

    if not compact.startswith(("反元", "元末反元", "红巾")) and compact.startswith(("元", "大元")):
        return "yuan"
    if any(name in compact for name in ("铁木真", "成吉思", "窝阔台", "蒙哥", "忽必烈", "铁穆耳", "爱育黎拔力八达", "妥懽帖睦尔")):
        return "yuan"
    if years is not None and years[1] <= 1259 and compact.startswith("蒙古"):
        if not any(marker in compact for marker in ("乃蛮", "克烈", "札木合", "太赤乌", "蔑儿乞", "塔塔儿")):
            return "yuan"

    if not compact.startswith(("反明", "明升")) and compact.startswith(("明", "大明", "南明")):
        return "ming"
    if compact.startswith(("建文", "弘光", "隆武", "永历")):
        return "ming"
    if any(
        name in compact
        for name in (
            "朱元璋", "朱允炆", "朱棣", "朱瞻基", "朱祁镇", "朱祁钰",
            "朱见深", "朱祐樘", "朱厚照", "朱厚熜", "朱载坖", "朱翊钧",
            "朱由校", "朱由检", "朱由崧", "朱聿键", "朱由榔",
        )
    ):
        return "ming"
    return None


def _bind_ruler(
    subject: str,
    years: tuple[int, int] | None,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    polity = _subject_polity(subject, years)
    if polity is None:
        return {
            "polity": None,
            "ruler_id": None,
            "ruler_name": None,
            "status": "OUTSIDE_TARGET_POLITIES",
            "basis": "主体阶段不属于南宋、元或明评价政权，禁止复制对手轴。",
        }
    if years is None:
        return {
            "polity": polity,
            "ruler_id": None,
            "ruler_name": None,
            "status": "UNRESOLVED_YEAR",
            "basis": "主体政权可识别，但campaign_group没有可核年份，禁止仅按姓名倒灌统治窗口。",
        }
    rulers = list((config.get("polities") or {})[polity]["rulers"])
    candidates = []
    overlaps = []
    for ruler in rulers:
        windows = [tuple(int(value) for value in window) for window in ruler["windows"]]
        if any(start <= years[0] and years[1] <= end for start, end in windows):
            candidates.append(ruler)
        if any(max(start, years[0]) <= min(end, years[1]) for start, end in windows):
            overlaps.append(ruler)
    if len(candidates) == 1:
        ruler = candidates[0]
        return {
            "polity": polity,
            "ruler_id": ruler["ruler_id"],
            "ruler_name": ruler["ruler_name"],
            "status": "BOUND_EXCLUSIVE_GOVERNING_WINDOW",
            "basis": "主体政权和完整年份范围落入唯一显式统治窗口。",
        }
    return {
        "polity": polity,
        "ruler_id": None,
        "ruler_name": None,
        "status": (
            "UNRESOLVED_WINDOW_OVERLAP"
            if overlaps
            else "OUTSIDE_SELECTED_RULER_WINDOWS"
        ),
        "basis": (
            "阶段跨越两个或以上统治窗口，禁止倒灌。"
            if overlaps
            else "阶段年份不属于当前评价名册中的显式统治窗口。"
        ),
        "candidate_ruler_ids": [str(row["ruler_id"]) for row in overlaps],
    }


def _validate_source_set(
    workspace_root: Path,
    partition: str,
    source: Mapping[str, Any],
) -> tuple[Path, list[Path]]:
    root = workspace_root / str(source["source_root"])
    cards, summaries = _source_paths(root)
    all_paths = sorted([*cards, *summaries], key=lambda path: path.name)
    fingerprint = sha256(b"".join(path.read_bytes() for path in all_paths)).hexdigest()
    if len(all_paths) != int(source["source_file_count"]):
        raise ValueError(f"{partition} canonical输入文件数漂移")
    if fingerprint != str(source["source_set_fingerprint"]):
        raise ValueError(f"{partition} canonical输入内容指纹漂移: {fingerprint}")
    if len(cards) != len(summaries):
        raise ValueError(f"{partition}战役卡与通读总结未一一配对")
    return root, cards


def build_post_tang_canonical_phase_records(
    workspace_root: Path,
) -> dict[str, Any]:
    config = _load_config(workspace_root)
    records: list[dict[str, Any]] = []
    withheld: list[dict[str, Any]] = []
    withheld_files: list[dict[str, Any]] = []
    normalized_legacy_files: list[dict[str, Any]] = []
    partition_summaries: dict[str, Any] = {}
    phase_ids: set[str] = set()
    for partition, source in (config.get("source_partitions") or {}).items():
        source_root, paths = _validate_source_set(
            workspace_root, str(partition), source
        )
        card_count = 0
        phase_count = 0
        partition_records: list[dict[str, Any]] = []
        for path in paths:
            match = VOLUME_RE.fullmatch(path.name)
            if match is None:
                raise ValueError(f"canonical战役卡文件名非法: {path}")
            volume = int(match.group(1))
            payload = json.loads(path.read_text(encoding="utf-8"))
            summary_path = _summary_for_card(path)
            if not summary_path.exists():
                raise ValueError(f"canonical战役卡缺少配对总结: {path}")
            raw_cards = list(payload.get("cards") or payload.get("battles") or ())
            raw_phase_count = sum(
                len(card.get("subject_phase_cards") or card.get("subject_phases") or ())
                for card in raw_cards
            )
            declared_schema = payload.get("schema_version") or payload.get("schema")
            if declared_schema not in (INPUT_SCHEMA, "battle-adjudication-v1"):
                card_count += len(raw_cards)
                phase_count += raw_phase_count
                withheld_files.append({
                    "source_partition": partition,
                    "source_file": path.relative_to(workspace_root).as_posix(),
                    "schema_version": payload.get("schema_version") or payload.get("schema"),
                    "card_count": len(raw_cards),
                    "subject_phase_count": raw_phase_count,
                    "reason": "INCOMPATIBLE_CANONICAL_CARD_SCHEMA",
                })
                continue
            if payload.get("schema_version") != INPUT_SCHEMA:
                normalized_legacy_files.append({
                    "source_partition": partition,
                    "source_file": path.relative_to(workspace_root).as_posix(),
                    "schema_version": declared_schema,
                    "card_count": len(raw_cards),
                    "subject_phase_count": raw_phase_count,
                })
            summary_text = summary_path.read_text(encoding="utf-8")
            identity = dict(payload.get("source_identity") or {})
            identity.setdefault("source_unit_id", payload.get("source_unit_id"))
            identity.setdefault("revision_ref", payload.get("revision_ref"))
            for key in ("source_unit_id", "revision_ref"):
                if not str(identity.get(key) or "") or str(identity[key]) not in summary_text:
                    raise ValueError(f"canonical战役卡与总结身份不一致: {path}/{key}")
            source_relative = path.relative_to(workspace_root).as_posix()
            summary_relative = summary_path.relative_to(workspace_root).as_posix()
            for card_index, card in enumerate(raw_cards, start=1):
                card_count += 1
                phases_raw = list(card.get("subject_phase_cards") or ())
                phase_count += len(phases_raw)
                group = str(card.get("campaign_group") or "").strip()
                anchors = [
                    str(value)
                    for value in (
                        card.get("source_anchor_refs")
                        or card.get("source_refs")
                        or ()
                    )
                ]
                if not group or not anchors:
                    withheld.append({
                        "source_partition": partition,
                        "source_file": source_relative,
                        "card_index": card_index,
                        "battle_label": str(card.get("battle_label") or ""),
                        "reason": "MISSING_CAMPAIGN_GROUP_OR_SOURCE_ANCHORS",
                    })
                    continue
                card_years = _years(group)
                token = f"{partition}:{volume}:{card_index}:{group}:{'|'.join(anchors)}"
                event_id = "WAR-CARD-" + sha256(token.encode("utf-8")).hexdigest()[:20].upper()
                phases: list[dict[str, Any]] = []
                for phase_index, raw_phase in enumerate(phases_raw, start=1):
                    phase = dict(raw_phase)
                    subject = str(phase.get("evaluation_subject_phase") or "")
                    if not subject:
                        raise ValueError(f"canonical主体阶段缺少评价主体: {path}#{card_index}/{phase_index}")
                    phase_id = f"{event_id}-P{phase_index:02d}"
                    if phase_id in phase_ids:
                        raise ValueError(f"canonical主体阶段ID重复: {phase_id}")
                    phase_ids.add(phase_id)
                    phase.update({
                        "phase_id": phase_id,
                        "source_partition": partition,
                        "campaign_group_ref": group,
                        "ruler_binding": _bind_ruler(subject, card_years, config),
                        "source_anchor_refs": list(
                            (phase.get("axis_source_refs") or {}).get("cost_axes")
                            or anchors
                        ),
                    })
                    phases.append(phase)
                record = {
                    "war_event_id": event_id,
                    "dynasty": str(partition),
                    "dynasty_partition": str(partition),
                    "record_level": "chronicle_battle_card",
                    "third_item_phase_container": True,
                    "campaign_group_ref": group,
                    "canonical_label": str(card.get("battle_label") or group),
                    "period": {
                        "start": str(card_years[0]) if card_years else "unknown",
                        "end": str(card_years[1]) if card_years else "unknown",
                    },
                    "public_outcome_registered": False,
                    "disposition": "REGISTERED_THIRD_ITEM_SUBJECT_PHASE_CONTAINER",
                    "source_lineage": {
                        "source_card_ids": [
                            f"{identity['source_unit_id']}#CARD-{card_index:03d}"
                        ],
                        "source_files": [source_relative, summary_relative],
                        "source_revision_refs": [str(identity["revision_ref"])],
                        "lineage_basis": "canonical战役裁决卡的第三项主体阶段容器；不重复登记公共战果。",
                    },
                    "source_refs": anchors,
                    "source_quotes": list(card.get("source_quotes") or ()),
                    "subject_phase_views": phases,
                    "subject_phase_count": len(phases),
                    "non_battle_disposition": card.get("non_battle_disposition"),
                    "contract_adjudication": True,
                    "post_tang_evidence_lower_bound": False,
                    "limitations": [
                        "只供第三项按主体阶段消费；不得与同一公共campaign成果重复计数。",
                        "来源分区不等于主体政权，皇帝归责只读取显式ruler_binding。",
                    ],
                }
                records.append(record)
                partition_records.append(record)
        if card_count != int(source["battle_card_count"]):
            raise ValueError(f"{partition} canonical战役卡数量漂移: {card_count}")
        if phase_count != int(source["subject_phase_count"]):
            raise ValueError(f"{partition} canonical主体阶段数量漂移: {phase_count}")
        partition_withheld_files = [
            row for row in withheld_files if row["source_partition"] == partition
        ]
        partition_withheld_cards = [
            row for row in withheld if row["source_partition"] == partition
        ]
        partition_normalized_files = [
            row
            for row in normalized_legacy_files
            if row["source_partition"] == partition
        ]
        if len(partition_withheld_files) != int(
            source.get("known_incompatible_file_count") or 0
        ):
            raise ValueError(f"{partition}不兼容canonical文件数量漂移")
        if len(partition_withheld_cards) != int(
            source.get("known_missing_campaign_group_count") or 0
        ):
            raise ValueError(f"{partition}缺失campaign_group卡数量漂移")
        if len(partition_normalized_files) != int(
            source.get("known_legacy_schema_file_count") or 0
        ):
            raise ValueError(f"{partition}旧schema兼容文件数量漂移")
        statuses = Counter(
            str((phase.get("ruler_binding") or {}).get("status") or "UNKNOWN")
            for record in partition_records
            for phase in record.get("subject_phase_views") or ()
        )
        partition_summaries[str(partition)] = {
            "source_file_count": int(source["source_file_count"]),
            "battle_card_count": card_count,
            "promoted_container_count": len(partition_records),
            "subject_phase_count": phase_count,
            "binding_status_counts": dict(sorted(statuses.items())),
            "withheld_incompatible_file_count": len(partition_withheld_files),
            "normalized_legacy_file_count": len(partition_normalized_files),
            "withheld_invalid_card_count": len(partition_withheld_cards),
        }
    return {
        "schema_version": "post-tang-canonical-phase-promotion-v1",
        "source_config": CONFIG_PATH.as_posix(),
        "source_partitions": partition_summaries,
        "record_count": len(records),
        "subject_phase_count": sum(
            len(record.get("subject_phase_views") or ()) for record in records
        ),
        "withheld_invalid_card_count": len(withheld),
        "withheld_invalid_cards": withheld,
        "withheld_incompatible_file_count": len(withheld_files),
        "withheld_incompatible_files": withheld_files,
        "normalized_legacy_file_count": len(normalized_legacy_files),
        "normalized_legacy_files": normalized_legacy_files,
        "records": records,
        "semantic_fingerprint": _digest({
            "records": records,
            "withheld": withheld,
            "withheld_files": withheld_files,
            "normalized_legacy_files": normalized_legacy_files,
        }),
    }


def promote_post_tang_canonical_phase_records(
    registry: Mapping[str, Any],
    workspace_root: Path,
) -> dict[str, Any]:
    promotion = build_post_tang_canonical_phase_records(workspace_root)
    current = dict(registry)
    target_partitions = set(promotion["source_partitions"])
    current["records"] = [
        dict(record)
        for record in registry.get("records") or ()
        if not record.get("third_item_phase_container")
        or str(record.get("dynasty_partition") or "") not in target_partitions
    ] + list(promotion["records"])
    current["post_tang_canonical_phase_promotion"] = {
        key: value for key, value in promotion.items() if key != "records"
    }
    current["public_outcome_count"] = sum(
        bool(record.get("public_outcome_registered"))
        for record in current["records"]
    )
    current["pending_count"] = sum(
        bool(record.get("public_outcome_registered"))
        and record.get("command_status") == "PERSON_DETAIL_PENDING"
        for record in current["records"]
    )
    current["disposition_counts"] = dict(sorted(Counter(
        str(record.get("disposition")) for record in current["records"]
    ).items()))
    current["semantic_fingerprint"] = _digest({
        key: value for key, value in current.items() if key != "semantic_fingerprint"
    })
    return current


def build_post_tang_canonical_binding_audit(
    registry: Mapping[str, Any],
) -> dict[str, Any]:
    records = [
        record for record in registry.get("records") or ()
        if record.get("third_item_phase_container")
    ]
    phases = [
        phase for record in records for phase in record.get("subject_phase_views") or ()
    ]
    status_counts = Counter(
        str((phase.get("ruler_binding") or {}).get("status") or "UNKNOWN")
        for phase in phases
    )
    ruler_counts = Counter(
        str((phase.get("ruler_binding") or {}).get("ruler_name"))
        for phase in phases
        if (phase.get("ruler_binding") or {}).get("ruler_name")
    )
    return {
        "record_count": len(records),
        "subject_phase_count": len(phases),
        "binding_status_counts": dict(sorted(status_counts.items())),
        "bound_phase_counts": dict(sorted(ruler_counts.items())),
        "bound_phase_count": sum(ruler_counts.values()),
        "duplicate_phase_id_count": len(phases)
        - len({str(phase.get("phase_id")) for phase in phases}),
    }


def write_post_tang_canonical_phase_records(
    workspace_root: Path,
) -> dict[str, Any]:
    path = workspace_root / REGISTRY_PATH
    registry = load_battle_registry(path)
    promoted = promote_post_tang_canonical_phase_records(registry, workspace_root)
    write_battle_registry(path, promoted)
    return build_post_tang_canonical_binding_audit(promoted)
