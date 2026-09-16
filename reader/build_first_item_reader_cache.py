"""Build compact per-person first-item reader sources for the browser."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_first_item_docs import DOCS, parse_people, validate

ROOT = Path(__file__).resolve().parents[1]
PEOPLE_DIR = ROOT / "reader/data/people"
OUTPUT_DIR = ROOT / "reader/data/first-item"
CONTRACT = ROOT / "docs/分项规则/第一项政权奠基与统一贡献及能力/00-规则与计分合同.md"
LABELS = {
    "A": "A统一贡献",
    "B1": "B1创业难度与效率",
    "B2": "B2组织与整合",
    "C": "C军事统帅与战争解题",
}

# Reader identity names and legacy/formal first-item headings are mostly identical.
# Keep the rare public-name alias explicit instead of weakening heading matching.
FORMAL_NAME_ALIASES = {
    "完颜晟": "完颜吴乞买",
}


def section_text(name: str, fields: dict[str, str], number: int = 1) -> str:
    lines = [f"### {number}. {name}", ""]
    lines.extend(f"- **{key}**：{value}" for key, value in fields.items())
    return "\n".join(lines).rstrip() + "\n"


def contract_excerpt() -> str:
    text = CONTRACT.read_text(encoding="utf-8")
    b2_start = text.index("### 4.1 ")
    b2_end = text.index("### 4.4 ", b2_start)
    window_start = text.index("## 7. ")
    window_end = text.index("## 8. ", window_start)
    return (
        text[b2_start:b2_end].rstrip()
        + "\n\n"
        + text[window_start:window_end].rstrip()
        + "\n\n## 8. 执行与审计\n"
    )


def applicable_people() -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for path in sorted(PEOPLE_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        record = payload.get("record") or {}
        net = record.get("net") or {}
        if net.get("first_item_status") != "APPLICABLE":
            continue
        ruler_id = record.get("ruler_id")
        name = record.get("ruler_name")
        if not ruler_id or not name:
            raise ValueError(f"Invalid first-item person shard: {path.name}")
        if any(part in ruler_id for part in ("/", "\\")):
            raise ValueError(f"Unsafe ruler_id for first-item cache: {ruler_id!r}")
        result[name] = (ruler_id, path.name)
    return result


def build_payloads() -> tuple[dict[str, str], str]:
    # This validates the full 84-person formal source set. The current composite
    # ranking intentionally uses only the subset whose first item is APPLICABLE.
    validate()
    parsed = {code: parse_people(path) for code, path in DOCS.items()}
    people = applicable_people()

    formal_names = set(parsed["A"])
    resolved: dict[str, str] = {}
    unresolved: list[str] = []
    for reader_name in people:
        formal_name = FORMAL_NAME_ALIASES.get(reader_name, reader_name)
        if formal_name not in formal_names:
            unresolved.append(reader_name)
        else:
            resolved[reader_name] = formal_name
    if unresolved:
        raise ValueError(f"Applicable first-item people missing formal source headings: {sorted(unresolved)}")

    project_groups: dict[str, list[str]] = {}
    for name, fields in parsed["A"].items():
        project = fields.get("项目总成果")
        if project:
            project_groups.setdefault(project, []).append(name)

    outputs: dict[str, str] = {}
    for reader_name, (ruler_id, _) in people.items():
        formal_name = resolved[reader_name]
        documents: dict[str, str] = {}
        a_fields = parsed["A"][formal_name]
        a_sections = [(formal_name, a_fields)]
        project = a_fields.get("项目总成果")
        if project:
            a_sections = [(partner, parsed["A"][partner]) for partner in project_groups[project]]
        documents[LABELS["A"]] = "\n".join(
            section_text(person, fields, index)
            for index, (person, fields) in enumerate(a_sections, 1)
        )
        for code in ("B1", "B2", "C"):
            documents[LABELS[code]] = section_text(formal_name, parsed[code][formal_name])
        payload = {
            "schema_version": "reader-first-item-source-v1",
            "ruler_id": ruler_id,
            "ruler_name": reader_name,
            "formal_name": formal_name,
            "documents": documents,
        }
        outputs[f"{ruler_id}.json"] = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
    return outputs, contract_excerpt()


def build(*, check: bool = False) -> None:
    outputs, contract = build_payloads()
    expected = set(outputs) | {"contract.md"}
    actual = {path.name for path in OUTPUT_DIR.iterdir()} if OUTPUT_DIR.exists() else set()
    if check:
        if actual != expected:
            raise ValueError(
                f"First-item reader cache is stale: missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
            )
        for name, content in outputs.items():
            if (OUTPUT_DIR / name).read_text(encoding="utf-8") != content:
                raise ValueError(f"First-item reader cache is stale: {name}")
        if (OUTPUT_DIR / "contract.md").read_text(encoding="utf-8") != contract:
            raise ValueError("First-item reader cache contract excerpt is stale")
        print(f"First-item reader cache current: people={len(outputs)}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for stale in OUTPUT_DIR.iterdir():
        if stale.is_file() and stale.name not in expected:
            stale.unlink()
    for name, content in outputs.items():
        (OUTPUT_DIR / name).write_text(content, encoding="utf-8", newline="\n")
    (OUTPUT_DIR / "contract.md").write_text(contract, encoding="utf-8", newline="\n")
    print(f"First-item reader cache built: people={len(outputs)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    build(check=parser.parse_args().check)
