from __future__ import annotations

import os
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event, Lock

from .models import ScanItem, ScanResult
from .scanner import DiskScanner, _is_reparse_or_link


class ParallelDiskScanner:
    """Dependency-free accelerated scanner.

    It scans independent top-level branches concurrently and merges exact byte/count results.
    This is not raw MFT access, so it works without third-party software and on non-NTFS paths too.
    """

    def __init__(self, workers: int | None = None, top_limit: int = 100, min_large_file: int = 100 * 1024 * 1024):
        cpu = os.cpu_count() or 4
        self.workers = workers or max(2, min(8, cpu))
        self.top_limit = top_limit
        self.min_large_file = min_large_file

    def scan(self, root: str, cancel: Event | None = None, progress=None) -> ScanResult:
        cancel = cancel or Event()
        root = os.path.abspath(root)
        result = ScanResult(root=root, started=time.time())
        dirs: list[str] = []
        direct_files: list[ScanItem] = []
        categories: defaultdict[str, int] = defaultdict(int)
        extensions: defaultdict[str, int] = defaultdict(int)
        try:
            with os.scandir(root) as entries:
                for entry in entries:
                    try:
                        if _is_reparse_or_link(entry): continue
                        if entry.is_dir(follow_symlinks=False): dirs.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            st = entry.stat(follow_symlinks=False)
                            ext = os.path.splitext(entry.name)[1].casefold() or "[no extension]"
                            category = DiskScanner._file_category(ext)
                            result.total_size += st.st_size; result.file_count += 1
                            categories[category] += st.st_size; extensions[ext] += st.st_size
                            if st.st_size >= self.min_large_file:
                                direct_files.append(ScanItem(entry.path, entry.name, st.st_size, kind="file", modified=st.st_mtime, category=category))
                    except OSError: result.errors += 1
        except OSError as exc:
            raise RuntimeError(f"Cannot read scan root: {exc}") from exc

        if not dirs:
            return DiskScanner(self.top_limit, self.min_large_file).scan(root, cancel, progress)

        states: dict[str, tuple[int, int, str]] = {path: (0, 0, path) for path in dirs}
        lock = Lock()

        def callback(branch: str):
            def update(path: str, files: int, folders: int):
                with lock: states[branch] = (files, folders, path)
                if progress:
                    with lock:
                        progress(path, result.file_count + sum(x[0] for x in states.values()), len(dirs) + sum(x[1] for x in states.values()))
            return update

        branch_results: list[ScanResult] = []
        with ThreadPoolExecutor(max_workers=min(self.workers, len(dirs)), thread_name_prefix="SpaceMedicScan") as pool:
            futures = {pool.submit(DiskScanner(self.top_limit, self.min_large_file).scan, path, cancel, callback(path)): path for path in dirs}
            for future in as_completed(futures):
                if cancel.is_set():
                    for pending in futures: pending.cancel()
                    break
                try: branch_results.append(future.result())
                except Exception: result.errors += 1

        top_files = direct_files[:]
        top_folders: list[ScanItem] = []
        for branch in branch_results:
            result.total_size += branch.total_size
            result.file_count += branch.file_count
            result.folder_count += 1 + branch.folder_count
            result.errors += branch.errors
            top_files.extend(branch.top_files)
            top_folders.append(ScanItem(branch.root, os.path.basename(branch.root), branch.total_size, kind="folder"))
            top_folders.extend(branch.top_folders)
            result.cleanup.extend(branch.cleanup)
            result.projects.extend(branch.projects)
            for key, value in branch.categories.items(): categories[key] += value
            for key, value in branch.extension_sizes.items(): extensions[key] += value
        result.top_files = sorted(top_files, key=lambda x: x.size, reverse=True)[:self.top_limit]
        result.top_folders = sorted(top_folders, key=lambda x: x.size, reverse=True)[:self.top_limit]
        result.cleanup.sort(key=lambda x: x.size, reverse=True)
        result.projects.sort(key=lambda x: x.total_size, reverse=True)
        result.categories = dict(sorted(categories.items(), key=lambda x: x[1], reverse=True))
        result.extension_sizes = dict(sorted(extensions.items(), key=lambda x: x[1], reverse=True)[:100])
        result.finished = time.time()
        return result
