from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = ROOT / "scripts" / "dev" / "i5b_chain_runner.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("i5b_chain_runner_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_chain_inputs_derives_ordered_emperors(monkeypatch) -> None:
    tool = load_tool()
    monkeypatch.setattr(
        tool,
        "load_payloads",
        lambda path: (
            SimpleNamespace(emperor=SimpleNamespace(name="刘邦")),
            SimpleNamespace(emperor=SimpleNamespace(name="刘恒")),
        ),
    )
    monkeypatch.setattr(
        tool,
        "load_cluster_payload",
        lambda path: (
            "I5B",
            (
                SimpleNamespace(emperor="刘恒"),
                SimpleNamespace(emperor="刘彻"),
            ),
        ),
    )

    inputs = tool.load_chain_inputs(
        object_payload_path=Path("objects.json"),
        cluster_payload_path=Path("clusters.json"),
        emperors=(),
    )

    assert inputs.emperors == ("刘邦", "刘恒", "刘彻")
    assert inputs.cluster_item_code == "I5B"


def test_run_chain_dry_run_skips_write_stages(monkeypatch) -> None:
    tool = load_tool()
    calls = []
    monkeypatch.setattr(
        tool,
        "load_chain_inputs",
        lambda **kwargs: tool.ChainInputs(("刘邦",), ("payload",), "I5B", ("cluster",)),
    )
    monkeypatch.setattr(
        tool,
        "import_payloads",
        lambda payloads, dsn, *, dry_run: calls.append(("objects", dry_run)) or {"dry_run": dry_run},
    )
    monkeypatch.setattr(
        tool,
        "upsert_clusters",
        lambda **kwargs: calls.append(("clusters", kwargs["dry_run"])) or {"dry_run": kwargs["dry_run"]},
    )
    monkeypatch.setattr(
        tool,
        "calculate_item_results",
        lambda **kwargs: calls.append(("results", kwargs["dry_run"])) or {"dry_run": kwargs["dry_run"]},
    )

    report = tool.run_chain(
        dsn="postgresql://example",
        object_payload_path=Path("objects.json"),
        cluster_payload_path=Path("clusters.json"),
        emperors=(),
        item_code="I5B",
        cluster_formula="evidence_cluster_signal_v2",
        result_formula="item_result_formula_i5b_v6",
        dry_run=True,
        skip_object_import=False,
        skip_cluster_upsert=False,
        skip_results=False,
        skip_validation=False,
    )

    assert calls == [("objects", True), ("clusters", True), ("results", True)]
    assert report["validation"] is None


def test_run_chain_write_mode_dry_runs_before_writes(monkeypatch) -> None:
    tool = load_tool()
    calls = []
    monkeypatch.setattr(
        tool,
        "load_chain_inputs",
        lambda **kwargs: tool.ChainInputs(("刘邦",), ("payload",), "I5B", ("cluster",)),
    )
    monkeypatch.setattr(
        tool,
        "import_payloads",
        lambda payloads, dsn, *, dry_run: calls.append(("objects", dry_run)) or {"dry_run": dry_run},
    )
    monkeypatch.setattr(
        tool,
        "upsert_clusters",
        lambda **kwargs: calls.append(("clusters", kwargs["dry_run"])) or {"dry_run": kwargs["dry_run"]},
    )
    monkeypatch.setattr(
        tool,
        "calculate_item_results",
        lambda **kwargs: calls.append(("results", kwargs["dry_run"])) or {"dry_run": kwargs["dry_run"]},
    )
    monkeypatch.setattr(
        tool,
        "validate_chain",
        lambda **kwargs: {"ok": True, "emperors": kwargs["emperors"]},
    )

    report = tool.run_chain(
        dsn="postgresql://example",
        object_payload_path=Path("objects.json"),
        cluster_payload_path=Path("clusters.json"),
        emperors=(),
        item_code="I5B",
        cluster_formula="evidence_cluster_signal_v2",
        result_formula="item_result_formula_i5b_v6",
        dry_run=False,
        skip_object_import=False,
        skip_cluster_upsert=False,
        skip_results=False,
        skip_validation=False,
    )

    assert calls == [
        ("objects", True),
        ("objects", False),
        ("clusters", True),
        ("clusters", False),
        ("results", True),
        ("results", False),
    ]
    assert report["validation"] == {"ok": True, "emperors": ("刘邦",)}


def test_validate_chain_counts_clusters_after_grouping(monkeypatch) -> None:
    tool = load_tool()

    class FakeCursor:
        def __init__(self, columns, rows):
            self.description = [SimpleNamespace(name=column) for column in columns]
            self._rows = rows

        def fetchall(self):
            return self._rows

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, query, params):
            if "from v_emp_item_results_by_id" in query:
                return FakeCursor(
                    ["emperor", "item_code", "formula_code", "score", "score_rate", "tier", "tier_band", "updated_at"],
                    [("刘邦", "I5B", "item_result_formula_i5b_v6", "36.437", "0.8097", "优秀", "低段", "now")],
                )
            if "count(distinct sd.id)" in query:
                return FakeCursor(
                    ["emperor", "src_docs", "emp_objs", "obj_srcs", "obj_attrs"],
                    [("刘邦", 11, 12, 27, 2)],
                )
            if "from evd_clusters c" in query:
                return FakeCursor(
                    ["emperor", "rule_code", "positive_signal", "negative_signal", "cluster_direction"],
                    [
                        ("刘邦", "appointment_trust", "4.551", "0.000", "positive"),
                        ("刘邦", "team_building", "6.403", "0.000", "positive"),
                    ],
                )
            if "having count(os.id) = 0" in query:
                return FakeCursor(["emperor", "raw_object"], [])
            if "and not exists" in query:
                return FakeCursor(["emperor", "raw_object", "attr_code", "doc_id"], [])
            if "select distinct e.name as emperor" in query:
                return FakeCursor(["emperor", "raw_object", "note"], [("刘邦", "萧何", "汉初功臣")])
            raise AssertionError(query)

    monkeypatch.setattr(tool.psycopg, "connect", lambda dsn: FakeConnection())

    report = tool.validate_chain(dsn="postgresql://example", emperors=("刘邦",))

    assert report["ok"] is True
    assert report["cluster_count"] == 2
    assert report["cluster_count_by_emperor"] == {"刘邦": 2}
    assert report["clusters"]["刘邦"][0]["rule_code"] == "appointment_trust"
