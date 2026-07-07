from __future__ import annotations

from scripts.dev import retrieval_v2_claim_passage_audit as tool


def claim_row(**overrides):
    row = {
        "claim_id": 10,
        "claim_code": "CLM-001",
        "target_id": 20,
        "target_code": "TGT-I5B-LH",
        "emperor_name": "刘恒",
        "source_pack_id": 30,
        "source_pack_code": "SPK-I5B-LH-DELEGATION",
        "source_rule_code": "delegation",
        "contract_rule_id": 40,
        "object_name": "冯唐",
        "claim_direction": "positive",
        "claim_summary": "文帝遣冯唐持节赦魏尚。",
        "source_passages": [
            {
                "passage_code": "PAS-001",
                "raw_text": "上令冯唐持节赦魏尚。",
                "source_title": "史记",
                "title": "张释之冯唐列传",
            }
        ],
        "candidate_count": 1,
        "resolved_candidate_count": 0,
        "binding_count": 1,
        "factor_judgment_count": 0,
        "material_score_count": 0,
        "open_material_review_count": 0,
    }
    row.update(overrides)
    return row


def test_build_audit_flags_mismatched_claim_passage_and_downstream() -> None:
    payload = tool.build_audit(
        [
            claim_row(),
            claim_row(
                claim_id=11,
                claim_code="CLM-002",
                claim_summary="刘敬建议刘邦迁都关中。",
                source_passages=[{"passage_code": "PAS-002", "raw_text": "高祖置酒雒阳南宫，论萧何、张良、韩信功。"}],
                resolved_candidate_count=1,
                factor_judgment_count=1,
                material_score_count=1,
            ),
        ]
    )

    assert payload["totals"]["claims"] == 2
    assert payload["totals"]["flagged_claims"] == 1
    assert payload["totals"]["downstream_impacted_claims"] == 1
    assert payload["issue_counts"] == {"claim_passage_mismatch": 1}
    assert payload["sample_downstream_impacted"][0]["claim_code"] == "CLM-002"


class FakeCursor:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[object] = []

    def execute(self, sql: str, params=()) -> None:
        self.statements.append(sql)
        self.params.append(params)


def test_enqueue_material_reviews_writes_claim_level_queue() -> None:
    cur = FakeCursor()
    counts = tool.enqueue_material_reviews(
        cur,
        [
            {
                **tool.audit_claim_row(
                    claim_row(
                        claim_summary="刘敬建议刘邦迁都关中。",
                        source_passages=[{"passage_code": "PAS-002", "raw_text": "高祖置酒雒阳南宫，论三杰功。"}],
                    )
                ),
                "resolved_candidate_count": 2,
                "factor_judgment_count": 3,
                "material_score_count": 4,
            }
        ],
    )

    assert counts == {"retrieval_v2.material_review_queue": 1}
    joined = "\n".join(cur.statements)
    assert "insert into retrieval_v2.material_review_queue" in joined
    assert "queue_status = retrieval_v2.material_review_queue.queue_status" in joined
    assert "claim_passage_alignment" in cur.params[0][1]
    assert cur.params[0][5] == "claim_passage_mismatch"


def test_enqueue_gap_events_writes_codex_review_repair_signal() -> None:
    cur = FakeCursor()
    flagged = [
        tool.audit_claim_row(
            claim_row(
                claim_summary="刘敬建议刘邦迁都关中。",
                source_passages=[{"passage_code": "PAS-002", "raw_text": "高祖置酒雒阳南宫，论三杰功。"}],
            )
        )
    ]

    counts = tool.enqueue_gap_events(cur, flagged)

    assert counts == {"retrieval_v2.coverage_gap_events": 1}
    joined = "\n".join(cur.statements)
    assert "insert into retrieval_v2.coverage_gap_events" in joined
    assert "then retrieval_v2.coverage_gap_events.status" in joined
    assert cur.params[0][5] == "material_classification_review"
    assert cur.params[0][6] == "codex_review"
    assert cur.params[0][8].startswith("补判该 claim")
