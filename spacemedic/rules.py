from __future__ import annotations

import json
import os
from pathlib import Path

ALLOWED_RISKS = {"safe", "review", "system"}


def user_rules_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / "SpaceMedic"
    path.mkdir(parents=True, exist_ok=True)
    return path / "cleanup_rules.json"


def bundled_rules_path() -> Path:
    return Path(__file__).with_name("cleanup_rules.json")


def load_cache_rules() -> tuple[list[tuple], list[str]]:
    specs: list[tuple] = []
    errors: list[str] = []
    for path in (bundled_rules_path(), user_rules_path()):
        if not path.exists(): continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list): raise ValueError("root must be a list")
            for index, row in enumerate(data):
                if not isinstance(row, dict): raise ValueError(f"rule {index} must be an object")
                env = str(row.get("env", "")).upper()
                relative = str(row.get("path", ""))
                label = str(row.get("label", ""))
                risk = str(row.get("risk", "review")).lower()
                reason = str(row.get("reason", "Community cleanup rule"))
                direct = bool(row.get("direct_cleanup", False))
                if not env or not relative or not label or risk not in ALLOWED_RISKS:
                    raise ValueError(f"rule {index} has invalid required fields")
                # Rules may only be relative to a known environment root; absolute/traversal paths are rejected.
                normalized = relative.replace("\\", "/")
                if os.path.isabs(relative) or ".." in normalized.split("/"):
                    raise ValueError(f"rule {index} path must be relative and cannot traverse parents")
                if risk == "system": direct = False
                specs.append((env, relative, label, risk, reason, direct))
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f"{path}: {exc}")
    # Exact duplicate rules are collapsed.
    unique = {(x[0], x[1].casefold(), x[2].casefold()): x for x in specs}
    return list(unique.values()), errors
