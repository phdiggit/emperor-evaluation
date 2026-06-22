import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
from validate.validate_i5b_cluster_adjudication_configs import *  # noqa: F403
from validate.validate_i5b_cluster_adjudication_configs import main

if __name__ == "__main__":
    raise SystemExit(main())
