import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUTO_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B三人自动结算草案.md"
AUTO_RULES_EXPORT_PATH = ROOT / "exports" / "markdown_views" / "第五项B自动结算规则敏感点清单.md"

AUTO_SPEC = importlib.util.spec_from_file_location(
    "export_i5b_auto_adjudication",
    ROOT / "scripts" / "export_i5b_auto_adjudication.py",
)
assert AUTO_SPEC is not None
auto = importlib.util.module_from_spec(AUTO_SPEC)
assert AUTO_SPEC.loader is not None
AUTO_SPEC.loader.exec_module(auto)


def run_script(script_name: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script_name)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_export_i5b_auto_adjudication_generates_rule_views() -> None:
    result = run_script("export_i5b_auto_adjudication.py")

    assert result.returncode == 0, result.stdout + result.stderr
    assert AUTO_EXPORT_PATH.exists()
    assert AUTO_RULES_EXPORT_PATH.exists()

    auto_content = AUTO_EXPORT_PATH.read_text(encoding="utf-8")
    rules_content = AUTO_RULES_EXPORT_PATH.read_text(encoding="utf-8")

    assert "第五项B三人自动结算草案" in auto_content
    assert "高位强正，上探极正候选" in auto_content
    assert "强正受压制，不上探极正" in auto_content
    assert "中正受中负压制" in auto_content
    assert "RULE-I5B-BOUNDARY-MIDNEG-NO-BLOCK" in rules_content
    assert "RULE-I5B-SINGLE-DIMENSION-STRONG-POS-NO-EXTREME" in rules_content
    assert "RULE-I5B-ADJACENT-STRONG-NEG-RESIDUAL" in rules_content
    assert "RULE-I5B-STRONG-NEG-CORE-VS-STRONG-POS" in rules_content


def test_auto_adjudication_hits_four_required_rule_cases() -> None:
    config = auto.read_json(auto.CONFIG_PATH)
    evidence_cards = auto.read_jsonl(auto.DATA_DIR / "evidence_cards.jsonl")
    evidence_clusters = auto.read_jsonl(auto.DATA_DIR / "evidence_clusters.jsonl")
    evidence_lookup = {row["evidence_id"]: row for row in evidence_cards if row.get("evidence_id")}
    reports = {
        person: auto.evaluate_person(person, evidence_clusters, evidence_lookup)
        for person in config["targets"]
    }
    cluster_lookup = {row["cluster_id"]: row for row in evidence_clusters if row.get("cluster_id")}

    assert reports["李世民"]["auto_band_direction"] == "高位强正，上探极正候选"
    assert reports["李世民"]["confidence"] == "high"
    assert "中负边界是否阻断极正" in [point["rule"] for point in reports["李世民"]["rule_sensitive_points"]]

    assert reports["刘秀"]["auto_band_direction"] == "强正受压制，不上探极正"
    assert reports["刘秀"]["confidence"] == "medium_high"
    assert "强负核心是否压制强正" in [point["rule"] for point in reports["刘秀"]["rule_sensitive_points"]]

    assert reports["刘庄"]["auto_band_direction"] == "中正受中负压制"
    assert reports["刘庄"]["confidence"] == "medium"
    assert reports["刘庄"]["cross_item_split_residual_level"] == "medium"

    liuzhuang_cluster = auto.evaluate_cluster(
        cluster_lookup["ADJ-I5B-LIUZHUANG-NEG-TALENT-SAFETY-001"],
        evidence_lookup,
    )
    assert liuzhuang_cluster["residual_level"] == "medium"
    assert liuzhuang_cluster["auto_cluster_result"] == "中负边界"

