from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
import time
from typing import Any, Iterable, Mapping, Sequence


SOURCE_ROOT = Path("docs/史料通读产物/五代十国/资治通鉴")
REGISTRY_PATH = Path("docs/公共成果/军事/01-战役登记.json")
REGISTRY_MARKDOWN_PATH = Path("docs/公共成果/军事/01-战役登记.md")
ADJUDICATION_PATH = Path("config/five-dynasties-third-item-adjudications.json")
AB_PATH = Path("docs/评分结算/第三项军事与边疆净收益/国防安全/01-皇帝AB项正式结算.json")
C_PATH = Path("docs/评分结算/第三项军事与边疆净收益/军事体系有效性/01-皇帝C项正式结算.json")
D_PATH = Path("docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json")
FORMAL_PATH = Path("docs/评分结算/第三项军事与边疆净收益/02-第三项正式结算.json")
QIN_TANG_BATTLE_INDEX_PATH = Path("docs/史料通读产物/唐以前编年/00-战争卡审计索引.json")
QIN_TANG_D_DIRECTION_PATH = Path("config/qin-tang-d-cycle-direction-adjudications.json")
FIRST_ITEM_C_WINDOWS_PATH = Path("config/first-item-c-acquisition-windows.json")
INPUT_SCHEMA = "chronicle-battle-adjudication-v2"
REGISTRY_SCHEMA = "battle-parent-contract-registry-v5"
SOURCE_SET_FINGERPRINT = (
    "d23622b8545ee5a49e06b93ad265a47e1a9643be844899eabd76ab92717fed57"
)
RETIRED_STALE_FIVE_DYNASTIES_RECORD_COUNT = 433


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


def _digest(value: object) -> str:
    return sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _grade_number(value: object, prefix: str) -> int | None:
    match = re.fullmatch(rf"{prefix}(\d)(?:估)?", str(value or ""))
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
    if payload.get("schema_version") != "five-dynasties-third-item-adjudications-v1":
        raise ValueError("五代十国第三项裁决配置schema错误")
    if payload.get("source_set_fingerprint") != SOURCE_SET_FINGERPRINT:
        raise ValueError("五代十国第三项裁决配置未绑定当前64份输入指纹")
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
            phase["polity_binding"] = item["polity"]
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
    source_identities: list[dict[str, Any]] = []
    for path in adjudication_paths:
        payload, summary_relative = _read_source_pair(path, workspace_root)
        volume = int(re.search(r"volume-(\d+)\.", path.name).group(1))
        source_relative = path.relative_to(workspace_root).as_posix()
        source_identities.append(dict(payload["source_identity"]))
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
                        "polity_binding": binding["polity"],
                        "ruler_binding": {key: value for key, value in binding.items() if key != "polity"},
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
    fingerprint = _digest(source_identities)
    return {
        "schema_version": "five-dynasties-battle-promotion-v1",
        "source_set_declared_fingerprint": SOURCE_SET_FINGERPRINT,
        "source_identity_fingerprint": fingerprint,
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
            "fingerprint": _digest(
                [
                    {
                        "record_ref": str(row.get("source_target_ref") or row.get("war_event_id") or ""),
                        "combat_difficulty": row["combat_difficulty"],
                        "combat_difficulty_basis": row["combat_difficulty_basis"],
                    }
                    for row in sorted(
                        current_high_difficulty,
                        key=lambda item: str(item.get("source_target_ref") or item.get("war_event_id") or ""),
                    )
                ]
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
    current["semantic_fingerprint"] = _digest(
        {key: value for key, value in current.items() if key != "semantic_fingerprint"}
    )
    return current


def iter_bound_cycles(
    registry: Mapping[str, Any], ruler_id: str
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    seen_phase_fingerprints: set[tuple[str, str]] = set()
    for record in registry.get("records") or ():
        if record.get("dynasty_partition") != "five_dynasties":
            continue
        campaign_group = str(record["campaign_group_ref"])
        for phase in record.get("subject_phase_views") or ():
            binding = phase.get("ruler_binding") or {}
            if binding.get("ruler_id") != ruler_id or binding.get("status") == "BOUND_YEAR_WINDOW_BOUNDARY":
                continue
            semantic = _digest(
                {
                    key: phase.get(key)
                    for key in (
                        "evaluation_subject_phase", "actual_process", "cost_axes",
                        "strategic_security", "material_return", "border_control",
                        "phase_return_class", "founding_startup_ledger",
                    )
                }
            )
            dedupe_key = (campaign_group, semantic)
            if dedupe_key in seen_phase_fingerprints:
                continue
            seen_phase_fingerprints.add(dedupe_key)
            cycle = grouped.setdefault(
                campaign_group,
                {"campaign_group_ref": campaign_group, "war_event_refs": [], "phases": []},
            )
            cycle["war_event_refs"].append(record["war_event_id"])
            cycle["phases"].append(dict(phase))
    return [
        {
            **cycle,
            "war_event_refs": _unique(cycle["war_event_refs"]),
            "phase_ids": [phase["phase_id"] for phase in cycle["phases"]],
        }
        for _, cycle in sorted(grouped.items())
    ]


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


def write_promoted_battle_registry(workspace_root: Path) -> dict[str, Any]:
    path = workspace_root / REGISTRY_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    promoted = promote_five_dynasties_battle_registry(payload, workspace_root)
    _write_text_atomic(
        path, json.dumps(promoted, ensure_ascii=False, indent=2) + "\n"
    )
    from emperor_v4.evaluation.battle_parent_contract_registry import (
        render_battle_parent_contract_registry_markdown,
    )

    _write_text_atomic(
        workspace_root / REGISTRY_MARKDOWN_PATH,
        render_battle_parent_contract_registry_markdown(promoted),
    )
    return build_promotion_audit(promoted)


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
D_BANDS = {
    "D-0": (0.0, 7.9), "D-1": (8.0, 15.9), "D-2": (16.0, 21.9),
    "D-3": (22.0, 29.9), "D-4": (30.0, 35.9), "D-5": (36.0, 40.0),
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
    base = max(0, min(100, 12 * end + 10 * (end - start)))
    transition = "IMPROVED" if end > start else "WORSENED" if end < start else "STABLE"
    return {
        "start": A_STATE_NAMES[axis][start],
        "end": A_STATE_NAMES[axis][end],
        "transition": transition,
        "transition_attribution": "RULER_REIGN_NET_RESULT",
        "base_trajectory_value": base,
        "ceiling_progress": "NONE",
        "ceiling_progress_refs": [],
        "ceiling_bonus": 0,
        "trajectory_value": base,
        "axis_points": round(base * 0.4, 2),
        "reason": decision["reason"],
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
        "reason": decision["reason"],
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
    exclusion_specs = {
        str(item["campaign_group_ref"]): item
        for item in decision.get("third_item_cycle_exclusions") or ()
    }
    unknown = sorted((set(overrides) | set(exclusion_specs)) - known)
    if unknown:
        raise ValueError(
            f"{decision['ruler_name']}第三项路由覆盖引用不存在: {unknown}"
        )
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
        if cycle_ref in exclusion_specs:
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
        if not founding or cycle_ref in overrides:
            routed = dict(cycle)
            override = overrides.get(cycle_ref)
            if override and override.get("return_class"):
                return_class = str(override["return_class"])
                if return_class not in {
                    "HIGH_RETURN", "PROPORTIONATE_RETURN", "LOW_RETURN",
                    "NEGATIVE_RETURN", "UNKNOWN",
                }:
                    raise ValueError(
                        f"{decision['ruler_name']}第三项路由覆盖回报类别非法"
                    )
                routed["return_class_override"] = return_class
                routed["route_override_reason"] = str(override["reason"])
            included.append(routed)
        else:
            excluded.append(dict(cycle))
    merge_specs = list(decision.get("third_item_cycle_merges") or ())
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
        return_class = str(spec.get("return_class") or "")
        if return_class not in {
            "HIGH_RETURN", "PROPORTIONATE_RETURN", "LOW_RETURN",
            "NEGATIVE_RETURN", "UNKNOWN",
        }:
            raise ValueError(f"{decision['ruler_name']}周期合并回报类别非法")
        by_ref = {str(cycle["campaign_group_ref"]): cycle for cycle in included}
        missing = sorted(set(members) - set(by_ref))
        if missing:
            raise ValueError(f"{decision['ruler_name']}周期合并成员不存在或已排除: {missing}")
        selected = [by_ref[ref] for ref in members]
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
            "return_class_override": return_class,
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
    return included, excluded


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
        base.update(
            {
                "axes": axes,
                "AB_score_points": round(sum(axis["axis_points"] for axis in axes.values()), 2),
                "b1_region_control": {"start": {"AGGREGATE_REVIEWED": start}, "end": {"AGGREGATE_REVIEWED": end}},
                "b1_region_adjudications": [{
                    "object_id": "FIVE_DYNASTIES_REIGN_CONTROL_PACKAGE",
                    "object_name": "本皇帝非统一边疆控制净包",
                    "anchors": ["start", "end"], "counted": True,
                    "control_equivalent": {"start": start, "end": end},
                    "evidence_refs": control_refs,
                    "reason": decision["AB"]["B1"]["reason"],
                }],
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
    grade = _axis_grade(row["C_overall_grade"], "C")
    failures = list(dict.fromkeys(row.get("major_system_failure_refs") or ()))
    successes = list(dict.fromkeys(row.get("major_system_success_refs") or ()))
    row["major_system_failure_refs"] = failures
    row["major_system_success_refs"] = successes
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
    row.setdefault("cap_reasons", []).append(
        f"C4重大胜绩门禁未通过：需{required}项、实有{len(successes)}项，封顶C3。"
    )


def _apply_c_task_evidence_ceiling(row: dict[str, Any]) -> None:
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
    row.setdefault("cap_reasons", []).append(
        f"排除创业统一账后仅余{tasks}项独立任务，C1/C3按证据上限{ceiling}档收束。"
    )


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
        records.append(base)
    return records


def _validate_bc_parent_cycle_alignment(
    ab_records: Sequence[Mapping[str, Any]],
    c_records: Sequence[Mapping[str, Any]],
) -> None:
    ab_by_id = {str(row["ruler_id"]): row for row in ab_records}
    if set(ab_by_id) != {str(row["ruler_id"]) for row in c_records}:
        raise ValueError("B项与C项评价主体集合不一致")
    for c_row in c_records:
        ruler_id = str(c_row["ruler_id"])
        ab_row = ab_by_id[ruler_id]
        if int(ab_row["defense_event_count"]) != int(
            c_row["independent_task_count"]
        ):
            raise ValueError(
                f"{c_row['ruler_name']}的B父周期数与C独立任务数不一致"
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
            if canonical not in groups or retired_members.intersection(groups):
                raise ValueError(
                    f"{c_row['ruler_name']}的C独立任务仍含父级合并成员"
                )


def _qin_tang_campaign_groups_by_ref(
    workspace_root: Path,
) -> dict[str, set[str]]:
    index_payload = json.loads(
        (workspace_root / QIN_TANG_BATTLE_INDEX_PATH).read_text(encoding="utf-8")
    )
    index_rows = index_payload.get("cards") or index_payload.get("records") or index_payload
    source_cache: dict[str, list[str]] = {}
    groups_by_ref: dict[str, set[str]] = defaultdict(set)
    for card in index_rows:
        source_ref = str(card["source_card_id"])
        source_file = str(card["source_file"])
        lines = source_cache.setdefault(
            source_file,
            (workspace_root / source_file).read_text(encoding="utf-8").splitlines(),
        )
        start = int(card["heading_line"]) - 1
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
    first_item_payload = json.loads(
        (workspace_root / FIRST_ITEM_C_WINDOWS_PATH).read_text(encoding="utf-8")
    )
    founding_refs_by_name = {
        str(item["ruler_name"]): {
            str(ref) for ref in item.get("campaign_refs") or ()
        }
        for item in first_item_payload.get("manual_windows") or ()
    }
    founding_refs_by_name.setdefault("杨坚", set()).add(
        "WAR-LEAD-SUI-ABSORB-LIANG-587"
    )
    founding_refs_by_name.setdefault("沮渠蒙逊", set()).add(
        "WAR-LEAD-112-MENGXUN-401"
    )
    founding_refs_by_name.setdefault("拓跋珪", set()).update(
        {"WAR-LEAD-112-WEI-MOYIGAN-402", "WAR-LEAD-115-WEI-SUCCESSION-409"}
    )
    curated_high_grade_failures = {
        "RULER-SHADOW-杨坚": ["SUI-LEAD-SUI-GOGURYEO-598"],
        "RULER-TANG-LICHUN": ["CAMPAIGN-TANG-238-01"],
    }
    for c_row in c_records:
        ruler_id = str(c_row.get("ruler_id") or "")
        groups = [str(ref) for ref in c_row.get("independent_task_groups") or ()]
        if len(groups) != len(set(groups)) or int(c_row["independent_task_count"]) != len(groups):
            raise ValueError(f"{c_row['ruler_name']}的C独立任务不是唯一父周期集合")
        if not ruler_id.startswith(("RULER-FD-", "RULER-NS-")):
            founding_refs = founding_refs_by_name.get(str(c_row["ruler_name"]), set())
            settled_refs = [
                str(ref) for ref in c_row.get("settled_event_refs") or ()
            ]
            consumed_founding_refs = [ref for ref in settled_refs if ref in founding_refs]
            excluded_groups: set[str] = set()
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
            c_row["excluded_founding_unification_refs"] = consumed_founding_refs
            if _axis_grade(c_row["C_overall_grade"], "C") >= 4:
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
                direction_by_id.get(ruler_id, {}).get("major_high_return_refs") or ()
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
        _apply_c_task_evidence_ceiling(c_row)
        _apply_c_major_victory_gate(c_row)
        c_row["parent_cycle_merge_adjudications"] = list(
            c_row.get("parent_cycle_merge_adjudications") or ()
        )
        c_row["parent_cycle_reference_policy"] = (
            "RAW_SETTLED_EVENT_REFS_PLUS_CANONICAL_INDEPENDENT_TASK_GROUPS"
        )
        ab_row = ab_by_id[ruler_id]
        if not ruler_id.startswith(("RULER-FD-", "RULER-NS-")):
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
    rate_positions = {
        0: {0, 15, 29}, 1: {30, 37, 44}, 2: {45, 52, 59},
        3: {60, 67, 74}, 4: {75, 82, 89}, 5: {90, 95, 100},
    }
    for row in ab_records:
        axes = row["axes"]
        for key in ("A1", "A2"):
            axis = axes[key]
            start = _axis_grade(axis["start"], key)
            end = _axis_grade(axis["end"], key)
            expected_base = max(0, min(100, 12 * end + 10 * (end - start)))
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
            grade = _axis_grade(axis["grade"], key)
            rate = int(axis["score_rate"])
            if rate not in rate_positions[grade] or abs(
                float(axis["axis_points"]) - rate * weight
            ) > 0.011:
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


def _aggregate_d_cycle(cycle: Mapping[str, Any]) -> dict[str, Any]:
    phases = list(cycle["phases"])
    final_class = str(cycle.get("return_class_override") or "") or next(
        (
            phase["phase_return_class"]
            for phase in reversed(phases)
            if phase["phase_return_class"] != "UNKNOWN"
        ),
        "UNKNOWN",
    )
    costs = {key: max((_grade_number(phase["cost_axes"].get(key), key) or 0) for phase in phases) for key in ("P", "S", "M", "A", "WC")}
    benefits = {
        key: max((_grade_number(value, key) or 0) for phase in phases for value in (
            [phase["strategic_security"]] if key in {"SB", "SN"} else
            [phase["border_control"][key]] if key in {"BCP", "BCN"} else
            [phase["material_return"]]
        ))
        for key in ("SB", "SN", "BCP", "BCN", "WR")
    }
    unknown_axes = sorted({
        key
        for phase in phases
        for key, value in {
            **phase["cost_axes"],
            "security": phase["strategic_security"],
            "return": phase["material_return"],
            "BCP": phase["border_control"].get("BCP"),
            "BCN": phase["border_control"].get("BCN"),
        }.items()
        if value == "UNKNOWN"
    })
    material = max(costs[key] for key in ("P", "S", "M", "A")) >= 3 or max(benefits[key] for key in ("SB", "SN", "BCP", "BCN")) >= 3
    major_benefit = max(benefits[key] for key in ("SB", "SN", "BCP", "BCN"))
    national_negative = final_class == "NEGATIVE_RETURN" and (
        costs["P"] >= 5
        or max(costs["M"], costs["A"]) >= 4
        or max(benefits["SN"], benefits["BCN"]) >= 4
    )
    return {
        "campaign_group_ref": cycle["campaign_group_ref"], "war_event_refs": cycle["war_event_refs"],
        "phase_ids": cycle["phase_ids"], "return_class": final_class,
        "cost_axes": costs, "benefit_axes": benefits, "material": material,
        "unknown_axes": unknown_axes,
        "major_high_return": final_class == "HIGH_RETURN" and major_benefit >= 4,
        "top_high_return": final_class == "HIGH_RETURN" and major_benefit >= 5,
        "national_negative": national_negative,
        "route": "D_INTERNAL_COST_ONLY" if re.search(r"MUTINY|REBELLION", cycle["campaign_group_ref"]) else "D_STANDARD",
        "merged_campaign_group_refs": list(cycle.get("merged_campaign_group_refs") or ()),
        "merge_reason": cycle.get("merge_reason"),
        "route_override_reason": cycle.get("route_override_reason"),
    }


def _d_grade_and_score(
    cycles: Sequence[Mapping[str, Any]], *,
    allow_exceptional_national_recovery: bool = False,
) -> tuple[str, float, dict[str, Any]]:
    counts = Counter(cycle["return_class"] for cycle in cycles)
    material = [cycle for cycle in cycles if cycle["material"]]
    known_material = [
        cycle for cycle in material if cycle["return_class"] != "UNKNOWN"
    ]
    material_counts = Counter(cycle["return_class"] for cycle in material)
    positive = material_counts["HIGH_RETURN"] + material_counts["PROPORTIONATE_RETURN"]
    negative = material_counts["LOW_RETURN"] + material_counts["NEGATIVE_RETURN"]
    material_negative = [
        cycle
        for cycle in material
        if cycle["return_class"] == "NEGATIVE_RETURN"
    ]
    national = [cycle for cycle in material if cycle["national_negative"]]
    major = [
        cycle for cycle in known_material
        if cycle["return_class"] == "HIGH_RETURN" and cycle["major_high_return"]
    ]
    top = [
        cycle for cycle in known_material
        if cycle["return_class"] == "HIGH_RETURN" and cycle["top_high_return"]
    ]
    material_unknown = [
        cycle
        for cycle in material
        if cycle["return_class"] == "UNKNOWN"
    ]
    potential_material = [
        cycle
        for cycle in cycles
        if not cycle["material"] and cycle.get("unknown_axes")
    ]
    exceptional_national_recovery = (
        allow_exceptional_national_recovery
        and
        len(national) == 1
        and len(material_negative) == 1
        and positive >= negative + 4
        and positive / max(1, positive + negative) >= 0.75
        and len(known_material) >= 5
        and len(major) >= 2
        and len(top) >= len(national)
    )
    if not material or not known_material:
        return "D-U", 20.0, {
            "status": (
                "NO_CLOSED_MATERIAL_RETURN"
                if material
                else
                "NO_CONFIRMED_MATERIAL_CYCLE_WITH_UNRESOLVED_AXES"
                if potential_material
                else "NO_MATERIAL_CYCLE"
            ),
            "return_class_counts": dict(sorted(counts.items())),
            "material_return_class_counts": dict(sorted(material_counts.items())),
            "usable_cycle_count": len(cycles),
            "material_cycle_count": len(material),
            "known_material_cycle_count": 0,
            "material_return_closure_rate": 0.0,
            "national_negative_return_refs": [],
            "material_negative_return_refs": [],
            "material_unknown_cycle_refs": [
                cycle["campaign_group_ref"] for cycle in material_unknown
            ],
            "potential_material_cycle_refs": [
                cycle["campaign_group_ref"] for cycle in potential_material
            ],
            "major_high_return_refs": [],
            "top_tier_high_return_refs": [],
            "evidence_status": "UNDER_TESTED",
        }
    if (len(national) >= 2 and negative >= positive) or (
        len(national) >= 1 and positive == 0
    ):
        grade = "D-1"
    elif (
        (len(national) >= 2 and not exceptional_national_recovery)
        or (national and negative >= positive)
        or (not national and negative >= 2 and negative >= positive)
    ):
        grade = "D-2"
    elif (
        len(top) >= 1
        and len(major) >= 2
        and material_counts["HIGH_RETURN"] >= 3
        and len(known_material) >= 4
        and not material_unknown
        and not national
        and material_counts["NEGATIVE_RETURN"] == 0
        and positive / max(1, positive + negative) >= 0.75
    ):
        grade = "D-5"
    elif (
        len(material_negative) <= 1
        and (not national or exceptional_national_recovery)
        and positive > negative
        and positive / max(1, positive + negative) >= 2 / 3
        and len(known_material) >= 2
        and len(known_material) / len(material) >= 2 / 3
        and (
            material_counts["HIGH_RETURN"] >= 1
            or (len(known_material) >= 4 and negative == 0)
        )
        and len(top) >= max(1, len(national))
    ):
        grade = "D-4"
        if len(material_negative) == 1 and (
            positive < negative + 3 or len(major) < 2
        ):
            grade = "D-3"
    else:
        grade = "D-3"
    h, r, low, neg = (
        material_counts[name]
        for name in ("HIGH_RETURN", "PROPORTIONATE_RETURN", "LOW_RETURN", "NEGATIVE_RETURN")
    )
    total = len(cycles)
    material_known_total = h + r + low + neg
    quality = (
        max(
            0.0,
            min(
                1.0,
                0.5
                + (2 * h + r - low - 2 * neg - 4 * len(national))
                / (4 * material_known_total),
            ),
        )
        if material_known_total
        else 0.25
    )
    if grade == "D-4":
        breadth = min(1.0, (len(known_material) + 2 * len(major)) / 8)
        dominance = positive / max(1, positive + negative)
        quality = (0.5 * quality + 0.3 * breadth + 0.2 * dominance) * min(1.0, 0.70 + 0.05 * len(known_material))
        if not major:
            quality = min(quality, 0.8)
        if national:
            quality = min(quality, 0.72)
    if grade == "D-3":
        breadth = min(1.0, len(known_material) / 4)
        quality = 0.6 * quality + 0.4 * breadth
    if len(known_material) == 1 and grade == "D-3":
        quality = min(quality, {"HIGH_RETURN": 0.65, "PROPORTIONATE_RETURN": 0.5, "LOW_RETURN": 0.3, "NEGATIVE_RETURN": 0.1}[known_material[0]["return_class"]])
    closure_rate = len(known_material) / len(material)
    if material_unknown:
        quality *= 0.90 + 0.10 * closure_rate
    lower, upper = D_BANDS[grade]
    score = round(lower + (upper - lower) * quality, 1)
    if grade == "D-4":
        thin_major_cap = (
            34.0
            if len(known_material) == 2 and len(major) >= 2
            else 34.8
            if len(known_material) == 3 and len(major) >= 2
            else None
        )
        score = min(
            score,
            thin_major_cap
            if thin_major_cap is not None
            else {2: 33.0, 3: 34.6, 4: 35.0, 5: 35.4}.get(
                len(known_material), 35.9
            ),
        )
    return grade, score, {
        "return_class_counts": dict(sorted(counts.items())), "usable_cycle_count": total,
        "material_return_class_counts": dict(sorted(material_counts.items())),
        "material_cycle_count": len(material),
        "known_material_cycle_count": len(known_material),
        "material_return_closure_rate": round(closure_rate, 4),
        "national_negative_return_refs": [cycle["campaign_group_ref"] for cycle in national],
        "material_negative_return_refs": [
            cycle["campaign_group_ref"] for cycle in material_negative
        ],
        "material_unknown_cycle_refs": [
            cycle["campaign_group_ref"] for cycle in material_unknown
        ],
        "potential_material_cycle_refs": [
            cycle["campaign_group_ref"] for cycle in potential_material
        ],
        "major_high_return_refs": [cycle["campaign_group_ref"] for cycle in major],
        "top_tier_high_return_refs": [cycle["campaign_group_ref"] for cycle in top],
        "exceptional_national_recovery_gate": (
            "PASSED_STRONG_COUNTEREVIDENCE"
            if exceptional_national_recovery
            else "NOT_APPLICABLE"
        ),
        "evidence_status": "UNDER_TESTED" if len(known_material) <= 1 else "LIMITED_EXPOSURE" if len(known_material) <= 3 else "SUFFICIENT_EXPOSURE",
    }


def _d_grade_reasons(grade: str, metrics: Mapping[str, Any]) -> list[str]:
    counts = metrics.get("material_return_class_counts") or {}
    high = int(counts.get("HIGH_RETURN", 0))
    proportionate = int(counts.get("PROPORTIONATE_RETURN", 0))
    low = int(counts.get("LOW_RETURN", 0))
    negative = int(counts.get("NEGATIVE_RETURN", 0))
    unknown = int(counts.get("UNKNOWN", 0))
    positive = high + proportionate
    adverse = low + negative
    material_count = int(metrics.get("material_cycle_count") or 0)
    major = len(metrics.get("major_high_return_refs") or [])
    top = len(metrics.get("top_tier_high_return_refs") or [])
    material_negative_returns = len(metrics.get("material_negative_return_refs") or [])
    national_negative = len(metrics.get("national_negative_return_refs") or [])
    if metrics.get("exceptional_national_recovery_gate") == "PASSED_STRONG_COUNTEREVIDENCE":
        return [
            "存在1项国家级负收益，但经至少5项实质周期、2项重大高收益、至少1项顶尖高收益、正向净多至少4项且占比不少于四分之三的厚样本反证；"
            "不以许多小胜稀释重大浪费，仍按D4低中位结算并保留国家级负收益引用。"
        ]
    if grade == "D-3" and material_negative_returns > 1 and national_negative == 0:
        return [
            f"存在{material_negative_returns}项实质的非国家级负收益，超过D4至多容纳1项的硬门槛；"
            "正向周期仍占优且未命中国家级负收益门槛，故按D3结算。"
        ]
    if grade == "D-U":
        return ["无实质军事投资周期，成本收益能力未受检验，按D-U固定20分结算。"]
    if grade == "D-5":
        return [
            f"{material_count}项实质父级周期中正向{positive}、负向{adverse}，含{major}项重大、{top}项顶尖高收益；"
            "满足多项重大任务、至少四分之三正向、无国家级负收益及无实质未知的D5门槛。"
        ]
    if grade == "D-4":
        unknown_note = (
            f"；另有{unknown}项实质回报未知，因此D5封顶D4"
            if unknown
            else ""
        )
        return [
            f"{material_count}项实质父级周期中正向{positive}、负向{adverse}，高收益{high}、重大高收益{major}{unknown_note}；"
            "通过D4的正向占优、比例、重大浪费与ABC少样本门禁。"
        ]
    if grade == "D-2":
        return [
            f"{material_count}项实质父级周期中正向{positive}、负向{adverse}，国家级负收益{national_negative}；"
            "命中明显失衡门槛但仍有可确认成果，按D2结算。"
        ]
    if grade == "D-1":
        return [
            f"{material_count}项实质父级周期中正向{positive}、负向{adverse}，国家级负收益{national_negative}；"
            "负收益长期占主导或国家级损失缺少足够补偿，按D1结算。"
        ]
    return [
        f"{material_count}项实质父级周期中正向{positive}、负向{adverse}、回报未知{unknown}；"
        "未命中D1/D2失衡门槛，也未满足D4/D5的正向占优与重大高收益组合门槛，按D3结算。"
    ]


def build_five_dynasties_d_records(
    registry: Mapping[str, Any], adjudications: Sequence[Mapping[str, Any]],
    ab_records: Sequence[Mapping[str, Any]], c_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    ab_by_id = {row["ruler_id"]: row for row in ab_records}
    c_by_id = {row["ruler_id"]: row for row in c_records}
    records = []
    for decision in adjudications:
        cycles, event_refs, _ = _cycles_and_refs(registry, str(decision["ruler_id"]))
        included_cycles, excluded = _third_item_cycles(decision, cycles)
        included = [_aggregate_d_cycle(cycle) for cycle in included_cycles]
        ready = bool(decision.get("score_ready", decision.get("coverage_complete", False)))
        base = {
            "ruler_id": decision["ruler_id"], "ruler_name": decision["ruler_name"],
            "polity": decision["polity"], "reign_range": decision["reign_range"],
            "schema_id": "emperor-v4-d-ruler-formal-settlement-v1", "canonical_status": "FORMAL_CURRENT" if ready else "PENDING",
            "formal_repository_entry": True, "formal_score_write": False, "database_write": False,
            "source_event_refs": event_refs,
            "d_cycle_refs": [cycle["campaign_group_ref"] for cycle in cycles],
            "included_d_cycle_refs": [cycle["campaign_group_ref"] for cycle in included],
            "excluded_unification_cycle_refs": [
                cycle["campaign_group_ref"]
                for cycle in excluded
                if not cycle.get("third_item_exclusion_reason")
            ],
            "excluded_non_attributable_cycle_refs": [
                cycle["campaign_group_ref"]
                for cycle in excluded
                if cycle.get("third_item_exclusion_reason")
            ],
            "excluded_cycle_adjudications": [
                {
                    "campaign_group_ref": cycle["campaign_group_ref"],
                    "reason": cycle["third_item_exclusion_reason"],
                }
                for cycle in excluded
                if cycle.get("third_item_exclusion_reason")
            ],
            "strategic_binding_refs": [ref for cycle in included for ref in cycle["phase_ids"]],
            "internal_cost_binding_refs": [cycle["campaign_group_ref"] for cycle in included if cycle["route"] == "D_INTERNAL_COST_ONLY"],
            "route_counts": dict(sorted(Counter(cycle["route"] for cycle in included).items())),
            "cycle_merge_adjudications": [
                {
                    "canonical_cycle_ref": cycle["campaign_group_ref"],
                    "member_campaign_group_refs": cycle["merged_campaign_group_refs"],
                    "reason": cycle["merge_reason"],
                }
                for cycle in included
                if cycle.get("merged_campaign_group_refs")
            ],
            "manual_portfolio_override": False,
        }
        if not ready:
            base.update({
                "D_grade": "UNKNOWN", "D_grade_reasons": [decision["pending_reason"]],
                "D_score_points": None, "D_score_band": None, "portfolio_status": "PENDING_INSUFFICIENT_EVIDENCE",
                "D_portfolio_metrics": {"evidence_status": "INCOMPLETE_REIGN_COVERAGE", "usable_cycle_count": len(included)},
                "unresolved_cycle_refs": [cycle["campaign_group_ref"] for cycle in included],
                "unresolved_source_refs": [decision["pending_reason"]], "positive_benefit_cycle_refs": [],
                "negative_benefit_cycle_refs": [], "high_cost_cycle_refs": [], "zero_return_high_cost_cycle_refs": [],
                "peak_d_cost_axes": {"P": None, "M": None, "A": None}, "readiness_counts": {"PENDING": len(included)},
                "binding_source": "SUBJECT_PHASE_INCOMPLETE", "ruler_event_class_overrides": [],
            })
            records.append(base)
            continue
        ab_points = ab_by_id[decision["ruler_id"]]["AB_score_points"]
        c_points = c_by_id[decision["ruler_id"]]["C_score_points"]
        grade, score, metrics = _d_grade_and_score(
            included,
            allow_exceptional_national_recovery=(
                ab_points >= 80
                and c_points >= 30
                and not decision.get("terminal_polity_collapse")
            ),
        )
        if grade in {"D-4", "D-5"} and 2 <= metrics["material_cycle_count"] <= 3 and (ab_points < 80 or c_points < 30):
            grade = "D-3"
            lower, upper = D_BANDS[grade]
            score = round((lower + upper) / 2, 1)
            metrics["abc_small_sample_gate"] = "CAPPED_TO_D3"
        metrics["unknown_axis_cycle_count"] = sum(
            bool(cycle.get("unknown_axes")) for cycle in included
        )
        positive = [cycle for cycle in included if cycle["return_class"] in {"HIGH_RETURN", "PROPORTIONATE_RETURN"}]
        negative = [cycle for cycle in included if cycle["return_class"] in {"LOW_RETURN", "NEGATIVE_RETURN"}]
        high_cost = [cycle for cycle in included if max(cycle["cost_axes"][key] for key in ("P", "S", "M", "A")) >= 4]
        lower, upper = D_BANDS.get(grade, (20.0, 20.0))
        metrics["abc_crosscheck"] = {
            "ab_score_points": ab_points, "ab_threshold_points": 80.0,
            "c_score_points": c_points, "c_threshold_points": 30.0,
            "small_sample_high_grade_gate_applied": metrics.get("abc_small_sample_gate") == "CAPPED_TO_D3",
            "status": "SUFFICIENT_SUPPORT" if ab_points >= 80 and c_points >= 30 else "INSUFFICIENT_SUPPORT",
        }
        base.update({
            "D_grade": grade, "D_grade_reasons": _d_grade_reasons(grade, metrics),
            "D_score_points": score, "D_score_band": {"lower_points": lower, "upper_points": upper},
            "portfolio_status": "FORMAL_CURRENT", "D_portfolio_metrics": metrics,
            "unresolved_cycle_refs": [cycle["campaign_group_ref"] for cycle in included if cycle["return_class"] == "UNKNOWN" or cycle.get("unknown_axes")],
            "unresolved_source_refs": [],
            "positive_benefit_cycle_refs": [cycle["campaign_group_ref"] for cycle in positive],
            "negative_benefit_cycle_refs": [cycle["campaign_group_ref"] for cycle in negative],
            "high_cost_cycle_refs": [cycle["campaign_group_ref"] for cycle in high_cost],
            "zero_return_high_cost_cycle_refs": [cycle["campaign_group_ref"] for cycle in high_cost if cycle["return_class"] in {"LOW_RETURN", "NEGATIVE_RETURN"}],
            "peak_d_cost_axes": {key: f"{key}{max((cycle['cost_axes'][key] for cycle in included), default=0)}" for key in ("P", "M", "A")},
            "readiness_counts": {"HOLD": len(included)}, "binding_source": "SUBJECT_PHASE_FORMAL_CURRENT",
            "ruler_event_class_overrides": [
                {
                    "campaign_group_ref": cycle["campaign_group_ref"],
                    "return_class": cycle["return_class"],
                    "reason": cycle["route_override_reason"],
                }
                for cycle in included
                if cycle.get("route_override_reason")
            ],
        })
        records.append(base)
    return records


def _replace_partition_records(
    payload: Mapping[str, Any], records: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    ruler_ids = {str(row["ruler_id"]) for row in records}
    preserved = [dict(row) for row in payload.get("records") or () if str(row.get("ruler_id")) not in ruler_ids]
    current = dict(payload)
    current["records"] = preserved + [dict(row) for row in records]
    return current


def _build_combined_records(
    adjudications: Sequence[Mapping[str, Any]], ab_records: Sequence[Mapping[str, Any]],
    c_records: Sequence[Mapping[str, Any]], d_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    ab_by_id = {row["ruler_id"]: row for row in ab_records}
    c_by_id = {row["ruler_id"]: row for row in c_records}
    d_by_id = {row["ruler_id"]: row for row in d_records}
    rows = []
    for decision in adjudications:
        ab = ab_by_id[decision["ruler_id"]]
        c = c_by_id[decision["ruler_id"]]
        d = d_by_id[decision["ruler_id"]]
        ready = bool(ab["score_ready"] and c["score_ready"] and d["D_score_points"] is not None)
        if ready:
            a_points = round(ab["axes"]["A1"]["axis_points"] + ab["axes"]["A2"]["axis_points"], 2)
            b_points = round(ab["axes"]["B1"]["axis_points"] + ab["axes"]["B2"]["axis_points"] + ab["axes"]["B4"]["axis_points"], 2)
            total = round(ab["AB_score_points"] + c["C_score_points"] + d["D_score_points"], 1)
            axes = {
                "A1": {key: ab["axes"]["A1"][key] for key in ("start", "end", "trajectory_value", "axis_points")},
                "A2": {key: ab["axes"]["A2"][key] for key in ("start", "end", "trajectory_value", "axis_points")},
                "B1": {key: ab["axes"]["B1"][key] for key in ("grade", "score_rate", "axis_points")},
                "B2": {key: ab["axes"]["B2"][key] for key in ("grade", "score_rate", "axis_points")},
                "B4": {key: ab["axes"]["B4"][key] for key in ("grade", "score_rate", "axis_points")},
                "C1": c["combat_delivery_grade"], "C2": c["operational_sustainability_cap"],
                "C3": c["system_reliability_cap"], "C_overall": c["C_overall_grade"], "D": d["D_grade"],
            }
        else:
            a_points = b_points = total = None
            axes = {"A1": "UNKNOWN", "A2": "UNKNOWN", "B1": "UNKNOWN", "B2": "UNKNOWN", "B4": "UNKNOWN", "C_overall": "UNKNOWN", "D": "UNKNOWN"}
        rows.append({
            "ruler_id": decision["ruler_id"], "ruler_name": decision["ruler_name"],
            "polity": decision["polity"], "reign_range": decision["reign_range"],
            "rank": None, "rank_status": "GLOBAL_CURRENT",
            "partition": "五代十国", "partition_rank": None,
            "A_score_points": a_points, "B_score_points": b_points,
            "AB_score_points": ab["AB_score_points"], "C_score_points": c["C_score_points"],
            "D_score_points": d["D_score_points"],
            "D_score_status": "DIRECT_D_SCORE_ASSIGNED" if ready else "UNASSESSED",
            "third_item_score_points": total,
            "third_item_score_rate": round(total / 250 * 100, 2) if total is not None else None,
            "axes": axes,
            "coverage_status": {"AB": ab["coverage_status"], "C": c["coverage_status"], "D": d["portfolio_status"]},
            "pending_reason": None if ready else decision["pending_reason"],
            "formal_score_write": False, "database_write": False,
        })
    eligible = sorted((row for row in rows if row["third_item_score_points"] is not None), key=lambda row: (-row["third_item_score_points"], row["ruler_name"]))
    for rank, row in enumerate(eligible, start=1):
        row["partition_rank"] = rank
    return rows


def _assign_global_third_item_ranks(records: Sequence[dict[str, Any]]) -> None:
    eligible = sorted(
        (row for row in records if row.get("third_item_score_points") is not None),
        key=lambda row: (-float(row["third_item_score_points"]), str(row["ruler_name"])),
    )
    previous_score: float | None = None
    current_rank = 0
    eligible_count = len(eligible)
    for position, row in enumerate(eligible, start=1):
        score = float(row["third_item_score_points"])
        if previous_score is None or score != previous_score:
            current_rank = position
            previous_score = score
        row["rank"] = current_rank
        row["rank_status"] = f"GLOBAL_CURRENT_{eligible_count}"


def _axis_numbers(text: str, axis: str) -> list[int]:
    values: list[int] = []
    for line in text.splitlines():
        match = re.search(rf"(?<![A-Z]){axis}(?:=)?([0-6])(?:估)?", line)
        if match:
            values.append(int(match.group(1)))
    return values


def _qin_tang_polity_aliases(polity: str) -> tuple[str, ...]:
    aliases = {
        "蜀汉": ("蜀汉", "蜀方", "蜀"),
        "东汉": ("东汉", "汉方", "汉"),
        "西汉": ("西汉", "汉方", "汉"),
        "东晋": ("东晋", "晋方", "晋"),
        "西晋": ("西晋", "晋方", "晋"),
        "前秦": ("前秦", "秦方"),
        "后秦": ("后秦", "秦方"),
        "北魏": ("北魏", "魏方"),
        "曹魏": ("曹魏", "魏方", "魏"),
    }.get(polity, (polity, f"{polity}方"))
    return tuple(dict.fromkeys(alias for alias in aliases if alias))


def _qin_tang_subject_axis_lines(
    axis_lines: Sequence[str], ruler_name: str, polity: str
) -> tuple[list[str], str]:
    ruler_matches = [line for line in axis_lines if ruler_name and ruler_name in line]
    if ruler_matches:
        return ruler_matches, "RULER_AXIS_LINE"
    aliases = _qin_tang_polity_aliases(polity)
    subject_fragments: list[str] = []
    for line in axis_lines:
        markers = list(re.finditer(r"影子定位（([^）]+)）", line))
        if markers:
            for index, marker in enumerate(markers):
                label = marker.group(1).strip()
                if not any(alias in label for alias in aliases):
                    continue
                stop = markers[index + 1].start() if index + 1 < len(markers) else len(line)
                subject_fragments.append(line[marker.start():stop])
            continue
        subject_match = re.search(
            r"评价主体(?:为|[：:=])\s*([^；;，,。`〔（\s]+)", line
        )
        if subject_match and any(
            alias in subject_match.group(1) for alias in aliases
        ):
            subject_fragments.append(line)
    if subject_fragments:
        return subject_fragments, "POLITY_AXIS_LINE"
    if any("影子定位（" in line or "评价主体" in line for line in axis_lines):
        return [], "NO_SUBJECT_AXIS_LINE"
    return list(axis_lines), "CARD_AXIS_LINE"


def _axis_closed_return_class(
    costs: Mapping[str, int],
    benefits: Mapping[str, int],
    *,
    s_attributable: bool,
) -> tuple[str, str]:
    positive = max(int(benefits[key]) for key in ("SB", "BCP", "WR"))
    negative = max(int(benefits[key]) for key in ("SN", "BCN"))
    cost_values = [int(costs[key]) for key in ("P", "M", "A")]
    if s_attributable:
        cost_values.append(int(costs["S"]))
    cost = max(cost_values)
    structural_cost = max(int(costs["M"]), int(costs["A"]))
    if s_attributable:
        structural_cost = max(structural_cost, int(costs["S"]))
    if negative >= 4:
        result = "NEGATIVE_RETURN"
    elif negative >= 2:
        result = "LOW_RETURN"
    elif positive >= 4:
        result = (
            "HIGH_RETURN" if cost <= 3
            else "PROPORTIONATE_RETURN" if cost == 4
            else "LOW_RETURN"
        )
    elif positive == 3:
        result = (
            "PROPORTIONATE_RETURN" if cost <= 3
            else "NEGATIVE_RETURN" if structural_cost >= 4
            else "LOW_RETURN"
        )
    elif positive == 2:
        result = (
            "PROPORTIONATE_RETURN" if cost <= 2
            else "NEGATIVE_RETURN" if structural_cost >= 4
            else "LOW_RETURN"
        )
    elif positive == 1:
        result = (
            "PROPORTIONATE_RETURN" if cost <= 1
            else "NEGATIVE_RETURN" if structural_cost >= 4
            else "LOW_RETURN"
        )
    else:
        result = "NEGATIVE_RETURN" if cost >= 4 else "LOW_RETURN"
    rationale = (
        f"主体阶段轴线已闭合：正向收益峰值{positive}、负向收益峰值{negative}、"
        f"可归责成本峰值{cost}；按现行成本—收益边界裁为{result}。"
    )
    return result, rationale


def _qin_tang_source_cycle(
    workspace_root: Path,
    ruler: Mapping[str, Any],
    ref: str,
    card_meta: Mapping[str, Any],
    source_cache: dict[str, list[str]],
    override: Mapping[str, Any] | None,
    ambiguous_same_polity_ref: bool,
) -> dict[str, Any]:
    source_file = str(card_meta["source_file"])
    lines = source_cache.setdefault(
        source_file,
        (workspace_root / source_file).read_text(encoding="utf-8").splitlines(),
    )
    start = int(card_meta["heading_line"]) - 1
    end = next(
        (index for index in range(start + 1, len(lines)) if lines[index].startswith("### ")),
        len(lines),
    )
    section_lines = lines[start:end]
    section_text = "\n".join(section_lines)
    axis_lines = [
        line
        for line in section_lines
        if "影子定位" in line or "WC四轴迁移" in line or "成本四轴" in line
    ]
    ruler_name = str(ruler.get("ruler_name") or "")
    polity = str(ruler.get("polity") or "")
    selected_lines, axis_selection_basis = _qin_tang_subject_axis_lines(
        axis_lines, ruler_name, polity
    )
    cost_text = "\n".join(selected_lines)
    benefit_text = "\n".join(
        selected_lines + [line for line in section_lines if "SB/WR依据" in line]
    )
    costs = {
        axis: max(_axis_numbers(cost_text, axis) or [0])
        for axis in ("P", "S", "M", "A")
    }
    benefits = {
        axis: max(_axis_numbers(benefit_text, axis) or [0])
        for axis in ("SB", "SN", "BCP", "BCN", "WR")
    }
    override_values = dict((override or {}).get("values") or {})
    override_costs = override_values.get("d_cost_axes") or override_values.get("cost_axes") or {}
    has_full_subject_override = bool(
        override_values.get("d_cost_axes")
        and override_values.get("return_class")
    )
    for axis in ("P", "M", "A"):
        if axis in override_costs:
            costs[axis] = max(_axis_numbers(str(override_costs[axis]), axis) or [costs[axis]])
    if override_values.get("s_effective_grade") is not None:
        costs["S"] = max(
            _axis_numbers(str(override_values["s_effective_grade"]), "S")
            or [costs["S"]]
        )
    for positive_axis, negative_axis, field in (
        ("SB", "SN", "strategic_security_grade"),
        ("BCP", "BCN", "border_control_grade"),
    ):
        value = override_values.get(field)
        if value is None:
            continue
        benefits[positive_axis] = max(
            benefits[positive_axis],
            max(_axis_numbers(str(value), positive_axis) or [0]),
        )
        benefits[negative_axis] = max(
            benefits[negative_axis],
            max(_axis_numbers(str(value), negative_axis) or [0]),
        )
    metrics = ruler.get("D_portfolio_metrics") or {}
    attributable_s_refs = set(metrics.get("hard_attributable_s4_plus_refs") or ()) | set(
        metrics.get("attributable_s4_plus_refs") or ()
    )
    s_attributable = ref in attributable_s_refs
    material = (
        max(costs[axis] for axis in ("P", "M", "A")) >= 3
        or max(benefits[axis] for axis in ("SB", "SN", "BCP", "BCN")) >= 3
        or (s_attributable and costs["S"] >= 3)
    )
    subject_window_ambiguous = ambiguous_same_polity_ref and not has_full_subject_override
    if subject_window_ambiguous:
        material = False
    explicit_class = str(override_values.get("return_class") or "")
    if explicit_class == "PROPORTIONATE":
        explicit_class = "PROPORTIONATE_RETURN"
    if explicit_class in {
        "HIGH_RETURN", "PROPORTIONATE_RETURN", "LOW_RETURN", "NEGATIVE_RETURN", "UNKNOWN"
    }:
        return_class = explicit_class
        class_basis = "RULER_PHASE_OVERRIDE"
    elif ref in set(metrics.get("national_negative_return_refs") or ()):
        return_class = "NEGATIVE_RETURN"
        class_basis = "CURRENT_NATIONAL_NEGATIVE_ADJUDICATION"
    elif ref in set(ruler.get("negative_benefit_cycle_refs") or ()):
        axis_class, axis_rationale = _axis_closed_return_class(
            costs, benefits, s_attributable=s_attributable
        )
        return_class = (
            "NEGATIVE_RETURN" if axis_class == "NEGATIVE_RETURN" else "LOW_RETURN"
        )
        class_basis = (
            "SUBJECT_AXIS_NEGATIVE_SEVERITY_ADJUDICATION"
            if return_class == "NEGATIVE_RETURN"
            else "CURRENT_NEGATIVE_DIRECTION_ADJUDICATION"
        )
        return_class_rationale = axis_rationale
    elif ref in set(ruler.get("positive_benefit_cycle_refs") or ()):
        axis_class, axis_rationale = _axis_closed_return_class(
            costs, benefits, s_attributable=s_attributable
        )
        benefit_axes_present = any(
            _axis_numbers(benefit_text, axis)
            for axis in ("SB", "SN", "BCP", "BCN", "WR")
        )
        if axis_class == "NEGATIVE_RETURN" and benefit_axes_present:
            return_class = "NEGATIVE_RETURN"
            class_basis = "SUBJECT_AXIS_POSITIVE_DIRECTION_OVERRIDDEN"
            return_class_rationale = axis_rationale
        else:
            return_class = (
                "HIGH_RETURN"
                if ref in set(metrics.get("major_high_return_refs") or ())
                else "PROPORTIONATE_RETURN"
            )
            class_basis = "CURRENT_POSITIVE_DIRECTION_ADJUDICATION"
    else:
        return_class, return_class_rationale = _axis_closed_return_class(
            costs, benefits, s_attributable=s_attributable
        )
        class_basis = "SUBJECT_AXIS_CLOSED_RETURN_ADJUDICATION"
    if class_basis not in {
        "SUBJECT_AXIS_CLOSED_RETURN_ADJUDICATION",
        "SUBJECT_AXIS_NEGATIVE_SEVERITY_ADJUDICATION",
        "SUBJECT_AXIS_POSITIVE_DIRECTION_OVERRIDDEN",
    }:
        return_class_rationale = (
            str(override_values.get("return_rationale") or "").strip()
            or f"沿用已闭合的{class_basis}回报裁决。"
        )
    machine_settlement = (
        "no" if "machine_settlement=no" in section_text
        else "yes" if "machine_settlement=yes" in section_text
        else "UNKNOWN"
    )
    owner_match = re.search(r"settlement_owner=([^`;\s]+)", section_text)
    settlement_owner = owner_match.group(1) if owner_match else None
    return {
        "campaign_group_ref": ref,
        "war_event_refs": [ref],
        "phase_ids": [],
        "return_class": return_class,
        "cost_axes": costs,
        "benefit_axes": benefits,
        "material": material,
        "unknown_axes": (
            ["SUBJECT_REIGN_COST_BENEFIT_SPLIT"] if subject_window_ambiguous else []
        ),
        "major_high_return": material and ref in set(metrics.get("major_high_return_refs") or ()),
        "top_high_return": material and ref in set(metrics.get("top_tier_high_return_refs") or ()),
        "national_negative": material and return_class == "NEGATIVE_RETURN" and (
            costs["P"] >= 5
            or costs["M"] >= 4
            or costs["A"] >= 4
            or benefits["SN"] >= 4
            or benefits["BCN"] >= 4
        ),
        "route": (
            "D_INTERNAL_COST_ONLY"
            if re.search(r"MUTINY|REBELLION|REVOLT", ref)
            else "D_STANDARD"
        ),
        "source_file": source_file,
        "source_heading_line": int(card_meta["heading_line"]),
        "axis_selection_basis": (
            "RULER_PHASE_OVERRIDE" if has_full_subject_override else axis_selection_basis
        ),
        "return_class_basis": class_basis,
        "return_class_rationale": return_class_rationale,
        "machine_settlement": machine_settlement,
        "settlement_owner": settlement_owner,
    }


def _recalculate_qin_tang_d_records(
    workspace_root: Path,
    records: Sequence[dict[str, Any]],
    ab_records: Sequence[Mapping[str, Any]],
    c_records: Sequence[Mapping[str, Any]],
) -> None:
    index_payload = json.loads(
        (workspace_root / QIN_TANG_BATTLE_INDEX_PATH).read_text(encoding="utf-8")
    )
    index_rows = index_payload.get("cards") or index_payload.get("records") or index_payload
    cards_by_id = {str(row["source_card_id"]): row for row in index_rows}
    direction_payload = json.loads(
        (workspace_root / QIN_TANG_D_DIRECTION_PATH).read_text(encoding="utf-8")
    )
    if direction_payload.get("schema_version") != "qin-tang-d-cycle-direction-adjudications-v1":
        raise ValueError("秦至唐D周期方向裁决输入schema错误")
    direction_by_id = {
        str(item["ruler_id"]): item for item in direction_payload["records"]
    }
    first_item_payload = json.loads(
        (workspace_root / FIRST_ITEM_C_WINDOWS_PATH).read_text(encoding="utf-8")
    )
    founding_refs_by_name = {
        str(item["ruler_name"]): {
            str(ref) for ref in item.get("campaign_refs") or ()
        }
        for item in first_item_payload.get("manual_windows") or ()
    }
    founding_refs_by_name.setdefault("杨坚", set()).add(
        "WAR-LEAD-SUI-ABSORB-LIANG-587"
    )
    founding_refs_by_name.setdefault("沮渠蒙逊", set()).add(
        "WAR-LEAD-112-MENGXUN-401"
    )
    founding_refs_by_name.setdefault("拓跋珪", set()).update(
        {"WAR-LEAD-112-WEI-MOYIGAN-402", "WAR-LEAD-115-WEI-SUCCESSION-409"}
    )
    qin_tang_ids = {
        str(row.get("ruler_id"))
        for row in records
        if not str(row.get("ruler_id") or "").startswith(("RULER-FD-", "RULER-NS-"))
    }
    if set(direction_by_id) != qin_tang_ids:
        raise ValueError("秦至唐D周期方向裁决输入与95人正式集合不一致")
    ab_by_id = {str(row.get("ruler_id")): row for row in ab_records}
    c_by_id = {str(row.get("ruler_id")): row for row in c_records}
    source_cache: dict[str, list[str]] = {}
    ref_polity_owners: dict[str, list[str]] = defaultdict(list)
    for candidate_row in records:
        candidate_id = str(candidate_row.get("ruler_id") or "")
        if candidate_id.startswith(("RULER-FD-", "RULER-NS-")):
            continue
        for candidate_ref in (
            candidate_row.get("included_d_cycle_refs")
            or candidate_row.get("d_cycle_refs")
            or ()
        ):
            ref_polity_owners[str(candidate_ref)].append(
                str(candidate_row.get("polity") or "")
            )
    for row in records:
        ruler_id = str(row.get("ruler_id") or "")
        if ruler_id.startswith(("RULER-FD-", "RULER-NS-")):
            continue
        if ruler_id not in direction_by_id:
            raise ValueError(f"{row.get('ruler_name')}缺少秦至唐D周期方向裁决输入")
        direction = direction_by_id[ruler_id]
        overrides = {
            str(item.get("war_event_id")): item
            for item in (direction.get("ruler_event_class_overrides") or ())
        }
        source_ruler = dict(row)
        source_ruler["positive_benefit_cycle_refs"] = list(
            direction.get("positive_benefit_cycle_refs") or ()
        )
        source_ruler["negative_benefit_cycle_refs"] = list(
            direction.get("negative_benefit_cycle_refs") or ()
        )
        source_metrics = dict(row.get("D_portfolio_metrics") or {})
        for key in (
            "major_high_return_refs",
            "top_tier_high_return_refs",
            "national_negative_return_refs",
        ):
            source_metrics[key] = list(direction.get(key) or ())
        source_ruler["D_portfolio_metrics"] = source_metrics
        row["ruler_event_class_overrides"] = list(
            direction.get("ruler_event_class_overrides") or ()
        )
        refs = [
            str(ref)
            for ref in (row.get("included_d_cycle_refs") or row.get("d_cycle_refs") or ())
        ]
        missing = [ref for ref in refs if ref not in cards_by_id]
        if missing:
            raise ValueError(f"{row.get('ruler_name')}的D周期无法回源：{missing}")
        candidates = [
            _qin_tang_source_cycle(
                workspace_root,
                source_ruler,
                ref,
                cards_by_id[ref],
                source_cache,
                overrides.get(ref),
                len(ref_polity_owners[ref]) > len(set(ref_polity_owners[ref])),
            )
            for ref in refs
        ]
        founding_refs = founding_refs_by_name.get(str(row["ruler_name"]), set())
        excluded = [
            cycle
            for cycle in candidates
            if cycle["machine_settlement"] == "no"
            or cycle["campaign_group_ref"] in founding_refs
        ]
        cycles = [cycle for cycle in candidates if cycle not in excluded]
        ab_score = float(ab_by_id[ruler_id]["AB_score_points"])
        c_score = float(c_by_id[ruler_id]["C_score_points"])
        grade, score, metrics = _d_grade_and_score(
            cycles,
            allow_exceptional_national_recovery=(ab_score >= 80 and c_score >= 30),
        )
        if (
            grade in {"D-4", "D-5"}
            and 2 <= int(metrics["known_material_cycle_count"]) <= 3
            and (ab_score < 80 or c_score < 30)
        ):
            grade = "D-3"
            lower, upper = D_BANDS[grade]
            score = round((lower + upper) / 2, 1)
            metrics["abc_small_sample_gate"] = "CAPPED_TO_D3"
        manual_d0 = bool(row.get("manual_portfolio_override")) and row.get("D_grade") == "D-0"
        if manual_d0:
            grade = "D-0"
            score = float(row["D_score_points"])
        metrics["abc_crosscheck"] = {
            "ab_score_points": ab_score,
            "ab_threshold_points": 80.0,
            "c_score_points": c_score,
            "c_threshold_points": 30.0,
            "small_sample_high_grade_gate_applied": metrics.get("abc_small_sample_gate") == "CAPPED_TO_D3",
            "status": "SUFFICIENT_SUPPORT" if ab_score >= 80 and c_score >= 30 else "INSUFFICIENT_SUPPORT",
        }
        metrics["material_cycle_adjudications"] = [
            {
                "campaign_group_ref": cycle["campaign_group_ref"],
                "material": cycle["material"],
                "return_class": cycle["return_class"],
                "cost_axes": cycle["cost_axes"],
                "benefit_axes": cycle["benefit_axes"],
                "axis_selection_basis": cycle["axis_selection_basis"],
                "return_class_basis": cycle["return_class_basis"],
                "return_class_rationale": cycle["return_class_rationale"],
                "source_ref": f"{cycle['source_file']}#L{cycle['source_heading_line']}",
            }
            for cycle in cycles
        ]
        metrics["parent_cycle_policy"] = "TERMINAL_OR_LEGACY_PARENT_ONLY"
        row["D_grade"] = grade
        row["D_score_points"] = score
        lower, upper = D_BANDS.get(grade, (20.0, 20.0))
        row["D_score_band"] = {
            "lower_points": lower,
            "upper_points": upper,
        }
        row["D_grade_reasons"] = (
            row.get("D_grade_reasons")
            if manual_d0
            else _d_grade_reasons(grade, metrics)
        )
        row["D_portfolio_metrics"] = metrics
        row["included_d_cycle_refs"] = [cycle["campaign_group_ref"] for cycle in cycles]
        row["excluded_nonterminal_cycle_refs"] = [cycle["campaign_group_ref"] for cycle in excluded]
        row["excluded_cycle_adjudications"] = [
            {
                "campaign_group_ref": cycle["campaign_group_ref"],
                "reason": (
                    "FOUNDING_UNIFICATION_ACCOUNT_EXCLUDED_FROM_THIRD_ITEM"
                    if cycle["campaign_group_ref"] in founding_refs
                    else "NON_TERMINAL_PARENT_STAGE_EXCLUDED_FROM_D"
                ),
                "settlement_owner": cycle["settlement_owner"],
            }
            for cycle in excluded
        ]
        row["positive_benefit_cycle_refs"] = [
            cycle["campaign_group_ref"]
            for cycle in cycles
            if cycle["return_class"] in {"HIGH_RETURN", "PROPORTIONATE_RETURN"}
        ]
        row["negative_benefit_cycle_refs"] = [
            cycle["campaign_group_ref"]
            for cycle in cycles
            if cycle["return_class"] in {"LOW_RETURN", "NEGATIVE_RETURN"}
        ]
        row["unresolved_cycle_refs"] = [
            cycle["campaign_group_ref"]
            for cycle in cycles
            if cycle["return_class"] == "UNKNOWN"
        ]
        row["high_cost_cycle_refs"] = [
            cycle["campaign_group_ref"]
            for cycle in cycles
            if max(cycle["cost_axes"][axis] for axis in ("P", "S", "M", "A")) >= 4
        ]
        row["zero_return_high_cost_cycle_refs"] = [
            cycle["campaign_group_ref"]
            for cycle in cycles
            if cycle["campaign_group_ref"] in row["high_cost_cycle_refs"]
            and cycle["return_class"] in {"LOW_RETURN", "NEGATIVE_RETURN"}
        ]
        row["peak_d_cost_axes"] = {
            axis: f"{axis}{max((cycle['cost_axes'][axis] for cycle in cycles), default=0)}"
            for axis in ("P", "M", "A")
        }
        row["binding_source"] = "QIN_TANG_PARENT_CYCLE_CURRENT_RECALCULATION"


def _normalize_formal_d_records(records: Sequence[dict[str, Any]]) -> None:
    for row in records:
        metrics = row.get("D_portfolio_metrics") or {}
        counts = dict(metrics.get("return_class_counts") or {})
        legacy_proportionate = int(counts.pop("PROPORTIONATE", 0))
        if legacy_proportionate:
            counts["PROPORTIONATE_RETURN"] = (
                int(counts.get("PROPORTIONATE_RETURN", 0)) + legacy_proportionate
            )
            metrics["return_class_counts"] = dict(sorted(counts.items()))
        material_count = metrics.get("material_cycle_count")
        if material_count is not None:
            material_count = int(material_count)
            known_material_count = int(
                metrics.get("known_material_cycle_count", material_count)
            )
            metrics["evidence_status"] = (
                "UNDER_TESTED"
                if known_material_count <= 1
                else "LIMITED_EXPOSURE"
                if known_material_count <= 3
                else "SUFFICIENT_EXPOSURE"
            )
        if (
            row.get("D_grade") in {"D-4", "D-5"}
            and int(counts.get("NEGATIVE_RETURN", 0)) == 0
        ):
            metrics.setdefault("material_negative_return_refs", [])
        metrics.pop("material_only_recalibration", None)


def _sync_formal_d_into_combined(
    d_records: Sequence[Mapping[str, Any]],
    combined_records: Sequence[dict[str, Any]],
) -> None:
    d_by_id = {str(row.get("ruler_id")): row for row in d_records}
    for row in combined_records:
        ruler_id = str(row.get("ruler_id") or "")
        if ruler_id not in d_by_id or row.get("third_item_score_points") is None:
            continue
        d_row = d_by_id[ruler_id]
        row["D_score_points"] = d_row["D_score_points"]
        row["axes"]["D"] = d_row["D_grade"]
        total = round(
            float(row["AB_score_points"])
            + float(row["C_score_points"])
            + float(row["D_score_points"]),
            1,
        )
        row["third_item_score_points"] = total
        row["third_item_score_rate"] = round(total / 250 * 100, 2)


def _sync_formal_c_into_combined(
    c_records: Sequence[Mapping[str, Any]],
    combined_records: Sequence[dict[str, Any]],
) -> None:
    c_by_id = {str(row.get("ruler_id")): row for row in c_records}
    for row in combined_records:
        ruler_id = str(row.get("ruler_id") or "")
        if ruler_id not in c_by_id or row.get("third_item_score_points") is None:
            continue
        c_row = c_by_id[ruler_id]
        row["C_score_points"] = c_row["C_score_points"]
        row["axes"]["C"] = c_row["C_overall_grade"]
        total = round(
            float(row["AB_score_points"])
            + float(row["C_score_points"])
            + float(row["D_score_points"]),
            1,
        )
        row["third_item_score_points"] = total
        row["third_item_score_rate"] = round(total / 250 * 100, 2)


def build_five_dynasties_formal_payloads(
    workspace_root: Path, registry: Mapping[str, Any]
) -> dict[str, Any]:
    adjudications = _load_adjudications(workspace_root)
    ab_records = build_five_dynasties_ab_records(registry, adjudications)
    c_records = build_five_dynasties_c_records(registry, adjudications)
    _validate_bc_parent_cycle_alignment(ab_records, c_records)
    d_records = build_five_dynasties_d_records(registry, adjudications, ab_records, c_records)
    combined_records = _build_combined_records(adjudications, ab_records, c_records, d_records)

    ab = _replace_partition_records(json.loads((workspace_root / AB_PATH).read_text(encoding="utf-8")), ab_records)
    existing_combined = json.loads((workspace_root / FORMAL_PATH).read_text(encoding="utf-8"))
    north_song_count = sum(str(row.get("ruler_id", "")).startswith("RULER-NS-") for row in existing_combined["records"])
    extension = f" + 北宋{north_song_count}人" if north_song_count else ""
    ab.update({
        "scope": f"秦至唐95人当前值 + 五代十国12人当前结算{extension}",
        "ruler_count": len(ab["records"]), "reviewed_count": sum(row.get("adjudication_status") == "REVIEWED" for row in ab["records"]),
        "pending_count": sum(not row.get("score_ready") for row in ab["records"]),
        "score_ready_count": sum(bool(row.get("score_ready")) for row in ab["records"]),
        "five_dynasties_source_fingerprint": SOURCE_SET_FINGERPRINT,
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
        "five_dynasties_source_fingerprint": SOURCE_SET_FINGERPRINT,
    })
    d = _replace_partition_records(json.loads((workspace_root / D_PATH).read_text(encoding="utf-8")), d_records)
    _recalculate_qin_tang_d_records(
        workspace_root,
        d["records"],
        ab["records"],
        c["records"],
    )
    _normalize_formal_d_records(d["records"])
    d.update({
        "scope": f"秦至唐95人父级实质周期统一重算 + 五代十国12人当前结算{extension}",
        "record_count": len(d["records"]),
        "grade_distribution": dict(sorted(Counter(str(row.get("D_grade")) for row in d["records"]).items())),
        "five_dynasties_source_fingerprint": SOURCE_SET_FINGERPRINT,
        "score_recalculation_policy": "ALL_RECORDS_REVIEWABLE_CURRENT_VALUE",
    })
    combined = _replace_partition_records(existing_combined, combined_records)
    _sync_formal_c_into_combined(c["records"], combined["records"])
    _sync_formal_d_into_combined(d["records"], combined["records"])
    _assign_global_third_item_ranks(combined["records"])
    combined.pop("qin_tang_rank_freeze", None)
    combined.pop("qin_tang_value_freeze", None)
    combined.update({
        "scope": f"秦至唐95人当前分值 + 五代十国12人{extension}；第三项{len(combined['records'])}人统一排名",
        "record_count": len(combined["records"]),
        "score_ready_count": sum(row.get("third_item_score_points") is not None for row in combined["records"]),
        "D_unassessed_neutral_count": sum(row.get("D_score_points") is None for row in combined["records"]),
        "five_dynasties_source_fingerprint": SOURCE_SET_FINGERPRINT,
        "five_dynasties_ready_count": sum(row.get("third_item_score_points") is not None for row in combined_records),
        "five_dynasties_pending_count": sum(row.get("third_item_score_points") is None for row in combined_records),
        "score_recalculation_policy": "ALL_RECORDS_REVIEWABLE_CURRENT_VALUE",
        "global_ranking_enabled": True,
        "rank_tie_policy": "COMPETITION_RANK",
        "shared_source_root": "docs/史料通读产物",
    })
    return {"AB": ab, "C": c, "D": d, "combined": combined, "partition_records": combined_records}


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
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return f"{value[0]}-{value[1]}"
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
    score_key = {"AB": "AB_score_points", "C": "C_score_points", "D": "D_score_points"}[kind]
    ranked = _competition_ranked_records(records, score_key)
    values = [float(row[score_key]) for _, row in ranked]
    definitions = {
        "AB": {
            "title": "# 秦至北宋第三项A/B国防安全正式结算",
            "rule": "[`A/B规则与结算合同`](../../../分项规则/第三项军事与边疆净收益/国防安全/00-规则与结算合同.md)",
            "description": "A战略安全收益80分与B边疆控制净收益80分",
            "maximum": 160,
        },
        "C": {
            "title": "# 秦至北宋第三项C军事体系有效性正式结算",
            "rule": "[`C规则与计分合同`](../../../分项规则/第三项军事与边疆净收益/军事体系有效性/00-规则与计分合同.md)",
            "description": "C军事体系有效性50分",
            "maximum": 50,
        },
        "D": {
            "title": "# 秦至北宋第三项D军事成本收益比正式结算",
            "rule": "[`D规则与结算合同`](../../../分项规则/第三项军事与边疆净收益/军事成本收益比/00-规则与结算合同.md)",
            "description": "D军事成本收益比40分",
            "maximum": 40,
        },
    }
    definition = definitions[kind]
    lines = [
        definition["title"],
        "",
        f"规则见{definition['rule']}。本表是同名JSON的统一人工阅读视图，按{definition['description']}当前正式值从高到低排列。",
        "",
        f"共{len(ranked)}位评价主体，得分范围{min(values):.1f}—{max(values):.1f}。同分并列，后一名次按竞赛排名顺延；所有分值统一显示一位小数。秦至北宋全部记录均为可复核当前值，所有朝代同等允许更新且不设保值例外。表后“逐人结算依据”展示当前裁决理由；机器读取仍以同名JSON为准。",
        "",
    ]
    if kind == "AB":
        lines += [
            "| 排名 | 皇帝 | 政权 | 在位 | A1/40 | A2/40 | A/80 | B1/25 | B2/30 | B4/25 | B/80 | A/B总分/160 |",
            "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for rank, row in ranked:
            axes = row["axes"]
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
    elif kind == "C":
        lines += [
            "| 排名 | 皇帝 | 政权 | 在位 | C1 | C2 | C3 | C总体 | 得分率 | C/50 | 独立任务 |",
            "|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for rank, row in ranked:
            lines.append(
                f"| {rank} | {row['ruler_name']} | {row['polity']} | {_reign_range_label(row['reign_range'])} | "
                f"{row['combat_delivery_grade']} | {row['operational_sustainability_cap']} | "
                f"{row['system_reliability_cap']} | {row['C_overall_grade']} | "
                f"{float(row['C_score_rate']):.1f}% | {float(row[score_key]):.1f} | "
                f"{int(row['independent_task_count'])} |"
            )
    else:
        lines += [
            "| 排名 | 皇帝 | 政权 | 在位 | D档 | D/40 | 检验状态 | 实质周期 | 高收益 | 相称收益 | 低收益 | 负收益 | 回报未知 | 重大高收益 | 顶尖高收益 | 国家级负收益 |",
            "|---:|---|---|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        status_labels = {
            "SUFFICIENT_EXPOSURE": "充分检验",
            "LIMITED_EXPOSURE": "有限检验",
            "UNDER_TESTED": "检验不足",
            "UNASSESSED": "未检验",
        }
        for rank, row in ranked:
            metrics = row.get("D_portfolio_metrics") or {}
            counts = metrics.get("material_return_class_counts")
            if counts is None:
                raise ValueError(f"{row.get('ruler_name')}缺少实质周期回报分布，拒绝渲染为零")
            count_keys = (
                "HIGH_RETURN", "PROPORTIONATE_RETURN", "LOW_RETURN",
                "NEGATIVE_RETURN", "UNKNOWN",
            )
            count_cells = [str(int(counts.get(key, 0))) for key in count_keys]
            if sum(int(counts.get(key, 0)) for key in count_keys) != int(
                metrics.get("material_cycle_count", 0)
            ):
                raise ValueError(f"{row.get('ruler_name')}的实质周期总数与回报分布不闭合")
            grade = str(row.get("D_grade") or "D-U")
            evidence_status = str(metrics.get("evidence_status") or "UNASSESSED")
            if grade == "D-U":
                evidence_status = "UNASSESSED"
            lines.append(
                f"| {rank} | {row['ruler_name']} | {row['polity']} | {_reign_range_label(row['reign_range'])} | "
                f"{grade} | {float(row[score_key]):.1f} | {status_labels.get(evidence_status, evidence_status)} | "
                f"{int(metrics.get('material_cycle_count', 0))} | "
                f"{' | '.join(count_cells)} | "
                f"{len(metrics.get('major_high_return_refs') or [])} | "
                f"{len(metrics.get('top_tier_high_return_refs') or [])} | "
                f"{len(metrics.get('national_negative_return_refs') or [])} |"
            )
    lines += ["", "## 逐人结算依据", ""]
    for rank, row in ranked:
        lines += [f"### {rank}. {row['ruler_name']}（{float(row[score_key]):.1f}）", ""]
        if kind == "AB":
            lines += [f"- 裁决：{_ab_settlement_basis(row)}", ""]
        elif kind == "C":
            c_basis = _joined_reasons(row.get("cap_reasons") or []) or "按C1、C2、C3短板门槛与独立任务暴露定档。"
            success_refs = row.get("major_system_success_refs") or []
            failure_refs = row.get("major_system_failure_refs") or []
            lines += [
                f"- 档位路径：{row['combat_delivery_grade']}／{row['operational_sustainability_cap']}／{row['system_reliability_cap']}→{row['C_overall_grade']}。",
                f"- 样本：去重独立任务{int(row['independent_task_count'])}项。",
                f"- 重大胜负：重大胜绩{len(success_refs)}项、重大体系失败{len(failure_refs)}项；胜绩门禁{(row.get('major_victory_gate') or {}).get('status', 'NOT_APPLICABLE')}。",
                f"- 裁决：{_markdown_cell(c_basis)}",
                "",
            ]
        else:
            metrics = row.get("D_portfolio_metrics") or {}
            counts = metrics.get("material_return_class_counts")
            return_summary = (
                f"高收益{int(counts.get('HIGH_RETURN', 0))}、相称收益{int(counts.get('PROPORTIONATE_RETURN', 0))}、低收益{int(counts.get('LOW_RETURN', 0))}、负收益{int(counts.get('NEGATIVE_RETURN', 0))}、回报未知{int(counts.get('UNKNOWN', 0))}"
                if counts is not None
                else "实质回报分布缺失"
            )
            d_basis = _joined_reasons(row.get("D_grade_reasons") or []) or "按去重战略周期的成本、回报与证据暴露定档。"
            lines += [
                f"- 组合：战术观察节点{int(metrics.get('usable_cycle_count', 0))}项（只作审计，不作为跨人物样本量）；去重实质投资周期{int(metrics.get('material_cycle_count', 0))}项，其中{return_summary}；重大高收益{len(metrics.get('major_high_return_refs') or [])}、顶尖高收益{len(metrics.get('top_tier_high_return_refs') or [])}、国家级负收益{len(metrics.get('national_negative_return_refs') or [])}。",
                f"- 裁决：{_markdown_cell(d_basis)}",
            ]
            excluded = row.get("excluded_cycle_adjudications") or []
            if excluded:
                exclusion_text = "；".join(
                    f"{item['campaign_group_ref']}（{item['reason']}）"
                    for item in excluded
                )
                lines.append(f"- 排除：{_markdown_cell(exclusion_text)}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_combined_markdown(records: Sequence[Mapping[str, Any]]) -> str:
    eligible = sorted(
        (row for row in records if row.get("third_item_score_points") is not None),
        key=lambda row: (int(row["rank"]), -float(row["third_item_score_points"]), str(row["ruler_name"])),
    )
    values = [float(row["third_item_score_points"]) for row in eligible]
    north_song_count = sum(str(row.get("ruler_id", "")).startswith("RULER-NS-") for row in eligible)
    title = "# 秦至北宋第三项军事与边疆正式结算" if north_song_count else "# 秦至五代十国第三项军事与边疆正式结算"
    extension_note = (
        f"五代十国12人与北宋{north_song_count}人已进入同一总榜；北宋卷001至097已闭合徽宗退位、钦宗主政与靖康覆亡。"
        if north_song_count else "五代十国12人已进入同一总榜。"
    )
    lines = [
        title,
        "",
        "规则总入口见[`docs/分项规则/第三项军事与边疆净收益`](../../分项规则/第三项军事与边疆净收益/README.md)。本表将A战略安全收益80分、B边疆控制净收益80分、C军事体系有效性50分、D军事成本收益比40分合并为第三项250分当前正式值；机器读取入口为同名JSON。",
        "",
        f"共{len(eligible)}位评价主体，得分范围{min(values):.1f}—{max(values):.1f}。同分并列，后一名次按竞赛排名顺延。秦至北宋全部对象均按当前规则形成可复核当前值，所有朝代同等允许更新且不设保值例外；{extension_note}D-U固定20分仅是未检验中性值，不得解释为D项能力中等。表后“逐人结算依据”展示A/B/C/D档位合成路径，具体史实理由见三份分项正式结算。",
        "",
        "| 排名 | 皇帝 | 政权 | 在位 | A/80 | B/80 | C/50 | D/40 | 总分/250 |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in eligible:
        d_label = str((row.get("axes") or {}).get("D") or "UNKNOWN")
        d_value = f"{d_label}/{float(row['D_score_points']):.1f}"
        if d_label == "D-U":
            d_value += "（未检验）"
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
    return "\n".join(lines).rstrip() + "\n"


def write_five_dynasties_third_item(workspace_root: Path) -> dict[str, Any]:
    promotion_audit = write_promoted_battle_registry(workspace_root)
    registry = json.loads((workspace_root / REGISTRY_PATH).read_text(encoding="utf-8"))
    payloads = build_five_dynasties_formal_payloads(workspace_root, registry)
    paths = {"AB": AB_PATH, "C": C_PATH, "D": D_PATH, "combined": FORMAL_PATH}
    md_paths = {
        "AB": AB_PATH.with_suffix(".md"), "C": C_PATH.with_suffix(".md"),
        "D": D_PATH.with_suffix(".md"), "combined": FORMAL_PATH.with_suffix(".md"),
    }
    for kind, path in paths.items():
        target = workspace_root / path
        _write_text_atomic(
            target, json.dumps(payloads[kind], ensure_ascii=False, indent=2) + "\n"
        )
        md_target = workspace_root / md_paths[kind]
        if kind == "combined":
            _write_text_atomic(
                md_target, _render_combined_markdown(payloads[kind]["records"])
            )
        else:
            _write_text_atomic(
                md_target, _render_formal_markdown(kind, payloads[kind]["records"])
            )
    hashes = {kind: sha256((workspace_root / path).read_bytes()).hexdigest() for kind, path in paths.items()}
    hashes["battle_registry"] = sha256((workspace_root / REGISTRY_PATH).read_bytes()).hexdigest()
    return {
        "promotion_audit": promotion_audit,
        "formal_ready_count": payloads["combined"]["five_dynasties_ready_count"],
        "formal_pending_count": payloads["combined"]["five_dynasties_pending_count"],
        "hashes": hashes,
        "records": payloads["partition_records"],
    }


def main() -> int:
    workspace_root = Path.cwd()
    result = write_five_dynasties_third_item(workspace_root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
