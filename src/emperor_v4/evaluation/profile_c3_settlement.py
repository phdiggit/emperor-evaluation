from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.formal_json_store import load_json
from emperor_v4.evaluation.profile_markdown import render_profile_markdown
from emperor_v4.evaluation.profile_registry import write_profile_manifest


ROOT = Path(__file__).resolve().parents[3]
PROFILE_ROOT = ROOT / "docs/评分结算/皇帝人物画像"
SETTLEMENT = PROFILE_ROOT / "C3/24-C3人才识别配置与授权正式结算.json"
MARKDOWN = SETTLEMENT.with_suffix(".md")
AUDIT = PROFILE_ROOT / "C3/25-C3主要入口单元处置审计.json"
HIGH_REVIEW = PROFILE_ROOT / "C3/26-C3高档授权生命周期复核.json"


def _load(path: Path) -> dict[str, Any]:
    return load_json(path)


def _update_manifest() -> None:
    write_profile_manifest(("C3",))


def build(*, write: bool = False) -> dict[str, Any]:
    settlement = _load(SETTLEMENT)
    if settlement.get("authority_mode") != "FORMAL_SETTLEMENT_PATCH_SOURCE":
        raise ValueError("C3 formal settlement is not declared as the patch authority")
    if write:
        MARKDOWN.write_text(
            render_profile_markdown(settlement), encoding="utf-8", newline="\n"
        )
        _update_manifest()
    return {"settlement": settlement}


if __name__ == "__main__":
    print(json.dumps(build(write=True)["settlement"]["summary"], ensure_ascii=False, indent=2))
