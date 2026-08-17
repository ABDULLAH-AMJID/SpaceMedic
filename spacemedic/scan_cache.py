from __future__ import annotations

import gzip
import json
import os
import time
from pathlib import Path

from .models import ScanResult


def cache_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / "SpaceMedic" / "scans"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _root_key(root: str) -> str:
    import hashlib
    return hashlib.sha256(os.path.normcase(os.path.abspath(root)).encode("utf-8", "surrogatepass")).hexdigest()[:20]


def latest(root: str) -> dict | None:
    files = sorted(cache_dir().glob(f"{_root_key(root)}-*.json.gz"), reverse=True)
    if not files: return None
    try:
        with gzip.open(files[0], "rt", encoding="utf-8") as f: return json.load(f)
    except (OSError, json.JSONDecodeError): return None


def save(result: ScanResult, backend: str = "recursive") -> str:
    payload = result.to_dict()
    payload["backend"] = backend
    payload["saved_at"] = time.time()
    path = cache_dir() / f"{_root_key(result.root)}-{int(payload['saved_at'])}.json.gz"
    with gzip.open(path, "wt", encoding="utf-8", compresslevel=6) as f: json.dump(payload, f, ensure_ascii=False)
    # Keep five snapshots per root.
    for old in sorted(cache_dir().glob(f"{_root_key(result.root)}-*.json.gz"), reverse=True)[5:]:
        try: old.unlink()
        except OSError: pass
    return str(path)


def compare(previous: dict | None, current: ScanResult) -> dict:
    if not previous:
        return {"available": False, "total_delta": 0, "new_large": [], "grown": [], "removed": []}
    old_items = {x["path"]: int(x.get("size", 0)) for x in previous.get("top_files", []) + previous.get("top_folders", [])}
    now_items = {x.path: x.size for x in current.top_files + current.top_folders}
    new_large = [{"path": p, "size": s} for p, s in now_items.items() if p not in old_items]
    grown = [{"path": p, "delta": s - old_items[p]} for p, s in now_items.items() if p in old_items and s > old_items[p]]
    removed = [{"path": p, "previous_size": s} for p, s in old_items.items() if p not in now_items]
    return {
        "available": True, "previous_saved_at": previous.get("saved_at"),
        "total_delta": current.total_size - int(previous.get("total_size", 0)),
        "new_large": sorted(new_large, key=lambda x: x["size"], reverse=True)[:50],
        "grown": sorted(grown, key=lambda x: x["delta"], reverse=True)[:50],
        "removed": sorted(removed, key=lambda x: x["previous_size"], reverse=True)[:50],
    }
