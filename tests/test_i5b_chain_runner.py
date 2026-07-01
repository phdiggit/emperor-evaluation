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
        cluster_log_path=Path("cluster.jsonl"),
        result_log_path=Path("result.jsonl"),
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
        cluster_log_path=Path("cluster.jsonl"),
        result_log_path=Path("result.jsonl"),
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
