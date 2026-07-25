from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4

from emperor_v4.application.discovery_source_backfill import (
    build_hanchi_policy_backfill_worklist,
    build_hanchi_policy_judge_worklist,
    build_hanchi_policy_local_source_report,
    merge_hanchi_policy_judge_results,
)


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"顶层必须是 object: {path}")
    return payload


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    encoded = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    if path.is_file() and path.read_bytes() == encoded:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(encoded)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="I5B 汉籍政策候选回源与并行 Judge 合同"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    backfill = commands.add_parser("backfill-worklist")
    backfill.add_argument("--hanchi-plan", type=Path, required=True)
    backfill.add_argument("--hanchi-result", type=Path, required=True)
    backfill.add_argument("--ruler-ref", required=True)
    backfill.add_argument("--ruler-name", required=True)
    backfill.add_argument("--output", type=Path, required=True)

    judge = commands.add_parser("judge-worklist")
    judge.add_argument("--backfill-worklist", type=Path, required=True)
    judge.add_argument("--source-report", type=Path, action="append", default=[])
    judge.add_argument("--max-concurrency", type=int, default=3)
    judge.add_argument("--output", type=Path, required=True)

    local_source = commands.add_parser("local-source-report")
    local_source.add_argument("--backfill-worklist", type=Path, required=True)
    local_source.add_argument("--local-source-index", type=Path, required=True)
    local_source.add_argument("--max-passages-per-candidate", type=int, default=2)
    local_source.add_argument("--output", type=Path, required=True)

    merge = commands.add_parser("merge")
    merge.add_argument("--judge-worklist", type=Path, required=True)
    merge.add_argument("--result", type=Path, action="append", default=[])
    merge.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "backfill-worklist":
        payload = build_hanchi_policy_backfill_worklist(
            hanchi_plan=_load(args.hanchi_plan),
            hanchi_result=_load(args.hanchi_result),
            ruler_ref=args.ruler_ref,
            ruler_name=args.ruler_name,
        )
        summary = {
            "candidate_count": payload["hanchi_policy_lineage"]["candidate_count"],
            "backfill_task_count": len(payload["tasks"]),
        }
    elif args.command == "local-source-report":
        payload = build_hanchi_policy_local_source_report(
            _load(args.backfill_worklist),
            local_source_index_path=args.local_source_index,
            max_passages_per_candidate=args.max_passages_per_candidate,
        )
        summary = {
            "candidate_count": payload["candidate_count"],
            "passage_count": payload["passage_count"],
            "gap_count": len(payload["gaps"]),
        }
    elif args.command == "judge-worklist":
        payload = build_hanchi_policy_judge_worklist(
            _load(args.backfill_worklist),
            source_reports=[_load(path) for path in args.source_report],
            max_concurrency=args.max_concurrency,
        )
        summary = {
            "candidate_count": payload["candidate_count"],
            "judge_task_count": len(payload["tasks"]),
            "automatic_gap_count": len(payload["automatic_gaps"]),
        }
    else:
        payload = merge_hanchi_policy_judge_results(
            _load(args.judge_worklist),
            [_load(path) for path in args.result],
        )
        summary = {
            "candidate_count": len(payload["candidate_reviews"]),
            "status": payload["status"],
        }
    _write(args.output, payload)
    print(json.dumps({**summary, "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
