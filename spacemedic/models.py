from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ScanItem:
    path: str
    name: str
    size: int
    kind: str = "folder"
    modified: float = 0.0
    category: str = "Other"
    risk: str = "review"
    reason: str = ""
    project_root: str = ""
    reclaimable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Project:
    root: str
    name: str
    ecosystem: str
    total_size: int = 0
    dependency_size: int = 0
    git_size: int = 0
    build_size: int = 0
    modified: float = 0.0
    artifacts: list[ScanItem] = field(default_factory=list)

    @property
    def reclaimable(self) -> int:
        return sum(a.size for a in self.artifacts if a.reclaimable)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["reclaimable"] = self.reclaimable
        return data


@dataclass(slots=True)
class ScanResult:
    root: str
    started: float
    finished: float = 0.0
    total_size: int = 0
    file_count: int = 0
    folder_count: int = 0
    errors: int = 0
    top_files: list[ScanItem] = field(default_factory=list)
    top_folders: list[ScanItem] = field(default_factory=list)
    cleanup: list[ScanItem] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    categories: dict[str, int] = field(default_factory=dict)
    extension_sizes: dict[str, int] = field(default_factory=dict)

    @property
    def reclaimable(self) -> int:
        # Cleanup entries are non-overlapping because scanner prunes recognized artifacts.
        return sum(x.size for x in self.cleanup if x.reclaimable)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "started": self.started,
            "finished": self.finished,
            "duration_seconds": max(0, self.finished - self.started),
            "total_size": self.total_size,
            "file_count": self.file_count,
            "folder_count": self.folder_count,
            "errors": self.errors,
            "reclaimable": self.reclaimable,
            "categories": self.categories,
            "extension_sizes": self.extension_sizes,
            "top_files": [x.to_dict() for x in self.top_files],
            "top_folders": [x.to_dict() for x in self.top_folders],
            "cleanup": [x.to_dict() for x in self.cleanup],
            "projects": [x.to_dict() for x in self.projects],
        }
