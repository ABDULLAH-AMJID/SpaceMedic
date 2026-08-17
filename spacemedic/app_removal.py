from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from .models import ScanItem
from .scanner import directory_size
from .windows_tools import InstalledApp

# Names that are too generic to prove ownership of a folder.
GENERIC = {
    "app", "application", "apps", "client", "desktop", "software", "program", "programs", "tool", "tools",
    "studio", "service", "services", "update", "updater", "setup", "installer", "launcher", "manager", "runtime",
    "framework", "common", "shared", "data", "cache", "system", "windows", "microsoft", "package", "packages",
    "professional", "enterprise", "community", "edition", "helper", "support", "components", "company", "inc", "ltd"
}

# Deep integrations need their vendor removal utility; heuristic deletion can break boot/network/security/shared runtimes.
HIGH_RISK_TERMS = {
    "driver", "antivirus", "security", "endpoint", "firewall", "vpn", "virtual private", "disk encryption",
    "boot", "firmware", "chipset", "redistributable", "runtime", "framework", "visual c++", ".net", "sdk",
    "database server", "sql server", "hyper-v", "virtualbox", "vmware", "docker", "wsl", "printer", "scanner"
}

PROTECTED_BASENAMES = {
    "common files", "windowsapps", "windows", "system32", "syswow64", "installer", "packages", "microsoft",
    "intel", "amd", "nvidia corporation", "apple", "adobe", "oracle", "google", "mozilla"
}


@dataclass(slots=True)
class RemovalSession:
    app: dict
    created: float
    inventory: list[dict]
    warnings: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def normalize(text: str) -> str:
    return "".join(ch for ch in text.casefold() if ch.isalnum())


def _words(text: str) -> list[str]:
    cleaned = re.sub(r"[®™©]|\([^)]*\)|\b(?:x64|x86|64-bit|32-bit|version|ver)\b.*$", " ", text, flags=re.I)
    return [w.casefold() for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9+.-]*", cleaned)]


def aliases(app: InstalledApp) -> set[str]:
    words = [w for w in _words(app.name) if w not in GENERIC and not w.isdigit()]
    values = {normalize(app.name)}
    if words:
        values.add(normalize("".join(words)))
        # Product part after publisher, e.g. "Google Chrome" -> "chrome".
        pub_words = {normalize(w) for w in _words(app.publisher)}
        product = [w for w in words if normalize(w) not in pub_words]
        if product:
            values.add(normalize("".join(product)))
        if len(words) == 1:
            values.add(normalize(words[0]))
    return {x for x in values if len(x) >= 4 and x not in GENERIC}


def is_high_risk(app: InstalledApp) -> bool:
    text = f"{app.name} {app.publisher}".casefold()
    return any(term in text for term in HIGH_RISK_TERMS)


def _known_vendor_residuals(app: InstalledApp) -> list[tuple[str, str]]:
    """Exact vendor-documented residual locations; never fuzzy matches."""
    if "docker desktop" not in app.name.casefold():
        return []
    specs = [
        ("PROGRAMDATA", "Docker"), ("PROGRAMDATA", "DockerDesktop"),
        ("PROGRAMFILES", "Docker"), ("LOCALAPPDATA", "Docker"),
        ("APPDATA", "Docker"), ("APPDATA", "Docker Desktop"),
        ("USERPROFILE", ".docker"),
    ]
    found = []
    for env, relative in specs:
        base = os.environ.get(env)
        if base:
            found.append((os.path.normpath(os.path.join(base, relative)), "Docker's official Windows uninstall documentation lists this as a possible residual path"))
    return found


def _docker_wsl_registered() -> list[str]:
    if os.name != "nt": return []
    import subprocess
    try:
        result = subprocess.run(["wsl.exe", "--list", "--quiet"], capture_output=True, text=True, timeout=15,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        return [x.replace("\x00", "").strip() for x in result.stdout.splitlines() if "docker-desktop" in x.replace("\x00", "").casefold()]
    except (OSError, subprocess.SubprocessError):
        return []


def session_path() -> str:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / "SpaceMedic"
    path.mkdir(parents=True, exist_ok=True)
    return str(path / "last-uninstall-session.json")


def _claimed_by_other(path: str, app: InstalledApp, installed: Iterable[InstalledApp]) -> bool:
    target = os.path.normcase(os.path.abspath(path))
    for other in installed:
        if other is app or (other.name == app.name and other.version == app.version and other.registry_id == app.registry_id):
            continue
        if not other.install_location:
            continue
        claim = os.path.normcase(os.path.abspath(os.path.expandvars(other.install_location)))
        if claim == target or claim.startswith(target + os.sep) or target.startswith(claim + os.sep):
            return True
    return False


def _safe_exact_install_location(path: str) -> bool:
    if not path or not os.path.exists(path): return False
    absolute = os.path.abspath(os.path.expandvars(path)).rstrip("\\/")
    drive, tail = os.path.splitdrive(absolute)
    parts = [p for p in re.split(r"[\\/]+", tail) if p]
    if len(parts) < 2: return False
    lower = {p.casefold() for p in parts}
    if lower & {"windows", "system32", "syswow64", "common files", "windowsapps", "installer"}: return False
    if os.path.basename(absolute).casefold() in PROTECTED_BASENAMES: return False
    try:
        attrs = getattr(os.stat(absolute, follow_symlinks=False), "st_file_attributes", 0)
        if os.path.islink(absolute) or attrs & 0x400: return False
    except OSError:
        return False
    return True


def _candidate_roots() -> list[str]:
    env_rel = [
        ("LOCALAPPDATA", ""), ("APPDATA", ""), ("PROGRAMDATA", ""),
        ("USERPROFILE", "AppData/LocalLow"),
        ("PROGRAMFILES", ""), ("PROGRAMFILES(X86)", ""),
    ]
    result = []
    for env, rel in env_rel:
        base = os.environ.get(env)
        if base:
            path = os.path.normpath(os.path.join(base, *rel.split("/"))) if rel else os.path.normpath(base)
            if os.path.isdir(path): result.append(path)
    return list(dict.fromkeys(map(os.path.normcase, result)))


def capture_inventory(app: InstalledApp, installed: list[InstalledApp]) -> RemovalSession:
    """Inventory only high-confidence, app-specific paths *before* uninstall.

    This pre-uninstall snapshot is the core safety property: post-uninstall cleanup can only offer paths
    that both existed while the selected app was registered and still exist after its own uninstaller ran.
    """
    warnings: list[str] = []
    inventory: dict[str, dict] = {}
    names = aliases(app)
    risky = is_high_risk(app)
    if risky:
        warnings.append("Deep system integration detected. Use the publisher's removal/cleanup utility; automatic leftover cleanup is disabled.")
    if app.protected:
        warnings.append("Windows/publisher marks this package non-removable or no uninstaller is registered.")

    def add(path: str, confidence: str, reason: str, allow_program_area: bool = False):
        absolute = os.path.abspath(os.path.expandvars(path))
        sensitive = [os.environ.get(k, "") for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA")]
        allow_program_area = allow_program_area or any(
            root and (os.path.normcase(absolute) == os.path.normcase(root) or os.path.normcase(absolute).startswith(os.path.normcase(root) + os.sep))
            for root in sensitive
        )
        key = os.path.normcase(absolute)
        if key in inventory or not os.path.exists(absolute): return
        if _claimed_by_other(absolute, app, installed):
            warnings.append(f"Shared path skipped because another installed app claims it: {absolute}")
            return
        size, _, _, _ = directory_size(absolute) if os.path.isdir(absolute) else (os.path.getsize(absolute), 1, 0, 0)
        inventory[key] = {"path": absolute, "size": size, "confidence": confidence, "reason": reason,
                          "allow_program_area": allow_program_area}

    for vendor_path, vendor_reason in _known_vendor_residuals(app):
        add(vendor_path, "VENDOR-DOCUMENTED", vendor_reason, True)
    if _known_vendor_residuals(app):
        warnings.append("Docker residuals may contain all local containers, images, volumes and credentials. Removing them is destructive; back up anything important first.")

    if app.app_type == "Store/MSIX" and app.package_family_name:
        local = os.environ.get("LOCALAPPDATA", "")
        pkg = os.path.join(local, "Packages", app.package_family_name)
        add(pkg, "HIGH", "Exact MSIX package-family data captured before uninstall")
    elif not risky:
        install = os.path.expandvars(app.install_location.strip().strip('"')) if app.install_location else ""
        if _safe_exact_install_location(install) and not _claimed_by_other(install, app, installed):
            add(install, "HIGH", "Exact registered install location; no other installed app claims it", True)

        publisher_norm = normalize(app.publisher)
        for root in _candidate_roots():
            try:
                children = list(os.scandir(root))
            except OSError:
                continue
            for entry in children:
                try:
                    if not entry.is_dir(follow_symlinks=False): continue
                    direct_norm = normalize(entry.name)
                    if direct_norm in names and entry.name.casefold() not in PROTECTED_BASENAMES:
                        add(entry.path, "HIGH", "Folder name exactly matches the selected product")
                    # One vendor level deep, but only delete the product child—not the shared vendor folder.
                    if publisher_norm and direct_norm == publisher_norm:
                        try:
                            for sub in os.scandir(entry.path):
                                if sub.is_dir(follow_symlinks=False) and normalize(sub.name) in names:
                                    add(sub.path, "HIGH", "Exact product folder under exact publisher folder")
                        except OSError:
                            pass
                except OSError:
                    continue

        # Exact shortcuts only. They are small but commonly left behind.
        shortcut_roots = [
            os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
            os.path.join(os.environ.get("PROGRAMDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
            os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
            os.path.join(os.environ.get("PUBLIC", ""), "Desktop"),
        ]
        for root in shortcut_roots:
            if not os.path.isdir(root): continue
            for current, dirs, files in os.walk(root):
                dirs[:] = dirs[:20]
                for filename in files:
                    if filename.lower().endswith(".lnk") and normalize(Path(filename).stem) in names:
                        add(os.path.join(current, filename), "HIGH", "Shortcut name exactly matches the selected product")

    session = RemovalSession(asdict(app), time.time(), list(inventory.values()), warnings)
    with open(session_path(), "w", encoding="utf-8") as f:
        json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)
    return session


def load_session() -> RemovalSession | None:
    try:
        with open(session_path(), encoding="utf-8") as f: data = json.load(f)
        return RemovalSession(data["app"], float(data["created"]), list(data["inventory"]), list(data.get("warnings", [])))
    except (OSError, KeyError, ValueError, TypeError, json.JSONDecodeError):
        return None


def scan_session_leftovers(session: RemovalSession, currently_installed: list[InstalledApp]) -> tuple[list[ScanItem], list[str]]:
    app = InstalledApp(**session.app)
    warnings = list(session.warnings)
    # Exact identity check: never clean while the same product still appears installed.
    still = [x for x in currently_installed if (
        (app.registry_id and x.registry_id == app.registry_id) or
        (app.package_full_name and x.package_full_name == app.package_full_name)
    )]
    if still:
        warnings.append("The selected app still appears installed. Finish its uninstaller/reboot, refresh apps, then scan again.")
        return [], warnings

    existing_inventory = {os.path.normcase(os.path.abspath(x.get("path", ""))) for x in session.inventory if x.get("path")}
    for vendor_path, vendor_reason in _known_vendor_residuals(app):
        key = os.path.normcase(os.path.abspath(vendor_path))
        if key not in existing_inventory and os.path.exists(vendor_path):
            size, _, _, _ = directory_size(vendor_path) if os.path.isdir(vendor_path) else (os.path.getsize(vendor_path), 1, 0, 0)
            session.inventory.append({"path": os.path.abspath(vendor_path), "size": size, "confidence": "VENDOR-DOCUMENTED",
                                      "reason": vendor_reason, "allow_program_area": True})
            existing_inventory.add(key)
    try:
        with open(session_path(), "w", encoding="utf-8") as f: json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)
    except OSError:
        pass
    docker_distros = _docker_wsl_registered() if _known_vendor_residuals(app) else []
    if docker_distros:
        warnings.append("Docker WSL distribution(s) are still registered: " + ", ".join(docker_distros) + ". Shut down WSL and unregister only after backing up required Docker data; raw VHDX deletion is blocked.")

    leftovers: list[ScanItem] = []
    for row in session.inventory:
        path = row.get("path", "")
        if not path or not os.path.exists(path): continue
        if _claimed_by_other(path, app, currently_installed):
            warnings.append(f"Leftover skipped because another installed app now claims it: {path}")
            continue
        try:
            size, _, _, _ = directory_size(path) if os.path.isdir(path) else (os.path.getsize(path), 1, 0, 0)
        except OSError:
            continue
        blocked_wsl = bool(docker_distros and "docker" in path.casefold())
        leftovers.append(ScanItem(
            path=path, name=os.path.basename(path), size=size,
            kind="folder" if os.path.isdir(path) else "file", category="App leftover", risk="system" if blocked_wsl else "review",
            reason=("WSL-REGISTERED — raw deletion blocked. " if blocked_wsl else "") + f"{row.get('confidence', 'HIGH')} confidence: {row.get('reason', 'pre-uninstall match')}",
            project_root=app.name, reclaimable=not blocked_wsl
        ))
    return sorted(leftovers, key=lambda x: x.size, reverse=True), warnings


def allowed_program_area_paths(session: RemovalSession) -> set[str]:
    return {os.path.normcase(os.path.abspath(x["path"])) for x in session.inventory if x.get("allow_program_area")}
