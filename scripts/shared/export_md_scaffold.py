from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


@dataclass(frozen=True)
class ExportStep:
    name: str
    exporter: Callable[[], Path | tuple[Path, ...]]


def read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def escape_cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).replace("|", "\\|").replace("\n", " ")


def join_list_cell(value: object) -> str:
    if isinstance(value, list):
        return escape_cell("、".join(str(item) for item in value))
    return escape_cell(value)


def summarize_unique_values(rows: list[dict[str, object]], field: str) -> str:
    values = []
    for row in rows:
        value = row.get(field)
        if value is None:
            continue
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned and cleaned not in values:
                values.append(cleaned)
    return "；".join(values)


def require_db_tables(db_path: Path, tables: Iterable[str]) -> None:
    required_tables = list(tables)
    if not db_path.exists():
        raise FileNotFoundError(
            f"{db_path} is missing; run python scripts/build/build_db.py before DB-backed Markdown exports."
        )
    with sqlite3.connect(db_path) as connection:
        existing_tables = {
            str(row[0])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    missing_tables = [table for table in required_tables if table not in existing_tables]
    if missing_tables:
        joined = ", ".join(missing_tables)
        raise RuntimeError(
            f"{db_path} is missing required table(s): {joined}; "
            "run python scripts/build/build_db.py before DB-backed Markdown exports."
        )


def export_db_table_markdown(
    db_path: Path,
    export_path: Path,
    title: str,
    table: str,
    headers: list[str],
    order_by: str,
) -> Path:
    export_path.parent.mkdir(parents=True, exist_ok=True)
    require_db_tables(db_path, [table])

    rows = []
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = list(connection.execute(f"SELECT raw_json FROM {table} ORDER BY {order_by}"))

    lines = [
        f"# {title}",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]

    for row in rows:
        raw_json = json.loads(row["raw_json"])
        lines.append("| " + " | ".join(escape_cell(raw_json.get(header)) for header in headers) + " |")

    export_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return export_path


def iter_exported_paths(result: Path | tuple[Path, ...]) -> Iterable[Path]:
    if isinstance(result, Path):
        yield result
        return
    yield from result


def run_export_steps(steps: list[ExportStep]) -> None:
    for step in steps:
        exported = step.exporter()
        for path in iter_exported_paths(exported):
            print(f"exported {path}")
