from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build.i5b_item_result_calculator import (  # noqa: E402
    DEFAULT_CLUSTER_FORMULA,
    DEFAULT_FORMULA_CODE,
    DEFAULT_ITEM_CODE,
    fetch_item_result_calc_detail_rows,
)
from scripts.dev.evidence_cluster_workbench import (  # noqa: E402
    EvidenceClusterWorkbenchError,
    fetch_cluster_calc_detail_rows,
    resolve_dsn,
)
from scripts.dev.i5b_calc_logs import read_jsonl  # noqa: E402


DEFAULT_PROFILE = ROOT / "data" / "query_profile_batches" / "i5b_layered_retrieval_profiles_20260630.jsonl"
TALENT_RULE_CODE = "talent_discovery"
TALENT_PREFIX = "POS-TALENT-RECOGNITION"


class I5BTalentDiscoveryAuditError(ValueError):
    pass


def strip_note(value: str) -> str:
    value = re.sub(r"[（(].*?[）)]", "", value)
    return value.strip().strip("；;，,。")


def split_expected_names(value: str) -> tuple[str, ...]:
    if ":" in value:
        value = value.split(":", 1)[1]
    names: list[str] = []
    for part in re.split(r"\s*/\s*|、|，|,", value):
        name = strip_note(part)
        if not name:
            continue
        if any(token in name for token in ("需回源", "待回源", "相邻项", "切分")):
            continue
        names.append(name)
    return tuple(dict.fromkeys(names))


def expected_talent_names(profile: dict[str, Any]) -> tuple[str, ...]:
    outcomes = profile.get("expected_lane_outcomes")
    if not isinstance(outcomes, list):
        return ()
    expected: list[str] = []
    for item in outcomes:
        if not isinstance(item, str):
            continue
        if item.strip().startswith(TALENT_PREFIX):
            expected.extend(split_expected_names(item))
    return tuple(dict.fromkeys(expected))


def load_query_profiles(path: Path) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(path):
        person = row.get("person")
        if isinstance(person, str) and person.strip():
            profiles[person] = row
    return profiles


def parse_accepted_missing(values: tuple[str, ...]) -> frozenset[tuple[str, str]]:
    accepted: set[tuple[str, str]] = set()
    for value in values:
        if ":" in value:
            emperor, names_text = value.split(":", 1)
        elif "：" in value:
            emperor, names_text = value.split("：", 1)
        else:
            raise I5BTalentDiscoveryAuditError(f"accepted missing must be EMPEROR:NAME, got: {value}")
        emperor = emperor.strip()
        names = split_expected_names(names_text)
        if not emperor or not names:
            raise I5BTalentDiscoveryAuditError(f"accepted missing must include emperor and name: {value}")
        for name in names:
            accepted.add((emperor, name))
    return frozenset(accepted)


def current_talent_names(cluster_row: dict[str, Any] | None) -> tuple[str, ...]:
    if cluster_row is None:
        return ()
    detail = cluster_row.get("calc_detail")
    if not isinstance(detail, dict):
        return ()
    materials = detail.get("materials")
    if not isinstance(materials, list):
        return ()
    names: list[str] = []
    for material in materials:
        if not isinstance(material, dict):
            continue
        if material.get("side") != "positive":
            continue
        name = material.get("obj_name") or material.get("object_name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return tuple(dict.fromkeys(names))


def default_emperors(
    *,
    dsn: str,
    item_code: str,
    cluster_formula: str,
    result_formula: str,
) -> tuple[str, ...]:
    rows = fetch_item_result_calc_detail_rows(
        dsn=dsn,
        item_code=item_code,
        cluster_formula=cluster_formula,
        formula_code=result_formula,
    )
    return tuple(rows)


def build_audit_report(
    *,
    profile_path: Path = DEFAULT_PROFILE,
    dsn: str | None = None,
    item_code: str = DEFAULT_ITEM_CODE,
    cluster_formula: str = DEFAULT_CLUSTER_FORMULA,
    result_formula: str = DEFAULT_FORMULA_CODE,
    emperors: tuple[str, ...] = (),
    accepted_missing: frozenset[tuple[str, str]] = frozenset(),
    cluster_rows: dict[tuple[str, str], dict[str, Any]] | None = None,
    result_rows: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    profiles = load_query_profiles(profile_path)
    if result_rows is None or cluster_rows is None:
        if dsn is None:
            raise I5BTalentDiscoveryAuditError("dsn is required when rows are not supplied")
        result_rows = fetch_item_result_calc_detail_rows(
            dsn=dsn,
            item_code=item_code,
            cluster_formula=cluster_formula,
            formula_code=result_formula,
            emperors=emperors,
        )
        targets = emperors or tuple(result_rows)
        cluster_rows = fetch_cluster_calc_detail_rows(
            dsn=dsn,
            item_code=item_code,
            formula_code=cluster_formula,
            emperors=targets,
            rule_codes=(TALENT_RULE_CODE,),
        )
    else:
        targets = emperors or tuple(result_rows)
    if not targets:
        raise I5BTalentDiscoveryAuditError("no emperors found; pass --emperor or check result detail table")

    rows: list[dict[str, Any]] = []
    for emperor in targets:
        profile = profiles.get(emperor)
        expected = expected_talent_names(profile or {})
        current = current_talent_names(cluster_rows.get((emperor, TALENT_RULE_CODE)))
        raw_missing = tuple(name for name in expected if name not in current)
        accepted = tuple(name for name in raw_missing if (emperor, name) in accepted_missing)
        missing = tuple(name for name in raw_missing if (emperor, name) not in accepted_missing)
        extra = tuple(name for name in current if name not in expected)
        rows.append(
            {
                "emperor": emperor,
                "query_profile_id": (profile or {}).get("query_profile_id"),
                "expected": list(expected),
                "current": list(current),
                "missing": list(missing),
                "accepted_missing": list(accepted),
                "extra": list(extra),
                "expected_count": len(expected),
                "current_count": len(current),
                "ok": not missing,
            }
        )

    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "profile_path": str(profile_path),
        "source": "postgres",
        "item_code": item_code,
        "cluster_formula": cluster_formula,
        "result_formula": result_formula,
        "rule_code": TALENT_RULE_CODE,
        "ok": all(row["ok"] for row in rows),
        "rows": rows,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# I5B 发现人才覆盖审计",
        "",
        f"- cluster_formula: `{report['cluster_formula']}`",
        f"- result_formula: `{report['result_formula']}`",
        f"- rule_code: `{report['rule_code']}`",
        f"- ok: `{report['ok']}`",
        "",
        "| 皇帝 | 检索包预期 | 当前入簇 | 缺口 | 审定不入 | 额外入簇 |",
        "|---|---:|---:|---|---|---|",
    ]
    for row in report["rows"]:
        expected = "、".join(row["expected"]) or "-"
        current = "、".join(row["current"]) or "-"
        missing = "、".join(row["missing"]) or "-"
        accepted = "、".join(row.get("accepted_missing", [])) or "-"
        extra = "、".join(row["extra"]) or "-"
        lines.append(
            f"| {row['emperor']} | {row['expected_count']}：{expected} | {row['current_count']}：{current} | {missing} | {accepted} | {extra} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def write_report(path: Path, report: dict[str, Any], *, output_format: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "json":
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return
    if output_format == "markdown":
        path.write_text(render_markdown(report), encoding="utf-8")
        return
    raise I5BTalentDiscoveryAuditError(f"unknown output format: {output_format}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit I5B talent_discovery coverage against query profile expectations.")
    parser.add_argument("--dsn-env", default="EMPEROR_EVAL_PG_DSN", help="Environment variable name for PostgreSQL DSN.")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE, help="Query profile JSONL path.")
    parser.add_argument("--item-code", default=DEFAULT_ITEM_CODE, help="Evaluation item code.")
    parser.add_argument("--cluster-formula", default=DEFAULT_CLUSTER_FORMULA, help="Evidence cluster formula_code.")
    parser.add_argument("--result-formula", default=DEFAULT_FORMULA_CODE, help="Item result formula_code.")
    parser.add_argument("--emperor", action="append", default=None, help="Optional emperor filter; repeatable.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown", help="Output format.")
    parser.add_argument("--output", type=Path, default=None, help="Optional report path; stdout if omitted.")
    parser.add_argument(
        "--accepted-missing",
        action="append",
        default=None,
        metavar="EMPEROR:NAME",
        help="Reviewed expected talent that current sources do not support for talent_discovery; repeatable.",
    )
    parser.add_argument("--fail-on-gap", action="store_true", help="Exit non-zero when any expected talent is missing.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = build_audit_report(
            profile_path=args.profile,
            dsn=resolve_dsn(args.dsn_env),
            item_code=args.item_code,
            cluster_formula=args.cluster_formula,
            result_formula=args.result_formula,
            emperors=tuple(args.emperor or ()),
            accepted_missing=parse_accepted_missing(tuple(args.accepted_missing or ())),
        )
    except (EvidenceClusterWorkbenchError, I5BTalentDiscoveryAuditError) as exc:
        parser.error(str(exc))

    if args.output:
        write_report(args.output, report, output_format=args.format)
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "format": args.format,
                    "ok": report["ok"],
                    "gap_count": sum(len(row["missing"]) for row in report["rows"]),
                    "accepted_gap_count": sum(len(row["accepted_missing"]) for row in report["rows"]),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    elif args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(render_markdown(report), end="")
    if args.fail_on_gap and not report["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
