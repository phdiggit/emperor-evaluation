from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dev.retrieval_v3_diagnostics_lib.actions import build_next_actions
from scripts.dev.retrieval_v3_diagnostics_lib.cli import build_parser, main
from scripts.dev.retrieval_v3_diagnostics_lib.orchestrator import fetch_db_report, fetch_report
from scripts.dev.retrieval_v3_diagnostics_lib.renderers import render_markdown
from scripts.dev.retrieval_v3_diagnostics_lib.score_chain import build_score_chain_observations, fetch_score_chain
from scripts.dev.retrieval_v3_diagnostics_lib.selectors import build_score_chain_selectors, score_chain_filter_values

__all__ = [
    "build_next_actions",
    "build_parser",
    "build_score_chain_observations",
    "build_score_chain_selectors",
    "fetch_db_report",
    "fetch_report",
    "fetch_score_chain",
    "main",
    "render_markdown",
    "score_chain_filter_values",
]

if __name__ == "__main__":
    raise SystemExit(main())
