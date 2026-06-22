from __future__ import annotations
import sys
from pathlib import Path

_IS_MAIN = __name__ == "__main__"
_LEGACY_MODULE_NAME = __name__
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
from validate import validate_all as _validate_all

if _IS_MAIN:
    raise SystemExit(_validate_all.main())
globals().update(_validate_all.__dict__)
sys.modules[_LEGACY_MODULE_NAME] = _validate_all
