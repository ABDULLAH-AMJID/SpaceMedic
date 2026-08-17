from __future__ import annotations

import hashlib
import os
from collections import defaultdict
from dataclasses import dataclass
from threading import Event
from typing import Callable


@dataclass(slots=True)
class DuplicateGroup:
    size: int
    digest: str
    paths: list[str]

    @property
    def reclaimable(self) -> int:
        return self.size * max(0, len(self.paths) - 1)


def _sample(path: str, size: int) -> bytes:
    with open(path, "rb") as f:
        first = f.read(65536)
        if size > 131072:
            f.seek(max(0, size - 65536))
            return first + f.read(65536)
        return first


def _hash(path: str, cancel: Event) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while not cancel.is_set():
            block = f.read(1024 * 1024)
            if not block: break
            digest.update(block)
    return digest.hexdigest()


def find_duplicates(root: str, min_size: int = 1024 * 1024, cancel: Event | None = None,
                    progress: Callable[[str, int], None] | None = None) -> tuple[list[DuplicateGroup], int]:
    cancel = cancel or Event()
    by_size: dict[int, list[str]] = defaultdict(list)
    seen_file_ids: set[tuple[int, int]] = set()
    errors = count = 0
    for current, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(current, d))]
        if cancel.is_set(): break
        for name in files:
            path = os.path.join(current, name)
            try:
                st = os.stat(path, follow_symlinks=False)
                identity = (st.st_dev, st.st_ino)
                if identity in seen_file_ids:
                    continue  # hard link: same allocated bytes, not a reclaimable duplicate
                seen_file_ids.add(identity)
                if st.st_size >= min_size: by_size[st.st_size].append(path)
                count += 1
                if progress and count % 500 == 0: progress(path, count)
            except OSError: errors += 1
    sampled: dict[tuple[int, bytes], list[str]] = defaultdict(list)
    for size, paths in by_size.items():
        if len(paths) < 2: continue
        for path in paths:
            if cancel.is_set(): break
            try: sampled[(size, hashlib.sha256(_sample(path, size)).digest())].append(path)
            except OSError: errors += 1
    exact: dict[tuple[int, str], list[str]] = defaultdict(list)
    for (size, _), paths in sampled.items():
        if len(paths) < 2: continue
        for path in paths:
            if cancel.is_set(): break
            try: exact[(size, _hash(path, cancel))].append(path)
            except OSError: errors += 1
    groups = [DuplicateGroup(size, digest, paths) for (size, digest), paths in exact.items() if len(paths) > 1]
    groups.sort(key=lambda x: x.reclaimable, reverse=True)
    return groups, errors
