from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from validate.validate_project_config import validate as validate_project_config  # noqa: E402


def validate() -> list[str]:
    return validate_project_config()


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(error)
        return 1

    print("I5B project config entry validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
