from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from export.dimension_adapters.i5b_people_delegation import adapter as _adapter

main = _adapter.main

if __name__ != "__main__":
    sys.modules[__name__] = _adapter


if __name__ == "__main__":
    raise SystemExit(main())
