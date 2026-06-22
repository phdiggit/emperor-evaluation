from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build.build_db import *  # noqa: F403
from build.build_db import main

if __name__ == "__main__":
    raise SystemExit(main())
