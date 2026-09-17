from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from emperor_v4.evaluation.formal_json_store import load_json, load_ruler_polities, write_json
from emperor_v4.evaluation.second_item_b1_adjudication import B1_PATH, _iter_profiles, _score_signature


FORBIDDEN = re.compile(
    r"(?:observed_or_repeated|sustained_or_systemic|not_restored|not_closed|"
    r"absorbed_same_lifecycle|context_only|balanced_mixed_lifecycle|按现合同|生命周期)",
    flags=re.I,
)


def _polish(value: object) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    replacements = (
        (r"\bobserved_or_repeated\b", "已有实际运行"),
        (r"\bsustained_or_systemic\b", "持续或系统运行"),
        (r"\bnot_restored\b", "未恢复"),
        (r"\bnot_closed\b", "运行证据尚未完整"),
        (r"\breversed\b", "后续逆转"),
        (r"正负向与混合生命周期按现合同抵扣", "当前结算已合并处理正负作用，避免重复计算"),
        (r"正负向与混合生命周期", "正负作用并存的运行过程"),
        (r"按现合同抵扣", "在当前结算中合并处理，避免重复计算"),
        (r"现合同", "当前结算规则"),
        (r"生命周期", "同一运行过程"),
        (r"官僚治理\s*官僚治理与行政执行结算", "官僚治理结算"),
        (r"官僚治理\s+官僚治理", "官僚治理"),
        (r"现有材料现有证据", "现有证据"),
        (r"现有证据现有证据", "现有证据"),
        (r"已有充分证据支持已有充分证据支持", "已有充分证据支持"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[；，]\s*[；，]+", "；", text)
    return text.strip(" ；，。")


def polish_payload(payload: dict[str, Any]) -> dict[str, Any]:
    before = _score_signature(payload)
    changed = 0
    for row in payload.get("records") or []:
        for profile in _iter_profiles(row):
            for field in ("adjudication_basis", "adjudication_boundary"):
                current = profile.get(field)
                if not isinstance(current, str) or not current.strip():
                    continue
                polished = _polish(current)
                if polished != current:
                    profile[field] = polished
                    changed += 1
                if FORBIDDEN.search(polished):
                    raise ValueError(
                        f"B1逐材料公开裁决仍含内部话术：{row.get('ruler_name')} / "
                        f"{profile.get('material_id')} / {field}"
                    )
    if _score_signature(payload) != before:
        raise ValueError("B1公开裁决措辞清洗意外改变了正式评分字段")
    payload["profile_adjudication_polish_count"] = changed
    return payload


def run(workspace_root: Path, *, write: bool = False) -> dict[str, Any]:
    path = workspace_root / B1_PATH
    payload = polish_payload(load_json(path))
    if write:
        write_json(path, payload, ruler_polities=load_ruler_polities(workspace_root))
    return {
        "record_count": len(payload.get("records") or []),
        "polish_count": payload.get("profile_adjudication_polish_count", 0),
        "write": write,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="清理B1逐材料公开裁决中的内部模板话术，不改变评分")
    parser.add_argument("--workspace-root", type=Path, default=Path("."))
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = run(args.workspace_root.resolve(), write=args.write)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
