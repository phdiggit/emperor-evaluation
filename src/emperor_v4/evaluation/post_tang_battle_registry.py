from __future__ import annotations

from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

SOURCE_PARTITIONS = {
    "资治通鉴-五代十国": ("five_dynasties", "五代十国", 0),
    "辽史": ("liao", "辽", 1),
    "续资治通鉴-北宋": ("north_song", "北宋", 2),
    "续资治通鉴-南宋": ("south_song", "南宋", 3),
    "西夏书事": ("xixia", "西夏", 4),
    "金史": ("jin", "金", 5),
    "元史": ("yuan", "元", 6),
    "明史": ("ming", "明", 7),
    "清史稿": ("qing", "清", 8),
}
NON_BATTLE_MARKERS = ("MUTINY", "COUP", "ASSASSIN", "PALACE", "KILLED", "兵变", "政变", "刺杀", "宫变", "哗变")
TERMINAL_MARKERS = ("灭亡", "覆灭", "亡国", "尽降", "悉降", "投降", "归降", "受降", "被俘", "擒获", "攻灭", "平定", "统一", "全军覆没", "主力被歼")
MAJOR_RESULT_MARKERS = ("大败", "击破", "大破", "攻下", "攻克", "克复", "收复", "解围", "退兵", "退军", "败退", "溃败", "歼灭", "全歼", "夺回", "控制")
BATTLE_RESULT_MARKERS = (*TERMINAL_MARKERS, *MAJOR_RESULT_MARKERS, "战败", "不利", "撤退", "撤军", "失守", "陷落", "战死", "被杀")
UNIFICATION_MARKERS = (
    "UNIFICATION", "FOUNDING", "PREACCESSION", "ANCESTRAL", "CONSOLIDATION", "-RISE",
    "统一诸", "完成统一", "创业兼并", "即位前兼并",
)
UNIFICATION_RESULT_MARKERS = ("臣属", "归附", "纳入", "兼并", "扩张", "攻服", "降服")
COMMAND_MARKERS = ("率", "帅", "统", "督", "领", "亲征", "讨伐", "进攻", "守御")
NEGATIVE_NAME_SUFFIXES = ("战败", "败退", "被俘", "被擒", "被杀", "战死", "不利")
# These are adjudicated chain memberships, not title-pattern propagation.  A
# member can stay below the public-outcome threshold while still being retained
# as neutral context inside the dynasty portfolio.
POST_TANG_UNIFICATION_CHAINS = {
    "UCP-POST-GORYEO-936": {
        "dynasty": "五代十国",
        "scope": "《资治通鉴》五代卷所载高丽击破新罗、百济并接受诸国归附的域外统一结果",
        "refs": ("CAMPAIGN-GORYEO-UNIFICATION-936",),
    },
    "UCP-POST-LIAO-901-926": {
        "dynasty": "辽",
        "scope": "阿保机即位前扩张至西方诸部、山北方向与渤海终局的辽朝形成链",
        "refs": (
            "CAMPAIGN-LIAO-PREACCESSION-EXPANSION-901-903",
            "CAMPAIGN-LIAO-WESTERN-EXPANSION-916",
            "CAMPAIGN-LIAO-TIANDE-920",
            "CAMPAIGN-LIAO-BALHAE-CONQUEST-925-926",
            "CAMPAIGN-LIAO-BALHAE-STABILIZATION-926",
        ),
    },
    "UCP-POST-SONG-963-979": {
        "dynasty": "北宋",
        "scope": "宋承后周中原起点，连续取得荆湖、后蜀、南汉、南唐并终结北汉的核心区域统一链",
        "refs": (
            "CAMPAIGN-HUNAN-CONQUERED-963",
            "CAMPAIGN-SHU-CAPITULATES-965",
            "CAMPAIGN-GUANGZHOU-BURNED-SURRENDERS-971",
            "CAMPAIGN-SONG-INVADES-JIANGNAN-974",
            "CAMPAIGN-CAISHI-BATTLE-974",
            "CAMPAIGN-XIAKOU-BATTLE-974",
            "CAMPAIGN-NORTH-CAMP-NIGHT-ATTACK-975",
            "CAMPAIGN-RUNZHOU-SURRENDERS-975",
            "CAMPAIGN-JINLING-CAPTURED-975",
            "CAMPAIGN-TAIYUAN-OUTER-CITIES-979",
            "CAMPAIGN-NORTHERN-HAN-SURRENDERS-979",
        ),
    },
    "UCP-POST-PROTO-JIN-SHILU": {
        "dynasty": "金",
        "scope": "石鲁时期以条教整合部众并对不服部落用兵的创业兼并上下文",
        "refs": ("CAMPAIGN-PROTO-JIN-SHILU-TRIBAL-CONSOLIDATION",),
    },
    "UCP-POST-JIN-1114-1126": {
        "dynasty": "金",
        "scope": "金由宁江起兵、终结辽朝并攻破北宋中枢的两大国家竞争极终局链",
        "refs": (
            "CAMPAIGN-JIN-LIAO-NINGJIANG-1114",
            "CAMPAIGN-JIN-GAO-YONGCHANG-1116",
            "CAMPAIGN-JIN-LIAO-CENTRAL-WESTERN-CAPITALS-1122",
            "CAMPAIGN-JIN-LIAO-YINSHAN-PURSUIT-1123",
            "CAMPAIGN-JIN-LIAO-FINAL-CAPTURE-1125",
            "CAMPAIGN-JIN-SONG-FIRST-KAIFENG-1125-1126",
            "CAMPAIGN-JIN-SONG-SECOND-KAIFENG-1126",
        ),
    },
    "UCP-POST-YUAN-ANCESTRAL-BODONCHAR": {
        "dynasty": "元",
        "scope": "孛端叉儿率壮士使无所隶属民户降服的单一先世兼并链",
        "refs": ("CAMPAIGN-YUAN-ANCESTRAL-SUBJUGATION",),
    },
    "UCP-POST-YUAN-ANCESTRAL-HAIDU": {
        "dynasty": "元",
        "scope": "海都灭门幸存后攻服押剌伊而并吸收周边部族的单一先世扩张链",
        "refs": ("CAMPAIGN-YUAN-ANCESTRAL-HAIDU-RISE",),
    },
    "UCP-POST-YUAN-1205-1279": {
        "dynasty": "元",
        "scope": "蒙古诸政权自西夏方向扩张至灭金、取大理和灭南宋的跨代统一链",
        "refs": (
            "CAMPAIGN-YUAN-XIXIA-1205",
            "CAMPAIGN-YUAN-XIXIA-1209",
            "CAMPAIGN-YUAN-XIXIA-1226-1227",
            "CAMPAIGN-YUAN-JIN-1211",
            "CAMPAIGN-YUAN-JIN-1212",
            "CAMPAIGN-YUAN-JIN-THREE-ARMIES-1213",
            "CAMPAIGN-YUAN-JIN-ZHONGDU-1214-1215",
            "CAMPAIGN-YUAN-MUKHALI-JIN-1217-1223",
            "CAMPAIGN-YUAN-JIN-1230-1231",
            "CAMPAIGN-YUAN-JIN-SANFENG-1232",
            "CAMPAIGN-YUAN-JIN-NANJING-1232-1233",
            "CAMPAIGN-YUAN-JIN-CAIZHOU-1233-1234",
            "CAMPAIGN-YUAN-DALI-1253",
            "CAMPAIGN-YUAN-DALI-1253-1254",
            "CAMPAIGN-YUAN-SONG-CONQUEST",
        ),
    },
    "UCP-POST-MING-1353-1382": {
        "dynasty": "明",
        "scope": "朱元璋政权由滁和根据地、渡江、消灭主要竞争政权至北伐和西南收束的统一链",
        "refs": (
            "CAMPAIGN-MING-CHUZHOU-1353",
            "CAMPAIGN-MING-HEZHOU-1355",
            "CAMPAIGN-MING-YANGTZE-CROSSING-1355",
            "CAMPAIGN-MING-JIANGNAN-CONSOLIDATION-1357-1359",
            "CAMPAIGN-MING-JIANGZHOU-1361-1362",
            "CAMPAIGN-MING-CHEN-HAN-END-1363-1364",
            "CAMPAIGN-MING-HUAIDONG-1365-1366",
            "CAMPAIGN-MING-ZHANGSHICHENG-DEFEAT-1367",
            "CAMPAIGN-MING-NORTHERN-EXPEDITION-1367-1368",
            "CAMPAIGN-MING-SHANXI-SHAANXI-1368-1369",
            "CAMPAIGN-MING-SOUTHERN-UNIFICATION-1368",
            "CAMPAIGN-MING-SICHUAN-1371",
            "CAMPAIGN-MING-YUNNAN-1381-1382",
        ),
    },
    "UCP-POST-QING-FOUNDING-1607-1662": {
        "dynasty": "清",
        "scope": "建州兼并、辽东突破、入关及南明主体终结的创业兼并链",
        "refs": (
            "CAMPAIGN-QING-EASTERN-TRIBES-HUIFA-1607-1611",
            "CAMPAIGN-QING-ULA-YEHE-1612-1613",
            "CAMPAIGN-QING-MING-FUSHUN-1618",
            "CAMPAIGN-QING-SARHU-AND-YEHE-1619",
            "CAMPAIGN-QING-SHENYANG-LIAOYANG-1621",
            "CAMPAIGN-QING-GUANGNING-1622",
            "CAMPAIGN-QING-DALINGHE-1631",
            "CAMPAIGN-QING-SONGJIN-1639",
            "CAMPAIGN-MING-SONGJIN-1641-1642",
            "CAMPAIGN-QING-SHANHAIGUAN-BEIJING-1644",
            "CAMPAIGN-QING-LI-ZICHENG-1644-1645",
            "CAMPAIGN-QING-SOUTHERN-MING-JIANGNAN-1645",
            "CAMPAIGN-QING-SOUTHERN-CONSOLIDATION-1645-1647",
            "CAMPAIGN-QING-ZHANG-XIANZHONG-1646",
            "CAMPAIGN-QING-DATONG-REBELLION-1648-1649",
            "CAMPAIGN-QING-JIN-SHENGHUAN-REBELLION-1648-1649",
            "CAMPAIGN-QING-YUNGUI-1657-1659",
            "CAMPAIGN-QING-YONGLI-END-1661-1662",
        ),
    },
    "UCP-POST-QING-REUNIFICATION-1673-1683": {
        "dynasty": "清",
        "scope": "三藩战争爆发至云南终局及台湾郑氏终结的再统一链",
        "refs": (
            "CAMPAIGN-QING-THREE-FEUDATORIES-OUTBREAK-1673-1674",
            "CAMPAIGN-QING-GENG-FUJIAN-1674-1677",
            "CAMPAIGN-QING-WANG-FUCHEN-1674-1676",
            "CAMPAIGN-QING-GUANGDONG-GUANGXI-1676-1680",
            "CAMPAIGN-QING-COUNTEROFFENSIVE-1678-1680",
            "CAMPAIGN-QING-YUNNAN-FINAL-1680-1681",
            "CAMPAIGN-QING-TAIWAN-1683",
        ),
    },
}

UNIFICATION_REF_TO_PORTFOLIO = {
    target_ref: (portfolio_ref, order)
    for portfolio_ref, portfolio in POST_TANG_UNIFICATION_CHAINS.items()
    for order, target_ref in enumerate(portfolio["refs"], start=1)
}

# Point adjudications for closed results which the generic lower-bound marker
# compiler cannot recognize reliably.  No value is inferred from dynasty name.
FORCED_UNIFICATION_TIERS = {
    "CAMPAIGN-YUAN-DALI-1253": "A",
    "CAMPAIGN-YUAN-DALI-1253-1254": "A",
    "CAMPAIGN-YUAN-SONG-CONQUEST": "A",
    "CAMPAIGN-MING-YANGTZE-CROSSING-1355": "B",
    "CAMPAIGN-MING-JIANGNAN-CONSOLIDATION-1357-1359": "A",
    "CAMPAIGN-MING-JIANGZHOU-1361-1362": "B",
    "CAMPAIGN-MING-NORTHERN-EXPEDITION-1367-1368": "A",
    "CAMPAIGN-MING-SOUTHERN-UNIFICATION-1368": "A",
    "CAMPAIGN-QING-MING-FUSHUN-1618": "B",
    "CAMPAIGN-QING-SARHU-AND-YEHE-1619": "A",
    "CAMPAIGN-QING-DALINGHE-1631": "B",
    "CAMPAIGN-QING-GUANGDONG-GUANGXI-1676-1680": "B",
    "CAMPAIGN-QING-TAIWAN-1683": "A",
}

# Same events observed from another dynastic chronicle receive one canonical
# public destination instead of being counted twice.
CROSS_SOURCE_MERGES = {
    "CAMPAIGN-YUAN-LINAN-SURRENDER-1276": "CAMPAIGN-YUAN-SONG-CONQUEST",
    "CAMPAIGN-MING-PINGJIANG-1366-1367": "CAMPAIGN-MING-ZHANGSHICHENG-DEFEAT-1367",
    "CAMPAIGN-YUAN-DALI-1253-1254": "CAMPAIGN-YUAN-DALI-1253",
    "HANDOFF-XZZTJ-137-KHITAN-SUPPRESSION": "CAMPAIGN-JIN-KHITAN-WOGUA-REVOLT-1161-1162",
    "CAMPAIGN-SONG220-NORTHERN-EXPEDITION": "CAMPAIGN-MING-NORTHERN-EXPEDITION-1367-1368",
    "CAMPAIGN-SONG220-ZHEDONG": "CAMPAIGN-MING-SOUTHEAST-1367",
    "CAMPAIGN-MING-HUAI-EAST-CONQUEST-1366": "CAMPAIGN-MING-HUAIDONG-1365-1366",
    "CAMPAIGN-MING-LOWER-YANGTZE-CONQUEST-1366-1367": "CAMPAIGN-MING-ZHANGSHICHENG-DEFEAT-1367",
    "CAMPAIGN-MING-NORTH-CENTRAL-CONQUEST-1368": "CAMPAIGN-MING-NORTHERN-EXPEDITION-1367-1368",
    "CAMPAIGN-MING-SOUTHERN-CONQUEST-1368": "CAMPAIGN-MING-SOUTHERN-UNIFICATION-1368",
    "CAMPAIGN-MING-CAPITAL-FALL-1368": "CAMPAIGN-MING-NORTHERN-EXPEDITION-1367-1368",
    "CAMPAIGN-MING-TONGZHOU-CAPITAL-1368": "CAMPAIGN-MING-NORTHERN-EXPEDITION-1367-1368",
}

# Several Ming-founding facts were read from the continuation chronicle and
# originally inherited its source partition and over-broad target.  Rehome only
# the exact accepted fact ids; this preserves their source refs while giving
# each fact one canonical battle destination.
FACT_TARGET_OVERRIDES = {
    "CHF-SONG-212-010": "CAMPAIGN-MING-YANGTZE-CROSSING-1355",
    "CHF-SONG-212-011": "CAMPAIGN-MING-JIQING-ZHENJIANG-1356",
    "CHF-SONG-213-004": "CAMPAIGN-MING-JIQING-ZHENJIANG-1356",
    "CHF-SONG-213-005": "CAMPAIGN-MING-JIQING-ZHENJIANG-1356",
    "CHF-SONG-214-005": "CAMPAIGN-MING-JIANGNAN-CONSOLIDATION-1357-1359",
    "CHF-SONG-214-012": "CAMPAIGN-MING-JIANGNAN-CONSOLIDATION-1357-1359",
    "CHF-SONG-215-002": "CAMPAIGN-MING-JIANGNAN-CONSOLIDATION-1357-1359",
    "CHF-SONG-215-008": "CAMPAIGN-MING-LONGWAN-1360",
    "CHF-SONG-218-015": "CAMPAIGN-MING-HUAIDONG-1365-1366",
    "CHF-SONG-219-001": "CAMPAIGN-MING-JIANGNAN-CONSOLIDATION-1357-1359",
    "CHF-SONG-219-008": "CAMPAIGN-MING-HUAIDONG-1365-1366",
    "CHF-SONG-219-011": "CAMPAIGN-MING-ZHANGSHICHENG-DEFEAT-1367",
    "CHF-SONG-219-012": "CAMPAIGN-MING-ZHANGSHICHENG-DEFEAT-1367",
    "CHF-SONG-220-004": "CAMPAIGN-MING-ZHANGSHICHENG-DEFEAT-1367",
    "CHF-XZZTJ-013-CAO-BIN-SUPPLY-CRISIS-986": "CAMPAIGN-QIGOU-PASS-DEFEAT-986",
    "CHF-QING-V03-SONGJIN-DECISIVE-CAMPAIGN-1640-1642": "CAMPAIGN-MING-SONGJIN-1641-1642",
    "CHF-MING-V05-JINGNAN-UPRISING-CONTEXT-1399": "CAMPAIGN-MING-JINGNAN-1399-1402",
    "CHF-MING-V05-JINGNAN-NORTH-CONTEXT-1399": "CAMPAIGN-MING-JINGNAN-1399-1402",
    "CHF-MING-V05-JINGNAN-1400-CONTEXT": "CAMPAIGN-MING-JINGNAN-1399-1402",
    "CHF-MING-V05-JINGNAN-ATTRITION-CONTEXT-1401": "CAMPAIGN-MING-JINGNAN-1399-1402",
    "CHF-MING-V05-JINGNAN-SOUTHWARD-CONTEXT-1402": "CAMPAIGN-MING-JINGNAN-1399-1402",
    "CHF-MING-V05-JINGNAN-CAPITAL-CONTEXT-1402": "CAMPAIGN-MING-JINGNAN-1399-1402",
}

TARGET_CANONICAL_SOURCE = {
    target_ref: "明史" for target_ref in set(FACT_TARGET_OVERRIDES.values())
}

PRE_TANG_CONTROL_PORTFOLIOS = (
    ("唐", "UCP-TANG-LIYUAN-617-628"),
    ("东汉", "UCP-HAN-LIUXIU-23-36"),
    ("西汉", "UCP-HAN-LIUBANG-BCE207-BCE202"),
    ("秦", "UCP-QIN-YINGZHENG-230-221"),
    ("晋", "UCP-JIN-SIMAYAN-279-280"),
    ("隋", "UCP-SUI-YANGJIAN-587-591"),
)


def _digest(value: object) -> str:
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _interval_union_length(intervals: Sequence[tuple[float, float]]) -> float:
    merged: list[list[float]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1]:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return sum(end - start for start, end in merged)


def _horizontal_total_band(value: float | None) -> str:
    if value is None:
        return "VALUE_UNKNOWN"
    if value >= 1000:
        return "H1"
    if value >= 850:
        return "H2"
    if value >= 700:
        return "H3"
    if value >= 500:
        return "H4"
    if value >= 300:
        return "H5"
    return "BELOW_H5"


def _load_period_war_region_values(
    workspace_root: Path,
) -> tuple[dict[str, str], dict[str, dict[str, dict[str, Any]]], dict[str, float]]:
    payload = json.loads(
        (
            workspace_root
            / "config/period-war-region-value-adjudications.json"
        ).read_text(encoding="utf-8")
    )
    if payload.get("schema_version") != "period-war-region-value-adjudications-v1":
        raise ValueError("时代化战争区域价值裁决配置无效")
    weights = {
        str(key): float(value)
        for key, value in (payload.get("rubric") or {})
        .get("grade_weights", {})
        .items()
    }
    if weights != {"R2": 40.0, "R3": 60.0, "R4": 80.0, "R5": 100.0}:
        raise ValueError("时代化战争区域价值权重漂移")
    profiles: dict[str, dict[str, dict[str, Any]]] = {}
    for period in payload.get("period_profiles") or ():
        period_id = str(period.get("period_id") or "")
        if not period_id or period_id in profiles or not period.get("basis"):
            raise ValueError(f"时代化战争区域窗口缺失或重复: {period_id}")
        regions = dict(period.get("regions") or {})
        if not regions:
            raise ValueError(f"时代化战争区域窗口无区域裁决: {period_id}")
        for region_id, row in regions.items():
            strategic = int(str(row.get("S") or "S0")[1:])
            military = int(str(row.get("M") or "M0")[1:])
            grade = str(row.get("R") or "")
            if strategic not in {2, 3, 4, 5} or military not in {2, 3, 4, 5}:
                raise ValueError(f"时代化战争区域轴非法: {period_id}/{region_id}")
            expected_grade = (
                "R5"
                if strategic == 5 and military >= 4
                else "R4"
                if (strategic == 5 and military == 3)
                or (strategic == 4 and military >= 4)
                else "R3"
                if strategic >= 3 and military >= 2
                else "R2"
            )
            if grade != expected_grade or not row.get("basis"):
                raise ValueError(
                    f"时代化战争区域档与矩阵不一致: {period_id}/{region_id}/{grade}/{expected_grade}"
                )
        profiles[period_id] = regions
    portfolio_period_map = {
        str(key): str(value)
        for key, value in (payload.get("portfolio_period_map") or {}).items()
    }
    if any(period_id not in profiles for period_id in portfolio_period_map.values()):
        raise ValueError("统一链引用了不存在的时代化战争区域窗口")
    return portfolio_period_map, profiles, weights


def _load_unification_opponent_calibrations(
    workspace_root: Path,
) -> dict[str, dict[str, Any]]:
    payload = json.loads(
        (
            workspace_root
            / "config/unification-chain-opponent-calibrations.json"
        ).read_text(encoding="utf-8")
    )
    if payload.get("schema_version") != "unification-chain-opponent-calibrations-v1":
        raise ValueError("统一链对手战争机器校准配置无效")
    rows = list(payload.get("adjudications") or ())
    by_ref = {str(row.get("portfolio_ref") or ""): row for row in rows}
    expected_refs = {
        *(portfolio_ref for _, portfolio_ref in PRE_TANG_CONTROL_PORTFOLIOS),
        *POST_TANG_UNIFICATION_CHAINS,
    }
    if len(by_ref) != len(rows) or set(by_ref) != expected_refs:
        raise ValueError(
            "统一链对手战争机器校准覆盖漂移: "
            f"missing={sorted(expected_refs - set(by_ref))}, "
            f"extra={sorted(set(by_ref) - expected_refs)}"
        )
    all_system_ids: set[str] = set()
    credited_closures = {"FULL_TERMINAL", "DECISIVE_SYSTEM_DEFEAT"}
    allowed_grades = {"O1", "O2", "O3", "O4", "O5"}
    allowed_chain_grades = {
        "H1", "H2", "H3", "H4", "H5", "BELOW_H5", "NOT_COMPARABLE"
    }
    for portfolio_ref, row in by_ref.items():
        chain_grade = str(row.get("chain_grade") or "")
        if (
            chain_grade not in allowed_chain_grades
            or not str(row.get("rule_hit") or "").strip()
            or not str(row.get("grade_basis") or "").strip()
        ):
            raise ValueError(f"统一链对手总档字段不完整: {portfolio_ref}")
        systems = list(row.get("opponent_systems") or ())
        local_ids = {str(system.get("system_id") or "") for system in systems}
        if len(local_ids) != len(systems) or "" in local_ids or all_system_ids & local_ids:
            raise ValueError(f"统一链对手体系ID缺失或重复: {portfolio_ref}")
        all_system_ids.update(local_ids)
        for system in systems:
            if (
                system.get("organization_grade") not in allowed_grades
                or not str(system.get("opponent_label") or "").strip()
                or not str(system.get("closure") or "").strip()
                or not str(system.get("basis") or "").strip()
                or not list(system.get("source_campaign_refs") or ())
            ):
                raise ValueError(
                    f"统一链对手体系字段不完整: {portfolio_ref}/{system.get('system_id')}"
                )
            lineage_parent = str(system.get("lineage_parent") or "")
            if lineage_parent and lineage_parent not in local_ids:
                raise ValueError(
                    f"统一链对手体系祖先不在同一组合: {portfolio_ref}/{lineage_parent}"
                )
        credited = [
            system for system in systems if system["closure"] in credited_closures
        ]
        full = [system for system in systems if system["closure"] == "FULL_TERMINAL"]
        credited_counts = Counter(system["organization_grade"] for system in credited)
        full_counts = Counter(system["organization_grade"] for system in full)
        compound_o5_counts = Counter(
            str(system.get("compound_group"))
            for system in full
            if system["organization_grade"] == "O5" and system.get("compound_group")
        )
        expected_grade = (
            "NOT_COMPARABLE"
            if chain_grade == "NOT_COMPARABLE"
            else "H1"
            if max(compound_o5_counts.values(), default=0) >= 2
            or full_counts["O5"] >= 3
            or (full_counts["O5"] >= 2 and full_counts["O4"] >= 1)
            else "H2"
            if credited_counts["O5"] >= 2
            or (credited_counts["O5"] >= 1 and full_counts["O4"] >= 2)
            or full_counts["O4"] >= 3
            else "H3"
            if credited_counts["O5"] >= 1 or full_counts["O4"] >= 2
            else "H4"
            if full_counts["O4"] >= 1 and full_counts["O3"] >= 1
            else "H5"
            if full_counts["O3"] >= 1
            else "BELOW_H5"
        )
        if chain_grade != expected_grade:
            raise ValueError(
                f"统一链对手总档与简单规则不一致: {portfolio_ref}/{chain_grade}/{expected_grade}"
            )
    return by_ref


def build_pre_tang_unification_control_calibrations(
    battle_payload: Mapping[str, Any], workspace_root: Path
) -> list[dict[str, Any]]:
    portfolio_period_map, period_profiles, grade_weights = (
        _load_period_war_region_values(workspace_root)
    )
    opponent_calibrations = _load_unification_opponent_calibrations(workspace_root)
    control_payload = json.loads(
        (workspace_root / "config/first-item-c-territorial-control-adjudications.json").read_text(encoding="utf-8")
    )
    acquisition_payload = json.loads(
        (
            workspace_root
            / "config/pre-tang-unification-war-control-adjudications.json"
        ).read_text(encoding="utf-8")
    )
    if (
        acquisition_payload.get("schema_version")
        != "pre-tang-unification-war-control-adjudications-v1"
        or acquisition_payload.get("acquisition_mode")
        != "WAR_ACQUIRED_AND_RETAINED_ONLY"
    ):
        raise ValueError("唐以前统一战争净控制裁决配置无效")
    acquisition_by_portfolio = {
        str(row["portfolio_ref"]): {
            str(item["region_id"]): item
            for item in row.get("region_adjudications") or ()
        }
        for row in acquisition_payload.get("portfolio_adjudications") or ()
    }
    portfolio_by_ref = {
        str(row["portfolio_ref"]): row
        for row in control_payload.get("portfolio_adjudications") or ()
    }
    battle_by_ref = {
        str(row["war_event_id"]): row for row in battle_payload.get("records") or ()
    }
    profile_by_key = {
        (str(row["era_id"]), str(row["region_id"])): row
        for row in control_payload.get("era_region_value_profiles") or ()
    }
    results: list[dict[str, Any]] = []
    for dynasty, portfolio_ref in PRE_TANG_CONTROL_PORTFOLIOS:
        source = portfolio_by_ref.get(portfolio_ref)
        if source is None:
            raise ValueError(f"唐以前统一链净控制校准来源缺失: {portfolio_ref}")
        if portfolio_ref not in acquisition_by_portfolio:
            raise ValueError(f"唐以前统一链战争取得裁决缺失: {portfolio_ref}")
        period_id = portfolio_period_map.get(portfolio_ref)
        if not period_id:
            raise ValueError(f"唐以前统一链缺少时代化战争区域窗口: {portfolio_ref}")
        period_region_profiles = period_profiles[period_id]
        region_adjudications = acquisition_by_portfolio[portfolio_ref]
        baseline = {
            str(row["region_id"]): float(row["control_fraction"])
            for row in source.get("baseline_snapshot") or ()
        }
        terminal = {
            str(row["region_id"]): float(row["control_fraction"])
            for row in source.get("terminal_snapshot") or ()
        }
        overrides = {
            str(row["region_id"]): row
            for row in source.get("region_value_overrides") or ()
        }
        eligible_intervals: dict[str, list[tuple[float, float]]] = defaultdict(list)
        eligible_refs: dict[str, list[str]] = defaultdict(list)
        excluded_groups: list[dict[str, Any]] = []
        for group in source.get("group_control_results") or ():
            group_ref = str(group["campaign_group_id"])
            battle = battle_by_ref.get(group_ref) or {}
            eligible = bool(battle.get("campaign_tier")) and str(
                battle.get("disposition") or ""
            ).startswith("REGISTERED")
            if not eligible:
                excluded_groups.append(
                    {
                        "campaign_group_id": group_ref,
                        "reason": "NON_BATTLE_OR_NOT_REGISTERED_PUBLIC_BATTLE",
                        "control_effects": group.get("control_effects") or [],
                    }
                )
                continue
            for effect in group.get("control_effects") or ():
                region_id = str(effect["region_id"])
                start = float(effect["pre_control_fraction"])
                end = (
                    float(effect["window_end_control_fraction"])
                    if effect.get("first_net_control_credit")
                    else min(
                        float(effect["post_control_fraction"]),
                        float(effect["window_end_control_fraction"]),
                    )
                )
                if end > start:
                    eligible_intervals[region_id].append((start, end))
                    eligible_refs[region_id].append(group_ref)
        deltas: list[dict[str, Any]] = []
        total = 0.0
        for region_id in sorted(set(baseline) | set(terminal)):
            raw_delta = max(
                0.0, terminal.get(region_id, 0.0) - baseline.get(region_id, 0.0)
            )
            auto_war_fraction = round(
                min(raw_delta, _interval_union_length(eligible_intervals.get(region_id, ()))),
                4,
            )
            region_adjudication = region_adjudications.get(region_id)
            war_fraction = round(
                float(region_adjudication["war_acquired_retained_fraction"])
                if region_adjudication
                else auto_war_fraction,
                4,
            )
            if war_fraction < 0 or war_fraction > raw_delta:
                raise ValueError(
                    f"唐以前统一链战争取得比例越界: {portfolio_ref}/{region_id}/{war_fraction}/{raw_delta}"
                )
            excluded_fraction = round(raw_delta - war_fraction, 4)
            if excluded_fraction and region_adjudication is None:
                raise ValueError(
                    f"唐以前统一链存在未裁决的非战争或未知取得: {portfolio_ref}/{region_id}/{excluded_fraction}"
                )
            name_profile = overrides.get(region_id) or profile_by_key.get(
                (str(source["value_era_id"]), region_id)
            )
            region_decision = period_region_profiles.get(region_id)
            if region_decision is None:
                if raw_delta:
                    raise ValueError(
                        f"唐以前统一链区域缺少时期化战争价值裁决: {portfolio_ref}/{period_id}/{region_id}"
                    )
                continue
            region_grade = str(region_decision["R"])
            region_value = grade_weights[region_grade]
            # Keep enough row precision so the displayed audit rows reproduce the
            # contract total after one final rounding, rather than accumulating
            # cent-level rounding drift region by region.
            weighted_value = round(region_value * war_fraction, 4)
            total += weighted_value
            if raw_delta:
                deltas.append(
                    {
                        "region_id": region_id,
                        "region_name": str((name_profile or {}).get("region_name") or region_id),
                        "baseline_control_fraction": baseline.get(region_id, 0.0),
                        "terminal_control_fraction": terminal.get(region_id, 0.0),
                        "raw_terminal_delta": round(raw_delta, 4),
                        "war_acquired_retained_fraction": war_fraction,
                        "excluded_non_war_fraction": excluded_fraction,
                        "unknown_acquisition_fraction": 0.0,
                        "acquisition_status": str(
                            (region_adjudication or {}).get("acquisition_status")
                            or "CONFIRMED_WAR_FROM_PUBLIC_CAMPAIGN_GROUPS"
                        ),
                        "acquisition_basis": str(
                            (region_adjudication or {}).get("basis")
                            or "已登记公共战役群直接取得并在统一链尾保有。"
                        ),
                        "acquisition_source_refs": list(
                            (region_adjudication or {}).get("source_refs") or ()
                        ),
                        "region_value_period_id": period_id,
                        "strategic_value_grade": str(region_decision["S"]),
                        "military_energy_grade": str(region_decision["M"]),
                        "war_region_grade": region_grade,
                        "war_region_grade_basis": str(region_decision["basis"]),
                        "region_value_weight": region_value,
                        "weighted_war_acquired_value": weighted_value,
                        "eligible_campaign_group_refs": _unique(eligible_refs.get(region_id, [])),
                    }
                )
        total = round(total, 2)
        results.append(
            {
                "dynasty": dynasty,
                "portfolio_ref": portfolio_ref,
                "status": "CALIBRATED_WAR_ACQUIRED_AND_RETAINED",
                "created_net_control_value": total,
                "horizontal_total_band": opponent_calibrations[portfolio_ref]["chain_grade"],
                "chain_grade_rule_hit": opponent_calibrations[portfolio_ref]["rule_hit"],
                "chain_grade_basis": opponent_calibrations[portfolio_ref]["grade_basis"],
                "opponent_systems": opponent_calibrations[portfolio_ref]["opponent_systems"],
                "control_subject": source.get("control_subject"),
                "window_start": source.get("window_start"),
                "window_end": source.get("window_end"),
                "source_value_era_id": source.get("value_era_id"),
                "region_value_period_id": period_id,
                "calculation_formula": "sum(period_war_region_grade_weight * war_acquired_retained_fraction)",
                "baseline_snapshot": source.get("baseline_snapshot") or [],
                "terminal_snapshot": source.get("terminal_snapshot") or [],
                "control_deltas": deltas,
                "group_control_results": source.get("group_control_results") or [],
                "excluded_non_battle_groups": excluded_groups,
                "source_basis": source.get("basis"),
                "source_configs": [
                    "config/first-item-c-territorial-control-adjudications.json",
                    "config/pre-tang-unification-war-control-adjudications.json",
                    "config/period-war-region-value-adjudications.json",
                    "config/unification-chain-opponent-calibrations.json",
                ],
                "unknown_acquisition_value": 0.0,
            }
        )
    return results


def _unify_unification_campaign_portfolios(
    pre_tang: Sequence[Mapping[str, Any]],
    post_tang: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Publish one current contract for every Qin-to-Qing unification chain."""

    portfolios: list[dict[str, Any]] = []
    for source in pre_tang:
        groups = list(source.get("group_control_results") or ())
        excluded = list(source.get("excluded_non_battle_groups") or ())
        excluded_refs = {str(row["campaign_group_id"]) for row in excluded}
        group_refs = [str(row["campaign_group_id"]) for row in groups]
        portfolios.append(
            {
                "portfolio_ref": source["portfolio_ref"],
                "dynasty": source["dynasty"],
                "chronology_scope": "PRE_TANG",
                "registration_role": "UNIFICATION_CAMPAIGN_PORTFOLIO",
                "status": source["status"],
                "scope": source.get("source_basis"),
                "window_start": source.get("window_start"),
                "window_end": source.get("window_end"),
                "campaign_group_refs": group_refs,
                "public_campaign_group_count": sum(
                    ref not in excluded_refs for ref in group_refs
                ),
                "context_or_below_threshold_count": len(excluded_refs),
                "horizontal_total_band": source["horizontal_total_band"],
                "chain_grade_rule_hit": source["chain_grade_rule_hit"],
                "chain_grade_basis": source["chain_grade_basis"],
                "opponent_systems": source.get("opponent_systems") or [],
                "created_net_control_value": source.get(
                    "created_net_control_value"
                ),
                "recovered_net_control_value": None,
                "net_control_auxiliary_note": "仅计战争直接取得并在链尾保持；数值只作辅助审计。",
                "region_value_period_id": source.get("region_value_period_id"),
                "control_audit": {
                    "calculation_formula": source.get("calculation_formula"),
                    "control_subject": source.get("control_subject"),
                    "baseline_snapshot": source.get("baseline_snapshot") or [],
                    "terminal_snapshot": source.get("terminal_snapshot") or [],
                    "control_deltas": source.get("control_deltas") or [],
                    "recovered_control_deltas": [],
                    "group_control_results": groups,
                    "excluded_non_battle_groups": excluded,
                    "unknown_acquisition_value": source.get(
                        "unknown_acquisition_value"
                    ),
                    "source_value_era_id": source.get("source_value_era_id"),
                    "source_basis": source.get("source_basis"),
                    "source_configs": source.get("source_configs") or [],
                },
                "defense_consumption": "EXCLUDED_UNIFICATION",
                "settlement_scope": "BATTLE_LEDGER_ONLY",
                "basis": source.get("source_basis"),
            }
        )
    for source in post_tang:
        portfolios.append(
            {
                "portfolio_ref": source["portfolio_ref"],
                "dynasty": source["dynasty"],
                "chronology_scope": "POST_TANG",
                "registration_role": source["registration_role"],
                "status": source["status"],
                "scope": source.get("scope"),
                "window_start": None,
                "window_end": None,
                "campaign_group_refs": source.get("campaign_group_refs") or [],
                "public_campaign_group_count": source[
                    "public_campaign_group_count"
                ],
                "context_or_below_threshold_count": source[
                    "context_or_below_threshold_count"
                ],
                "horizontal_total_band": source["horizontal_total_band"],
                "chain_grade_rule_hit": source["chain_grade_rule_hit"],
                "chain_grade_basis": source["chain_grade_basis"],
                "opponent_systems": source.get("opponent_systems") or [],
                "created_net_control_value": source.get(
                    "created_net_control_value"
                ),
                "recovered_net_control_value": source.get(
                    "recovered_net_control_value"
                ),
                "net_control_auxiliary_note": source.get(
                    "net_control_auxiliary_note"
                ),
                "region_value_period_id": source.get("region_value_period_id"),
                "control_audit": {
                    "calculation_formula": "sum(period_war_region_grade_weight * net_control_fraction)",
                    "control_subject": None,
                    "baseline_snapshot": [],
                    "terminal_snapshot": [],
                    "control_deltas": source.get("control_deltas") or [],
                    "recovered_control_deltas": source.get(
                        "recovered_control_deltas"
                    )
                    or [],
                    "group_control_results": [],
                    "excluded_non_battle_groups": [],
                    "unknown_acquisition_value": None,
                    "source_value_era_id": None,
                    "source_basis": source.get("basis"),
                    "source_configs": [
                        "config/post-tang-unification-total-adjudications.json",
                        "config/period-war-region-value-adjudications.json",
                        "config/unification-chain-opponent-calibrations.json",
                    ],
                },
                "defense_consumption": source["defense_consumption"],
                "settlement_scope": source["settlement_scope"],
                "basis": source.get("basis"),
            }
        )
    portfolios.sort(key=lambda row: str(row["portfolio_ref"]))
    if len({str(row["portfolio_ref"]) for row in portfolios}) != len(portfolios):
        raise ValueError("秦至清统一链组合ID重复")
    top_shapes = {tuple(sorted(row)) for row in portfolios}
    audit_shapes = {tuple(sorted(row["control_audit"])) for row in portfolios}
    if len(top_shapes) != 1 or len(audit_shapes) != 1:
        raise ValueError("秦至清统一链组合未使用统一JSON合同")
    return portfolios


def _stable_event_id(target_ref: str) -> str:
    return "WAR-POST-" + sha256(target_ref.encode("utf-8")).hexdigest()[:20].upper()


def _stable_person_id(actor_name: str) -> str:
    return "PERSON-POST-" + sha256(actor_name.encode("utf-8")).hexdigest()[:16].upper()


def _load_groups(workspace_root: Path) -> dict[str, list[dict[str, Any]]]:
    base = workspace_root / "docs/共享史料/唐以后编年"
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_fact_ids: set[str] = set()
    for source_name, (_, _, source_order) in SOURCE_PARTITIONS.items():
        for path in sorted((base / source_name).glob("volume-*.registry.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            for fact in payload.get("facts") or ():
                fact_id = str(fact.get("fact_id") or "")
                routes = [route for route in fact.get("routes") or () if route.get("domain") == "battle" and route.get("decision") == "HANDOFF_BATTLE_WORKFLOW"]
                if fact_id in FACT_TARGET_OVERRIDES and not routes:
                    routes = [{"target_ref": FACT_TARGET_OVERRIDES[fact_id]}]
                for route in routes:
                    target_ref = str(
                        FACT_TARGET_OVERRIDES.get(fact_id)
                        or route.get("target_ref")
                        or ""
                    )
                    if not fact_id or not target_ref:
                        raise ValueError(f"唐以后战役路由缺少fact_id/target_ref: {path}")
                    if fact_id in seen_fact_ids:
                        raise ValueError(f"唐以后战役事实重复进入路由: {fact_id}")
                    seen_fact_ids.add(fact_id)
                    groups[target_ref].append({"source_name": source_name, "source_order": source_order, "source_file": path.relative_to(workspace_root).as_posix(), "fact": dict(fact)})
    tier_payload = json.loads(
        (workspace_root / "config/post-tang-campaign-tier-adjudications.json").read_text(
            encoding="utf-8"
        )
    )
    for supplement in tier_payload.get("targeted_fact_supplements") or ():
        fact = dict(supplement.get("fact") or {})
        fact_id = str(fact.get("fact_id") or "")
        target_ref = str(supplement.get("source_target_ref") or "")
        source_name = str(supplement.get("source_name") or "")
        if (
            not fact_id
            or not target_ref
            or source_name not in SOURCE_PARTITIONS
            or fact_id in seen_fact_ids
            or not fact.get("source_refs")
            or not str(supplement.get("basis") or "").strip()
        ):
            raise ValueError(f"唐以后定点事实补充字段缺失、来源无效或fact_id重复: {supplement}")
        seen_fact_ids.add(fact_id)
        groups[target_ref].append(
            {
                "source_name": source_name,
                "source_order": SOURCE_PARTITIONS[source_name][2],
                "source_file": "config/post-tang-campaign-tier-adjudications.json#targeted_fact_supplements",
                "fact": fact,
            }
        )
    return groups


def _joined(group: Sequence[Mapping[str, Any]], key: str) -> str:
    return "；".join(str(row["fact"].get(key) or "").strip() for row in group if str(row["fact"].get(key) or "").strip())


def _canonical_source_name(
    target_ref: str, group: Sequence[Mapping[str, Any]]
) -> str:
    canonical_source = TARGET_CANONICAL_SOURCE.get(target_ref)
    return str(
        next(
            (
                row["source_name"]
                for row in group
                if row["source_name"] == canonical_source
            ),
            group[0]["source_name"],
        )
    )


def _unique(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _destination(target_ref: str, action: str, result: str) -> str:
    combined = f"{target_ref} {action} {result}"
    if any(marker in combined for marker in NON_BATTLE_MARKERS) and not any(marker in result for marker in MAJOR_RESULT_MARKERS):
        return "REDIRECT_NON_BATTLE_OUTCOME"
    if any(marker in result for marker in BATTLE_RESULT_MARKERS):
        return "CAMPAIGN_GROUP"
    if any(marker in combined for marker in UNIFICATION_MARKERS) and any(
        marker in result for marker in UNIFICATION_RESULT_MARKERS
    ):
        return "CAMPAIGN_GROUP"
    return "BELOW_PUBLIC_OUTCOME_THRESHOLD"


def _tier(result: str) -> tuple[str, str, str, str, str]:
    if any(marker in result for marker in TERMINAL_MARKERS):
        return "A", "major_stage_or_crisis", "important_region", "regional_major", "major_degradation"
    if any(marker in result for marker in MAJOR_RESULT_MARKERS):
        return "B", "important_objective", "strategic_gateway", "regional_major", "limited_attrition"
    return "C", "local_tactical", "local_point", "minor", "limited_attrition"


def _battle_result(result: str) -> tuple[str, str, str]:
    negative = any(marker in result for marker in ("战败", "不利", "失守", "陷落", "全军覆没"))
    positive = any(marker in result for marker in (*TERMINAL_MARKERS, *MAJOR_RESULT_MARKERS))
    if positive and negative:
        return "mixed", "partial", "mixed"
    if negative:
        return "defeat", "failed", "negative"
    if positive:
        return "victory", "complete", "positive"
    return "unclear", "unclear", "mixed"


def _unification_metadata(target_ref: str) -> dict[str, Any]:
    membership = UNIFICATION_REF_TO_PORTFOLIO.get(target_ref)
    if membership is None:
        return {}
    portfolio_ref, stage_order = membership
    return {
        "unification_portfolio_ref": portfolio_ref,
        "unification_stage_order": stage_order,
        "account_routing": ["UNIFICATION_ONLY"],
        "defense_consumption": "EXCLUDED_UNIFICATION",
        "settlement_scope": "BATTLE_LEDGER_ONLY",
    }


def _tier_payload(tier: str) -> tuple[str, str, str, str]:
    if tier == "A":
        return "major_stage_or_crisis", "important_region", "regional_major", "major_degradation"
    if tier == "B":
        return "important_objective", "strategic_gateway", "regional_major", "limited_attrition"
    return "local_tactical", "local_point", "minor", "limited_attrition"


def _members(group: Sequence[Mapping[str, Any]], *, tier: str, difficulty: str, result_direction: str, adjudicated_members: Sequence[Mapping[str, Any]] = ()) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    members: dict[str, dict[str, Any]] = {}
    failures: list[dict[str, Any]] = []
    replaced_source_actor_refs = {
        str(actor_ref)
        for decision in adjudicated_members
        for actor_ref in decision.get("source_actor_refs_to_replace", ())
        if str(actor_ref)
    }
    for row in group:
        fact = row["fact"]
        action = str(fact.get("action") or "")
        result = str(fact.get("observable_result") or "")
        source_refs = list(fact.get("source_refs") or ())
        actors = list(fact.get("actors") or ())
        if not actors:
            continue
        actor = actors[0]
        name = str(actor.get("source_name") or "").strip()
        person_ref = str(actor.get("person_ref") or "").strip()
        actor_action = str(actor.get("action") or "").strip()
        if not name or not person_ref or actor.get("role_status") != "resolved" or not any(marker in actor_action or marker in action for marker in COMMAND_MARKERS):
            continue
        if person_ref in replaced_source_actor_refs:
            continue
        negative = any(f"{name}{suffix}" in result for suffix in NEGATIVE_NAME_SUFFIXES)
        direction = "negative" if negative else result_direction
        if direction not in {"positive", "negative"}:
            continue
        contribution = {"capability_mode": "integrated_command", "decisive_relation": "decisive_creator" if direction == "positive" else "none", "basis": f"仅按共享层显式行动与结果建立{name}的人物下限。", "source_refs": source_refs}
        command_result = {"result_ref": f"PCR-{sha256((person_ref + str(fact['fact_id'])).encode('utf-8')).hexdigest()[:20].upper()}", "result_label": action or str(fact["fact_id"]), "result_direction": direction, "result_tier": tier, "combat_difficulty": difficulty, "stable_delivery": False, "outcome_responsibility": "actual_command_scope" if direction in {"negative", "mixed_review"} else None, "causal_fault": "UNKNOWN" if direction in {"negative", "mixed_review"} else None, "basis": f"共享事实显式列出{name}{actor_action}；只消费该事实可观察结果，不继承同群其他阶段。", "source_refs": source_refs, "military_capability_contribution": contribution}
        member = members.setdefault(person_ref, {"actor_ref": person_ref, "actor_name": name, "actor_kind": "person", "role_code": "commander_in_chief", "contribution_scope": actor_action or action, "person_command_index": {"consumption_mode": "person_result", "capability_mode": "integrated_command", "decisive_relation": contribution["decisive_relation"], "result_direction": direction, "projected_result_tier": tier, "projected_combat_difficulty": difficulty, "detail_status": "resolved_person_result", "basis": "共享层显式person_ref与行动，按单一事实结果作证据下限定档。", "source_refs": source_refs}, "person_command_result": []})
        member["person_command_result"].append(command_result)
        if negative:
            failures.append({"actor_ref": person_ref, "actor_name": name, "actor_kind": "person", "failure_domain": "command_failure", "responsibility": "primary", "failure_impact_tier": tier, "severity": 0.4 if tier in {"A", "B"} else 0.2, "basis": f"共享事实明确记载{name}亲自率军且本次结果失利。", "source_refs": source_refs})
    parent_refs = _unique([ref for row in group for ref in row["fact"].get("source_refs") or ()])
    fact_by_id = {str(row["fact"]["fact_id"]): row["fact"] for row in group}
    tier_rank = {"C": 0, "B": 1, "A": 2, "S-": 3, "S": 4, "S+": 5}
    difficulty_rank = {"D0": 0, "D1": 1, "D2": 2, "D3": 3, "D4": 4}
    for decision in adjudicated_members:
        name = str(decision.get("actor_name") or "").strip()
        basis = str(decision.get("basis") or "").strip()
        requested_mode = str(decision.get("consumption_mode") or "person_result")
        if requested_mode == "none":
            if not name or not basis:
                raise ValueError(f"唐以后无独立人物结果裁决字段无效: {decision}")
            person_ref = _stable_person_id(name)
            members[person_ref] = {
                "actor_ref": person_ref,
                "actor_name": name,
                "actor_kind": "person",
                "role_code": str(decision.get("role_code") or "principal_commander"),
                "contribution_scope": basis,
                "person_command_index": {
                    "consumption_mode": "none",
                    "command_scope": str(
                        decision.get("command_scope")
                        or "continuous_campaign_no_separate_result"
                    ),
                    "capability_mode": "none",
                    "decisive_relation": "none",
                    "result_direction": "unknown",
                    "projected_result_tier": None,
                    "projected_combat_difficulty": None,
                    "detail_status": "resolved_no_separate_person_result",
                    "basis": basis,
                    "source_refs": parent_refs,
                },
            }
            continue
        if requested_mode == "person_result_required":
            if not name or not basis:
                raise ValueError(f"唐以后待补人物裁决字段无效: {decision}")
            person_ref = _stable_person_id(name)
            members[person_ref] = {
                "actor_ref": person_ref,
                "actor_name": name,
                "actor_kind": "person",
                "role_code": str(decision.get("role_code") or "principal_commander"),
                "contribution_scope": basis,
                "person_command_index": {
                    "consumption_mode": "person_result_required",
                    "command_scope": str(
                        decision.get("command_scope")
                        or "pending_person_command_resolution"
                    ),
                    "capability_mode": "unresolved",
                    "decisive_relation": "unresolved",
                    "result_direction": "unknown",
                    "projected_result_tier": None,
                    "projected_combat_difficulty": None,
                    "detail_status": "person_result_required",
                    "basis": basis,
                    "source_refs": parent_refs,
                },
            }
            continue
        result_decisions = list(decision.get("command_results") or (decision,))
        if not name or not basis or not result_decisions:
            raise ValueError(f"唐以后人物裁决字段无效: {decision}")
        person_ref = _stable_person_id(name)
        command_results: list[dict[str, Any]] = []
        result_metadata: list[tuple[str, str, str, str, list[str]]] = []
        for result_decision in result_decisions:
            direction = str(result_decision.get("result_direction") or "")
            relation = str(result_decision.get("decisive_relation") or "")
            result_basis = str(result_decision.get("basis") or basis).strip()
            result_tier = str(result_decision.get("result_tier") or tier)
            raw_difficulty = result_decision.get("combat_difficulty", difficulty)
            result_difficulty = None if raw_difficulty is None else str(raw_difficulty)
            if direction not in {"positive", "negative", "mixed_review"} or relation not in {"decisive_creator", "decisive_successor", "co_decisive", "terminal_finisher", "stage_executor", "none"} or not result_basis:
                raise ValueError(f"唐以后人物裁决字段无效: {result_decision}")
            operational_without_difficulty = (
                str(result_decision.get("consumption_mode") or requested_mode)
                == "operational_result"
                and str(result_decision.get("capability_mode") or "")
                == "operational_design"
                and result_difficulty is None
            )
            if result_tier not in tier_rank or (
                result_difficulty not in difficulty_rank
                and not operational_without_difficulty
            ):
                raise ValueError(f"唐以后人物结果档位无效: {name}/{result_tier}/{result_difficulty}")
            operational_design_result = (
                str(result_decision.get("consumption_mode") or requested_mode)
                == "operational_result"
                and str(result_decision.get("capability_mode") or "")
                == "operational_design"
            )
            if direction == "positive" and relation == "none" and not operational_design_result:
                raise ValueError(f"唐以后正向人物裁决缺少实际贡献关系: {name}")
            if direction in {"negative", "mixed_review"} and relation != "none":
                raise ValueError(f"唐以后失败或混合人物裁决不得产生正向贡献: {name}")
            selected_fact_ids = [str(value) for value in result_decision.get("source_fact_ids") or ()]
            if selected_fact_ids:
                if len(selected_fact_ids) != len(set(selected_fact_ids)) or set(selected_fact_ids) - set(fact_by_id):
                    raise ValueError(f"唐以后人物裁决source_fact_ids无效: {name}/{selected_fact_ids}")
                selected_facts = [fact_by_id[fact_id] for fact_id in selected_fact_ids]
                decision_refs = _unique([ref for fact in selected_facts for ref in fact.get("source_refs") or ()])
            else:
                selected_facts = [row["fact"] for row in group]
                selected_fact_ids = [str(fact["fact_id"]) for fact in selected_facts]
                decision_refs = parent_refs
            additional_source_refs = [str(ref).strip() for ref in result_decision.get("additional_source_refs") or ()]
            if any(not ref for ref in additional_source_refs):
                raise ValueError(f"唐以后人物裁决additional_source_refs无效: {name}")
            decision_refs = _unique([*decision_refs, *additional_source_refs])
            result_label = str(result_decision.get("result_label") or selected_facts[-1].get("action") or selected_facts[-1]["fact_id"])
            capability_mode = str(result_decision.get("capability_mode") or {
                "decisive_creator": "integrated_command",
                "decisive_successor": "independent_direction",
                "co_decisive": "independent_direction",
                "terminal_finisher": "independent_direction",
                "stage_executor": "tactical_execution",
                "none": "integrated_command",
            }[relation])
            contribution = {"capability_mode": capability_mode, "decisive_relation": relation, "basis": result_basis, "source_refs": decision_refs}
            command_result = {"result_ref": f"PCR-{sha256((person_ref + '|'.join(selected_fact_ids) + result_label).encode('utf-8')).hexdigest()[:20].upper()}", "result_label": result_label, "result_direction": direction, "result_tier": result_tier, "combat_difficulty": result_difficulty, "stable_delivery": bool(result_decision.get("stable_delivery", False)), "outcome_responsibility": str(result_decision.get("outcome_responsibility") or "actual_command_scope") if direction in {"negative", "mixed_review"} else None, "causal_fault": str(result_decision.get("causal_fault") or "UNKNOWN") if direction in {"negative", "mixed_review"} else None, "basis": result_basis, "source_refs": decision_refs, "military_capability_contribution": contribution}
            if result_decision.get("capability_episode_ref"):
                command_result["capability_episode_ref"] = str(result_decision["capability_episode_ref"])
            command_results.append(command_result)
            result_metadata.append((direction, relation, result_tier, result_difficulty, decision_refs))
            if bool(result_decision.get("attributable_failure", direction == "negative")):
                failures.append({"actor_ref": person_ref, "actor_name": name, "actor_kind": "person", "failure_domain": "command_failure", "responsibility": "actual_command_scope", "causal_fault": str(result_decision.get("causal_fault") or "UNKNOWN"), "failure_impact_tier": result_tier, "severity": 0.4 if result_tier == "A" else 0.3 if result_tier == "B" else 0.2, "basis": result_basis, "source_refs": decision_refs})
        directions = {item[0] for item in result_metadata}
        relations = {item[1] for item in result_metadata}
        index_direction = next(iter(directions)) if len(directions) == 1 else "mixed_review"
        index_relation = next(iter(relations)) if len(relations) == 1 else "none"
        projected_tier = max((item[2] for item in result_metadata), key=tier_rank.__getitem__)
        projected_difficulties = [
            item[3] for item in result_metadata if item[3] is not None
        ]
        projected_difficulty = (
            max(projected_difficulties, key=difficulty_rank.__getitem__)
            if projected_difficulties
            else None
        )
        index_refs = _unique([ref for item in result_metadata for ref in item[4]])
        members[person_ref] = {
            "actor_ref": person_ref,
            "actor_name": name,
            "actor_kind": "person",
            "role_code": str(decision.get("role_code") or (
                "commander_in_chief"
                if index_relation in {"decisive_creator", "none"}
                else "principal_commander"
            )),
            "contribution_scope": basis,
            "person_command_index": {
                "consumption_mode": requested_mode,
                "command_scope": str(decision.get("command_scope") or (
                    "full_campaign" if index_relation in {"decisive_creator", "co_decisive"} else "scoped_stage"
                )),
                "capability_mode": str(decision.get("capability_mode") or (
                    "integrated_command"
                    if index_relation in {"decisive_creator", "none"}
                    else "independent_direction"
                    if index_relation in {"decisive_successor", "co_decisive", "terminal_finisher"}
                    else "tactical_execution"
                )),
                "decisive_relation": index_relation,
                "result_direction": index_direction,
                "projected_result_tier": projected_tier,
                "projected_combat_difficulty": projected_difficulty,
                "detail_status": "resolved_person_result",
                "basis": basis,
                "source_refs": index_refs,
            },
            "person_command_result": command_results,
        }
    return list(members.values()), failures


def _record(
    target_ref: str,
    group: Sequence[Mapping[str, Any]],
    person_adjudication: Mapping[str, Any] | None = None,
    tier_adjudication: Mapping[str, Any] | None = None,
    tier_batch_review: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    group = sorted(group, key=lambda row: (row["source_order"], row["source_file"], row["fact"]["fact_id"]))
    primary_source = _canonical_source_name(target_ref, group)
    token, dynasty, _ = SOURCE_PARTITIONS[primary_source]
    action = _joined(group, "action")
    result = _joined(group, "observable_result")
    destination = _destination(target_ref, action, result)
    route_override = str((tier_adjudication or {}).get("route_override") or "")
    if route_override:
        if route_override not in {
            "CAMPAIGN_GROUP",
            "REDIRECT_NON_BATTLE_OUTCOME",
            "BELOW_PUBLIC_OUTCOME_THRESHOLD",
        }:
            raise ValueError(f"唐以后战役去向覆核值非法: {target_ref}/{route_override}")
        destination = route_override
    source_refs = _unique([ref for row in group for ref in row["fact"].get("source_refs") or ()])
    source_files = _unique([str(row["source_file"]) for row in group])
    source_fact_ids = _unique([str(row["fact"]["fact_id"]) for row in group])
    if target_ref in FORCED_UNIFICATION_TIERS:
        destination = "CAMPAIGN_GROUP"
    base: dict[str, Any] = {"war_event_id": _stable_event_id(target_ref), "dynasty": dynasty, "dynasty_partition": token, "record_level": "campaign_group", "source_target_ref": target_ref, "candidate_destination": destination, "public_outcome_registered": destination == "CAMPAIGN_GROUP", "canonical_label": str(group[-1]["fact"].get("action") or target_ref), "period": {"start": str(group[0]["fact"].get("time_range", {}).get("start") or "unknown"), "end": str(group[-1]["fact"].get("time_range", {}).get("end") or "unknown")}, "observable_result": result or "未知（共享层未明示结果，保持未知）", "source_lineage": {"source_card_ids": source_fact_ids, "source_files": source_files, "source_revision_refs": source_refs, "lineage_basis": "唐以后已验收编年事实的battle路由；按稳定target_ref合并，跨书同target_ref只登记一次。"}, "source_refs": source_refs, "uncertainties": _unique([str(value) for row in group for value in row["fact"].get("uncertainties") or ()]), "cost_or_burden": _joined(group, "cost_or_burden") or "unknown", "members": [], "attributable_failures": [], "merged_into": None, "limitations": [], "contract_adjudication": True, "post_tang_evidence_lower_bound": True, **_unification_metadata(target_ref)}
    canonical_target = str(
        CROSS_SOURCE_MERGES.get(target_ref)
        or (tier_adjudication or {}).get("merge_into")
        or ""
    )
    if canonical_target:
        base.update({
            "public_outcome_registered": False,
            "disposition": "MERGED_CROSS_SOURCE_DUPLICATE",
            "result_direction": None,
            "campaign_tier": None,
            "result_class": None,
            "land_strategic_value": None,
            "opponent_strategic_weight": None,
            "opponent_condition": None,
            "battle_result": None,
            "objective_completion": None,
            "objective_shortfalls": [],
            "opponent_force_effect": None,
            "tier_basis": None,
            "combat_difficulty": "D_NOT_REQUIRED",
            "combat_difficulty_basis": None,
            "command_status": "NOT_REQUIRED_MERGED",
            "campaign_command_topology": None,
            "ruler_role_status": "unresolved",
            "ruler_role_basis": "跨书同一统一阶段已并入主分区记录，不重复产生人物信用。",
            "detail_expansion_status": "merged_cross_source_duplicate",
            "wc_grade": None,
            "security_grade": None,
            "merged_into": _stable_event_id(canonical_target),
            "basis": f"跨书重复观察并入{canonical_target}；本记录只保留lineage，不重复登记战果。",
        })
        return base
    if destination != "CAMPAIGN_GROUP":
        base.update({"disposition": "REDIRECTED_NON_BATTLE_OUTCOME" if destination == "REDIRECT_NON_BATTLE_OUTCOME" else "EXCLUDED_BELOW_PUBLIC_THRESHOLD", "result_direction": None, "campaign_tier": None, "result_class": None, "land_strategic_value": None, "opponent_strategic_weight": None, "opponent_condition": None, "battle_result": None, "objective_completion": None, "objective_shortfalls": [], "opponent_force_effect": None, "tier_basis": None, "combat_difficulty": "D_NOT_REQUIRED", "combat_difficulty_basis": None, "command_status": "NOT_REQUIRED", "campaign_command_topology": None, "ruler_role_status": "unresolved", "ruler_role_basis": "非公共战役成果，不进入人物或皇帝战役消费。", "detail_expansion_status": "not_required", "wc_grade": None, "security_grade": None, "basis": str((tier_adjudication or {}).get("basis") or "共享层已完成战役工作流转交，但当前结果未达到公共成果门槛或应转入非战役成果。")})
        return base
    tier, result_class, land_axis, opponent_weight, force_effect = _tier(result)
    forced_tier = FORCED_UNIFICATION_TIERS.get(target_ref)
    if forced_tier:
        tier = forced_tier
        result_class, land_axis, opponent_weight, force_effect = _tier_payload(tier)
    tier_review_source_tier = tier
    battle_result, objective_completion, direction = _battle_result(result)
    difficulty = "D2" if tier == "A" else "D1"
    if tier_adjudication:
        tier = str(tier_adjudication["campaign_tier"])
        result_class = str(tier_adjudication["result_class"])
        land_axis = str(tier_adjudication["land_strategic_value"])
        opponent_weight = str(tier_adjudication["opponent_strategic_weight"])
        force_effect = str(tier_adjudication["opponent_force_effect"])
        difficulty = str(tier_adjudication["combat_difficulty"])
        battle_result = str(tier_adjudication.get("battle_result") or battle_result)
        objective_completion = str(tier_adjudication.get("objective_completion") or objective_completion)
        direction = str(tier_adjudication.get("result_direction") or direction)
    adjudicated_members = []
    if person_adjudication:
        adjudicated_members = [
            {
                **member,
                "result_tier": member.get("result_tier") or person_adjudication.get("result_tier"),
                "combat_difficulty": member.get("combat_difficulty") or person_adjudication.get("combat_difficulty"),
            }
            for member in person_adjudication.get("members") or ()
        ]
    unknown_person_status = str(
        (person_adjudication or {}).get("status") or ""
    ).startswith("UNKNOWN_")
    defer_s_person_adjudication = tier in {"S-", "S", "S+"} and not person_adjudication
    if unknown_person_status or defer_s_person_adjudication:
        members, failures = [], []
    else:
        members, failures = _members(
            group,
            tier=tier,
            difficulty=difficulty,
            result_direction=direction,
            adjudicated_members=adjudicated_members,
        )
    unification = target_ref in UNIFICATION_REF_TO_PORTFOLIO
    person_status_basis = str((person_adjudication or {}).get("basis") or "")
    tier_basis = str((tier_adjudication or {}).get("basis") or "")
    if not tier_basis:
        tier_basis = str((tier_batch_review or {}).get("retained_a_basis") or f"证据下限：仅按已兑现结果登记{tier}；土地轴={land_axis}，对手轴={opponent_weight}，未用国号、官衔或名望升档。")
    base.update({"disposition": "REGISTERED_CONTRACT", "result_direction": direction, "campaign_tier": tier, "result_class": result_class, "land_strategic_value": land_axis, "opponent_strategic_weight": opponent_weight, "opponent_condition": str((tier_adjudication or {}).get("opponent_condition") or "unclear"), "battle_result": battle_result, "objective_completion": objective_completion, "objective_shortfalls": [] if objective_completion == "complete" else ["共享层未闭合全部战略目标，保持证据下限。"], "opponent_force_effect": force_effect, "external_hegemony_prewar_assessment": None, "external_hegemony_terminal_assessment": None, "tier_basis": tier_basis, "tier_review_source_tier": tier_review_source_tier, "tier_adjudication_status": "ADJUDICATED_EXPLICIT" if tier_adjudication else "REVIEWED_RETAINED_A" if tier_batch_review else "PENDING_S_TIER_REVIEW" if tier == "A" else "NOT_REQUIRED_BELOW_A", "combat_difficulty": difficulty, "combat_difficulty_basis": "仅按共享事实中已明示的战役闭合程度作保守下限；兵力、成本或对手状态未载者不补推。", "command_status": "PERSON_COMMAND_UNKNOWN" if unknown_person_status else "RESOLVED_EXPLICIT_ACTORS" if members else "PERSON_DETAIL_PENDING", "campaign_command_topology": "single_integrated_command" if len(members) == 1 else "command_unresolved", "ruler_role_status": "unresolved", "ruler_role_basis": person_status_basis if unknown_person_status else "未从官职或政权身份推定皇帝指挥；只保留共享层显式person_ref。", "members": members, "attributable_failures": failures, "detail_expansion_status": "complete_unknown" if unknown_person_status else "evidence_lower_bound" if not members else "resolved_explicit_actor_lower_bound", "wc_grade": None, "security_grade": None, "basis": "按唐以后编年battle路由和稳定target_ref登记；拆合只依赖共享层已给出的同目标连续链。", "account_routing": ["UNIFICATION_ONLY" if unification else "THREE_LEDGER_STANDARD"], "defense_consumption": "EXCLUDED_UNIFICATION" if unification else "ELIGIBLE_BATTLE_LEDGER_ONLY", "settlement_scope": "BATTLE_LEDGER_ONLY"})
    return base


def _split_child_record(
    parent_target_ref: str,
    group: Sequence[Mapping[str, Any]],
    decision: Mapping[str, Any],
) -> dict[str, Any]:
    group = sorted(
        group,
        key=lambda row: (row["source_order"], row["source_file"], row["fact"]["fact_id"]),
    )
    token, dynasty, _ = SOURCE_PARTITIONS[
        _canonical_source_name(parent_target_ref, group)
    ]
    child_ref = str(decision["child_ref"])
    source_refs = list(decision.get("source_refs") or ())
    tier = str(decision["campaign_tier"])
    direction = str(decision["result_direction"])
    route_override = str(decision.get("route_override") or "CAMPAIGN_GROUP")
    if route_override not in {
        "CAMPAIGN_GROUP",
        "REDIRECT_NON_BATTLE_OUTCOME",
        "BELOW_PUBLIC_OUTCOME_THRESHOLD",
    }:
        raise ValueError(f"唐以后拆分子项去向无效: {child_ref}/{route_override}")
    public_outcome_registered = route_override == "CAMPAIGN_GROUP"
    members = []
    failures = []
    for member_decision in decision.get("members") or ():
        name = str(member_decision.get("actor_name") or "").strip()
        member_direction = str(member_decision.get("result_direction") or "")
        relation = str(member_decision.get("decisive_relation") or "")
        member_tier = str(member_decision.get("result_tier") or tier)
        member_difficulty = str(member_decision.get("combat_difficulty") or decision["combat_difficulty"])
        basis = str(member_decision.get("basis") or "").strip()
        if not name or member_direction not in {"positive", "negative", "mixed_review"} or not basis:
            raise ValueError(f"唐以后拆分子项人物裁决无效: {child_ref}/{member_decision}")
        if member_direction == "positive" and relation not in {"decisive_creator", "decisive_successor", "co_decisive", "terminal_finisher", "stage_executor"}:
            raise ValueError(f"唐以后拆分子项正向贡献关系无效: {child_ref}/{name}")
        if member_direction in {"negative", "mixed_review"}:
            relation = "none"
        person_ref = _stable_person_id(name)
        result_ref = f"PCR-{sha256((person_ref + child_ref).encode('utf-8')).hexdigest()[:20].upper()}"
        capability_mode = str(
            member_decision.get("capability_mode")
            or (
                "integrated_command"
                if relation == "decisive_creator"
                else "independent_direction"
                if relation in {"decisive_successor", "co_decisive", "terminal_finisher"}
                else "tactical_execution"
            )
        )
        consumption_mode = str(
            member_decision.get("consumption_mode") or "person_result"
        )
        command_scope = str(
            member_decision.get("command_scope")
            or (
                "full_campaign"
                if relation in {"decisive_creator", "co_decisive"}
                else "scoped_stage"
            )
        )
        contribution = {"capability_mode": capability_mode, "decisive_relation": relation, "basis": basis, "source_refs": source_refs}
        command_result = {"result_ref": result_ref, "result_label": str(member_decision.get("result_label") or decision["canonical_label"]), "result_direction": member_direction, "result_tier": member_tier, "combat_difficulty": member_difficulty, "stable_delivery": True, "outcome_responsibility": str(member_decision.get("outcome_responsibility") or "actual_command_scope") if member_direction in {"negative", "mixed_review"} else None, "causal_fault": str(member_decision.get("causal_fault") or "UNKNOWN") if member_direction in {"negative", "mixed_review"} else None, "basis": basis, "source_refs": source_refs, "military_capability_contribution": contribution}
        members.append({"actor_ref": person_ref, "actor_name": name, "actor_kind": "person", "role_code": str(member_decision.get("role_code") or ("commander_in_chief" if relation in {"decisive_creator", "none"} else "principal_commander")), "contribution_scope": basis, "person_command_index": {"consumption_mode": consumption_mode, "command_scope": command_scope, "capability_mode": capability_mode, "decisive_relation": relation, "result_direction": member_direction, "projected_result_tier": member_tier, "projected_combat_difficulty": member_difficulty, "detail_status": "resolved_person_result", "basis": basis, "source_refs": source_refs}, "person_command_result": [command_result]})
        if bool(member_decision.get("attributable_failure", member_direction == "negative")):
            failures.append({"actor_ref": person_ref, "actor_name": name, "actor_kind": "person", "failure_domain": "command_failure", "responsibility": "actual_command_scope", "causal_fault": str(member_decision.get("causal_fault") or "UNKNOWN"), "failure_impact_tier": member_tier, "severity": 0.4 if member_tier == "A" else 0.3 if member_tier == "B" else 0.2, "basis": basis, "source_refs": source_refs})
    record = {
        "war_event_id": _stable_event_id(child_ref),
        "dynasty": dynasty,
        "dynasty_partition": token,
        "record_level": "campaign_group",
        "source_target_ref": child_ref,
        "split_from_source_target_ref": parent_target_ref,
        "candidate_destination": route_override,
        "public_outcome_registered": public_outcome_registered,
        "disposition": (
            "REGISTERED_CONTRACT"
            if public_outcome_registered
            else "REDIRECTED_NON_BATTLE_OUTCOME"
            if route_override == "REDIRECT_NON_BATTLE_OUTCOME"
            else "BELOW_PUBLIC_OUTCOME_THRESHOLD"
        ),
        "canonical_label": str(decision["canonical_label"]),
        "period": dict(decision["period"]),
        "observable_result": str(decision["observable_result"]),
        "result_direction": direction,
        "campaign_tier": tier,
        "result_class": str(decision["result_class"]),
        "land_strategic_value": str(decision["land_strategic_value"]),
        "opponent_strategic_weight": str(decision["opponent_strategic_weight"]),
        "opponent_condition": str(decision["opponent_condition"]),
        "battle_result": str(decision["battle_result"]),
        "objective_completion": str(decision["objective_completion"]),
        "objective_shortfalls": (
            []
            if decision["objective_completion"] == "complete"
            else ["只闭合本子方向；混合父项其他战区不传播。"]
        ),
        "opponent_force_effect": str(decision["opponent_force_effect"]),
        "tier_basis": str(decision["basis"]),
        "tier_review_source_tier": None,
        "tier_adjudication_status": "ADJUDICATED_EXPLICIT_SPLIT_CHILD",
        "combat_difficulty": str(decision["combat_difficulty"]),
        "combat_difficulty_basis": "仅按该子方向逐字锚可证的攻陷、平定或归降结果取证据下限。",
        "command_status": (
            "RESOLVED_EXPLICIT_ACTORS"
            if members
            else "PERSON_COMMAND_UNKNOWN"
            if public_outcome_registered
            else "NOT_REQUIRED_NON_PUBLIC"
        ),
        "campaign_command_topology": "single_integrated_command" if len(members) == 1 else "command_unresolved",
        "ruler_role_status": "unresolved",
        "ruler_role_basis": "混合父项未保存可归责的连续子方向指挥，不从官职推定。",
        "members": members,
        "attributable_failures": failures,
        "detail_expansion_status": "resolved_explicit_actor_lower_bound" if members else "complete_unknown",
        "source_lineage": {
            "source_card_ids": [],
            "source_files": _unique([str(row["source_file"]) for row in group]),
            "source_revision_refs": source_refs,
            "lineage_basis": "同一共享事实含多个互不连续战区；父项持有fact_id，子项只持定点逐字锚，避免事实ID重复消费。",
        },
        "source_refs": source_refs,
        "uncertainties": list(decision.get("uncertainties") or ()),
        "cost_or_burden": "unknown",
        "wc_grade": None,
        "security_grade": None,
        "merged_into": None,
        "limitations": ["不得把混合父项的总兵力、四百余处规模或其他战区结果复制到本子项。"],
        "contract_adjudication": True,
        "post_tang_evidence_lower_bound": True,
        "basis": str(decision["basis"]),
        "account_routing": ["THREE_LEDGER_STANDARD"],
        "defense_consumption": "ELIGIBLE_BATTLE_LEDGER_ONLY",
        "settlement_scope": "BATTLE_LEDGER_ONLY",
    }
    return record


def build_post_tang_battle_partitions(
    workspace_root: Path,
    pre_tang_control_calibrations: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    groups = _load_groups(workspace_root)
    portfolio_period_map, period_profiles, grade_weights = (
        _load_period_war_region_values(workspace_root)
    )
    opponent_calibrations = _load_unification_opponent_calibrations(workspace_root)
    total_payload = json.loads(
        (workspace_root / "config/post-tang-unification-total-adjudications.json").read_text(encoding="utf-8")
    )
    if total_payload.get("schema_version") != "post-tang-unification-total-adjudications-v4":
        raise ValueError("唐以后统一总链裁决schema_version无效")
    total_rows = list(total_payload.get("adjudications") or ())
    total_adjudications = {str(row.get("portfolio_ref") or ""): row for row in total_rows}
    if len(total_adjudications) != len(total_rows) or "" in total_adjudications:
        raise ValueError("唐以后统一总链裁决portfolio_ref缺失或重复")
    if set(total_adjudications) != set(POST_TANG_UNIFICATION_CHAINS):
        raise ValueError(
            "唐以后统一总链裁决覆盖不完整: "
            f"missing={sorted(set(POST_TANG_UNIFICATION_CHAINS) - set(total_adjudications))}, "
            f"extra={sorted(set(total_adjudications) - set(POST_TANG_UNIFICATION_CHAINS))}"
        )
    enriched_control_deltas: dict[str, list[dict[str, Any]]] = {}
    enriched_recovered_deltas: dict[str, list[dict[str, Any]]] = {}
    for portfolio_ref, decision in total_adjudications.items():
        if not all(str(decision.get(key) or "").strip() for key in ("net_control_auxiliary_note", "status", "basis")):
            raise ValueError(f"唐以后统一总链裁决字段不完整: {portfolio_ref}")
        deltas = list(decision.get("control_deltas") or ())
        delta_regions = [str(row.get("region_id") or "") for row in deltas]
        if len(delta_regions) != len(set(delta_regions)):
            raise ValueError(f"唐以后统一总链区域引用缺失或重复: {portfolio_ref}")
        if any(not 0 < float(row.get("net_control_fraction") or 0) <= 1 for row in deltas):
            raise ValueError(f"唐以后统一总链净控制比例无效: {portfolio_ref}")
        period_id = portfolio_period_map.get(portfolio_ref)
        if deltas and not period_id:
            raise ValueError(f"唐以后统一总链缺少时代化战争区域窗口: {portfolio_ref}")
        period_region_profiles = period_profiles.get(period_id or "", {})
        if any(region not in period_region_profiles for region in delta_regions):
            raise ValueError(f"唐以后统一总链区域未完成时期化裁决: {portfolio_ref}/{period_id}")
        enriched_control_deltas[portfolio_ref] = [
            {
                **row,
                "region_value_period_id": period_id,
                "strategic_value_grade": period_region_profiles[str(row["region_id"])]["S"],
                "military_energy_grade": period_region_profiles[str(row["region_id"])]["M"],
                "war_region_grade": period_region_profiles[str(row["region_id"])]["R"],
                "war_region_grade_basis": period_region_profiles[str(row["region_id"])]["basis"],
                "region_value_weight": grade_weights[period_region_profiles[str(row["region_id"])]["R"]],
                "weighted_war_acquired_value": round(
                    grade_weights[period_region_profiles[str(row["region_id"])]["R"]]
                    * float(row["net_control_fraction"]),
                    4,
                ),
            }
            for row in deltas
        ]
        calculated = round(sum(row["weighted_war_acquired_value"] for row in enriched_control_deltas[portfolio_ref]), 2)
        configured = decision.get("created_net_control_value")
        if configured is None:
            if deltas:
                raise ValueError(f"唐以后统一总链已有区域增量却未写净控制量: {portfolio_ref}")
        elif abs(float(configured) - calculated) > 0.001:
            raise ValueError(f"唐以后统一总链净控制量与区域公式不一致: {portfolio_ref}/{configured}/{calculated}")
        recovered_deltas = list(decision.get("recovered_control_deltas") or ())
        recovered_regions = [str(row.get("region_id") or "") for row in recovered_deltas]
        if len(recovered_regions) != len(set(recovered_regions)) or any(region not in period_region_profiles for region in recovered_regions):
            raise ValueError(f"唐以后再统一恢复控制区域引用缺失、重复或未完成时期化裁决: {portfolio_ref}")
        if any(not 0 < float(row.get("net_control_fraction") or 0) <= 1 for row in recovered_deltas):
            raise ValueError(f"唐以后再统一恢复控制比例无效: {portfolio_ref}")
        enriched_recovered_deltas[portfolio_ref] = [
            {
                **row,
                "region_value_period_id": period_id,
                "strategic_value_grade": period_region_profiles[str(row["region_id"])]["S"],
                "military_energy_grade": period_region_profiles[str(row["region_id"])]["M"],
                "war_region_grade": period_region_profiles[str(row["region_id"])]["R"],
                "war_region_grade_basis": period_region_profiles[str(row["region_id"])]["basis"],
                "region_value_weight": grade_weights[period_region_profiles[str(row["region_id"])]["R"]],
                "weighted_recovered_value": round(
                    grade_weights[period_region_profiles[str(row["region_id"])]["R"]]
                    * float(row["net_control_fraction"]),
                    4,
                ),
            }
            for row in recovered_deltas
        ]
        recovered = round(sum(row["weighted_recovered_value"] for row in enriched_recovered_deltas[portfolio_ref]), 2)
        if recovered_deltas and abs(float(decision.get("recovered_net_control_value") or -1) - recovered) > 0.001:
            raise ValueError(f"唐以后再统一恢复控制量与区域公式不一致: {portfolio_ref}")
    tier_payload = json.loads(
        (workspace_root / "config/post-tang-campaign-tier-adjudications.json").read_text(encoding="utf-8")
    )
    if tier_payload.get("schema_version") != "post-tang-campaign-tier-adjudications-v1":
        raise ValueError("唐以后战役档位裁决schema_version无效")
    difficulty_review = dict(tier_payload.get("combat_difficulty_review") or {})
    difficulty_basis_by_ref = dict(
        difficulty_review.get("combat_difficulty_basis_by_source_target_ref") or {}
    )
    if (
        difficulty_review.get("status") != "ACCEPTED_CURRENT"
        or not difficulty_basis_by_ref
        or int(difficulty_review.get("reviewed_record_count") or 0) != len(difficulty_basis_by_ref)
    ):
        raise ValueError("唐以后D3/D4战役合同复核Gate缺失或不完整")
    tier_rows = list(tier_payload.get("adjudications") or ())
    tier_adjudications = {str(row.get("source_target_ref") or ""): row for row in tier_rows}
    if len(tier_adjudications) != len(tier_rows) or "" in tier_adjudications:
        raise ValueError("唐以后战役档位裁决target_ref缺失或重复")
    if set(tier_adjudications) - set(groups):
        raise ValueError(f"唐以后战役档位裁决引用不存在: {sorted(set(tier_adjudications) - set(groups))}")
    for target_ref, decision in tier_adjudications.items():
        split_children = list(decision.get("split_children") or ())
        if split_children:
            child_refs = [str(child.get("child_ref") or "") for child in split_children]
            required_child = (
                "child_ref", "canonical_label", "period", "observable_result",
                "campaign_tier", "result_class", "land_strategic_value",
                "opponent_strategic_weight", "opponent_condition",
                "opponent_force_effect", "combat_difficulty", "result_direction",
                "battle_result", "objective_completion", "basis", "source_refs",
            )
            if (
                len(child_refs) != len(set(child_refs))
                or any(not child_ref or child_ref in groups for child_ref in child_refs)
                or any(any(not child.get(key) for key in required_child) for child in split_children)
            ):
                raise ValueError(f"唐以后混合父项拆分字段无效: {target_ref}")
            continue
        merge_into = str(decision.get("merge_into") or "")
        if merge_into:
            if (
                merge_into == target_ref
                or merge_into not in groups
                or not str(decision.get("basis") or "").strip()
            ):
                raise ValueError(f"唐以后战役合并目标无效: {target_ref}/{merge_into}")
            continue
        if decision.get("route_override"):
            if decision["route_override"] not in {
                "CAMPAIGN_GROUP",
                "REDIRECT_NON_BATTLE_OUTCOME",
                "BELOW_PUBLIC_OUTCOME_THRESHOLD",
            } or not str(decision.get("basis") or "").strip():
                raise ValueError(f"唐以后战役去向覆核字段不完整: {target_ref}")
            if decision["route_override"] != "CAMPAIGN_GROUP":
                continue
        required = ("campaign_tier", "result_class", "land_strategic_value", "opponent_strategic_weight", "opponent_condition", "opponent_force_effect", "combat_difficulty", "basis")
        if any(not str(decision.get(key) or "").strip() for key in required):
            raise ValueError(f"唐以后战役档位裁决字段不完整: {target_ref}")
        if decision["campaign_tier"] not in {"C", "B", "A", "S-", "S", "S+"}:
            raise ValueError(f"唐以后显式覆核档位非法: {target_ref}")
    difficulty_decisions: dict[str, Mapping[str, Any]] = {}
    for target_ref, decision in tier_adjudications.items():
        difficulty_decisions[target_ref] = decision
        for child in decision.get("split_children") or ():
            child_ref = str(child.get("child_ref") or "")
            if child_ref in difficulty_decisions:
                raise ValueError(f"唐以后难度复核引用重复: {child_ref}")
            difficulty_decisions[child_ref] = child
    reviewed_refs = set(difficulty_basis_by_ref)
    if reviewed_refs - set(difficulty_decisions):
        raise ValueError(
            f"唐以后难度复核引用不存在: {sorted(reviewed_refs - set(difficulty_decisions))}"
        )
    normalized_difficulty_review = [
        {
            "source_target_ref": target_ref,
            "combat_difficulty": str(difficulty_decisions[target_ref]["combat_difficulty"]),
            "basis": str(difficulty_basis_by_ref[target_ref]),
        }
        for target_ref in sorted(reviewed_refs)
    ]
    calculated_review_fingerprint = sha256(
        json.dumps(
            normalized_difficulty_review,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    if calculated_review_fingerprint != difficulty_review.get("adjudication_fingerprint"):
        raise ValueError("唐以后D3/D4战役合同复核fingerprint漂移")
    reviewed_batches = list(tier_payload.get("reviewed_batches") or ())
    batch_reviews: dict[tuple[str, str], Mapping[str, Any]] = {}
    for review in reviewed_batches:
        key = (str(review.get("dynasty_partition") or ""), str(review.get("source_tier") or ""))
        if key in batch_reviews or not all(key):
            raise ValueError("唐以后战役档位复核批次缺失或重复")
        refs = sorted(
            target_ref for target_ref, group in groups.items()
            if SOURCE_PARTITIONS[_canonical_source_name(target_ref, group)][0] == key[0]
            and (FORCED_UNIFICATION_TIERS.get(target_ref) or _tier(_joined(group, "observable_result"))[0]) == key[1]
            and (
                target_ref in FORCED_UNIFICATION_TIERS
                or _destination(target_ref, _joined(group, "action"), _joined(group, "observable_result")) == "CAMPAIGN_GROUP"
            )
        )
        if len(refs) != int(review.get("reviewed_record_count") or -1) or _digest(refs) != review.get("source_target_ref_fingerprint"):
            raise ValueError(f"唐以后战役档位复核批次输入漂移: {key}")
        batch_reviews[key] = review
    person_payload = json.loads(
        (workspace_root / "config/post-tang-battle-person-adjudications.json").read_text(encoding="utf-8")
    )
    if person_payload.get("schema_version") != "post-tang-battle-person-adjudications-v1":
        raise ValueError("唐以后人物裁决schema_version无效")
    person_coverage_gate = person_payload.get("public_outcome_person_coverage_gate") or {}
    person_rows = list(person_payload.get("adjudications") or ())
    person_adjudications = {str(row.get("source_target_ref") or ""): row for row in person_rows}
    if len(person_adjudications) != len(person_rows) or "" in person_adjudications:
        raise ValueError("唐以后人物裁决target_ref缺失或重复")
    unknown_person_targets = set(person_adjudications) - set(groups)
    if unknown_person_targets:
        raise ValueError(f"唐以后人物裁决引用不存在: {sorted(unknown_person_targets)}")
    for target_ref, decision in person_adjudications.items():
        status = str(decision.get("status") or "ADJUDICATED")
        members = list(decision.get("members") or ())
        names = [str(member.get("actor_name") or "") for member in members]
        if len(names) != len(set(names)) or any(not name for name in names):
            raise ValueError(f"唐以后人物裁决同父项姓名缺失或重复: {target_ref}")
        if status.startswith("UNKNOWN_"):
            if members or not str(decision.get("basis") or "").strip():
                raise ValueError(f"唐以后unknown人物裁决不得含成员且必须有basis: {target_ref}")
        elif not members:
            raise ValueError(f"唐以后已裁决人物记录不得为空: {target_ref}")
    missing_chain_refs = set(UNIFICATION_REF_TO_PORTFOLIO) - set(groups)
    if missing_chain_refs:
        raise ValueError(f"唐以后统一链裁决引用不存在: {sorted(missing_chain_refs)}")
    missing_merge_targets = (set(CROSS_SOURCE_MERGES) | set(CROSS_SOURCE_MERGES.values())) - set(groups)
    if missing_merge_targets:
        raise ValueError(f"唐以后跨书合并引用不存在: {sorted(missing_merge_targets)}")
    records = []
    for target_ref in sorted(groups):
        group = groups[target_ref]
        token = SOURCE_PARTITIONS[_canonical_source_name(target_ref, group)][0]
        source_tier = FORCED_UNIFICATION_TIERS.get(target_ref) or _tier(_joined(group, "observable_result"))[0]
        tier_decision = tier_adjudications.get(target_ref)
        split_children = list((tier_decision or {}).get("split_children") or ())
        parent_record = _record(
            target_ref,
            group,
            person_adjudications.get(target_ref),
            None if split_children else tier_decision,
            batch_reviews.get((token, source_tier)),
        )
        if split_children:
            parent_record.update(
                {
                    "public_outcome_registered": False,
                    "candidate_destination": "REDIRECTED_MIXED_PARENT",
                    "disposition": "REDIRECTED_MIXED_PARENT",
                    "campaign_tier": None,
                    "command_status": "NOT_REQUIRED_SPLIT_PARENT",
                    "members": [],
                    "attributable_failures": [],
                    "basis": "混合父项按战区、对手和连续指挥链拆分；父项只持共享fact_id，不登记战果。",
                    "detail_expansion_status": "split_into_independent_children",
                }
            )
        records.append(parent_record)
        records.extend(
            _split_child_record(target_ref, group, child)
            for child in split_children
        )
    records_by_target = {str(row["source_target_ref"]): row for row in records}
    if len(records_by_target) != len(records):
        raise ValueError("唐以后战役source_target_ref重复")
    missing_review_records = reviewed_refs - set(records_by_target)
    if missing_review_records:
        raise ValueError(f"唐以后难度复核记录未生成: {sorted(missing_review_records)}")
    for target_ref in reviewed_refs:
        records_by_target[target_ref]["combat_difficulty_basis"] = str(
            difficulty_basis_by_ref[target_ref]
        )
    unreviewed_high_difficulty = sorted(
        target_ref
        for target_ref, record in records_by_target.items()
        if record.get("public_outcome_registered")
        and record.get("combat_difficulty") in {"D3", "D4"}
        and target_ref not in reviewed_refs
    )
    if unreviewed_high_difficulty:
        raise ValueError(f"唐以后仍有未复核D3/D4战役: {unreviewed_high_difficulty}")
    difficulty_rank = {"D0": 0, "D1": 1, "D2": 2, "D3": 3, "D4": 4}
    for record in records:
        record_difficulty = str(record.get("combat_difficulty") or "")
        if record.get("public_outcome_registered") and record_difficulty == "D4":
            if record.get("battle_result") != "victory" or record.get("objective_completion") != "complete":
                raise ValueError(
                    f"唐以后D4未闭合胜利与完成目标: {record['source_target_ref']}"
                )
        if record_difficulty not in difficulty_rank:
            continue
        if str(record.get("source_target_ref") or "") not in reviewed_refs:
            continue
        for member in record.get("members") or ():
            for command_result in member.get("person_command_result") or ():
                person_difficulty = str(command_result.get("combat_difficulty") or "")
                if (
                    person_difficulty in difficulty_rank
                    and difficulty_rank[person_difficulty] > difficulty_rank[record_difficulty]
                ):
                    raise ValueError(
                        "唐以后人物难度超过已复核本人战役范围: "
                        f"{record['source_target_ref']}/{member.get('actor_name')}"
                    )
    if person_coverage_gate.get("enforced") is True:
        public_records = [row for row in records if row.get("public_outcome_registered")]
        command_status_counts = dict(sorted(Counter(
            str(row.get("command_status") or "") for row in public_records
        ).items()))
        expected_status_counts = person_coverage_gate.get("expected_command_status_counts") or {}
        if command_status_counts != expected_status_counts:
            raise ValueError(
                f"唐以后公共战役人物消费覆盖Gate漂移: {command_status_counts}"
            )
        if command_status_counts.get("PERSON_DETAIL_PENDING", 0):
            raise ValueError("唐以后公共战役仍有人物事实待消费")
    partitions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        partitions[str(record["dynasty_partition"])].append(record)
    checkpoints = workspace_root / "tmp/战役登记/唐以后批次"
    checkpoints.mkdir(parents=True, exist_ok=True)
    summaries: dict[str, Any] = {}
    for token, dynasty, _ in sorted(SOURCE_PARTITIONS.values(), key=lambda row: row[2]):
        batch = partitions.get(token, [])
        summary = {"task_code": f"post-tang-battle-registry-{token}-v1", "dynasty": dynasty, "candidate_count": len(batch), "public_outcome_count": sum(row["public_outcome_registered"] for row in batch), "destination_counts": dict(sorted(Counter(row["candidate_destination"] for row in batch).items())), "person_command_result_count": sum(len(row.get("members") or ()) for row in batch), "fingerprint": _digest(batch)}
        (checkpoints / f"{token}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        summaries[token] = summary
    by_target = {str(row["source_target_ref"]): row for row in records}
    portfolios = []
    for portfolio_ref, decision in POST_TANG_UNIFICATION_CHAINS.items():
        members = [by_target[target_ref] for target_ref in decision["refs"]]
        total = total_adjudications[portfolio_ref]
        portfolios.append({
            "portfolio_ref": portfolio_ref,
            "dynasty": decision["dynasty"],
            "registration_role": "UNIFICATION_CAMPAIGN_PORTFOLIO",
            "status": total["status"],
            "scope": decision["scope"],
            "campaign_group_refs": [row["war_event_id"] for row in members],
            "public_campaign_group_count": sum(bool(row["public_outcome_registered"]) for row in members),
            "context_or_below_threshold_count": sum(not bool(row["public_outcome_registered"]) for row in members),
            "created_net_control_value": total["created_net_control_value"],
            "horizontal_total_band": opponent_calibrations[portfolio_ref]["chain_grade"],
            "chain_grade_rule_hit": opponent_calibrations[portfolio_ref]["rule_hit"],
            "chain_grade_basis": opponent_calibrations[portfolio_ref]["grade_basis"],
            "opponent_systems": opponent_calibrations[portfolio_ref]["opponent_systems"],
            "net_control_auxiliary_note": total["net_control_auxiliary_note"],
            "region_value_period_id": portfolio_period_map.get(portfolio_ref),
            "control_deltas": enriched_control_deltas[portfolio_ref],
            "recovered_net_control_value": total.get("recovered_net_control_value"),
            "recovered_control_deltas": enriched_recovered_deltas[portfolio_ref],
            "defense_consumption": "EXCLUDED_UNIFICATION",
            "settlement_scope": "BATTLE_LEDGER_ONLY",
            "basis": total["basis"] + " 总链不向子战役或人物传播档位。",
        })
    all_portfolios = [*pre_tang_control_calibrations, *portfolios]
    grade_rank = {
        "H1": 0,
        "H2": 1,
        "H3": 2,
        "H4": 3,
        "H5": 4,
        "BELOW_H5": 5,
        "NOT_COMPARABLE": 6,
    }
    credited_closures = {"FULL_TERMINAL", "DECISIVE_SYSTEM_DEFEAT"}
    benchmark_records = []
    for row in all_portfolios:
        systems = list(row.get("opponent_systems") or ())
        credited_counts = Counter(
            str(system["organization_grade"])
            for system in systems
            if system["closure"] in credited_closures
        )
        benchmark_records.append(
            {
                "portfolio_ref": row["portfolio_ref"],
                "dynasty": row["dynasty"],
                "horizontal_total_band": row["horizontal_total_band"],
                "chain_grade_rule_hit": row["chain_grade_rule_hit"],
                "credited_opponent_counts": {
                    grade: credited_counts.get(grade, 0)
                    for grade in ("O5", "O4", "O3", "O2", "O1")
                },
                "top_opponents": [
                    system["opponent_label"]
                    for system in systems
                    if system["closure"] in credited_closures
                    and system["organization_grade"]
                    in ({"O5"} if credited_counts["O5"] else {"O4"})
                ],
                "created_net_control_value_auxiliary": row.get(
                    "created_net_control_value"
                ),
                "recovered_net_control_value_auxiliary": row.get(
                    "recovered_net_control_value"
                ),
            }
        )
    benchmark_records.sort(
        key=lambda row: (
            grade_rank[row["horizontal_total_band"]],
            str(row["dynasty"]),
            str(row["portfolio_ref"]),
        )
    )
    grade_groups = {
        grade: [
            row["portfolio_ref"]
            for row in benchmark_records
            if row["horizontal_total_band"] == grade
        ]
        for grade in grade_rank
        if any(row["horizontal_total_band"] == grade for row in benchmark_records)
    }
    calibration = {
        "source_config": "config/unification-chain-opponent-calibrations.json",
        "comparison_basis": "统一链主档只消费被实际击败的独立战争机器：按交战时已经兑现的统一指挥、财政补给、兵员再生、根据地纵深和持续作战能力裁O1至O5；先去重同一体系的复起和残余，再以最高对手层级、同级数量及复合终局落H1至H5。区域价值和净控制量只校验根据地支撑与战果落地，不再通过数值公式决定总档。",
        "band_rules": {
            "H1": "复合终结至少两个O5，或终结至少三个O5，或完整终结两个O5并另有O4。",
            "H2": "击败两个O5，或一个O5并完整终结至少两个O4，或完整终结至少三个O4。",
            "H3": "击败一个O5，或完整终结至少两个O4。",
            "H4": "完整终结一个O4并另有O3纵深。",
            "H5": "至少完整终结一个O3。",
        },
        "benchmark_records": benchmark_records,
        "grade_groups": grade_groups,
        "post_tang_status": "CALIBRATED_OPPONENT_WAR_SYSTEMS_WITH_EXPLICIT_UNKNOWNS",
        "assertion": "；".join(
            f"{grade}（同档不强排）：{'、'.join(refs)}"
            for grade, refs in grade_groups.items()
        ),
        "auxiliary_net_control_policy": "净控制量继续逐区保留，只证明战争取得范围和链尾兑现；不再决定H档，也不向子战役或人物传播。",
    }
    tier_review_summary = {
        "reviewed_batch_count": len(batch_reviews),
        "reviewed_record_count": sum(int(row["reviewed_record_count"]) for row in batch_reviews.values()),
        "explicit_s_tier_count": sum(
            row.get("campaign_tier") in {"S-", "S", "S+"}
            for row in tier_adjudications.values()
        ),
        "pending_a_review_count": sum(row.get("tier_adjudication_status") == "PENDING_S_TIER_REVIEW" for row in records),
        "difficulty_contract_reviewed_record_count": len(reviewed_refs),
        "difficulty_contract_review_fingerprint": calculated_review_fingerprint,
        "difficulty_contract_pending_count": 0,
    }
    return {"records": records, "partition_summaries": summaries, "source_fact_count": sum(len(group) for group in groups.values()), "candidate_count": len(records), "unification_portfolios": portfolios, "unification_horizontal_calibration": calibration, "tier_review_summary": tier_review_summary, "fingerprint": _digest(records)}


def merge_post_tang_battle_registry(payload: Mapping[str, Any], workspace_root: Path) -> dict[str, Any]:
    current = dict(payload)
    # Capture the freshly rebuilt Qin-to-Tang current value before adding the
    # post-Tang partitions.  Deliberate tier/route recalibrations must change
    # this fingerprint; physical source-directory relocation alone must not.
    qin_tang_fingerprint = str(current.get("semantic_fingerprint") or "")
    if not qin_tang_fingerprint:
        raise ValueError("秦至唐战役登记缺少构建指纹")
    pre_tang_control_calibrations = build_pre_tang_unification_control_calibrations(
        current, workspace_root
    )
    extension = build_post_tang_battle_partitions(
        workspace_root, pre_tang_control_calibrations
    )
    old_ids = {str(row["war_event_id"]) for row in current.get("records") or ()}
    post_ids = {str(row["war_event_id"]) for row in extension["records"]}
    if old_ids & post_ids:
        raise ValueError("唐以后战役ID与秦至唐重叠")
    records = [*(current.get("records") or ()), *extension["records"]]
    opponent_calibrations = _load_unification_opponent_calibrations(workspace_root)
    known_campaign_refs = {
        str(row.get("source_target_ref") or row.get("war_event_id") or "")
        for row in records
    }
    allowed_campaign_refs = {
        row["portfolio_ref"]: {
            str(group["campaign_group_id"])
            for group in row.get("group_control_results") or ()
        }
        for row in pre_tang_control_calibrations
    }
    allowed_campaign_refs.update(
        {
            portfolio_ref: set(decision["refs"])
            for portfolio_ref, decision in POST_TANG_UNIFICATION_CHAINS.items()
        }
    )
    for portfolio_ref, calibration in opponent_calibrations.items():
        for system in calibration.get("opponent_systems") or ():
            source_refs = set(system.get("source_campaign_refs") or ())
            if not source_refs <= known_campaign_refs:
                raise ValueError(
                    f"统一链对手体系引用不存在: {portfolio_ref}/"
                    f"{sorted(source_refs - known_campaign_refs)}"
                )
            if not source_refs <= allowed_campaign_refs[portfolio_ref]:
                raise ValueError(
                    f"统一链对手体系引用越出本组合: {portfolio_ref}/"
                    f"{sorted(source_refs - allowed_campaign_refs[portfolio_ref])}"
                )
    high_tier_review = json.loads(
        (workspace_root / "config/high-tier-campaign-recalibrations.json").read_text(
            encoding="utf-8"
        )
    )
    if high_tier_review.get("schema_version") != "high-tier-campaign-recalibrations-v1":
        raise ValueError("秦至清S档复核配置无效")
    records_by_ref = {
        str(row.get("source_target_ref") or row.get("war_event_id") or ""): row
        for row in records
    }
    individual_credit_policy = high_tier_review.get(
        "unification_individual_credit_policy"
    ) or {}
    required_credit_policy = {
        "compound_two_o5_same_campaign": "S+_CAP",
        "single_o5": "S_CAP",
        "single_o4": "S-_CAP",
        "single_o3": "A_CAP",
        "duplicate_system_consumption": "FORBIDDEN",
    }
    if any(
        individual_credit_policy.get(key) != value
        for key, value in required_credit_policy.items()
    ):
        raise ValueError("统一链单项对手信用规则缺失或漂移")
    opponent_systems_by_id = {
        str(system["system_id"]): system
        for calibration in opponent_calibrations.values()
        for system in calibration.get("opponent_systems") or ()
    }
    credited_system_ids: set[str] = set()
    credit_anchors = list(high_tier_review.get("credit_anchors") or ())
    for anchor in credit_anchors:
        battle_ref = str(anchor.get("battle_ref") or "")
        record = records_by_ref.get(battle_ref)
        system_ids = [str(value) for value in anchor.get("credit") or ()]
        if record is None or not system_ids or record.get("campaign_tier") != anchor.get("tier"):
            raise ValueError(f"统一链单项对手信用锚无效: {battle_ref}")
        if len(system_ids) != len(set(system_ids)) or set(system_ids) & credited_system_ids:
            raise ValueError(f"统一链对手体系被重复完整消费: {battle_ref}")
        systems = [opponent_systems_by_id.get(system_id) for system_id in system_ids]
        if any(system is None for system in systems):
            raise ValueError(f"统一链单项引用未知对手体系: {battle_ref}")
        if any(
            battle_ref not in set(system.get("source_campaign_refs") or ())
            for system in systems
        ):
            raise ValueError(f"统一链单项对手体系缺少战役引用: {battle_ref}")
        o5_count = sum(system["organization_grade"] == "O5" for system in systems)
        if anchor["tier"] == "S+" and o5_count < 2:
            raise ValueError(f"统一链S+未在同役闭合两套O5: {battle_ref}")
        if anchor["tier"] == "S" and o5_count < 1:
            raise ValueError(f"统一链S未实际交战O5: {battle_ref}")
        credited_system_ids.update(system_ids)
    ordinary_audit_payload = high_tier_review.get(
        "ordinary_high_tier_opponent_audit"
    ) or {}
    ordinary_audits = list(ordinary_audit_payload.get("adjudications") or ())
    ordinary_audit_by_ref = {
        str(row.get("battle_ref") or ""): row for row in ordinary_audits
    }
    if (
        int(ordinary_audit_payload.get("source_high_tier_count") or -1)
        != len(ordinary_audits)
        or len(ordinary_audit_by_ref) != len(ordinary_audits)
        or "" in ordinary_audit_by_ref
    ):
        raise ValueError("普通战役高档对手信用审计缺失或重复")
    tier_rank = {None: -1, "C": 0, "B": 1, "A": 2, "S-": 3, "S": 4, "S+": 5}
    grade_cap = {"O1": "B", "O2": "B", "O3": "A", "O4": "S-", "O5": "S"}
    for battle_ref, audit in ordinary_audit_by_ref.items():
        record = records_by_ref.get(battle_ref)
        final_tier = audit.get("final_tier")
        grade = str(audit.get("effective_opponent_grade") or "")
        if record is None or record.get("campaign_tier") != final_tier or grade not in grade_cap:
            raise ValueError(f"普通战役高档对手信用当前值漂移: {battle_ref}")
        if final_tier == "S+":
            if audit.get("force_credit") != "EXTERNAL_HEGEMONY_TERMINAL":
                raise ValueError(f"普通战役S+缺少外部霸权终局: {battle_ref}")
        elif tier_rank[final_tier] > tier_rank[grade_cap[grade]]:
            raise ValueError(f"普通战役档位越过对手O档上限: {battle_ref}")
    current_ordinary_high_refs = {
        str(row.get("source_target_ref") or row.get("war_event_id") or "")
        for row in records
        if row.get("public_outcome_registered")
        and row.get("campaign_tier") in {"S-", "S", "S+"}
        and "UNIFICATION_ONLY" not in set(row.get("account_routing") or ())
        and row.get("disposition") != "REGISTERED_UNIFICATION"
    }
    if not current_ordinary_high_refs <= set(ordinary_audit_by_ref):
        raise ValueError(
            f"普通战役当前高档未完成O档复核: {sorted(current_ordinary_high_refs - set(ordinary_audit_by_ref))}"
        )
    for decision in high_tier_review.get("decisions") or ():
        battle_ref = str(decision.get("battle_ref") or "")
        record = records_by_ref.get(battle_ref)
        if record is None:
            raise ValueError(f"秦至清S档复核引用不存在: {battle_ref}")
        if (
            record.get("disposition") != decision.get("final_disposition")
            or record.get("campaign_tier") != decision.get("final_tier")
        ):
            raise ValueError(f"秦至清S档复核当前值漂移: {battle_ref}")
    current_high = [
        row
        for row in records
        if row.get("public_outcome_registered")
        and row.get("campaign_tier") in {"S-", "S", "S+"}
    ]
    high_tier_counts = dict(
        sorted(Counter(str(row["campaign_tier"]) for row in current_high).items())
    )
    if high_tier_counts != high_tier_review.get("expected_current_tier_counts"):
        raise ValueError(f"秦至清S档复核计数漂移: {high_tier_counts}")
    high_tier_recalibration_summary = {
        "scope": high_tier_review["scope"],
        "policy": high_tier_review["policy"],
        "reviewed_existing_high_tier_count": high_tier_review[
            "reviewed_existing_high_tier_count"
        ],
        "current_high_tier_count": len(current_high),
        "current_tier_counts": high_tier_counts,
        "changed_decision_count": len(high_tier_review.get("decisions") or ()),
        "unification_individual_credit_policy": individual_credit_policy,
        "unification_credit_anchor_count": len(credit_anchors),
        "unification_credited_system_count": len(credited_system_ids),
        "ordinary_opponent_audit_count": len(ordinary_audits),
        "current_ordinary_high_tier_count": len(current_ordinary_high_refs),
        "retained_without_change_count": len(current_high)
        - sum(
            decision.get("final_tier") in {"S-", "S", "S+"}
            for decision in high_tier_review.get("decisions") or ()
        ),
        "structural_a_promotion_pending_count": sum(
            row.get("campaign_tier") == "A"
            and row.get("result_class")
            in {
                "independent_direction",
                "single_pole_decisive_defeat",
                "external_hegemony_decisive_defeat",
                "single_pole_or_state_terminal",
                "composite_poles_terminal",
                "unification_terminal",
                "external_hegemony_terminal",
            }
            for row in records
        ),
        "s_plus_refs": sorted(
            str(row.get("source_target_ref") or row.get("war_event_id"))
            for row in current_high
            if row.get("campaign_tier") == "S+"
        ),
        "changed_decisions": high_tier_review.get("decisions") or [],
    }
    if high_tier_recalibration_summary["structural_a_promotion_pending_count"]:
        raise ValueError("秦至清A档存在结果类型达到S硬路径但未复核的记录")
    current_high_difficulty = [
        row
        for row in records
        if row.get("public_outcome_registered")
        and row.get("combat_difficulty") in {"D3", "D4"}
    ]
    generic_difficulty_basis = {
        "现有阶段序列显示双方均有现实取胜路径，结果依赖指挥判断与组织。",
        "仅按共享事实中已明示的战役闭合程度作保守下限；兵力、成本或对手状态未载者不补推。",
        "仅按该子方向逐字锚可证的攻陷、平定或归降结果取证据下限。",
    }
    invalid_difficulty_basis_refs = sorted(
        str(row.get("source_target_ref") or row.get("war_event_id") or "")
        for row in current_high_difficulty
        if not str(row.get("combat_difficulty_basis") or "").strip()
        or str(row.get("combat_difficulty_basis")) in generic_difficulty_basis
    )
    if invalid_difficulty_basis_refs:
        raise ValueError(
            f"秦至清D3/D4仍有空白或机械难度依据: {invalid_difficulty_basis_refs}"
        )
    invalid_d4_refs = sorted(
        str(row.get("source_target_ref") or row.get("war_event_id") or "")
        for row in current_high_difficulty
        if row.get("combat_difficulty") == "D4"
        and (
            row.get("battle_result") not in {"victory", "mixed"}
            or row.get("objective_completion") != "complete"
            or row.get("result_direction") not in {"positive", "victory", "mixed"}
        )
    )
    if invalid_d4_refs:
        raise ValueError(f"秦至清D4未闭合胜利与完成目标: {invalid_d4_refs}")
    difficulty_counts = dict(
        sorted(Counter(str(row["combat_difficulty"]) for row in current_high_difficulty).items())
    )
    difficulty_review_fingerprint = _digest(
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
    )
    high_difficulty_contract_review_summary = {
        "contract_ref": "docs/证据规则/公共成果登记与人物画像规则.md#作战难度",
        "status": "ACCEPTED_CURRENT",
        "current_d3_d4_count": len(current_high_difficulty),
        "current_difficulty_counts": difficulty_counts,
        "post_tang_source_reviewed_record_count": extension["tier_review_summary"][
            "difficulty_contract_reviewed_record_count"
        ],
        "pending_count": 0,
        "fingerprint": difficulty_review_fingerprint,
    }
    unification_campaign_portfolios = _unify_unification_campaign_portfolios(
        pre_tang_control_calibrations, extension["unification_portfolios"]
    )
    current.update({"schema_version": "battle-parent-contract-registry-v4", "scope": "秦至清（唐以后九分区已登记）", "qin_tang_semantic_fingerprint": qin_tang_fingerprint, "unification_campaign_portfolios": unification_campaign_portfolios, "post_tang_source_fact_count": extension["source_fact_count"], "post_tang_candidate_count": extension["candidate_count"], "post_tang_partition_summaries": extension["partition_summaries"], "post_tang_tier_review_summary": extension["tier_review_summary"], "high_tier_recalibration_summary": high_tier_recalibration_summary, "high_difficulty_contract_review_summary": high_difficulty_contract_review_summary, "unification_horizontal_calibration": extension["unification_horizontal_calibration"], "post_tang_fingerprint": extension["fingerprint"], "records": records, "public_outcome_count": sum(bool(row.get("public_outcome_registered")) for row in records), "pending_count": sum(row.get("public_outcome_registered") and row.get("command_status") == "PERSON_DETAIL_PENDING" for row in records), "disposition_counts": dict(sorted(Counter(str(row.get("disposition")) for row in records).items())), "tier_counts": dict(sorted(Counter(str(row["campaign_tier"]) for row in records if row.get("campaign_tier")).items()))})
    current["semantic_fingerprint"] = _digest({key: value for key, value in current.items() if key != "semantic_fingerprint"})
    return current
