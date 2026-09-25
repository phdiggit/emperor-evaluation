"""Packaging invariants, without pinning any person's adjudication or pool size."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import zipfile

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("evaluation_package", ROOT / "package_net_review.py")
packager = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(packager)


@pytest.fixture(scope="module")
def prepared():
    return packager.prepare(ROOT)


def test_sources_are_verbatim_and_contracts_are_complete(prepared):
    entries, manifest = prepared
    for item in manifest["files"]:
        content = (ROOT / item["path"]).read_bytes()
        assert entries[item["path"]] == content
        assert item["sha256"] == hashlib.sha256(content).hexdigest()
        assert item["bytes"] == len(content)
        assert item["transformation"] == "VERBATIM"
    assert manifest["file_count"] == len(manifest["files"])
    for directory in ("docs/项目总纲", "docs/分项规则", "docs/证据规则"):
        for path in (ROOT / directory).rglob("*.md"):
            if path.name != "README.md":
                assert path.relative_to(ROOT).as_posix() in entries
    assert set(entries) - {item["path"] for item in manifest["files"]} == {
        "00-使用说明.md", "文件清单.json",
    }


def test_current_system_entries_and_all_router_shards_are_present(prepared):
    entries, manifest = prepared
    project = yaml.safe_load(entries["config/project.yml"])
    impact = project["historical_impact_assessment"]
    profile = project["profile_assessment"]
    required = [impact[key] for key in ("contract", "calibration_document", "json", "markdown")]
    required.append(project["scoring_contract"]["composite_governance_context"])
    required += [profile[key] for key in ("contract", "manifest_json", "manifest_markdown", "summary_markdown")]
    for section in (*project["formal_settlements"].values(), *profile["settled_axes"].values()):
        required.extend(section[key] for key in ("json", "markdown") if key in section)
        required.extend(section.get("component_markdown", []))
    assert all(name in entries for name in required)
    routers = 0
    for name, content in entries.items():
        if not name.endswith(".json"):
            continue
        data = json.loads(content)
        if isinstance(data, dict) and data.get("schema_version") == packager.ROUTER_SCHEMA:
            routers += 1
            for route in data["routes"]:
                assert (Path(name).parent / route["path"]).as_posix() in entries
    assert routers == manifest["router_count"]


@pytest.mark.parametrize("package", ["contracts", "settlements"])
def test_net_packages_include_current_governance_context(package):
    project = yaml.safe_load((ROOT / "config/project.yml").read_text(encoding="utf-8"))
    context_path = project["scoring_contract"]["composite_governance_context"]
    paths = {path.relative_to(ROOT).as_posix() for path in packager.collect(ROOT, package)}
    assert context_path in paths


@pytest.mark.parametrize("package", ["all", "settlements"])
def test_composite_markdown_local_links_are_packaged(package):
    project = yaml.safe_load((ROOT / "config/project.yml").read_text(encoding="utf-8"))
    markdown = project["scoring_contract"]["composite_ranking_markdown"]
    selected = {path.relative_to(ROOT).as_posix() for path in packager.collect(ROOT, package)}
    assert markdown in selected
    for target in re.findall(r"\]\(([^)]+)\)", (ROOT / markdown).read_text(encoding="utf-8")):
        if target.startswith(("https://", "http://", "#")):
            continue
        resolved = (ROOT / markdown).parent.joinpath(target.split("#", 1)[0]).resolve()
        assert resolved.is_relative_to(ROOT)
        assert resolved.relative_to(ROOT).as_posix() in selected


@pytest.mark.parametrize("package", [kind for kind in packager.PACKAGE_KINDS if kind != "all"])
def test_optional_packages_are_subsets_of_complete_package(package, prepared):
    entries, _ = prepared
    paths = packager.collect(ROOT, package)
    assert paths
    assert all(path.relative_to(ROOT).as_posix() in entries for path in paths)
    formal_roots = {path.relative_to(ROOT).parts[2] for path in paths
                    if path.is_relative_to(ROOT / "docs/评分结算")}
    if package.endswith("contract") or package == "contracts":
        assert not formal_roots
    else:
        expected = {"settlements": "净收益", "profile-settlements": "人物画像",
                    "historical-impact-settlements": "历史影响"}[package]
        assert formal_roots == {expected}


def test_missing_router_shard_fails_collection(monkeypatch, prepared):
    entries, _ = prepared
    router_name, router = next(
        (name, json.loads(content)) for name, content in entries.items()
        if name.endswith(".json") and isinstance(json.loads(content), dict)
        and json.loads(content).get("schema_version") == packager.ROUTER_SCHEMA
    )
    missing = (Path(router_name).parent / router["routes"][0]["path"]).as_posix()
    original = packager.source_path

    def unavailable(root, relative):
        if relative == missing:
            raise FileNotFoundError(missing)
        return original(root, relative)

    monkeypatch.setattr(packager, "source_path", unavailable)
    with pytest.raises(FileNotFoundError):
        packager.collect(ROOT)


def test_zip_is_deterministic_and_preserves_bytes(tmp_path, monkeypatch):
    entries = {"合同.md": "# 原始合同\r\n\r\n完整例外与输出约束。\r\n".encode("utf-8"),
               "data.json": b'{"synthetic": true}\n'}
    manifest = {"file_count": len(entries), "uncompressed_source_bytes": sum(map(len, entries.values())),
                "router_count": 0}
    monkeypatch.setattr(packager, "prepare", lambda root, package: (entries, manifest))
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    packager.build(tmp_path, first)
    packager.build(tmp_path, second)
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert set(archive.namelist()) == set(entries)
        assert all(archive.read(name) == content for name, content in entries.items())


def test_source_paths_cannot_escape_root(tmp_path):
    with pytest.raises(ValueError, match="来源路径非法"):
        packager.source_path(tmp_path, "../outside.md")
