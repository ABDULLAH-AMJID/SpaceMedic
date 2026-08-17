from __future__ import annotations

import ctypes
import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

IS_WINDOWS = os.name == "nt"


@dataclass(slots=True)
class InstalledApp:
    name: str
    publisher: str = ""
    version: str = ""
    estimated_size: int = 0
    install_location: str = ""
    uninstall_string: str = ""
    app_type: str = "Desktop"
    registry_id: str = ""
    package_full_name: str = ""
    package_family_name: str = ""
    protected: bool = False


def drive_stats(path: str = "C:\\") -> tuple[int, int, int]:
    total, used, free = shutil.disk_usage(path)
    return total, used, free


def list_drives() -> list[str]:
    if not IS_WINDOWS:
        return [os.path.abspath(os.sep)]
    mask = ctypes.windll.kernel32.GetLogicalDrives()
    return [f"{chr(65 + i)}:\\" for i in range(26) if mask & (1 << i)]


def is_admin() -> bool:
    if not IS_WINDOWS:
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin() -> bool:
    if not IS_WINDOWS:
        return False
    import sys
    params = subprocess.list2cmdline(sys.argv)
    executable = sys.executable
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, None, 1)
    return rc > 32


def open_path(path: str) -> None:
    if IS_WINDOWS:
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", path])


def reveal_path(path: str) -> None:
    if IS_WINDOWS:
        if os.path.isfile(path):
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        else:
            subprocess.Popen(["explorer", os.path.normpath(path)])
    else:
        open_path(str(Path(path).parent if os.path.isfile(path) else path))


def open_uri(uri: str) -> None:
    if IS_WINDOWS:
        os.startfile(uri)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", uri])


def _allowed_cleanup_target(path: str) -> bool:
    """Hard safety boundary independent of UI classification."""
    absolute = os.path.abspath(path)
    drive, _ = os.path.splitdrive(absolute)
    # Slash normalization also makes this safety check unit-testable off Windows.
    parts = {p.lower() for p in path.replace("\\", "/").split("/") if p and not p.endswith(":")}
    protected = {"windows", "program files", "program files (x86)", "programdata", "$recycle.bin", "system volume information"}
    if parts & protected:
        return False
    compact = path.replace("\\", "/").rstrip("/")
    if compact.endswith(":") or absolute == os.path.abspath(drive + os.sep):
        return False
    home = os.path.abspath(os.path.expanduser("~"))
    if os.path.normcase(absolute) == os.path.normcase(home):
        return False
    return True


def _safe_verified_leftover(path: str) -> bool:
    absolute = os.path.abspath(path).rstrip("\\/")
    parts = [x.casefold() for x in path.replace("\\", "/").split("/") if x and not x.endswith(":")]
    if any(x in {"windows", "system32", "syswow64", "windowsapps", "common files", "installer", "$recycle.bin", "system volume information"} for x in parts):
        return False
    # Never allow a drive, Program Files, or ProgramData root itself.
    if len(parts) < 2 or parts[-1] in {"program files", "program files (x86)", "programdata"}:
        return False
    try:
        attrs = getattr(os.stat(absolute, follow_symlinks=False), "st_file_attributes", 0)
        return not os.path.islink(absolute) and not bool(attrs & 0x400)
    except OSError:
        return False


def recycle(paths: Iterable[str], verified_exact: Iterable[str] = ()) -> tuple[list[str], list[str]]:
    """Move approved items to Recycle Bin on Windows. Returns (succeeded, failed).

    `verified_exact` is reserved for app-removal paths captured before uninstall and revalidated
    afterwards; it permits an exact former app directory under Program Files/ProgramData while
    keeping broad protected-directory cleanup blocked.
    """
    requested = [os.path.abspath(p) for p in paths if os.path.exists(p)]
    verified = {os.path.normcase(os.path.abspath(p)) for p in verified_exact if _safe_verified_leftover(p)}
    paths = [p for p in requested if _allowed_cleanup_target(p) or os.path.normcase(p) in verified]
    rejected = [p for p in requested if p not in paths]
    if not paths:
        return [], rejected
    if not IS_WINDOWS:
        return [], requested

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", ctypes.c_void_p), ("wFunc", ctypes.c_uint),
            ("pFrom", ctypes.c_wchar_p), ("pTo", ctypes.c_wchar_p),
            ("fFlags", ctypes.c_ushort), ("fAnyOperationsAborted", ctypes.c_bool),
            ("hNameMappings", ctypes.c_void_p), ("lpszProgressTitle", ctypes.c_wchar_p),
        ]

    # Double-NUL-separated source list. FOF_ALLOWUNDO routes deletes to Recycle Bin.
    source = "\0".join(paths) + "\0\0"
    op = SHFILEOPSTRUCTW()
    op.wFunc = 0x0003  # FO_DELETE
    op.pFrom = source
    op.fFlags = 0x0040 | 0x0010 | 0x4000  # ALLOWUNDO, NOCONFIRMATION, WANTNUKEWARNING
    rc = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if rc == 0 and not op.fAnyOperationsAborted:
        return paths, rejected
    return [], paths + rejected


def installed_apps() -> list[InstalledApp]:
    if not IS_WINDOWS:
        return []
    import winreg
    locations = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", winreg.KEY_WOW64_64KEY),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", winreg.KEY_WOW64_32KEY),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", 0),
    ]
    result: dict[tuple[str, str], InstalledApp] = {}
    for hive, key_path, view in locations:
        try:
            with winreg.OpenKey(hive, key_path, 0, winreg.KEY_READ | view) as root:
                for i in range(winreg.QueryInfoKey(root)[0]):
                    try:
                        subkey_name = winreg.EnumKey(root, i)
                        with winreg.OpenKey(root, subkey_name) as sub:
                            def val(name: str, default=""):
                                try: return winreg.QueryValueEx(sub, name)[0]
                                except OSError: return default
                            name = str(val("DisplayName")).strip()
                            if not name or int(val("SystemComponent", 0) or 0) == 1:
                                continue
                            size = int(val("EstimatedSize", 0) or 0) * 1024
                            uninstall = str(val("UninstallString"))
                            protected = bool(int(val("NoRemove", 0) or 0)) or not uninstall
                            app = InstalledApp(name, str(val("Publisher")), str(val("DisplayVersion")), size,
                                               str(val("InstallLocation")), uninstall, "Desktop",
                                               registry_id=subkey_name, protected=protected)
                            result[(name.lower(), app.version.lower())] = app
                    except (OSError, ValueError, TypeError):
                        continue
        except OSError:
            continue
    for app in _store_apps():
        result[(app.name.lower(), app.version.lower())] = app
    return sorted(result.values(), key=lambda x: (x.estimated_size, x.name.lower()), reverse=True)


def _store_apps() -> list[InstalledApp]:
    """Read current-user MSIX/AppX packages without importing PowerShell modules in-process."""
    if not IS_WINDOWS:
        return []
    script = (
        "Get-AppxPackage | Where-Object {$_.IsFramework -eq $false} | "
        "Select-Object Name,Publisher,Version,PackageFullName,PackageFamilyName,InstallLocation,NonRemovable | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW
        )
        if completed.returncode or not completed.stdout.strip():
            return []
        data = json.loads(completed.stdout)
        if isinstance(data, dict): data = [data]
        apps = []
        for row in data:
            name = str(row.get("Name") or "").strip()
            if not name: continue
            apps.append(InstalledApp(
                name=name, publisher=str(row.get("Publisher") or ""), version=str(row.get("Version") or ""),
                install_location=str(row.get("InstallLocation") or ""), app_type="Store/MSIX",
                package_full_name=str(row.get("PackageFullName") or ""),
                package_family_name=str(row.get("PackageFamilyName") or ""), protected=bool(row.get("NonRemovable"))
            ))
        return apps
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, TypeError):
        return []


def launch_uninstall(app: InstalledApp) -> tuple[bool, str]:
    """Launch the app's registered interactive uninstaller; never invent silent switches."""
    if not IS_WINDOWS:
        return False, "Uninstall is available only on Windows."
    if app.protected:
        return False, "Windows or the publisher marks this app as non-removable, or no uninstaller is registered."
    try:
        if app.app_type == "Store/MSIX":
            if not app.package_full_name:
                return False, "The package identity is missing."
            # LiteralPath-style quoting prevents package names from becoming script syntax.
            package = app.package_full_name.replace("'", "''")
            command = f"Remove-AppxPackage -Package '{package}'"
            return run_admin_command(command, f"Uninstall {app.name}"), "Store/MSIX uninstaller launched."
        if not app.uninstall_string:
            return False, "This desktop app did not register an uninstall command."
        # This is the same registered command used by Windows Apps & Features.
        subprocess.Popen(app.uninstall_string, shell=False)
        return True, "Publisher's registered uninstaller launched."
    except OSError as exc:
        return False, str(exc)


def launch_uninstall_settings() -> None:
    open_uri("ms-settings:appsfeatures")


def launch_storage_settings() -> None:
    open_uri("ms-settings:storagesense")


def launch_update_history() -> None:
    open_uri("ms-settings:windowsupdate-history")


def launch_delivery_optimization() -> None:
    open_uri("ms-settings:delivery-optimization")


def launch_reliability_monitor() -> None:
    if IS_WINDOWS:
        subprocess.Popen(["perfmon.exe", "/rel"])


def launch_system_protection() -> None:
    if IS_WINDOWS:
        subprocess.Popen(["SystemPropertiesProtection.exe"])


def inspect_reserved_storage() -> bool:
    return run_admin_command("DISM.exe /Online /Get-ReservedStorageState", "Reserved Storage status")


def inspect_shadow_storage() -> bool:
    return run_admin_command("vssadmin.exe list shadowstorage", "Restore point / shadow-copy storage")


def launch_cleanup() -> None:
    if IS_WINDOWS:
        subprocess.Popen(["cleanmgr.exe", "/d", "C:"])


def run_admin_command(command: str, title: str = "SpaceMedic") -> bool:
    if not IS_WINDOWS:
        return False
    # Visible PowerShell window so the user can inspect output. No hidden destructive work.
    quoted = command.replace('"', '\\"')
    safe_title = title.replace("'", "''")
    args = f'-NoExit -ExecutionPolicy Bypass -Command "Write-Host \'{safe_title}\' -ForegroundColor Cyan; {quoted}"'
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", "powershell.exe", args, None, 1)
    return rc > 32


def analyze_component_store() -> bool:
    return run_admin_command("DISM.exe /Online /Cleanup-Image /AnalyzeComponentStore", "Windows Component Store analysis")


def cleanup_component_store() -> bool:
    return run_admin_command("DISM.exe /Online /Cleanup-Image /StartComponentCleanup", "Safe standard component cleanup")


def cleanup_delivery_optimization() -> bool:
    return run_admin_command("Delete-DeliveryOptimizationCache -Force", "Clear Windows Delivery Optimization cache")


def run_system_file_check() -> bool:
    return run_admin_command("sfc.exe /scannow", "Windows protected system-file check")


def disable_hibernation() -> bool:
    return run_admin_command("powercfg.exe /hibernate off", "Disable hibernation (also disables Fast Startup)")


def git_gc(project: str) -> bool:
    if not shutil.which("git"):
        return False
    subprocess.Popen(["git", "-C", project, "gc"], creationflags=subprocess.CREATE_NEW_CONSOLE if IS_WINDOWS else 0)
    return True
