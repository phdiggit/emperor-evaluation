from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if sys.path[:1] != [str(SCRIPTS_DIR)]:
    sys.path = [str(SCRIPTS_DIR), *[path for path in sys.path if path != str(SCRIPTS_DIR)]]

loaded_matrix = sys.modules.get("matrix")
loaded_matrix_paths = getattr(loaded_matrix, "__path__", [])
if loaded_matrix and not any(Path(path).resolve() == SCRIPTS_DIR / "matrix" for path in loaded_matrix_paths):
    sys.modules.pop("matrix", None)
    sys.modules.pop("matrix.run_matrix", None)

from matrix.run_matrix import *  # noqa: F403
from matrix.run_matrix import main

if __name__ == "__main__":
    raise SystemExit(main())
