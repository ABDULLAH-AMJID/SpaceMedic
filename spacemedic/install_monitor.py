from __future__ import annotations

import gzip
import json
import os
import subprocess
import time
from pathlib import Path
from threading import Event
from typing import Callable

Progress = Callable[[str, int], None]
MAX_ENTRIES = 600_000


def monitor_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / "SpaceMedic" / "install-monitor"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _roots() -> list[str]:
    specs = [
        ("PROGRAMFILES", ""), ("PROGRAMFILES(X86)", ""), ("PROGRAMDATA", ""),
        ("LOCALAPPDATA", ""), ("APPDATA", ""),
        ("USERPROFILE", "AppData/LocalLow"), ("USERPROFILE", "Desktop"),
    ]
    result = []
    for env, rel in specs:
        base = os.environ.get(env)
        if not base: continue
        path = os.path.normpath(os.path.join(base, *rel.split("/"))) if rel else os.path.normpath(base)
        if os.path.isdir(path) and os.path.normcase(path) not in map(os.path.normcase, result): result.append(path)
    return result


def _registry_snapshot() -> list[str]:
    if os.name != "nt": return []
    lines: list[str] = []
    for key in (r"HKCU\Software", r"HKLM\Software"):
        try:
            result = subprocess.run(["reg.exe", "query", key, "/s"], capture_output=True, text=True, timeout=120,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            # Registry is analysis-only. Keep deterministic nonblank lines, capped for memory safety.
            lines.extend(x.rstrip() for x in result.stdout.splitlines() if x.strip())
            if len(lines) >= 250_000: break
        except (OSError, subprocess.SubprocessError): pass
    return sorted(set(lines[:250_000]))


def take_snapshot(name: str, cancel: Event | None = None, progress: Progress | None = None) -> Path:
    cancel = cancel or Event()
    files: dict[str, list[int]] = {}
    count = 0
    exclusions = {"temp", "cache", "code cache", "gpucache", "$recycle.bin", "system volume information", "windowsapps"}
    for root in _roots():
        for current, dirs, names in os.walk(root, followlinks=False):
            if cancel.is_set() or count >= MAX_ENTRIES: break
            dirs[:] = [d for d in dirs if d.casefold() not in exclusions and not os.path.islink(os.path.join(current, d))]
            for filename in names:
                path = os.path.join(current, filename)
                try:
                    st = os.stat(path, follow_symlinks=False)
                    files[os.path.normcase(path)] = [st.st_size, int(st.st_mtime_ns)]
                    count += 1
                    if progress and count % 1000 == 0: progress(path, count)
                    if count >= MAX_ENTRIES: break
                except OSError: pass
    payload = {
        "name": name, "time": time.time(), "roots": _roots(), "truncated": count >= MAX_ENTRIES,
        "files": files, "registry": _registry_snapshot(),
        "note": "Registry differences are report-only and are never automatically deleted."
    }
    path = monitor_dir() / f"{int(payload['time'])}-{name}.json.gz"
    with gzip.open(path, "wt", encoding="utf-8") as f: json.dump(payload, f, ensure_ascii=False)
    return path


def compare(before_path: str, after_path: str) -> dict:
    with gzip.open(before_path, "rt", encoding="utf-8") as f: before = json.load(f)
    with gzip.open(after_path, "rt", encoding="utf-8") as f: after = json.load(f)
    old, new = before["files"], after["files"]
    created = [{"path": p, "size": values[0]} for p, values in new.items() if p not in old]
    modified = [{"path": p, "before_size": old[p][0], "after_size": values[0]} for p, values in new.items() if p in old and old[p] != values]
    removed = [p for p in old if p not in new]
    old_reg, new_reg = set(before.get("registry", [])), set(after.get("registry", []))
    report = {
        "created": sorted(created, key=lambda x: x["size"], reverse=True), "modified": modified,
        "removed": removed, "registry_added_report_only": sorted(new_reg - old_reg),
        "registry_removed_report_only": sorted(old_reg - new_reg),
        "truncated": before.get("truncated") or after.get("truncated"),
        "warning": "A changed item is not proof of exclusive app ownership. Registry changes are never auto-removed. Review all trace data."
    }
    output = monitor_dir() / f"trace-{int(time.time())}.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["report_path"] = str(output)
    return report
