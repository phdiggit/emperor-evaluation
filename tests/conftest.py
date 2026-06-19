import os
import shutil
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTEST_TMP_ROOT = ROOT / ".tmp"

PYTEST_TMP_ROOT.mkdir(exist_ok=True)
os.environ.setdefault("TMP", str(PYTEST_TMP_ROOT))
os.environ.setdefault("TEMP", str(PYTEST_TMP_ROOT))
os.environ.setdefault("TMPDIR", str(PYTEST_TMP_ROOT))
tempfile.tempdir = str(PYTEST_TMP_ROOT)


def pytest_sessionfinish(session, exitstatus) -> None:
    for path in [
        ROOT / "evidence_cache.sqlite",
        ROOT / ".pytest_cache",
        ROOT / "scripts" / "__pycache__",
        ROOT / "tests" / "__pycache__",
        PYTEST_TMP_ROOT,
    ]:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink()
