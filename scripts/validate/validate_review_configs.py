from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REVIEW_CONFIG_DIR = ROOT / "data" / "configs" / "人工复核配置"
RETIRED_KEYWORD_CONFIG_NAMES = {
    "第五项B_检索关键词基础.json",
    "第五项B_检索关键词补丁.json",
}


def validate() -> list[str]:
    errors: list[str] = []
    for name in sorted(RETIRED_KEYWORD_CONFIG_NAMES):
        path = REVIEW_CONFIG_DIR / name
        if path.exists():
            errors.append(
                f"{path}: retired keyword config must not exist; "
                "后续检索词由 Codex / search task generator / source passage 抽取生成"
            )
    return errors


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(error)
        return 1

    print("Review keyword config validation passed; retired keyword configs are absent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
