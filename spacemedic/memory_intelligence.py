from __future__ import annotations

import ctypes
import math
import os
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from .memory_tools import MemorySnapshot, ProcessMemory, IS_WINDOWS


@dataclass(slots=True)
class LeakFinding:
    identity: str
    pid: int
    process: str
    kind: str
    confidence: float
    rate_per_hour: float
    current_value: int
    duration_seconds: float
    explanation: str


@dataclass(slots=True)
class MemoryPlan:
    state: str
    headline: str
    recommendations: list[str]
    automatic_action: str


def database_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / "SpaceMedic"
    path.mkdir(parents=True, exist_ok=True)
    return path / "memory-intelligence.db"


def _regression(points: list[tuple[float, float]]) -> tuple[float, float]:
    """Return slope per second and R². A trend is evidence, not proof of a leak."""
    n = len(points)
    if n < 3: return 0.0, 0.0
    x0 = points[0][0]
    xs = [x - x0 for x, _ in points]; ys = [y for _, y in points]
    sx, sy = sum(xs), sum(ys)
    sxx = sum(x*x for x in xs); sxy = sum(x*y for x, y in zip(xs, ys))
    denom = n * sxx - sx * sx
    if not denom: return 0.0, 0.0
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    mean = sy / n
    ss_res = sum((y - (slope*x + intercept))**2 for x, y in zip(xs, ys))
    ss_tot = sum((y - mean)**2 for y in ys)
    r2 = max(0.0, min(1.0, 1.0 - ss_res / ss_tot)) if ss_tot else 0.0
    return slope, r2


def _monotonic_fraction(values: list[float]) -> float:
    if len(values) < 2: return 0.0
    return sum(1 for a, b in zip(values, values[1:]) if b >= a) / (len(values) - 1)


def confirmed_low_memory(snapshot: MemorySnapshot) -> bool:
    """Require current physical/commit evidence in addition to a transient OS event."""
    commit_ratio = snapshot.commit_total / snapshot.commit_limit if snapshot.commit_limit else 0.0
    threshold = max(512 * 1024**2, int(snapshot.total_physical * 0.03))
    return snapshot.available_physical <= threshold or commit_ratio >= 0.95


class MemoryIntelligence:
    def __init__(self, path: str | None = None):
        self.path = str(path or database_path())
        self._initialize()
        self._low_handle = None
        self._watch_stop = threading.Event()
        self._watch_thread = None
        if IS_WINDOWS:
            try:
                creator = ctypes.windll.kernel32.CreateMemoryResourceNotification
                creator.restype = ctypes.c_void_p
                self._low_handle = creator(0)
            except Exception: self._low_handle = None

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS system_samples(
                    ts REAL NOT NULL, total_phys INTEGER, avail_phys INTEGER, load_pct INTEGER,
                    commit_total INTEGER, commit_limit INTEGER, pressure TEXT, low_signal INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS process_samples(
                    ts REAL NOT NULL, identity TEXT NOT NULL, pid INTEGER, name TEXT,
                    working_set INTEGER, private_bytes INTEGER, handles INTEGER, gdi INTEGER,
                    user_objects INTEGER, threads INTEGER, page_faults INTEGER, cpu_seconds REAL,
                    foreground INTEGER DEFAULT 0);
                CREATE INDEX IF NOT EXISTS ix_process_identity_time ON process_samples(identity, ts);
                CREATE INDEX IF NOT EXISTS ix_system_time ON system_samples(ts);
            """)

    def low_memory_signal(self) -> bool:
        if not IS_WINDOWS or not self._low_handle: return False
        state = ctypes.c_int(0)
        try:
            return bool(ctypes.windll.kernel32.QueryMemoryResourceNotification(ctypes.c_void_p(self._low_handle), ctypes.byref(state)) and state.value)
        except Exception:
            return False

    @staticmethod
    def identity(item: ProcessMemory) -> str:
        return f"{item.name.casefold()}|{item.pid}|{item.start_key}"

    def record(self, snapshot: MemorySnapshot, rows: list[ProcessMemory], foreground_pid: int = 0) -> None:
        now = time.time(); low = int(self.low_memory_signal())
        with self._connect() as db:
            db.execute("INSERT INTO system_samples VALUES(?,?,?,?,?,?,?,?)",
                       (now, snapshot.total_physical, snapshot.available_physical, snapshot.load_percent,
                        snapshot.commit_total, snapshot.commit_limit, snapshot.pressure, low))
            selected = rows[:150]
            selected_ids = {p.pid for p in selected}
            selected += [p for p in rows[150:] if p.pid not in selected_ids and (p.private_bytes >= 100*1024**2 or p.handle_count >= 1000 or p.gdi_count >= 1000)]
            db.executemany("INSERT INTO process_samples VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", [
                (now, self.identity(p), p.pid, p.name, p.working_set, p.private_bytes, p.handle_count,
                 p.gdi_count, p.user_count, p.thread_count, p.page_fault_count, p.cpu_seconds, int(p.pid == foreground_pid))
                for p in selected
            ])
            db.execute("DELETE FROM system_samples WHERE ts < ?", (now - 7 * 86400,))
            db.execute("DELETE FROM process_samples WHERE ts < ?", (now - 2 * 86400,))

    def findings(self, rows: list[ProcessMemory], window_hours: float = 2.0) -> list[LeakFinding]:
        now = time.time(); cutoff = now - window_hours * 3600
        findings: list[LeakFinding] = []
        with self._connect() as db:
            for item in rows:
                identity = self.identity(item)
                samples = db.execute(
                    "SELECT ts,private_bytes,handles,gdi,cpu_seconds FROM process_samples WHERE identity=? AND ts>=? ORDER BY ts",
                    (identity, cutoff)).fetchall()
                if len(samples) < 8: continue
                duration = samples[-1][0] - samples[0][0]
                if duration < 300: continue
                cpu_growth = max(0.0, samples[-1][4] - samples[0][4])
                workload_penalty = 0.15 if cpu_growth > duration * 0.35 else 0.0

                private_points = [(r[0], r[1]) for r in samples]
                slope, r2 = _regression(private_points)
                values = [r[1] for r in samples]; growth = values[-1] - values[0]
                monotonic = _monotonic_fraction(values)
                rate = slope * 3600
                confidence = max(0.0, min(0.99, r2 * 0.72 + monotonic * 0.28 - workload_penalty))
                if values[-1] >= 100 * 1024**2 and growth >= 64 * 1024**2 and rate >= 50 * 1024**2 and confidence >= 0.72:
                    findings.append(LeakFinding(identity, item.pid, item.name, "private-memory trend", confidence, rate,
                                                int(values[-1]), duration,
                                                "Private committed bytes have grown consistently. Workload growth can resemble a leak; confirm with PerfMon, VMMap, WPR or the app vendor."))

                handle_points = [(r[0], r[2]) for r in samples]
                hslope, hr2 = _regression(handle_points); hvalues = [r[2] for r in samples]
                hconf = max(0.0, min(0.99, hr2 * 0.75 + _monotonic_fraction(hvalues) * 0.25 - workload_penalty))
                if hvalues[-1] >= 2000 and hvalues[-1] - hvalues[0] >= 500 and hslope * 3600 >= 100 and hconf >= 0.75:
                    findings.append(LeakFinding(identity, item.pid, item.name, "handle trend", hconf, hslope * 3600,
                                                int(hvalues[-1]), duration,
                                                "Handle count is rising consistently. Handles cannot be safely closed externally; restart/update the owning app and investigate with Process Explorer."))

                gdi_points = [(r[0], r[3]) for r in samples]
                gslope, gr2 = _regression(gdi_points); gvalues = [r[3] for r in samples]
                gconf = max(0.0, min(0.99, gr2 * 0.75 + _monotonic_fraction(gvalues) * 0.25 - workload_penalty))
                if gvalues[-1] >= 3000 and gvalues[-1] - gvalues[0] >= 300 and gslope > 0 and gconf >= 0.70:
                    findings.append(LeakFinding(identity, item.pid, item.name, "GDI object trend", gconf, gslope * 3600,
                                                int(gvalues[-1]), duration,
                                                "GDI objects are approaching the default per-process limit of 10,000. Save work and update/restart the app; increasing the quota is not a repair."))
        return sorted(findings, key=lambda x: (x.confidence, x.rate_per_hour), reverse=True)

    def plan(self, snapshot: MemorySnapshot, rows: list[ProcessMemory], findings: list[LeakFinding]) -> MemoryPlan:
        commit_ratio = snapshot.commit_total / snapshot.commit_limit if snapshot.commit_limit else 0
        closeable = [p for p in rows if not p.protected and p.window_title]
        top = closeable[0] if closeable else None
        recommendations: list[str] = []
        if findings:
            recommendations.append(f"Investigate {len(findings)} sustained resource-growth finding(s); trimming cannot repair a leak.")
        if top:
            recommendations.append(f"Largest normal app: {top.name} ({top.working_set / 1024**2:.0f} MB working set). Save work before closing it.")
        if commit_ratio >= 0.90:
            recommendations.append("Commit usage is near its limit. Keep a pagefile and close high-private-byte applications immediately.")
        if snapshot.available_physical < 1024**3:
            recommendations.append("Less than 1 GB is immediately available. Avoid launching another heavy workload.")
        if snapshot.pressure == "healthy":
            return MemoryPlan("healthy", "Windows has adequate reusable memory", recommendations or ["No memory action is needed."], "None")
        if snapshot.pressure == "moderate":
            return MemoryPlan("observe", "Memory use is elevated but not critical", recommendations, "Continue monitoring; no automatic trim")
        if snapshot.pressure == "high":
            return MemoryPlan("action", "Real memory pressure is developing", recommendations, "Ask the user to close an unnecessary app")
        return MemoryPlan("critical", "Critical memory pressure", recommendations, "Protect foreground/system processes; request explicit user action")

    def start_low_memory_watch(self, callback) -> None:
        """Wait on the Windows low-memory event without polling or automatic cleanup."""
        if not IS_WINDOWS or not self._low_handle or self._watch_thread: return
        def watch():
            signaled = False
            while not self._watch_stop.is_set():
                result = ctypes.windll.kernel32.WaitForSingleObject(ctypes.c_void_p(self._low_handle), 1000)
                if result in (-1, 0xFFFFFFFF):
                    break
                now_signaled = result == 0 and self.low_memory_signal()
                if now_signaled and not signaled:
                    try: callback()
                    except Exception: pass
                signaled = now_signaled
        self._watch_thread = threading.Thread(target=watch, name="SpaceMedicLowMemory", daemon=True)
        self._watch_thread.start()

    def close(self) -> None:
        self._watch_stop.set()
        if self._watch_thread and self._watch_thread.is_alive(): self._watch_thread.join(timeout=1.5)
        if IS_WINDOWS and self._low_handle:
            try: ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(self._low_handle))
            except Exception: pass
            self._low_handle = None
