from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import time
from typing import Any, Iterable, Mapping, Sequence

from emperor_v4.evaluation.battle_registry_store import (
    load_battle_registry,
    write_battle_registry,
)
from emperor_v4.evaluation.talent_registry_store import load_talent_registry
from emperor_v4.evaluation.post_tang_third_item_consumption import (
    iter_post_tang_bound_cycles,
)
from emperor_v4.evaluation.third_item_d_settlement import (
    verify_third_item_d_formal_settlement,
)


SOURCE_ROOT = Path("docs/史料通读产物/五代十国/资治通鉴")
REGISTRY_PATH = Path("docs/公共成果/军事/01-战役登记.json")
REGISTRY_MARKDOWN_PATH = Path("docs/公共成果/军事/01-战役登记.md")
ADJUDICATION_PATH = Path("config/third-item/five-dynasties-third-item-adjudications.json")
AB_PATH = Path("docs/评分结算/第三项军事与边疆净收益/国防安全/01-皇帝AB项正式结算.json")
C_PATH = Path("docs/评分结算/第三项军事与边疆净收益/军事体系有效性/01-皇帝C项正式结算.json")
D_PATH = Path("docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json")
FORMAL_PATH = Path("docs/评分结算/第三项军事与边疆净收益/02-第三项正式结算.json")
QIN_TANG_BATTLE_INDEX_PATH = Path("docs/史料通读产物/唐以前编年/00-战争卡审计索引.json")
QIN_TANG_D_DIRECTION_PATH = Path("config/third-item/qin-tang-d-cycle-direction-adjudications.json")
FIRST_ITEM_C_WINDOWS_PATH = Path("config/first-item/first-item-c-acquisition-windows.json")
FIRST_ITEM_C_SETTLEMENT_PATH = Path(
    "docs/评分结算/第一项创业与政权取得能力/军事夺取能力/01-第一项C军事夺取能力结算.json"
)
FIRST_ITEM_A_COMPETITIVE_LANDSCAPES_PATH = Path(
    "config/first-item/first-item-a-competitive-landscapes.json"
)
AB_HANDOFF_ADJUDICATION_PATH = Path("config/third-item/third-item-ab-handoff-adjudications.json")
C_OUTCOME_ADJUDICATION_PATH = Path("config/third-item/third-item-c-outcome-adjudications.json")
MILITARY_TALENT_REGISTRY_PATH = Path("docs/公共成果/军事/02-武将人才等级.json")
INPUT_SCHEMA = "chronicle-battle-adjudication-v2"
REGISTRY_SCHEMA = "battle-parent-contract-registry-v5"
RETIRED_STALE_FIVE_DYNASTIES_RECORD_COUNT = 433


PARENT_CYCLE_BENEFIT_STRENGTH: dict[str, tuple[int, ...]] = {
    "SB": (0, 1, 2, 3, 5, 8),
    "BCP": (0, 1, 2, 3, 4, 6),
    "WR": (0, 1, 1, 2, 3, 4),
}


def _write_text_atomic(path: Path, text: str) -> None:
    temporary = path.with_name(f".{path.name}.write-tmp")
    try:
        for attempt in range(3):
            try:
                temporary.write_text(text, encoding="utf-8")
                temporary.replace(path)
                return
            except OSError:
                if attempt == 2:
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        if temporary.exists():
            temporary.unlink()


RULER_WINDOWS: tuple[dict[str, Any], ...] = (
    {"ruler_id": "RULER-FD-ZHU-WEN", "ruler_name": "朱温", "polity": "后梁", "start": 907, "end": 912, "aliases": ("梁太祖",)},
    {"ruler_id": "RULER-FD-ZHU-YOUZHEN", "ruler_name": "朱友贞", "polity": "后梁", "start": 913, "end": 923, "aliases": ("梁末帝",)},
    {"ruler_id": "RULER-FD-LI-CUNXU", "ruler_name": "李存勖", "polity": "后唐", "start": 923, "end": 926, "aliases": ("唐庄宗", "后唐庄宗", "庄宗")},
    {"ruler_id": "RULER-FD-LI-SIYUAN", "ruler_name": "李嗣源", "polity": "后唐", "start": 926, "end": 933, "aliases": ("唐明宗", "后唐明宗", "明宗")},
    {"ruler_id": "RULER-FD-SHI-JINGTANG", "ruler_name": "石敬瑭", "polity": "后晋", "start": 936, "end": 942, "aliases": ("晋高祖", "后晋高祖")},
    {"ruler_id": "RULER-FD-GUO-WEI", "ruler_name": "郭威", "polity": "后周", "start": 951, "end": 954, "aliases": ("周太祖", "后周太祖")},
    {"ruler_id": "RULER-FD-CHAI-RONG", "ruler_name": "柴荣", "polity": "后周", "start": 954, "end": 959, "aliases": ("周世宗", "后周世宗", "世宗")},
    {"ruler_id": "RULER-FD-LI-BIAN", "ruler_name": "李昪", "polity": "南唐", "start": 937, "end": 943, "aliases": ("南唐烈祖", "烈祖")},
    {"ruler_id": "RULER-FD-LI-YU", "ruler_name": "李煜", "polity": "南唐", "start": 961, "end": 975, "aliases": ("南唐后主",)},
    {"ruler_id": "RULER-FD-WANG-JIAN", "ruler_name": "王建", "polity": "前蜀", "start": 907, "end": 918, "aliases": ("前蜀高祖", "蜀高祖")},
    {"ruler_id": "RULER-FD-MENG-CHANG", "ruler_name": "孟昶", "polity": "后蜀", "start": 934, "end": 965, "aliases": ("后蜀后主",)},
    {"ruler_id": "RULER-FD-LIU-YAN", "ruler_name": "刘龑", "polity": "南汉", "start": 917, "end": 942, "aliases": ("南汉高祖",)},
)

VOLUME_YEAR_RANGES = {
    263: (902, 903), 264: (902, 904), 265: (903, 906), 266: (906, 908),
    267: (907, 911), 268: (910, 913), 269: (913, 917), 270: (916, 919),
    271: (919, 922), 272: (921, 923), 273: (921, 925), 274: (925, 926),
    275: (921, 927), 276: (926, 929), 277: (930, 932), 278: (932, 934),
    279: (934, 935), 280: (935, 936), 281: (937, 938), 282: (939, 942),
    283: (942, 944), 284: (944, 945), 285: (945, 946), 286: (946, 947),
    287: (947, 948), 288: (948, 950), 289: (950, 950), 290: (950, 952),
    291: (952, 954), 292: (954, 956), 293: (955, 957), 294: (955, 959),
}

POLITY_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("后梁", ("后梁", "朱全忠", "朱温", "梁军", "汴军", "梁政权", "梁中央")),
    ("后唐", ("后唐", "李存勖", "李嗣源", "晋王", "晋军")),
    ("后晋", ("后晋", "石敬瑭")),
    ("后汉", ("后汉", "刘知远")),
    ("后周", ("后周", "郭威", "柴荣", "世宗")),
    ("南唐", ("南唐",)),
    ("前蜀", ("前蜀", "王建—西川", "王建军")),
    ("后蜀", ("后蜀", "孟昶")),
    ("南汉", ("南汉", "刘岩", "刘龑", "岭南军", "清海刘")),
    ("吴越", ("吴越", "钱镠", "两浙军")),
    ("吴", ("吴军", "淮南军", "杨行密")),
    ("楚", ("楚军", "楚政权", "湖南军", "马殷")),
    ("闽", ("闽军", "闽王", "王延政", "王审知")),
    ("荆南", ("荆南", "高季昌", "高季兴")),
    ("契丹", ("契丹",)),
    ("北汉", ("北汉",)),
)


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _grade_number(value: object, prefix: str) -> int | None:
    match = re.fullmatch(rf"{prefix}(\d)(?:估)?", str(value or ""))
    return int(match.group(1)) if match else None


def _embedded_grade_number(value: object, prefix: str) -> int | None:
    direct = _grade_number(value, prefix)
    if direct is not None:
        return direct
    match = re.search(
        rf"(?<![A-Z]){prefix}(\d)(?:估)?(?!\d)",
        str(value or ""),
    )
    return int(match.group(1)) if match else None


def _card_year_range(campaign_group: str, volume: int) -> tuple[int, int]:
    years = [
        int(value)
        for value in re.findall(r"(?<!\d)(0?[89]\d{2}|1\d{3})(?!\d)", campaign_group)
    ]
    if years:
        return min(years), max(years)
    return VOLUME_YEAR_RANGES[volume]


def _infer_polity(text: str, year_range: tuple[int, int]) -> str | None:
    if text.startswith("梁"):
        return "后梁"
    if text.startswith("晋") and year_range[1] < 923:
        return "后唐"
    for polity, markers in POLITY_MARKERS:
        if any(marker in text for marker in markers):
            if polity == "后唐" and "晋军" in text and year_range[1] < 923:
                return "后唐"
            return polity
    return None


def _bind_ruler(
    phase: Mapping[str, Any], year_range: tuple[int, int]
) -> dict[str, Any]:
    subject_text = str(phase.get("evaluation_subject_phase") or "")
    polity = _infer_polity(str(phase.get("evaluation_subject_phase") or ""), year_range)
    explicit = [
        ruler
        for ruler in RULER_WINDOWS
        if any(alias in subject_text for alias in ruler["aliases"])
        and max(ruler["start"], year_range[0]) <= min(ruler["end"], year_range[1])
    ]
    if len(explicit) == 1:
        ruler = explicit[0]
        if ruler["polity"] == polity or polity is None:
            return {
                "polity": ruler["polity"],
                "ruler_id": ruler["ruler_id"],
                "ruler_name": ruler["ruler_name"],
                "status": "BOUND_EXPLICIT_RULER",
                "basis": "主体阶段正文显式出现本皇帝名号；只绑定该主体阶段。",
            }
    candidates = [
        ruler
        for ruler in RULER_WINDOWS
        if ruler["polity"] == polity
        and ruler["start"] <= year_range[0]
        and year_range[1] <= ruler["end"]
    ]
    if len(candidates) == 1:
        ruler = candidates[0]
        boundary = year_range[0] in {ruler["start"], ruler["end"]} or year_range[1] in {ruler["start"], ruler["end"]}
        return {
            "polity": polity,
            "ruler_id": ruler["ruler_id"],
            "ruler_name": ruler["ruler_name"],
            "status": "BOUND_YEAR_WINDOW_BOUNDARY" if boundary else "BOUND_YEAR_WINDOW",
            "basis": "主体政权与卡片年代完全落入在位窗口；边界年不含月日时单独标记复核。" if boundary else "主体政权与卡片年代完整落入在位窗口。",
        }
    overlap = [
        ruler
        for ruler in RULER_WINDOWS
        if ruler["polity"] == polity
        and max(ruler["start"], year_range[0]) <= min(ruler["end"], year_range[1])
    ]
    if len(overlap) == 1:
        ruler = overlap[0]
        return {
            "polity": polity,
            "ruler_id": ruler["ruler_id"],
            "ruler_name": ruler["ruler_name"],
            "status": "BOUND_REVIEWED_VOLUME_FALLBACK",
            "basis": (
                "战役群年代只能由卷级范围定位，但该主体政权在范围内只有一个合法统治窗口；"
                "按唯一候选绑定，不把对手或继任阶段倒灌。"
            ),
        }
    return {
        "polity": polity,
        "ruler_id": None,
        "ruler_name": None,
        "status": "UNRESOLVED_WINDOW_OVERLAP" if overlap else "OUTSIDE_CONFIGURED_RULER_WINDOWS",
        "basis": "卡片年代跨越在位边界且主体阶段未显式给出皇帝，禁止倒灌。" if overlap else "主体不属于本轮12人或年代不在其统治窗口。",
        "candidate_ruler_ids": [ruler["ruler_id"] for ruler in overlap],
    }


def _read_source_pair(path: Path, workspace_root: Path) -> tuple[dict[str, Any], Path]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != INPUT_SCHEMA:
        raise ValueError(f"五代十国战役裁决卡schema错误: {path}")
    volume = int(re.search(r"volume-(\d+)\.", path.name).group(1))
    summary = path.with_name(f"volume-{volume}.source-summary.md")
    summary_text = summary.read_text(encoding="utf-8")
    identity = payload.get("source_identity") or {}
    required = (
        str(payload.get("source_volume") or ""),
        str(identity.get("source_unit_id") or ""),
        str(identity.get("revision_ref") or ""),
        str(identity.get("raw_sha256") or ""),
    )
    if not all(required) or not all(value in summary_text for value in required[1:]):
        raise ValueError(f"五代十国战役卡与通读总结source identity不匹配: {path}")
    return payload, summary.relative_to(workspace_root)


def _load_adjudication_payload(workspace_root: Path) -> dict[str, Any]:
    payload = json.loads((workspace_root / ADJUDICATION_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "five-dynasties-third-item-adjudications-v3":
        raise ValueError("五代十国第三项裁决配置schema错误")
    return payload


def build_five_dynasties_supplement_records(workspace_root: Path) -> list[dict[str, Any]]:
    """Build narrowly scoped post-959 terminal records from tracked primary-source adjudications."""
    payload = _load_adjudication_payload(workspace_root)
    records: list[dict[str, Any]] = []
    for item in payload.get("supplemental_records") or ():
        source = item["source_identity"]
        required_source = ("source_unit_id", "revision_ref", "raw_sha256", "text_sha256", "source_url")
        if not all(source.get(key) for key in required_source):
            raise ValueError(f"补充裁决缺少固定史源身份: {item.get('war_event_id')}")
        phases = []
        for index, raw_phase in enumerate(item.get("subject_phase_views") or (), start=1):
            phase = dict(raw_phase)
            for key in (
                "evaluation_subject_phase", "subject_role", "actual_process", "cost_axes",
                "strategic_security", "material_return", "border_control", "phase_return_class",
                "founding_startup_ledger", "ruler_binding",
            ):
                if key not in phase:
                    raise ValueError(f"补充裁决主体阶段缺少{key}: {item['war_event_id']}")
            phase["phase_id"] = f"{item['war_event_id']}-P{index:02d}"
            phase["campaign_group_ref"] = item["campaign_group_ref"]
            phase["polity_binding"] = item["polity"]
            phase["ruler_binding"] = {
                "polity": item["polity"],
                **dict(phase["ruler_binding"]),
            }
            phase["source_anchor_refs"] = list(item["source_refs"])
            phases.append(phase)
        if not phases:
            raise ValueError(f"补充裁决没有主体阶段: {item['war_event_id']}")
        records.append(
            {
                "war_event_id": item["war_event_id"],
                "dynasty": "五代十国",
                "dynasty_partition": "five_dynasties",
                "record_level": "targeted_primary_source_supplement",
                "campaign_group_ref": item["campaign_group_ref"],
                "canonical_label": item["canonical_label"],
                "period": dict(item["period"]),
                "public_outcome_registered": True,
                "disposition": "REGISTERED_SUBJECT_PHASE_CONTRACT",
                "source_lineage": {
                    "source_card_ids": [source["source_unit_id"] + "#TARGETED-ADJUDICATION"],
                    "source_files": [ADJUDICATION_PATH.as_posix()],
                    "source_revision_refs": [str(source["revision_ref"])],
                    "source_identity": dict(source),
                    "lineage_basis": "卷294止于959年后的定向缺口补齐；仅保存固定原典身份、短引文和主体阶段裁决，不消费旧唐以后派生登记。",
                },
                "source_refs": list(item["source_refs"]),
                "source_quotes": list(item["source_quotes"]),
                "subject_phase_views": phases,
                "subject_phase_count": len(phases),
                "third_item_phase_container": True,
                "non_battle_disposition": None,
                "wc_grade": None,
                "security_grade": None,
                "contract_adjudication": True,
                "post_tang_evidence_lower_bound": False,
                "limitations": ["定向补充只闭合卷294以后本政权终局；父卡指标不得复制给其他主体。"],
            }
        )
    return records


def build_five_dynasties_battle_records(workspace_root: Path) -> dict[str, Any]:
    source_root = workspace_root / SOURCE_ROOT
    adjudication_paths = sorted(source_root.glob("volume-*.battle-adjudications.json"))
    if len(adjudication_paths) != 32:
        raise ValueError(f"五代十国战役裁决输入应为32卷，实际{len(adjudication_paths)}卷")
    records: list[dict[str, Any]] = []
    phase_ids: set[str] = set()
    for path in adjudication_paths:
        payload, summary_relative = _read_source_pair(path, workspace_root)
        volume = int(re.search(r"volume-(\d+)\.", path.name).group(1))
        source_relative = path.relative_to(workspace_root).as_posix()
        for card_index, card in enumerate(payload.get("cards") or (), start=1):
            campaign_group = str(card.get("campaign_group") or "")
            if not campaign_group:
                raise ValueError(f"战役卡缺少campaign_group: {path}#{card_index}")
            anchors = [str(value) for value in card.get("source_anchor_refs") or ()]
            if not anchors:
                raise ValueError(f"战役卡缺少source_anchor_refs: {path}#{card_index}")
            year_range = _card_year_range(campaign_group, volume)
            card_token = f"{volume}:{card_index}:{campaign_group}:{'|'.join(anchors)}"
            war_event_id = "WAR-FD-" + sha256(card_token.encode("utf-8")).hexdigest()[:20].upper()
            phase_views: list[dict[str, Any]] = []
            for phase_index, raw_phase in enumerate(card.get("subject_phase_cards") or (), start=1):
                phase = dict(raw_phase)
                phase_id = f"{war_event_id}-P{phase_index:02d}"
                if phase_id in phase_ids:
                    raise ValueError(f"主体阶段ID重复: {phase_id}")
                phase_ids.add(phase_id)
                binding = _bind_ruler(phase, year_range)
                phase_views.append(
                    {
                        "phase_id": phase_id,
                        "evaluation_subject_phase": phase["evaluation_subject_phase"],
                        "subject_role": phase["subject_role"],
                        "actual_process": phase["actual_process"],
                        "cost_axes": dict(phase["cost_axes"]),
                        "P_inference": dict(phase.get("P_inference") or {}),
                        "cost_evidence": dict(phase.get("cost_evidence") or {}),
                        "strategic_security": phase["strategic_security"],
                        "material_return": phase["material_return"],
                        "border_control": dict(phase["border_control"]),
                        "phase_return_class": phase["phase_return_class"],
                        "founding_startup_ledger": dict(phase["founding_startup_ledger"]),
                        "carry_in": phase.get("carry_in"),
                        "carry_out": phase.get("carry_out"),
                        "campaign_group_ref": campaign_group,
                        "polity_binding": binding["polity"],
                        "ruler_binding": binding,
                        "source_anchor_refs": anchors,
                    }
                )
            records.append(
                {
                    "war_event_id": war_event_id,
                    "dynasty": "五代十国",
                    "dynasty_partition": "five_dynasties",
                    "record_level": "chronicle_battle_card",
                    "campaign_group_ref": campaign_group,
                    "canonical_label": card["battle_label"],
                    "period": {"start": str(year_range[0]), "end": str(year_range[1])},
                    "public_outcome_registered": True,
                    "disposition": "REGISTERED_SUBJECT_PHASE_CONTRACT",
                    "source_lineage": {
                        "source_card_ids": [f"{payload['source_identity']['source_unit_id']}#CARD-{card_index:03d}"],
                        "source_files": [source_relative, summary_relative.as_posix()],
                        "source_revision_refs": [str(payload["source_identity"]["revision_ref"])],
                        "lineage_basis": "五代十国32卷配对通读总结与战役裁决卡；父卡只作容器，计分消费主体阶段。",
                    },
                    "source_refs": anchors,
                    "source_quotes": list(card.get("source_quotes") or ()),
                    "subject_phase_views": phase_views,
                    "subject_phase_count": len(phase_views),
                    "third_item_phase_container": True,
                    "non_battle_disposition": card.get("non_battle_disposition"),
                    "wc_grade": None,
                    "security_grade": None,
                    "contract_adjudication": True,
                    "post_tang_evidence_lower_bound": False,
                    "limitations": ["父卡指标不得复制给主体；AB/C/D只读取subject_phase_views。"],
                }
            )
    if len(records) != 521 or len(phase_ids) != 1434:
        raise ValueError(f"五代十国输入覆盖异常: cards={len(records)}, phases={len(phase_ids)}")
    return {
        "schema_version": "five-dynasties-battle-promotion-v1",
        "source_file_count": len(adjudication_paths) * 2,
        "battle_card_count": len(records),
        "campaign_group_count": len({row["campaign_group_ref"] for row in records}),
        "subject_phase_count": len(phase_ids),
        "records": records,
    }


def promote_five_dynasties_battle_registry(
    payload: Mapping[str, Any], workspace_root: Path
) -> dict[str, Any]:
    promotion = build_five_dynasties_battle_records(workspace_root)
    adjudication_payload = _load_adjudication_payload(workspace_root)
    boundary_inclusions = dict(adjudication_payload.get("reviewed_boundary_phase_inclusions") or {})
    binding_overrides = {
        str(phase_id): {
            "ruler_id": str(item["ruler_id"]),
            "reason": str(item["reason"]),
        }
        for item in adjudication_payload.get("reviewed_phase_binding_overrides") or ()
        for phase_id in item.get("phase_ids") or ()
    }
    binding_exclusions = {
        str(phase_id): str(reason)
        for phase_id, reason in (
            adjudication_payload.get("reviewed_phase_binding_exclusions") or {}
        ).items()
    }
    found_boundary_inclusions: set[str] = set()
    found_binding_overrides: set[str] = set()
    found_binding_exclusions: set[str] = set()
    rulers_by_id = {str(item["ruler_id"]): item for item in RULER_WINDOWS}
    for record in promotion["records"]:
        for phase in record.get("subject_phase_views") or ():
            phase_id = str(phase["phase_id"])
            if phase_id in binding_exclusions:
                binding = phase["ruler_binding"]
                if binding.get("status") != "UNRESOLVED_WINDOW_OVERLAP":
                    raise ValueError(f"阶段归责排除不是跨窗口未决阶段: {phase_id}")
                if not binding_exclusions[phase_id].strip():
                    raise ValueError(f"阶段归责排除缺少理由: {phase_id}")
                phase["ruler_binding"] = {
                    "ruler_id": None,
                    "ruler_name": None,
                    "status": "OUTSIDE_FORMAL_REIGN_FOUNDING_PHASE",
                    "basis": binding_exclusions[phase_id],
                    "candidate_ruler_ids": [],
                }
                found_binding_exclusions.add(phase_id)
            if phase_id in binding_overrides:
                override = binding_overrides[phase_id]
                binding = phase["ruler_binding"]
                if binding.get("status") not in {
                    "UNRESOLVED_WINDOW_OVERLAP",
                    "OUTSIDE_CONFIGURED_RULER_WINDOWS",
                }:
                    raise ValueError(f"阶段归责复核覆盖不是跨窗口未决阶段: {phase_id}")
                ruler = rulers_by_id.get(override["ruler_id"])
                candidates = binding.get("candidate_ruler_ids") or ()
                if ruler is None or (
                    candidates and override["ruler_id"] not in candidates
                ):
                    raise ValueError(f"阶段归责复核对象不是合法候选: {phase_id}")
                if not override["reason"].strip():
                    raise ValueError(f"阶段归责复核缺少理由: {phase_id}")
                phase["ruler_binding"] = {
                    "polity": ruler["polity"],
                    "ruler_id": ruler["ruler_id"],
                    "ruler_name": ruler["ruler_name"],
                    "status": "BOUND_REVIEWED_TRANSITION_SLICE",
                    "basis": override["reason"],
                }
                found_binding_overrides.add(phase_id)
            if phase_id not in boundary_inclusions:
                continue
            binding = phase["ruler_binding"]
            if binding.get("status") not in {
                "BOUND_YEAR_WINDOW_BOUNDARY",
                "BOUND_YEAR_WINDOW",
                "BOUND_REVIEWED_VOLUME_FALLBACK",
            }:
                raise ValueError(f"边界阶段复核覆盖不是边界绑定: {phase_id}")
            binding.update(
                {
                    "status": "BOUND_REVIEWED_BOUNDARY",
                    "basis": boundary_inclusions[phase_id],
                }
            )
            found_boundary_inclusions.add(phase_id)
    if found_boundary_inclusions != set(boundary_inclusions):
        raise ValueError(
            f"边界阶段复核引用不存在: {sorted(set(boundary_inclusions) - found_boundary_inclusions)}"
        )
    if found_binding_overrides != set(binding_overrides):
        raise ValueError(
            f"阶段归责复核引用不存在: {sorted(set(binding_overrides) - found_binding_overrides)}"
        )
    if found_binding_exclusions != set(binding_exclusions):
        raise ValueError(
            f"阶段归责排除引用不存在: {sorted(set(binding_exclusions) - found_binding_exclusions)}"
        )
    preserved = [
        dict(row)
        for row in payload.get("records") or ()
        if row.get("dynasty_partition") != "five_dynasties" and row.get("dynasty") != "五代十国"
    ]
    supplements = build_five_dynasties_supplement_records(workspace_root)
    current_partition_count = len(list(payload.get("records") or ())) - len(preserved)
    allowed_partition_counts = {
        RETIRED_STALE_FIVE_DYNASTIES_RECORD_COUNT,
        promotion["battle_card_count"] + len(supplements),
    }
    if current_partition_count not in allowed_partition_counts:
        raise ValueError(f"五代十国公共登记替换范围异常: {current_partition_count}")
    records = preserved + list(promotion["records"]) + supplements
    current_high_difficulty = [
        row for row in records
        if row.get("public_outcome_registered")
        and row.get("combat_difficulty") in {"D3", "D4"}
    ]
    difficulty_review = dict(payload.get("high_difficulty_contract_review_summary") or {})
    difficulty_review.update(
        {
            "current_d3_d4_count": len(current_high_difficulty),
            "current_difficulty_counts": dict(
                sorted(Counter(str(row["combat_difficulty"]) for row in current_high_difficulty).items())
            ),
        }
    )
    current = dict(payload)
    current.update(
        {
            "schema_version": REGISTRY_SCHEMA,
            "scope": "秦至清（五代十国使用主体阶段裁决卡；其余分区维持当前值）",
            "five_dynasties_promotion": {
                key: value for key, value in promotion.items() if key != "records"
            }
            | {
                "supplemental_record_count": len(supplements),
                "reviewed_boundary_phase_inclusion_count": len(boundary_inclusions),
                "promoted_record_count": promotion["battle_card_count"] + len(supplements),
                "retired_stale_record_count": RETIRED_STALE_FIVE_DYNASTIES_RECORD_COUNT,
            },
            "records": records,
            "high_difficulty_contract_review_summary": difficulty_review,
            "public_outcome_count": sum(bool(row.get("public_outcome_registered")) for row in records),
            "pending_count": sum(
                bool(row.get("public_outcome_registered"))
                and row.get("command_status") == "PERSON_DETAIL_PENDING"
                for row in records
            ),
            "disposition_counts": dict(sorted(Counter(str(row.get("disposition")) for row in records).items())),
            "tier_counts": dict(sorted(Counter(str(row["campaign_tier"]) for row in records if row.get("campaign_tier")).items())),
        }
    )
    return current


def iter_bound_cycles(
    registry: Mapping[str, Any], ruler_id: str
) -> list[dict[str, Any]]:
    ruler = next(item for item in RULER_WINDOWS if item["ruler_id"] == ruler_id)
    return iter_post_tang_bound_cycles(
        registry,
        ruler_id,
        ruler_name=str(ruler["ruler_name"]),
        polity=str(ruler["polity"]),
    )


def build_promotion_audit(registry: Mapping[str, Any]) -> dict[str, Any]:
    records = [
        row for row in registry.get("records") or ()
        if row.get("dynasty_partition") == "five_dynasties"
    ]
    phases = [phase for row in records for phase in row.get("subject_phase_views") or ()]
    status_counts = Counter((phase.get("ruler_binding") or {}).get("status") for phase in phases)
    ruler_counts = Counter(
        (phase.get("ruler_binding") or {}).get("ruler_name")
        for phase in phases
        if (phase.get("ruler_binding") or {}).get("ruler_name")
    )
    cycles = {
        ruler["ruler_name"]: len(iter_bound_cycles(registry, ruler["ruler_id"]))
        for ruler in RULER_WINDOWS
    }
    phase_ids = [phase["phase_id"] for phase in phases]
    return {
        "battle_card_count": sum(row.get("record_level") == "chronicle_battle_card" for row in records),
        "supplemental_record_count": sum(row.get("record_level") == "targeted_primary_source_supplement" for row in records),
        "promoted_record_count": len(records),
        "campaign_group_count": len({row["campaign_group_ref"] for row in records}),
        "subject_phase_count": len(phases),
        "duplicate_phase_id_count": len(phase_ids) - len(set(phase_ids)),
        "binding_status_counts": dict(sorted(status_counts.items())),
        "bound_phase_counts": dict(sorted(ruler_counts.items())),
        "deduplicated_cycle_counts": cycles,
        "score_consumed_phase_count": sum(
            count for status, count in status_counts.items()
            if str(status).startswith("BOUND_") and status != "BOUND_YEAR_WINDOW_BOUNDARY"
        ),
        "excluded_boundary_phase_count": status_counts.get("BOUND_YEAR_WINDOW_BOUNDARY", 0),
        "out_of_scope_phase_count": status_counts.get("OUTSIDE_CONFIGURED_RULER_WINDOWS", 0),
        "unmatched_phase_count": status_counts.get("UNRESOLVED_WINDOW_OVERLAP", 0),
        "window_conflict_count": status_counts.get("UNRESOLVED_WINDOW_OVERLAP", 0),
    }


A_STATE_NAMES = {
    "A1": (
        "A1S0_EXISTENTIAL_CRISIS", "A1S1_SEVERE_THREAT", "A1S2_STRATEGIC_DISADVANTAGE",
        "A1S3_CONTESTED_BALANCE", "A1S4_STABLE_ADVANTAGE", "A1S5_DOMINANT_ORDER",
    ),
    "A2": (
        "A2S0_CORE_EXPOSED", "A2S1_BROKEN_BOUNDARY", "A2S2_LOCAL_DEFENSIBLE_POINTS",
        "A2S3_EFFECTIVE_MAIN_BOUNDARY", "A2S4_OVERALL_SECURE_WITH_GAPS", "A2S5_SECURE_STRATEGIC_SYSTEM",
    ),
}
B_RATES = {
    0: {"LOW": 0, "MID": 15, "HIGH": 29},
    1: {"LOW": 30, "MID": 37, "HIGH": 44},
    2: {"LOW": 45, "MID": 52, "HIGH": 59},
    3: {"LOW": 60, "MID": 67, "HIGH": 74},
    4: {"LOW": 75, "MID": 82, "HIGH": 89},
    5: {"LOW": 90, "MID": 95, "HIGH": 100},
}
def _load_adjudications(workspace_root: Path) -> list[dict[str, Any]]:
    payload = _load_adjudication_payload(workspace_root)
    rows = [dict(row) for row in payload.get("adjudications") or ()]
    if [row["ruler_id"] for row in rows] != [row["ruler_id"] for row in RULER_WINDOWS]:
        raise ValueError("五代十国第三项裁决对象或顺序与当前12人窗口不一致")
    return rows


def _cycles_and_refs(registry: Mapping[str, Any], ruler_id: str) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    cycles = iter_bound_cycles(registry, ruler_id)
    event_refs = _unique(ref for cycle in cycles for ref in cycle["war_event_refs"])
    phase_refs = [phase_id for cycle in cycles for phase_id in cycle["phase_ids"]]
    return cycles, event_refs, phase_refs


def _axis_a(axis: str, decision: Mapping[str, Any]) -> dict[str, Any]:
    start = int(decision["start"])
    end = int(decision["end"])
    observed_base = max(0, min(100, 12 * end + 10 * (end - start)))
    if decision.get("score_excluded"):
        raise ValueError(
            f"{axis}宏观状态轨迹不得因第一项战役链归属而整轴排除"
        )
    base = observed_base
    transition = "IMPROVED" if end > start else "WORSENED" if end < start else "STABLE"
    return {
        "start": A_STATE_NAMES[axis][start],
        "end": A_STATE_NAMES[axis][end],
        "transition": transition,
        "transition_attribution": "RULER_REIGN_NET_RESULT",
        "observed_trajectory_value": observed_base,
        "base_trajectory_value": base,
        "ceiling_progress": "NONE",
        "ceiling_progress_refs": [],
        "ceiling_bonus": 0,
        "trajectory_value": base,
        "axis_points": round(base * 0.4, 2),
        "score_exclusion_reason": None,
        "assessment_scope": "OVERALL_FRONTIER_STRATEGIC_SITUATION",
        "reason": _scoped_axis_reason(
            "整体边疆形势", str(decision["reason"])
        ),
    }


def _axis_b(axis: str, decision: Mapping[str, Any]) -> dict[str, Any]:
    grade = int(decision["grade"])
    position = str(decision["position"])
    rate = B_RATES[grade][position]
    max_points = {"B1": 25, "B2": 30, "B4": 25}[axis]
    result = {
        "grade": f"{axis}-{grade}",
        "band_position": position,
        "score_rate": rate,
        "axis_points": round(rate * max_points / 100, 2),
        "assessment_scope": "CONTROL_SCALE_AND_INTENSITY",
        "reason": _scoped_axis_reason(
            "规模与控制强度", str(decision["reason"])
        ),
    }
    if axis == "B1":
        start = float(decision["start_equivalent"])
        end = float(decision["end_equivalent"])
        result.update(
            {
                "raw_net_change": round(end - start, 3),
                "weighted_control_value": round(0.6 * (end - start) + 0.4 * end, 3),
            }
        )
    return result


def _scoped_axis_reason(scope_label: str, reason: str) -> str:
    prefix = f"{scope_label}："
    return reason if reason.startswith(prefix) else f"{prefix}{reason}"


CONTROL_CONTRIBUTION_CAPS = {
    "NEW_RECOVERED_REBUILT": 5,
    "SAVED_UNDER_MAJOR_PRESSURE": 4,
    "ROUTINE_MAINTENANCE": 2,
    "INHERITED_ONLY": 0,
}


def _expected_b1_grade(weighted_value: float) -> int:
    if weighted_value <= 0:
        return 0
    if weighted_value < 0.75:
        return 1
    if weighted_value < 1.5:
        return 2
    if weighted_value < 3.0:
        return 3
    if weighted_value < 6.0:
        return 4
    return 5


def _third_item_cycles(
    decision: Mapping[str, Any], cycles: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    overrides = {
        str(item["campaign_group_ref"]): item
        for item in decision.get("third_item_route_overrides") or ()
    }
    known = {str(cycle["campaign_group_ref"]) for cycle in cycles}
    admitted_rebellions = {
        str(ref) for ref in decision.get("admitted_large_rebellion_refs") or ()
    }
    merge_specs = list(decision.get("third_item_cycle_merges") or ())
    legacy_return_overrides = [
        str(item.get("campaign_group_ref") or item.get("canonical_cycle_ref") or "")
        for item in (*overrides.values(), *merge_specs)
        if "parent_return_class" in item or "return_class" in item
    ]
    if legacy_return_overrides:
        raise ValueError(
            f"{decision['ruler_name']}仍配置显式父级回报类别，"
            f"必须改为父级成本/收益轴后由公式生成：{legacy_return_overrides}"
        )
    merged_canonical_refs = {
        str(spec["canonical_cycle_ref"]) for spec in merge_specs
    }
    known_admission_refs = known | {
        str(spec["canonical_cycle_ref"]) for spec in merge_specs
    } | {
        str(ref)
        for spec in merge_specs
        for ref in spec.get("member_campaign_group_refs") or ()
    }
    exclusion_specs = {
        str(item["campaign_group_ref"]): item
        for item in decision.get("third_item_cycle_exclusions") or ()
    }
    unknown = sorted(
        (set(overrides) | set(exclusion_specs)) - known
        | (admitted_rebellions - known_admission_refs)
    )
    if unknown:
        raise ValueError(
            f"{decision['ruler_name']}第三项路由覆盖引用不存在: {unknown}"
        )
    if decision.get("large_rebellion_audit_status") == "COMPLETE":
        candidate_refs = {
            str(cycle["campaign_group_ref"])
            for cycle in cycles
            if _is_large_internal_rebellion_candidate(cycle)
        }
        reviewed_exclusions = {
            str(item["campaign_group_ref"])
            for item in decision.get("reviewed_large_rebellion_exclusions") or ()
        }
        merge_members = {
            str(ref)
            for item in decision.get("third_item_cycle_merges") or ()
            for ref in item.get("member_campaign_group_refs") or ()
        }
        internal_override_refs = {
            ref
            for ref, item in overrides.items()
            if str(item.get("d_route") or "").startswith("D_INTERNAL")
            or item.get("material_internal_admitted")
        }
        reviewed_refs = (
            admitted_rebellions
            | reviewed_exclusions
            | merge_members
            | internal_override_refs
        )
        missing_rebellion_audit = sorted(candidate_refs - reviewed_refs)
        if missing_rebellion_audit:
            raise ValueError(
                f"{decision['ruler_name']}存在未裁决大型内部战争候选: "
                f"{missing_rebellion_audit}"
            )
        unknown_rebellion_exclusions = sorted(reviewed_exclusions - candidate_refs)
        if unknown_rebellion_exclusions:
            raise ValueError(
                f"{decision['ruler_name']}大型叛乱排除项不符合候选规则: "
                f"{unknown_rebellion_exclusions}"
            )
        if any(
            not str(item.get("reason") or "").strip()
            for item in decision.get("reviewed_large_rebellion_exclusions") or ()
        ):
            raise ValueError(f"{decision['ruler_name']}大型叛乱排除项缺少理由")
    if any(not str(item.get("reason") or "").strip() for item in overrides.values()):
        raise ValueError(f"{decision['ruler_name']}第三项路由覆盖缺少理由")
    if any(
        not str(item.get("reason") or "").strip()
        for item in exclusion_specs.values()
    ):
        raise ValueError(f"{decision['ruler_name']}第三项周期排除缺少理由")
    if set(overrides).intersection(exclusion_specs):
        raise ValueError(f"{decision['ruler_name']}同一周期不得同时覆盖并排除")
    included = []
    excluded = []
    for cycle in cycles:
        cycle_ref = str(cycle["campaign_group_ref"])
        if cycle_ref in exclusion_specs and cycle_ref not in merged_canonical_refs:
            routed = dict(cycle)
            routed["third_item_exclusion_reason"] = str(
                exclusion_specs[cycle_ref]["reason"]
            )
            excluded.append(routed)
            continue
        founding = any(
            phase["founding_startup_ledger"]["is_founding_process"]
            for phase in cycle["phases"]
        )
        if (
            not founding
            or cycle_ref in overrides
            or cycle_ref in admitted_rebellions
        ):
            routed = dict(cycle)
            routed["large_rebellion_admitted"] = cycle_ref in admitted_rebellions
            routed["material_admission_basis"] = (
                "ALL_RULERS_LARGE_REBELLION_AUDIT"
                if cycle_ref in admitted_rebellions
                else None
            )
            override = overrides.get(cycle_ref)
            if override:
                d_route = str(override.get("d_route") or "")
                if d_route:
                    if d_route not in {
                        "D_EXTERNAL_OR_FRONTIER",
                        "D_INTERNAL_STRATEGIC",
                        "D_INTERNAL_RESTORATION",
                    }:
                        raise ValueError(f"{decision['ruler_name']}第三项内部战争路由非法")
                    routed["d_route"] = d_route
                if override.get("parent_cost_axes"):
                    routed["parent_cost_axes"] = dict(override["parent_cost_axes"])
                if override.get("parent_benefit_axes"):
                    routed["parent_benefit_axes"] = dict(override["parent_benefit_axes"])
                if override.get("strategic_result_chain_ref"):
                    routed["strategic_result_chain_ref"] = str(
                        override["strategic_result_chain_ref"]
                    )
                if override.get("allow_explicit_phase_return_fallback"):
                    routed["allow_explicit_phase_return_fallback"] = True
                if override.get("material_internal_admitted"):
                    routed["material_internal_admitted"] = True
                if override.get("material_cumulative_admitted"):
                    routed["material_cumulative_admitted"] = True
                routed["route_override_reason"] = str(override["reason"])
            if routed["large_rebellion_admitted"]:
                configured_internal_route = str((override or {}).get("d_route") or "")
                routed["d_route"] = (
                    configured_internal_route
                    if configured_internal_route.startswith("D_INTERNAL")
                    else "D_INTERNAL_RESTORATION"
                )
                routed["route_override_reason"] = (
                    str((override or {}).get("reason") or "")
                    or "统一大型叛乱审计准入：平乱只恢复事前秩序，不按外部扩张收益结算。"
                )
            included.append(routed)
        else:
            excluded.append(dict(cycle))
    used_members: set[str] = set()
    for spec in merge_specs:
        canonical_ref = str(spec["canonical_cycle_ref"])
        members = [str(ref) for ref in spec.get("member_campaign_group_refs") or ()]
        if len(members) < 2 or canonical_ref not in members:
            raise ValueError(
                f"{decision['ruler_name']}周期合并必须包含至少两个成员且规范键属于成员"
            )
        if len(set(members)) != len(members) or used_members.intersection(members):
            raise ValueError(f"{decision['ruler_name']}周期合并成员重复")
        if not str(spec.get("reason") or "").strip():
            raise ValueError(f"{decision['ruler_name']}周期合并缺少理由")
        by_ref = {str(cycle["campaign_group_ref"]): cycle for cycle in included}
        missing = sorted(set(members) - set(by_ref))
        if missing:
            raise ValueError(f"{decision['ruler_name']}周期合并成员不存在或已排除: {missing}")
        selected = [by_ref[ref] for ref in members]
        canonical_member = by_ref[canonical_ref]
        merged = {
            "campaign_group_ref": canonical_ref,
            "war_event_refs": _unique(
                ref for cycle in selected for ref in cycle["war_event_refs"]
            ),
            "phase_ids": _unique(
                ref for cycle in selected for ref in cycle["phase_ids"]
            ),
            "phases": [phase for cycle in selected for phase in cycle["phases"]],
            "merged_campaign_group_refs": members,
            "merge_reason": str(spec["reason"]),
            "d_route": (
                "D_INTERNAL_RESTORATION"
                if canonical_ref in admitted_rebellions
                or any(bool(cycle.get("large_rebellion_admitted")) for cycle in selected)
                else spec.get("d_route") or canonical_member.get("d_route")
            ),
            "parent_cost_axes": spec.get("parent_cost_axes") or canonical_member.get("parent_cost_axes"),
            "parent_benefit_axes": spec.get("parent_benefit_axes") or canonical_member.get("parent_benefit_axes"),
            "strategic_result_chain_ref": str(
                spec.get("strategic_result_chain_ref") or canonical_ref
            ),
            "allow_explicit_phase_return_fallback": any(
                bool(cycle.get("allow_explicit_phase_return_fallback"))
                for cycle in selected
            ),
            "route_override_reason": canonical_member.get("route_override_reason"),
            "large_rebellion_admitted": canonical_ref in admitted_rebellions or any(
                bool(cycle.get("large_rebellion_admitted")) for cycle in selected
            ),
            "material_internal_admitted": any(
                bool(cycle.get("material_internal_admitted")) for cycle in selected
            ),
            "material_cumulative_admitted": bool(
                spec.get("material_cumulative_admitted")
            ) or any(
                bool(cycle.get("material_cumulative_admitted")) for cycle in selected
            ),
            "material_admission_basis": (
                "ALL_RULERS_LARGE_REBELLION_AUDIT"
                if canonical_ref in admitted_rebellions
                or any(bool(cycle.get("large_rebellion_admitted")) for cycle in selected)
                else None
            ),
        }
        first_index = min(
            index
            for index, cycle in enumerate(included)
            if str(cycle["campaign_group_ref"]) in set(members)
        )
        included = [
            cycle
            for cycle in included
            if str(cycle["campaign_group_ref"]) not in set(members)
        ]
        included.insert(first_index, merged)
        used_members.update(members)
    if merged_canonical_refs.intersection(exclusion_specs):
        retained = []
        for cycle in included:
            cycle_ref = str(cycle["campaign_group_ref"])
            if cycle_ref not in exclusion_specs:
                retained.append(cycle)
                continue
            routed = dict(cycle)
            routed["third_item_exclusion_reason"] = str(
                exclusion_specs[cycle_ref]["reason"]
            )
            excluded.append(routed)
        included = retained
    return included, excluded


def _is_large_internal_rebellion_candidate(cycle: Mapping[str, Any]) -> bool:
    roles = {
        str(phase.get("subject_role") or "")
        for phase in cycle.get("phases") or ()
    }
    role_prefixes = (
        "COUNTERINSURGENCY", "COUNTERREBELLION", "COUNTERMUTINY",
        "COUNTER_MUTINY", "COUNTERCOUP", "SUPPRESSOR", "MUTINY_VICTIM",
        "INTERNAL_SECURITY", "MILITARY_PACIFICATION", "PACIFICATION",
    )
    internal_role = any(
        role.startswith(role_prefixes) for role in roles
    )
    text = " ".join(
        str(value or "")
        for phase in cycle.get("phases") or ()
        for value in (
            phase.get("evaluation_subject_phase"),
            phase.get("actual_process"),
            phase.get("phase_return_basis"),
        )
    )
    internal_text = any(
        marker in text
        for marker in ("叛乱", "叛军", "复叛", "平乱", "讨平", "平定", "兵变", "民变", "起事")
    )
    if not (internal_role or internal_text):
        return False
    audit = _aggregate_parent_cycle_audit(cycle)
    return int(audit.get("material_exposure_index") or 0) >= 9


def _conflicts_for_ruler(registry: Mapping[str, Any], ruler_id: str) -> list[dict[str, Any]]:
    conflicts = []
    for record in registry.get("records") or ():
        if record.get("dynasty_partition") != "five_dynasties":
            continue
        for phase in record.get("subject_phase_views") or ():
            binding = phase.get("ruler_binding") or {}
            if ruler_id in (binding.get("candidate_ruler_ids") or ()):
                conflicts.append(
                    {
                        "phase_id": phase["phase_id"],
                        "war_event_id": record["war_event_id"],
                        "reason": binding["basis"],
                    }
                )
    return conflicts


def build_five_dynasties_ab_records(
    registry: Mapping[str, Any], adjudications: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    records = []
    for decision in adjudications:
        raw_cycles, _, _ = _cycles_and_refs(registry, str(decision["ruler_id"]))
        cycles, _ = _third_item_cycles(decision, raw_cycles)
        event_refs = _unique(
            ref for cycle in cycles for ref in cycle["war_event_refs"]
        )
        phase_refs = _unique(
            ref for cycle in cycles for ref in cycle["phase_ids"]
        )
        conflicts = _conflicts_for_ruler(registry, str(decision["ruler_id"]))
        ready = bool(decision.get("score_ready", decision.get("coverage_complete", False)))
        base = {
            "ruler_id": decision["ruler_id"], "ruler_name": decision["ruler_name"],
            "polity": decision["polity"], "partition": "五代十国",
            "reign_range": decision["reign_range"],
            "subject_binding_review_status": "REVIEWED_SUFFICIENT" if ready else "REVIEWED_INSUFFICIENT",
            "ambiguous_event_refs": conflicts,
            "boundary_stage_refs": [item["phase_id"] for item in conflicts],
            "boundary_stage_excluded_refs": [item["phase_id"] for item in conflicts],
            "boundary_stage_review_status": "REVIEWED",
            "evidence_event_refs": event_refs,
            "parent_cycle_refs": [cycle["campaign_group_ref"] for cycle in cycles],
            "defense_event_count": len(cycles),
            "parent_cycle_merge_adjudications": [
                {
                    "canonical_cycle_ref": cycle["campaign_group_ref"],
                    "member_campaign_group_refs": cycle["merged_campaign_group_refs"],
                    "reason": cycle["merge_reason"],
                }
                for cycle in cycles
                if cycle.get("merged_campaign_group_refs")
            ],
            "parent_cycle_reference_policy": "RAW_EVIDENCE_EVENT_REFS_PLUS_CANONICAL_PARENT_CYCLE_REFS",
            "terminal_polity_collapse": bool(decision.get("terminal_polity_collapse")),
            "coverage_status": "FORMAL_CURRENT" if ready else "PENDING_INSUFFICIENT_EVIDENCE",
            "score_ready": ready,
            "adjudication_status": "REVIEWED" if ready else "PENDING",
            "rationale": decision.get("pending_reason") or "按32卷主体阶段卡完成在位窗口、统一排除、状态锚与控制包裁决。",
        }
        if not ready:
            base.update(
                {
                    "axes": {axis: {"grade": "UNKNOWN", "reason": decision["pending_reason"]} for axis in ("A1", "A2", "B1", "B2", "B4")},
                    "AB_score_points": None,
                    "b1_region_control": {"start": {}, "end": {}},
                    "b1_region_adjudications": [],
                    "b1_control_equivalents": {"start": None, "end": None, "net_change": None, "weighted_value": None},
                    "control_contribution_type": "UNKNOWN",
                    "control_contribution_grade_cap": None,
                    "major_in_reign_reversal_refs": [],
                    "primary_threat_refs": [],
                    "primary_control_package_refs": [],
                    "hold_event_refs": [],
                    "non_defense_routing_refs": [],
                }
            )
            records.append(base)
            continue
        axes = {
            "A1": _axis_a("A1", decision["AB"]["A1"]),
            "A2": _axis_a("A2", decision["AB"]["A2"]),
            "B1": _axis_b("B1", decision["AB"]["B1"]),
            "B2": _axis_b("B2", decision["AB"]["B2"]),
            "B4": _axis_b("B4", decision["AB"]["B4"]),
        }
        start = float(decision["AB"]["B1"]["start_equivalent"])
        end = float(decision["AB"]["B1"]["end_equivalent"])
        control_refs = _unique(
            phase["phase_id"]
            for cycle in cycles for phase in cycle["phases"]
            if _grade_number((phase.get("border_control") or {}).get("BCP"), "BCP")
            or _grade_number((phase.get("border_control") or {}).get("BCN"), "BCN")
        )
        threat_refs = _unique(
            phase["phase_id"]
            for cycle in cycles for phase in cycle["phases"]
            if (_grade_number(phase.get("strategic_security"), "SB") or 0) >= 3
            or (_grade_number(phase.get("strategic_security"), "SN") or 0) >= 3
        )
        weighted = round(0.6 * (end - start) + 0.4 * end, 3)
        expected_b1_grade = _expected_b1_grade(weighted)
        if int(decision["AB"]["B1"]["grade"]) != expected_b1_grade:
            raise ValueError(
                f"{decision['ruler_name']} B1档位不符合加权控制值{weighted}: "
                f"应为B1-{expected_b1_grade}"
            )
        contribution_type = str(decision["AB"]["control_contribution_type"])
        contribution_cap = CONTROL_CONTRIBUTION_CAPS.get(contribution_type)
        if contribution_cap is None:
            raise ValueError(f"{decision['ruler_name']}控制成果归责类型非法: {contribution_type}")
        if any(int(decision["AB"][axis]["grade"]) > contribution_cap for axis in ("B2", "B4")):
            raise ValueError(f"{decision['ruler_name']} B2/B4超过控制成果归责上限{contribution_cap}")
        has_explicit_region_ledger = "regions" in decision["AB"]["B1"]
        region_decisions = decision["AB"]["B1"].get("regions") or []
        if has_explicit_region_ledger:
            counted_regions = [item for item in region_decisions if item.get("counted", True)]
            region_start = round(sum(float(item["start_equivalent"]) for item in counted_regions), 3)
            region_end = round(sum(float(item["end_equivalent"]) for item in counted_regions), 3)
            if region_start != start or region_end != end:
                raise ValueError(f"{decision['ruler_name']} B1逐区域账与汇总不一致")
            region_control = {
                "start": {str(item["object_id"]): float(item["start_equivalent"]) for item in counted_regions if float(item["start_equivalent"])},
                "end": {str(item["object_id"]): float(item["end_equivalent"]) for item in counted_regions if float(item["end_equivalent"])},
            }
            region_adjudications = [{
                "object_id": str(item["object_id"]), "object_name": str(item["object_name"]),
                "anchors": ["start", "end"], "counted": bool(item.get("counted", True)),
                "control_equivalent": {"start": float(item["start_equivalent"]), "end": float(item["end_equivalent"])},
                "control_form": str(item["control_form"]),
                "evidence_refs": [str(ref) for ref in item["evidence_refs"]],
                "reason": str(item["reason"]),
            } for item in region_decisions]
            region_ledger_status = "EXPLICIT_REGION_LEDGER"
        else:
            region_control = {"start": {"AGGREGATE_REVIEWED": start}, "end": {"AGGREGATE_REVIEWED": end}}
            region_adjudications = [{
                "object_id": "FIVE_DYNASTIES_REIGN_CONTROL_PACKAGE", "object_name": "本皇帝非统一边疆控制净包",
                "anchors": ["start", "end"], "counted": True,
                "control_equivalent": {"start": start, "end": end}, "evidence_refs": control_refs,
                "reason": decision["AB"]["B1"]["reason"],
            }]
            region_ledger_status = "LEGACY_AGGREGATE_REQUIRES_REGION_MIGRATION"
        if not control_refs and any(int(decision["AB"][axis]["grade"]) > 0 for axis in ("B2", "B4")):
            control_refs = _unique(
                ref
                for item in region_adjudications
                if item.get("counted", True)
                for ref in item.get("evidence_refs") or []
            )
        if not control_refs and any(int(decision["AB"][axis]["grade"]) > 0 for axis in ("B2", "B4")):
            raise ValueError(f"{decision['ruler_name']} B2/B4有正向贡献但缺少可追溯主控制包")
        base.update(
            {
                "axes": axes,
                "AB_score_points": round(sum(axis["axis_points"] for axis in axes.values()), 2),
                "b1_region_control": region_control,
                "b1_region_adjudications": region_adjudications,
                "b1_region_ledger_status": region_ledger_status,
                "b1_control_equivalents": {"start": start, "end": end, "net_change": round(end - start, 3), "weighted_value": weighted},
                "control_contribution_type": contribution_type,
                "control_contribution_grade_cap": contribution_cap,
                "major_in_reign_reversal_refs": _unique(
                    phase["phase_id"] for cycle in cycles for phase in cycle["phases"]
                    if (_grade_number((phase.get("border_control") or {}).get("BCN"), "BCN") or 0) >= 4
                ),
                "primary_threat_refs": threat_refs,
                "primary_control_package_refs": control_refs,
                "hold_event_refs": phase_refs,
                "non_defense_routing_refs": [],
            }
        )
        records.append(base)
    return records


def _c_score(c1: int, c2: int, c3: int) -> tuple[str, float, float, int]:
    grade = min(c1, c2, c3)
    lower, upper = ((0, 29), (30, 44), (45, 59), (60, 74), (75, 89), (90, 100))[grade]
    surplus = (c1 - grade) + (c2 - grade) + (c3 - grade)
    rate = 100.0 if grade == 5 else lower + (upper - lower) * surplus / (2 * (5 - grade))
    return f"C-{grade}", round(rate, 2), round(50 * rate / 100, 1), surplus


def _apply_c_major_victory_gate(row: dict[str, Any]) -> None:
    """C4/C5 must be supported by major wins, not merely many ordinary tasks."""
    row["cap_reasons"] = list(dict.fromkeys(row.get("cap_reasons") or ()))
    grade = _axis_grade(row["C_overall_grade"], "C")
    failures = list(dict.fromkeys(row.get("major_system_failure_refs") or ()))
    successes = list(dict.fromkeys(row.get("major_system_success_refs") or ()))
    row["major_system_failure_refs"] = failures
    row["major_system_success_refs"] = successes

    # C5 is deliberately scarcer than C4.  The contract requires at least
    # three cross-period/direction high-difficulty parent tasks and no major
    # system failure.  Major-system successes are the closed, auditable subset
    # of tasks that can satisfy that threshold; raw task count cannot.
    if grade == 5:
        c5_passed = len(successes) >= 3 and not failures
        row["c5_scarcity_gate"] = {
            "required_major_system_success_count": 3,
            "actual_major_system_success_count": len(successes),
            "requires_zero_major_system_failure": True,
            "actual_major_system_failure_count": len(failures),
            "status": "PASSED" if c5_passed else "CAPPED_BELOW_C5",
        }
        if not c5_passed:
            c4_required = max(1, len(failures))
            ceiling = 4 if len(successes) >= c4_required else 3
            c1 = min(ceiling, _axis_grade(row["combat_delivery_grade"], "C1"))
            c2 = min(ceiling, _axis_grade(row["operational_sustainability_cap"], "C2"))
            c3 = min(ceiling, _axis_grade(row["system_reliability_cap"], "C3"))
            overall, rate, points, surplus = _c_score(c1, c2, c3)
            lower, upper = (
                (0, 29), (30, 44), (45, 59),
                (60, 74), (75, 89), (90, 100),
            )[min(c1, c2, c3)]
            row.update({
                "combat_delivery_grade": f"C1-{c1}",
                "operational_sustainability_cap": f"C2-{c2}",
                "system_reliability_cap": f"C3-{c3}",
                "C_overall_grade": overall,
                "C_score_rate": rate,
                "C_score_points": points,
                "C_score_support_surplus": surplus,
                "C_score_band": {"lower_rate": lower, "upper_rate": upper},
            })
            reason = (
                "C5稀缺门禁未通过：至少需要3项重大体系胜绩且不得保留"
                f"重大体系失败；当前胜绩{len(successes)}项、失败{len(failures)}项，"
                f"封顶C{ceiling}。"
            )
            if reason not in row["cap_reasons"]:
                row["cap_reasons"].append(reason)
            grade = _axis_grade(row["C_overall_grade"], "C")

    required = max(1, len(failures)) if grade >= 4 else 0
    row["major_victory_gate"] = {
        "required_count": required,
        "actual_count": len(successes),
        "status": "PASSED" if len(successes) >= required else "CAPPED_TO_C3",
    }
    if grade < 4 or len(successes) >= required:
        return
    c1 = min(3, _axis_grade(row["combat_delivery_grade"], "C1"))
    c2 = min(3, _axis_grade(row["operational_sustainability_cap"], "C2"))
    c3 = min(3, _axis_grade(row["system_reliability_cap"], "C3"))
    overall, rate, points, surplus = _c_score(c1, c2, c3)
    row.update({
        "combat_delivery_grade": f"C1-{c1}",
        "operational_sustainability_cap": f"C2-{c2}",
        "system_reliability_cap": f"C3-{c3}",
        "C_overall_grade": overall,
        "C_score_rate": rate,
        "C_score_points": points,
        "C_score_support_surplus": surplus,
        "C_score_band": {"lower_rate": 60, "upper_rate": 74},
    })
    reason = f"C4重大胜绩门禁未通过：需{required}项、实有{len(successes)}项，封顶C3。"
    if reason not in row["cap_reasons"]:
        row["cap_reasons"].append(reason)


def _apply_c_within_band_position(row: dict[str, Any]) -> None:
    """Resolve position from axis surplus and outcome quality, not raw volume."""
    row.pop("C_score_major_result_position", None)
    axes = [
        _axis_grade(row["combat_delivery_grade"], "C1"),
        _axis_grade(row["operational_sustainability_cap"], "C2"),
        _axis_grade(row["system_reliability_cap"], "C3"),
    ]
    grade = min(axes)
    lower, upper = (
        (0, 29), (30, 44), (45, 59),
        (60, 74), (75, 89), (90, 100),
    )[grade]
    surplus = sum(axis - grade for axis in axes)
    if grade == 5:
        axis_position = 1.0
        outcome_position = 1.0
        band_position = 1.0
        rate = 100.0
    else:
        axis_position = surplus / (2 * (5 - grade))
        outcome_profile = row.get("task_outcome_profile") or {}
        counts = dict(outcome_profile.get("return_class_counts") or {})
        known = sum(
            int(count)
            for outcome, count in counts.items()
            if outcome != "UNKNOWN"
        )
        if known:
            quality = (
                int(counts.get("HIGH_RETURN", 0))
                + 0.55 * int(counts.get("PROPORTIONATE_RETURN", 0))
                + 0.2 * int(counts.get("LOW_RETURN", 0))
            ) / known
            successes = int(outcome_profile.get("major_system_success_count") or 0)
            failures = int(outcome_profile.get("major_system_failure_count") or 0)
            decisive_balance = (successes + 1) / (successes + failures + 2)
            raw_outcome_position = 0.65 * quality + 0.35 * decisive_balance
            confidence = min(1.0, known / 4)
            outcome_position = 0.5 + (raw_outcome_position - 0.5) * confidence
        else:
            outcome_position = axis_position
        position_decision = row.get("C_score_within_band_adjudication") or {}
        position_code = str(position_decision.get("position") or "")
        adjudicated_position = {
            "LOW": 0.25,
            "MID": 0.5,
            "HIGH": 0.75,
        }.get(position_code)
        # Founding/unification capability may establish the C axis grade, but
        # it must not also provide a second within-band bonus when the current
        # Third Item contributes no independent stress cycle of its own.
        if (
            int(row.get("current_item_task_count") or 0) == 0
            and row.get("capability_only_parent_refs")
        ):
            outcome_position = min(outcome_position, 0.5)
            if adjudicated_position is not None:
                adjudicated_position = min(adjudicated_position, 0.5)
        evidence_position = max(axis_position, outcome_position)
        band_position = (
            max(axis_position, adjudicated_position)
            if adjudicated_position is not None
            else evidence_position
        )
        rate = lower + (upper - lower) * band_position
    row.update({
        "C_score_rate": round(rate, 2),
        "C_score_points": round(50 * rate / 100, 1),
        "C_score_support_surplus": surplus,
        "C_score_axis_surplus_position": round(axis_position, 4),
        "C_score_outcome_position": round(outcome_position, 4),
        "C_score_band_position": round(band_position, 4),
        "C_score_position_method": (
            "AXIS_SURPLUS_PLUS_EXPLICIT_WITHIN_BAND_ADJUDICATION"
            if row.get("C_score_within_band_adjudication")
            else "AXIS_SURPLUS_PLUS_OUTCOME_QUALITY"
        ),
        "C_score_band": {"lower_rate": lower, "upper_rate": upper},
    })


def _apply_c5_axis_gate(
    row: dict[str, Any],
    decision: Mapping[str, Any] | None,
    stress_refs: Sequence[str],
    talent_profiles_by_ref: Mapping[str, Mapping[str, Any]],
    opponent_systems_by_ref: Mapping[str, Mapping[str, Any]],
) -> None:
    """Require independent top-level evidence for every C5 axis."""
    requested_axes = {
        "C1": row.get("combat_delivery_grade") == "C1-5",
        "C2": row.get("operational_sustainability_cap") == "C2-5",
        "C3": row.get("system_reliability_cap") == "C3-5",
    }
    if not any(requested_axes.values()):
        return

    gate = dict((decision or {}).get("c5_axis_gate") or {})
    stress_ref_set = set(stress_refs)
    capability_only_ref_set = {
        str(ref)
        for ref in (decision or {}).get("capability_only_parent_refs") or ()
    }

    def opponent_dimension_passed() -> tuple[bool, list[dict[str, Any]]]:
        items = list(gate.get("C1_high_difficulty_opponents") or ())
        evidence: list[dict[str, Any]] = []
        task_refs: set[str] = set()
        system_refs: set[str] = set()
        for item in items:
            system_ref = str(item.get("opponent_system_ref") or "").strip()
            refs = {str(ref) for ref in item.get("task_refs") or ()}
            system = opponent_systems_by_ref.get(system_ref)
            grade = str((system or {}).get("organization_grade") or "")
            accepted_refs = {str(ref) for ref in (system or {}).get("accepted_task_refs") or ()}
            if (
                not system_ref
                or system is None
                or grade not in {"O4", "O5", "O6"}
                or not refs
                or not refs.issubset(stress_ref_set)
                or not refs.issubset(accepted_refs)
            ):
                return False, evidence
            system_refs.add(system_ref)
            task_refs.update(refs)
            evidence.append({
                "opponent_system_ref": system_ref,
                "opponent_label": str(system.get("opponent_label") or system_ref),
                "organization_grade": grade,
                "task_refs": sorted(refs),
            })
        return len(system_refs) >= 2 and len(task_refs) >= 3, evidence

    def direction_dimension_passed() -> tuple[bool, list[dict[str, Any]]]:
        items = list(gate.get("C2_strategic_directions") or ())
        evidence: list[dict[str, Any]] = []
        task_refs: set[str] = set()
        system_refs: set[str] = set()
        directions: set[str] = set()
        for item in items:
            direction = str(item.get("direction") or "").strip()
            refs = {str(ref) for ref in item.get("task_refs") or ()}
            refs_for_systems = {str(ref) for ref in item.get("opponent_system_refs") or ()}
            systems = [opponent_systems_by_ref.get(ref) for ref in refs_for_systems]
            if (
                not direction
                or not refs
                or not refs_for_systems
                or not refs.issubset(stress_ref_set)
                or any(system is None for system in systems)
                or any(
                    str((system or {}).get("organization_grade") or "")
                    not in {"O4", "O5", "O6"}
                    for system in systems
                )
                or not all(
                    refs.intersection(
                        str(value) for value in (system or {}).get("accepted_task_refs") or ()
                    )
                    for system in systems
                )
            ):
                return False, evidence
            directions.add(direction)
            task_refs.update(refs)
            system_refs.update(refs_for_systems)
            evidence.append({
                "direction": direction,
                "opponent_system_refs": sorted(refs_for_systems),
                "task_refs": sorted(refs),
            })
        return (
            len(directions) >= 2
            and len(system_refs) >= 2
            and len(task_refs) >= 3
        ), evidence

    c1_passed, opponent_evidence = opponent_dimension_passed()
    c2_passed, direction_evidence = direction_dimension_passed()

    commander_refs: list[str] = []
    commander_names: list[str] = []
    c3_passed = True
    deliveries = list(gate.get("C3_top_commander_deliveries") or ())
    for item in deliveries:
        profile_ref = str(item.get("profile_ref") or "")
        profile = talent_profiles_by_ref.get(profile_ref)
        achievement_refs = {str(ref) for ref in item.get("achievement_refs") or ()}
        if not profile or not achievement_refs:
            c3_passed = False
            continue
        achievements = {
            str(achievement.get("campaign_ref")): achievement
            for achievement in profile.get("consumed_achievements") or ()
        }
        if (
            str(profile.get("military_grade")) not in {"top", "historic"}
            or not achievement_refs.issubset(achievements)
            or any(
                str(achievements[ref].get("campaign_tier"))
                not in {"A", "S-", "S", "S+"}
                for ref in achievement_refs
            )
        ):
            c3_passed = False
            continue
        commander_refs.append(profile_ref)
        commander_names.append(str(profile.get("person") or profile_ref))
    c3_passed = c3_passed and len(set(commander_refs)) >= 2

    passed = {"C1": c1_passed, "C2": c2_passed, "C3": c3_passed}
    axis_status = {
        axis: (
            "NOT_APPLICABLE"
            if not requested_axes[axis]
            else "PASSED" if passed[axis]
            else "CAPPED_TO_4"
        )
        for axis in ("C1", "C2", "C3")
    }
    all_requested_passed = all(
        passed[axis] for axis in requested_axes if requested_axes[axis]
    )
    row["c5_axis_gate"] = {
        "C1_O4_plus_opponent_systems": opponent_evidence,
        "C2_O4_plus_strategic_directions": direction_evidence,
        "C3_top_commander_profiles": sorted(set(commander_refs)),
        "C3_top_commander_names": sorted(set(commander_names)),
        "axis_status": axis_status,
        "founding_capability_only_refs_admitted_for_C1_C2_gate": sorted(
            capability_only_ref_set
        ),
        "status": "PASSED" if all_requested_passed else "CAPPED_BELOW_AXIS_5",
    }
    if all_requested_passed:
        return

    c1 = min(
        4 if requested_axes["C1"] and not c1_passed else 5,
        _axis_grade(row["combat_delivery_grade"], "C1"),
    )
    c2 = min(
        4 if requested_axes["C2"] and not c2_passed else 5,
        _axis_grade(row["operational_sustainability_cap"], "C2"),
    )
    c3 = min(
        4 if requested_axes["C3"] and not c3_passed else 5,
        _axis_grade(row["system_reliability_cap"], "C3"),
    )
    overall, rate, points, surplus = _c_score(c1, c2, c3)
    lower, upper = (
        (0, 29), (30, 44), (45, 59),
        (60, 74), (75, 89), (90, 100),
    )[min(c1, c2, c3)]
    row.update({
        "combat_delivery_grade": f"C1-{c1}",
        "operational_sustainability_cap": f"C2-{c2}",
        "system_reliability_cap": f"C3-{c3}",
        "C_overall_grade": overall,
        "C_score_rate": rate,
        "C_score_points": points,
        "C_score_support_surplus": surplus,
        "C_score_band": {"lower_rate": lower, "upper_rate": upper},
    })
    failed_axes = "/".join(
        axis for axis, status in axis_status.items() if status == "CAPPED_TO_4"
    )
    reason = f"C轴5档门禁未通过：{failed_axes}缺少独立顶级证据，对应轴封顶4档。"
    if reason not in row.setdefault("cap_reasons", []):
        row["cap_reasons"].append(reason)


def _apply_c_task_evidence_ceiling(row: dict[str, Any]) -> None:
    row["cap_reasons"] = list(dict.fromkeys(row.get("cap_reasons") or ()))
    tasks = int(row.get("independent_task_count") or 0)
    ceiling = 3 if tasks <= 1 else 4 if tasks == 2 else 5
    c1 = min(ceiling, _axis_grade(row["combat_delivery_grade"], "C1"))
    c2 = _axis_grade(row["operational_sustainability_cap"], "C2")
    c3 = min(ceiling, _axis_grade(row["system_reliability_cap"], "C3"))
    if (
        c1 == _axis_grade(row["combat_delivery_grade"], "C1")
        and c3 == _axis_grade(row["system_reliability_cap"], "C3")
    ):
        return
    overall, rate, points, surplus = _c_score(c1, c2, c3)
    lower, upper = ((0, 29), (30, 44), (45, 59), (60, 74), (75, 89), (90, 100))[min(c1, c2, c3)]
    row.update({
        "combat_delivery_grade": f"C1-{c1}",
        "operational_sustainability_cap": f"C2-{c2}",
        "system_reliability_cap": f"C3-{c3}",
        "C_overall_grade": overall,
        "C_score_rate": rate,
        "C_score_points": points,
        "C_score_support_surplus": surplus,
        "C_score_band": {"lower_rate": lower, "upper_rate": upper},
        "evidence_ceiling": ceiling,
    })
    reason = f"排除创业统一账后仅余{tasks}项独立任务，C1/C3按证据上限{ceiling}档收束。"
    if reason not in row["cap_reasons"]:
        row["cap_reasons"].append(reason)


def _opponent_systems_by_ref(
    workspace_root: Path,
    registry: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Load the shared O1-O6 system facts and their public task aliases."""
    landscapes = json.loads(
        (workspace_root / FIRST_ITEM_A_COMPETITIVE_LANDSCAPES_PATH).read_text(
            encoding="utf-8"
        )
    )
    if (
        landscapes.get("schema_version") != "first-item-a-competitive-landscapes-v9"
        or landscapes.get("status") != "CURRENT"
    ):
        raise ValueError("第一项A对手战争机器O档合同非法")
    systems: dict[str, dict[str, Any]] = {}
    for portfolio in registry.get("unification_campaign_portfolios") or ():
        for raw in portfolio.get("opponent_systems") or ():
            system_ref = str(raw.get("system_id") or "")
            if not system_ref or system_ref in systems:
                raise ValueError(f"公共统一链O体系标识缺失或重复: {system_ref}")
            systems[system_ref] = dict(raw)
    supplemental = {
        str(ref): dict(row)
        for ref, row in dict(
            landscapes.get("supplemental_opponent_systems") or {}
        ).items()
    }
    overlap = set(systems) & set(supplemental)
    if overlap:
        raise ValueError(f"公共统一链与补充O体系重复: {sorted(overlap)}")
    systems.update(supplemental)

    public_aliases: dict[str, set[str]] = defaultdict(set)
    for record in registry.get("records") or ():
        record_ref = str(record.get("war_event_id") or "")
        source_target_ref = str(record.get("source_target_ref") or "")
        campaign_group_ref = str(record.get("campaign_group_ref") or "")
        for source_ref in (source_target_ref, campaign_group_ref):
            if source_ref and record_ref:
                public_aliases[source_ref].add(record_ref)
    for system in systems.values():
        source_refs = {str(ref) for ref in system.get("source_campaign_refs") or ()}
        accepted = set(source_refs)
        for source_ref in source_refs:
            accepted.update(public_aliases.get(source_ref) or ())
        system["accepted_task_refs"] = sorted(accepted)
    return systems


def build_five_dynasties_c_records(
    registry: Mapping[str, Any], adjudications: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    records = []
    for decision in adjudications:
        cycles, event_refs, _ = _cycles_and_refs(registry, str(decision["ruler_id"]))
        third_item_cycles, _ = _third_item_cycles(decision, cycles)
        ready = bool(decision.get("score_ready", decision.get("coverage_complete", False)))
        base = {
            "ruler_id": decision["ruler_id"], "ruler_name": decision["ruler_name"],
            "polity": decision["polity"], "partition": "五代十国", "reign_range": decision["reign_range"],
            "independent_task_count": len(third_item_cycles),
            "independent_task_groups": [cycle["campaign_group_ref"] for cycle in third_item_cycles],
            "parent_cycle_merge_adjudications": [
                {
                    "canonical_cycle_ref": cycle["campaign_group_ref"],
                    "member_campaign_group_refs": cycle["merged_campaign_group_refs"],
                    "reason": cycle["merge_reason"],
                }
                for cycle in third_item_cycles
                if cycle.get("merged_campaign_group_refs")
            ],
            "settled_event_refs": _unique(ref for cycle in third_item_cycles for ref in cycle["war_event_refs"]),
            "cross_reign_slice_refs": [item["phase_id"] for item in _conflicts_for_ruler(registry, str(decision["ruler_id"]))],
            "non_war_evidence_refs": [], "major_system_failure_refs": [],
            "score_ready": ready,
            "coverage_status": "FULL_REIGN_WAR_EVENT_BINDING" if ready else "PENDING_INSUFFICIENT_EVIDENCE",
            "unresolved_gaps": [] if ready else [decision["pending_reason"]],
        }
        if not ready:
            base.update({
                "combat_delivery_grade": "UNKNOWN", "operational_sustainability_cap": "UNKNOWN",
                "system_reliability_cap": "UNKNOWN", "C_overall_grade": "UNKNOWN",
                "C_score_rate": None, "C_score_points": None, "C_score_support_surplus": None,
                "C_score_band": None, "adjudication_method": "INSUFFICIENT_EVIDENCE",
                "score_status": "UNASSESSED",
                "evidence_ceiling": min(3, len(third_item_cycles) + 2) if third_item_cycles else 0,
                "evidence_ceiling_adjustments": [], "cap_reasons": [decision["pending_reason"]],
                "collapse_profile": "UNKNOWN", "passive_C1_adjustment": None,
                "passive_C1_cap": None, "passive_loss_rationale": None, "passive_loss_refs": [],
            })
            records.append(base)
            continue
        c1, c2, c3 = (int(decision["C"][key]) for key in ("C1", "C2", "C3"))
        evidence_ceiling = 3 if len(third_item_cycles) <= 1 else 4 if len(third_item_cycles) == 2 else 5
        if not third_item_cycles and not decision.get("C", {}).get("non_war_evidence_refs"):
            raise ValueError(f"{decision['ruler_name']} C项无独立任务或非战争体系证据，不得直接结算")
        if c1 > evidence_ceiling or c3 > evidence_ceiling:
            raise ValueError(
                f"{decision['ruler_name']} C1/C3超过{len(third_item_cycles)}项独立任务的证据上限{evidence_ceiling}"
            )
        overall, rate, points, surplus = _c_score(c1, c2, c3)
        major_failures = [
            str(ref)
            for ref in decision.get("C", {}).get(
                "major_system_failure_group_refs", ()
            )
        ]
        major_successes = [
            str(ref)
            for ref in decision.get("C", {}).get(
                "major_system_success_group_refs", ()
            )
        ]
        known_task_groups = {
            str(cycle["campaign_group_ref"]) for cycle in third_item_cycles
        }
        if (
            len(set(major_failures)) != len(major_failures)
            or len(set(major_successes)) != len(major_successes)
            or not set(major_failures).issubset(known_task_groups)
            or not set(major_successes).issubset(known_task_groups)
        ):
            raise ValueError(
                f"{decision['ruler_name']} C项重大胜负必须引用本人已结算的去重战役群"
            )
        grade = min(c1, c2, c3)
        if grade == 5 and major_failures:
            raise ValueError(f"{decision['ruler_name']} C5不得保留重大体系失败引用")
        lower, upper = ((0, 29), (30, 44), (45, 59), (60, 74), (75, 89), (90, 100))[grade]
        base.update({
            "combat_delivery_grade": f"C1-{c1}", "operational_sustainability_cap": f"C2-{c2}",
            "system_reliability_cap": f"C3-{c3}", "C_overall_grade": overall,
            "C_score_rate": rate, "C_score_points": points, "C_score_support_surplus": surplus,
            "C_score_band": {"lower_rate": lower, "upper_rate": upper},
            "adjudication_method": "SUBJECT_PHASE_CONTRACT_ADJUDICATION",
            "score_status": "DIRECT_C_SCORE_ASSIGNED",
            "evidence_ceiling": evidence_ceiling,
            "evidence_ceiling_adjustments": [], "cap_reasons": [decision["C"]["reason"]],
            "major_system_failure_refs": major_failures,
            "major_system_success_refs": major_successes,
            "collapse_profile": "NATIONWIDE_DOMINANT_UNRECOVERED" if c3 == 0 else "NO_NATIONWIDE_DOMINANT_COLLAPSE",
            "passive_C1_adjustment": None, "passive_C1_cap": None,
            "passive_loss_rationale": None, "passive_loss_refs": [],
        })
        _apply_c_major_victory_gate(base)
        _apply_c_within_band_position(base)
        records.append(base)
    return records


def _validate_bc_parent_cycle_alignment(
    ab_records: Sequence[Mapping[str, Any]],
    c_records: Sequence[Mapping[str, Any]],
) -> None:
    ab_by_id = {str(row["ruler_id"]): row for row in ab_records}
    c_ids = {str(row["ruler_id"]) for row in c_records}
    if not set(ab_by_id).issubset(c_ids):
        missing = sorted(set(ab_by_id) - c_ids)
        raise ValueError(f"B项已有主体缺少C项记录：{missing}")
    for c_row in c_records:
        ruler_id = str(c_row["ruler_id"])
        if ruler_id not in ab_by_id:
            continue
        ab_row = ab_by_id[ruler_id]
        capability_only_refs = {
            str(ref) for ref in c_row.get("capability_only_parent_refs") or ()
        }
        ab_parent_refs = {
            str(ref) for ref in ab_row.get("parent_cycle_refs") or ()
        }
        leaked_refs = sorted(capability_only_refs & ab_parent_refs)
        if (
            ab_row.get("parent_cycle_reference_policy")
            == "AB_STATE_CHANGE_EVIDENCE_EXCLUDING_C_ONLY_FOUNDING_CAPABILITY"
            and leaked_refs
        ):
            raise ValueError(
                f"{c_row['ruler_name']}的C专用创业统一能力引用污染A/B追溯集合："
                f"{leaked_refs}"
            )
        if list(ab_row.get("parent_cycle_merge_adjudications") or ()) != list(
            c_row.get("parent_cycle_merge_adjudications") or ()
        ):
            raise ValueError(f"{c_row['ruler_name']}的B/C父级合并裁决不一致")
        groups = {str(ref) for ref in c_row["independent_task_groups"]}
        if not set(c_row.get("major_system_failure_refs") or ()).issubset(groups):
            raise ValueError(
                f"{c_row['ruler_name']}的C项重大体系失败未引用去重父周期"
            )
        if not set(c_row.get("major_system_success_refs") or ()).issubset(groups):
            raise ValueError(
                f"{c_row['ruler_name']}的C项重大胜绩未引用去重父周期"
            )
        for merge in c_row.get("parent_cycle_merge_adjudications") or ():
            canonical = str(merge["canonical_cycle_ref"])
            retired_members = {
                str(ref) for ref in merge["member_campaign_group_refs"]
            } - {canonical}
            if retired_members.intersection(groups):
                raise ValueError(
                    f"{c_row['ruler_name']}的C独立任务仍含父级合并成员"
                )


def _qin_tang_source_index_rows(workspace_root: Path) -> list[dict[str, Any]]:
    """Combine the canonical WAR index with tracked DEF parent-card headings."""

    index_payload = json.loads(
        (workspace_root / QIN_TANG_BATTLE_INDEX_PATH).read_text(encoding="utf-8")
    )
    raw_index_rows = list(
        index_payload.get("cards") or index_payload.get("records") or index_payload
    )
    chronicle_root = workspace_root / "docs/史料通读产物/唐以前编年"
    source_cache: dict[str, list[str]] = {}
    heading_cache: dict[str, dict[str, list[int]]] = {}
    index_rows: list[dict[str, Any]] = []

    def resolve_index_row(raw_row: Mapping[str, Any]) -> dict[str, Any]:
        row = dict(raw_row)
        source_card_id = str(row["source_card_id"])
        actual_heading_id = str(row.get("actual_heading_id") or source_card_id)
        source_file = str(row["source_file"])
        lines = source_cache.setdefault(
            source_file,
            (workspace_root / source_file).read_text(encoding="utf-8").splitlines(),
        )
        headings = heading_cache.setdefault(source_file, defaultdict(list))
        if not headings:
            for line_number, line in enumerate(lines, start=1):
                match = re.match(r"^###\s+([^\s|｜]+)", line)
                if match:
                    headings[match.group(1)].append(line_number)
        matches = list(headings.get(actual_heading_id) or ())
        if len(matches) != 1:
            raise ValueError(
                f"秦至唐战争卡索引标题ID必须唯一闭合：{source_card_id}→"
                f"{actual_heading_id}，命中{matches}"
            )
        resolved_line = matches[0]
        audit_line = int(row["heading_line"])
        if audit_line != resolved_line:
            raise ValueError(
                f"秦至唐战争卡索引行号漂移：{source_card_id}记录L{audit_line}，"
                f"实际标题{actual_heading_id}位于L{resolved_line}"
            )
        end = next(
            (
                index
                for index in range(resolved_line, len(lines))
                if lines[index].startswith("### ")
            ),
            len(lines),
        )
        section = "\n".join(lines[resolved_line - 1 : end])
        owner_match = re.search(r"settlement_owner=([^`;\s]+)", section)
        machine_match = re.search(r"machine_settlement=(yes|no)", section)
        group_match = re.search(r"campaign_group=([^`;\s]+)", section)
        settlement_owner = owner_match.group(1) if owner_match else None
        if actual_heading_id != source_card_id:
            if settlement_owner != source_card_id:
                raise ValueError(
                    f"秦至唐战争卡索引别名关系非法：{source_card_id}→"
                    f"{actual_heading_id}，标题区段owner={settlement_owner}"
                )
            if not str(row.get("title") or "").startswith("父级结算键（源卡："):
                raise ValueError(f"秦至唐战争卡索引别名缺少显式标题声明：{source_card_id}")
        row.update(
            {
                "actual_heading_id": actual_heading_id,
                "resolved_heading_line": resolved_line,
                "source_settlement_owner": settlement_owner,
                "source_machine_settlement": (
                    machine_match.group(1) if machine_match else "UNKNOWN"
                ),
                "source_campaign_group": (
                    group_match.group(1) if group_match else None
                ),
            }
        )
        return row

    index_rows.extend(resolve_index_row(row) for row in raw_index_rows)
    seen = {str(row["source_card_id"]) for row in index_rows}
    for source_path in sorted(chronicle_root.rglob("卷*-通读总结.md")):
        lines = source_path.read_text(encoding="utf-8").splitlines()
        for heading_line, line in enumerate(lines, start=1):
            match = re.match(
                r"^### (DEF-[^\s|｜]+)(?:\s*[|｜]\s*|\s+)?(.*)?$",
                line,
            )
            if not match:
                continue
            source_card_id = match.group(1)
            if source_card_id in seen:
                raise ValueError(f"DEF父卡ID重复：{source_card_id}")
            seen.add(source_card_id)
            relative = source_path.relative_to(workspace_root).as_posix()
            index_rows.append(
                resolve_index_row({
                    "source_card_id": source_card_id,
                    "title": (match.group(2) or source_card_id).strip(),
                    "dynasty": source_path.parent.name,
                    "volume": source_path.stem.split("-", 1)[0],
                    "source_file": relative,
                    "heading_line": heading_line,
                    "source_kind": "DEF",
                })
            )
    return index_rows


def _qin_tang_campaign_groups_by_ref(
    workspace_root: Path,
) -> dict[str, set[str]]:
    index_rows = _qin_tang_source_index_rows(workspace_root)
    source_cache: dict[str, list[str]] = {}
    groups_by_ref: dict[str, set[str]] = defaultdict(set)
    for card in index_rows:
        source_ref = str(card["source_card_id"])
        source_file = str(card["source_file"])
        lines = source_cache.setdefault(
            source_file,
            (workspace_root / source_file).read_text(encoding="utf-8").splitlines(),
        )
        start = int(card["resolved_heading_line"]) - 1
        end = next(
            (
                index
                for index in range(start + 1, len(lines))
                if lines[index].startswith(("## ", "### "))
            ),
            len(lines),
        )
        section = "\n".join(lines[start:end])
        for pattern in (
            r"`campaign_group=([^`]+)`",
            r"^- campaign_group:\s*(\S+)\s*$",
            r"^- campaign_group：\s*(\S+)\s*$",
        ):
            match = re.search(pattern, section, re.MULTILINE)
            if match:
                groups_by_ref[source_ref].add(match.group(1).strip())
                break
    return groups_by_ref


def _resolve_qin_tang_failure_group(
    source_ref: str,
    existing_groups: Sequence[str],
    source_groups: set[str],
) -> str:
    existing = set(existing_groups)
    if source_ref in existing:
        return source_ref
    direct = existing.intersection(source_groups)
    if len(direct) == 1:
        return direct.pop()
    event_ref = f"EVENT:{source_ref}"
    if event_ref in existing:
        return event_ref
    suffix = source_ref.removeprefix("WAR-")
    suffix_matches = [group for group in existing if group.endswith(suffix)]
    if len(suffix_matches) == 1:
        return suffix_matches[0]
    ignored = {"WAR", "LEAD", "CAMPAIGN", "EVENT", "PARENT"}
    candidate_texts = [source_ref, *source_groups]
    source_tokens = {
        token
        for text in candidate_texts
        for token in re.split(r"[^A-Z0-9]+", text.upper())
        if token and token not in ignored and not re.fullmatch(r"V\d+", token)
    }
    scored: list[tuple[int, float, str]] = []
    for group in existing:
        group_tokens = {
            token
            for token in re.split(r"[^A-Z0-9]+", group.upper())
            if token and token not in ignored and not re.fullmatch(r"V\d+", token)
        }
        overlap = len(source_tokens.intersection(group_tokens))
        scored.append(
            (overlap, overlap / max(1, len(source_tokens.union(group_tokens))), group)
        )
    scored.sort(reverse=True)
    if scored and scored[0][0] >= 2 and (
        len(scored) == 1 or scored[0][:2] > scored[1][:2]
    ):
        return scored[0][2]
    raise ValueError(f"C项重大体系失败{source_ref}无法确定其去重父周期")


def _qin_tang_founding_refs_by_name(
    workspace_root: Path,
) -> dict[str, set[str]]:
    first_item_payload = json.loads(
        (workspace_root / FIRST_ITEM_C_WINDOWS_PATH).read_text(encoding="utf-8")
    )
    refs_by_name = {
        str(item["ruler_name"]): {
            str(ref) for ref in item.get("campaign_refs") or ()
        }
        for item in first_item_payload.get("manual_windows") or ()
    }
    refs_by_name.setdefault("刘秀", set()).add(
        "WAR-LEAD-HAN-STARTUP-UNIFICATION-23-36"
    )
    refs_by_name.setdefault("杨坚", set()).add(
        "WAR-LEAD-SUI-ABSORB-LIANG-587"
    )
    refs_by_name.setdefault("沮渠蒙逊", set()).add(
        "WAR-LEAD-112-MENGXUN-401"
    )
    refs_by_name.setdefault("李雄", set()).add(
        "CAMPAIGN-JIN-YIZHOU-LI-300-OPEN"
    )
    refs_by_name.setdefault("李渊", set()).update(
        {
            "CAMPAIGN-TANG-XUYUANLANG-621-623",
            "CAMPAIGN-TANG-LIUHEITA-621-623",
            "CAMPAIGN-TANG-FUGONGSHI-623-624",
        }
    )
    return refs_by_name


def _normalize_qin_tang_bc_parent_cycles(
    workspace_root: Path,
    ab_records: Sequence[dict[str, Any]],
    c_records: Sequence[dict[str, Any]],
) -> None:
    ab_by_id = {str(row["ruler_id"]): row for row in ab_records}
    source_groups_by_ref = _qin_tang_campaign_groups_by_ref(workspace_root)
    direction_payload = json.loads(
        (workspace_root / QIN_TANG_D_DIRECTION_PATH).read_text(encoding="utf-8")
    )
    direction_by_id = {
        str(item["ruler_id"]): item for item in direction_payload["records"]
    }
    founding_refs_by_name = _qin_tang_founding_refs_by_name(workspace_root)
    curated_high_grade_failures = {
        "RULER-SHADOW-杨坚": ["SUI-LEAD-SUI-GOGURYEO-598"],
        "RULER-TANG-LICHUN": ["CAMPAIGN-TANG-238-01"],
    }
    for c_row in c_records:
        ruler_id = str(c_row.get("ruler_id") or "")
        groups = [str(ref) for ref in c_row.get("independent_task_groups") or ()]
        if len(groups) != len(set(groups)) or int(c_row["independent_task_count"]) != len(groups):
            raise ValueError(f"{c_row['ruler_name']}的C独立任务不是唯一父周期集合")
        if ruler_id not in ab_by_id:
            c_row["component_join_status"] = "C_ONLY_PENDING_AB"
            continue
        if not ruler_id.startswith(("RULER-FD-", "RULER-NS-", "RULER-SS-", "RULER-YUAN-", "RULER-MING-")):
            founding_refs = founding_refs_by_name.get(str(c_row["ruler_name"]), set())
            settled_refs = [
                str(ref) for ref in c_row.get("settled_event_refs") or ()
            ]
            consumed_founding_refs = [ref for ref in settled_refs if ref in founding_refs]
            excluded_groups: set[str] = set(groups).intersection(founding_refs)
            for ref in consumed_founding_refs:
                try:
                    excluded_groups.add(
                        _resolve_qin_tang_failure_group(
                            ref, groups, source_groups_by_ref.get(ref, set())
                        )
                    )
                except ValueError:
                    # Some legacy C rows already omitted the corresponding parent
                    # group while retaining the raw trace ref. Removing the trace is
                    # sufficient and must not invent a replacement group.
                    continue
            groups = [group for group in groups if group not in excluded_groups]
            c_row["independent_task_groups"] = groups
            c_row["independent_task_count"] = len(groups)
            c_row["settled_event_refs"] = [
                ref for ref in settled_refs if ref not in founding_refs
            ]
            c_row["excluded_founding_unification_refs"] = list(
                dict.fromkeys([*consumed_founding_refs, *sorted(excluded_groups)])
            )
            if (
                c_row.get("C_overall_grade") not in {"UNKNOWN", "C-N"}
                and _axis_grade(c_row["C_overall_grade"], "C") >= 4
            ):
                c_row["major_system_failure_refs"] = curated_high_grade_failures.get(
                    ruler_id, []
                )
            else:
                c_row["major_system_failure_refs"] = [
                    str(ref)
                    for ref in c_row.get("major_system_failure_refs") or ()
                    if str(ref) not in excluded_groups
                    and str(ref) not in founding_refs
                ]
            c_row["major_system_failure_refs"] = list(
                dict.fromkeys(
                    _resolve_qin_tang_failure_group(
                        str(ref), groups, source_groups_by_ref.get(str(ref), set())
                    )
                    for ref in c_row.get("major_system_failure_refs") or ()
                )
            )
            major_success_source_refs = list(
                direction_by_id.get(ruler_id, {}).get("c_major_success_refs") or ()
            )
            major_success_source_refs = [
                ref for ref in major_success_source_refs if ref not in founding_refs
            ]
            resolved_successes: list[str] = []
            for ref in major_success_source_refs:
                try:
                    resolved_successes.append(
                        _resolve_qin_tang_failure_group(
                            str(ref), groups, source_groups_by_ref.get(str(ref), set())
                        )
                    )
                except ValueError:
                    # A D return cycle outside the current C task portfolio cannot
                    # be used to satisfy the C major-victory gate.
                    continue
            c_row["major_system_success_refs"] = list(
                dict.fromkeys(resolved_successes)
            )
            c_axis_adjudication = direction_by_id.get(ruler_id, {}).get(
                "c_axis_adjudication"
            )
            if c_axis_adjudication:
                c1, c2, c3 = (
                    int(c_axis_adjudication[key]) for key in ("C1", "C2", "C3")
                )
                overall, rate, points, surplus = _c_score(c1, c2, c3)
                lower, upper = (
                    (0, 29), (30, 44), (45, 59),
                    (60, 74), (75, 89), (90, 100),
                )[min(c1, c2, c3)]
                c_row.update({
                    "combat_delivery_grade": f"C1-{c1}",
                    "operational_sustainability_cap": f"C2-{c2}",
                    "system_reliability_cap": f"C3-{c3}",
                    "C_overall_grade": overall,
                    "C_score_rate": rate,
                    "C_score_points": points,
                    "C_score_support_surplus": surplus,
                    "C_score_band": {"lower_rate": lower, "upper_rate": upper},
                    "cap_reasons": [str(c_axis_adjudication["reason"])],
                })
                c_row["major_system_failure_refs"] = list(
                    dict.fromkeys(
                        str(ref)
                        for ref in c_axis_adjudication.get(
                            "major_system_failure_group_refs", ()
                        )
                    )
                )
        if c_row.get("C_overall_grade") not in {"UNKNOWN", "C-N"}:
            _apply_c_task_evidence_ceiling(c_row)
            _apply_c_major_victory_gate(c_row)
            _apply_c_within_band_position(c_row)
        ab_axis_adjudication = direction_by_id.get(ruler_id, {}).get(
            "ab_axis_adjudication"
        )
        if ab_axis_adjudication:
            ab_row = ab_by_id[ruler_id]
            axes = dict(ab_row["axes"])
            for axis in ("A1", "A2"):
                if axis in ab_axis_adjudication:
                    axes[axis] = _axis_a(axis, ab_axis_adjudication[axis])
            for axis in ("B1", "B2", "B4"):
                if axis in ab_axis_adjudication:
                    axes[axis] = _axis_b(axis, ab_axis_adjudication[axis])
            ab_row["axes"] = axes
            ab_row["AB_score_points"] = round(
                sum(float(axes[axis]["axis_points"]) for axis in ("A1", "A2", "B1", "B2", "B4")),
                2,
            )
            ab_row["adjudication_method"] = "CURRENT_CONTRACT_AXIS_ADJUDICATION"
        c_row["parent_cycle_merge_adjudications"] = list(
            c_row.get("parent_cycle_merge_adjudications") or ()
        )
        c_row["parent_cycle_reference_policy"] = (
            "RAW_SETTLED_EVENT_REFS_PLUS_CANONICAL_INDEPENDENT_TASK_GROUPS"
        )
        ab_row = ab_by_id[ruler_id]
        if not ruler_id.startswith(("RULER-FD-", "RULER-NS-", "RULER-SS-", "RULER-YUAN-", "RULER-MING-")):
            founding_refs = founding_refs_by_name.get(str(c_row["ruler_name"]), set())
            ab_row["evidence_event_refs"] = [
                str(ref)
                for ref in ab_row.get("evidence_event_refs") or ()
                if str(ref) not in founding_refs
            ]
            ab_row["excluded_founding_unification_refs"] = list(
                c_row.get("excluded_founding_unification_refs") or ()
            )
        ab_row["evidence_event_refs"] = list(
            dict.fromkeys(
                [
                    *(str(ref) for ref in ab_row.get("evidence_event_refs") or ()),
                    *(str(ref) for ref in c_row.get("settled_event_refs") or ()),
                ]
            )
        )
        ab_row["parent_cycle_refs"] = groups
        ab_row["defense_event_count"] = len(groups)
        ab_row["parent_cycle_merge_adjudications"] = list(
            c_row["parent_cycle_merge_adjudications"]
        )
        ab_row["parent_cycle_reference_policy"] = (
            "RAW_EVIDENCE_EVENT_REFS_PLUS_CANONICAL_PARENT_CYCLE_REFS"
        )


def _axis_grade(value: object, axis: str) -> int:
    match = re.search(rf"{axis}(?:S|-)(\d)", str(value))
    if not match:
        raise ValueError(f"无法解析{axis}档位：{value}")
    return int(match.group(1))


def _validate_formal_abc_contracts(
    ab_records: Sequence[Mapping[str, Any]],
    c_records: Sequence[Mapping[str, Any]],
) -> None:
    _validate_bc_parent_cycle_alignment(ab_records, c_records)
    ab_ids = {str(row["ruler_id"]) for row in ab_records}
    rate_positions = {
        0: {0, 15, 29}, 1: {30, 37, 44}, 2: {45, 52, 59},
        3: {60, 67, 74}, 4: {75, 82, 89}, 5: {90, 95, 100},
    }
    for row in ab_records:
        axes = row["axes"]
        for key in ("A1", "A2"):
            axis = axes[key]
            if axis.get("assessment_scope") is not None and (
                axis["assessment_scope"] != "OVERALL_FRONTIER_STRATEGIC_SITUATION"
            ):
                raise ValueError(f"{row['ruler_name']}的{key}整体边疆形势口径错误")
            start = _axis_grade(axis["start"], key)
            end = _axis_grade(axis["end"], key)
            active_segments = axis.get("active_window_segments") or ()
            attributable_delta = (
                sum(int(segment["delta"]) for segment in active_segments)
                if active_segments
                else end - start
            )
            observed_base = max(0, min(100, 12 * end + 10 * attributable_delta))
            if axis.get("transition_attribution") == "FIRST_ITEM_OWNED_EXCLUDED":
                raise ValueError(f"{row['ruler_name']}的{key}不得按第一项归属整轴清零")
            expected_base = observed_base
            expected_value = max(
                0, min(100, expected_base + int(axis.get("ceiling_bonus") or 0))
            )
            if int(axis["base_trajectory_value"]) != expected_base or int(
                axis["trajectory_value"]
            ) != expected_value:
                raise ValueError(f"{row['ruler_name']}的{key}轨迹公式不一致")
            if abs(float(axis["axis_points"]) - expected_value * 0.4) > 0.011:
                raise ValueError(f"{row['ruler_name']}的{key}得分不一致")
        for key, weight in (("B1", 0.25), ("B2", 0.30), ("B4", 0.25)):
            axis = axes[key]
            if axis.get("assessment_scope") is not None and (
                axis["assessment_scope"] != "CONTROL_SCALE_AND_INTENSITY"
            ):
                raise ValueError(f"{row['ruler_name']}的{key}规模与控制强度口径错误")
            grade = _axis_grade(axis["grade"], key)
            rate = int(axis["score_rate"])
            if rate not in rate_positions[grade] or abs(
                float(axis["axis_points"]) - rate * weight
            ) > 0.051:
                raise ValueError(f"{row['ruler_name']}的{key}档内赋分不一致")
        if set(row.get("boundary_stage_refs") or ()).intersection(
            row.get("boundary_stage_excluded_refs") or ()
        ):
            raise ValueError(f"{row['ruler_name']}的A/B边界阶段重复消费")
        if row.get("terminal_polity_collapse") and any(
            _axis_grade(axes[key]["grade"], key) != 0
            for key in ("B1", "B2", "B4")
        ):
            raise ValueError(f"{row['ruler_name']}的亡国交班未执行B项归零门禁")
    for row in c_records:
        if str(row["ruler_id"]) not in ab_ids:
            continue
        if row.get("C_overall_grade") == "UNKNOWN":
            if (
                any(row.get(field) != "UNKNOWN" for field in (
                    "combat_delivery_grade",
                    "operational_sustainability_cap",
                    "system_reliability_cap",
                ))
                or row.get("C_score_points") is not None
                or row.get("score_ready") is not False
            ):
                raise ValueError(f"{row['ruler_name']}的C未知状态合同不完整")
            continue
        if row.get("C_overall_grade") == "C-N":
            if (
                row.get("no_system_stress_disposition")
                != "CONFIRMED_NOT_APPLICABLE"
                or any(row.get(field) != "NOT_APPLICABLE_NO_SYSTEM_STRESS" for field in (
                    "combat_delivery_grade",
                    "operational_sustainability_cap",
                    "system_reliability_cap",
                ))
                or float(row.get("C_score_points") or 0) != 0.0
                or int(row.get("independent_task_count") or 0) != 0
                or row.get("score_ready") is not True
            ):
                raise ValueError(f"{row['ruler_name']}的C-N无实战任务合同不完整")
            continue
        grades = [
            _axis_grade(row[field], axis)
            for field, axis in (
                ("combat_delivery_grade", "C1"),
                ("operational_sustainability_cap", "C2"),
                ("system_reliability_cap", "C3"),
            )
        ]
        overall = _axis_grade(row["C_overall_grade"], "C")
        tasks = int(row["independent_task_count"])
        if overall != min(grades):
            raise ValueError(f"{row['ruler_name']}的C总体档不是三轴最低档")
        if tasks <= 1 and (grades[0] > 3 or grades[2] > 3):
            raise ValueError(f"{row['ruler_name']}的C项单任务超过证据上限")
        if tasks == 2 and (grades[0] > 4 or grades[2] > 4):
            raise ValueError(f"{row['ruler_name']}的C项双任务超过证据上限")


def _aggregate_parent_cycle_audit(cycle: Mapping[str, Any]) -> dict[str, Any]:
    phases = list(cycle["phases"])
    canonical_ref = str(cycle["campaign_group_ref"])
    member_refs = {
        str(ref) for ref in cycle.get("merged_campaign_group_refs") or ()
    } or {canonical_ref}
    phase_group_refs = {
        str(phase.get("campaign_group_ref"))
        for phase in phases
        if phase.get("campaign_group_ref")
    }
    if not phase_group_refs.issubset(member_refs):
        raise ValueError(
            f"{canonical_ref}父级合并含未声明成员阶段："
            f"{sorted(phase_group_refs - member_refs)}"
        )
    binding_identities = {
        (
            str(
                (phase.get("ruler_binding") or {}).get("polity")
                or phase.get("polity_binding")
                or ""
            ),
            str((phase.get("ruler_binding") or {}).get("ruler_id") or ""),
            str((phase.get("ruler_binding") or {}).get("ruler_name") or ""),
        )
        for phase in phases
        if (phase.get("ruler_binding") or {}).get("ruler_id")
    }
    if len(binding_identities) > 1:
        raise ValueError(
            f"{canonical_ref}父级周期混入不同主体或统治窗口："
            f"{sorted(binding_identities)}"
        )
    subject_binding = (
        {
            "polity": next(iter(binding_identities))[0],
            "ruler_id": next(iter(binding_identities))[1],
            "ruler_name": next(iter(binding_identities))[2],
            "status": "SINGLE_SUBJECT_RULER_WINDOW",
        }
        if binding_identities
        else None
    )
    costs, benefits, parent_axis_basis, unknown_axes = _rollup_parent_axes(phases)
    for axis, value in dict(cycle.get("parent_cost_axes") or {}).items():
        if axis in costs:
            parsed = _grade_number(value, axis)
            if parsed is None:
                raise ValueError(f"{cycle['campaign_group_ref']}父级成本轴{axis}非法")
            costs[axis] = parsed
            unknown_axes = [item for item in unknown_axes if item != axis]
    for axis, value in dict(cycle.get("parent_benefit_axes") or {}).items():
        if axis in benefits:
            parsed = _grade_number(value, axis)
            if parsed is None:
                raise ValueError(f"{cycle['campaign_group_ref']}父级收益轴{axis}非法")
            benefits[axis] = parsed
            unknown_axes = [item for item in unknown_axes if item != axis]
    route = str(cycle.get("d_route") or _semantic_internal_route(phases))
    s_attributable = True
    exposure_index = _cycle_exposure_index(
        costs, benefits, s_attributable=s_attributable
    )
    if bool(cycle.get("large_rebellion_admitted")):
        material = True
        material_admission_basis = "ALL_RULERS_LARGE_REBELLION_AUDIT"
    elif bool(cycle.get("material_cumulative_admitted")):
        material = True
        material_admission_basis = "EXPLICIT_CUMULATIVE_STRATEGIC_BURDEN"
    elif bool(cycle.get("material_internal_admitted")):
        material = True
        material_admission_basis = "EXPLICIT_MAJOR_INTERNAL_STRATEGIC_ADMISSION"
    elif route in {"D_INTERNAL_STRATEGIC", "D_INTERNAL_RESTORATION"}:
        material = False
        material_admission_basis = "ORDINARY_INTERNAL_EVENT_EXCLUDED"
    else:
        material = _major_non_rebellion_cycle(costs, benefits)
        material_admission_basis = (
            "MAJOR_STRATEGIC_INVESTMENT_FACTS"
            if material
            else "LOW_INTENSITY_OBSERVATION_EXCLUDED"
        )
    asset_component_profile = _asset_component_profile(
        int(costs["A"]),
        {"asset_component_split": cycle.get("asset_component_split")}
        if cycle.get("asset_component_split")
        else {},
    )
    asset_residual_grade = asset_component_profile[
        "residual_or_permanent_harm_grade"
    ]
    if unknown_axes:
        final_class = "UNKNOWN"
        class_rationale = "父级关键成本或终局收益轴仍为UNKNOWN，禁止以0或负收益代填。"
    else:
        final_class, class_rationale = _parent_cycle_return_class(
            costs,
            benefits,
            s_attributable=s_attributable,
            route=route,
            asset_residual_grade=(
                int(asset_residual_grade)
                if asset_residual_grade is not None
                else None
            ),
        )
    high_return_tier = _high_return_tier(benefits, final_class)
    national_negative = final_class == "NEGATIVE_RETURN" and (
        costs["P"] >= 5
        or costs["S"] >= 5
        or int(asset_residual_grade or 0) >= 5
        or max(benefits["SN"], benefits["BCN"]) >= 5
    )
    p_inference_evidence = []
    for phase in phases:
        if not phase.get("P_inference"):
            continue
        inference = {
            "phase_id": str(phase.get("phase_id") or ""),
            **dict(phase["P_inference"]),
        }
        inference.setdefault(
            "P_scoring",
            str((phase.get("cost_axes") or {}).get("P") or "UNKNOWN"),
        )
        p_inference_evidence.append(inference)
    cost_evidence: dict[str, list[dict[str, Any]]] = {}
    for axis in ("P", "S", "M", "A"):
        axis_evidence: list[dict[str, Any]] = []
        for phase in phases:
            raw_evidence = (phase.get("cost_evidence") or {}).get(axis)
            if not raw_evidence:
                continue
            evidence_items = (
                [str(raw_evidence)]
                if isinstance(raw_evidence, str)
                else [str(item) for item in raw_evidence]
            )
            axis_evidence.append({
                "phase_id": str(phase.get("phase_id") or ""),
                "evidence": evidence_items,
            })
        cost_evidence[axis] = axis_evidence
    benefit_source_refs = sorted({
        str(ref)
        for phase in phases
        for ref in phase.get("source_anchor_refs") or ()
    })
    return {
        "campaign_group_ref": cycle["campaign_group_ref"], "war_event_refs": cycle["war_event_refs"],
        "phase_ids": cycle["phase_ids"], "return_class": final_class,
        "cost_axes": costs, "benefit_axes": benefits, "material": material,
        "material_exposure_index": exposure_index,
        "material_admission_basis": material_admission_basis,
        "unknown_axes": unknown_axes,
        "high_return_tier": high_return_tier,
        "major_high_return": high_return_tier in {"MAJOR", "TOP"},
        "top_high_return": high_return_tier == "TOP",
        "national_negative": national_negative,
        "route": route,
        "s_attributable": s_attributable,
        "subject_binding": subject_binding,
        "return_class_basis": "PARENT_AXES_DIRECT_MAPPING",
        "return_class_rationale": class_rationale,
        "parent_axis_basis": (
            "EXPLICIT_PARENT_AXIS_ADJUDICATION"
            if cycle.get("parent_cost_axes") or cycle.get("parent_benefit_axes")
            else parent_axis_basis
        ),
        "strategic_result_chain_ref": str(
            cycle.get("strategic_result_chain_ref") or cycle["campaign_group_ref"]
        ),
        "asset_component_profile": asset_component_profile,
        "P_inference_evidence": p_inference_evidence,
        "cost_evidence": cost_evidence,
        "benefit_source_refs": benefit_source_refs,
        "merged_campaign_group_refs": list(cycle.get("merged_campaign_group_refs") or ()),
        "merge_reason": cycle.get("merge_reason"),
        "route_override_reason": cycle.get("route_override_reason"),
    }




def validate_ab_shared_handoffs(
    workspace_root: Path, records: Sequence[Mapping[str, Any]]
) -> None:
    payload = json.loads(
        (workspace_root / AB_HANDOFF_ADJUDICATION_PATH).read_text(encoding="utf-8")
    )
    if payload.get("schema_version") != "third-item-ab-handoff-adjudications-v1":
        raise ValueError("AB共享交班裁决schema错误")
    if payload.get("status") != "CURRENT":
        raise ValueError("AB共享交班裁决不是当前值")
    rows_by_name: dict[str, Mapping[str, Any]] = {}
    for row in records:
        name = str(row["ruler_name"])
        if name in rows_by_name:
            raise ValueError(f"AB共享交班不能按重名主体定位：{name}")
        rows_by_name[name] = row

    declared_pairs: set[tuple[str, str]] = set()
    for sequence in payload.get("direct_sequences") or ():
        names = [str(value) for value in sequence]
        if len(names) < 2:
            raise ValueError("AB直接交班序列至少需要两位主体")
        missing = [name for name in names if name not in rows_by_name]
        if missing:
            raise ValueError("AB直接交班主体缺失：" + ",".join(missing))
        for left_name, right_name in zip(names, names[1:]):
            pair = (left_name, right_name)
            if pair in declared_pairs:
                raise ValueError(f"AB直接交班重复声明：{left_name}->{right_name}")
            declared_pairs.add(pair)
            left = rows_by_name[left_name]
            right = rows_by_name[right_name]
            mismatches: list[str] = []
            for axis in ("A1", "A2"):
                left_end = str(left["axes"][axis]["end"])
                right_start = str(right["axes"][axis]["start"])
                if left_end != right_start:
                    mismatches.append(f"{axis}:{left_end}->{right_start}")
            left_control = float(left["b1_control_equivalents"]["end"])
            right_control = float(right["b1_control_equivalents"]["start"])
            if abs(left_control - right_control) > 1e-9:
                mismatches.append(f"B1:{left_control}->{right_control}")
            if mismatches:
                raise ValueError(
                    f"AB直接交班快照不一致：{left_name}->{right_name}；"
                    + "；".join(mismatches)
                )

    bridge_pairs: set[tuple[str, str]] = set()
    for bridge in payload.get("state_bridges") or ():
        left_name = str(bridge.get("left_ruler") or "")
        right_name = str(bridge.get("right_ruler") or "")
        pair = (left_name, right_name)
        if not left_name or not right_name or pair in bridge_pairs:
            raise ValueError("AB状态桥主体为空或重复")
        if left_name not in rows_by_name or right_name not in rows_by_name:
            raise ValueError(f"AB状态桥主体缺失：{left_name}->{right_name}")
        if pair in declared_pairs:
            raise ValueError(f"AB交班不得同时声明直接与状态桥：{left_name}->{right_name}")
        if not str(bridge.get("bridge_type") or "").strip() or not str(
            bridge.get("rationale") or ""
        ).strip():
            raise ValueError(f"AB状态桥缺少类型或理由：{left_name}->{right_name}")
        bridge_pairs.add(pair)






def _replace_partition_records(
    payload: Mapping[str, Any], records: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    ruler_ids = {str(row["ruler_id"]) for row in records}
    preserved = [dict(row) for row in payload.get("records") or () if str(row.get("ruler_id")) not in ruler_ids]
    current = dict(payload)
    current["records"] = preserved + [dict(row) for row in records]
    return current






def _asset_component_profile(
    asset_grade: int,
    evidence: object,
) -> dict[str, int | str | None]:
    structured = evidence if isinstance(evidence, Mapping) else {}
    component = structured.get("asset_component_split")
    component = component if isinstance(component, Mapping) else {}
    source_refs = [str(ref) for ref in component.get("source_refs") or ()]

    def explicit_grade(field: str) -> int | None:
        value = component.get(field)
        if value is None:
            return 0 if asset_grade == 0 else None
        parsed = int(value)
        if not 0 <= parsed <= asset_grade:
            raise ValueError(f"A组件{field}={parsed}超出gross A{asset_grade}")
        return parsed

    reusable_grade = explicit_grade("reusable_input_grade")
    loss_grade = explicit_grade("consumed_or_lost_asset_grade")
    destruction_grade = explicit_grade("permanent_destruction_grade")
    residual_grade = explicit_grade("residual_or_permanent_harm_grade")
    if asset_grade == 0:
        status = "NO_ASSET_BURDEN"
    elif component and source_refs and all(
        value is not None
        for value in (reusable_grade, loss_grade, destruction_grade, residual_grade)
    ):
        status = "EXPLICIT_STRUCTURED_COMPONENT_SPLIT"
    else:
        status = "UNRESOLVED_REUSE_LOSS_DESTRUCTION_SPLIT"
    return {
        "gross_commitment_grade": asset_grade,
        "reusable_input_grade": reusable_grade,
        "consumed_or_lost_asset_grade": loss_grade,
        "permanent_destruction_grade": destruction_grade,
        "residual_or_permanent_harm_grade": residual_grade,
        "component_split_status": status,
        "source_refs": source_refs,
    }


def _parent_cycle_return_class(
    costs: Mapping[str, int],
    benefits: Mapping[str, int],
    *,
    s_attributable: bool,
    route: str = "D_EXTERNAL_OR_FRONTIER",
    asset_residual_grade: int | None = None,
    benefit_claim_bundle: Mapping[str, Any] | None = None,
) -> tuple[str, str]:
    positive_axes = {key: int(benefits[key]) for key in ("SB", "BCP", "WR")}
    negative_axes = {key: int(benefits[key]) for key in ("SN", "BCN")}
    cost_values = [int(costs[key]) for key in ("P", "M", "A")]
    if s_attributable:
        cost_values.append(int(costs["S"]))
    highest_cost = max(cost_values)
    highest_positive = max(positive_axes.values())
    highest_negative = max(negative_axes.values())
    irreversible_loss = max(
        int(costs["P"]),
        int(asset_residual_grade or 0),
        int(costs["S"]) if s_attributable else 0,
        highest_negative,
    )
    cost_profile = tuple(sorted(cost_values, reverse=True)[:3])
    cost_profile = cost_profile + (0,) * (3 - len(cost_profile))
    claim_bundle = dict(benefit_claim_bundle or {})
    unresolved_high_axes = list(claim_bundle.get("unresolved_high_axes") or ())
    if unresolved_high_axes:
        return (
            "UNKNOWN",
            "高收益轴缺少显式历史对象或轴别终局证据："
            + ",".join(unresolved_high_axes),
        )
    suppressed_axes = set(claim_bundle.get("supporting_axis_refs") or ())
    benefit_strengths = [
        0
        if axis in suppressed_axes
        else PARENT_CYCLE_BENEFIT_STRENGTH[axis][max(0, min(5, grade))]
        for axis, grade in positive_axes.items()
    ]
    benefit_profile = tuple(sorted(benefit_strengths, reverse=True))
    burden_profile = tuple(
        sorted((*cost_profile, highest_negative), reverse=True)[:3]
    )
    if highest_cost == 0 and highest_positive == 0 and highest_negative == 0:
        result = "UNKNOWN"
    elif route == "D_INTERNAL_RESTORATION":
        if highest_negative >= 3 and highest_negative >= highest_positive:
            result = "NEGATIVE_RETURN"
        elif irreversible_loss >= 4 and irreversible_loss > highest_positive:
            result = "NEGATIVE_RETURN"
        elif highest_positive == 0:
            result = "LOW_RETURN"
        elif benefit_profile < burden_profile:
            result = "LOW_RETURN"
        else:
            result = "PROPORTIONATE_RETURN"
    elif highest_negative >= 4 and highest_positive <= highest_negative:
        result = "NEGATIVE_RETURN"
    elif (
        route == "D_INTERNAL_STRATEGIC"
        and cost_profile >= (3, 3, 3)
        and highest_positive <= 1
    ):
        result = "NEGATIVE_RETURN"
    elif highest_positive == 0:
        result = "NEGATIVE_RETURN" if irreversible_loss >= 4 else "LOW_RETURN"
    elif irreversible_loss >= 4 and benefit_profile < burden_profile:
        result = "NEGATIVE_RETURN"
    elif highest_negative >= highest_positive and highest_negative > 0:
        result = "NEGATIVE_RETURN" if highest_cost >= highest_positive else "LOW_RETURN"
    elif max(benefit_strengths, default=0) >= 3 and benefit_profile > burden_profile:
        result = "HIGH_RETURN"
    elif benefit_profile >= burden_profile:
        result = "PROPORTIONATE_RETURN"
    elif highest_positive > highest_negative:
        result = "LOW_RETURN"
    else:
        result = "NEGATIVE_RETURN"
    rationale = (
        f"父级轴直接裁决：成本P/S/M/A={costs['P']}/{costs['S']}/{costs['M']}/{costs['A']}，"
        f"收益SB/SN/BCP/BCN/WR={benefits['SB']}/{benefits['SN']}/{benefits['BCP']}/"
        f"{benefits['BCN']}/{benefits['WR']}，收益强度剖面={benefit_profile}，"
        f"成本负收益剖面={burden_profile}，路由={route}；裁为{result}。"
        f"A残余毁损={asset_residual_grade if asset_residual_grade is not None else 'UNRESOLVED'}。"
        f"收益claim={claim_bundle.get('claim_ids') or []}；旁证轴不重复入主贡献。"
    )
    return result, rationale


def _cycle_exposure_index(
    costs: Mapping[str, int],
    benefits: Mapping[str, int],
    *,
    s_attributable: bool,
) -> int:
    """Return a descriptive exposure index; it never decides admission."""

    burden_values = [int(costs[key]) for key in ("P", "M", "A")]
    if s_attributable:
        burden_values.append(int(costs["S"]))
    burden_values.extend(int(benefits[key]) for key in ("SN", "BCN"))
    burden_profile = sorted(burden_values, reverse=True)[:3]
    burden_profile += [0] * (3 - len(burden_profile))
    highest_benefit = max(int(benefits[key]) for key in ("SB", "BCP", "WR"))
    exposure_index = max(
        2 * burden_profile[0],
        sum(burden_profile),
        2 * highest_benefit,
    )
    return exposure_index


def _major_non_rebellion_cycle(
    costs: Mapping[str, int], benefits: Mapping[str, int]
) -> bool:
    """Admit major external campaigns/projects without reusing Q or I.

    One level-4 strategic consequence is sufficient.  A project with at least
    two independently evidenced level-3 cost axes is also major (for example a
    large military engineering programme).  Ordinary internal unrest never
    reaches D through this helper; it requires the all-ruler rebellion audit.
    """

    values = [int(costs[key]) for key in ("P", "S", "M", "A")]
    values.extend(int(benefits[key]) for key in ("SB", "SN", "BCP", "BCN", "WR"))
    major_cost_axes = sum(int(costs[key]) >= 3 for key in ("P", "S", "M", "A"))
    major_positive_axes = sum(
        int(benefits[key]) >= 3 for key in ("SB", "BCP", "WR")
    )
    return (
        max(values) >= 4
        or major_cost_axes >= 2
        or (major_cost_axes >= 1 and major_positive_axes >= 2)
    )


def _high_return_tier(
    benefits: Mapping[str, int],
    return_class: str,
    benefit_claim_bundle: Mapping[str, Any] | None = None,
) -> str | None:
    if return_class != "HIGH_RETURN":
        return None
    bundle = dict(benefit_claim_bundle or {})
    primary_axis = str(bundle.get("primary_axis") or "")
    primary_grade = int(bundle.get("primary_grade") or 0)
    if primary_axis == "SB":
        return "TOP" if primary_grade >= 5 else "MAJOR" if primary_grade >= 4 else "ORDINARY"
    if primary_axis == "BCP":
        return "TOP" if primary_grade >= 5 else "MAJOR" if primary_grade >= 4 else "ORDINARY"
    if primary_axis == "WR":
        return "MAJOR" if primary_grade >= 5 else "ORDINARY"
    return "ORDINARY"


def _semantic_internal_route(phases: Sequence[Mapping[str, Any]]) -> str:
    roles = {str(phase.get("subject_role") or "") for phase in phases}
    if any(
        role.startswith(
            (
                "COUNTERINSURGENCY",
                "COUNTERREBELLION",
                "COUNTERMUTINY",
                "COUNTER_MUTINY",
                "COUNTERCOUP",
                "SUPPRESSOR",
                "MUTINY_VICTIM",
                "DEFENDER_ADMIN_CIVILIAN",
                "INTERNAL_SECURITY",
                "MILITARY_PACIFICATION",
                "PACIFICATION",
            )
        )
        for role in roles
    ):
        return "D_INTERNAL_RESTORATION"
    return "D_EXTERNAL_OR_FRONTIER"


def _rollup_parent_axes(
    phases: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, int], dict[str, int], str, list[str]]:
    """Collapse one ordered phase or require an explicit multi-phase terminal adjudication."""
    sequence_numbers: list[int | None] = []
    for phase in phases:
        match = re.search(r"-P(\d+)$", str(phase.get("phase_id") or ""))
        sequence_numbers.append(int(match.group(1)) if match else None)
    ordered = list(phases)
    ordered_status = "SINGLE_PHASE"
    if len(phases) > 1:
        if any(number is None for number in sequence_numbers):
            ordered_status = "MULTI_PHASE_ORDER_UNRESOLVED"
        elif len(set(sequence_numbers)) != len(sequence_numbers):
            ordered_status = "MULTI_PHASE_ORDER_DUPLICATED"
        else:
            ordered = [
                phase
                for _, phase in sorted(
                    zip(sequence_numbers, phases), key=lambda item: int(item[0])
                )
            ]
            ordered_status = "MULTI_PHASE_ORDERED_REQUIRES_EXPLICIT_TERMINAL"
    costs: dict[str, int] = {}
    unknown_axes: set[str] = set()
    for axis in ("P", "S", "M", "A", "WC"):
        grades = [
            _grade_number((phase.get("cost_axes") or {}).get(axis), axis)
            for phase in ordered
        ]
        known = [grade for grade in grades if grade is not None]
        if axis == "S" and grades:
            costs[axis] = int(grades[-1] or 0)
            if grades[-1] is None:
                unknown_axes.add(axis)
        else:
            costs[axis] = max(known, default=0)
        if not known:
            unknown_axes.add(axis)
    benefits = {axis: 0 for axis in ("SB", "SN", "BCP", "BCN", "WR")}
    if len(ordered) > 1:
        unknown_axes.update(benefits)
        return costs, benefits, ordered_status, sorted(unknown_axes)

    phase = ordered[0] if ordered else {}
    for positive_axis, negative_axis, field in (
        ("SB", "SN", "strategic_security"),
        ("BCP", "BCN", "border_control"),
    ):
        values = phase.get(field) or {}
        positive = _embedded_grade_number(
            values.get(positive_axis) if isinstance(values, Mapping) else values,
            positive_axis,
        )
        negative = _embedded_grade_number(
            values.get(negative_axis) if isinstance(values, Mapping) else values,
            negative_axis,
        )
        if positive is not None or negative is not None:
            positive = int(positive or 0)
            negative = int(negative or 0)
            if positive > negative:
                benefits[positive_axis] = positive
            elif negative > positive:
                benefits[negative_axis] = negative
            elif positive > 0:
                unknown_axes.update((positive_axis, negative_axis))
            else:
                unknown_axes.discard(positive_axis)
                unknown_axes.discard(negative_axis)
        else:
            unknown_axes.update((positive_axis, negative_axis))
    wr_grade = _grade_number(phase.get("material_return"), "WR")
    benefits["WR"] = int(wr_grade or 0)
    if wr_grade is None:
        unknown_axes.add("WR")
    return costs, benefits, "SINGLE_PHASE_AXIS_DIRECT", sorted(unknown_axes)










def _align_bc_to_system_stress_parent_cycles(
    workspace_root: Path,
    ab_records: Sequence[dict[str, Any]],
    c_records: Sequence[dict[str, Any]],
    d_records: Sequence[Mapping[str, Any]],
) -> None:
    """Use one parent-cycle portfolio for B audit thickness and C stress tests."""
    outcome_payload = json.loads(
        (workspace_root / C_OUTCOME_ADJUDICATION_PATH).read_text(encoding="utf-8")
    )
    if (
        outcome_payload.get("schema_version")
        != "third-item-c-outcome-adjudications-v1"
        or outcome_payload.get("status") != "CURRENT"
    ):
        raise ValueError("第三项C重大结果跨分区裁决合同非法")
    outcome_adjudications = {
        str(item["ruler_id"]): dict(item)
        for item in outcome_payload.get("adjudications") or ()
    }
    if len(outcome_adjudications) != len(outcome_payload.get("adjudications") or ()):
        raise ValueError("第三项C重大结果跨分区裁决对象重复")
    task_return_class_adjudications = {
        str(item["ruler_id"]): dict(item)
        for item in outcome_payload.get("task_return_class_adjudications") or ()
    }
    if len(task_return_class_adjudications) != len(
        outcome_payload.get("task_return_class_adjudications") or ()
    ):
        raise ValueError("第三项C逐任务回报分类裁决对象重复")
    founder_reviews = {
        str(item["ruler_id"]): dict(item)
        for item in outcome_payload.get("founder_capability_reviews") or ()
    }
    if len(founder_reviews) != len(outcome_payload.get("founder_capability_reviews") or ()):
        raise ValueError("第三项C王朝奠基人能力复核对象重复")
    founder_no_capability_reviews = {
        str(item["ruler_name"]): dict(item)
        for item in outcome_payload.get("founder_no_capability_reviews") or ()
    }
    if len(founder_no_capability_reviews) != len(
        outcome_payload.get("founder_no_capability_reviews") or ()
    ):
        raise ValueError("第三项C无可消费能力引用的奠基人复核对象重复")
    founder_current_c_reviews = {
        str(item["ruler_name"]): dict(item)
        for item in outcome_payload.get("founder_current_c_reviews") or ()
    }
    if len(founder_current_c_reviews) != len(
        outcome_payload.get("founder_current_c_reviews") or ()
    ):
        raise ValueError("第三项C沿用当前能力结论的奠基人复核对象重复")
    # Partition writers may rebuild one dynasty at a time.  Review closure is
    # therefore checked against the records actually supplied to this call;
    # unrelated founder reviews must not make a scoped deterministic rebuild
    # fail as "out of scope".
    supplied_ruler_ids = {str(row["ruler_id"]) for row in c_records}
    founder_reviews = {
        ruler_id: row
        for ruler_id, row in founder_reviews.items()
        if ruler_id in supplied_ruler_ids
    }
    within_band_adjudications = {
        str(item["ruler_name"]): dict(item)
        for item in outcome_payload.get("within_band_adjudications") or ()
    }
    if len(within_band_adjudications) != len(
        outcome_payload.get("within_band_adjudications") or ()
    ):
        raise ValueError("第三项C档内位置裁决对象重复")
    talent_payload = load_talent_registry(
        workspace_root / MILITARY_TALENT_REGISTRY_PATH
    )
    talent_profiles_by_ref = {
        str(profile["profile_ref"]): profile
        for profile in talent_payload.get("profiles") or ()
    }
    first_item_c_payload = json.loads(
        (workspace_root / FIRST_ITEM_C_SETTLEMENT_PATH).read_text(encoding="utf-8")
    )
    first_item_capability_refs_by_id: dict[str, set[str]] = {}
    first_item_major_success_refs_by_id: dict[str, set[str]] = defaultdict(set)
    first_item_major_failure_refs_by_id: dict[str, set[str]] = defaultdict(set)
    first_item_source_refs_by_id: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: defaultdict(set)
    )
    first_item_founder_ids: set[str] = set()
    first_item_founder_by_name: dict[str, Mapping[str, Any]] = {}
    for first_row in first_item_c_payload.get("records") or ():
        refs = {
            str(item["campaign_group_id"])
            for axis in (first_row.get("C1") or {}, first_row.get("C2") or {})
            for field in ("campaign_results", "frontline_results")
            for item in axis.get(field) or ()
            if item.get("campaign_group_id")
        }
        ruler_id = str(first_row["ruler_id"])
        first_item_capability_refs_by_id[ruler_id] = refs
        if first_row.get("score_applicable"):
            first_item_founder_ids.add(ruler_id)
            first_item_founder_by_name[str(first_row["ruler_name"])] = first_row
        for item in (first_row.get("C1") or {}).get("campaign_results") or ():
            ref = str(item.get("campaign_group_id") or "")
            first_item_source_refs_by_id[ruler_id][ref].update(
                str(source_ref)
                for source_ref in item.get("source_refs") or ()
                if source_ref
            )
            # 第一项个人战果只能为第三项C提供候选事实，不能把每一条A档
            # 个人胜负机械升级为“重大体系胜绩/失败”。自动桥接只接收
            # S-/S/S+；A档若确实改变体系判断，必须在C人物裁决中显式列入。
            if ref not in refs or str(item.get("personal_result_tier") or "") not in {
                "S-", "S", "S+",
            }:
                continue
            if item.get("result_direction") == "positive":
                first_item_major_success_refs_by_id[ruler_id].add(ref)
            elif item.get("result_direction") == "negative":
                first_item_major_failure_refs_by_id[ruler_id].add(ref)
    registry = load_battle_registry(workspace_root / REGISTRY_PATH)

    def nested_source_refs(value: object) -> set[str]:
        found: set[str] = set()
        if isinstance(value, Mapping):
            for key, child in value.items():
                if key == "source_refs" and isinstance(child, Sequence) and not isinstance(child, (str, bytes)):
                    found.update(str(ref) for ref in child if ref)
                else:
                    found.update(nested_source_refs(child))
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            for child in value:
                found.update(nested_source_refs(child))
        return found

    registry_source_refs_by_task: dict[str, set[str]] = defaultdict(set)
    for record in registry.get("records") or ():
        source_refs = nested_source_refs(record)
        for field in ("war_event_id", "source_target_ref", "campaign_group_ref"):
            task_ref = str(record.get(field) or "")
            if task_ref:
                registry_source_refs_by_task[task_ref].update(source_refs)
    opponent_systems_by_ref = _opponent_systems_by_ref(workspace_root, registry)
    public_unification_portfolio_by_ref = {
        str(row["war_event_id"]): str(row.get("unification_portfolio_ref") or "")
        for row in registry.get("records") or ()
        if row.get("disposition") == "REGISTERED_UNIFICATION"
        and row.get("war_event_id")
    }
    ab_by_id = {str(row["ruler_id"]): row for row in ab_records}
    d_by_id = {str(row["ruler_id"]): row for row in d_records}
    review_required_ids = {
        str(row["ruler_id"])
        for row in c_records
        if str(row["ruler_id"]) in first_item_founder_ids
        and first_item_capability_refs_by_id.get(str(row["ruler_id"]))
    }
    if set(founder_reviews) != review_required_ids:
        raise ValueError(
            "第三项C王朝奠基人能力复核未全量闭合: "
            f"缺少={sorted(review_required_ids - set(founder_reviews))};"
            f"越界={sorted(set(founder_reviews) - review_required_ids)}"
        )
    no_capability_review_required_names = {
        str(row["ruler_name"])
        for row in c_records
        if not row.get("score_ready")
        and str(row["ruler_name"]) in first_item_founder_by_name
        and not first_item_capability_refs_by_id.get(
            str(first_item_founder_by_name[str(row["ruler_name"])]["ruler_id"])
        )
    }
    allowed_no_capability_review_names = {
        name
        for name, row in first_item_founder_by_name.items()
        if not first_item_capability_refs_by_id.get(str(row["ruler_id"]))
    }
    if (
        not no_capability_review_required_names.issubset(founder_no_capability_reviews)
        or not set(founder_no_capability_reviews).issubset(
            allowed_no_capability_review_names
        )
    ):
        raise ValueError(
            "第三项C无能力引用奠基人复核未闭合: "
            f"缺少={sorted(no_capability_review_required_names - set(founder_no_capability_reviews))};"
            f"越界={sorted(set(founder_no_capability_reviews) - allowed_no_capability_review_names)}"
        )
    current_c_review_required_names = {
        str(row["ruler_name"])
        for row in c_records
        if row.get("score_ready")
        and str(row["ruler_name"]) in first_item_founder_by_name
        and str(row["ruler_id"]) not in founder_reviews
        and str(row["ruler_name"]) not in founder_no_capability_reviews
    }
    if (
        not current_c_review_required_names.issubset(founder_current_c_reviews)
        or not set(founder_current_c_reviews).issubset(first_item_founder_by_name)
    ):
        raise ValueError(
            "第三项C沿用当前结论的奠基人复核未闭合: "
            f"缺少={sorted(current_c_review_required_names - set(founder_current_c_reviews))};"
            f"越界={sorted(set(founder_current_c_reviews) - set(first_item_founder_by_name))}"
        )
    for c_row in c_records:
        ruler_id = str(c_row["ruler_id"])
        first_item_source_row = first_item_founder_by_name.get(
            str(c_row["ruler_name"])
        )
        first_item_source_id = str(
            (first_item_source_row or {}).get("ruler_id") or ruler_id
        )
        c_row["cross_item_identity"] = {
            "join_key": str(c_row["ruler_name"]),
            "first_item_ruler_id": (
                first_item_source_id if first_item_source_row is not None else None
            ),
            "third_item_ruler_id": ruler_id,
            "status": (
                "EXPLICIT_NAME_CROSSWALK"
                if first_item_source_row is not None and first_item_source_id != ruler_id
                else "SAME_ID"
                if first_item_source_row is not None
                else "FIRST_ITEM_NOT_APPLICABLE"
            ),
        }
        first_refs_for_c = first_item_capability_refs_by_id.get(
            first_item_source_id, set()
        )
        first_successes_for_c = first_item_major_success_refs_by_id.get(
            first_item_source_id, set()
        )
        first_failures_for_c = first_item_major_failure_refs_by_id.get(
            first_item_source_id, set()
        )
        first_source_refs_for_c = first_item_source_refs_by_id.get(
            first_item_source_id, {}
        )
        # Formal C output is also the next run's input.  Derived gates must be
        # rebuilt from current adjudications rather than carried forward as
        # historical residue.
        c_row.pop("c5_scarcity_gate", None)
        c_row.pop("c5_axis_gate", None)
        c_row["major_system_success_refs"] = [
            ref
            for ref in c_row.get("major_system_success_refs") or ()
            if str(ref) not in first_refs_for_c
        ]
        c_row["major_system_failure_refs"] = [
            ref
            for ref in c_row.get("major_system_failure_refs") or ()
            if str(ref) not in first_refs_for_c
        ]
        d_row = d_by_id[ruler_id]
        metrics = d_row.get("D_portfolio_metrics") or {}
        merge_member_to_canonical = {
            str(member): str(merge["canonical_cycle_ref"])
            for merge in c_row.get("parent_cycle_merge_adjudications") or ()
            for member in merge.get("member_campaign_group_refs") or ()
        }

        first_member_to_canonical: dict[str, str] = {}

        def canonicalize(ref: object) -> str:
            value = str(ref)
            if value in first_refs_for_c:
                return first_member_to_canonical.get(value, value)
            value = merge_member_to_canonical.get(value, value)
            return first_member_to_canonical.get(value, value)

        def canonicalize_first_ref(ref: object) -> str:
            value = str(ref)
            return first_member_to_canonical.get(value, value)

        all_parent_refs = list(
            dict.fromkeys(
                canonicalize(ref)
                for ref in metrics.get("canonical_parent_cycle_refs") or ()
            )
        )
        material_parent_refs = list(
            dict.fromkeys(
                canonicalize(ref)
                for ref in metrics.get("material_parent_cycle_refs") or ()
            )
        )
        outcome_decision = outcome_adjudications.get(ruler_id)
        founder_review = founder_reviews.get(ruler_id)
        founder_no_capability_review = founder_no_capability_reviews.get(
            str(c_row["ruler_name"])
        )
        founder_current_c_review = founder_current_c_reviews.get(
            str(c_row["ruler_name"])
        )
        alias_candidates = list(dict.fromkeys([
            *all_parent_refs,
            *(c_row.get("major_system_success_refs") or ()),
            *(c_row.get("major_system_failure_refs") or ()),
            *((outcome_decision or {}).get("capability_only_parent_refs") or ()),
            *((outcome_decision or {}).get("major_system_success_refs") or ()),
            *((outcome_decision or {}).get("major_system_failure_refs") or ()),
        ]))
        explicit_first_aliases = {
            str(source): str(target)
            for source, target in dict(
                (founder_current_c_review or {}).get("first_item_parent_aliases")
                or (founder_review or {}).get("first_item_parent_aliases")
                or {}
            ).items()
        }
        if not set(explicit_first_aliases).issubset(first_refs_for_c):
            raise ValueError(f"{c_row['ruler_name']}的第一项C父任务别名源引用越界")
        if not set(explicit_first_aliases.values()).issubset(set(alias_candidates)):
            raise ValueError(f"{c_row['ruler_name']}的第一项C父任务别名目标引用越界")
        first_member_to_canonical.update(explicit_first_aliases)
        # Source overlap is lineage evidence, not campaign identity.  Automatic
        # overlap matching previously joined adjacent but distinct wars (for
        # example 苻坚代国战役与龟兹远征), which then leaked a founding-chain
        # alias into D.  Cross-ID deduplication is therefore explicit-only.
        if founder_review:
            if founder_review.get("disposition") != "CONSUME_FIRST_ITEM_C_CAPABILITY":
                raise ValueError(f"{c_row['ruler_name']}的第一项C能力复核处置非法")
            excluded_refs = {
                str(ref) for ref in founder_review.get("excluded_refs") or ()
            }
            first_refs = first_refs_for_c
            if not excluded_refs.issubset(first_refs):
                raise ValueError(f"{c_row['ruler_name']}的第一项C排除引用越界")
            review_reason = str(founder_review.get("reason") or "").strip()
            if not review_reason:
                raise ValueError(f"{c_row['ruler_name']}的第一项C能力复核缺少理由")
            merged = dict(outcome_decision or {})
            merged["ruler_id"] = ruler_id
            merged["ruler_name"] = str(c_row["ruler_name"])
            merged["capability_only_parent_refs"] = list(dict.fromkeys([
                *(merged.get("capability_only_parent_refs") or ()),
                *(canonicalize_first_ref(ref) for ref in sorted(first_refs - excluded_refs)),
            ]))
            merged["major_system_success_refs"] = list(dict.fromkeys([
                *(merged.get("major_system_success_refs") or ()),
                *(canonicalize_first_ref(ref) for ref in sorted(first_successes_for_c - excluded_refs)),
            ]))
            merged["major_system_failure_refs"] = list(dict.fromkeys([
                *(merged.get("major_system_failure_refs") or ()),
                *(canonicalize_first_ref(ref) for ref in sorted(first_failures_for_c - excluded_refs)),
            ]))
            if founder_review.get("axis_override"):
                merged["axis_override"] = dict(founder_review["axis_override"])
            existing_reason = str(merged.get("reason") or "").strip()
            merged["reason"] = (
                f"{existing_reason} {review_reason}".strip()
                if existing_reason else review_reason
            )
            outcome_decision = merged
        elif founder_current_c_review and first_refs_for_c:
            review_reason = str(founder_current_c_review.get("reason") or "").strip()
            merged = dict(outcome_decision or {})
            merged["ruler_id"] = ruler_id
            merged["ruler_name"] = str(c_row["ruler_name"])
            merged["capability_only_parent_refs"] = list(dict.fromkeys([
                *(merged.get("capability_only_parent_refs") or ()),
                *(canonicalize_first_ref(ref) for ref in sorted(first_refs_for_c)),
            ]))
            merged["major_system_success_refs"] = list(dict.fromkeys([
                *(merged.get("major_system_success_refs") or ()),
                *(canonicalize_first_ref(ref) for ref in sorted(first_successes_for_c)),
            ]))
            merged["major_system_failure_refs"] = list(dict.fromkeys([
                *(merged.get("major_system_failure_refs") or ()),
                *(canonicalize_first_ref(ref) for ref in sorted(first_failures_for_c)),
            ]))
            existing_reason = str(merged.get("reason") or "").strip()
            merged["reason"] = (
                f"{existing_reason} {review_reason}".strip()
                if existing_reason else review_reason
            )
            outcome_decision = merged
        excluded_out_of_window_refs = {
            str(ref)
            for ref in (outcome_decision or {}).get(
                "excluded_out_of_window_parent_refs", ()
            )
        }
        if excluded_out_of_window_refs:
            exclusion_candidates = {
                *all_parent_refs,
                *material_parent_refs,
                *(str(ref) for ref in c_row.get("major_system_success_refs") or ()),
                *(str(ref) for ref in c_row.get("major_system_failure_refs") or ()),
            }
            if not excluded_out_of_window_refs.issubset(exclusion_candidates):
                unknown = sorted(excluded_out_of_window_refs - exclusion_candidates)
                raise ValueError(
                    f"{c_row['ruler_name']}的C越窗排除引用不属于当前任务: {unknown}"
                )
            if not str((outcome_decision or {}).get("reason") or "").strip():
                raise ValueError(f"{c_row['ruler_name']}的C越窗排除缺少理由")
            all_parent_refs = [
                ref for ref in all_parent_refs
                if ref not in excluded_out_of_window_refs
            ]
            material_parent_refs = [
                ref for ref in material_parent_refs
                if ref not in excluded_out_of_window_refs
            ]
            c_row["major_system_success_refs"] = [
                ref for ref in c_row.get("major_system_success_refs") or ()
                if str(ref) not in excluded_out_of_window_refs
            ]
            c_row["major_system_failure_refs"] = [
                ref for ref in c_row.get("major_system_failure_refs") or ()
                if str(ref) not in excluded_out_of_window_refs
            ]
            c_row["excluded_out_of_window_parent_refs"] = sorted(
                excluded_out_of_window_refs
            )
        else:
            c_row.pop("excluded_out_of_window_parent_refs", None)
        capability_only_refs: list[str] = []
        if outcome_decision:
            capability_only_refs = list(dict.fromkeys(
                str(ref)
                for ref in outcome_decision.get("capability_only_parent_refs") or ()
            ))
            excluded_founding_refs = set(
                str(ref) for ref in d_row.get("excluded_unification_cycle_refs") or ()
            )
            allowed_capability_refs = (
                excluded_founding_refs
                | first_refs_for_c
                | {canonicalize_first_ref(ref) for ref in first_refs_for_c}
            )
            if outcome_decision.get("cross_item_capability_only_authorized"):
                if not str(outcome_decision.get("reason") or "").strip():
                    raise ValueError(
                        f"{c_row['ruler_name']}的跨项能力专用授权缺少理由"
                    )
                allowed_capability_refs.update(capability_only_refs)
            expected_unification_portfolio = str(
                outcome_decision.get("unification_portfolio_ref") or ""
            )
            for ref in capability_only_refs:
                if ref in allowed_capability_refs:
                    continue
                public_portfolio = public_unification_portfolio_by_ref.get(ref)
                if public_portfolio is None:
                    if any(
                        ref in set(system.get("accepted_task_refs") or ())
                        for system in opponent_systems_by_ref.values()
                    ):
                        allowed_capability_refs.add(ref)
                    continue
                if not expected_unification_portfolio or public_portfolio != expected_unification_portfolio:
                    raise ValueError(
                        f"{c_row['ruler_name']}的C统一战争合同归属错误: {ref}"
                    )
                allowed_capability_refs.add(ref)
            unknown_capability_refs = sorted(
                set(capability_only_refs) - allowed_capability_refs
            )
            if unknown_capability_refs:
                raise ValueError(
                    f"{c_row['ruler_name']}的C统一链能力证据不属于第一项或公共统一战争合同: "
                    f"{unknown_capability_refs}"
                )
            configured_successes = [
                canonicalize(ref)
                for ref in outcome_decision.get("major_system_success_refs") or ()
            ]
            configured_failures = [
                canonicalize(ref)
                for ref in outcome_decision.get("major_system_failure_refs") or ()
            ]
            unknown_refs = sorted(
                (set(configured_successes) | set(configured_failures))
                - set(all_parent_refs)
                - set(capability_only_refs)
            )
            if unknown_refs:
                raise ValueError(
                    f"{c_row['ruler_name']}跨分区C重大结果不属于当前父周期: {unknown_refs}"
                )
            c_row["major_system_success_refs"] = list(dict.fromkeys(
                configured_successes
                if outcome_decision.get("replace_major_system_success_refs")
                else [*(c_row.get("major_system_success_refs") or ()), *configured_successes]
            ))
            c_row["major_system_failure_refs"] = list(dict.fromkeys(
                configured_failures
                if outcome_decision.get("replace_major_system_failure_refs")
                else [*(c_row.get("major_system_failure_refs") or ()), *configured_failures]
            ))
            axis_override = dict(outcome_decision.get("axis_override") or {})
            if axis_override:
                def resolved_axis(axis: str, field: str) -> int:
                    if axis in axis_override:
                        return int(axis_override[axis])
                    return _axis_grade(c_row[field], axis)

                c1 = resolved_axis("C1", "combat_delivery_grade")
                c2 = resolved_axis("C2", "operational_sustainability_cap")
                c3 = resolved_axis("C3", "system_reliability_cap")
                overall, rate, points, surplus = _c_score(c1, c2, c3)
                lower, upper = ((0, 29), (30, 44), (45, 59), (60, 74), (75, 89), (90, 100))[min(c1, c2, c3)]
                c_row.update({
                    "combat_delivery_grade": f"C1-{c1}",
                    "operational_sustainability_cap": f"C2-{c2}",
                    "system_reliability_cap": f"C3-{c3}",
                    "C_overall_grade": overall,
                    "C_score_rate": rate,
                    "C_score_points": points,
                    "C_score_support_surplus": surplus,
                    "C_score_band": {"lower_rate": lower, "upper_rate": upper},
                })
            reason = str(outcome_decision.get("reason") or "").strip()
            if not reason:
                raise ValueError(f"{c_row['ruler_name']}跨分区C重大结果裁决缺少理由")
            # The adjudication file stores the current conclusion, not an
            # append-only history.  Replacing the old reason prevents retired
            # "unification excluded" and obsolete gate messages from
            # contradicting the current capability-only settlement.
            c_row["cap_reasons"] = [reason]
        success_refs = list(dict.fromkeys(
            canonicalize(ref) for ref in c_row.get("major_system_success_refs") or ()
        ))
        failure_refs = list(dict.fromkeys(
            canonicalize(ref) for ref in c_row.get("major_system_failure_refs") or ()
        ))
        c_row["major_system_success_refs"] = success_refs
        c_row["major_system_failure_refs"] = failure_refs
        major_refs = list(dict.fromkeys([*success_refs, *failure_refs]))
        c_only_major_refs = sorted(set(major_refs) - set(all_parent_refs))
        stress_refs = list(dict.fromkeys([
            *material_parent_refs,
            *capability_only_refs,
            *major_refs,
        ]))
        if founder_review:
            c_row["founder_capability_review"] = {
                "disposition": "CONSUME_FIRST_ITEM_C_CAPABILITY",
                "cross_item_identity": dict(c_row["cross_item_identity"]),
                "consumed_first_item_c_refs": sorted(
                    first_refs_for_c - {
                        str(ref) for ref in founder_review.get("excluded_refs") or ()
                    }
                ),
                "first_item_c_parent_aliases": dict(sorted(first_member_to_canonical.items())),
                "excluded_first_item_c_refs": sorted(
                    str(ref) for ref in founder_review.get("excluded_refs") or ()
                ),
                "opponent_system_evidence": [
                    {
                        "task_ref": task_ref,
                        "opponent_system_ref": system_ref,
                        "opponent_label": str(system.get("opponent_label") or system_ref),
                        "organization_grade": str(system.get("organization_grade") or ""),
                    }
                    for task_ref in sorted(set(capability_only_refs))
                    for system_ref, system in sorted(opponent_systems_by_ref.items())
                    if task_ref in set(system.get("accepted_task_refs") or ())
                ],
                "reason": str(founder_review["reason"]),
            }
        elif founder_no_capability_review:
            c_row["founder_capability_review"] = {
                "disposition": "HOLD_NO_FIRST_ITEM_C_CAPABILITY_REF",
                "cross_item_identity": dict(c_row["cross_item_identity"]),
                "consumed_first_item_c_refs": [],
                "excluded_first_item_c_refs": [],
                "opponent_system_evidence": [],
                "reason": str(founder_no_capability_review["reason"]),
            }
            c_row["cap_reasons"] = [str(founder_no_capability_review["reason"])]
        elif founder_current_c_review:
            c_row["founder_capability_review"] = {
                "disposition": (
                    "CONSUME_CROSS_ID_FIRST_ITEM_C_CAPABILITY"
                    if first_refs_for_c
                    else "RETAIN_CURRENT_C_WITHOUT_FIRST_ITEM_C_REFS"
                ),
                "cross_item_identity": dict(c_row["cross_item_identity"]),
                "consumed_first_item_c_refs": sorted(
                    first_refs_for_c
                ),
                "first_item_c_parent_aliases": dict(sorted(first_member_to_canonical.items())),
                "excluded_first_item_c_refs": [],
                "opponent_system_evidence": [],
                "reason": str(founder_current_c_review["reason"]),
            }
        else:
            c_row.pop("founder_capability_review", None)
        _apply_c5_axis_gate(
            c_row,
            outcome_decision,
            stress_refs,
            talent_profiles_by_ref,
            opponent_systems_by_ref,
        )
        selection_policy = "CLOSED_MATERIAL_PARENT_CYCLES_PLUS_MAJOR_SYSTEM_OUTCOMES"
        if not stress_refs:
            selection_policy = "NO_SYSTEM_STRESS_TASK_LOW_INTENSITY_OBSERVATIONS_ONLY"
        observed_count = int(
            c_row.get("observed_parent_cycle_count")
            or c_row.get("independent_task_count")
            or 0
        )
        c_row["observed_parent_cycle_count"] = observed_count
        c_row["independent_task_groups"] = stress_refs
        c_row["independent_task_count"] = len(stress_refs)
        c_row["task_selection_policy"] = selection_policy
        c_row["c_only_major_parent_refs"] = c_only_major_refs
        c_row["capability_only_parent_refs"] = capability_only_refs
        c_row["non_scoring_observation_count"] = max(
            0, observed_count - len(stress_refs)
        )
        q_by_ref = {
            canonicalize(item["canonical_parent_cycle_ref"]): item
            for item in metrics.get("cycle_q_adjudications") or ()
        }
        current_item_stress_refs = [
            ref for ref in stress_refs if ref not in set(capability_only_refs)
        ]
        c_row["current_item_task_count"] = len(current_item_stress_refs)
        c_row["current_item_task_refs"] = current_item_stress_refs
        previous_profile = dict(c_row.get("task_outcome_profile") or {})
        previous_class_by_ref = {
            canonicalize(ref): str(outcome)
            for outcome, outcome_refs in dict(
                previous_profile.get("return_class_refs") or {}
            ).items()
            for ref in outcome_refs or ()
        }
        configured_return_classes = task_return_class_adjudications.get(
            str(c_row["ruler_id"]), {}
        )
        for outcome, outcome_refs in dict(
            configured_return_classes.get("return_class_refs") or {}
        ).items():
            for ref in outcome_refs or ():
                previous_class_by_ref[canonicalize(ref)] = str(outcome)
        resolved_outcomes: list[tuple[str, str, str]] = []
        for ref in current_item_stress_refs:
            current = q_by_ref.get(ref)
            if current is not None and current.get("return_class"):
                resolved_outcomes.append(
                    (ref, str(current["return_class"]), "PUBLIC_LINEAR_Q")
                )
            elif ref in previous_class_by_ref:
                # A scoped partition rebuild may add reviewed system-stress
                # parents after the public D/Q portfolio was built.  Preserve
                # the already-current per-parent result class for unchanged
                # refs instead of silently degrading it to UNKNOWN.
                resolved_outcomes.append(
                    (ref, previous_class_by_ref[ref], "CURRENT_C_PROFILE")
                )
            else:
                resolved_outcomes.append((ref, "UNKNOWN", "UNRESOLVED"))
        if resolved_outcomes:
            outcome_counts = dict(sorted(Counter(
                outcome for _, outcome, _ in resolved_outcomes
            ).items()))
            outcome_refs = {
                outcome: [
                    ref for ref, resolved, _ in resolved_outcomes
                    if resolved == outcome
                ]
                for outcome in outcome_counts
            }
            used_previous = any(
                source == "CURRENT_C_PROFILE"
                for _, _, source in resolved_outcomes
            )
            profile_source = (
                "CLOSED_SYSTEM_STRESS_PARENT_CYCLES_WITH_CURRENT_PROFILE_FALLBACK"
                if used_previous
                else "CLOSED_SYSTEM_STRESS_PARENT_CYCLES"
            )
        else:
            outcome_counts = {}
            outcome_refs = {}
            profile_source = "NO_CURRENT_ITEM_STRESS_CYCLE"
        known_outcomes = sum(
            count for outcome, count in outcome_counts.items() if outcome != "UNKNOWN"
        )
        c_row["task_outcome_profile"] = {
            "source": profile_source,
            "selected_task_count": len(current_item_stress_refs),
            "known_outcome_count": known_outcomes,
            "return_class_counts": outcome_counts,
            "return_class_refs": outcome_refs,
            "major_system_success_count": len([
                ref for ref in success_refs if ref not in set(capability_only_refs)
            ]),
            "major_system_failure_count": len([
                ref for ref in failure_refs if ref not in set(capability_only_refs)
            ]),
            "status": "QUANTIFIED" if known_outcomes else "UNQUANTIFIED",
        }
        c_row["current_task_basis_reason"] = (
            f"当前第三项独立体系压力父周期{len(current_item_stress_refs)}项，已知结果{known_outcomes}项，"
            f"回报剖面={outcome_counts}；重大体系胜绩{len(success_refs)}项、"
            f"重大体系失败{len(failure_refs)}项。"
        )
        # C1 is combat delivery, so a non-war institution, garrison, or source-
        # coverage reference cannot by itself make the C item scoreable.  Such
        # evidence may support C2/C3 only after at least one actual system-stress
        # parent cycle has tested the force in war.
        no_scoring_evidence = not stress_refs
        if no_scoring_evidence and (
            c_row.get("no_system_stress_disposition")
            == "CONFIRMED_NOT_APPLICABLE"
        ):
            c_row.update({
                "combat_delivery_grade": "NOT_APPLICABLE_NO_SYSTEM_STRESS",
                "operational_sustainability_cap": "NOT_APPLICABLE_NO_SYSTEM_STRESS",
                "system_reliability_cap": "NOT_APPLICABLE_NO_SYSTEM_STRESS",
                "C_overall_grade": "C-N",
                "C_score_rate": 0,
                "C_score_points": 0.0,
                "C_score_support_surplus": None,
                "C_score_band": None,
                "C_score_band_position": 0.0,
                "score_ready": True,
                "score_status": "CONFIRMED_NOT_APPLICABLE_NO_SYSTEM_STRESS",
                "coverage_status": "CONFIRMED_NOT_APPLICABLE_NO_SYSTEM_STRESS",
                "major_victory_gate": {
                    "required_count": 0,
                    "actual_count": 0,
                    "status": "NOT_APPLICABLE_NO_SYSTEM_STRESS",
                },
            })
            hold_reason = "完整统治窗口复核确认没有可消费的实战体系压力任务；按C-N记未受实战检验，不把史料沉默伪装成C0，也不产生C项表现收益。"
            c_row["cap_reasons"] = [hold_reason]
        elif no_scoring_evidence:
            c_row.update({
                "combat_delivery_grade": "UNKNOWN",
                "operational_sustainability_cap": "UNKNOWN",
                "system_reliability_cap": "UNKNOWN",
                "C_overall_grade": "UNKNOWN",
                "C_score_rate": None,
                "C_score_points": None,
                "C_score_support_surplus": None,
                "C_score_band": None,
                "score_ready": False,
                "score_status": "HOLD_NO_SYSTEM_STRESS_EVIDENCE",
                "coverage_status": "HOLD_NO_SYSTEM_STRESS_EVIDENCE",
                "major_victory_gate": {
                    "required_count": None,
                    "actual_count": len(success_refs),
                    "status": "NOT_REVIEWABLE",
                },
            })
            hold_reason = "当前没有可消费的实战体系压力父周期，C1无法检验；军制、驻防或史料覆盖只能旁证C2/C3，不能单独生成C总分，故C保持UNKNOWN。"
            if hold_reason not in c_row.setdefault("cap_reasons", []):
                c_row["cap_reasons"].append(hold_reason)
        else:
            c_row["score_ready"] = True
            c_row["score_status"] = "DIRECT_C_SCORE_ASSIGNED"
            if founder_review:
                c_row["coverage_status"] = "FIRST_ITEM_C_CAPABILITY_REVIEW"
            _apply_c_task_evidence_ceiling(c_row)
        if not no_scoring_evidence:
            _apply_c_major_victory_gate(c_row)
            axes_after_gate = (
                c_row.get("combat_delivery_grade"),
                c_row.get("operational_sustainability_cap"),
                c_row.get("system_reliability_cap"),
            )
            position_decision = within_band_adjudications.get(
                str(c_row["ruler_name"])
            )
            if axes_after_gate == ("C1-4", "C2-4", "C3-4"):
                if position_decision and position_decision.get("position") not in {"LOW", "MID", "HIGH"}:
                    raise ValueError(f"{c_row['ruler_name']}的C4档内位置非法")
                if position_decision and not str(position_decision.get("reason") or "").strip():
                    raise ValueError(f"{c_row['ruler_name']}的C4档内位置缺少理由")
                if position_decision:
                    c_row["C_score_within_band_adjudication"] = position_decision
                else:
                    c_row.pop("C_score_within_band_adjudication", None)
            else:
                c_row.pop("C_score_within_band_adjudication", None)
            _apply_c_within_band_position(c_row)

        # A/B evaluates strategic-security and frontier-control state changes.
        # C-only founding capability evidence must not overwrite its trace
        # portfolio or event count.
        ab_row = ab_by_id[ruler_id]
        existing_ab_refs = [
            str(ref) for ref in ab_row.get("parent_cycle_refs") or ()
        ]
        ab_row["observed_parent_cycle_count"] = int(
            ab_row.get("observed_parent_cycle_count")
            or ab_row.get("defense_event_count")
            or len(existing_ab_refs)
        )
        ab_row["parent_cycle_refs"] = [
            ref for ref in existing_ab_refs if ref not in set(capability_only_refs)
        ]
        ab_row["defense_event_count"] = len(ab_row["parent_cycle_refs"])
        ab_row["parent_cycle_reference_policy"] = (
            "AB_STATE_CHANGE_EVIDENCE_EXCLUDING_C_ONLY_FOUNDING_CAPABILITY"
        )






def build_five_dynasties_formal_payloads(
    workspace_root: Path, registry: Mapping[str, Any]
) -> dict[str, Any]:
    adjudications = _load_adjudications(workspace_root)
    ab_records = build_five_dynasties_ab_records(registry, adjudications)
    c_records = build_five_dynasties_c_records(registry, adjudications)
    _validate_bc_parent_cycle_alignment(ab_records, c_records)
    ab = _replace_partition_records(json.loads((workspace_root / AB_PATH).read_text(encoding="utf-8")), ab_records)
    existing_combined = json.loads((workspace_root / FORMAL_PATH).read_text(encoding="utf-8"))
    north_song_count = sum(str(row.get("ruler_id", "")).startswith("RULER-NS-") for row in existing_combined["records"])
    extension = f" + 北宋{north_song_count}人" if north_song_count else ""
    ab.update({
        "scope": f"秦至唐95人当前值 + 五代十国12人当前结算{extension}",
        "ruler_count": len(ab["records"]), "reviewed_count": sum(row.get("adjudication_status") == "REVIEWED" for row in ab["records"]),
        "pending_count": sum(not row.get("score_ready") for row in ab["records"]),
        "score_ready_count": sum(bool(row.get("score_ready")) for row in ab["records"]),
    })
    c = _replace_partition_records(json.loads((workspace_root / C_PATH).read_text(encoding="utf-8")), c_records)
    for row in c["records"]:
        row.pop("confidence", None)
    _normalize_qin_tang_bc_parent_cycles(workspace_root, ab["records"], c["records"])
    _validate_formal_abc_contracts(ab["records"], c["records"])
    c.update({
        "scope": f"秦至唐95人当前值 + 五代十国12人当前结算{extension}",
        "record_count": len(c["records"]), "score_ready_count": sum(bool(row.get("score_ready")) for row in c["records"]),
        "partition_counts": dict(sorted(Counter(str(row.get("partition")) for row in c["records"]).items())),
        "grade_distribution": dict(sorted(Counter(str(row.get("C_overall_grade")) for row in c["records"]).items())),
    })
    _validate_bc_parent_cycle_alignment(ab["records"], c["records"])
    _validate_formal_abc_contracts(ab["records"], c["records"])
    partition_ids = {str(row["ruler_id"]) for row in adjudications}
    final_partition_records = [
        row for row in existing_combined["records"]
        if str(row.get("ruler_id")) in partition_ids
    ]
    return {"AB": ab, "C": c, "partition_records": final_partition_records}


def _competition_ranked_records(
    records: Sequence[Mapping[str, Any]], score_key: str
) -> list[tuple[int, Mapping[str, Any]]]:
    eligible = sorted(
        (row for row in records if row.get(score_key) is not None),
        key=lambda row: (-float(row[score_key]), str(row["ruler_name"])),
    )
    ranked: list[tuple[int, Mapping[str, Any]]] = []
    previous_score: float | None = None
    current_rank = 0
    for position, row in enumerate(eligible, start=1):
        score = float(row[score_key])
        if previous_score is None or score != previous_score:
            current_rank = position
            previous_score = score
        ranked.append((current_rank, row))
    return ranked


def _markdown_cell(value: object) -> str:
    return " ".join(str(value).replace("|", "／").splitlines()).strip()


def _reign_range_label(value: object) -> str:
    if isinstance(value, (list, tuple)):
        if len(value) == 2 and all(isinstance(item, int) for item in value):
            return f"{value[0]}-{value[1]}"
        return "；".join(str(item) for item in value)
    return str(value)


def _joined_reasons(values: Iterable[object]) -> str:
    reasons = [str(value).strip().rstrip("。；") for value in values if str(value).strip()]
    return "；".join(reasons) + ("。" if reasons else "")


def _trajectory_label(axis: Mapping[str, Any], prefix: str) -> str:
    def label(value: object) -> str:
        match = re.search(rf"{prefix}S(\d+)", str(value))
        return f"{prefix}-{match.group(1)}" if match else str(value)

    return f"{label(axis.get('start'))}→{label(axis.get('end'))}"


def _ab_settlement_basis(row: Mapping[str, Any]) -> str:
    axes = row["axes"]
    grades = "、".join(str(axes[key].get("grade") or key) for key in ("B1", "B2", "B4"))
    prefix = f"{_trajectory_label(axes['A1'], 'A1')}，{_trajectory_label(axes['A2'], 'A2')}；{grades}。"
    rationale = str(row.get("rationale") or "").strip()
    generic = rationale.startswith(
        ("分区实审已完成", "按32卷主体阶段卡", "按97卷主体阶段卡")
    )
    if not rationale or generic:
        reasons = [
            str(axes[key].get("reason") or "").strip()
            for key in ("A1", "A2", "B1", "B2", "B4")
        ]
        rationale = _joined_reasons(reason for reason in reasons if reason)
        if not rationale:
            rationale = (
                f"威胁证据{len(row.get('primary_threat_refs') or [])}项、"
                f"控制证据{len(row.get('primary_control_package_refs') or [])}项；"
                f"边界阶段{row.get('boundary_stage_review_status') or '已复核'}。"
            )
    return _markdown_cell(prefix + rationale)


def _combined_settlement_basis(row: Mapping[str, Any]) -> str:
    axes = row.get("axes") or {}
    b_grades = "／".join(str((axes.get(key) or {}).get("grade") or key) for key in ("B1", "B2", "B4"))
    return _markdown_cell(
        f"{_trajectory_label(axes['A1'], 'A1')}，{_trajectory_label(axes['A2'], 'A2')}；"
        f"B为{b_grades}；C为{axes.get('C1')}／{axes.get('C2')}／{axes.get('C3')}→{axes.get('C_overall')}；"
        f"D为{axes.get('D')}。"
    )


def _render_formal_markdown(
    kind: str, records: Sequence[Mapping[str, Any]]
) -> str:
    human_status = {
        "NOT_APPLICABLE": "不适用",
        "NOT_APPLICABLE_NO_SYSTEM_STRESS": "无体系压力任务",
        "NONE": "无额外守成难度",
        "TESTED": "经受压力检验",
        "HIGH": "高位",
        "MID": "中位",
        "LOW": "低位",
    }

    def human_label(value: object) -> str:
        text = str(value)
        return human_status.get(text, text)

    if kind not in {"AB", "C"}:
        raise ValueError("正式分项Markdown仅支持AB或C；D由军事行动成本和收益登记专用renderer生成")
    current_ab = kind == "AB" and all("AB200_score_points" in row for row in records)
    score_key = "AB200_score_points" if current_ab else {"AB": "AB_score_points", "C": "C_score_points"}[kind]
    ranked = _competition_ranked_records(records, score_key)
    unscored = [row for row in records if row.get(score_key) is None]
    values = [float(row[score_key]) for _, row in ranked]
    scope_label = (
        "秦至清"
        if any(str(row.get("polity", "")) in {"清", "后金（清前身）"} for row in records)
        else "秦至明"
        if any(str(row.get("ruler_id", "")).startswith("RULER-MING-") for row in records)
        else "秦至元"
        if any(str(row.get("ruler_id", "")).startswith("RULER-YUAN-") for row in records)
        else "秦至南宋"
        if any(str(row.get("ruler_id", "")).startswith("RULER-SS-") for row in records)
        else "秦至北宋"
    )
    definitions = {
        "AB": {
            "title": f"# {scope_label}第三项A/B国防安全正式结算",
            "rule": "[A/B规则与结算合同](../../../分项规则/第三项军事与边疆净收益/国防安全/00-规则与结算合同.md)",
            "description": "A战略安全结果120分与B边疆控制结果80分" if current_ab else "A战略安全收益80分与B边疆控制净收益80分",
        },
        "C": {
            "title": f"# {scope_label}第三项C军事体系有效性正式结算",
            "rule": "[C规则与计分合同](../../../分项规则/第三项军事与边疆净收益/军事体系有效性/00-规则与计分合同.md)",
            "description": "C军事体系有效性50分",
        },
    }
    definition = definitions[kind]
    range_text = (
        f"得分范围{min(values):.1f}—{max(values):.1f}"
        if values else "暂无已计分主体"
    )
    display_note = (
        "当前总值统一显示两位小数，原子率显示整数百分比"
        if current_ab
        else "所有分值统一显示一位小数"
    )
    lines = [
        definition["title"],
        "",
        f"规则见{definition['rule']}。本表按{definition['description']}正式值从高到低排列。",
        "",
        f"共{len(ranked)}位评价主体已计分，{range_text}；另有{len(unscored)}位保持未结算。同分并列，后一名次按竞赛排名顺延；{display_note}。",
        "",
    ]
    if kind == "AB":
        if current_ab:
            lines += [
                "A1/A2与B1/B2/B4原子档用于解释；当前计分只读取A120和非线性合成的B80。成本尚未在本表折算，最终分见第三项总榜。",
                "",
                "| 排名 | 皇帝 | 政权 | 在位 | A客观锚 | A正向信用 | A120 | B1率 | B2率 | B4率 | B80 | A+B/200 |",
                "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        else:
            lines += [
                "| 排名 | 皇帝 | 政权 | 在位 | A1/40 | A2/40 | A/80 | B1/25 | B2/30 | B4/25 | B/80 | A/B总分/160 |",
                "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        for rank, row in ranked:
            axes = row["axes"]
            if current_ab:
                b_current = row["B80_adjudication"]
                lines.append(
                    f"| {rank} | {row['ruler_name']} | {row['polity']} | {_reign_range_label(row['reign_range'])} | "
                    f"{float(row['A120_non_cost_anchor_points']):.2f} | {float(row['A120_positive_result_credit_points']):.2f} | "
                    f"{float(row['A120_score_points']):.2f} | {float(b_current['adjudicated_B1_rate']):.0f}% | "
                    f"{float(b_current['adjudicated_B2_rate']):.0f}% | {float(b_current['adjudicated_B4_rate']):.0f}% | "
                    f"{float(row['B80_score_points']):.2f} | {float(row[score_key]):.2f} |"
                )
            else:
                a1 = float(axes["A1"]["axis_points"])
                a2 = float(axes["A2"]["axis_points"])
                b1 = float(axes["B1"]["axis_points"])
                b2 = float(axes["B2"]["axis_points"])
                b4 = float(axes["B4"]["axis_points"])
                lines.append(
                    f"| {rank} | {row['ruler_name']} | {row['polity']} | {_reign_range_label(row['reign_range'])} | "
                    f"{a1:.1f} | {a2:.1f} | {a1 + a2:.1f} | {b1:.1f} | {b2:.1f} | "
                    f"{b4:.1f} | {b1 + b2 + b4:.1f} | {float(row[score_key]):.1f} |"
                )
    else:
        lines += [
            "| 排名 | 皇帝 | 政权 | 在位 | C1 | C2 | C3 | C总体 | 得分率 | C/50 | 体系压力父任务 |",
            "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for rank, row in ranked:
            lines.append(
                f"| {rank} | {row['ruler_name']} | {row['polity']} | {_reign_range_label(row['reign_range'])} | "
                f"{human_label(row['combat_delivery_grade'])} | {human_label(row['operational_sustainability_cap'])} | "
                f"{human_label(row['system_reliability_cap'])} | {row['C_overall_grade']} | "
                f"{float(row['C_score_rate']):.1f}% | {float(row[score_key]):.1f} | "
                f"{int(row['independent_task_count'])} |"
            )
    lines += ["", "## 逐人结算依据", ""]
    for rank, row in ranked:
        lines += [f"### {rank}. {row['ruler_name']}（{float(row[score_key]):.1f}）", ""]
        if kind == "AB":
            if current_ab:
                adjudications = row["A120_axis_adjudications"]
                b_current = row["B80_adjudication"]
                a_lines = []
                for axis_code in ("A1", "A2"):
                    axis = adjudications[axis_code]
                    a_lines.append(
                        f"{axis_code} {axis['start_grade']}→{axis['end_grade']}，本人变化{float(axis['attributable_delta']):g}，"
                        f"守成{human_label(axis.get('maintenance_difficulty', 'NONE'))}"
                    )
                lines += [
                    f"- A归责：{'；'.join(a_lines)}。",
                    f"- B归责：{_markdown_cell(str(b_current['consistency_basis']))}",
                    f"- 裁决：{_ab_settlement_basis(row)}",
                    "",
                ]
            else:
                lines += [f"- 裁决：{_ab_settlement_basis(row)}", ""]
            continue
        if row.get("C_overall_grade") == "C-N":
            lines += [
                f"- 裁决：{_markdown_cell(_joined_reasons(row.get('cap_reasons') or []))}",
                "",
            ]
            continue
        c_basis = _joined_reasons(row.get("cap_reasons") or []) or "按C1、C2、C3短板门槛与体系压力父任务暴露定档。"
        position = row.get("C_score_within_band_adjudication") or {}
        position_line = (
            f"- 档内位置：{human_label(position['position'])}；{_markdown_cell(str(position['reason']))}"
            if position else
            f"- 档内位置：按三轴差值计算，位置系数{float(row.get('C_score_band_position', 0)):.2f}。"
        )
        lines += [
            position_line,
            f"- 裁决：{_markdown_cell(c_basis)}",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def _render_combined_markdown(records: Sequence[Mapping[str, Any]]) -> str:
    eligible = sorted(
        (row for row in records if row.get("third_item_score_points") is not None),
        key=lambda row: (int(row["rank"]), -float(row["third_item_score_points"]), str(row["ruler_name"])),
    )
    unscored = sorted(
        (row for row in records if row.get("third_item_score_points") is None),
        key=lambda row: (str(row.get("polity")), str(row.get("ruler_name"))),
    )
    values = [float(row["third_item_score_points"]) for row in eligible]
    north_song_count = sum(str(row.get("ruler_id", "")).startswith("RULER-NS-") for row in records)
    south_song_count = sum(str(row.get("ruler_id", "")).startswith("RULER-SS-") for row in records)
    yuan_count = sum(str(row.get("ruler_id", "")).startswith("RULER-YUAN-") for row in records)
    ming_count = sum(str(row.get("ruler_id", "")).startswith("RULER-MING-") for row in records)
    qing_count = sum(
        str(row.get("polity", "")) in {"清", "后金（清前身）"}
        for row in records
    )
    title = (
        "# 秦至清第三项军事与边疆正式结算"
        if qing_count
        else "# 秦至明第三项军事与边疆正式结算"
        if ming_count
        else "# 秦至元第三项军事与边疆正式结算"
        if yuan_count
        else "# 秦至南宋第三项军事与边疆正式结算"
        if south_song_count
        else "# 秦至北宋第三项军事与边疆正式结算"
        if north_song_count
        else "# 秦至五代十国第三项军事与边疆正式结算"
    )
    extensions = ["五代十国12人已进入同一总榜"]
    if north_song_count:
        extensions.append(
            f"北宋{north_song_count}人已闭合卷001至097的互斥主政窗口"
        )
    if south_song_count:
        extensions.append(
            f"南宋{south_song_count}人已完成创业链隔离、D父周期去重及AB/C/D消费"
        )
    if yuan_count:
        extensions.append(
            f"元朝{yuan_count}人已完成显式统一窗口隔离、跨来源父周期去重及AB/C/D消费"
        )
    if ming_count:
        extensions.append(
            f"明朝{ming_count}人已完成显式统一窗口隔离、父战役去重及AB/C/D消费"
        )
    if qing_count:
        extensions.append(
            f"清朝及后金前身{qing_count}人已进入组件并集，未闭合者不赋中性总分"
        )
    extension_note = "；".join(extensions) + "。"
    score_summary = (
        f"共{len(eligible)}位评价主体完成第三项计分，得分范围"
        f"{min(values):.1f}—{max(values):.1f}；另有{len(unscored)}位仅完成部分组件并在表后单列。"
        if values
        else "当前D线性Q已由军事行动成本和收益登记闭合；旧经验D档与40分映射已停用，暂无主体进入第三项总分排名。"
    )
    lines = [
        title,
        "",
        "规则总入口见[`docs/分项规则/第三项军事与边疆净收益`](../../分项规则/第三项军事与边疆净收益/README.md)。本表将A战略安全收益80分、B边疆控制净收益80分、C军事体系有效性50分、D军事成本收益比40分合并为第三项250分当前正式值；机器读取入口为同名JSON。军事安全、控制和体系后果的持续性均在第三项相应结果轴内校准，不另设历史负债扣分。",
        "",
        f"{score_summary}{extension_note}表后逐人列出当前未排名原因；D的Q事实只取公共登记。",
        "",
        "| 排名 | 皇帝 | 政权 | 在位 | A/80 | B/80 | C/50 | D/40 | 总分/250 |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in eligible:
        d_label = str((row.get("axes") or {}).get("D") or "UNKNOWN")
        d_value = f"{d_label}/{float(row['D_score_points']):.1f}"
        lines.append(
            f"| {row['rank']} | {row['ruler_name']} | {row['polity']} | {_reign_range_label(row['reign_range'])} | "
            f"{float(row['A_score_points']):.1f} | {float(row['B_score_points']):.1f} | "
            f"{float(row['C_score_points']):.1f} | {d_value} | {float(row['third_item_score_points']):.1f} |"
        )
    lines += ["", "## 逐人结算依据", ""]
    for row in eligible:
        lines += [
            f"### {row['rank']}. {row['ruler_name']}（{float(row['third_item_score_points']):.1f}）",
            "",
            f"- 分数组成：A {float(row['A_score_points']):.1f}，B {float(row['B_score_points']):.1f}，C {float(row['C_score_points']):.1f}，D {float(row['D_score_points']):.1f}。",
            f"- 合成路径：{_combined_settlement_basis(row)}",
            "",
        ]
    for row in unscored:
        reason = str(row.get("pending_reason") or "组成部分尚未闭合，第三项不赋中性总分。")
        ab_value = "—" if row.get("AB_score_points") is None else f"{float(row['AB_score_points']):.1f}"
        c_value = "—" if row.get("C_score_points") is None else f"{float(row['C_score_points']):.1f}"
        d_value = "—" if row.get("D_score_points") is None else f"{float(row['D_score_points']):.1f}"
        lines += [
            f"### 未结算. {row['ruler_name']}（不进入排名）",
            "",
            f"- 已结算部分：A/B {ab_value}，C {c_value}，D {d_value}。",
            f"- 裁决：{_markdown_cell(reason)}",
            "",
        ]
    return "\n".join(lines).rstrip() + "\n"


def write_five_dynasties_third_item(workspace_root: Path) -> dict[str, Any]:
    promotion_audit = write_promoted_battle_registry(workspace_root)
    registry = load_battle_registry(workspace_root / REGISTRY_PATH)
    payloads = build_five_dynasties_formal_payloads(workspace_root, registry)
    paths = {"AB": AB_PATH, "C": C_PATH}
    md_paths = {
        "AB": AB_PATH.with_suffix(".md"), "C": C_PATH.with_suffix(".md"),
        "combined": FORMAL_PATH.with_suffix(".md"),
    }
    for kind, path in paths.items():
        target = workspace_root / path
        _write_text_atomic(
            target, json.dumps(payloads[kind], ensure_ascii=False, indent=2) + "\n"
        )
        md_target = workspace_root / md_paths[kind]
        _write_text_atomic(
            md_target, _render_formal_markdown(kind, payloads[kind]["records"])
        )
    verify_third_item_d_formal_settlement(workspace_root)
    paths["D"] = D_PATH
    from emperor_v4.evaluation.third_item_current_settlement import (
        write_current_third_item_settlement,
    )

    current_payload = write_current_third_item_settlement(workspace_root)
    paths["combined"] = FORMAL_PATH
    partition_ids = {
        str(row["ruler_id"]) for row in payloads["partition_records"]
    }
    current_partition_records = [
        row for row in current_payload["records"]
        if str(row.get("ruler_id")) in partition_ids
    ]
    return {
        "promotion_audit": promotion_audit,
        "formal_ready_count": sum(
            row["third_item_score_points"] is not None
            for row in current_partition_records
        ),
        "formal_pending_count": sum(
            row["third_item_score_points"] is None
            for row in current_partition_records
        ),
        "records": current_partition_records,
    }


def main() -> int:
    workspace_root = Path.cwd()
    result = write_five_dynasties_third_item(workspace_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
