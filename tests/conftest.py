import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def pytest_sessionfinish(session, exitstatus) -> None:
    for path in [
        ROOT / "evidence_cache.sqlite",
        ROOT / ".pytest_cache",
        ROOT / "scripts" / "__pycache__",
        ROOT / "tests" / "__pycache__",
    ]:
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            path.unlink()
