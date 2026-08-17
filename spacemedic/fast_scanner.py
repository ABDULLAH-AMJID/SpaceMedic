from __future__ import annotations

import csv
import os
import shutil
import subprocess
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from threading import Event
from typing import Callable

from .models import Project, ScanItem, ScanResult
from .scanner import ARTIFACTS, PROJECT_MARKERS, DiskScanner


def find_wiztree() -> str | None:
    candidates = [shutil.which("WizTree64.exe"), shutil.which("WizTree.exe")]
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            candidates += [os.path.join(base, "WizTree", "WizTree64.exe"), os.path.join(base, "WizTree", "WizTree.exe")]
    return next((os.path.abspath(x) for x in candidates if x and os.path.isfile(x)), None)


def available() -> tuple[bool, str]:
    exe = find_wiztree()
    if exe: return True, exe
    return False, "WizTree was not found. SpaceMedic does not bundle or download it; install it separately and review its licence."


def _field(row: dict, *names: str) -> str:
    normalized = {k.casefold().replace(" ", "").replace("(", "").replace(")", ""): v for k, v in row.items() if k}
    for name in names:
        key = name.casefold().replace(" ", "").replace("(", "").replace(")", "")
        if key in normalized: return str(normalized[key] or "")
    return ""


def _integer(value: str) -> int:
    try: return int(value.replace(",", "").strip())
    except (ValueError, AttributeError): return 0


def scan(root: str, cancel: Event | None = None, progress: Callable[[str, int, int], None] | None = None) -> ScanResult:
    """Use a user-installed WizTree CLI as an optional MFT-backed provider.

    No executable is downloaded or redistributed. If schema validation fails, this raises and the
    caller should offer the built-in scanner instead.
    """
    exe = find_wiztree()
    if not exe: raise RuntimeError(available()[1])
    cancel = cancel or Event()
    result = ScanResult(root=os.path.abspath(root), started=time.time())
    fd, csv_path = tempfile.mkstemp(prefix="spacemedic-wiztree-", suffix=".csv")
    os.close(fd)
    try:
        args = [exe, root, f"/export={csv_path}", "/admin=1", "/exportfolders=1", "/exportfiles=1",
                "/exportallsizes=1", "/exportsplitfilename=1", "/exportUTCTime=1"]
        proc = subprocess.Popen(args)
        while proc.poll() is None:
            if cancel.wait(0.2):
                proc.terminate(); raise RuntimeError("Fast scan cancelled")
        if proc.returncode != 0 or not os.path.getsize(csv_path): raise RuntimeError(f"WizTree export failed with code {proc.returncode}")
        top_files: list[ScanItem] = []
        top_folders: list[ScanItem] = []
        categories: defaultdict[str, int] = defaultdict(int)
        extensions: defaultdict[str, int] = defaultdict(int)
        markers: dict[str, str] = {}
        artifact_rows: list[tuple[str, int]] = []
        with open(csv_path, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames: raise RuntimeError("WizTree CSV had no header")
            for index, row in enumerate(reader, 1):
                if cancel.is_set(): raise RuntimeError("Fast scan cancelled")
                full = _field(row, "Full Path")
                if not full:
                    root_part = _field(row, "Root")
                    folder, filename = _field(row, "Folder", "Path"), _field(row, "File Name", "Filename", "Name")
                    bits = [x for x in (root_part, folder, filename) if x]
                    full = os.path.join(*bits) if bits else ""
                if not full: continue
                size = _integer(_field(row, "Size Bytes", "Size (Bytes)", "Size"))
                attrs = _field(row, "Attributes")
                is_dir = "D" in attrs.upper() or full.endswith(("\\", "/")) or _field(row, "File Count", "Files") != ""
                path = os.path.normpath(full.rstrip("\\/"))
                name = os.path.basename(path) or path
                if is_dir:
                    result.folder_count += 1
                    top_folders.append(ScanItem(path, name, size, kind="folder"))
                    if name.casefold() in ARTIFACTS: artifact_rows.append((path, size))
                else:
                    result.file_count += 1
                    ext = Path(name).suffix.casefold() or "[no extension]"
                    extensions[ext] += size
                    categories[DiskScanner._file_category(ext)] += size
                    top_files.append(ScanItem(path, name, size, kind="file", category=DiskScanner._file_category(ext)))
                    if name in PROJECT_MARKERS: markers[os.path.dirname(path)] = PROJECT_MARKERS[name]
                    elif name.casefold().endswith((".sln", ".csproj")): markers[os.path.dirname(path)] = ".NET"
                if progress and index % 10000 == 0: progress(path, result.file_count, result.folder_count)
        if not top_files and not top_folders: raise RuntimeError("WizTree CSV schema was not recognized")
        top_files.sort(key=lambda x: x.size, reverse=True); top_folders.sort(key=lambda x: x.size, reverse=True)
        result.top_files, result.top_folders = top_files[:100], top_folders[:100]
        root_row = next((x for x in top_folders if os.path.normcase(x.path) == os.path.normcase(os.path.abspath(root))), None)
        result.total_size = root_row.size if root_row else sum(x.size for x in top_files)
        projects = {p: Project(p, os.path.basename(p), eco, total_size=next((x.size for x in top_folders if os.path.normcase(x.path)==os.path.normcase(p)), 0)) for p, eco in markers.items()}
        for path, size in artifact_rows:
            owner = max((p for p in projects if os.path.normcase(path).startswith(os.path.normcase(p) + os.sep)), key=len, default="")
            if not owner: continue
            name = os.path.basename(path).casefold(); cat, risk, regen, reason = ARTIFACTS[name]
            item = ScanItem(path, os.path.basename(path), size, category=cat, risk=risk, reason=reason, project_root=owner, reclaimable=regen)
            projects[owner].artifacts.append(item); result.cleanup.append(item)
            if name in {"node_modules", ".venv", "venv", "env"}: projects[owner].dependency_size += size
            elif name == ".git": projects[owner].git_size += size
            else: projects[owner].build_size += size
        result.projects = sorted(projects.values(), key=lambda x: x.total_size, reverse=True)
        result.cleanup.sort(key=lambda x: x.size, reverse=True)
        result.categories = dict(sorted(categories.items(), key=lambda x: x[1], reverse=True))
        result.extension_sizes = dict(sorted(extensions.items(), key=lambda x: x[1], reverse=True)[:100])
        result.finished = time.time()
        return result
    finally:
        try: os.remove(csv_path)
        except OSError: pass
