"""Build and stage the complete static reader without committing generated files."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
GENERATED_PAGES = (
    "index.html", "military.html",
    "first-item-a.html", "first-item-b1.html", "first-item-b2.html", "first-item-c.html",
    "second-item-b2.html", "second-item-c.html", "second-item-d.html",
    "third-item-c.html", "fourth-item-a.html", "fourth-item-b.html", "fourth-item-c.html",
)
DATA_DIRECTORIES = ("people", "first-item", "military", "third-item-c")


def stage_site(root: Path = ROOT) -> Path:
    """Copy only runtime assets; fail before replacing a site if inputs are missing."""
    root = root.resolve()
    reader = root / "reader"
    files = [root / "index.html", *(reader / name for name in GENERATED_PAGES),
             reader / "data/person-reading-notes.json"]
    directories = [reader / "data" / name for name in DATA_DIRECTORIES]
    for path in files:
        if not path.is_file():
            raise FileNotFoundError(f"Missing reader output: {path}; run python reader/build_site.py")
    for path in directories:
        if not path.is_dir() or not any(path.iterdir()):
            raise FileNotFoundError(f"Missing reader data: {path}; run python reader/build_site.py")
    files.extend(sorted(reader.glob("*.js")))
    files.extend(sorted(reader.glob("*.css")))
    identity = reader / "source-revision.json"
    if identity.is_file():
        files.append(identity)

    temporary_root = (root / ".tmp").resolve()
    output = root / ".tmp/pages-site"
    if temporary_root != root / ".tmp" or output.resolve() != temporary_root / "pages-site":
        raise ValueError("Pages staging directory must stay inside the workspace .tmp directory")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    for source in files:
        target = output / source.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    for source in directories:
        shutil.copytree(source, output / source.relative_to(root))
    (output / ".nojekyll").touch()
    return output


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-only", action="store_true",
                        help="Package already built and validated runtime files (used by CI)")
    args = parser.parse_args(argv)
    if not args.stage_only:
        for script, options in (
            ("build_military_archive.py", ()),
            ("build.py", ()),
            ("build_first_item_reader_cache.py", ()),
            ("build.py", ("--check",)),
            ("build_first_item_reader_cache.py", ("--check",)),
        ):
            subprocess.run([sys.executable, str(ROOT / "reader" / script), *options],
                           cwd=ROOT, check=True)
    print(f"Reader site staged: {stage_site()}")


if __name__ == "__main__":
    main()
