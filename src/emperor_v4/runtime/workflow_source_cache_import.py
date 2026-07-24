from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from emperor_v4.runtime.workflow_source_cache import import_source_cache_snapshots


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="将已核验的固定史源快照幂等导入中央 Source Cache"
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--state-root", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = import_source_cache_snapshots(
        import_path=args.input,
        state_root=args.state_root,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
