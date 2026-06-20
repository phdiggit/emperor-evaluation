from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIEW_CONFIG_DIR = ROOT / "data" / "view_configs"


def validate_jsonl_file(path: Path) -> list[str]:
    errors: list[str] = []

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue

        line_label = f"{path}: line {line_number}"
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            errors.append(f"{line_label}: invalid JSON ({exc.msg})")
            continue

        if not isinstance(row, dict):
            errors.append(f"{line_label}: expected JSON object, got {type(row).__name__}")
            continue

    return errors


def validate() -> list[str]:
    errors: list[str] = []

    for path in sorted(VIEW_CONFIG_DIR.glob("*.jsonl")):
        errors.extend(validate_jsonl_file(path))

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(error)
        return 1

    print("View config validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
