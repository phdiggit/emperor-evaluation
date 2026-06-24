from __future__ import annotations

import os
from pathlib import Path
from typing import MutableMapping


ROOT = Path(__file__).resolve().parents[2]


def read_dotenv_values(path: Path = ROOT / ".env") -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = _unquote(value.strip())
        if key:
            values[key] = value
    return values


def load_dotenv(path: Path = ROOT / ".env", environ: MutableMapping[str, str] | None = None) -> None:
    if environ is None:
        environ = os.environ
    for key, value in read_dotenv_values(path).items():
        environ.setdefault(key, value)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
