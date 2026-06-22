from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if sys.path[:1] != [str(SCRIPTS_DIR)]:
    sys.path = [str(SCRIPTS_DIR), *[path for path in sys.path if path != str(SCRIPTS_DIR)]]

loaded_build = sys.modules.get("build")
loaded_build_paths = getattr(loaded_build, "__path__", [])
if loaded_build and not any(Path(path).resolve() == SCRIPTS_DIR / "build" for path in loaded_build_paths):
    sys.modules.pop("build", None)
    sys.modules.pop("build.build_db", None)

from build.build_db import *  # noqa: F403
from build.build_db import main

if __name__ == "__main__":
    raise SystemExit(main())
