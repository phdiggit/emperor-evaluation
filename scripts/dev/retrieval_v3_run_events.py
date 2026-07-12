from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


class RunEventLogger:
    def __init__(self, path: Path, *, echo: bool = False) -> None:
        self.path = path
        self.echo = echo
        self._started = time.perf_counter()
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")

    def emit(self, event_type: str, **payload: Any) -> None:
        event = {
            "event": event_type,
            "elapsed_seconds": round(time.perf_counter() - self._started, 3),
            "ts": datetime.now().isoformat(timespec="seconds"),
        }
        event.update(payload)
        line = stable_json(event)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        if self.echo:
            target = payload.get("emperor_name") or payload.get("target_code") or ""
            phase = payload.get("phase") or payload.get("round") or ""
            print(f"[retrieval_v3] {event_type} {target} {phase}".rstrip(), file=sys.stderr)
