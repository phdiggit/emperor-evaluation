"""Validate the four first-item reader source documents as one public contract."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from emperor_v4.evaluation.first_item_public_outcomes import (  # noqa: E402
    verify_first_item_public_outcomes,
)
from emperor_v4.evaluation.first_item_c_public import verify_first_item_c_public
from emperor_v4.evaluation.first_item_b1_cost_public import verify_first_item_b1_cost_public
BASE = ROOT / "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力"
DOCS = {
    "A": BASE / "01-第一项A统一主链客观贡献正式结算.md",
    "B1": BASE / "02-第一项B1创业难度与战略效率正式结算.md",
    "B2": BASE / "03-第一项B2创业组织与政治整合正式结算.md",
    "C": BASE / "04-第一项C本人军事统帅与战争解题能力正式结算.md",
}

PERSON_HEADING = re.compile(r"^###\s+\d+\.\s+(.+?)\s*$", re.MULTILINE)
BULLET = re.compile(r"^-\s+\*\*(.+?)\*\*[：:]\s*(.*)$")
BATTLE_LIST_FIELD = "统一链战役清单"
BATTLE_LIST_ITEM = re.compile(
    r"^(.+?)\s*[｜|]\s*(前线作战|战略统筹)\s*[｜|]\s*([SABCD][+−-]?)\s*[｜|]\s*(D[0-4]|[—-])$"
)
RESULT_ORDER = {
    "S+": 12, "S": 11, "S-": 10, "S−": 10,
    "A+": 9, "A": 8, "A-": 7, "A−": 7,
    "B+": 6, "B": 5, "B-": 4, "B−": 4,
    "C+": 3, "C": 2, "C-": 1, "C−": 1,
    "D": 0,
}


def parse_people(path: Path) -> dict[str, dict[str, str]]:
    text = path.read_text(encoding="utf-8")
    matches = list(PERSON_HEADING.finditer(text))
    result: dict[str, dict[str, str]] = {}
    for index, match in enumerate(matches):
        name = match.group(1).strip()
        if name in result:
            raise ValueError(f"{path.name}: duplicate person heading: {name}")
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        fields: dict[str, str] = {}
        for line in text[match.end():end].splitlines():
            bullet = BULLET.match(line)
            if not bullet:
                continue
            key = bullet.group(1).strip()
            if key in fields:
                raise ValueError(f"{path.name}: {name}: duplicate field: {key}")
            fields[key] = bullet.group(2).replace("**", "").replace("`", "").strip()
        result[name] = fields
    return result


def require(fields: dict[str, str], names: tuple[str, ...], *, doc: str, person: str) -> None:
    missing = [name for name in names if not fields.get(name)]
    if missing:
        raise ValueError(f"{doc}: {person}: missing fields: {', '.join(missing)}")


def validate_battle_list(value: str, *, person: str) -> None:
    entries = []
    for raw in value.split("；"):
        item = raw.strip().rstrip("。")
        if not item:
            continue
        match = BATTLE_LIST_ITEM.match(item)
        if not match:
            raise ValueError(f"C: {person}: invalid {BATTLE_LIST_FIELD} item: {item}")
        entries.append(match.groups())
    if not entries:
        raise ValueError(f"C: {person}: empty {BATTLE_LIST_FIELD}")
    names = [name for name, *_ in entries]
    if len(names) != len(set(names)):
        raise ValueError(f"C: {person}: duplicate {BATTLE_LIST_FIELD} battle")
    ranks = [RESULT_ORDER[grade.replace("−", "-")] for _, _, grade, _ in entries]
    if ranks != sorted(ranks, reverse=True):
        raise ValueError(f"C: {person}: {BATTLE_LIST_FIELD} must be sorted by result grade descending")


def validate() -> None:
    parsed = {code: parse_people(path) for code, path in DOCS.items()}
    expected = set(parsed["A"])
    if not expected:
        raise ValueError('A: formal applicable people are missing')
    for code, people in parsed.items():
        names = set(people)
        if names != expected:
            missing = sorted(expected - names)
            extra = sorted(names - expected)
            raise ValueError(f"{code}: person coverage differs from A: missing={missing}, extra={extra}")

    shared_projects: dict[str, list[str]] = defaultdict(list)
    for person, fields in parsed["A"].items():
        require(fields, ("结算结果", "成果内容", "计算"), doc="A", person=person)
        if fields.get("项目总成果"):
            require(fields, ("项目总成果", "本人取得/归属成果", "分账边界"), doc="A", person=person)
            calculation = fields["计算"]
            if "项目A池" not in calculation or "个人A" not in calculation:
                raise ValueError(f"A: {person}: shared project calculation must show project pool and personal allocation")
            shared_projects[fields["项目总成果"]].append(person)
        else:
            require(fields, ("取得/恢复成果",), doc="A", person=person)

    for project, people in shared_projects.items():
        if len(people) < 2:
            raise ValueError(f"A: shared project has only one participant: {people[0]} / {project[:80]}")

    for person, fields in parsed["B1"].items():
        require(fields, ("B1结算", "起点", "对手", "效率"), doc="B1", person=person)

    for person, fields in parsed["B2"].items():
        require(fields, ("B2结算", "并行执行", "异质整合"), doc="B2", person=person)
        if not (fields.get("团队能力覆盖与组织杠杆") or fields.get("能力覆盖/组织杠杆")):
            raise ValueError(f"B2: {person}: missing team-capability/organizational-leverage field")

    for person, fields in parsed["C"].items():
        require(fields, ("C结算", "责任路线", "结算依据"), doc="C", person=person)
        if fields.get(BATTLE_LIST_FIELD):
            validate_battle_list(fields[BATTLE_LIST_FIELD], person=person)

    public_report = verify_first_item_public_outcomes(ROOT)
    verify_first_item_c_public(ROOT)
    verify_first_item_b1_cost_public(ROOT)
    if public_report["record_count"] != len(expected):
        raise ValueError("第一项A公开成果字段覆盖人数与正式A来源不一致")

    shared_people = sum(len(people) for people in shared_projects.values())
    print(
        f"First-item reader sources validated: people={len(expected)}, "
        f"shared_projects={len(shared_projects)}, shared_people={shared_people}, "
        f"public_outcomes={public_report['record_count']}"
    )


if __name__ == "__main__":
    validate()
