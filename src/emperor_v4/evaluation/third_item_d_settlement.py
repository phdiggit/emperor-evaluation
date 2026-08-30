from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any, Mapping


FORMAL_SETTLEMENT_JSON_PATH = Path(
    "docs/评分结算/第三项军事与边疆净收益/军事成本收益比/01-皇帝D项正式结算.json"
)
FORMAL_SETTLEMENT_MARKDOWN_PATH = FORMAL_SETTLEMENT_JSON_PATH.with_suffix(".md")

D_SCORE_POINTS = {
    "D0": {"LOW": 0.0, "MID": 3.0, "HIGH": 6.0},
    "D1": {"LOW": 10.0, "MID": 12.0, "HIGH": 14.0},
    "D2": {"LOW": 18.0, "MID": 20.0, "HIGH": 22.0},
    "D3": {"LOW": 24.0, "MID": 26.0, "HIGH": 28.0},
    "D4": {"LOW": 30.0, "MID": 32.0, "HIGH": 34.0},
    "D5": {"LOW": 36.0, "MID": 38.0, "HIGH": 40.0},
    "D-N": {"NOT_APPLICABLE": 0.0},
}


def _load(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"UTF-8 BOM forbidden: {path}")
    return json.loads(raw.decode("utf-8"))


def _distribution(records: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row[key]) for row in records).items()))


def _validate_markdown(payload: Mapping[str, Any], markdown: str) -> None:
    position_labels = {"低位": "LOW", "中位": "MID", "高位": "HIGH", "不适用": "NOT_APPLICABLE"}
    rows: dict[str, tuple[str, str, float]] = {}
    in_table = False
    for line in markdown.splitlines():
        if line == "## 正式结算总表":
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table or not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line[1:-1].split("|")]
        if not cells[0].isdigit():
            continue
        rows[cells[1]] = (cells[4], position_labels[cells[5]], float(cells[6]))
    if len(rows) != len(payload["records"]):
        raise ValueError("D Markdown总表未覆盖全部正式人物")
    for record in payload["records"]:
        expected = (
            record["D_grade"], record["D_within_grade_position"],
            float(record["D_score_points"]),
        )
        if rows.get(record["ruler_name"]) != expected:
            raise ValueError(f"D Markdown与JSON不一致：{record['ruler_name']}")


def validate_third_item_d_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if payload.get("schema_id") != "emperor-v4-d-strategy-chain-formal-settlement-batch-v2":
        raise ValueError("第三项D正式schema不合法")
    if payload.get("canonical_status") != "FORMAL_CURRENT":
        raise ValueError("第三项D不是当前正式结算")
    if payload.get("authority_mode") != "FORMAL_SETTLEMENT_PATCH_SOURCE":
        raise ValueError("第三项D正式JSON未声明为patch权威")
    if not payload.get("formal_grade_write") or not payload.get("formal_score_write"):
        raise ValueError("第三项D正式档位或点值未闭合")
    if payload.get("database_write") or payload.get("third_item_total_and_ranking_written"):
        raise ValueError("第三项D写入边界不合法")

    records = list(payload.get("records") or ())
    if payload.get("record_count") != len(records) or len(records) != 201:
        raise ValueError("第三项D正式覆盖必须为201人")
    if len({row.get("ruler_id") for row in records}) != len(records):
        raise ValueError("第三项D存在重复人物ID")
    if len({row.get("ruler_name") for row in records}) != len(records):
        raise ValueError("第三项D存在重复人物名")

    chain_count = 0
    excluded_chain_count = 0
    for row in records:
        grade = str(row.get("D_grade"))
        position = str(row.get("D_within_grade_position"))
        try:
            expected = D_SCORE_POINTS[grade][position]
        except KeyError as exc:
            raise ValueError(f"D点值映射未闭合：{row.get('ruler_name')} {grade}/{position}") from exc
        if float(row.get("D_score_points")) != expected:
            raise ValueError(f"D正式点值与档位不一致：{row.get('ruler_name')}")
        if row.get("D_score_status") != "DIRECT_D_SCORE_ASSIGNED":
            raise ValueError(f"D正式点值状态未闭合：{row.get('ruler_name')}")
        if not row.get("coverage_status") or not row.get("adjudication_basis"):
            raise ValueError(f"D正式裁决依据不完整：{row.get('ruler_name')}")
        if not row.get("formal_grade_write") or not row.get("formal_score_write") or row.get("database_write"):
            raise ValueError(f"D人物写入边界不合法：{row.get('ruler_name')}")
        profile = row.get("attributable_cost_profile") or {}
        if not profile.get("cost_band") or not profile.get("position") or not profile.get("status"):
            raise ValueError(f"D成本画像不完整：{row.get('ruler_name')}")

        chains = [
            *(row.get("external_strategic_chains") or ()),
            *(row.get("strategic_internal_chains") or ()),
        ]
        chain_ids = [chain.get("chain_id") for chain in chains]
        if len(chain_ids) != len(set(chain_ids)) or any(not value for value in chain_ids):
            raise ValueError(f"D计分战略链ID重复或缺失：{row.get('ruler_name')}")
        for chain in chains:
            if not chain.get("source_refs") or not (
                chain.get("security_change_basis")
                or chain.get("basis")
                or chain.get("terminal_result_profile")
            ):
                raise ValueError(f"D战略链证据不完整：{row.get('ruler_name')} {chain.get('chain_id')}")
        chain_count += len(chains)
        excluded_chain_count += len(row.get("cross_item_excluded_chains") or ())

    grade_distribution = _distribution(records, "D_grade")
    position_distribution = dict(sorted(Counter(
        f"{row['D_grade']}-{row['D_within_grade_position']}" for row in records
    ).items()))
    score_distribution = dict(sorted(Counter(
        str(float(row["D_score_points"])) for row in records
    ).items(), key=lambda item: float(item[0])))
    if payload.get("grade_distribution") != grade_distribution:
        raise ValueError("D档位分布与正式记录不一致")
    if payload.get("grade_position_distribution") != position_distribution:
        raise ValueError("D档内位置分布与正式记录不一致")
    if payload.get("score_distribution") != score_distribution:
        raise ValueError("D点值分布与正式记录不一致")
    if (payload.get("score_mapping") or {}).get("points") != D_SCORE_POINTS:
        raise ValueError("D点值映射合同不一致")
    if (payload.get("score_mapping") or {}).get("legacy_Q_consumed") is not False:
        raise ValueError("旧线性Q不得成为当前D正式裁决来源")
    if (payload.get("cross_item_deduplication") or {}).get("excluded_chain_count") != excluded_chain_count:
        raise ValueError("D跨项排除链计数不一致")
    if (payload.get("cross_item_deduplication") or {}).get("leaked_into_scoring_arrays") != 0:
        raise ValueError("D跨项排除链泄漏到计分数组")
    return {
        "status": "PASS", "record_count": len(records),
        "strategic_chain_count": chain_count,
        "excluded_chain_count": excluded_chain_count,
        "grade_distribution": grade_distribution,
    }


def verify_third_item_d_formal_settlement(repo_root: Path) -> dict[str, Any]:
    json_path = repo_root / FORMAL_SETTLEMENT_JSON_PATH
    markdown_path = repo_root / FORMAL_SETTLEMENT_MARKDOWN_PATH
    payload = _load(json_path)
    result = validate_third_item_d_payload(payload)
    _validate_markdown(payload, markdown_path.read_text(encoding="utf-8"))
    return result


if __name__ == "__main__":
    print(json.dumps(verify_third_item_d_formal_settlement(Path.cwd()), ensure_ascii=False, indent=2))
