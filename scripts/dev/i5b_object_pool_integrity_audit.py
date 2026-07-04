from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.evidence_cluster_workbench import DEFAULT_DSN_ENV, resolve_dsn
from scripts.dev.i5b_object_pool_integrity_common import (
    DEFAULT_OUTPUT,
    ObjectPoolIntegrityAuditError,
    _json_default,
    build_report,
    render_markdown,
    write_output,
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run read-only I5B object-pool integrity audit.")
    parser.add_argument("--dsn-env", default=DEFAULT_DSN_ENV)
    parser.add_argument("--dsn", help="PostgreSQL DSN; overrides --dsn-env.")
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sample-limit", type=int, default=20)
    parser.add_argument("--fail-on-issue", action="store_true")
    parser.add_argument("--fail-on-warning", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.sample_limit < 1:
        raise ObjectPoolIntegrityAuditError("--sample-limit must be >= 1")
    report = build_report(dsn=args.dsn or resolve_dsn(args.dsn_env), sample_limit=args.sample_limit)
    if args.format == "json":
        text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default) + "\n"
    else:
        text = render_markdown(report)
    write_output(args.output, text)
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "output": str(args.output) if args.output else None,
                "error_count": report["error_count"],
                "warning_count": report["warning_count"],
                "issue_count": report["issue_count"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if args.fail_on_issue and not report["ok"]:
        return 1
    if args.fail_on_warning and int(report["warning_count"] or 0):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
