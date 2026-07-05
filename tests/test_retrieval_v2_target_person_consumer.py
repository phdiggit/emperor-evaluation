from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_target_person_consumer as tool


def target_row(name: str = "李世民", *, target_id: int = 1, item_code: str = "I5B") -> dict:
    return {
        "target_id": target_id,
        "target_code": f"TGT-{target_id}",
        "emperor_name": name,
        "item_code": item_code,
        "target_status": "active",
        "target_payload": {},
    }


def old_emp_row(name: str = "李世民", period: str = "唐", title: str = "唐太宗") -> dict:
    return {"name": name, "period": period, "title": title}


def test_build_target_person_plan_creates_profile_role_and_dynasty_affiliation() -> None:
    plan = tool.build_target_person_plan([target_row()], [old_emp_row()])

    assert plan["totals"]["target_rows"] == 1
    assert plan["totals"]["profile_rows"] == 1
    assert plan["totals"]["dynasty_affiliation_rows"] == 1
    assert plan["totals"]["emperor_role_rows"] == 1
    assert plan["totals"]["missing_emperor_period"] == 0
    assert plan["object_rows"][0]["canonical_name"] == "李世民"
    assert plan["target_object_rows"][0]["object_role"] == "target_emperor"
    assert plan["profile_rows"][0]["review_status"] == "accepted"
    assert plan["profile_rows"][0]["talent_grade"] is None
    assert plan["profile_rows"][0]["talent_grade_basis"] == "李世民，当前评价项目标皇帝；朝代为唐；称号为唐太宗。"
    assert plan["role_rows"][0]["role_kind"] == "emperor"
    assert plan["role_rows"][0]["dynasty_label"] == "唐"


def test_build_target_person_plan_omits_english_title_from_chinese_basis() -> None:
    plan = tool.build_target_person_plan([target_row("朱瞻基")], [old_emp_row("朱瞻基", "明", "Ming Xuanzong")])

    basis = plan["profile_rows"][0]["talent_grade_basis"]
    assert basis == "朱瞻基，当前评价项目标皇帝；朝代为明。"
    assert "Ming" not in basis
    assert plan["role_rows"][0]["role_title"] == ""


def test_build_target_person_plan_reports_missing_period_without_blocking_profile() -> None:
    plan = tool.build_target_person_plan([target_row("李亨")], [])

    assert plan["totals"]["profile_rows"] == 1
    assert plan["totals"]["dynasty_affiliation_rows"] == 0
    assert plan["totals"]["missing_emperor_period"] == 1
    assert plan["review_needed"]["missing_emperor_period"][0]["emperor_name"] == "李亨"


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
        if "from public.emps" in lowered:
            self.rows = [old_emp_row()]
            self.row = None
            return
        if "from retrieval_v2.retrieval_targets" in lowered:
            self.rows = [target_row()]
            self.row = None
            return
        if "insert into retrieval_v2." in lowered:
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
    def __init__(self, *, old: bool = False) -> None:
        self.old = old
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
    def __init__(self, old_conn: FakeConnection, new_conn: FakeConnection) -> None:
        self.old_conn = old_conn
        self.new_conn = new_conn

    def connect(self, dsn: str, *args, **kwargs) -> FakeConnection:
        return self.old_conn if dsn == "old-dsn" else self.new_conn


def patch_fake_db(monkeypatch) -> tuple[FakeConnection, FakeConnection]:
    old_conn = FakeConnection(old=True)
    new_conn = FakeConnection()
    monkeypatch.setattr(tool, "import_psycopg", lambda: (FakePsycopg(old_conn, new_conn), object()))
    monkeypatch.setattr(tool, "resolve_dsn", lambda env: "old-dsn" if env == "OLD_DSN" else "new-dsn")
    return old_conn, new_conn


def test_apply_defaults_to_db_backed_dry_run_without_writes(tmp_path: Path, monkeypatch, capsys) -> None:
    _old_conn, new_conn = patch_fake_db(monkeypatch)
    output_json = tmp_path / "targets.json"
    output_md = tmp_path / "targets.md"

    assert tool.main([
        "apply",
        "--old-dsn-env",
        "OLD_DSN",
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
    assert payload["totals"]["profile_rows"] == 1
    assert new_conn.rolled_back is True
    assert not any("insert into retrieval_v2.objects" in statement for statement in new_conn.statements)
    assert json.loads(capsys.readouterr().out)["totals"]["emperor_role_rows"] == 1


def test_execute_writes_objects_before_profiles_and_roles(monkeypatch) -> None:
    _old_conn, new_conn = patch_fake_db(monkeypatch)

    payload = tool.execute_target_person_consumer(env_file=None, dsn_env="NEW_DSN", old_dsn_env="OLD_DSN", item_code="I5B", execute=True)

    assert payload["executed"] is True
    assert payload["executed_counts"]["retrieval_v2.objects"] == 1
    assert payload["executed_counts"]["retrieval_v2.person_profiles"] == 1
    assert payload["executed_counts"]["retrieval_v2.person_roles"] == 1
    assert new_conn.committed is True
    inserts = [statement for statement in new_conn.statements if "insert into retrieval_v2." in statement]
    assert "insert into retrieval_v2.objects" in inserts[0]
    assert "insert into retrieval_v2.person_roles" in inserts[-1]
    role_statement = inserts[-1]
    assert "coalesce(nullif(excluded.dynasty_label, ''), retrieval_v2.person_roles.dynasty_label)" in role_statement
    assert "role_payload = retrieval_v2.person_roles.role_payload || excluded.role_payload" in role_statement
