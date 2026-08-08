from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

from emperor_v4.evaluation.five_dynasties_third_item import (
    AB_PATH,
    C_PATH,
    D_BANDS,
    D_PATH,
    FORMAL_PATH,
    REGISTRY_MARKDOWN_PATH,
    REGISTRY_PATH,
    REGISTRY_SCHEMA,
    CONTROL_CONTRIBUTION_CAPS,
    _axis_a,
    _axis_b,
    _apply_c_major_victory_gate,
    _c_score,
    _d_grade_and_score,
    _d_grade_reasons,
    _expected_b1_grade,
    _grade_number,
    _normalize_qin_tang_bc_parent_cycles,
    _normalize_formal_d_records,
    _recalculate_qin_tang_d_records,
    _third_item_cycles,
    _validate_bc_parent_cycle_alignment,
    _validate_formal_abc_contracts,
    _write_text_atomic,
    _sync_formal_d_into_combined,
    _sync_formal_c_into_combined,
    _render_combined_markdown,
    _render_formal_markdown,
    _replace_partition_records,
)


SOURCE_ROOT = Path("docs/史料通读产物/北宋/续资治通鉴")
ADJUDICATION_PATH = Path("config/north-song-third-item-adjudications.json")
INPUT_SCHEMA = "chronicle-battle-adjudication-v2"
SOURCE_SET_FINGERPRINT = "62ac210a794cb4cfa6c9b3bcef2c58d72f9caa8316b9313e051e2507481ac7ac"
SOURCE_IDENTITY_FINGERPRINT = "97b96dca527e274cc1b2f40228eefabc6c43e5c6693d17cc51562b6b57ce4119"
RETIRED_STALE_NORTH_SONG_RECORD_COUNT = 801

RULER_WINDOWS: tuple[dict[str, Any], ...] = (
    {"ruler_id": "RULER-NS-ZHAO-KUANGYIN", "ruler_name": "赵匡胤", "start": 960, "end": 976},
    {"ruler_id": "RULER-NS-ZHAO-GUANGYI", "ruler_name": "赵光义", "start": 977, "end": 997},
    {"ruler_id": "RULER-NS-ZHAO-HENG", "ruler_name": "赵恒", "start": 998, "end": 1021},
    {"ruler_id": "RULER-NS-LIU-E", "ruler_name": "刘娥", "start": 1022, "end": 1032},
    {"ruler_id": "RULER-NS-ZHAO-ZHEN", "ruler_name": "赵祯", "start": 1033, "end": 1063},
    {"ruler_id": "RULER-NS-ZHAO-SHU", "ruler_name": "赵曙", "start": 1064, "end": 1066},
    {"ruler_id": "RULER-NS-ZHAO-XU", "ruler_name": "赵顼", "start": 1067, "end": 1085},
    {"ruler_id": "RULER-NS-GAO-TAOTAO", "ruler_name": "高滔滔", "start": 1086, "end": 1093},
    {"ruler_id": "RULER-NS-ZHAO-XU-ZHEZONG", "ruler_name": "赵煦", "start": 1094, "end": 1100},
    {"ruler_id": "RULER-NS-ZHAO-JI", "ruler_name": "赵佶", "start": 1101, "end": 1125},
    {"ruler_id": "RULER-NS-ZHAO-HUAN", "ruler_name": "赵桓", "start": 1126, "end": 1127},
)

# No-year groups are carry-in/retrospective cards. The volume window is only a
# last-resort attribution aid and never overrides an explicit campaign year.
VOLUME_FALLBACK: dict[int, str] = {
    **{n: "RULER-NS-ZHAO-KUANGYIN" for n in range(1, 9)},
    **{n: "RULER-NS-ZHAO-GUANGYI" for n in range(9, 20)},
    **{n: "RULER-NS-ZHAO-HENG" for n in range(20, 36)},
    **{n: "RULER-NS-LIU-E" for n in range(36, 39)},
    **{n: "RULER-NS-ZHAO-ZHEN" for n in range(39, 62)},
    **{n: "RULER-NS-ZHAO-SHU" for n in range(62, 65)},
    **{n: "RULER-NS-ZHAO-XU" for n in range(65, 79)},
    **{n: "RULER-NS-GAO-TAOTAO" for n in range(79, 84)},
    **{n: "RULER-NS-ZHAO-XU-ZHEZONG" for n in range(84, 88)},
    **{n: "RULER-NS-ZHAO-JI" for n in range(88, 96)},
    **{n: "RULER-NS-ZHAO-HUAN" for n in range(96, 98)},
}
YEAR_RE = re.compile(r"(?<!\d)(0?9\d{2}|10\d{2}|11\d{2})(?!\d)")
POST_COLLAPSE_UNATTRIBUTED_GROUPS = {
    "XZTJ-SONG-RESTORATION-YUANSHUAI-1126-1127",
    "XZTJ-JIN-SONG-TWO-RIVERS-LOCAL-RESISTANCE-1127",
    "XZTJ-JIN-SONG-SECOND-INVASION-WEST-HEDONG-1126",
    "XZTJ-SONG-RESTORATION-ZONGZE-1127",
    "XZTJ-SONG-ZHONGSHAN-MUTINY-1127",
    "XZTJ-CHU-WUGE-UPRISING-1127",
    "XZTJ-JIN-SONG-SHANZHOU-1127",
    "XZTJ-SONG-RESTORATION-YINGTIAN-1127",
}


def _digest(value: object) -> str:
    return sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _is_north_song_subject(subject: str) -> bool:
    if subject.startswith("宋江"):
        return False
    return subject.startswith("宋") or subject.startswith("北宋") or any(
        marker in subject
        for marker in ("赵匡胤", "赵光义", "赵恒", "赵祯", "赵曙", "赵顼", "赵煦", "赵佶", "赵桓")
    )


def _year_range(campaign_group: str) -> tuple[int, int] | None:
    years = [int(value) for value in YEAR_RE.findall(campaign_group)]
    return (min(years), max(years)) if years else None


def _bind_phase(
    subject: str,
    campaign_group: str,
    volume: int,
    source_anchor_refs: Sequence[str] = (),
) -> dict[str, Any]:
    if not _is_north_song_subject(subject):
        return {
            "ruler_id": None,
            "ruler_name": None,
            "status": "OUTSIDE_NORTH_SONG_EVALUATION_SUBJECT",
            "basis": "主体阶段属于辽、西夏、叛军或其他非北宋国家评价主体；禁止把对手指标复制给北宋人物。",
        }
    if campaign_group in POST_COLLAPSE_UNATTRIBUTED_GROUPS:
        return {
            "ruler_id": None,
            "ruler_name": None,
            "status": "OUTSIDE_RULER_CONTROL_AFTER_COLLAPSE",
            "basis": "北宋中枢覆亡后由地方守军、康王元帅府或复国军政核心承担；不得倒灌给已失去实际控制的赵桓。",
        }
    if volume == 95:
        anchor_paragraphs = [
            int(match.group(1))
            for ref in source_anchor_refs
            if (match := re.search(r"-P(\d{4})$", str(ref)))
        ]
        if anchor_paragraphs and min(anchor_paragraphs) >= 230:
            ruler = next(row for row in RULER_WINDOWS if row["ruler_id"] == "RULER-NS-ZHAO-HUAN")
            return {
                "ruler_id": ruler["ruler_id"], "ruler_name": ruler["ruler_name"],
                "status": "BOUND_REVIEWED_ABDICATION_ANCHOR",
                "basis": "卷095 P0230起已在徽宗内禅后，按固定修订段落锚绑定钦宗，不按公历年整年倒灌徽宗。",
            }
    years = _year_range(campaign_group)
    if years is None:
        ruler_id = VOLUME_FALLBACK.get(volume)
        ruler = next((row for row in RULER_WINDOWS if row["ruler_id"] == ruler_id), None)
        if ruler is None:
            return {
                "ruler_id": None, "ruler_name": None,
                "status": "OUTSIDE_COMPLETE_RULER_WINDOWS",
                "basis": "无年份卡不在当前已完整覆盖的互斥主政窗口，暂不结算。",
            }
        return {
            "ruler_id": ruler["ruler_id"], "ruler_name": ruler["ruler_name"],
            "status": "BOUND_REVIEWED_VOLUME_FALLBACK",
            "basis": "campaign_group无年份；按续资治通鉴卷次所在互斥主政窗口复核绑定。",
        }
    if years == (1125, 1126) and volume in {95, 96, 97}:
        ruler_id = "RULER-NS-ZHAO-JI" if volume == 95 else "RULER-NS-ZHAO-HUAN"
        ruler = next(row for row in RULER_WINDOWS if row["ruler_id"] == ruler_id)
        return {
            "ruler_id": ruler["ruler_id"], "ruler_name": ruler["ruler_name"],
            "status": "BOUND_REVIEWED_TRANSITION_SLICE",
            "basis": "跨1125—1126父战役已按卷095退位前阶段与卷096—097即位后阶段切片，禁止跨皇帝倒灌。",
        }
    if campaign_group == "XZTJ-JIN-SONG-KAIFENG-SECOND-SIEGE-1126-1127":
        ruler = next(row for row in RULER_WINDOWS if row["ruler_id"] == "RULER-NS-ZHAO-HUAN")
        return {
            "ruler_id": ruler["ruler_id"], "ruler_name": ruler["ruler_name"],
            "status": "BOUND_REVIEWED_TERMINAL_COLLAPSE",
            "basis": "东京第二次围城至废帝是赵桓任内北宋终端覆亡阶段；只绑定守城与中枢覆亡，P0234后康王复国行动另组排除。",
        }
    candidates = [
        ruler for ruler in RULER_WINDOWS
        if ruler["start"] <= years[0] and years[1] <= ruler["end"]
    ]
    if len(candidates) == 1:
        ruler = candidates[0]
        return {
            "ruler_id": ruler["ruler_id"], "ruler_name": ruler["ruler_name"],
            "status": "BOUND_EXCLUSIVE_GOVERNING_WINDOW",
            "basis": "北宋主体阶段年代完整落入皇帝或摄政者的互斥实际主政窗口。",
        }
    overlap = [
        ruler for ruler in RULER_WINDOWS
        if max(ruler["start"], years[0]) <= min(ruler["end"], years[1])
    ]
    return {
        "ruler_id": None, "ruler_name": None,
        "status": "UNRESOLVED_WINDOW_OVERLAP" if overlap else "OUTSIDE_COMPLETE_RULER_WINDOWS",
        "basis": "卡片跨越互斥主政窗口，禁止倒灌。" if overlap else "阶段属于当前结算范围外年代。",
        "candidate_ruler_ids": [row["ruler_id"] for row in overlap],
    }


def _read_pair(path: Path, workspace_root: Path) -> tuple[dict[str, Any], Path]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != INPUT_SCHEMA:
        raise ValueError(f"北宋战役裁决卡schema错误: {path}")
    volume = int(re.search(r"volume-(\d+)\.", path.name).group(1))
    if payload.get("source_volume") != f"续资治通鉴/卷{volume:03d}":
        raise ValueError(f"北宋卷号身份错误: {path}")
    summary = path.with_name(f"volume-{volume:03d}.source-summary.md")
    summary_text = summary.read_text(encoding="utf-8")
    identity = payload.get("source_identity") or {}
    if not all(str(identity.get(key) or "") in summary_text for key in ("source_unit_id", "revision_ref", "raw_sha256")):
        raise ValueError(f"北宋战役卡与配对总结source identity不匹配: {path}")
    return payload, summary.relative_to(workspace_root)


def _load_adjudication_payload(workspace_root: Path) -> dict[str, Any]:
    payload = json.loads((workspace_root / ADJUDICATION_PATH).read_text(encoding="utf-8"))
    if payload.get("schema_version") != "north-song-third-item-adjudications-v1":
        raise ValueError("北宋第三项裁决配置schema错误")
    if payload.get("source_set_fingerprint") != SOURCE_SET_FINGERPRINT:
        raise ValueError("北宋第三项裁决未绑定当前194份输入内容指纹")
    return payload


def build_north_song_battle_records(workspace_root: Path) -> dict[str, Any]:
    source_root = workspace_root / SOURCE_ROOT
    paths = sorted(source_root.glob("volume-*.battle-adjudications.json"))
    if [int(path.name[7:10]) for path in paths] != list(range(1, 98)):
        raise ValueError("北宋战役裁决输入必须完整覆盖卷001至097")
    content_fingerprint = sha256(
        b"".join(path.read_bytes() for path in sorted(source_root.iterdir(), key=lambda item: item.name))
    ).hexdigest()
    if content_fingerprint != SOURCE_SET_FINGERPRINT:
        raise ValueError(f"北宋194份输入内容指纹漂移: {content_fingerprint}")
    records: list[dict[str, Any]] = []
    phase_ids: set[str] = set()
    identities: list[dict[str, Any]] = []
    for path in paths:
        payload, summary_relative = _read_pair(path, workspace_root)
        volume = int(path.name[7:10])
        identities.append(dict(payload["source_identity"]))
        source_relative = path.relative_to(workspace_root).as_posix()
        for card_index, card in enumerate(payload.get("cards") or (), start=1):
            group = str(card.get("campaign_group") or "")
            anchors = [str(value) for value in card.get("source_anchor_refs") or ()]
            if not group or not anchors:
                raise ValueError(f"北宋战役卡缺少group或anchor: {path}#{card_index}")
            token = f"{volume}:{card_index}:{group}:{'|'.join(anchors)}"
            event_id = "WAR-NS-" + sha256(token.encode("utf-8")).hexdigest()[:20].upper()
            phases = []
            for phase_index, raw in enumerate(card.get("subject_phase_cards") or (), start=1):
                for key in (
                    "evaluation_subject_phase", "subject_role", "actual_process", "cost_axes",
                    "strategic_security", "material_return", "border_control", "phase_return_class",
                    "founding_startup_ledger",
                ):
                    if key not in raw:
                        raise ValueError(f"北宋主体阶段缺少{key}: {path}#{card_index}/{phase_index}")
                phase_id = f"{event_id}-P{phase_index:02d}"
                if phase_id in phase_ids:
                    raise ValueError(f"北宋主体阶段ID重复: {phase_id}")
                phase_ids.add(phase_id)
                subject = str(raw["evaluation_subject_phase"])
                binding = _bind_phase(subject, group, volume, anchors)
                phases.append({
                    "phase_id": phase_id,
                    "evaluation_subject_phase": subject,
                    "subject_role": raw["subject_role"],
                    "actual_process": raw["actual_process"],
                    "cost_axes": dict(raw["cost_axes"]),
                    "P_inference": raw.get("P_inference"),
                    "cost_evidence": dict(raw.get("cost_evidence") or {}),
                    "strategic_security": raw["strategic_security"],
                    "material_return": raw["material_return"],
                    "border_control": dict(raw["border_control"]),
                    "phase_return_class": raw["phase_return_class"],
                    "founding_startup_ledger": dict(raw["founding_startup_ledger"]),
                    "carry_in": raw.get("carry_in"), "carry_out": raw.get("carry_out"),
                    "polity_binding": "北宋" if binding.get("ruler_id") else None,
                    "ruler_binding": binding,
                    "source_anchor_refs": list(raw.get("axis_source_refs", {}).get("cost_axes") or anchors),
                    "axis_source_refs": dict(raw.get("axis_source_refs") or {}),
                })
            period = _year_range(group)
            records.append({
                "war_event_id": event_id, "dynasty": "北宋", "dynasty_partition": "north_song",
                "record_level": "chronicle_battle_card", "campaign_group_ref": group,
                "canonical_label": card["battle_label"],
                "period": {"start": str(period[0]) if period else "unknown", "end": str(period[1]) if period else "unknown"},
                "public_outcome_registered": True, "disposition": "REGISTERED_SUBJECT_PHASE_CONTRACT",
                "source_lineage": {
                    "source_card_ids": [f"{payload['source_identity']['source_unit_id']}#CARD-{card_index:03d}"],
                    "source_files": [source_relative, summary_relative.as_posix()],
                    "source_revision_refs": [str(payload["source_identity"]["revision_ref"])],
                    "lineage_basis": "北宋卷001至097配对通读总结与战役裁决卡；父卡只作容器，第三项仅消费主体阶段。",
                },
                "source_refs": anchors, "source_quotes": list(card.get("source_quotes") or ()),
                "subject_phase_views": phases, "subject_phase_count": len(phases),
                "non_battle_disposition": card.get("non_battle_disposition"),
                "wc_grade": None, "security_grade": None, "contract_adjudication": True,
                "post_tang_evidence_lower_bound": False,
                "limitations": ["父卡指标不得复制给主体；皇帝与摄政者按互斥实际主政窗口归责。"],
            })
    if len(records) != 716 or len(phase_ids) != 1586:
        raise ValueError(f"北宋输入覆盖异常: cards={len(records)}, phases={len(phase_ids)}")
    identity_fingerprint = _digest(identities)
    if identity_fingerprint != SOURCE_IDENTITY_FINGERPRINT:
        raise ValueError(f"北宋source identity指纹漂移: {identity_fingerprint}")
    return {
        "schema_version": "north-song-battle-promotion-v1",
        "source_set_fingerprint": content_fingerprint,
        "source_identity_fingerprint": identity_fingerprint,
        "source_file_count": 194, "volume_count": 97,
        "battle_card_count": len(records),
        "campaign_group_count": len({row["campaign_group_ref"] for row in records}),
        "subject_phase_count": len(phase_ids), "records": records,
    }


def _replace_unification_refs(payload: dict[str, Any], records: Sequence[Mapping[str, Any]]) -> None:
    groups_by_opponent = {
        "OPP-SONG-JINGHU": {"XUZJ-003-SONG-JINGHU-CONQUEST-0963"},
        "OPP-SONG-LATER-SHU": {"XUZJ-004-SONG-LATER-SHU-CONQUEST-0964-0965"},
        "OPP-SONG-SOUTHERN-HAN": {"XZTJ-006-SONG-SOUTHERN-HAN-CONQUEST-0970-0971"},
        "OPP-SONG-SOUTHERN-TANG": {
            "XZTJ-008-SONG-JIANGNAN-CONQUEST-0974-0975",
            "XZTJ-008-SONG-JIANGNAN-MIDYANGTZE-0974-0975",
            "XZTJ-008-SONG-JIANGNAN-FLANKS-0975",
            "XZTJ-008-WUYUE-JIANGNAN-EASTFRONT-0974-0975",
            "XZTJ-008-SONG-JIANGNAN-ZHUQUANYUN-WANKOU-0975",
            "XZTJ-008-SONG-JIANGNAN-JINLING-NIGHTATTACK-0975",
        },
        "OPP-SONG-NORTHERN-HAN": {"XZTJ-009-010-SONG-NORTHHAN-CONQUEST-0979"},
    }
    record_refs_by_group: dict[str, list[str]] = {}
    for row in records:
        record_refs_by_group.setdefault(str(row["campaign_group_ref"]), []).append(str(row["war_event_id"]))
    refs_by_opponent = {
        opponent: _unique(
            ref for group in sorted(groups) for ref in record_refs_by_group.get(group, ())
        )
        for opponent, groups in groups_by_opponent.items()
    }
    if any(not refs for refs in refs_by_opponent.values()):
        raise ValueError("北宋统一总链存在未解析的canonical campaign group")
    canonical_refs = _unique(
        ref for opponent in groups_by_opponent for ref in refs_by_opponent[opponent]
    )
    goryeo_refs = [
        str(row["war_event_id"]) for row in payload.get("records") or ()
        if row.get("campaign_group_ref") == "ZZTJ-280-GORYEO-UNIFICATION-0936"
    ]
    if len(goryeo_refs) != 1:
        raise ValueError("五代十国高丽统一canonical父卡缺失或重复")
    for portfolio in payload.get("unification_campaign_portfolios") or ():
        portfolio.pop("canonical_promotion_note", None)
        if portfolio.get("portfolio_ref") == "UCP-POST-GORYEO-936":
            portfolio["campaign_group_refs"] = goryeo_refs
            portfolio["public_campaign_group_count"] = 1
            portfolio["context_or_below_threshold_count"] = 0
        if portfolio.get("portfolio_ref") == "UCP-POST-SONG-963-979":
            portfolio["campaign_group_refs"] = canonical_refs
            portfolio["public_campaign_group_count"] = len(canonical_refs)
            portfolio["context_or_below_threshold_count"] = 0
            for opponent in portfolio.get("opponent_systems") or ():
                opponent_id = str(opponent.get("system_id") or "")
                if opponent_id in refs_by_opponent:
                    opponent["source_campaign_refs"] = refs_by_opponent[opponent_id]


def promote_north_song_battle_registry(payload: Mapping[str, Any], workspace_root: Path) -> dict[str, Any]:
    promotion = build_north_song_battle_records(workspace_root)
    existing = list(payload.get("records") or ())
    preserved = [
        dict(row) for row in existing
        if row.get("dynasty_partition") != "north_song" and row.get("dynasty") != "北宋"
    ]
    prior_count = len(existing) - len(preserved)
    if prior_count not in {
        RETIRED_STALE_NORTH_SONG_RECORD_COUNT,
        657,  # previous canonical卷001—094 partition, replaced atomically by卷001—097
        promotion["battle_card_count"],
    }:
        raise ValueError(f"北宋公共登记替换范围异常: {prior_count}")
    current = dict(payload)
    current["records"] = preserved + list(promotion["records"])
    _replace_unification_refs(current, promotion["records"])
    summaries = dict(current.get("post_tang_partition_summaries") or {})
    summaries["north_song"] = {
        "task_code": "north-song-canonical-battle-card-promotion-v1", "dynasty": "北宋",
        "candidate_count": promotion["battle_card_count"],
        "public_outcome_count": promotion["battle_card_count"],
        "destination_counts": {"REGISTERED_SUBJECT_PHASE_CONTRACT": promotion["battle_card_count"]},
        "person_command_result_count": 0,
        "fingerprint": _digest([row["war_event_id"] for row in promotion["records"]]),
    }
    five_records = [row for row in current["records"] if row.get("dynasty_partition") == "five_dynasties"]
    if five_records:
        summaries["five_dynasties"] = {
            "task_code": "five-dynasties-canonical-battle-card-promotion-v1", "dynasty": "五代十国",
            "candidate_count": len(five_records),
            "public_outcome_count": sum(bool(row.get("public_outcome_registered")) for row in five_records),
            "destination_counts": dict(sorted(Counter(str(row.get("disposition")) for row in five_records).items())),
            "person_command_result_count": 0,
            "fingerprint": _digest([row["war_event_id"] for row in five_records]),
        }
    current.update({
        "schema_version": REGISTRY_SCHEMA,
        "scope": "秦至清（五代十国、北宋使用主体阶段裁决卡；其余分区维持当前值）",
        "post_tang_partition_summaries": summaries,
        "north_song_promotion": {key: value for key, value in promotion.items() if key != "records"} | {
            "promoted_record_count": promotion["battle_card_count"],
            "retired_stale_record_count": RETIRED_STALE_NORTH_SONG_RECORD_COUNT,
            "complete_ruler_count": len(RULER_WINDOWS),
        },
        "public_outcome_count": sum(bool(row.get("public_outcome_registered")) for row in current["records"]),
        "pending_count": sum(bool(row.get("public_outcome_registered")) and row.get("command_status") == "PERSON_DETAIL_PENDING" for row in current["records"]),
        "disposition_counts": dict(sorted(Counter(str(row.get("disposition")) for row in current["records"]).items())),
        "tier_counts": dict(sorted(Counter(str(row["campaign_tier"]) for row in current["records"] if row.get("campaign_tier")).items())),
    })
    current["post_tang_candidate_count"] = sum(int(row.get("candidate_count") or 0) for row in summaries.values())
    post_tang_records = [
        row for row in current["records"]
        if row.get("post_tang_evidence_lower_bound")
        or row.get("dynasty_partition") in {"five_dynasties", "north_song"}
    ]
    source_fact_ids = [
        str(source_id) for row in post_tang_records
        for source_id in (row.get("source_lineage") or {}).get("source_card_ids") or ()
    ]
    if len(source_fact_ids) != len(set(source_fact_ids)):
        raise ValueError("唐以后当前公共登记source card identity重复")
    current["post_tang_source_fact_count"] = len(source_fact_ids)
    current["post_tang_fingerprint"] = _digest({
        "partition_summaries": summaries,
        "source_card_ids": source_fact_ids,
    })
    current_high_difficulty = [
        row for row in current["records"]
        if row.get("public_outcome_registered") and row.get("combat_difficulty") in {"D3", "D4"}
    ]
    difficulty_review = dict(current.get("high_difficulty_contract_review_summary") or {})
    difficulty_review.update({
        "current_d3_d4_count": len(current_high_difficulty),
        "current_difficulty_counts": dict(sorted(Counter(str(row["combat_difficulty"]) for row in current_high_difficulty).items())),
        "fingerprint": _digest([
            {
                "record_ref": str(row.get("source_target_ref") or row.get("war_event_id") or ""),
                "combat_difficulty": row["combat_difficulty"],
                "combat_difficulty_basis": row["combat_difficulty_basis"],
            }
            for row in sorted(current_high_difficulty, key=lambda item: str(item.get("source_target_ref") or item.get("war_event_id") or ""))
        ]),
    })
    current["high_difficulty_contract_review_summary"] = difficulty_review
    current["semantic_fingerprint"] = _digest({key: value for key, value in current.items() if key != "semantic_fingerprint"})
    return current


def iter_bound_cycles(registry: Mapping[str, Any], ruler_id: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    seen: set[tuple[str, str]] = set()
    for record in registry.get("records") or ():
        if record.get("dynasty_partition") != "north_song":
            continue
        group = str(record["campaign_group_ref"])
        for phase in record.get("subject_phase_views") or ():
            if (phase.get("ruler_binding") or {}).get("ruler_id") != ruler_id:
                continue
            semantic = _digest({
                key: phase.get(key) for key in (
                    "evaluation_subject_phase", "actual_process", "cost_axes", "strategic_security",
                    "material_return", "border_control", "phase_return_class", "founding_startup_ledger",
                )
            })
            key = (group, semantic)
            if key in seen:
                continue
            seen.add(key)
            cycle = grouped.setdefault(group, {"campaign_group_ref": group, "war_event_refs": [], "phases": []})
            cycle["war_event_refs"].append(record["war_event_id"])
            cycle["phases"].append(dict(phase))
    return [
        {**row, "war_event_refs": _unique(row["war_event_refs"]), "phase_ids": [phase["phase_id"] for phase in row["phases"]]}
        for _, row in sorted(grouped.items())
    ]


def build_promotion_audit(registry: Mapping[str, Any]) -> dict[str, Any]:
    records = [row for row in registry.get("records") or () if row.get("dynasty_partition") == "north_song"]
    phases = [phase for row in records for phase in row.get("subject_phase_views") or ()]
    statuses = Counter((phase.get("ruler_binding") or {}).get("status") for phase in phases)
    rulers = Counter((phase.get("ruler_binding") or {}).get("ruler_name") for phase in phases if (phase.get("ruler_binding") or {}).get("ruler_name"))
    phase_ids = [phase["phase_id"] for phase in phases]
    return {
        "battle_card_count": len(records), "campaign_group_count": len({row["campaign_group_ref"] for row in records}),
        "subject_phase_count": len(phases), "duplicate_phase_id_count": len(phase_ids) - len(set(phase_ids)),
        "binding_status_counts": dict(sorted(statuses.items())), "bound_phase_counts": dict(sorted(rulers.items())),
        "deduplicated_cycle_counts": {row["ruler_name"]: len(iter_bound_cycles(registry, row["ruler_id"])) for row in RULER_WINDOWS},
        "score_consumed_phase_count": sum(rulers.values()),
        "out_of_scope_phase_count": sum(statuses.get(key, 0) for key in (
            "OUTSIDE_NORTH_SONG_EVALUATION_SUBJECT",
            "OUTSIDE_COMPLETE_RULER_WINDOWS",
            "OUTSIDE_RULER_CONTROL_AFTER_COLLAPSE",
        )),
        "unmatched_phase_count": statuses.get("UNRESOLVED_WINDOW_OVERLAP", 0),
        "window_conflict_count": statuses.get("UNRESOLVED_WINDOW_OVERLAP", 0),
        "retired_stale_record_count": RETIRED_STALE_NORTH_SONG_RECORD_COUNT,
    }


def write_promoted_battle_registry(workspace_root: Path) -> dict[str, Any]:
    path = workspace_root / REGISTRY_PATH
    payload = json.loads(path.read_text(encoding="utf-8"))
    promoted = promote_north_song_battle_registry(payload, workspace_root)
    _write_text_atomic(
        path, json.dumps(promoted, ensure_ascii=False, indent=2) + "\n"
    )
    from emperor_v4.evaluation.battle_parent_contract_registry import render_battle_parent_contract_registry_markdown
    _write_text_atomic(
        workspace_root / REGISTRY_MARKDOWN_PATH,
        render_battle_parent_contract_registry_markdown(promoted),
    )
    return build_promotion_audit(promoted)


def _load_adjudications(workspace_root: Path) -> list[dict[str, Any]]:
    rows = [dict(row) for row in _load_adjudication_payload(workspace_root).get("adjudications") or ()]
    if [row["ruler_id"] for row in rows] != [row["ruler_id"] for row in RULER_WINDOWS]:
        raise ValueError("北宋第三项裁决对象或顺序与11位完整主政窗口不一致")
    return rows


def _aggregate_d_cycle(cycle: Mapping[str, Any]) -> dict[str, Any]:
    phases = list(cycle["phases"])
    final_class = str(cycle.get("return_class_override") or "") or next((phase["phase_return_class"] for phase in reversed(phases) if phase["phase_return_class"] != "UNKNOWN"), "UNKNOWN")
    costs = {key: max((_grade_number(phase["cost_axes"].get(key), key) or 0) for phase in phases) for key in ("P", "S", "M", "A", "WC")}
    benefits = {
        key: max((_grade_number(value, key) or 0) for phase in phases for value in (
            [phase["strategic_security"]] if key in {"SB", "SN"} else
            [phase["border_control"].get(key)] if key in {"BCP", "BCN"} else [phase["material_return"]]
        )) for key in ("SB", "SN", "BCP", "BCN", "WR")
    }
    unknown_axes = sorted({
        key for phase in phases for key, value in {
            **phase["cost_axes"], "security": phase["strategic_security"], "return": phase["material_return"],
            "BCP": phase["border_control"].get("BCP"), "BCN": phase["border_control"].get("BCN"),
        }.items() if value == "UNKNOWN"
    })
    material = max(costs[key] for key in ("P", "S", "M", "A")) >= 3 or max(benefits[key] for key in ("SB", "SN", "BCP", "BCN")) >= 3
    positive_benefit_grade = max(benefits[key] for key in ("SB", "BCP", "WR"))
    negative_benefit_grade = max(benefits[key] for key in ("SN", "BCN"))
    return {
        "campaign_group_ref": cycle["campaign_group_ref"], "war_event_refs": cycle["war_event_refs"],
        "phase_ids": cycle["phase_ids"], "return_class": final_class, "cost_axes": costs,
        "benefit_axes": benefits, "unknown_axes": unknown_axes, "material": material,
        "positive_benefit_grade": positive_benefit_grade,
        "negative_benefit_grade": negative_benefit_grade,
        "major_high_return": final_class == "HIGH_RETURN" and positive_benefit_grade >= 4,
        "top_high_return": final_class == "HIGH_RETURN" and positive_benefit_grade >= 5,
        "national_negative": final_class == "NEGATIVE_RETURN" and (
            costs["P"] >= 5
            or max(costs["M"], costs["A"]) >= 4
            or max(benefits["SN"], benefits["BCN"]) >= 4
        ),
        "route": "D_INTERNAL_COST_ONLY" if re.search(r"MUTINY|REBELLION", cycle["campaign_group_ref"]) else "D_STANDARD",
        "merged_campaign_group_refs": list(cycle.get("merged_campaign_group_refs") or ()),
        "merge_reason": cycle.get("merge_reason"),
    }


def _cycles(registry: Mapping[str, Any], ruler_id: str) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    cycles = iter_bound_cycles(registry, ruler_id)
    return cycles, _unique(ref for cycle in cycles for ref in cycle["war_event_refs"]), [ref for cycle in cycles for ref in cycle["phase_ids"]]


def build_north_song_ab_records(registry: Mapping[str, Any], decisions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for decision in decisions:
        raw_cycles, _, _ = _cycles(registry, str(decision["ruler_id"]))
        cycles, _ = _third_item_cycles(decision, raw_cycles)
        event_refs = _unique(
            ref for cycle in cycles for ref in cycle["war_event_refs"]
        )
        phase_refs = _unique(
            ref for cycle in cycles for ref in cycle["phase_ids"]
        )
        axes = {axis: (_axis_a(axis, decision["AB"][axis]) if axis.startswith("A") else _axis_b(axis, decision["AB"][axis])) for axis in ("A1", "A2", "B1", "B2", "B4")}
        start, end = (float(decision["AB"]["B1"][key]) for key in ("start_equivalent", "end_equivalent"))
        control_refs = _unique(phase["phase_id"] for cycle in cycles for phase in cycle["phases"] if _grade_number(phase["border_control"].get("BCP"), "BCP") or _grade_number(phase["border_control"].get("BCN"), "BCN"))
        threat_refs = _unique(phase["phase_id"] for cycle in cycles for phase in cycle["phases"] if (_grade_number(phase.get("strategic_security"), "SB") or 0) >= 3 or (_grade_number(phase.get("strategic_security"), "SN") or 0) >= 3)
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
        records.append({
            "ruler_id": decision["ruler_id"], "ruler_name": decision["ruler_name"], "polity": "北宋", "partition": "北宋",
            "reign_range": decision["reign_range"], "subject_binding_review_status": "REVIEWED_SUFFICIENT",
            "ambiguous_event_refs": [], "boundary_stage_refs": [], "boundary_stage_excluded_refs": [], "boundary_stage_review_status": "REVIEWED",
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
            "coverage_status": "FORMAL_CURRENT", "score_ready": True, "adjudication_status": "REVIEWED",
            "rationale": "按97卷主体阶段卡与互斥皇帝/摄政主政窗口完成裁决。", "axes": axes,
            "AB_score_points": round(sum(axis["axis_points"] for axis in axes.values()), 2),
            "b1_region_control": {"start": {"AGGREGATE_REVIEWED": start}, "end": {"AGGREGATE_REVIEWED": end}},
            "b1_region_adjudications": [{"object_id": "NORTH_SONG_REIGN_CONTROL_PACKAGE", "object_name": "本主政窗口非统一边疆控制净包", "anchors": ["start", "end"], "counted": True, "control_equivalent": {"start": start, "end": end}, "evidence_refs": control_refs, "reason": decision["AB"]["B1"]["reason"]}],
            "b1_control_equivalents": {"start": start, "end": end, "net_change": round(end-start, 3), "weighted_value": weighted},
            "control_contribution_type": contribution_type,
            "control_contribution_grade_cap": contribution_cap,
            "major_in_reign_reversal_refs": _unique(phase["phase_id"] for cycle in cycles for phase in cycle["phases"] if (_grade_number(phase["border_control"].get("BCN"), "BCN") or 0) >= 4),
            "primary_threat_refs": threat_refs, "primary_control_package_refs": control_refs,
            "hold_event_refs": phase_refs, "non_defense_routing_refs": [],
        })
    return records


def build_north_song_c_records(registry: Mapping[str, Any], decisions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    records = []
    for decision in decisions:
        cycles, _, _ = _cycles(registry, str(decision["ruler_id"]))
        usable, _ = _third_item_cycles(decision, cycles)
        c1, c2, c3 = (int(decision["C"][key]) for key in ("C1", "C2", "C3"))
        evidence_ceiling = 3 if len(usable) <= 1 else 4 if len(usable) == 2 else 5
        if not usable and not decision.get("C", {}).get("non_war_evidence_refs"):
            raise ValueError(f"{decision['ruler_name']} C项无独立任务或非战争体系证据，不得直接结算")
        if c1 > evidence_ceiling or c3 > evidence_ceiling:
            raise ValueError(
                f"{decision['ruler_name']} C1/C3超过{len(usable)}项独立任务的证据上限{evidence_ceiling}"
            )
        overall, rate, points, surplus = _c_score(c1, c2, c3)
        grade = min(c1, c2, c3)
        lower, upper = ((0, 29), (30, 44), (45, 59), (60, 74), (75, 89), (90, 100))[grade]
        failures = [
            str(ref)
            for ref in decision.get("C", {}).get(
                "major_system_failure_group_refs", ()
            )
        ]
        successes = [
            str(ref)
            for ref in decision.get("C", {}).get(
                "major_system_success_group_refs", ()
            )
        ]
        known_task_groups = {str(cycle["campaign_group_ref"]) for cycle in usable}
        if (
            len(set(failures)) != len(failures)
            or len(set(successes)) != len(successes)
            or not set(failures).issubset(known_task_groups)
            or not set(successes).issubset(known_task_groups)
        ):
            raise ValueError(
                f"{decision['ruler_name']} C项重大胜负必须引用本人已结算的去重战役群"
            )
        if min(c1, c2, c3) == 5 and failures:
            raise ValueError(f"{decision['ruler_name']} C5不得保留重大体系失败引用")
        record = {
            "ruler_id": decision["ruler_id"], "ruler_name": decision["ruler_name"], "polity": "北宋", "partition": "北宋", "reign_range": decision["reign_range"],
            "independent_task_count": len(usable), "independent_task_groups": [cycle["campaign_group_ref"] for cycle in usable],
            "parent_cycle_merge_adjudications": [
                {
                    "canonical_cycle_ref": cycle["campaign_group_ref"],
                    "member_campaign_group_refs": cycle["merged_campaign_group_refs"],
                    "reason": cycle["merge_reason"],
                }
                for cycle in usable
                if cycle.get("merged_campaign_group_refs")
            ],
            "settled_event_refs": _unique(ref for cycle in usable for ref in cycle["war_event_refs"]), "cross_reign_slice_refs": [], "non_war_evidence_refs": [],
            "major_system_failure_refs": failures,
            "major_system_success_refs": successes,
            "score_ready": True, "coverage_status": "FULL_REIGN_WAR_EVENT_BINDING", "unresolved_gaps": [],
            "combat_delivery_grade": f"C1-{c1}", "operational_sustainability_cap": f"C2-{c2}", "system_reliability_cap": f"C3-{c3}",
            "C_overall_grade": overall, "C_score_rate": rate, "C_score_points": points, "C_score_support_surplus": surplus,
            "C_score_band": {"lower_rate": lower, "upper_rate": upper}, "adjudication_method": "SUBJECT_PHASE_CONTRACT_ADJUDICATION",
            "score_status": "DIRECT_C_SCORE_ASSIGNED",
            "evidence_ceiling": evidence_ceiling, "evidence_ceiling_adjustments": [],
            "cap_reasons": [decision["C"]["reason"]],
            "collapse_profile": "TERMINAL_NATIONWIDE_COLLAPSE" if decision.get("terminal_polity_collapse") else "NO_NATIONWIDE_DOMINANT_COLLAPSE",
            "passive_C1_adjustment": None, "passive_C1_cap": None, "passive_loss_rationale": None, "passive_loss_refs": [],
        }
        _apply_c_major_victory_gate(record)
        records.append(record)
    return records


def build_north_song_d_records(registry: Mapping[str, Any], decisions: Sequence[Mapping[str, Any]], ab_records: Sequence[Mapping[str, Any]], c_records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ab_by_id = {row["ruler_id"]: row for row in ab_records}
    c_by_id = {row["ruler_id"]: row for row in c_records}
    records = []
    for decision in decisions:
        cycles, event_refs, _ = _cycles(registry, str(decision["ruler_id"]))
        included_cycles, excluded = _third_item_cycles(decision, cycles)
        included = [_aggregate_d_cycle(cycle) for cycle in included_cycles]
        ab_points = ab_by_id[decision["ruler_id"]]["AB_score_points"]
        c_points = c_by_id[decision["ruler_id"]]["C_score_points"]
        grade, score, metrics = _d_grade_and_score(included)
        metrics["unknown_axis_cycle_count"] = sum(bool(cycle["unknown_axes"]) for cycle in included)
        metrics["abc_crosscheck"] = {
            "ab_score_points": ab_points,
            "ab_threshold_points": 80.0,
            "c_score_points": c_points,
            "c_threshold_points": 30.0,
            "small_sample_high_grade_gate_applied": False,
            "status": "SUFFICIENT_SUPPORT" if ab_points >= 80 and c_points >= 30 else "INSUFFICIENT_SUPPORT",
        }
        positive = [cycle for cycle in included if cycle["return_class"] in {"HIGH_RETURN", "PROPORTIONATE_RETURN"}]
        negative = [cycle for cycle in included if cycle["return_class"] in {"LOW_RETURN", "NEGATIVE_RETURN"}]
        high_cost = [cycle for cycle in included if max(cycle["cost_axes"][key] for key in ("P", "S", "M", "A")) >= 4]
        score_band = D_BANDS.get(grade)
        records.append({
            "ruler_id": decision["ruler_id"], "ruler_name": decision["ruler_name"], "polity": "北宋", "reign_range": decision["reign_range"],
            "schema_id": "emperor-v4-d-ruler-formal-settlement-v1", "canonical_status": "FORMAL_CURRENT", "formal_repository_entry": True,
            "formal_score_write": False, "database_write": False, "source_event_refs": event_refs,
            "d_cycle_refs": [cycle["campaign_group_ref"] for cycle in cycles], "included_d_cycle_refs": [cycle["campaign_group_ref"] for cycle in included],
            "excluded_unification_cycle_refs": [cycle["campaign_group_ref"] for cycle in excluded if not cycle.get("third_item_exclusion_reason")],
            "excluded_non_attributable_cycle_refs": [cycle["campaign_group_ref"] for cycle in excluded if cycle.get("third_item_exclusion_reason")],
            "excluded_cycle_adjudications": [
                {"campaign_group_ref": cycle["campaign_group_ref"], "reason": cycle["third_item_exclusion_reason"]}
                for cycle in excluded if cycle.get("third_item_exclusion_reason")
            ],
            "strategic_binding_refs": [ref for cycle in included for ref in cycle["phase_ids"]],
            "internal_cost_binding_refs": [cycle["campaign_group_ref"] for cycle in included if cycle["route"] == "D_INTERNAL_COST_ONLY"],
            "route_counts": dict(sorted(Counter(cycle["route"] for cycle in included).items())), "manual_portfolio_override": False,
            "cycle_merge_adjudications": [{"canonical_cycle_ref": cycle["campaign_group_ref"], "member_campaign_group_refs": cycle["merged_campaign_group_refs"], "reason": cycle["merge_reason"]} for cycle in included if cycle.get("merged_campaign_group_refs")],
            "D_grade": grade, "D_grade_reasons": _d_grade_reasons(grade, metrics),
            "D_score_points": score,
            "D_score_band": (
                {"lower_points": score_band[0], "upper_points": score_band[1]}
                if score_band is not None else None
            ),
            "portfolio_status": "FORMAL_CURRENT" if score is not None else "UNASSESSED_NO_MATERIAL_CYCLE",
            "D_portfolio_metrics": metrics,
            "unresolved_cycle_refs": [cycle["campaign_group_ref"] for cycle in included if cycle["return_class"] == "UNKNOWN" or cycle["unknown_axes"]],
            "unresolved_source_refs": [], "positive_benefit_cycle_refs": [cycle["campaign_group_ref"] for cycle in positive],
            "negative_benefit_cycle_refs": [cycle["campaign_group_ref"] for cycle in negative], "high_cost_cycle_refs": [cycle["campaign_group_ref"] for cycle in high_cost],
            "zero_return_high_cost_cycle_refs": [cycle["campaign_group_ref"] for cycle in high_cost if cycle["return_class"] in {"LOW_RETURN", "NEGATIVE_RETURN"}],
            "peak_d_cost_axes": {key: f"{key}{max((cycle['cost_axes'][key] for cycle in included), default=0)}" for key in ("P", "M", "A")},
            "readiness_counts": {"HOLD": len(included)}, "binding_source": "SUBJECT_PHASE_FORMAL_CURRENT", "ruler_event_class_overrides": [],
        })
    return records


def _build_combined(decisions: Sequence[Mapping[str, Any]], ab: Sequence[Mapping[str, Any]], c: Sequence[Mapping[str, Any]], d: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ab_by = {row["ruler_id"]: row for row in ab}; c_by = {row["ruler_id"]: row for row in c}; d_by = {row["ruler_id"]: row for row in d}
    rows = []
    for decision in decisions:
        a, cr, dr = ab_by[decision["ruler_id"]], c_by[decision["ruler_id"]], d_by[decision["ruler_id"]]
        a_points = round(a["axes"]["A1"]["axis_points"] + a["axes"]["A2"]["axis_points"], 2)
        b_points = round(a["axes"]["B1"]["axis_points"] + a["axes"]["B2"]["axis_points"] + a["axes"]["B4"]["axis_points"], 2)
        ready = dr["D_score_points"] is not None
        total = (
            round(a["AB_score_points"] + cr["C_score_points"] + dr["D_score_points"], 1)
            if ready else None
        )
        rows.append({
            "ruler_id": decision["ruler_id"], "ruler_name": decision["ruler_name"], "polity": "北宋", "reign_range": decision["reign_range"],
            "rank": None, "rank_status": "GLOBAL_CURRENT", "partition": "北宋", "partition_rank": None,
            "A_score_points": a_points, "B_score_points": b_points, "AB_score_points": a["AB_score_points"],
            "C_score_points": cr["C_score_points"], "D_score_points": dr["D_score_points"],
            "D_score_status": "DIRECT_D_SCORE_ASSIGNED" if ready else "UNASSESSED_NO_MATERIAL_CYCLE",
            "third_item_score_points": total,
            "third_item_score_rate": round(total / 250 * 100, 2) if total is not None else None,
            "axes": {"A1": a["axes"]["A1"], "A2": a["axes"]["A2"], "B1": a["axes"]["B1"], "B2": a["axes"]["B2"], "B4": a["axes"]["B4"], "C1": cr["combat_delivery_grade"], "C2": cr["operational_sustainability_cap"], "C3": cr["system_reliability_cap"], "C_overall": cr["C_overall_grade"], "D": dr["D_grade"]},
            "coverage_status": {"AB": a["coverage_status"], "C": cr["coverage_status"], "D": dr["portfolio_status"]},
            "pending_reason": None if ready else "D项无已闭合实质投资周期，不赋中性分。",
        })
    eligible = [row for row in rows if row["third_item_score_points"] is not None]
    for rank, row in enumerate(sorted(eligible, key=lambda item: (-item["third_item_score_points"], item["ruler_name"])), start=1):
        row["partition_rank"] = rank
    return rows


def _assign_global(records: Sequence[dict[str, Any]]) -> None:
    eligible = sorted((row for row in records if row.get("third_item_score_points") is not None), key=lambda row: (-float(row["third_item_score_points"]), str(row["ruler_name"])))
    previous = None; rank = 0
    for position, row in enumerate(eligible, start=1):
        score = float(row["third_item_score_points"])
        if previous is None or score != previous:
            rank = position; previous = score
        row["rank"] = rank; row["rank_status"] = f"GLOBAL_CURRENT_{len(eligible)}"


def build_north_song_formal_payloads(workspace_root: Path, registry: Mapping[str, Any]) -> dict[str, Any]:
    decisions = _load_adjudications(workspace_root)
    ab_rows = build_north_song_ab_records(registry, decisions)
    c_rows = build_north_song_c_records(registry, decisions)
    _validate_bc_parent_cycle_alignment(ab_rows, c_rows)
    d_rows = build_north_song_d_records(registry, decisions, ab_rows, c_rows)
    partition_rows = _build_combined(decisions, ab_rows, c_rows, d_rows)
    ab = _replace_partition_records(json.loads((workspace_root / AB_PATH).read_text(encoding="utf-8")), ab_rows)
    c = _replace_partition_records(json.loads((workspace_root / C_PATH).read_text(encoding="utf-8")), c_rows)
    for row in c["records"]:
        row.pop("confidence", None)
    _normalize_qin_tang_bc_parent_cycles(workspace_root, ab["records"], c["records"])
    _validate_formal_abc_contracts(ab["records"], c["records"])
    d = _replace_partition_records(json.loads((workspace_root / D_PATH).read_text(encoding="utf-8")), d_rows)
    _recalculate_qin_tang_d_records(workspace_root, d["records"], ab["records"], c["records"])
    _normalize_formal_d_records(d["records"])
    combined = _replace_partition_records(json.loads((workspace_root / FORMAL_PATH).read_text(encoding="utf-8")), partition_rows)
    combined.pop("qin_tang_rank_freeze", None)
    combined.pop("qin_tang_value_freeze", None)
    _sync_formal_c_into_combined(c["records"], combined["records"])
    _sync_formal_d_into_combined(d["records"], combined["records"])
    _assign_global(combined["records"])
    total = len(combined["records"])
    for payload, count_key in ((ab, "ruler_count"), (c, "record_count"), (d, "record_count")):
        payload[count_key] = len(payload["records"]); payload["scope"] = f"秦至唐95人可复核当前值 + 五代十国12人 + 北宋11人当前结算"
        payload["north_song_source_fingerprint"] = SOURCE_SET_FINGERPRINT
    ab.update({"reviewed_count": sum(row.get("adjudication_status") == "REVIEWED" for row in ab["records"]), "pending_count": sum(not row.get("score_ready") for row in ab["records"]), "score_ready_count": sum(bool(row.get("score_ready")) for row in ab["records"])})
    c.update({"score_ready_count": sum(bool(row.get("score_ready")) for row in c["records"]), "partition_counts": dict(sorted(Counter(str(row.get("partition")) for row in c["records"]).items())), "grade_distribution": dict(sorted(Counter(str(row.get("C_overall_grade")) for row in c["records"]).items()))})
    d["grade_distribution"] = dict(sorted(Counter(str(row.get("D_grade")) for row in d["records"]).items()))
    combined.update({
        "scope": f"秦至唐95人当前分值 + 五代十国12人 + 北宋11人；第三项{total}人统一排名",
        "record_count": total, "score_ready_count": sum(row.get("third_item_score_points") is not None for row in combined["records"]),
        "D_unassessed_neutral_count": sum(row.get("D_score_points") is None for row in combined["records"]),
        "north_song_source_fingerprint": SOURCE_SET_FINGERPRINT,
        "north_song_ready_count": sum(row.get("third_item_score_points") is not None for row in partition_rows),
        "north_song_pending_count": sum(row.get("third_item_score_points") is None for row in partition_rows),
        "north_song_partial_exclusions": [],
        "score_recalculation_policy": "ALL_RECORDS_REVIEWABLE_CURRENT_VALUE", "global_ranking_enabled": True, "rank_tie_policy": "COMPETITION_RANK", "shared_source_root": "docs/史料通读产物",
    })
    return {"AB": ab, "C": c, "D": d, "combined": combined, "partition_records": partition_rows}


def write_north_song_third_item(workspace_root: Path) -> dict[str, Any]:
    promotion_audit = write_promoted_battle_registry(workspace_root)
    registry = json.loads((workspace_root / REGISTRY_PATH).read_text(encoding="utf-8"))
    payloads = build_north_song_formal_payloads(workspace_root, registry)
    paths = {"AB": AB_PATH, "C": C_PATH, "D": D_PATH, "combined": FORMAL_PATH}
    for kind, path in paths.items():
        _write_text_atomic(
            workspace_root / path,
            json.dumps(payloads[kind], ensure_ascii=False, indent=2) + "\n",
        )
        md_path = workspace_root / path.with_suffix(".md")
        if kind == "combined":
            _write_text_atomic(
                md_path, _render_combined_markdown(payloads[kind]["records"])
            )
        else:
            _write_text_atomic(
                md_path, _render_formal_markdown(kind, payloads[kind]["records"])
            )
    hashes = {kind: sha256((workspace_root / path).read_bytes()).hexdigest() for kind, path in paths.items()}
    hashes["battle_registry"] = sha256((workspace_root / REGISTRY_PATH).read_bytes()).hexdigest()
    return {
        "promotion_audit": promotion_audit,
        "formal_ready_count": payloads["combined"]["north_song_ready_count"],
        "formal_pending_count": payloads["combined"]["north_song_pending_count"],
        "hashes": hashes,
        "records": payloads["partition_records"],
    }


def main() -> int:
    print(json.dumps(write_north_song_third_item(Path.cwd()), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
