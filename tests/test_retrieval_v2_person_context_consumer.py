from __future__ import annotations

import json
from pathlib import Path

from scripts.dev import retrieval_v2_person_context_consumer as tool


def person_row(name: str, object_id: int = 1) -> dict:
    return {
        "object_id": object_id,
        "object_code": f"OBJ-{object_id}",
        "object_identity_key": f"target|TGT|type|person|name|{name}",
        "canonical_name": name,
        "normalized_name": name,
        "identity_status": "active",
    }


def old_person_row(name: str, period: str, *, old_id: int = 10, note: str = "冯唐以谏议和边政判断见称。") -> dict:
    return {
        "old_obj_id": old_id,
        "old_name": name,
        "old_period": period,
        "old_note": note,
        "alias_text": "",
        "normalized_alias": "",
        "alias_kind": "",
    }


def old_emp_row(name: str = "刘恒", period: str = "西汉") -> dict:
    return {"name": name, "period": period, "title": "汉文帝"}


def target_context_row(*, role: str = "civil_delegate", object_id: int = 1, name: str = "冯唐", target: str = "刘恒") -> dict:
    return {
        "object_id": object_id,
        "object_code": f"OBJ-{object_id}",
        "object_identity_key": f"target|TGT|type|person|name|{name}",
        "canonical_name": name,
        "normalized_name": name,
        "target_object_id": 100 + object_id,
        "target_id": 20,
        "target_code": "TGT-I5B-LH",
        "emperor_name": target,
        "material_role": role,
        "link_count": 2,
    }


def test_build_context_plan_adds_old_period_affiliation_and_pending_role() -> None:
    plan = tool.build_context_plan(
        [person_row("冯唐", 1)],
        [old_person_row("冯唐", "西汉")],
        [old_emp_row()],
        [target_context_row(role="civil_delegate"), target_context_row(role="revoked_or_failed_delegate")],
    )

    assert plan["totals"]["person_objects"] == 1
    assert plan["totals"]["old_period_affiliations"] == 1
    assert plan["totals"]["target_service_affiliations"] == 1
    assert plan["totals"]["role_rows"] == 1
    assert plan["totals"]["missing_role_candidate"] == 0
    dynasty = [row for row in plan["affiliation_rows"] if row["affiliation_kind"] == "dynasty"][0]
    assert dynasty["dynasty_label"] == "西汉"
    assert dynasty["review_status"] == "accepted"
    assert dynasty["affiliation_basis"] == "冯唐以谏议和边政判断见称"
    service = [row for row in plan["affiliation_rows"] if row["affiliation_kind"] == "service"][0]
    assert service["review_status"] == "pending"
    assert service["affiliation_label"] == "刘恒评价语境"
    assert plan["role_rows"][0]["role_kind"] == "official"
    assert plan["role_rows"][0]["review_status"] == "pending"
    assert plan["role_rows"][0]["role_payload"]["ignored_material_roles"] == ["revoked_or_failed_delegate"]


def test_build_context_plan_does_not_guess_role_from_failed_delegate_only() -> None:
    plan = tool.build_context_plan(
        [person_row("某人", 1)],
        [],
        [old_emp_row()],
        [target_context_row(role="revoked_or_failed_delegate", name="某人")],
    )

    assert plan["totals"]["role_rows"] == 0
    assert plan["totals"]["missing_role_candidate"] == 1
    assert plan["review_needed"]["missing_role_candidate"][0]["material_roles"] == {"revoked_or_failed_delegate": 2}


def test_build_context_plan_marks_conflicting_old_period_for_review() -> None:
    plan = tool.build_context_plan(
        [person_row("姚崇", 1)],
        [old_person_row("姚崇", "唐", old_id=1), old_person_row("姚崇", "武周", old_id=2)],
        [],
        [],
    )

    assert plan["totals"]["conflicting_old_person_period"] == 1
    assert plan["totals"]["old_period_affiliations"] == 0
    assert plan["review_needed"]["old_period"][0]["periods"] == ["唐", "武周"]


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
            self.rows = [dict(row) for row in self.conn.old_person_rows]
            self.row = None
            return
        if "from public.emps" in lowered:
            self.rows = [dict(row) for row in self.conn.old_emp_rows]
            self.row = None
            return
        if "from retrieval_v2.objects" in lowered and "join retrieval_v2.target_objects" not in lowered:
            self.rows = [dict(row) for row in self.conn.person_rows]
            self.row = None
            return
        if "join retrieval_v2.target_objects" in lowered:
            self.rows = [dict(row) for row in self.conn.target_rows]
            self.row = None
            return
        if "insert into retrieval_v2.person_affiliations" in lowered or "insert into retrieval_v2.person_roles" in lowered:
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
        self.old_person_rows = [old_person_row("冯唐", "西汉")] if old else []
        self.old_emp_rows = [old_emp_row()] if old else []
        self.person_rows = [] if old else [person_row("冯唐", 1)]
        self.target_rows = [] if old else [target_context_row(role="civil_delegate")]
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
    new_conn = FakeConnection(old=False)
    monkeypatch.setattr(tool, "import_psycopg", lambda: (FakePsycopg(old_conn, new_conn), object()))
    monkeypatch.setattr(tool, "resolve_dsn", lambda env: "old-dsn" if env == "OLD_DSN" else "new-dsn")
    return old_conn, new_conn


def test_apply_defaults_to_db_backed_dry_run_without_writes(tmp_path: Path, monkeypatch, capsys) -> None:
    _old_conn, new_conn = patch_fake_db(monkeypatch)
    output_json = tmp_path / "contexts.json"
    output_md = tmp_path / "contexts.md"

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
    assert payload["totals"]["affiliation_rows"] == 2
    assert new_conn.rolled_back is True
    assert not any("insert into retrieval_v2.person_affiliations" in statement for statement in new_conn.statements)
    assert json.loads(capsys.readouterr().out)["totals"]["role_rows"] == 1


def test_execute_writes_affiliations_before_roles(monkeypatch) -> None:
    _old_conn, new_conn = patch_fake_db(monkeypatch)

    payload = tool.execute_person_context_consumer(env_file=None, dsn_env="NEW_DSN", old_dsn_env="OLD_DSN", execute=True)

    assert payload["executed"] is True
    assert payload["write_db"] is True
    assert payload["executed_counts"] == {
        "retrieval_v2.person_affiliations": 2,
        "retrieval_v2.person_roles": 1,
    }
    assert new_conn.committed is True
    insert_statements = [statement for statement in new_conn.statements if "insert into retrieval_v2." in statement]
    assert "insert into retrieval_v2.person_affiliations" in insert_statements[0]
    assert "insert into retrieval_v2.person_roles" in insert_statements[-1]
