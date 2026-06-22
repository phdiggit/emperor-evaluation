from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from validate.validate_config_readability import *  # noqa: F403
from validate.validate_config_readability import main

if __name__ == "__main__":
    raise SystemExit(main())
