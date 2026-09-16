"""Validate the four first-item reader source documents as one public contract."""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "docs/评分结算/净收益/第一项政权奠基与统一贡献及能力"
DOCS = {
    "A": BASE / "01-第一项A统一主链客观贡献正式结算.md",
    "B1": BASE / "02-第一项B1创业难度与战略效率正式结算.md",
    "B2": BASE / "03-第一项B2创业组织与政治整合正式结算.md",
    "C": BASE / "04-第一项C本人军事统帅与战争解题能力正式结算.md",
}

PERSON_HEADING = re.compile(r"^###\s+\d+\.\s+(.+?)\s*$", re.MULTILINE)
BULLET = re.compile(r"^-\s+\*\*(.+?)\*\*[：:]\s*(.*)$")


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


def validate() -> None:
    parsed = {code: parse_people(path) for code, path in DOCS.items()}
    expected = set(parsed["A"])
    if len(expected) != 84:
        raise ValueError(f"A: expected 84 applicable people, got {len(expected)}")
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

    shared_people = sum(len(people) for people in shared_projects.values())
    print(
        f"First-item reader sources validated: people={len(expected)}, "
        f"shared_projects={len(shared_projects)}, shared_people={shared_people}"
    )


if __name__ == "__main__":
    validate()
