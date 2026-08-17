from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Insight:
    category: str
    name: str
    value: str
    detail: str
    severity: str = "info"


def _file_size(path: str) -> int:
    try: return os.path.getsize(path)
    except OSError: return 0


def system_storage() -> list[Insight]:
    if os.name != "nt": return []
    drive = os.environ.get("SYSTEMDRIVE", "C:") + "\\"
    rows = []
    for name, detail in [
        ("hiberfil.sys", "Hibernate/Fast Startup file; disable only if you accept losing both features."),
        ("pagefile.sys", "Virtual memory; do not delete manually."),
        ("swapfile.sys", "Windows app memory backing; do not delete manually."),
        ("MEMORY.DMP", "Full crash dump; retain while diagnosing blue screens."),
    ]:
        size = _file_size(os.path.join(drive, name)) if name != "MEMORY.DMP" else _file_size(os.path.join(os.environ.get("SYSTEMROOT", "C:\\Windows"), name))
        if size: rows.append(Insight("System storage", name, str(size), detail, "review"))
    total, used, free = shutil.disk_usage(drive)
    rows.append(Insight("Drive", drive, str(free), f"{used} bytes used of {total}", "warning" if free < 15 * 1024**3 else "info"))
    return rows


def developer_platforms() -> list[Insight]:
    rows: list[Insight] = []
    if os.name != "nt": return rows
    commands = [
        ("Docker", ["docker", "system", "df"], "Images, containers, volumes and build cache. Use Docker prune commands, never delete its data files."),
        ("WSL", ["wsl.exe", "--list", "--verbose"], "Installed distributions. VHDX files must be managed through WSL, not deleted manually."),
    ]
    for name, command, detail in commands:
        if not shutil.which(command[0]): continue
        try:
            out = subprocess.run(command, capture_output=True, text=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
            text = (out.stdout or out.stderr).strip()
            rows.append(Insight("Developer platform", name, text[:1500], detail, "review"))
        except (OSError, subprocess.SubprocessError): pass
    roots = [os.environ.get("USERPROFILE", ""), os.environ.get("PUBLIC", "")]
    extensions = {".vhd", ".vhdx", ".vmdk", ".qcow2"}
    for root in roots:
        if not root or not os.path.isdir(root): continue
        for current, dirs, files in os.walk(root):
            if len(Path(current).parts) - len(Path(root).parts) > 5:
                dirs[:] = []; continue
            for file in files:
                if Path(file).suffix.lower() in extensions:
                    path = os.path.join(current, file)
                    try:
                        size = os.path.getsize(path)
                        if size >= 512 * 1024**2: rows.append(Insight("Virtual disk", path, str(size), "Manage through its VM/WSL application.", "review"))
                    except OSError: pass
    return rows


def startup_inventory() -> list[Insight]:
    if os.name != "nt": return []
    script = r'''$r=@(); Get-CimInstance Win32_StartupCommand -ErrorAction SilentlyContinue | % {$r += [pscustomobject]@{Type='Startup';Name=$_.Name;Value=$_.Command;Detail=$_.Location}}; Get-CimInstance Win32_Service -ErrorAction SilentlyContinue | ? {$_.StartMode -eq 'Auto'} | % {$r += [pscustomobject]@{Type='Service';Name=$_.Name;Value=$_.PathName;Detail=$_.State}}; Get-ScheduledTask -ErrorAction SilentlyContinue | ? {$_.State -ne 'Disabled'} | Select-Object -First 300 | % {$r += [pscustomobject]@{Type='Task';Name=$_.TaskName;Value=$_.TaskPath;Detail=$_.State.ToString()}}; $r|ConvertTo-Json -Compress'''
    try:
        out = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], capture_output=True, text=True, timeout=45, creationflags=subprocess.CREATE_NO_WINDOW)
        if not out.stdout.strip(): return []
        data = json.loads(out.stdout)
        if isinstance(data, dict): data = [data]
        return [Insight(str(x.get("Type", "Background")), str(x.get("Name", "")), str(x.get("Value", "")), str(x.get("Detail", "")), "review") for x in data]
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError): return []
