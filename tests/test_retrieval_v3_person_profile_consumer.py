from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v3_person_profile_consumer as tool


def person_row(name: str, object_id: int = 1) -> dict:
    return {
        "object_id": object_id,
        "object_code": f"OBJ-{object_id}",
        "object_identity_key": f"target|TGT|type|person|name|{name}",
        "canonical_name": name,
        "normalized_name": name,
        "identity_status": "active",
    }


def old_talent_row(name: str, label: str, *, attr_id: int = 20, note: str = "旧库已复核。") -> dict:
    return {
        "old_obj_id": attr_id + 100,
        "old_name": name,
        "old_obj_type": "person",
        "old_attr_id": attr_id,
        "talent_quality_label": label,
        "old_attr_note": note,
        "old_confidence": 1.0,
        "alias_text": "",
        "normalized_alias": "",
        "alias_kind": "",
    }


def test_build_profile_plan_uses_only_current_person_objects_and_marks_missing() -> None:
    plan = tool.build_profile_plan(
        [person_row("冯唐", 1), person_row("傅友德", 2)],
        [
            old_talent_row("冯唐", "顶级人才", attr_id=10, note="冯唐以谏议和政务判断见称。"),
            old_talent_row("旧库其他人", "历史级人才", attr_id=11),
        ],
    )

    assert plan["totals"]["person_objects"] == 2
    assert plan["totals"]["matched_old_talent_quality"] == 1
    assert plan["totals"]["missing_old_talent_quality"] == 1
    by_name = {row["canonical_name"]: row for row in plan["profile_rows"]}
    assert by_name["冯唐"]["talent_grade"] == "top_talent"
    assert by_name["冯唐"]["review_status"] == "accepted"
    assert by_name["冯唐"]["talent_grade_basis"] == "冯唐，以谏议和政务判断见称"
    assert by_name["傅友德"]["talent_grade"] is None
    assert by_name["傅友德"]["review_status"] == "needs_review"
    assert by_name["傅友德"]["talent_grade_basis"] == ""
    assert plan["operation_counts"] == {"retrieval_v3.person_profiles": 2}


def test_clean_person_evaluation_keeps_only_chinese_evaluation_segments() -> None:
    note = (
        "清史稿本传将其视为清廉能吏代表，地方治理声望很高。"
        "；basis=authority_consensus"
        "；Backfilled by talent_quality attr audit."
        "；不把清廉声望直接转化为顶级中枢人才"
        "；旧库记录仅供导入审计"
    )

    assert tool.clean_person_evaluation(note) == "清史稿本传将其视为清廉能吏代表，地方治理声望很高"


def test_build_profile_plan_does_not_choose_between_conflicting_old_grades() -> None:
    plan = tool.build_profile_plan(
        [person_row("姚崇", 1)],
        [
            old_talent_row("姚崇", "历史级人才", attr_id=1),
            old_talent_row("姚崇", "顶级人才", attr_id=2),
        ],
    )

    row = plan["profile_rows"][0]
    assert row["match_status"] == "conflicting_old_talent_quality"
    assert row["talent_grade"] is None
    assert row["review_status"] == "needs_review"


class FakeCursor:
    def __init__(self, conn: "FakeConnection") -> None:
        self.conn = conn
        self.rows: list[dict] = []
        self.row: dict | None = None

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, sql: str, params=None) -> None:
        lowered = sql.lower()
        self.conn.statements.append(lowered)
        if "from public.raw_objs" in lowered:
            self.rows = [dict(row) for row in self.conn.old_rows]
            self.row = None
            return
        if "from retrieval_v3.objects" in lowered:
            self.rows = [dict(row) for row in self.conn.person_rows]
            self.row = None
            return
        if "insert into retrieval_v3.person_profiles" in lowered:
            self.conn.next_id += 1
            self.row = {"id": self.conn.next_id}
            self.rows = []
            return
        self.rows = []
        self.row = None

    def fetchall(self) -> list[dict]:
        return self.rows

    def fetchone(self) -> dict | None:
        return self.row


class FakeConnection:
    def __init__(self, *, old_rows: list[dict] | None = None, person_rows: list[dict] | None = None) -> None:
        self.old_rows = old_rows or []
        self.person_rows = person_rows or []
        self.statements: list[str] = []
        self.next_id = 100
        self.committed = False
        self.rolled_back = False

    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class FakePsycopg:
    def __init__(self, reference_conn: FakeConnection, new_conn: FakeConnection) -> None:
        self.reference_conn = reference_conn
        self.new_conn = new_conn

    def connect(self, dsn: str, *args, **kwargs) -> FakeConnection:
        return self.reference_conn if dsn == "reference-dsn" else self.new_conn


def patch_fake_db(monkeypatch) -> tuple[FakeConnection, FakeConnection]:
    reference_conn = FakeConnection(old_rows=[old_talent_row("冯唐", "顶级人才")])
    new_conn = FakeConnection(person_rows=[person_row("冯唐", 1), person_row("傅友德", 2)])
    monkeypatch.setattr(tool, "import_psycopg", lambda: (FakePsycopg(reference_conn, new_conn), object()))
    monkeypatch.setattr(tool, "resolve_dsn", lambda env: "reference-dsn" if env == "REFERENCE_DSN" else "new-dsn")
    return reference_conn, new_conn


def test_apply_defaults_to_db_backed_dry_run_without_writes(tmp_path: Path, monkeypatch, capsys) -> None:
    _reference_conn, new_conn = patch_fake_db(monkeypatch)
    output_json = tmp_path / "profiles.json"
    output_md = tmp_path / "profiles.md"

    assert tool.main([
        "apply",
        "--reference-dsn-env",
        "REFERENCE_DSN",
        "--dsn-env",
        "NEW_DSN",
        "--output-json",
        str(output_json),
        "--output-md",
        str(output_md),
    ]) == 0

    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["write_db"] is False
    assert payload["executed"] is False
    assert payload["totals"]["profile_rows"] == 2
    assert new_conn.rolled_back is True
    assert not any("insert into retrieval_v3.person_profiles" in statement for statement in new_conn.statements)
    assert json.loads(capsys.readouterr().out)["totals"]["profile_rows"] == 2


def test_execute_upserts_one_profile_per_current_person_object(monkeypatch) -> None:
    _reference_conn, new_conn = patch_fake_db(monkeypatch)

    payload = tool.execute_person_profile_consumer(env_file=None, dsn_env="NEW_DSN", reference_dsn_env="REFERENCE_DSN", execute=True)

    assert payload["executed"] is True
    assert payload["write_db"] is True
    assert payload["executed_counts"] == {"retrieval_v3.person_profiles": 2}
    assert new_conn.committed is True
    insert_statements = [statement for statement in new_conn.statements if "insert into retrieval_v3.person_profiles" in statement]
    assert len(insert_statements) == 2
