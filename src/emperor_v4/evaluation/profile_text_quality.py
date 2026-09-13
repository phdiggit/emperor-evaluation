"""Audit reader-facing profile text fields in formal settlements without changing adjudications."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import argparse
import re
import sys

import yaml

from .formal_json_store import load_json

ROOT = Path(__file__).resolve().parents[3]
PUBLIC_FIELDS = ("typical_pattern", "counterpattern", "grade_basis", "position_basis", "limitations")

RAW_CODE_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:G[0-5](?:[-_/](?:LOW|MID|HIGH))?|MI[1-4](?:_[A-Z0-9_]+)?|"
    r"PS[0-4]|DW[0-4]|E[1-4]|FULL_GRADE|BOUNDED_PROFILE|SCORING_PARENT|"
    r"BACKGROUND_VALIDATION|AXIS_OUT_WITH_REASON|FORMAL_CURRENT|COUNTEREVIDENCE_FOUND)(?![A-Za-z0-9_])"
)
WORKFLOW_TERMS = (
    "父链", "裁档", "重裁", "本轮", "本次", "最新重裁", "原稿", "附件", "正式快照",
    "高档门", "低档门", "不转档", "消费点", "消费的是", "路由", "轴外", "跨轴",
    "上沿", "下沿", "档内", "复验", "重开", "审计",
)
KNOWN_FRAGMENT_ENDINGS = (
    "这些正证真实",
    "这些正证",
    "当前仍是",
)


@dataclass(frozen=True)
class Issue:
    severity: str
    axis: str
    ruler_id: str
    ruler_name: str
    field: str
    kind: str
    detail: str


def _norm(text: str) -> str:
    return re.sub(r"[\s；;。,.，：:（）()【】\[\]“”\"'`]+", "", text or "")


def _texts(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [x for item in value for x in _texts(item)]
    return []


def _add(issues, severity, axis, record, field, kind, detail):
    issues.append(Issue(
        severity=severity,
        axis=axis,
        ruler_id=str(record.get("ruler_id", "")),
        ruler_name=str(record.get("ruler_name", "")),
        field=field,
        kind=kind,
        detail=detail.replace("\n", " ")[:260],
    ))


def audit_record(axis: str, record: dict) -> list[Issue]:
    issues: list[Issue] = []
    field_text = {}
    for field in PUBLIC_FIELDS:
        texts = _texts(record.get(field))
        if texts:
            field_text[field] = "\n".join(texts)
        for text in texts:
            if "�" in text or "\x00" in text:
                _add(issues, "error", axis, record, field, "broken_character", text)
            if any(text.rstrip().endswith(x) for x in KNOWN_FRAGMENT_ENDINGS):
                _add(issues, "error", axis, record, field, "truncated_fragment", text)
            codes = sorted(set(RAW_CODE_RE.findall(text)))
            if codes:
                _add(issues, "warning", axis, record, field, "raw_internal_code", ", ".join(codes))
            terms = [term for term in WORKFLOW_TERMS if term in text]
            if terms:
                _add(issues, "warning", axis, record, field, "workflow_language", ", ".join(terms))

    # Field responsibilities should remain distinct even when they discuss the same evidence.
    basis = field_text.get("grade_basis", "")
    position = field_text.get("position_basis", "")
    if basis and position:
        nb, np = _norm(basis), _norm(position)
        if nb and nb == np:
            _add(issues, "error", axis, record, "grade_basis/position_basis", "exact_duplicate", basis)
        elif min(len(nb), len(np)) >= 28 and SequenceMatcher(None, nb, np).ratio() >= 0.93:
            _add(issues, "warning", axis, record, "grade_basis/position_basis", "near_duplicate", f"similarity={SequenceMatcher(None, nb, np).ratio():.2f}")

    limitations = _texts(record.get("limitations"))
    for i, limitation in enumerate(limitations):
        nl = _norm(limitation)
        if not nl:
            continue
        for field in ("typical_pattern", "counterpattern", "grade_basis", "position_basis"):
            other = field_text.get(field)
            if other and nl == _norm(other):
                _add(issues, "error", axis, record, f"limitations[{i}]", "duplicates_other_field", field)
                break

    return issues


def audit_all() -> list[Issue]:
    config = yaml.safe_load((ROOT / "config/project.yml").read_text(encoding="utf-8"))
    issues: list[Issue] = []
    for axis, spec in config["profile_assessment"]["settled_axes"].items():
        payload = load_json(ROOT / spec["json"])
        for record in payload.get("records", []):
            issues.extend(audit_record(axis, record))
    return issues


def print_report(issues: list[Issue]) -> None:
    by_kind = Counter((x.severity, x.kind) for x in issues)
    by_axis = Counter(x.axis for x in issues)
    print(f"profile-text-quality: issues={len(issues)} errors={sum(x.severity == 'error' for x in issues)} warnings={sum(x.severity == 'warning' for x in issues)}")
    if by_kind:
        print("kinds: " + ", ".join(f"{severity}/{kind}={count}" for (severity, kind), count in sorted(by_kind.items())))
    if by_axis:
        print("axes: " + ", ".join(f"{axis}={count}" for axis, count in sorted(by_axis.items())))
    for issue in issues:
        print("QUALITY|{severity}|{axis}|{ruler_name}|{ruler_id}|{field}|{kind}|{detail}".format(**issue.__dict__))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fail-on", choices=("none", "error", "warning"), default="none")
    args = parser.parse_args(argv)
    issues = audit_all()
    print_report(issues)
    if args.fail_on == "warning" and issues:
        return 1
    if args.fail_on == "error" and any(x.severity == "error" for x in issues):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
