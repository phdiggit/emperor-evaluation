"""Offline cost-adjudication pilot; never writes a scoring input or ranks profiles."""
from __future__ import annotations

import json
from pathlib import Path
import yaml

from emperor_v4.evaluation.formal_json_store import load_json

CONFIG_PATH = Path("config/third-item/cost-sensitivity-cases.json")
OUTPUT_JSON = Path("docs/评分结算/综合分析/01-军事成本裁决敏感性.json")
OUTPUT_MD = OUTPUT_JSON.with_suffix(".md")


def _project_score(row: dict, third: dict, factor: float) -> tuple[float, float, float, float]:
    debit = 80 * (1 - factor)
    applied = max(debit, abs(float(third["military_net_loss_penalty"])))
    third_score = round(sum(float(third[k]) for k in ("A120_score_points", "B80_score_points", "C50_score_points")) - applied, 2)
    first = float(row.get("first_item_raw_score") or 0)
    addon = 0.15 * 637 * (first / 240) ** 1.25 if first > 0 else 0
    total = round(float(row["second_item_score"]) + third_score + addon + float(row["fourth_item_adjustment"]), 2)
    return debit, applied, third_score, total


def analyze(records: list[dict], third_by_id: dict, factors: dict, cases: list[dict]) -> dict:
    """Each case is independent; all other adjudications remain at the current baseline."""
    indexed = {r["ruler_id"]: r for r in records}
    if len(indexed) != len(records) or len({c["case_id"] for c in cases}) != len(cases):
        raise ValueError("敏感性人物或案例ID重复")
    results = []
    for case in cases:
        rid = case["ruler_id"]
        row, third = indexed[rid], third_by_id[rid]
        cost = third["global_cost_credit_profile"]
        if (cost["cost_band"], cost["position"]) != (case["baseline_cost_band"], case["baseline_cost_position"]):
            raise ValueError(f"敏感性案例基准已变，须复核解释：{case['case_id']}")
        if not case.get("source_refs"):
            raise ValueError("敏感性案例缺少证据")
        _, _, baseline_third, baseline_total = _project_score(row, third, factors[cost["cost_band"]][cost["position"]])
        if (baseline_third, baseline_total) != (row["third_item_score"], row["total_score"]):
            raise ValueError("敏感性基准换分与当前正式结果不同值")
        scenarios = case["scenarios"]
        if not scenarios or len({s["scenario_id"] for s in scenarios}) != len(scenarios):
            raise ValueError("敏感性情景为空或ID重复")
        evaluated = []
        supported_ranks = [row["rank"]]
        supported_scores = [row["total_score"]]
        for scenario in scenarios:
            status = scenario["status"]
            if status not in {"SUPPORTED_INTERPRETATION", "REJECTED_DIAGNOSTIC"} or not scenario.get("basis"):
                raise ValueError("敏感性情景必须声明解释依据与准入状态")
            ml = abs(float(third["military_net_loss_penalty"]))
            if ml and int(scenario["cost_band"][1:]) < 5:
                raise ValueError("成本情景影响ML准入，须联合重裁，不能固定ML")
            debit, applied, third_score, total = _project_score(row, third, factors[scenario["cost_band"]][scenario["cost_position"]])
            scores = {key: float(r["total_score"]) for key, r in indexed.items()}
            scores[rid] = total
            ranks = {key: 1 + sum(value > score for value in scores.values()) for key, score in scores.items()}
            if status == "SUPPORTED_INTERPRETATION":
                supported_ranks.append(ranks[rid])
                supported_scores.append(total)
            evaluated.append({
                **scenario,
                "cost_debit": round(debit, 2), "applied_debit": round(applied, 2),
                "third_item_score": third_score, "total_score": total,
                "total_delta": round(total - row["total_score"], 2), "rank": ranks[rid],
                "rank_changes": [
                    {"ruler_id": r["ruler_id"], "ruler_name": r["ruler_name"], "baseline_rank": r["rank"], "scenario_rank": ranks[r["ruler_id"]]}
                    for r in records if ranks[r["ruler_id"]] != r["rank"]
                ],
            })
        results.append({
            "case_id": case["case_id"], "ruler_id": rid, "ruler_name": row["ruler_name"],
            "source_refs": case["source_refs"],
            "baseline": {"rank": row["rank"], "total_score": row["total_score"], "third_item_score": row["third_item_score"], "cost_band": cost["cost_band"], "cost_position": cost["position"]},
            "supported_rank_range": [min(supported_ranks), max(supported_ranks)],
            "supported_total_range": [min(supported_scores), max(supported_scores)],
            "scenarios": evaluated,
        })
    return {"schema_id": "military-cost-sensitivity-analysis-v1", "non_scoring": True,
            "scope": "INDEPENDENT_COST_CASES_OTHER_ADJUDICATIONS_FIXED", "confidence_interval": False,
            "case_count": len(results), "cases": results}


def build(root: Path) -> dict:
    from emperor_v4.evaluation.composite_ranking import verify_composite_ranking
    verify_composite_ranking(root)
    project = yaml.safe_load((root / "config/project.yml").read_text(encoding="utf-8"))
    composite = load_json(root / project["scoring_contract"]["composite_ranking_json"])
    third = load_json(root / project["formal_settlements"]["third_item"]["json"])
    source_index = {r["ruler_id"]: r for r in third["records"]}
    pool = load_json(root / project["canonical_ruler_pool"]["json"])
    mapped = {r["ruler_id"]: source_index[r["source_item_ids"]["third_item"]]
              for r in pool["records"] if r["settlement_readiness"] == "COMPOSITE_READY"}
    cases = load_json(root / CONFIG_PATH)["cases"]
    for case in cases:
        for ref in case["source_refs"]:
            if not (root / ref.split("#", 1)[0]).is_file():
                raise ValueError(f"敏感性证据不存在：{ref}")
    factors = load_json(root / "config/third-item/third-item-cost-credit-factors.json")["factor_by_global_cost_band_and_position"]
    return analyze(composite["records"], mapped, factors, cases)


def render(payload: dict) -> str:
    lines = ["# 军事成本裁决敏感性", "",
             "本页为不计分的证据解释试点，每个案例单独计算，其他人物、权重、成果与ML裁决固定。证据允许范围仅覆盖所列解释；不是置信区间，也不代表完整历史不确定性。被排除假设仅展示影响，不进入允许范围。", ""]
    for case in payload["cases"]:
        baseline = case["baseline"]
        lines += [f"## {case['ruler_name']}", "",
                  f"当前基准：{baseline['cost_band']}-{baseline['cost_position']}；第三项{baseline['third_item_score']:.2f}，总分{baseline['total_score']:.2f}，第{baseline['rank']}名。", "",
                  "| 解释 | 性质 | 成本 | 总分 | 分差 | 名次 |", "|---|---|---|---:|---:|---:|"]
        for s in case["scenarios"]:
            label = "证据允许的解释" if s["status"] == "SUPPORTED_INTERPRETATION" else "被排除假设，仅诊断"
            lines.append(f"| {s['label']} | {label} | {s['cost_band']}-{s['cost_position']} | {s['total_score']:.2f} | {s['total_delta']:+.2f} | {s['rank']} |")
        lines += ["", f"所列证据允许解释下：总分{case['supported_total_range'][0]:.2f}—{case['supported_total_range'][1]:.2f}，名次{case['supported_rank_range'][0]}—{case['supported_rank_range'][1]}。范围相同只说明这些解释不改变计分，不能推出其他裁决无不确定性。", ""]
        lines += [f"- {s['label']}：{s['basis']}" for s in case["scenarios"]]
        lines += ["", *[f"证据：[当前数量审计](../../../{ref})。" for ref in case["source_refs"]], ""]
    return "\n".join(lines).rstrip() + "\n"


def run(root: Path, *, write: bool = False) -> dict:
    payload = build(root)
    markdown = render(payload)
    if write:
        (root / OUTPUT_JSON).parent.mkdir(parents=True, exist_ok=True)
        (root / OUTPUT_JSON).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        (root / OUTPUT_MD).write_text(markdown, encoding="utf-8", newline="\n")
    elif load_json(root / OUTPUT_JSON) != payload or (root / OUTPUT_MD).read_text(encoding="utf-8") != markdown:
        raise ValueError("军事成本裁决敏感性结果未同步；请运行cost-sensitivity --write")
    return {"status": "PASS", "case_count": payload["case_count"], "non_scoring": True}
