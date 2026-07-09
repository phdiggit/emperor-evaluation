from __future__ import annotations

from scripts.dev import retrieval_v3_background_status as tool


def test_render_markdown_summarizes_queues_and_alerts() -> None:
    report = {
        "schema_name": "retrieval_v3",
        "queue_summary": {
            "object_source": [{"status": "succeeded", "count": 2}],
            "claim_extraction": [{"status": "running", "count": 1}],
        },
        "recent_object_source_jobs": [
            {
                "job_code": "OSCACHE-001",
                "status": "succeeded",
                "emperor_name": "刘邦",
                "source_document_count": 3,
                "mention_slice_count": 5,
                "claim_bridge_status": "planned",
                "claim_job_code": "CLMEXT-001",
            }
        ],
        "recent_claim_jobs": [
            {
                "job_code": "CLMEXT-001",
                "status": "running",
                "emperor_name": "刘邦",
                "uncovered_slice_count": 7,
                "latest_claim_count": 0,
                "latest_run_code": "CLMRUN-001",
            }
        ],
        "claim_cache_by_emperor": [{"emperor_name": "刘邦", "status": "active", "claim_count": 12}],
        "alerts": {"zero_claim_target_objects": ["李孝恭"]},
    }

    text = tool.render_markdown(report)

    assert "object-source queue: succeeded=2" in text
    assert "claim-extraction queue: running=1" in text
    assert "| OSCACHE-001 | succeeded | 刘邦 | 3 | 5 | planned | CLMEXT-001 |" in text
    assert "- 刘邦 `active`: 12" in text
    assert "zero-claim target objects: 李孝恭" in text

