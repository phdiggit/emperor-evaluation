"""Static publication boundaries, using synthetic files rather than ruling snapshots."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "reader_build_site", Path(__file__).resolve().parents[1] / "reader/build_site.py")
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


def fixture_sources(root):
    paths = ["index.html", "reader/data/person-reading-notes.json",
             "reader/runtime.js", "reader/style.css", "reader/source-revision.json",
             "reader/private.template.html", "reader/authored.json", "reader/build.py"]
    paths += [f"reader/{name}" for name in site.GENERATED_PAGES]
    paths += [f"reader/data/{name}/synthetic.json" for name in site.DATA_DIRECTORIES]
    for name in paths:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name, encoding="utf-8")


def test_site_contains_all_runtime_outputs_and_no_authoring_sources(tmp_path):
    fixture_sources(tmp_path)
    output = site.stage_site(tmp_path)
    for name in site.GENERATED_PAGES:
        assert (output / "reader" / name).read_bytes() == (tmp_path / "reader" / name).read_bytes()
    for name in site.DATA_DIRECTORIES:
        assert (output / "reader/data" / name / "synthetic.json").is_file()
    for name in ("runtime.js", "style.css", "source-revision.json", "data/person-reading-notes.json"):
        assert (output / "reader" / name).is_file()
    for name in ("private.template.html", "authored.json", "build.py"):
        assert not (output / "reader" / name).exists()
    assert (output / ".nojekyll").is_file()
    (output / "stale.html").touch()
    site.stage_site(tmp_path)
    assert not (output / "stale.html").exists()


def test_missing_generated_page_preserves_previous_site(tmp_path):
    fixture_sources(tmp_path)
    output = site.stage_site(tmp_path)
    missing = site.GENERATED_PAGES[-1]
    (tmp_path / "reader" / missing).unlink()
    with pytest.raises(FileNotFoundError, match="Missing reader output"):
        site.stage_site(tmp_path)
    assert (output / "reader" / missing).is_file()
