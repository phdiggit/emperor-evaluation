from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[3]
POOL = ROOT / "config/common/canonical-ruler-pool.json"
MANUAL = ROOT / "config/profile/m4-readiness-adjudications.json"
PROFILE_ROOT = ROOT / "docs/评分结算/皇帝人物画像"
AUDIT = PROFILE_ROOT / "34-M4结算准备度与边界整改审计.json"
REPORT = PROFILE_ROOT / "35-M4整改说明与补证门禁.md"
SOURCES = {
    "FIRST_ITEM_B": ROOT / "docs/评分结算/第一项创业与政权取得能力/政治整合能力/01-第一项B政治整合能力结算.json",
    "FOURTH_ITEM_A": ROOT / "docs/评分结算/第四项文明与国家整合收益/01-第四项文明与国家整合收益正式结算.json",
    "FIFTH_ITEM_B": ROOT / "docs/评分结算/第五项统治者政治素质/02-B轴用人与授权正式结算.json",
    "FIFTH_ITEM_C": ROOT / "docs/评分结算/第五项统治者政治素质/03-C轴强制权力伦理正式结算.json",
    "PROFILE_C3": PROFILE_ROOT / "24-C3人才识别配置与授权正式结算.json",
    "PROFILE_C5": PROFILE_ROOT / "02-C5权力运用风格与克制正式结算.json",
    "PROFILE_M2": PROFILE_ROOT / "12-M2外交博弈与对外联盟能力正式结算.json",
}

GROUP_TERMS = re.compile(
    r"功臣|宗室|外戚|后党|宦官|士人|士族|世族|门阀|豪强|勋贵|军功|军镇|藩镇|禁军|"
    r"官僚|文官|武臣|旧臣|旧部|旧政权|降附|降将|地方集团|地域集团|部族|部落|八旗|"
    r"满洲|蒙古|汉军|汉人|契丹|女真|南人|北人|江南|关陇|山东|河北|河东|储位|太子|"
    r"顾命|派系|党争|朋党|新党|旧党|清流|联盟|集团|共同体|异质"
)
LIFECYCLE_TERMS = re.compile(
    r"吸收|招附|招降|归附|联合|结盟|参与|议政|任官|授官|封爵|封赏|分权|资源|身份|"
    r"承诺|守约|背约|信用|兑现|合作|协商|安置|整合|冲突|倒戈|叛乱|清洗|诛杀|株连|"
    r"退出|罢黜|收权|继承|交接|废立|储位|安全|猜忌|重组|分裂|离心"
)


def _read(path: Path) -> bytes:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"UTF-8 BOM forbidden: {path}")
    raw.decode("utf-8")
    return raw


def _load(path: Path) -> Any:
    return json.loads(_read(path).decode("utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(_read(path)).hexdigest()


def _rows(path: Path) -> list[dict[str, Any]]:
    payload = _load(path)
    return payload.get("records") or payload.get("scores") or []


def _candidate_units(entry: str, source: dict[str, Any]) -> Iterable[tuple[str, str]]:
    if entry == "FIRST_ITEM_B":
        for index, outcome in enumerate((source.get("B1") or {}).get("outcome_evidence") or [], 1):
            text = "；".join((str(outcome.get("chain") or ""), "、".join(outcome.get("actors") or []), str(source.get("basis") or "")))
            yield f"B1.outcome_evidence[{index}]", text
        return
    if entry == "FOURTH_ITEM_A":
        for index, axis in enumerate(source.get("axis_results") or [], 1):
            if axis.get("axis") == "A":
                yield f"axis_results[{index}]", "；".join(str(axis.get(key) or "") for key in ("direction", "band", "disposition", "magnitude_grade"))
        return
    if entry in {"FIFTH_ITEM_B", "FIFTH_ITEM_C"}:
        for index, trait in enumerate(source.get("traits") or [], 1):
            text = "；".join(str(trait.get(key) or "") for key in ("domain", "adjudicated_trait", "positive_basis", "counter_evidence_or_negative_basis"))
            if GROUP_TERMS.search(text):
                yield f"traits[{index}]", text
        return
    if entry == "PROFILE_C3":
        for index, parent in enumerate(source.get("parents") or [], 1):
            text = "；".join(str(parent.get(key) or "") for key in ("task_requirement", "candidate_identification", "position_configuration", "actual_authority", "delivery", "feedback", "lifecycle_narrative"))
            if GROUP_TERMS.search(text):
                yield f"parents[{index}]", text
        return
    if entry == "PROFILE_C5":
        for index, parent in enumerate(source.get("parents") or [], 1):
            text = str(parent.get("basis") or "")
            if GROUP_TERMS.search(text):
                yield f"parents[{index}]", text


def _build_report(audit: dict[str, Any]) -> str:
    counts = audit["summary"]
    lines = [
        "# M4 整改说明与补证门禁",
        "",
        "> 状态：`UNSETTLED_EVIDENCE_REVIEW`。本文不是M4正式结算，不生成档位、雷达值、画像总分或排名。JSON是机器审计入口。",
        "",
        "## 整改结论",
        "",
        "此前按个人授权和权力伦理材料统一拼接集团父链的做法已撤回。M4与M2共享联盟生命周期骨架，但对象改为国内集团；个人名臣、团队战果、处罚案件和社会整合结果都不能直接换算M4。",
        "",
        f"第一轮机械筛查覆盖 `{audit['population_count']}` 人及全部登记入口，得到 `{counts['candidate_unit_count']}` 个导航候选；其中 `{counts['substantive_candidate_unit_count']}` 个不是纯结果背景，涉及 `{counts['substantive_candidate_ruler_count']}` 人。第二轮逐人语义复核从既有入口中确认 `{counts['priority_group_candidate_count']}` 人已有优先关系线索；这只是补证次序，不是其余人物没有集团。",
        "",
        f"集团是实际统治的通用结构，184人均已建立六域强制观察矩阵，共 `{counts['mandatory_group_domain_task_count']}` 个拓扑任务，不允许出现“无集团适用”记录。当前 `{counts['registered_input_joint_signal_gap_ruler_count']}` 人只是在本地规范入口中未观察到集团与生命周期的同条信号，必须回到统治窗口重建，不能据此判无事例。正式写入数为 `0`，实际变档数为 `0`。",
        "",
        "## 与相邻轴的硬边界",
        "",
        "- M2：外部主权行为者、条约、战争与对外交换；M4：国内集团的身份吸收、利益配置、政治信用和退出。",
        "- C3：识别和配置具体个人；只有该人代表或控制集团并改变集团均衡时，相关切片才可进入M4。",
        "- C5：强制权力边界与伦理；只有处置改变整个集团安全预期或合作选择时，相关切片才可进入M4。",
        "- 第一项B与第四项A：只复验背景和结果，不提供M4档位。",
        "",
        "## 正式结算前必须补齐",
        "",
        "每条评分父链必须同时闭合集团身份、利益与谈判资源、加入条件、地位资源配置、可信承诺、合作兑现、反馈冲突、本人重组选择、退出或交接结果、反例和本地来源。高档还须跨集团或阶段复验。缺任一环节只能保留缺口，不能默认G3，也不能从其他轴继承方向或档位。",
        "",
        "每位人物不论既有入口是否命中，都必须检查中枢官僚、军事强制、宗室继承、地域与被征服精英、资源社会中介、宫廷信息接口六类集团。某一类别确实不适用时也须给出与实际权力窗口相符的理由，不能用关键词未命中代替。",
        "",
        "## 优先补证队列",
        "",
        "| 人物 | 候选集团生命周期 | 当前处置 |",
        "|---|---|---|",
    ]
    for row in audit["priority_group_candidates"]:
        lines.append(f"| {row['ruler_name']} | {row['candidate']} | `GROUP_LIFECYCLE_SOURCE_REVIEW_REQUIRED` |")
    lines.extend([
        "",
        "## 发布状态",
        "",
        "`config/project.yml`继续声明七轴正式结算，并把M4登记在`unsettled_axes`。只有本审计列出的全部发布门关闭后，才允许新增M4结算文件及第八轴入口。",
        "",
    ])
    return "\n".join(lines)


def build(*, write: bool = False) -> dict[str, Any]:
    pool = [row for row in _load(POOL)["records"] if row["pool_status"] == "INCLUDED"]
    manual = _load(MANUAL)
    priority = {row["ruler_id"]: row["candidate"] for row in manual["priority_group_candidates"]}
    source_rows = {code: {row["ruler_id"]: row for row in _rows(path)} for code, path in SOURCES.items()}
    records: list[dict[str, Any]] = []
    entry_counts: Counter[str] = Counter()
    substantive_count = 0
    substantive_rulers = 0
    no_joint_signal = 0
    for ruler in pool:
        candidates = []
        for entry in SOURCES:
            source = source_rows[entry].get(ruler["ruler_id"])
            if source is None or entry == "PROFILE_M2":
                continue
            for field_path, text in _candidate_units(entry, source):
                background = entry in {"FIRST_ITEM_B", "FOURTH_ITEM_A"}
                joint = bool(GROUP_TERMS.search(text) and LIFECYCLE_TERMS.search(text))
                candidates.append({"entry": entry, "field_path": field_path, "background_only": background, "group_and_lifecycle_signal": joint})
                entry_counts[entry] += 1
                if not background:
                    substantive_count += 1
        substantive = [row for row in candidates if not row["background_only"]]
        if substantive:
            substantive_rulers += 1
        joint_substantive = sum(row["group_and_lifecycle_signal"] and not row["background_only"] for row in candidates)
        if not joint_substantive:
            no_joint_signal += 1
        status = "GROUP_LIFECYCLE_SOURCE_REVIEW_REQUIRED" if ruler["ruler_id"] in priority else ("TOPOLOGY_RECONSTRUCTION_AND_CROSS_AXIS_REVIEW_REQUIRED" if substantive else "TOPOLOGY_RECONSTRUCTION_REQUIRED")
        topology_tasks = [{
            "domain_code": domain["domain_code"],
            "domain_name": domain["domain_name"],
            "review_status": "RECONSTRUCTION_REQUIRED",
            "applicability": "MUST_DETERMINE_FROM_ACTUAL_POWER_WINDOW",
        } for domain in manual["mandatory_group_domains"]]
        records.append({
            "task_code": f"PROFILE-M4-READINESS-{ruler['ruler_id']}",
            "ruler_id": ruler["ruler_id"],
            "ruler_name": ruler["ruler_name"],
            "actual_power_window": ruler["actual_power_window"],
            "candidate_unit_count": len(candidates),
            "substantive_candidate_unit_count": len(substantive),
            "group_and_lifecycle_candidate_count": joint_substantive,
            "group_topology_tasks": topology_tasks,
            "semantic_disposition": status,
            "priority_candidate": priority.get(ruler["ruler_id"]),
            "formal_grade": None,
        })
    priority_rows = [{"ruler_id": row["ruler_id"], "ruler_name": next(item["ruler_name"] for item in pool if item["ruler_id"] == row["ruler_id"]), "candidate": row["candidate"]} for row in manual["priority_group_candidates"]]
    audit = {
        "schema_version": "profile-m4-readiness-audit-v1",
        "canonical_status": "UNSETTLED_EVIDENCE_REVIEW",
        "axis_code": "M4",
        "construct": manual["construct"],
        "population_count": len(records),
        "formal_profile_write": False,
        "profile_total_enabled": False,
        "profile_ranking_enabled": False,
        "database_write": False,
        "canonical_pool_sha256": _sha(POOL),
        "manual_adjudication_sha256": _sha(MANUAL),
        "source_sha256": {code: _sha(path) for code, path in SOURCES.items()},
        "two_pass_review": {"mechanical_screen_count": len(records), "semantic_review_count": len(records), "actual_grade_change_count": 0},
        "summary": {
            "candidate_unit_count": sum(row["candidate_unit_count"] for row in records),
            "substantive_candidate_unit_count": substantive_count,
            "substantive_candidate_ruler_count": substantive_rulers,
            "priority_group_candidate_count": len(priority_rows),
            "mandatory_topology_ruler_count": len(records),
            "mandatory_group_domain_task_count": sum(len(row["group_topology_tasks"]) for row in records),
            "ruler_with_zero_group_obligation_count": sum(not row["group_topology_tasks"] for row in records),
            "registered_input_joint_signal_gap_ruler_count": no_joint_signal,
            "formal_record_count": 0,
        },
        "entry_candidate_counts": dict(sorted(entry_counts.items())),
        "required_parent_fields": manual["required_parent_fields"],
        "mandatory_group_domains": manual["mandatory_group_domains"],
        "publication_gates": manual["publication_gates"],
        "routing_rules": manual["routing_rules"],
        "priority_group_candidates": priority_rows,
        "records": records,
        "conclusion": manual["review_conclusion"],
    }
    report = _build_report(audit)
    if write:
        AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        REPORT.write_text(report, encoding="utf-8", newline="\n")
    return {"audit": audit, "report": report}
