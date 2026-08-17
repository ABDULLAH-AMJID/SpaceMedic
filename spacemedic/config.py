from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Settings:
    language: str = "en"
    theme: str = "hud"
    scan_workers: int = 0
    last_scan_path: str = ""
    onboarding_complete: bool = False
    confirm_destructive_actions: bool = True
    update_checks: bool = False  # Public edition is offline by default.


def settings_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / "SpaceMedic"
    path.mkdir(parents=True, exist_ok=True)
    return path / "settings.json"


def load() -> Settings:
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
        allowed = Settings.__dataclass_fields__
        settings = Settings(**{k: v for k, v in data.items() if k in allowed})
        if settings.theme == "dark":  # migrate pre-3.6 public builds to the new default
            settings.theme = "hud"
        return settings
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return Settings()


def save(settings: Settings) -> None:
    target = settings_path()
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(asdict(settings), indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temp, target)
