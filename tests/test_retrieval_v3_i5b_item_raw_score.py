from __future__ import annotations

from decimal import Decimal

from scripts.dev import retrieval_v3_i5b_item_raw_score as tool


def test_markdown_labels_raw_signal_and_dynamic_mapping_boundary() -> None:
    report = {
        "results": [{
            "emperor": "测试帝", "weighted_raw_signal": "1.234",
            "rules": {
                rule: {
                    "cluster_id": 7 if rule == "appointment_delegation" else None,
                    "positive_signal": "2.000" if rule == "appointment_delegation" else "0.000",
                    "negative_signal": "0.500" if rule == "appointment_delegation" else "0.000",
                    "rule_raw_net": "1.500" if rule == "appointment_delegation" else "0.000",
                    "rule_weight": "0.360" if rule == "appointment_delegation" else "0.000",
                    "weighted_raw_signal": "0.540" if rule == "appointment_delegation" else "0.000",
                }
                for rule in tool.RULE_ORDER
            },
            "rule_cluster_lineage": {"appointment_delegation": {
                "id": 7, "rule_score_code": "RSC-7", "scored_judgment_count": 3,
                "target_code": "TGT-7", "updated_at": "2026-07-12", "calc_detail": {"materials": [{
                    "object_name": "测试臣", "claim_key": "CLMK-7", "event_group_keys": ["CEG-7"],
                    "side": "positive", "raw_score": "2.000", "factor_values": {"source_factor": "1.100000"},
                }]} }},
        }]
    }
    rendered = tool.render_markdown(report)

    assert "weighted raw signal" in rendered
    assert "最终 0–45 分和档位仍需批量动态映射" in rendered
    assert "| 测试帝 | 1.234 | 完整 |" in rendered
    assert "| appointment_delegation | 7 | 3 | 2.000 | 0.500 | 1.500 | 0.360 | 0.540 |" in rendered
    assert "`RSC-7`" in rendered
    assert "0.000 + 0.540 + 0.000 + 0.000 + 0.000 = 1.234" in rendered
    assert "| 测试臣 | `CLMK-7` | CEG-7 | positive | 2.000 | source_factor=1.100000 |" in rendered


def test_tool_is_read_only_and_does_not_write_final_results() -> None:
    source = open(tool.__file__, encoding="utf-8").read().lower()
    assert "insert into" not in source
    assert "update emp_item_results" not in source
    assert "final_score_generated\": false" in source
    assert "public." not in source


def test_fetch_v3_rule_signals_uses_v3_clusters_only() -> None:
    class Cursor:
        sql = ""

        def execute(self, sql, _params):
            self.sql = sql

        @staticmethod
        def fetchall():
            return [(
                "appointment_delegation", 7, "RSC-7", Decimal("2.500"), Decimal("0.500"),
                3, "2026-07-12", "TGT-7", {"materials": []},
            )]

    cur = Cursor()
    signals = tool.fetch_v3_rule_signals(
        cur,
        emperor="测试帝",
        item_code="I5B",
        cluster_formula="evidence_cluster_signal_v3",
    )

    assert "retrieval_v3.target_rule_score_clusters" in cur.sql
    assert signals["appointment_delegation"].positive_signal == Decimal("2.500")
    assert signals["appointment_delegation"].negative_signal == Decimal("0.500")
