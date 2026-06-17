from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def main() -> int:
    trigger_terms = read_jsonl(DATA_DIR / "trigger_terms.jsonl")
    search_logs = read_jsonl(DATA_DIR / "search_logs.jsonl")
    print("matrix runner placeholder")
    print(f"trigger_terms={len(trigger_terms)} search_logs={len(search_logs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
