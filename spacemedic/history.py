from __future__ import annotations

import json
import os
import time
from pathlib import Path
from threading import Lock

_lock = Lock()


def history_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / "SpaceMedic"
    path.mkdir(parents=True, exist_ok=True)
    return path / "history.jsonl"


def record(action: str, **details) -> None:
    row = {"time": time.time(), "action": action, **details}
    with _lock:
        with history_path().open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load(limit: int = 500) -> list[dict]:
    try:
        lines = history_path().read_text(encoding="utf-8").splitlines()[-limit:]
        return [json.loads(x) for x in reversed(lines) if x.strip()]
    except (OSError, json.JSONDecodeError):
        return []
