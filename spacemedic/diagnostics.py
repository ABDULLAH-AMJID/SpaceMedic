from __future__ import annotations

import json
import os
import platform
import re
import sys
import time
import zipfile
from pathlib import Path

from . import __version__
from .fast_scanner import available as fast_available
from .history import load as load_history


def _redact(value):
    home = str(Path.home())
    if isinstance(value, str):
        value = value.replace(home, "%USERPROFILE%")
        value = re.sub(r"C:\\Users\\[^\\\s]+", r"C:\\Users\\<redacted>", value, flags=re.I)
        value = re.sub(r"(?i)\b[A-Z]:\\[^,;\]\}\n\r]+", "<local-path>", value)
        value = re.sub(r"\\\\[^\\\s]+\\[^,;\]\}\n\r]+", "<network-path>", value)
        return value
    if isinstance(value, list): return [_redact(x) for x in value]
    if isinstance(value, dict): return {k: _redact(v) for k, v in value.items()}
    return value


def create_bundle(destination: str) -> str:
    ok, fast_detail = fast_available()
    payload = {
        "generated_at": time.time(), "spacemedic_version": __version__, "python": sys.version,
        "platform": platform.platform(), "machine": platform.machine(), "windows_version": platform.version(),
        "fast_backend_available": ok, "fast_backend": _redact(fast_detail),
        "history_last_100_redacted": _redact(load_history(100)),
        "privacy": "Absolute local/network paths are redacted. No file contents, installed-app list, browser history, project source, registry dump or credentials are included. Review diagnostics.json before sharing."
    }
    destination = os.path.abspath(destination)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("diagnostics.json", json.dumps(payload, indent=2, ensure_ascii=False))
        z.writestr("README.txt", "Review diagnostics.json before sharing. This bundle is intended for SpaceMedic performance testing.\n")
    return destination
