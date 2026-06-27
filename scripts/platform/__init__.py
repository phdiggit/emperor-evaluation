"""Runtime skeleton for PostgreSQL-backed jobs and RabbitMQ-style delivery."""

from pathlib import Path


_POST_G10_S1_RETIRED_PATH = Path(__file__).resolve().parent / "_retired" / "post_g10_s1"
if _POST_G10_S1_RETIRED_PATH.is_dir():
    # Keep retired audit modules importable for historical tests without exposing them as CLI routes.
    __path__.append(str(_POST_G10_S1_RETIRED_PATH))  # type: ignore[name-defined]
