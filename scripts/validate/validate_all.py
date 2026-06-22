from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VALIDATION_STEPS = [
    ("validate_evidence", ROOT / "scripts" / "validate_evidence.py"),
    ("validate_canonical_data_integrity", ROOT / "scripts" / "validate_canonical_data_integrity.py"),
    ("validate_view_configs", ROOT / "scripts" / "validate_view_configs.py"),
    ("validate_chinese_view_configs", ROOT / "scripts" / "validate_chinese_view_configs.py"),
    ("validate_review_configs", ROOT / "scripts" / "validate_review_configs.py"),
    (
        "validate_i5b_cluster_adjudication_configs",
        ROOT / "scripts" / "validate" / "validate_i5b_cluster_adjudication_configs.py",
    ),
    ("validate_config_comments", ROOT / "scripts" / "validate" / "validate_config_comments.py"),
    (
        "validate_human_readable_markdown_exports",
        ROOT / "scripts" / "validate" / "validate_human_readable_markdown_exports.py",
    ),
    ("validate_config_readability", ROOT / "scripts" / "validate_config_readability.py"),
]


def run_step(name: str, script_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    for name, script_path in VALIDATION_STEPS:
        print(f"[validate_all] running {name}: {script_path}")
        result = run_step(name, script_path)
        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="", file=sys.stderr)
        if result.returncode != 0:
            print(f"[validate_all] failed at {name} with exit code {result.returncode}")
            return result.returncode
        print(f"[validate_all] passed {name}")

    print("[validate_all] all validation steps passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
