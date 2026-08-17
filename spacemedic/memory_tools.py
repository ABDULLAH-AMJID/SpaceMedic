from __future__ import annotations

import ctypes
from ctypes import wintypes
import gc
import os
import subprocess
from dataclasses import dataclass

IS_WINDOWS = os.name == "nt"


@dataclass(slots=True)
class MemorySnapshot:
    total_physical: int
    available_physical: int
    load_percent: int
    commit_total: int
    commit_limit: int
    pagefile_available: int
    system_cache: int = 0
    kernel_paged: int = 0
    kernel_nonpaged: int = 0
    process_count: int = 0
    handle_count: int = 0

    @property
    def used_physical(self) -> int:
        return max(0, self.total_physical - self.available_physical)

    @property
    def pressure(self) -> str:
        if self.load_percent >= 90 or self.available_physical < 1024**3: return "critical"
        if self.load_percent >= 80 or self.available_physical < 2 * 1024**3: return "high"
        if self.load_percent >= 65: return "moderate"
        return "healthy"


@dataclass(slots=True)
class ProcessMemory:
    pid: int
    name: str
    working_set: int
    private_bytes: int
    cpu_seconds: float
    window_title: str
    responding: bool
    protected: bool
    handle_count: int = 0
    gdi_count: int = 0
    user_count: int = 0
    thread_count: int = 0
    page_fault_count: int = 0
    start_key: str = ""


if IS_WINDOWS:
    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    class PERFORMANCE_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong), ("CommitTotal", ctypes.c_size_t), ("CommitLimit", ctypes.c_size_t),
            ("CommitPeak", ctypes.c_size_t), ("PhysicalTotal", ctypes.c_size_t), ("PhysicalAvailable", ctypes.c_size_t),
            ("SystemCache", ctypes.c_size_t), ("KernelTotal", ctypes.c_size_t), ("KernelPaged", ctypes.c_size_t),
            ("KernelNonpaged", ctypes.c_size_t), ("PageSize", ctypes.c_size_t),
            ("HandleCount", ctypes.c_ulong), ("ProcessCount", ctypes.c_ulong), ("ThreadCount", ctypes.c_ulong),
        ]

    class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260),
        ]

    ctypes.windll.kernel32.OpenProcess.restype = ctypes.c_void_p
    ctypes.windll.kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p


PROTECTED_NAMES = {
    "system", "registry", "memory compression", "secure system", "idle", "csrss", "wininit", "winlogon",
    "services", "lsass", "smss", "dwm", "fontdrvhost", "sihost", "taskhostw", "explorer", "svchost",
    "audiodg", "spoolsv", "searchindexer", "securityhealthservice", "msmpeng", "wslservice",
}


def memory_snapshot() -> MemorySnapshot:
    if not IS_WINDOWS:
        raise RuntimeError("Memory Center is available on Windows only")
    status = MEMORYSTATUSEX(); status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ctypes.WinError()
    perf = PERFORMANCE_INFORMATION(); perf.cb = ctypes.sizeof(perf)
    commit_total = commit_limit = 0
    if ctypes.windll.psapi.GetPerformanceInfo(ctypes.byref(perf), perf.cb):
        commit_total, commit_limit = int(perf.CommitTotal * perf.PageSize), int(perf.CommitLimit * perf.PageSize)
    return MemorySnapshot(
        int(status.ullTotalPhys), int(status.ullAvailPhys), int(status.dwMemoryLoad),
        commit_total, commit_limit, int(status.ullAvailPageFile),
        int(perf.SystemCache * perf.PageSize), int(perf.KernelPaged * perf.PageSize),
        int(perf.KernelNonpaged * perf.PageSize), int(perf.ProcessCount), int(perf.HandleCount)
    )


def _filetime_value(value) -> int:
    return (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)


def _visible_windows() -> dict[int, tuple[str, bool]]:
    windows: dict[int, tuple[str, bool]] = {}
    if not IS_WINDOWS: return windows
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        if not ctypes.windll.user32.IsWindowVisible(hwnd): return True
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length <= 0: return True
        buffer = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buffer, len(buffer))
        pid = wintypes.DWORD(0)
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value and buffer.value and pid.value not in windows:
            windows[int(pid.value)] = (buffer.value, not bool(ctypes.windll.user32.IsHungAppWindow(hwnd)))
        return True
    callback = callback_type(visit)
    ctypes.windll.user32.EnumWindows(callback, 0)
    return windows


def processes() -> list[ProcessMemory]:
    """Low-overhead native process snapshot; no PowerShell child process or third-party runtime."""
    if not IS_WINDOWS: return []
    TH32CS_SNAPPROCESS = 0x00000002
    PROCESS_QUERY_LIMITED_INFORMATION, PROCESS_QUERY_INFORMATION, PROCESS_VM_READ = 0x1000, 0x0400, 0x0010
    snapshot = ctypes.windll.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == ctypes.c_void_p(-1).value: return []
    windows = _visible_windows(); own_pid = os.getpid(); rows: list[ProcessMemory] = []
    entry = PROCESSENTRY32W(); entry.dwSize = ctypes.sizeof(entry)
    try:
        ok = ctypes.windll.kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            pid, name = int(entry.th32ProcessID), os.path.splitext(entry.szExeFile)[0]
            handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
            if not handle:
                handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            working = private = faults = handles = gdi = user = 0; cpu = 0.0; start_key = "0"
            if handle:
                try:
                    counters = PROCESS_MEMORY_COUNTERS_EX(); counters.cb = ctypes.sizeof(counters)
                    if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                        working, private, faults = int(counters.WorkingSetSize), int(counters.PrivateUsage), int(counters.PageFaultCount)
                    count = wintypes.DWORD(0)
                    if ctypes.windll.kernel32.GetProcessHandleCount(handle, ctypes.byref(count)): handles = int(count.value)
                    gdi = int(ctypes.windll.user32.GetGuiResources(handle, 0)); user = int(ctypes.windll.user32.GetGuiResources(handle, 1))
                    created = wintypes.FILETIME(); exited = wintypes.FILETIME(); kernel = wintypes.FILETIME(); user_time = wintypes.FILETIME()
                    if ctypes.windll.kernel32.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited), ctypes.byref(kernel), ctypes.byref(user_time)):
                        start_key = str(_filetime_value(created)); cpu = (_filetime_value(kernel) + _filetime_value(user_time)) / 10_000_000.0
                finally:
                    ctypes.windll.kernel32.CloseHandle(handle)
            title, responding = windows.get(pid, ("", True))
            rows.append(ProcessMemory(
                pid=pid, name=name, working_set=working, private_bytes=private, cpu_seconds=cpu,
                window_title=title, responding=responding,
                protected=pid in (0, 4, own_pid) or name.casefold() in PROTECTED_NAMES,
                handle_count=handles, gdi_count=gdi, user_count=user, thread_count=int(entry.cntThreads),
                page_fault_count=faults, start_key=start_key
            ))
            ok = ctypes.windll.kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        ctypes.windll.kernel32.CloseHandle(snapshot)
    return sorted(rows, key=lambda x: x.working_set, reverse=True)


def foreground_pid() -> int:
    if not IS_WINDOWS: return 0
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    pid = ctypes.c_ulong(0)
    if hwnd: ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return int(pid.value)


def trim_process(pid: int) -> tuple[bool, str]:
    """Request a working-set trim. This is temporary and can cause page faults later."""
    if int(pid) == foreground_pid(): return False, "Foreground applications are protected from working-set trimming"
    if not IS_WINDOWS: return False, "Windows only"
    PROCESS_SET_QUOTA, PROCESS_QUERY_INFORMATION = 0x0100, 0x0400
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION, False, int(pid))
    if not handle: return False, "Access denied or process no longer exists"
    try:
        ok = bool(ctypes.windll.psapi.EmptyWorkingSet(handle))
        return (ok, "Working set trim requested" if ok else "Windows rejected the trim")
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def trim_self() -> tuple[bool, str]:
    gc.collect()
    return trim_process(os.getpid())


def close_process_gracefully(pid: int) -> tuple[bool, str]:
    if not IS_WINDOWS: return False, "Windows only"
    try:
        result = subprocess.run(["taskkill.exe", "/PID", str(int(pid))], capture_output=True, text=True, timeout=20,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        return result.returncode == 0, (result.stdout or result.stderr).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)


def open_task_manager() -> None:
    if IS_WINDOWS: subprocess.Popen(["taskmgr.exe"])


def open_resource_monitor() -> None:
    if IS_WINDOWS: subprocess.Popen(["resmon.exe"])


def open_memory_diagnostic() -> None:
    if IS_WINDOWS: subprocess.Popen(["mdsched.exe"])


def open_performance_options() -> None:
    if IS_WINDOWS: subprocess.Popen(["SystemPropertiesPerformance.exe"])


def open_startup_apps() -> None:
    if IS_WINDOWS: os.startfile("ms-settings:startupapps")  # type: ignore[attr-defined]


def open_power_mode() -> None:
    if IS_WINDOWS: os.startfile("ms-settings:powersleep")  # type: ignore[attr-defined]
