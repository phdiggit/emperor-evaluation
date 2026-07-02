from __future__ import annotations

import sys
from pathlib import Path

import psycopg
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev import source_excerpt_pool_lib as _impl
from scripts.dev.source_excerpt_pool_lib import *  # noqa: F401,F403
from scripts.dev.source_excerpt_pool_lib import builder, cache, cli, common, profile, reporting, wikisource
from scripts.dev.source_excerpt_pool_lib.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
