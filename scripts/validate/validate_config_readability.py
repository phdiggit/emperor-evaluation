from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
USER_CONFIG_DIRS = [
    ROOT / "data" / "view_configs",
]
UNICODE_ESCAPE_PATTERN = re.compile(r"\\u([0-9a-fA-F]{4})")


def is_cjk_readability_escape(codepoint: int) -> bool:
    return (
        0x3000 <= codepoint <= 0x303F
        or 0x3400 <= codepoint <= 0x4DBF
        or 0x4E00 <= codepoint <= 0x9FFF
        or 0xF900 <= codepoint <= 0xFAFF
        or 0xFF00 <= codepoint <= 0xFFEF
    )


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        for match in UNICODE_ESCAPE_PATTERN.finditer(raw_line):
            codepoint = int(match.group(1), 16)
            if is_cjk_readability_escape(codepoint):
                errors.append(
                    f"{path}: line {line_number}: found escaped CJK unicode sequence {match.group(0)!r}; "
                    "user-editable config must use UTF-8 Chinese text directly"
                )
                break

    return errors


def validate() -> list[str]:
    errors: list[str] = []

    for config_dir in USER_CONFIG_DIRS:
        if not config_dir.exists():
            continue
        for path in sorted(config_dir.glob("*.jsonl")):
            errors.extend(validate_file(path))

    configs_dir = ROOT / "data" / "configs"
    if configs_dir.exists():
        for path in sorted(configs_dir.rglob("*.json")):
            errors.extend(validate_file(path))
        for path in sorted(configs_dir.rglob("*.jsonl")):
            errors.extend(validate_file(path))

    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(error)
        return 1

    print("Config readability validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
