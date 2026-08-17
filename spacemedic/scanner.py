from __future__ import annotations

import glob
import heapq
import os
import queue
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable, Iterable

from .models import Project, ScanItem, ScanResult
from .rules import load_cache_rules

Progress = Callable[[str, int, int], None]

PROJECT_MARKERS = {
    "package.json": "Node.js",
    "pyproject.toml": "Python",
    "requirements.txt": "Python",
    "Pipfile": "Python",
    "poetry.lock": "Python",
    "Cargo.toml": "Rust",
    "go.mod": "Go",
    "pom.xml": "Java/Maven",
    "build.gradle": "Java/Gradle",
    "build.gradle.kts": "Java/Gradle",
    "composer.json": "PHP",
    "Gemfile": "Ruby",
}

# name: (category, risk, regenerable, explanation)
ARTIFACTS = {
    "node_modules": ("Project dependencies", "review", True, "Can be restored with npm/yarn/pnpm install"),
    ".venv": ("Python environment", "review", True, "Virtual environment; restore from lock/requirements"),
    "venv": ("Python environment", "review", True, "Virtual environment; restore from requirements"),
    "env": ("Python environment", "review", True, "Possible virtual environment; verify before cleanup"),
    "__pycache__": ("Build/cache", "safe", True, "Python bytecode cache; recreated automatically"),
    ".pytest_cache": ("Build/cache", "safe", True, "pytest cache; recreated automatically"),
    ".mypy_cache": ("Build/cache", "safe", True, "mypy cache; recreated automatically"),
    ".ruff_cache": ("Build/cache", "safe", True, "Ruff cache; recreated automatically"),
    ".next": ("Build output", "safe", True, "Next.js output; recreated by build/dev"),
    ".nuxt": ("Build output", "safe", True, "Nuxt output; recreated by build/dev"),
    ".svelte-kit": ("Build output", "safe", True, "SvelteKit output; recreated by build/dev"),
    ".turbo": ("Build/cache", "safe", True, "Turborepo cache; recreated automatically"),
    ".parcel-cache": ("Build/cache", "safe", True, "Parcel cache; recreated automatically"),
    ".vite": ("Build/cache", "safe", True, "Vite cache; recreated automatically"),
    "target": ("Build output", "review", True, "Often Rust/Maven build output; verify project type"),
    "dist": ("Build output", "review", True, "Generated output in most projects; verify before cleanup"),
    "build": ("Build output", "review", True, "Generated output in most projects; verify before cleanup"),
    "obj": ("Build output", "safe", True, ".NET intermediate build output"),
    "bin": ("Build output", "review", True, "Often .NET build output; may contain manually placed files"),
    ".gradle": ("Build/cache", "safe", True, "Project-local Gradle cache"),
    ".vs": ("IDE cache", "safe", True, "Visual Studio project cache"),
    ".idea": ("IDE data", "review", False, "IDE settings; small and not automatically safe"),
    "coverage": ("Build output", "safe", True, "Test coverage output"),
    ".git": ("Git history", "review", False, "Repository history; optimize with git gc, do not delete casually"),
}

# env, path/glob, label, safety, explanation, direct_recycle_allowed
# Windows-managed items are measured but deliberately routed to Microsoft cleanup tools.
GLOBAL_CACHE_SPECS = [
    ("LOCALAPPDATA", "Temp", "User temporary files", "safe", "App temporary files; close apps first; in-use files are skipped", True),
    ("LOCALAPPDATA", "CrashDumps", "Application crash dumps", "safe", "Diagnostic dumps from crashed apps; keep only when troubleshooting", True),
    ("LOCALAPPDATA", "Microsoft/Windows/WER/ReportArchive", "Archived Windows error reports", "safe", "Past per-user crash reports; no longer needed unless troubleshooting", True),
    ("LOCALAPPDATA", "Microsoft/Windows/WER/ReportQueue", "Queued Windows error reports", "review", "Pending per-user crash reports; keep if you want them submitted/analyzed", True),
    ("LOCALAPPDATA", "D3DSCache", "DirectX shader cache", "safe", "Graphics shader cache; games rebuild it and may stutter briefly once", True),
    ("LOCALAPPDATA", "NVIDIA/DXCache", "NVIDIA DirectX cache", "safe", "GPU shader cache; recreated by the driver", True),
    ("LOCALAPPDATA", "NVIDIA/GLCache", "NVIDIA OpenGL cache", "safe", "GPU shader cache; recreated by the driver", True),
    ("LOCALAPPDATA", "Microsoft/Windows/INetCache", "Windows internet cache", "safe", "Temporary web content; recreated when needed", True),
    ("LOCALAPPDATA", "Google/Chrome/User Data/*/Cache", "Chrome browser cache", "safe", "Cached images/files only; close Chrome before cleanup", True),
    ("LOCALAPPDATA", "Google/Chrome/User Data/*/Code Cache", "Chrome code cache", "safe", "Compiled web code cache; close Chrome first", True),
    ("LOCALAPPDATA", "Microsoft/Edge/User Data/*/Cache", "Edge browser cache", "safe", "Cached images/files only; close Edge before cleanup", True),
    ("LOCALAPPDATA", "Microsoft/Edge/User Data/*/Code Cache", "Edge code cache", "safe", "Compiled web code cache; close Edge first", True),
    ("LOCALAPPDATA", "Mozilla/Firefox/Profiles/*/cache2", "Firefox browser cache", "safe", "Cached web content; close Firefox before cleanup", True),
    ("APPDATA", "discord/Cache", "Discord cache", "safe", "Temporary app content; close Discord first", True),
    ("APPDATA", "discord/Code Cache", "Discord code cache", "safe", "Compiled app cache; close Discord first", True),
    ("LOCALAPPDATA", "pip/Cache", "pip cache", "safe", "Download/build cache; pip recreates it", True),
    ("LOCALAPPDATA", "npm-cache", "npm cache", "safe", "Package download cache; npm recreates it", True),
    ("USERPROFILE", ".cache/uv", "uv cache", "safe", "uv package cache; recreated on demand", True),
    ("USERPROFILE", ".cache/huggingface", "Hugging Face models", "review", "Models re-download; consider bandwidth before cleanup", True),
    ("USERPROFILE", ".cache/torch", "PyTorch cache", "review", "Models/checkpoints may re-download", True),
    ("USERPROFILE", ".cache/whisper", "Whisper models", "review", "Models re-download; consider bandwidth", True),
    ("USERPROFILE", ".ollama/models", "Ollama models", "review", "Deleting removes locally available models", True),
    ("USERPROFILE", ".cargo/registry/cache", "Cargo cache", "safe", "Crate archives can be downloaded again", True),
    ("USERPROFILE", ".gradle/caches", "Gradle cache", "safe", "Dependencies and build cache can be recreated", True),
    ("USERPROFILE", ".m2/repository", "Maven repository", "review", "Dependencies re-download; offline builds may be affected", True),
    ("USERPROFILE", ".nuget/packages", "NuGet packages", "review", "Global packages can be restored", True),
    ("LOCALAPPDATA", "ms-playwright", "Playwright browsers", "review", "Browser binaries can be reinstalled", True),
    ("LOCALAPPDATA", "puppeteer/Cache", "Puppeteer browsers", "review", "Browser binaries can be reinstalled", True),
    ("APPDATA", "Code/Cache", "VS Code cache", "safe", "Editor cache; recreated automatically", True),
    ("APPDATA", "Code/CachedData", "VS Code cached data", "safe", "Editor cache; recreated automatically", True),
    ("PROGRAMDATA", "Microsoft/Windows/WER/ReportArchive", "System WER archive", "system", "System crash reports; clean through Windows Temporary files/Disk Cleanup", False),
    ("PROGRAMDATA", "Microsoft/Windows/WER/ReportQueue", "System WER queue", "system", "Queued system reports; use Windows cleanup rather than forced deletion", False),
    ("SYSTEMROOT", "Temp", "Windows temporary files", "system", "Windows-managed temporary files; use Storage or Disk Cleanup", False),
    ("SYSTEMROOT", "Minidump", "System error minidumps", "system", "Useful for blue-screen diagnosis; Disk Cleanup can remove them", False),
    ("SYSTEMROOT", "MEMORY.DMP", "System memory dump", "system", "Large blue-screen dump; keep for diagnosis or remove with Disk Cleanup", False),
    ("SYSTEMDRIVE", "Windows.old", "Previous Windows installation", "system", "Enables OS rollback; remove only through Windows Temporary files after system is stable", False),
    ("SYSTEMDRIVE", "$WINDOWS.~BT", "Windows upgrade files", "system", "Upgrade/setup files; remove through Windows Temporary files/Disk Cleanup", False),
]

PROTECTED_PARTS = {"windows", "program files", "program files (x86)", "programdata", "system32", "winsxs"}


def format_bytes(value: int) -> str:
    size = float(max(0, value))
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if size < 1024 or unit == "PB":
            return f"{size:.0f} {unit}" if unit in ("B", "KB") else f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


def _is_reparse_or_link(entry: os.DirEntry) -> bool:
    try:
        if entry.is_symlink():
            return True
        attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
        return bool(attrs & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT (junctions/cloud links)
    except OSError:
        return True


def directory_size(path: str, cancel: Event | None = None) -> tuple[int, int, int, int]:
    total = files = folders = errors = 0
    stack = [path]
    while stack:
        if cancel and cancel.is_set():
            break
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if _is_reparse_or_link(entry):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            folders += 1
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            files += 1
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        errors += 1
        except OSError:
            errors += 1
    return total, files, folders, errors


def known_global_caches(cancel: Event | None = None, progress: Progress | None = None) -> list[ScanItem]:
    """Measure known junk/cache locations, including wildcard browser profiles.

    `reclaimable` here also means direct Recycle-Bin cleanup is allowed. Windows-managed
    findings are informational and must be handled through Storage/Disk Cleanup/DISM.
    """
    found: list[ScanItem] = []
    seen: set[str] = set()
    community_specs, _rule_errors = load_cache_rules()
    for env, relative, label, risk, reason, direct_cleanup in GLOBAL_CACHE_SPECS + community_specs:
        base = os.environ.get(env)
        if not base:
            continue
        if os.name == "nt" and base.endswith(":"):
            base += "\\"
        pattern = os.path.normpath(os.path.join(base, *relative.replace("\\", "/").split("/")))
        matches = glob.glob(pattern) if glob.has_magic(pattern) else [pattern]
        for path in matches:
            path = os.path.normpath(path)
            key = os.path.normcase(path)
            if key in seen or not os.path.exists(path):
                continue
            seen.add(key)
            if progress:
                progress(f"Measuring {label}", 0, 0)
            if os.path.isdir(path):
                size, _, _, _ = directory_size(path, cancel)
            else:
                try: size = os.path.getsize(path)
                except OSError: size = 0
            if size:
                profile = os.path.basename(os.path.dirname(path)) if glob.has_magic(pattern) else ""
                display = f"{label} ({profile})" if profile else label
                category = "Windows-managed junk" if risk == "system" else ("Browser/App caches" if any(x in label.lower() for x in ("browser", "discord", "code cache", "internet")) else "Developer/App caches")
                found.append(ScanItem(path, display, size, category=category, risk=risk,
                                      reason=reason, reclaimable=direct_cleanup))
    return sorted(found, key=lambda x: x.size, reverse=True)


class DiskScanner:
    """Conservative recursive scanner. It never follows symlinks/reparse points or deletes data."""

    def __init__(self, top_limit: int = 100, min_large_file: int = 100 * 1024 * 1024):
        self.top_limit = top_limit
        self.min_large_file = min_large_file

    def scan(self, root: str, cancel: Event | None = None, progress: Progress | None = None) -> ScanResult:
        cancel = cancel or Event()
        root = os.path.abspath(root)
        result = ScanResult(root=root, started=time.time())
        file_heap: list[tuple[int, int, ScanItem]] = []
        folder_heap: list[tuple[int, int, ScanItem]] = []
        seq = 0
        projects: dict[str, Project] = {}
        ext_sizes: defaultdict[str, int] = defaultdict(int)
        categories: defaultdict[str, int] = defaultdict(int)
        last_update = 0.0

        # Iterative post-order traversal: (path, visited, project_root)
        stack: list[tuple[str, bool, str]] = [(root, False, "")]
        sizes: dict[str, int] = {}
        counts: dict[str, tuple[int, int]] = {}
        project_hint: dict[str, str] = {}

        while stack and not cancel.is_set():
            path, visited, inherited_project = stack.pop()
            if visited:
                total = 0
                direct_files = direct_folders = 0
                try:
                    with os.scandir(path) as entries:
                        for entry in entries:
                            try:
                                if _is_reparse_or_link(entry):
                                    continue
                                if entry.is_dir(follow_symlinks=False):
                                    total += sizes.get(entry.path, 0)
                                    direct_folders += 1 + counts.get(entry.path, (0, 0))[1]
                                    direct_files += counts.get(entry.path, (0, 0))[0]
                                elif entry.is_file(follow_symlinks=False):
                                    stat = entry.stat(follow_symlinks=False)
                                    total += stat.st_size
                                    direct_files += 1
                            except OSError:
                                result.errors += 1
                except OSError:
                    result.errors += 1
                sizes[path] = total
                counts[path] = (direct_files, direct_folders)
                seq += 1
                item = ScanItem(path, os.path.basename(path) or path, total, modified=self._mtime(path))
                self._push(folder_heap, (total, seq, item))
                project_root = project_hint.get(path, inherited_project)
                if path in projects:
                    projects[path].total_size = total
                    projects[path].modified = self._mtime(path)
                name_key = os.path.basename(path).lower()
                if name_key in ARTIFACTS and project_root:
                    cat, risk, regen, reason = ARTIFACTS[name_key]
                    art = ScanItem(path, os.path.basename(path), total, category=cat, risk=risk,
                                   reason=reason, project_root=project_root, reclaimable=regen)
                    result.cleanup.append(art)
                    project = projects.get(project_root)
                    if project:
                        project.artifacts.append(art)
                        if name_key == ".git": project.git_size += total
                        elif name_key in {"node_modules", ".venv", "venv", "env"}: project.dependency_size += total
                        else: project.build_size += total
                now = time.time()
                if progress and now - last_update > 0.08:
                    progress(path, result.file_count, result.folder_count)
                    last_update = now
                continue

            try:
                names: list[str] = []
                dirs: list[os.DirEntry[str]] = []
                files: list[os.DirEntry[str]] = []
                with os.scandir(path) as entries:
                    for entry in entries:
                        try:
                            if _is_reparse_or_link(entry):
                                continue
                            names.append(entry.name)
                            if entry.is_dir(follow_symlinks=False): dirs.append(entry)
                            elif entry.is_file(follow_symlinks=False): files.append(entry)
                        except OSError:
                            result.errors += 1
                ecosystem = self._detect_project(names)
                current_project = inherited_project
                if ecosystem:
                    current_project = path
                    if path not in projects:
                        projects[path] = Project(path, os.path.basename(path) or path, ecosystem)
                project_hint[path] = current_project
                stack.append((path, True, current_project))
                for entry in reversed(dirs):
                    result.folder_count += 1
                    stack.append((entry.path, False, current_project))
                for entry in files:
                    try:
                        st = entry.stat(follow_symlinks=False)
                        result.file_count += 1
                        ext = Path(entry.name).suffix.lower() or "[no extension]"
                        ext_sizes[ext] += st.st_size
                        category = self._file_category(ext)
                        categories[category] += st.st_size
                        if st.st_size >= self.min_large_file:
                            seq += 1
                            fi = ScanItem(entry.path, entry.name, st.st_size, kind="file", modified=st.st_mtime,
                                          category=category, risk="review", reason="Large file")
                            self._push(file_heap, (st.st_size, seq, fi))
                    except OSError:
                        result.errors += 1
            except OSError:
                result.errors += 1
                sizes[path] = 0
                counts[path] = (0, 0)

        result.total_size = sizes.get(root, 0)
        result.top_files = [x[2] for x in sorted(file_heap, reverse=True)]
        result.top_folders = [x[2] for x in sorted(folder_heap, reverse=True) if x[2].path != root]
        # Keep cleanup targets non-overlapping so reclaimable totals are not double-counted.
        result.cleanup.sort(key=lambda x: (len(Path(x.path).parts), -x.size))
        roots: list[str] = []
        unique_cleanup: list[ScanItem] = []
        for item in result.cleanup:
            norm = os.path.normcase(os.path.abspath(item.path))
            if any(norm == r or norm.startswith(r + os.sep) for r in roots):
                continue
            roots.append(norm)
            unique_cleanup.append(item)
        result.cleanup = sorted(unique_cleanup, key=lambda x: x.size, reverse=True)
        allowed = {os.path.normcase(x.path) for x in result.cleanup}
        for project in projects.values():
            project.artifacts = [a for a in project.artifacts if os.path.normcase(a.path) in allowed]
            project.dependency_size = sum(a.size for a in project.artifacts if os.path.basename(a.path).lower() in {"node_modules", ".venv", "venv", "env"})
            project.git_size = sum(a.size for a in project.artifacts if os.path.basename(a.path).lower() == ".git")
            project.build_size = sum(a.size for a in project.artifacts if os.path.basename(a.path).lower() not in {"node_modules", ".venv", "venv", "env", ".git"})
        result.projects = sorted(projects.values(), key=lambda x: x.total_size, reverse=True)
        result.categories = dict(sorted(categories.items(), key=lambda x: x[1], reverse=True))
        result.extension_sizes = dict(sorted(ext_sizes.items(), key=lambda x: x[1], reverse=True)[:100])
        result.finished = time.time()
        return result

    def _push(self, heap: list, value: tuple) -> None:
        if len(heap) < self.top_limit:
            heapq.heappush(heap, value)
        elif value[0] > heap[0][0]:
            heapq.heapreplace(heap, value)

    @staticmethod
    def _detect_project(names: Iterable[str]) -> str:
        name_set = set(names)
        for marker, ecosystem in PROJECT_MARKERS.items():
            if marker in name_set:
                return ecosystem
        if any(n.lower().endswith((".sln", ".csproj")) for n in name_set):
            return ".NET"
        return ""

    @staticmethod
    def _file_category(ext: str) -> str:
        if ext in {".mp4", ".mkv", ".avi", ".mov", ".webm"}: return "Videos"
        if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".raw", ".psd"}: return "Images"
        if ext in {".zip", ".7z", ".rar", ".tar", ".gz", ".iso"}: return "Archives/ISOs"
        if ext in {".exe", ".msi", ".dll", ".sys"}: return "Programs/System"
        if ext in {".vhd", ".vhdx", ".vmdk", ".qcow2"}: return "Virtual machines"
        if ext in {".log", ".dmp", ".tmp"}: return "Logs/temporary"
        if ext in {".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go", ".java", ".cs", ".cpp", ".h"}: return "Source code"
        if ext in {".doc", ".docx", ".pdf", ".xlsx", ".pptx", ".txt"}: return "Documents"
        return "Other"

    @staticmethod
    def _mtime(path: str) -> float:
        try: return os.stat(path, follow_symlinks=False).st_mtime
        except OSError: return 0.0
