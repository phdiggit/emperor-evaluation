from __future__ import annotations

import sys
from pathlib import Path

_IS_MAIN = __name__ == "__main__"
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from export import export_md as _export_md

globals().update(_export_md.__dict__)
sys.modules[__name__] = _export_md
if _IS_MAIN:
    raise SystemExit(_export_md.main())
