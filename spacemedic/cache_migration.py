from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from threading import Event
from typing import Callable

SUPPORTED = {
    "pip cache": "pip",
    "npm cache": "npm",
    "uv cache": "uv",
    "Hugging Face models": "huggingface",
    "Ollama models": "ollama",
}


def identify(label: str) -> str | None:
    for prefix, kind in SUPPORTED.items():
        if label.startswith(prefix): return kind
    return None


def migrate(source: str, label: str, destination_root: str, cancel: Event | None = None,
            progress: Callable[[str], None] | None = None) -> tuple[bool, str, str]:
    """Copy first, configure second, keep source for manual rollback/removal."""
    kind = identify(label)
    if not kind: return False, "This cache has no verified relocation adapter yet.", ""
    if not os.path.isdir(source): return False, "Source cache no longer exists.", ""
    cancel = cancel or Event()
    destination = os.path.abspath(os.path.join(destination_root, f"SpaceMedic-{kind}-cache"))
    try:
        if os.path.commonpath([os.path.abspath(source), destination]) == os.path.abspath(source):
            return False, "Destination cannot be inside the source cache.", ""
    except ValueError:
        pass  # Different Windows drives are expected for relocation.
    Path(destination).mkdir(parents=True, exist_ok=True)
    copied = 0
    try:
        for current, dirs, files in os.walk(source):
            if cancel.is_set(): return False, "Migration cancelled; source remains unchanged.", destination
            relative = os.path.relpath(current, source)
            target_dir = destination if relative == "." else os.path.join(destination, relative)
            Path(target_dir).mkdir(parents=True, exist_ok=True)
            for filename in files:
                src, dst = os.path.join(current, filename), os.path.join(target_dir, filename)
                shutil.copy2(src, dst)
                copied += os.path.getsize(dst)
                if progress and copied % (64 * 1024 * 1024) < os.path.getsize(dst): progress(dst)
        py_launcher = [shutil.which("py"), "-3"] if shutil.which("py") else [shutil.which("python") or "python"]
        commands = {
            "pip": py_launcher + ["-m", "pip", "config", "set", "global.cache-dir", destination],
            "npm": ["npm", "config", "set", "cache", destination, "--global"],
            "uv": ["setx", "UV_CACHE_DIR", destination],
            "huggingface": ["setx", "HF_HOME", destination],
            "ollama": ["setx", "OLLAMA_MODELS", destination],
        }
        command = commands[kind]
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        if result.returncode:
            return False, f"Files copied, but configuration failed: {result.stderr.strip()}", destination
        return True, "Copy and configuration succeeded. Restart terminals/apps, verify the new cache, then recycle the old source from SpaceMedic.", destination
    except (OSError, shutil.Error, subprocess.SubprocessError) as exc:
        return False, f"Migration stopped safely; source was not deleted: {exc}", destination
