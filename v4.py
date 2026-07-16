from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from emperor_v4.eval import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
