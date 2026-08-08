from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence


SOURCE_ROOT = Path("docs/史料通读产物/五代十国/资治通鉴")
REGISTRY_PATH = Path("docs/公共成果/军事/01-战役登记.json")
REGISTRY_MARKDOWN_PATH = Path("docs/公共成果/军事/01-战役登记.md")
ADJUDICATION_PATH = Path("config/five-dynasties-third-item-adjudications.json")
AB_PATH = Path("docs/评分结算/第三项军事与边疆净收益/国防安全/01-皇帝AB项正式结算.json")
C_PATH = Path("docs/评分结算/第三项军事与边疆净收益/军事体系有效性/01-皇帝C项正式结算.json")
D_PATH = Path("docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json")
FORMAL_PATH = Path("docs/评分结算/第三项军事与边疆净收益/02-第三项正式结算.json")
INPUT_SCHEMA = "chronicle-battle-adjudication-v2"
REGISTRY_SCHEMA = "battle-parent-contract-registry-v5"
SOURCE_SET_FINGERPRINT = (
    "d23622b8545ee5a49e06b93ad265a47e1a9643be844899eabd76ab92717fed57"
)
RETIRED_STALE_FIVE_DYNASTIES_RECORD_COUNT = 433


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
    for polity, markers in POLITY_MARKERS:
        if any(marker in text for marker in markers):
            if polity == "后唐" and "晋军" in text and year_range[1] < 923:
                return "后唐"
            return polity
    return None


def _bind_ruler(
    phase: Mapping[str, Any], year_range: tuple[int, int]
) -> dict[str, Any]:
    subject_text = "；".join(
        str(phase.get(field) or "")
        for field in ("evaluation_subject_phase", "actual_process")
    )
    text = "；".join((subject_text, str(phase.get("carry_in") or ""), str(phase.get("carry_out") or "")))
    polity = _infer_polity(str(phase.get("evaluation_subject_phase") or ""), year_range)
    if polity is None:
        polity = _infer_polity(str(phase.get("actual_process") or ""), year_range)
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
    found_boundary_inclusions: set[str] = set()
    for record in promotion["records"]:
        for phase in record.get("subject_phase_views") or ():
            phase_id = str(phase["phase_id"])
            if phase_id not in boundary_inclusions:
                continue
            binding = phase["ruler_binding"]
            if binding.get("status") != "BOUND_YEAR_WINDOW_BOUNDARY":
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
    path.write_text(json.dumps(promoted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    from emperor_v4.evaluation.battle_parent_contract_registry import (
        render_battle_parent_contract_registry_markdown,
    )

    (workspace_root / REGISTRY_MARKDOWN_PATH).write_text(
        render_battle_parent_contract_registry_markdown(promoted), encoding="utf-8"
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
        cycles, event_refs, phase_refs = _cycles_and_refs(registry, str(decision["ruler_id"]))
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
            "defense_event_count": len(cycles),
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
                "control_contribution_type": "NEW_RECOVERED_REBUILT" if end > start else "HOLD_OR_RETREAT",
                "control_contribution_grade_cap": int(decision["AB"]["B1"]["grade"]),
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


def build_five_dynasties_c_records(
    registry: Mapping[str, Any], adjudications: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    records = []
    for decision in adjudications:
        cycles, event_refs, _ = _cycles_and_refs(registry, str(decision["ruler_id"]))
        third_item_cycles = [
            cycle for cycle in cycles
            if not any(phase["founding_startup_ledger"]["is_founding_process"] for phase in cycle["phases"])
        ]
        ready = bool(decision.get("score_ready", decision.get("coverage_complete", False)))
        base = {
            "ruler_id": decision["ruler_id"], "ruler_name": decision["ruler_name"],
            "polity": decision["polity"], "partition": "五代十国", "reign_range": decision["reign_range"],
            "independent_task_count": len(third_item_cycles),
            "independent_task_groups": [cycle["campaign_group_ref"] for cycle in third_item_cycles],
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
                "score_status": "UNASSESSED", "confidence": "INSUFFICIENT",
                "evidence_ceiling": min(3, len(third_item_cycles) + 2) if third_item_cycles else 0,
                "evidence_ceiling_adjustments": [], "cap_reasons": [decision["pending_reason"]],
                "collapse_profile": "UNKNOWN", "passive_C1_adjustment": None,
                "passive_C1_cap": None, "passive_loss_rationale": None, "passive_loss_refs": [],
            })
            records.append(base)
            continue
        c1, c2, c3 = (int(decision["C"][key]) for key in ("C1", "C2", "C3"))
        overall, rate, points, surplus = _c_score(c1, c2, c3)
        major_failures = _unique(
            phase["phase_id"] for cycle in third_item_cycles for phase in cycle["phases"]
            if phase["phase_return_class"] == "NEGATIVE_RETURN"
            and max((_grade_number(phase["cost_axes"].get(key), key) or 0) for key in ("P", "M", "A", "WC")) >= 4
        )
        grade = min(c1, c2, c3)
        lower, upper = ((0, 29), (30, 44), (45, 59), (60, 74), (75, 89), (90, 100))[grade]
        base.update({
            "combat_delivery_grade": f"C1-{c1}", "operational_sustainability_cap": f"C2-{c2}",
            "system_reliability_cap": f"C3-{c3}", "C_overall_grade": overall,
            "C_score_rate": rate, "C_score_points": points, "C_score_support_surplus": surplus,
            "C_score_band": {"lower_rate": lower, "upper_rate": upper},
            "adjudication_method": "SUBJECT_PHASE_CONTRACT_ADJUDICATION",
            "score_status": "DIRECT_C_SCORE_ASSIGNED", "confidence": "MEDIUM_HIGH",
            "evidence_ceiling": 3 if len(third_item_cycles) <= 1 else 4 if len(third_item_cycles) == 2 else 5,
            "evidence_ceiling_adjustments": [], "cap_reasons": [decision["C"]["reason"]],
            "major_system_failure_refs": major_failures,
            "collapse_profile": "NATIONWIDE_DOMINANT_UNRECOVERED" if c3 == 0 else "NO_NATIONWIDE_DOMINANT_COLLAPSE",
            "passive_C1_adjustment": None, "passive_C1_cap": None,
            "passive_loss_rationale": None, "passive_loss_refs": [],
        })
        records.append(base)
    return records


def _aggregate_d_cycle(cycle: Mapping[str, Any]) -> dict[str, Any]:
    phases = list(cycle["phases"])
    final_class = next((phase["phase_return_class"] for phase in reversed(phases) if phase["phase_return_class"] != "UNKNOWN"), "UNKNOWN")
    costs = {key: max((_grade_number(phase["cost_axes"].get(key), key) or 0) for phase in phases) for key in ("P", "S", "M", "A", "WC")}
    benefits = {
        key: max((_grade_number(value, key) or 0) for phase in phases for value in (
            [phase["strategic_security"]] if key in {"SB", "SN"} else
            [phase["border_control"][key]] if key in {"BCP", "BCN"} else
            [phase["material_return"]]
        ))
        for key in ("SB", "SN", "BCP", "BCN", "WR")
    }
    material = max(costs[key] for key in ("P", "S", "M", "A")) >= 3 or max(benefits[key] for key in ("SB", "SN", "BCP", "BCN")) >= 3
    major_benefit = max(benefits[key] for key in ("SB", "SN", "BCP", "BCN"))
    national_negative = final_class == "NEGATIVE_RETURN" and (max(costs["M"], costs["A"]) >= 4 or max(benefits["SN"], benefits["BCN"]) >= 4)
    return {
        "campaign_group_ref": cycle["campaign_group_ref"], "war_event_refs": cycle["war_event_refs"],
        "phase_ids": cycle["phase_ids"], "return_class": final_class,
        "cost_axes": costs, "benefit_axes": benefits, "material": material,
        "major_high_return": final_class == "HIGH_RETURN" and major_benefit >= 4,
        "top_high_return": final_class == "HIGH_RETURN" and major_benefit >= 5,
        "national_negative": national_negative,
        "route": "D_INTERNAL_COST_ONLY" if re.search(r"MUTINY|REBELLION", cycle["campaign_group_ref"]) else "D_STANDARD",
    }


def _d_grade_and_score(cycles: Sequence[Mapping[str, Any]]) -> tuple[str, float, dict[str, Any]]:
    counts = Counter(cycle["return_class"] for cycle in cycles)
    positive = counts["HIGH_RETURN"] + counts["PROPORTIONATE_RETURN"]
    negative = counts["LOW_RETURN"] + counts["NEGATIVE_RETURN"]
    material = [cycle for cycle in cycles if cycle["material"]]
    national = [cycle for cycle in cycles if cycle["national_negative"]]
    major = [cycle for cycle in cycles if cycle["major_high_return"]]
    top = [cycle for cycle in cycles if cycle["top_high_return"]]
    if not material:
        return "D-U", 20.0, {"status": "NO_MATERIAL_CYCLE"}
    if (len(national) >= 3 and negative + len(national) >= positive) or (len(national) >= 2 and negative >= positive) or (len(national) >= 1 and positive == 0):
        grade = "D-1"
    elif national or (negative >= 2 and negative >= positive):
        grade = "D-2"
    elif len(top) >= 1 and len(major) >= 2 and counts["HIGH_RETURN"] >= 3 and not national and negative <= 1 and counts["LOW_RETURN"] <= 3:
        grade = "D-5"
    elif positive >= negative + 2 and positive / max(1, positive + negative) >= 2 / 3 and len(material) >= 2 and (counts["HIGH_RETURN"] >= 1 or (len(material) >= 4 and negative == 0)):
        grade = "D-4"
        if counts["NEGATIVE_RETURN"] == 1 and (positive < negative + 3 or len(major) < 2):
            grade = "D-3"
    else:
        grade = "D-3"
    h, r, low, neg = (counts[name] for name in ("HIGH_RETURN", "PROPORTIONATE_RETURN", "LOW_RETURN", "NEGATIVE_RETURN"))
    total = len(cycles)
    quality = max(0.0, min(1.0, 0.5 + (2 * h + r - low - 2 * neg) / (4 * total))) if total else 0.25
    if grade == "D-4":
        breadth = min(1.0, (len(material) + 2 * len(major)) / 8)
        dominance = positive / max(1, positive + negative)
        quality = (0.5 * quality + 0.3 * breadth + 0.2 * dominance) * min(1.0, 0.70 + 0.05 * len(material))
        if not major:
            quality = min(quality, 0.8)
    if len(material) == 1 and grade == "D-3":
        quality = min(quality, {"HIGH_RETURN": 0.65, "PROPORTIONATE_RETURN": 0.5, "LOW_RETURN": 0.3, "NEGATIVE_RETURN": 0.1, "UNKNOWN": 0.25}[material[0]["return_class"]])
    lower, upper = D_BANDS[grade]
    score = round(lower + (upper - lower) * quality, 1)
    return grade, score, {
        "return_class_counts": dict(sorted(counts.items())), "usable_cycle_count": total,
        "material_cycle_count": len(material), "national_negative_return_refs": [cycle["campaign_group_ref"] for cycle in national],
        "major_high_return_refs": [cycle["campaign_group_ref"] for cycle in major],
        "top_tier_high_return_refs": [cycle["campaign_group_ref"] for cycle in top],
        "evidence_status": "UNDER_TESTED" if len(material) <= 1 else "LIMITED_EXPOSURE" if len(material) <= 3 else "SUFFICIENT_EXPOSURE",
    }


def build_five_dynasties_d_records(
    registry: Mapping[str, Any], adjudications: Sequence[Mapping[str, Any]],
    ab_records: Sequence[Mapping[str, Any]], c_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    ab_by_id = {row["ruler_id"]: row for row in ab_records}
    c_by_id = {row["ruler_id"]: row for row in c_records}
    records = []
    for decision in adjudications:
        cycles, event_refs, _ = _cycles_and_refs(registry, str(decision["ruler_id"]))
        excluded = [cycle for cycle in cycles if any(phase["founding_startup_ledger"]["is_founding_process"] for phase in cycle["phases"])]
        included = [_aggregate_d_cycle(cycle) for cycle in cycles if cycle not in excluded]
        ready = bool(decision.get("score_ready", decision.get("coverage_complete", False)))
        base = {
            "ruler_id": decision["ruler_id"], "ruler_name": decision["ruler_name"],
            "polity": decision["polity"], "reign_range": decision["reign_range"],
            "schema_id": "emperor-v4-d-ruler-formal-settlement-v1", "canonical_status": "FORMAL_CURRENT" if ready else "PENDING",
            "formal_repository_entry": True, "formal_score_write": False, "database_write": False,
            "source_event_refs": event_refs,
            "d_cycle_refs": [cycle["campaign_group_ref"] for cycle in cycles],
            "included_d_cycle_refs": [cycle["campaign_group_ref"] for cycle in included],
            "excluded_unification_cycle_refs": [cycle["campaign_group_ref"] for cycle in excluded],
            "strategic_binding_refs": [ref for cycle in included for ref in cycle["phase_ids"]],
            "internal_cost_binding_refs": [cycle["campaign_group_ref"] for cycle in included if cycle["route"] == "D_INTERNAL_COST_ONLY"],
            "route_counts": dict(sorted(Counter(cycle["route"] for cycle in included).items())),
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
        grade, score, metrics = _d_grade_and_score(included)
        ab_points = ab_by_id[decision["ruler_id"]]["AB_score_points"]
        c_points = c_by_id[decision["ruler_id"]]["C_score_points"]
        if grade in {"D-4", "D-5"} and 2 <= metrics["material_cycle_count"] <= 3 and (ab_points < 80 or c_points < 30):
            grade = "D-3"
            lower, upper = D_BANDS[grade]
            score = round((lower + upper) / 2, 1)
            metrics["abc_small_sample_gate"] = "CAPPED_TO_D3"
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
            "D_grade": grade, "D_grade_reasons": ["按主体阶段去重后的独立战略周期执行现行D机器定档顺序。"],
            "D_score_points": score, "D_score_band": {"lower_points": lower, "upper_points": upper},
            "portfolio_status": "FORMAL_CURRENT", "D_portfolio_metrics": metrics,
            "unresolved_cycle_refs": [cycle["campaign_group_ref"] for cycle in included if cycle["return_class"] == "UNKNOWN"],
            "unresolved_source_refs": [],
            "positive_benefit_cycle_refs": [cycle["campaign_group_ref"] for cycle in positive],
            "negative_benefit_cycle_refs": [cycle["campaign_group_ref"] for cycle in negative],
            "high_cost_cycle_refs": [cycle["campaign_group_ref"] for cycle in high_cost],
            "zero_return_high_cost_cycle_refs": [cycle["campaign_group_ref"] for cycle in high_cost if cycle["return_class"] in {"LOW_RETURN", "NEGATIVE_RETURN"}],
            "peak_d_cost_axes": {key: f"{key}{max((cycle['cost_axes'][key] for cycle in included), default=0)}" for key in ("P", "M", "A")},
            "readiness_counts": {"HOLD": len(included)}, "binding_source": "SUBJECT_PHASE_FORMAL_CURRENT",
            "ruler_event_class_overrides": [],
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


def build_five_dynasties_formal_payloads(
    workspace_root: Path, registry: Mapping[str, Any]
) -> dict[str, Any]:
    adjudications = _load_adjudications(workspace_root)
    ab_records = build_five_dynasties_ab_records(registry, adjudications)
    c_records = build_five_dynasties_c_records(registry, adjudications)
    d_records = build_five_dynasties_d_records(registry, adjudications, ab_records, c_records)
    combined_records = _build_combined_records(adjudications, ab_records, c_records, d_records)

    ab = _replace_partition_records(json.loads((workspace_root / AB_PATH).read_text(encoding="utf-8")), ab_records)
    existing_combined = json.loads((workspace_root / FORMAL_PATH).read_text(encoding="utf-8"))
    north_song_count = sum(str(row.get("ruler_id", "")).startswith("RULER-NS-") for row in existing_combined["records"])
    extension = f" + 北宋{north_song_count}人" if north_song_count else ""
    ab.update({
        "scope": f"秦至唐95人冻结值 + 五代十国12人当前结算{extension}",
        "ruler_count": len(ab["records"]), "reviewed_count": sum(row.get("adjudication_status") == "REVIEWED" for row in ab["records"]),
        "pending_count": sum(not row.get("score_ready") for row in ab["records"]),
        "score_ready_count": sum(bool(row.get("score_ready")) for row in ab["records"]),
        "five_dynasties_source_fingerprint": SOURCE_SET_FINGERPRINT,
    })
    c = _replace_partition_records(json.loads((workspace_root / C_PATH).read_text(encoding="utf-8")), c_records)
    c.update({
        "scope": f"秦至唐95人冻结值 + 五代十国12人当前结算{extension}",
        "record_count": len(c["records"]), "score_ready_count": sum(bool(row.get("score_ready")) for row in c["records"]),
        "partition_counts": dict(sorted(Counter(str(row.get("partition")) for row in c["records"]).items())),
        "grade_distribution": dict(sorted(Counter(str(row.get("C_overall_grade")) for row in c["records"]).items())),
        "five_dynasties_source_fingerprint": SOURCE_SET_FINGERPRINT,
    })
    d = _replace_partition_records(json.loads((workspace_root / D_PATH).read_text(encoding="utf-8")), d_records)
    d.update({
        "scope": f"秦至唐95人冻结值 + 五代十国12人当前结算{extension}",
        "record_count": len(d["records"]),
        "grade_distribution": dict(sorted(Counter(str(row.get("D_grade")) for row in d["records"]).items())),
        "five_dynasties_source_fingerprint": SOURCE_SET_FINGERPRINT,
    })
    combined = _replace_partition_records(existing_combined, combined_records)
    _assign_global_third_item_ranks(combined["records"])
    combined.pop("qin_tang_rank_freeze", None)
    combined.update({
        "scope": f"秦至唐95人冻结分值 + 五代十国12人{extension}；第三项{len(combined['records'])}人统一排名",
        "record_count": len(combined["records"]),
        "score_ready_count": sum(row.get("third_item_score_points") is not None for row in combined["records"]),
        "D_unassessed_neutral_count": sum(row.get("D_score_points") is None for row in combined["records"]),
        "five_dynasties_source_fingerprint": SOURCE_SET_FINGERPRINT,
        "five_dynasties_ready_count": sum(row.get("third_item_score_points") is not None for row in combined_records),
        "five_dynasties_pending_count": sum(row.get("third_item_score_points") is None for row in combined_records),
        "qin_tang_value_freeze": True,
        "global_ranking_enabled": True,
        "rank_tie_policy": "COMPETITION_RANK",
        "shared_source_root": "docs/史料通读产物",
    })
    return {"AB": ab, "C": c, "D": d, "combined": combined, "partition_records": combined_records}


def _replace_marked_section(text: str, section: str) -> str:
    start = "<!-- FIVE_DYNASTIES_FORMAL_START -->"
    end = "<!-- FIVE_DYNASTIES_FORMAL_END -->"
    block = f"{start}\n{section.rstrip()}\n{end}\n"
    if start in text and end in text:
        return text[: text.index(start)] + block + text[text.index(end) + len(end):].lstrip("\n")
    return text.rstrip() + "\n\n" + block


def _formal_markdown_section(kind: str, records: Sequence[Mapping[str, Any]]) -> str:
    lines = ["## 五代十国当前正式结算", "", "本节由卷263至294主体阶段裁决卡及卷004、卷008两条定向终局补充确定性生成；秦至唐既有正文、分值与排名不重算。", ""]
    if kind == "combined":
        lines += ["| 分区名次 | 皇帝 | 政权 | 在位 | AB/160 | C/50 | D/40 | 第三项/250 | 状态 |", "|---:|---|---|---|---:|---:|---:|---:|---|"]
        for row in sorted(records, key=lambda item: (item["partition_rank"] is None, item["partition_rank"] or 999, item["ruler_name"])):
            value = lambda key: "待定" if row.get(key) is None else f"{row[key]:.1f}"
            lines.append(f"| {row.get('partition_rank') or '—'} | {row['ruler_name']} | {row['polity']} | {row['reign_range']} | {value('AB_score_points')} | {value('C_score_points')} | {value('D_score_points')} | {value('third_item_score_points')} | {'正式' if row['third_item_score_points'] is not None else row['pending_reason']} |")
    else:
        score_key = {"AB": "AB_score_points", "C": "C_score_points", "D": "D_score_points"}[kind]
        max_points = {"AB": 160, "C": 50, "D": 40}[kind]
        lines += [f"| 皇帝 | 政权 | 在位 | {kind}/{max_points} | 状态 |", "|---|---|---|---:|---|"]
        for row in records:
            value = "待定" if row.get(score_key) is None else f"{row[score_key]:.1f}"
            status = "正式" if row.get(score_key) is not None else (row.get("rationale") or row.get("unresolved_gaps", [""])[0] or row.get("unresolved_source_refs", [""])[0])
            lines.append(f"| {row['ruler_name']} | {row['polity']} | {row['reign_range']} | {value} | {status} |")
    return "\n".join(lines) + "\n"


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
        f"共{len(eligible)}位评价主体，得分范围{min(values):.1f}—{max(values):.1f}。同分并列，后一名次按竞赛排名顺延。秦至唐95人的既有分值与证据记录未重算；{extension_note}D-U固定20分仅是未检验中性值，不得解释为D项能力中等。",
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
            f"| {row['rank']} | {row['ruler_name']} | {row['polity']} | {row['reign_range']} | "
            f"{float(row['A_score_points']):.1f} | {float(row['B_score_points']):.1f} | "
            f"{float(row['C_score_points']):.1f} | {d_value} | {float(row['third_item_score_points']):.1f} |"
        )
    return "\n".join(lines) + "\n"


def write_five_dynasties_third_item(workspace_root: Path) -> dict[str, Any]:
    promotion_audit = write_promoted_battle_registry(workspace_root)
    registry = json.loads((workspace_root / REGISTRY_PATH).read_text(encoding="utf-8"))
    payloads = build_five_dynasties_formal_payloads(workspace_root, registry)
    paths = {"AB": AB_PATH, "C": C_PATH, "D": D_PATH, "combined": FORMAL_PATH}
    md_paths = {
        "AB": AB_PATH.with_suffix(".md"), "C": C_PATH.with_suffix(".md"),
        "D": D_PATH.with_suffix(".md"), "combined": FORMAL_PATH.with_suffix(".md"),
    }
    partition_by_kind = {
        "AB": [row for row in payloads["AB"]["records"] if row.get("partition") == "五代十国"],
        "C": [row for row in payloads["C"]["records"] if row.get("partition") == "五代十国"],
        "D": [row for row in payloads["D"]["records"] if row.get("ruler_id", "").startswith("RULER-FD-")],
        "combined": payloads["partition_records"],
    }
    for kind, path in paths.items():
        target = workspace_root / path
        target.write_text(json.dumps(payloads[kind], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        md_target = workspace_root / md_paths[kind]
        if kind == "combined":
            md_target.write_text(_render_combined_markdown(payloads[kind]["records"]), encoding="utf-8")
        else:
            md_target.write_text(
                _replace_marked_section(md_target.read_text(encoding="utf-8"), _formal_markdown_section(kind, partition_by_kind[kind])),
                encoding="utf-8",
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
