from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_claim_passage_repair as tool


def test_select_candidate_slices_prefers_original_slice_refs() -> None:
    row = {
        "object_name": "刘敬",
        "claim_summary": "刘邦采纳娄敬迁都关中的建策，并拜为奉春君、赐姓刘氏。",
        "claim_payload": {"source_slice_refs": ["SLI-RIGHT"]},
    }
    candidates = {
        "candidate_slices": [
            {
                "slice_code": "SLI-OTHER",
                "object_name": "刘敬",
                "document_code": "DOC-1",
                "locator": "chars:1-20",
                "score": 100,
                "text": "刘敬求见。",
            },
            {
                "slice_code": "SLI-RIGHT",
                "object_name": "张良",
                "document_code": "DOC-1",
                "locator": "chars:20-80",
                "score": 10,
                "text": "戍卒娄敬求见，说上曰，不如入关。拜娄敬为奉春君，赐姓刘氏。",
            },
        ]
    }

    selected = tool.select_candidate_slices(row, candidates, limit=2)

    assert selected[0]["slice_code"] == "SLI-RIGHT"
    assert "奉春君" in selected[0]["text"]


def test_repair_workitem_contains_current_passages_and_patch_template(monkeypatch) -> None:
    monkeypatch.setattr(
        tool,
        "load_candidate_payload",
        lambda row: {
            "candidate_slices": [
                {
                    "slice_code": "SLI-1",
                    "object_name": "张良",
                    "document_code": "DOC-1",
                    "locator": "chars:1-80",
                    "text": "夫运筹帷幄之中，决胜千里之外，吾不如子房。",
                }
            ]
        },
    )

    item = tool.repair_workitem(
        {
            "review_code": "MRQ-1",
            "review_kind": "claim_passage_mismatch",
            "queue_status": "blocked",
            "target_code": "TGT-LB",
            "emperor_name": "刘邦",
            "item_code": "I5B",
            "source_pack_id": 3,
            "source_pack_code": "SPK-LB",
            "claim_id": 9,
            "claim_code": "CLM-1",
            "raw_claim_code": "RAW-1",
            "object_name": "张良",
            "object_type": "person",
            "claim_direction": "positive",
            "claim_summary": "刘邦称张良运筹帷幄、决胜千里。",
            "claim_payload": {"source_slice_refs": ["SLI-1"], "source_passage_refs": ["PAS-BAD"]},
            "source_passages": [{"passage_code": "PAS-BAD", "raw_text": "高帝置酒雒阳南宫。"}],
        },
        candidate_limit=4,
    )

    assert item["subject"]["object_name"] == "张良"
    assert item["current_source_passages"][0]["passage_code"] == "PAS-BAD"
    assert item["candidate_slices"][0]["slice_code"] == "SLI-1"
    assert item["required_patch"]["repair_action"] == ""


def test_candidate_payload_paths_falls_back_to_latest_target_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(tool, "ROOT", tmp_path)
    stale = tmp_path / "missing" / "candidates.final.json"
    old_path = tmp_path / "tmp" / "retrieval_v2_clean_runs" / "runner_old" / "TGT-1_appointment_delegation" / "candidates.final.json"
    new_path = tmp_path / "tmp" / "retrieval_v2_clean_runs" / "runner_new" / "TGT-1_appointment_delegation" / "candidates.final.json"
    old_path.parent.mkdir(parents=True)
    new_path.parent.mkdir(parents=True)
    old_path.write_text("{}", encoding="utf-8")
    new_path.write_text("{}", encoding="utf-8")

    paths = tool.candidate_payload_paths({"artifacts": {"candidates": str(stale)}, "target_code": "TGT-1"})

    assert paths[0] == stale
    assert new_path in paths
    assert old_path in paths


def test_prompt_names_repair_actions_and_disposition_rule(tmp_path: Path) -> None:
    prompt = tool.prompt_for_task(
        task={"task_code": "CPR-1"},
        workitems=[
            {
                "review_code": "MRQ-1",
                "claim_summary": "胡惟庸伏诛。",
                "candidate_slices": [{"slice_code": "SLI-1", "text": "胡惟庸伏诛。"}],
                "required_patch": {},
            }
        ],
        patch_path=tmp_path / "patch.jsonl",
    )

    assert "repair_action=relink" in prompt
    assert "repair_action=drop_claim" in prompt
    assert "repair_action=block_claim" in prompt
    assert "处置性材料" in prompt
    assert tool.PATCH_BEGIN in prompt


def test_collect_patch_outputs_writes_jsonl(tmp_path: Path) -> None:
    last_path = tmp_path / "logs" / "task.last.md"
    last_path.parent.mkdir(parents=True)
    last_path.write_text(
        f"{tool.PATCH_BEGIN}\n"
        "{\"review_code\":\"MRQ-1\",\"repair_action\":\"relink\",\"queue_status\":\"resolved\",\"review_note\":\"候选片段直接出现运筹帷幄和子房，可重链。\",\"claim_summary\":\"\",\"source_slice_codes\":[\"SLI-1\"],\"claim_payload_patch\":{}}\n"
        f"{tool.PATCH_END}\n",
        encoding="utf-8",
    )
    patch_path = tmp_path / "patches" / "task.jsonl"
    tasks_path = tmp_path / "tasks.jsonl"
    tool.write_jsonl(tasks_path, [{"task_code": "CPR-1", "patch_path": str(patch_path), "last_message_path": str(last_path)}])

    payload = tool.collect_patch_outputs(tasks_jsonl=tasks_path, output_json=tmp_path / "collect.json", overwrite=False)

    assert payload["ok"] is True
    rows = [json.loads(line) for line in patch_path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["repair_action"] == "relink"


def test_validate_patch_row_enforces_action_contract() -> None:
    row = tool.validate_patch_row(
        {
            "review_code": "MRQ-1",
            "repair_action": "rewrite",
            "queue_status": "resolved",
            "review_note": "候选片段支撑较窄事实，需要改写为原文可直接支撑的 claim。",
            "claim_summary": "刘邦称张良运筹帷幄。",
            "source_slice_codes": ["SLI-1"],
        }
    )

    assert row["repair_action"] == "rewrite"
    assert row["source_slice_codes"] == ["SLI-1"]


def test_validate_patch_row_allows_block_claim_without_rejecting_claim() -> None:
    row = tool.validate_patch_row(
        {
            "review_code": "MRQ-1",
            "repair_action": "block_claim",
            "queue_status": "blocked",
            "review_note": "处置性材料不能作为当前 appointment_delegation claim 自动消费，但保留史料供后续规则复核。",
        }
    )

    assert row["repair_action"] == "block_claim"
    assert row["source_slice_codes"] == []


def test_read_patch_inputs_accepts_directory(tmp_path: Path) -> None:
    patch_dir = tmp_path / "patches"
    patch_dir.mkdir()
    (patch_dir / "a.jsonl").write_text("{\"review_code\":\"MRQ-A\"}\n", encoding="utf-8")
    (patch_dir / "b.jsonl").write_text("{\"review_code\":\"MRQ-B\"}\n", encoding="utf-8")

    rows = tool.read_patch_inputs([patch_dir])

    assert [row["review_code"] for row in rows] == ["MRQ-A", "MRQ-B"]


def test_auto_patch_relinks_full_source_slice_refs() -> None:
    patch, reason = tool.auto_patch_for_workitem(
        {
            "review_code": "MRQ-A",
            "claim_summary": "刘邦采纳张良谋略，并称其运筹帷幄。",
            "claim_source_slice_refs": ["SLI-A"],
            "subject": {"object_name": "张良", "claim_direction": "positive"},
            "candidate_slices": [
                {"slice_code": "SLI-A", "text": "夫运筹帷幄之中，决胜千里之外，吾不如子房。张良受用。"}
            ],
        }
    )

    assert reason == ""
    assert patch is not None
    assert patch["repair_action"] == "relink"
    assert patch["source_slice_codes"] == ["SLI-A"]


def test_auto_patch_skips_disposition_negative() -> None:
    patch, reason = tool.auto_patch_for_workitem(
        {
            "review_code": "MRQ-B",
            "claim_summary": "刘昉后来与梁士彦谋反，事发伏诛。",
            "claim_source_slice_refs": ["SLI-B"],
            "subject": {"object_name": "刘昉", "claim_direction": "negative"},
            "candidate_slices": [{"slice_code": "SLI-B", "text": "刘昉与梁士彦谋反，伏诛。"}],
        }
    )

    assert patch is None
    assert reason == "disposition_negative_needs_review"


def test_auto_triage_emits_needs_source_refine_for_disposition_negative() -> None:
    patch, reason = tool.auto_triage_patch_for_workitem(
        {
            "review_code": "MRQ-B",
            "claim_summary": "刘昉后来与梁士彦谋反，事发伏诛。",
            "claim_source_slice_refs": ["SLI-B"],
            "subject": {"object_name": "刘昉", "claim_direction": "negative"},
            "candidate_slices": [{"slice_code": "SLI-B", "text": "刘昉与梁士彦谋反，伏诛。"}],
        }
    )

    assert reason == ""
    assert patch is not None
    assert patch["repair_action"] == "needs_source_refine"
    assert patch["queue_status"] == "needs_review"


class FakeCursor:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.params: list[tuple] = []
        self.rowcount = 1
        self.fetchone_queue = [
            {
                "review_id": 1,
                "queue_status": "blocked",
                "claim_id": 10,
                "claim_summary": "刘邦称张良运筹帷幄。",
                "claim_payload": {},
                "source_pack_id": 20,
                "source_pack_code": "SPK-LB",
            },
            {"id": 30},
            {"id": 40},
        ]

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, sql: str, params=None) -> None:
        self.statements.append(" ".join(sql.lower().split()))
        self.params.append(tuple(params or ()))
        self.rowcount = 1

    def fetchone(self):
        return self.fetchone_queue.pop(0)


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_obj = FakeCursor()
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return self.cursor_obj

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class FakePsycopg:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn

    def connect(self, *args, **kwargs) -> FakeConnection:
        return self.conn


def test_apply_repair_patch_relinks_claim_passages(monkeypatch) -> None:
    conn = FakeConnection()
    monkeypatch.setattr(tool, "import_psycopg", lambda: (FakePsycopg(conn), object()))
    workitems = {
        "MRQ-1": {
            "candidate_slices": [
                {
                    "slice_code": "SLI-1",
                    "document_code": "DOC-RAW",
                    "locator": "chars:1-40",
                    "text": "夫运筹帷幄之中，决胜千里之外，吾不如子房。",
                }
            ]
        }
    }

    payload = tool.apply_repair_patch(
        dsn="postgresql://fake",
        patch_rows=[
            {
                "review_code": "MRQ-1",
                "repair_action": "relink",
                "queue_status": "resolved",
                "review_note": "候选片段直接出现运筹帷幄和子房，可重链。",
                "source_slice_codes": ["SLI-1"],
            }
        ],
        workitems=workitems,
        execute=False,
    )

    joined = "\n".join(conn.cursor_obj.statements)
    assert payload["applied_counts"]["retrieval_v2.source_passages"] == 1
    assert "delete from retrieval_v2.claim_source_passages" in joined
    assert "insert into retrieval_v2.claim_source_passages" in joined
    assert "update retrieval_v2.material_review_queue" in joined
    assert "update retrieval_v2.coverage_gap_events" in joined
    assert "update retrieval_v2.jobs" in joined
    assert conn.rolled_back is True
