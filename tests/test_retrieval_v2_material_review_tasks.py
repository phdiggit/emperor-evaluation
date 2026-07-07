from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_material_review_tasks as tool


def test_review_item_contains_claim_passage_patch_template() -> None:
    item = tool.review_item(
        {
            "review_code": "MRQ-001",
            "review_kind": "claim_passage_mismatch",
            "queue_status": "ready",
            "priority": 20,
            "target_code": "TGT-LB",
            "emperor_name": "刘邦",
            "item_code": "I5B",
            "source_pack_code": "SP-LB",
            "claim_id": 10,
            "claim_code": "CLM-001",
            "raw_claim_code": "C-1",
            "object_name": "刘敬",
            "object_type": "person",
            "claim_direction": "positive",
            "claim_summary": "刘敬建议迁都关中，刘邦采纳其议。",
            "diagnosis": "summary 与 passage 弱匹配",
            "recommended_action": "暂停自动入分",
            "review_payload": {"issue_code": "claim_passage_mismatch", "issue_message": "no overlap"},
            "source_passages": [
                {
                    "passage_code": "PAS-001",
                    "document_code": "DOC-001",
                    "source_title": "汉书",
                    "title": "汉书/卷一",
                    "locator": "高帝纪",
                    "raw_text": "高帝置酒雒阳南宫，论功行封。",
                }
            ],
        }
    )

    assert item["review_code"] == "MRQ-001"
    assert item["subject"]["object_name"] == "刘敬"
    assert item["audit_issue"]["issue_code"] == "claim_passage_mismatch"
    assert item["source_passages"][0]["raw_text"] == "高帝置酒雒阳南宫，论功行封。"
    assert item["required_patch"] == {
        "review_code": "MRQ-001",
        "queue_status": "",
        "review_note": "",
        "review_payload_patch": {
            "claim_passage_review": {
                "verdict": "",
                "basis": "",
                "passage_codes": [],
            }
        },
    }


def test_prompt_keeps_material_review_narrow(tmp_path: Path) -> None:
    item = tool.review_item(
        {
            "review_code": "MRQ-002",
            "review_kind": "claim_passage_object_only_match",
            "queue_status": "ready",
            "emperor_name": "朱元璋",
            "object_name": "胡惟庸",
            "claim_summary": "胡惟庸案造成株连清洗。",
            "source_passages": [{"passage_code": "PAS-002", "raw_text": "胡惟庸伏诛。"}],
        }
    )

    prompt = tool.prompt_for_task(
        task={"task_code": "MRT-001"},
        workitems=[item],
        patch_path=tmp_path / "patch.jsonl",
    )

    assert "只判断 claim_summary 是否被本任务给出的 source_passages 直接支撑" in prompt
    assert "禁止运行任何命令" in prompt
    assert "不要重判 positive/negative" in prompt
    assert "不要判断 rule 归属或因子取值" in prompt
    assert "verdict=needs_context" in prompt
    assert tool.PATCH_BEGIN in prompt
    assert "胡惟庸案造成株连清洗" in prompt


def test_write_worklist_outputs_builds_codex_tasks(tmp_path: Path) -> None:
    workitems = [
        tool.review_item(
            {
                "review_code": "MRQ-003",
                "review_kind": "claim_passage_mismatch",
                "queue_status": "ready",
                "emperor_name": "刘秀",
                "object_name": "来歙",
                "claim_summary": "来歙奉命经营陇右。",
                "source_passages": [{"passage_code": "PAS-003", "raw_text": "帝使来歙说隗嚣。"}],
                "resolved_candidate_count": 1,
            }
        ),
        tool.review_item(
            {
                "review_code": "MRQ-004",
                "review_kind": "claim_passage_object_mismatch",
                "queue_status": "ready",
                "emperor_name": "杨坚",
                "object_name": "杨素",
                "claim_summary": "杨素平定叛乱。",
                "source_passages": [{"passage_code": "PAS-004", "raw_text": "高颎议国政。"}],
            }
        ),
    ]

    summary = tool.write_worklist_outputs(output_root=tmp_path, workitems=workitems, batch_size=1)

    assert summary["totals"] == {"codex_tasks": 2, "downstream_impacted_workitems": 1, "workitems": 2}
    assert summary["counts_by_review_kind"] == {"claim_passage_mismatch": 1, "claim_passage_object_mismatch": 1}
    tasks = [json.loads(line) for line in (tmp_path / "codex_tasks.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(tasks) == 2
    assert all(task["task_kind"] == "claim_passage_material_review" for task in tasks)
    assert "--dangerously-bypass-approvals-and-sandbox" in tasks[0]["argv"]
    prompt_text = Path(tasks[0]["prompt_path"]).read_text(encoding="utf-8")
    assert "禁止运行任何命令" in prompt_text
    assert tool.PATCH_BEGIN in prompt_text


class FakeCursor:
    def __init__(self) -> None:
        self.sql = ""
        self.params = ()

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, sql: str, params=None) -> None:
        self.sql = sql.lower()
        self.params = tuple(params or ())

    def fetchall(self) -> list[dict]:
        return [
            {
                "review_code": "MRQ-005",
                "review_kind": "claim_passage_mismatch",
                "queue_status": "ready",
                "target_code": "TGT-ZZ",
                "emperor_name": "赵祯",
                "item_code": "I5B",
                "source_pack_code": "SP-ZZ",
                "claim_id": 5,
                "claim_code": "CLM-005",
                "object_name": "包拯",
                "object_type": "person",
                "claim_direction": "positive",
                "claim_summary": "包拯因失保任被左授。",
                "source_passages": [{"passage_code": "PAS-005", "raw_text": "包拯知开封府。"}],
            }
        ]


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_obj = FakeCursor()

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return self.cursor_obj


class FakePsycopg:
    def __init__(self, conn: FakeConnection) -> None:
        self.conn = conn

    def connect(self, *args, **kwargs) -> FakeConnection:
        return self.conn


def test_build_workitems_reads_material_review_queue(monkeypatch) -> None:
    conn = FakeConnection()
    monkeypatch.setattr(tool, "import_psycopg", lambda: (FakePsycopg(conn), object()))

    rows = tool.build_workitems(
        dsn="postgresql://fake",
        item_code="I5B",
        scope="accepted-packs",
        review_kinds=["claim_passage_mismatch"],
        target_names=["赵祯"],
        target_codes=[],
        limit=10,
    )

    assert rows[0]["review_code"] == "MRQ-005"
    assert rows[0]["source_passages"][0]["raw_text"] == "包拯知开封府。"
    assert "from retrieval_v2.material_review_queue mrq" in conn.cursor_obj.sql
    assert "claim_source_passages" in conn.cursor_obj.sql
    assert conn.cursor_obj.params[1] == ["claim_passage_mismatch"]


def test_extract_patch_rows_from_last_message() -> None:
    message = (
        "ignored\n"
        f"{tool.PATCH_BEGIN}\n"
        "{\"review_code\":\"MRQ-001\",\"queue_status\":\"blocked\",\"review_note\":\"当前 passage 只见南宫论功，不能支撑迁都关中 claim。\",\"review_payload_patch\":{\"claim_passage_review\":{\"verdict\":\"unsupported\",\"basis\":\"passage 不含刘敬迁都事实\",\"passage_codes\":[\"PAS-1\"]}}}\n"
        f"{tool.PATCH_END}\n"
    )

    rows = tool.extract_patch_rows(message)

    assert rows[0]["review_code"] == "MRQ-001"
    assert rows[0]["review_payload_patch"]["claim_passage_review"]["verdict"] == "unsupported"


def test_collect_patch_outputs_writes_missing_patch_from_last_message(tmp_path: Path) -> None:
    patch_path = tmp_path / "patches" / "task.jsonl"
    last_path = tmp_path / "logs" / "task.last.md"
    last_path.parent.mkdir(parents=True)
    last_path.write_text(
        f"{tool.PATCH_BEGIN}\n"
        "{\"review_code\":\"MRQ-002\",\"queue_status\":\"needs_review\",\"review_note\":\"当前 passage 截断在事件前后，无法确认 summary 是否被直接支撑。\",\"review_payload_patch\":{\"claim_passage_review\":{\"verdict\":\"needs_context\",\"basis\":\"需要更长上下文\",\"passage_codes\":[\"PAS-2\"]}}}\n"
        f"{tool.PATCH_END}\n",
        encoding="utf-8",
    )
    tasks_path = tmp_path / "tasks.jsonl"
    tool.write_jsonl(
        tasks_path,
        [
            {
                "task_code": "MRT-TEST",
                "patch_path": str(patch_path),
                "last_message_path": str(last_path),
            }
        ],
    )

    payload = tool.collect_patch_outputs(tasks_jsonl=tasks_path, output_json=tmp_path / "collect.json", overwrite=False)

    assert payload["ok"] is True
    assert payload["totals"]["files_written"] == 1
    rows = [json.loads(line) for line in patch_path.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["queue_status"] == "needs_review"
