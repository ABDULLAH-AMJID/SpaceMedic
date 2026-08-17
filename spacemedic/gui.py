from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .models import ScanItem, ScanResult
from .scanner import DiskScanner, format_bytes, known_global_caches
from . import windows_tools as wt
from .app_removal import capture_inventory, load_session, scan_session_leftovers, allowed_program_area_paths, RemovalSession
from .duplicates import find_duplicates, DuplicateGroup
from .history import record as record_history, load as load_history
from .system_insights import system_storage, developer_platforms, startup_inventory, Insight
from .install_monitor import take_snapshot, compare as compare_snapshots
from .cache_migration import migrate as migrate_cache, identify as identify_cache
from .fast_scanner import scan as fast_scan, available as fast_scan_available
from .parallel_scanner import ParallelDiskScanner
from .scan_cache import latest as latest_scan, save as save_scan, compare as compare_scan
from .diagnostics import create_bundle as create_diagnostic_bundle
from .config import load as load_settings, save as save_settings
from .i18n import tr, LANGUAGES
from .rules import user_rules_path, bundled_rules_path
from .memory_tools import (memory_snapshot, processes as memory_processes, trim_process, trim_self,
                           close_process_gracefully, open_task_manager, open_resource_monitor,
                           open_memory_diagnostic, open_performance_options, open_startup_apps, open_power_mode,
                           ProcessMemory, foreground_pid)
from .memory_intelligence import MemoryIntelligence, LeakFinding, confirmed_low_memory

APP_NAME = "SpaceMedic"
VERSION = "3.6.0"
DEVELOPER = "M.Abdullah Amjid"
PALETTES = {
    "hud": {
        "bg": "#050a16", "panel": "#101827", "panel2": "#192437", "text": "#edf7ff", "muted": "#8298ad",
        "blue": "#5dd6ff", "green": "#58e0b0", "amber": "#ffc96b", "red": "#ff7083",
        "nav": "#080f1d", "top": "#07101f", "border": "#334861",
    },
    "professional": {
        "bg": "#0f1115", "panel": "#181b22", "panel2": "#222630", "text": "#f3f4f6", "muted": "#9aa3b2",
        "blue": "#4c9fff", "green": "#48bd89", "amber": "#e7b75b", "red": "#e86671",
        "nav": "#14171d", "top": "#12151a", "border": "#303642",
    },
}

BG = PANEL = PANEL2 = TEXT = MUTED = BLUE = GREEN = AMBER = RED = NAV_BG = TOP_BG = BORDER = ""

def apply_palette(name: str) -> None:
    global BG, PANEL, PANEL2, TEXT, MUTED, BLUE, GREEN, AMBER, RED, NAV_BG, TOP_BG, BORDER
    p = PALETTES.get(name, PALETTES["hud"])
    BG, PANEL, PANEL2 = p["bg"], p["panel"], p["panel2"]
    TEXT, MUTED, BLUE, GREEN, AMBER, RED = p["text"], p["muted"], p["blue"], p["green"], p["amber"], p["red"]
    NAV_BG, TOP_BG, BORDER = p["nav"], p["top"], p["border"]


class SpaceMedicApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        apply_palette(self.settings.theme)
        self.title(f"{APP_NAME} — Windows Storage & Developer Cleanup")
        self.geometry("1240x800")
        self.minsize(980, 650)
        self.configure(bg=BG)
        self.result: ScanResult | None = None
        self.cache_items: list[ScanItem] = []
        self.app_leftovers: list[ScanItem] = []
        self.installed_app_rows: list[wt.InstalledApp] = []
        self.removal_session: RemovalSession | None = load_session()
        self.duplicate_groups: list[DuplicateGroup] = []
        self.monitor_before: str = ""
        self.scan_backend = "recursive"
        self.change_report: dict = {}
        self.treemap_mode = "folders"
        self.treemap_view_root = ""
        self.detached_rows: dict[ttk.Treeview, list[str]] = {}
        self.memory_intelligence = MemoryIntelligence()
        self.memory_findings: list[LeakFinding] = []
        self._memory_refresh_running = False
        self._memory_timer = None
        self._last_low_memory_alert = 0.0
        self.cancel = threading.Event()
        self.worker: threading.Thread | None = None
        self.row_objects: dict[str, object] = {}
        self._row_seq = 0
        self._setup_style()
        self._build()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.memory_intelligence.start_low_memory_watch(lambda: self.after(0, self._on_windows_low_memory))
        self.after(200, self.refresh_drive)
        if os.name == "nt":
            self.after(500, self.load_apps)
        if not self.settings.onboarding_complete:
            self.after(900, self._show_onboarding)

    def t(self, key: str) -> str:
        return tr(self.settings.language, key)

    def _setup_style(self) -> None:
        style = ttk.Style(self)
        try: style.theme_use("clam")
        except tk.TclError: pass
        style.configure(".", background=BG, foreground=TEXT, fieldbackground=PANEL2, bordercolor="#273853")
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 18))
        style.configure("PageTitle.TLabel", font=("Segoe UI Semibold", 20), foreground=TEXT)
        style.configure("Metric.TLabel", background=PANEL, font=("Segoe UI Semibold", 17))
        style.configure("MetricName.TLabel", background=PANEL, foreground=MUTED)
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 8), background=PANEL2, foreground=TEXT, borderwidth=1, relief="flat")
        style.map("TButton", background=[("active", "#303641"), ("pressed", "#383f4b")])
        style.configure("Accent.TButton", background=BLUE, foreground="white", font=("Segoe UI Semibold", 10))
        style.map("Accent.TButton", background=[("active", "#68adff"), ("pressed", "#3488e8")])
        style.configure("Danger.TButton", background="#7b333a", foreground="white")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(14, 9))
        style.map("TNotebook.Tab", background=[("selected", PANEL2)], foreground=[("selected", TEXT)])
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=TEXT, rowheight=30, borderwidth=0)
        style.map("Treeview", background=[("selected", "#1e5482")])
        style.configure("Treeview.Heading", background=PANEL2, foreground=TEXT, font=("Segoe UI Semibold", 10))
        style.configure("Horizontal.TProgressbar", troughcolor=PANEL2, background=BLUE)
        style.configure("Hidden.TNotebook", background=BG, borderwidth=0, tabmargins=0)
        style.layout("Hidden.TNotebook.Tab", [])
        style.configure("Top.TFrame", background=TOP_BG)
        style.configure("Nav.TFrame", background=NAV_BG)
        style.configure("Content.TFrame", background=BG)
        style.configure("Card.TFrame", background=PANEL, bordercolor=BORDER, relief="solid", borderwidth=1)

    def _draw_hud_top(self, event=None) -> None:
        c = self.top_canvas; c.delete("all")
        w, h = max(900, c.winfo_width()), 82
        c.create_polygon(0, 0, w, 0, w, 64, w-24, 64, w-34, 76, 390, 76, 378, 64, 0, 64,
                         fill=TOP_BG, outline="")
        c.create_line(0, 64, 370, 64, 384, 77, w-36, 77, w-24, 64, w, 64, fill=BORDER, width=1)
        c.create_line(18, 64, 180, 64, 196, 72, 286, 72, fill=BLUE, width=2)
        c.create_oval(22, 15, 62, 55, outline=BLUE, width=2)
        c.create_arc(27, 20, 57, 50, start=25, extent=270, style="arc", outline="#dbeeff", width=3)
        c.create_text(42, 35, text="S", fill=TEXT, font=("Segoe UI Semibold", 13))
        c.create_text(78, 25, anchor="w", text="SPACEMEDIC", fill=TEXT, font=("Segoe UI Semibold", 17))
        c.create_text(78, 47, anchor="w", text=self.t("tagline"), fill=MUTED, font=("Segoe UI", 9))
        c.create_text(w-28, 25, anchor="e", text=f"BUILD {VERSION}", fill=MUTED, font=("Consolas", 8))
        c.create_text(w-28, 47, anchor="e", text="ADMINISTRATOR" if wt.is_admin() else "STANDARD • CLICK TO ELEVATE",
                      fill=GREEN if wt.is_admin() else AMBER, font=("Consolas", 9, "bold"))

    def _build_top_bar(self) -> None:
        if self.settings.theme == "hud":
            self.top_canvas = tk.Canvas(self, height=82, bg=BG, highlightthickness=0)
            self.top_canvas.pack(fill="x")
            self.top_canvas.bind("<Configure>", self._draw_hud_top)
            self.top_canvas.bind("<Button-1>", lambda e: self._elevate() if (os.name == "nt" and not wt.is_admin() and e.x > self.top_canvas.winfo_width()-260) else None)
            return
        top = ttk.Frame(self, style="Top.TFrame", padding=(20, 12)); top.pack(fill="x")
        logo = tk.Canvas(top, width=38, height=38, bg=TOP_BG, highlightthickness=0); logo.pack(side="left", padx=(0, 12))
        logo.create_rectangle(2, 2, 36, 36, fill=BLUE, outline=""); logo.create_text(19, 19, text="S", fill="white", font=("Segoe UI Semibold", 17))
        identity = ttk.Frame(top, style="Top.TFrame"); identity.pack(side="left")
        ttk.Label(identity, text="SpaceMedic", style="Title.TLabel", background=TOP_BG).pack(anchor="w")
        ttk.Label(identity, text=self.t("tagline"), style="Muted.TLabel", background=TOP_BG).pack(anchor="w")
        ttk.Label(top, text="Administrator" if wt.is_admin() else "Standard access", background=TOP_BG,
                  foreground=GREEN if wt.is_admin() else AMBER, font=("Segoe UI Semibold", 9)).pack(side="right", padx=(10, 0))
        if os.name == "nt" and not wt.is_admin(): ttk.Button(top, text="Restart as administrator", command=self._elevate).pack(side="right")

    def _build(self) -> None:
        self._build_top_bar()

        self.alert_host = tk.Frame(self, bg=BG)
        self.alert_host.pack(fill="x")

        metrics = ttk.Frame(self, padding=(20, 10, 20, 12))
        metrics.pack(fill="x")
        self.metric_vars: list[tk.StringVar] = []
        for index, title in enumerate((self.t("drive_used"), self.t("drive_free"), self.t("scanned"), self.t("reclaimable"))):
            var = tk.StringVar(value="—"); self.metric_vars.append(var)
            if self.settings.theme == "hud":
                card = tk.Frame(metrics, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
                card.pack(side="left", fill="x", expand=True, padx=(0, 10))
                strip = tk.Canvas(card, height=15, bg=PANEL, highlightthickness=0); strip.pack(fill="x")
                strip.create_line(0, 13, 72, 13, 82, 4, 150, 4, fill=BLUE if index < 2 else GREEN, width=2)
                for x in range(160, 208, 10): strip.create_line(x, 4, x+5, 12, fill="#6d7d90", width=2)
                tk.Label(card, text=title.upper(), bg=PANEL, fg=MUTED, anchor="w", font=("Consolas", 8)).pack(fill="x", padx=14, pady=(5, 0))
                tk.Label(card, textvariable=var, bg=PANEL, fg=TEXT, anchor="w", font=("Segoe UI Semibold", 17)).pack(fill="x", padx=14, pady=(3, 12))
            else:
                card = ttk.Frame(metrics, style="Card.TFrame", padding=(16, 12)); card.pack(side="left", fill="x", expand=True, padx=(0, 10))
                ttk.Label(card, text=title, style="MetricName.TLabel").pack(anchor="w")
                ttk.Label(card, textvariable=var, style="Metric.TLabel").pack(anchor="w", pady=(4, 0))

        controls = ttk.Frame(self, padding=(20, 4, 20, 12))
        controls.pack(fill="x")
        ttk.Label(controls, text=self.t("scan_location")).pack(side="left")
        default_path = self.settings.last_scan_path or ("C:\\" if os.name == "nt" else str(Path.home()))
        self.path_var = tk.StringVar(value=default_path)
        ttk.Entry(controls, textvariable=self.path_var, width=55).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(controls, text=self.t("browse"), command=self.browse).pack(side="left", padx=3)
        self.scan_btn = ttk.Button(controls, text=self.t("analyze"), style="Accent.TButton", command=self.start_scan)
        self.scan_btn.pack(side="left", padx=3)
        self.fast_btn = ttk.Button(controls, text=self.t("fast_scan"), command=self.start_fast_scan)
        self.fast_btn.pack(side="left", padx=3)
        self.stop_btn = ttk.Button(controls, text=self.t("stop"), command=self.stop_scan, state="disabled")
        self.stop_btn.pack(side="left", padx=3)

        status = ttk.Frame(self, padding=(20, 0, 20, 8))
        status.pack(fill="x")
        self.progress = ttk.Progressbar(status, mode="indeterminate")
        self.progress.pack(fill="x")
        self.status_var = tk.StringVar(value=self.t("ready"))
        ttk.Label(status, textvariable=self.status_var, style="Muted.TLabel").pack(anchor="w", pady=(5, 0))

        search = ttk.Frame(self, padding=(20, 0, 20, 8))
        search.pack(fill="x")
        ttk.Label(search, text=self.t("search")).pack(side="left")
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=8)
        search_entry.bind("<KeyRelease>", lambda e: self._apply_search())
        ttk.Button(search, text=self.t("clear"), command=self._clear_search).pack(side="right")

        workspace = ttk.Frame(self, padding=(16, 0, 16, 10))
        workspace.pack(fill="both", expand=True)
        self.nav_shell = tk.Frame(workspace, bg=NAV_BG, width=224, highlightbackground=BORDER, highlightthickness=1)
        self.nav_shell.pack(side="left", fill="y", padx=(0, 12))
        self.nav_shell.pack_propagate(False)
        self.nav_header = tk.Frame(self.nav_shell, bg=NAV_BG)
        self.nav_header.pack(fill="x", padx=10, pady=(12, 4))
        tk.Label(self.nav_header, text="Navigation", bg=NAV_BG, fg=TEXT, font=("Segoe UI Semibold", 11), anchor="w").pack(fill="x")
        tk.Label(self.nav_header, text="Storage & performance", bg=NAV_BG, fg=MUTED, font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(2, 0))
        self.nav_settings_host = tk.Frame(self.nav_shell, bg=NAV_BG)
        self.nav_settings_host.pack(side="bottom", fill="x", padx=8, pady=8)
        nav_body = tk.Frame(self.nav_shell, bg=NAV_BG)
        nav_body.pack(fill="both", expand=True, padx=(0, 2), pady=4)
        self.nav_canvas = tk.Canvas(nav_body, bg=NAV_BG, highlightthickness=0, width=204)
        self.nav_scrollbar = ttk.Scrollbar(nav_body, orient="vertical", command=self.nav_canvas.yview)
        self.nav_canvas.configure(yscrollcommand=self.nav_scrollbar.set)
        self.nav_scrollbar.pack(side="right", fill="y")
        self.nav_canvas.pack(side="left", fill="both", expand=True)
        self.nav_rail = tk.Frame(self.nav_canvas, bg=NAV_BG)
        self.nav_window = self.nav_canvas.create_window((0, 0), window=self.nav_rail, anchor="nw")
        self.nav_rail.bind("<Configure>", self._sync_nav_scrollregion)
        self.nav_canvas.bind("<Configure>", self._sync_nav_width)

        self.content_shell = ttk.Frame(workspace, style="Content.TFrame")
        self.content_shell.pack(side="left", fill="both", expand=True)
        page_header = ttk.Frame(self.content_shell, style="Content.TFrame", padding=(4, 2, 4, 10))
        page_header.pack(fill="x")
        self.page_title_var = tk.StringVar(value=self.t("largest"))
        self.page_desc_var = tk.StringVar(value="Understand what is using storage and review the largest items.")
        ttk.Label(page_header, textvariable=self.page_title_var, style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(page_header, textvariable=self.page_desc_var, style="Muted.TLabel").pack(anchor="w", pady=(2, 0))
        if self.settings.theme == "hud":
            page_decor = tk.Canvas(page_header, height=14, bg=BG, highlightthickness=0)
            page_decor.pack(fill="x", pady=(6, 0))
            page_decor.bind("<Configure>", lambda e, c=page_decor: self._draw_page_decor(c))
        self.tabs = ttk.Notebook(self.content_shell, style="Hidden.TNotebook")
        self.tabs.pack(fill="both", expand=True)
        self.overview_tab = ttk.Frame(self.tabs, padding=8)
        self.projects_tab = ttk.Frame(self.tabs, padding=8)
        self.cleanup_tab = ttk.Frame(self.tabs, padding=8)
        self.apps_tab = ttk.Frame(self.tabs, padding=8)
        self.treemap_tab = ttk.Frame(self.tabs, padding=8)
        self.changes_tab = ttk.Frame(self.tabs, padding=8)
        self.duplicates_tab = ttk.Frame(self.tabs, padding=8)
        self.insights_tab = ttk.Frame(self.tabs, padding=8)
        self.memory_tab = ttk.Frame(self.tabs, padding=8)
        self.monitor_tab = ttk.Frame(self.tabs, padding=8)
        self.tools_tab = ttk.Frame(self.tabs, padding=12)
        self.settings_tab = ttk.Frame(self.tabs, padding=16)
        self.tabs.add(self.overview_tab, text=self.t("largest"))
        self.tabs.add(self.treemap_tab, text=self.t("treemap"))
        self.tabs.add(self.changes_tab, text=self.t("changes"))
        self.tabs.add(self.projects_tab, text=self.t("projects"))
        self.tabs.add(self.duplicates_tab, text=self.t("duplicates"))
        self.tabs.add(self.cleanup_tab, text=self.t("junk"))
        self.tabs.add(self.apps_tab, text=self.t("apps"))
        self.tabs.add(self.insights_tab, text=self.t("system"))
        self.tabs.add(self.memory_tab, text=self.t("memory"))
        self.tabs.add(self.monitor_tab, text=self.t("monitor"))
        self.tabs.add(self.tools_tab, text=self.t("tools"))
        self.tabs.add(self.settings_tab, text=self.t("settings"))
        self._build_tables()
        self._build_advanced_tabs()
        self._build_memory_center()
        self._build_tools()
        self._build_settings()
        self._build_navigation()

        bottom = ttk.Frame(self, padding=(20, 0, 20, 14))
        bottom.pack(fill="x")
        ttk.Label(bottom, text=self.t("privacy"), style="Muted.TLabel").pack(side="left")
        ttk.Button(bottom, text=self.t("export"), command=self.export_report).pack(side="right")
        ttk.Button(bottom, text=self.t("diagnostics"), command=self.export_diagnostics).pack(side="right", padx=6)

    def _draw_page_decor(self, canvas) -> None:
        canvas.delete("all"); w = max(200, canvas.winfo_width())
        canvas.create_line(0, 6, 120, 6, 130, 12, w-120, 12, w-108, 3, w, 3, fill=BORDER, width=1)
        canvas.create_line(0, 6, 84, 6, fill=BLUE, width=2)
        for x in range(w-94, w-34, 12): canvas.create_oval(x, 1, x+4, 5, fill=GREEN, outline="")

    def _sync_nav_scrollregion(self, event=None) -> None:
        self.nav_canvas.configure(scrollregion=self.nav_canvas.bbox("all"))

    def _sync_nav_width(self, event) -> None:
        self.nav_canvas.itemconfigure(self.nav_window, width=max(180, event.width))

    def _scroll_navigation(self, event) -> str:
        self.nav_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _nav_button(self, parent, text: str, index: int) -> tk.Button:
        button = tk.Button(parent, text=text, command=lambda i=index: self._select_nav(i), anchor="w",
                           bg=NAV_BG, fg=MUTED, activebackground="#252a33", activeforeground=TEXT,
                           relief="flat", bd=0, padx=12, pady=8, font=("Segoe UI", 10), cursor="hand2")
        button.pack(fill="x", padx=6, pady=1)
        button.bind("<MouseWheel>", self._scroll_navigation)
        return button

    def _build_navigation(self) -> None:
        groups = (
            ("OVERVIEW", (("largest", 0), ("treemap", 1), ("changes", 2))),
            ("CLEANUP & ANALYSIS", (("projects", 3), ("duplicates", 4), ("junk", 5), ("apps", 6))),
            ("SYSTEM", (("system", 7), ("memory", 8))),
            ("TOOLS", (("monitor", 9), ("tools", 10))),
        )
        self.nav_buttons: list[tuple[int, tk.Button]] = []
        for group_name, items in groups:
            label = tk.Label(self.nav_rail, text=group_name, bg=NAV_BG, fg="#6f7887", anchor="w",
                             font=("Segoe UI Semibold", 8), padx=12, pady=6)
            label.pack(fill="x", pady=(8, 0)); label.bind("<MouseWheel>", self._scroll_navigation)
            for key, index in items:
                self.nav_buttons.append((index, self._nav_button(self.nav_rail, self.t(key), index)))
        settings_button = self._nav_button(self.nav_settings_host, self.t("settings"), 11)
        self.nav_buttons.append((11, settings_button))
        offline = tk.Label(self.nav_settings_host, text="Offline • no telemetry", bg=NAV_BG, fg=GREEN, font=("Segoe UI", 8))
        offline.pack(anchor="w", padx=12, pady=(4, 0))
        self.nav_canvas.bind("<MouseWheel>", self._scroll_navigation)
        self.nav_rail.bind("<MouseWheel>", self._scroll_navigation)
        self._select_nav(0)

    def _select_nav(self, index: int) -> None:
        self.tabs.select(index)
        descriptions = {
            0: "Understand what is using storage and review the largest items.",
            1: "Explore disk usage visually by folder or file type.",
            2: "Compare the current scan with the previous snapshot.",
            3: "Review development projects, dependencies and rebuildable output.",
            4: "Find byte-identical files with SHA-256 verification.",
            5: "Review safe, caution and Windows-managed cleanup candidates.",
            6: "Inventory applications and use staged, verified uninstall workflows.",
            7: "Inspect system storage, startup items, services and virtual platforms.",
            8: "Measure real memory pressure and review high-memory applications.",
            9: "Capture before/after installation changes for future removal evidence.",
            10: "Open supported Windows maintenance and recovery tools.",
            11: "Configure language, performance and local cleanup rules.",
        }
        keys = ("largest", "treemap", "changes", "projects", "duplicates", "junk", "apps", "system", "memory", "monitor", "tools", "settings")
        self.page_title_var.set(self.t(keys[index])); self.page_desc_var.set(descriptions[index])
        for nav_index, button in getattr(self, "nav_buttons", []):
            if nav_index == index:
                button.configure(bg="#253348", fg=TEXT, font=("Segoe UI Semibold", 10), highlightbackground=BLUE, highlightthickness=1)
            else:
                button.configure(bg=NAV_BG, fg=MUTED, font=("Segoe UI", 10), highlightthickness=0)

    def _tree(self, parent, columns: tuple[str, ...], widths: tuple[int, ...]) -> ttk.Treeview:
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended")
        for col, width in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=width, minwidth=70, anchor="w")
        y = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        x = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        frame.columnconfigure(0, weight=1); frame.rowconfigure(0, weight=1)
        tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        tree.bind("<Double-1>", lambda e: self._open_selected(tree))
        tree.bind("<Button-3>", lambda e: self._context_menu(e, tree))
        return tree

    def _all_searchable_trees(self) -> list[ttk.Treeview]:
        names = ("largest_tree", "change_tree", "project_tree", "duplicate_tree", "cleanup_tree", "apps_tree", "insight_tree", "memory_tree", "monitor_tree")
        return [getattr(self, name) for name in names if hasattr(self, name)]

    def _apply_search(self) -> None:
        query = self.search_var.get().strip().casefold() if hasattr(self, "search_var") else ""
        for tree in self._all_searchable_trees():
            detached = self.detached_rows.setdefault(tree, [])
            for iid in list(detached):
                if tree.exists(iid): tree.move(iid, "", "end")
            detached.clear()
            if not query: continue
            for iid in list(tree.get_children("")):
                values = " ".join(str(x) for x in tree.item(iid, "values")).casefold()
                if query not in values:
                    tree.detach(iid); detached.append(iid)

    def _clear_search(self) -> None:
        self.search_var.set("")
        self._apply_search()

    def _build_tables(self) -> None:
        self.largest_tree = self._tree(self.overview_tab, ("Type", "Size", "Modified", "Path"), (110, 120, 150, 700))
        self.change_tree = self._tree(self.changes_tab, ("Change", "Size / delta", "Path"), (130, 140, 850))
        self.project_tree = self._tree(self.projects_tab, ("Ecosystem", "Total", "Dependencies", "Build/cache", "Reclaimable", "Rebuild command", "Project"), (105, 90, 105, 100, 105, 170, 440))
        clean_top = ttk.Frame(self.cleanup_tab)
        clean_top.pack(fill="x", pady=(0, 8))
        ttk.Label(clean_top, text="SAFE = regenerable • REVIEW = inspect first • SYSTEM = use Microsoft's cleanup tool", style="Muted.TLabel").pack(side="left")
        ttk.Button(clean_top, text="Scan all known junk", command=self.scan_caches).pack(side="right", padx=4)
        ttk.Button(clean_top, text="Move cache to another drive", command=self.migrate_selected_cache).pack(side="right", padx=4)
        ttk.Button(clean_top, text="Recycle selected", style="Danger.TButton", command=self.recycle_selected).pack(side="right", padx=4)
        self.cleanup_tree = self._tree(self.cleanup_tab, ("Safety", "Size", "Category", "Reason", "Path"), (90, 110, 155, 360, 450))
        apps_top = ttk.Frame(self.apps_tab)
        apps_top.pack(fill="x", pady=(0, 8))
        ttk.Label(apps_top, text="Desktop + Store/MSIX apps. Safe flow: inventory → publisher uninstall → verify → review leftovers.", style="Muted.TLabel").pack(side="left")
        ttk.Button(apps_top, text="Scan leftovers", command=self.scan_app_leftovers).pack(side="right", padx=4)
        ttk.Button(apps_top, text="Safe uninstall selected", style="Danger.TButton", command=self.uninstall_selected_app).pack(side="right", padx=4)
        ttk.Button(apps_top, text="Refresh all apps", command=self.load_apps).pack(side="right", padx=4)
        self.apps_tree = self._tree(self.apps_tab, ("Type", "Estimated size", "Name", "Version", "Publisher", "Install location"), (100, 110, 260, 120, 210, 390))

    def _build_advanced_tabs(self) -> None:
        # Treemap is intentionally based on non-overlapping immediate children of the scan root.
        map_top = ttk.Frame(self.treemap_tab)
        map_top.pack(fill="x", pady=(0, 6))
        self.treemap_path_var = tk.StringVar(value="Scan root")
        ttk.Label(map_top, textvariable=self.treemap_path_var, style="Muted.TLabel").pack(side="left", fill="x", expand=True)
        ttk.Button(map_top, text="Back", command=self._treemap_back).pack(side="right", padx=3)
        ttk.Button(map_top, text="File types", command=lambda: self._set_treemap_mode("types")).pack(side="right", padx=3)
        ttk.Button(map_top, text="Folders", command=lambda: self._set_treemap_mode("folders")).pack(side="right", padx=3)
        self.treemap_canvas = tk.Canvas(self.treemap_tab, bg=PANEL, highlightthickness=0)
        self.treemap_canvas.pack(fill="both", expand=True)
        self.treemap_canvas.bind("<Configure>", lambda e: self._draw_treemap())

        dup_top = ttk.Frame(self.duplicates_tab)
        dup_top.pack(fill="x", pady=(0, 8))
        ttk.Label(dup_top, text="SHA-256 byte-identical files only; hard links are not counted as separate space.", style="Muted.TLabel").pack(side="left")
        ttk.Button(dup_top, text="Recycle selected copies", style="Danger.TButton", command=self.recycle_duplicate_selected).pack(side="right", padx=4)
        ttk.Button(dup_top, text="Find duplicates", command=self.start_duplicate_scan).pack(side="right", padx=4)
        self.duplicate_tree = self._tree(self.duplicates_tab, ("Group", "File size", "Potential saving", "Path"), (80, 110, 130, 750))

        insight_top = ttk.Frame(self.insights_tab)
        insight_top.pack(fill="x", pady=(0, 8))
        ttk.Label(insight_top, text="Analysis-only inventory. Manage services, tasks, Docker, WSL and virtual disks through their owning tools.", style="Muted.TLabel").pack(side="left")
        ttk.Button(insight_top, text="Load startup/services", command=self.load_startup).pack(side="right", padx=4)
        ttk.Button(insight_top, text="Load system/VM storage", command=self.load_insights).pack(side="right", padx=4)
        self.insight_tree = self._tree(self.insights_tab, ("Category", "Name", "Value / size", "Safety note"), (130, 260, 380, 410))

        mon_top = ttk.Frame(self.monitor_tab)
        mon_top.pack(fill="x", pady=(0, 8))
        ttk.Label(mon_top, text="For future installs: snapshot before and after. Changes are evidence for review—not automatic ownership proof.", style="Muted.TLabel").pack(side="left")
        ttk.Button(mon_top, text="Finish & compare", command=self.finish_install_monitor).pack(side="right", padx=4)
        ttk.Button(mon_top, text="Begin snapshot", command=self.begin_install_monitor).pack(side="right", padx=4)
        self.monitor_tree = self._tree(self.monitor_tab, ("Time", "Action", "Details"), (160, 220, 800))
        self.refresh_history()

    def _build_memory_center(self) -> None:
        head = ttk.Frame(self.memory_tab, style="Panel.TFrame", padding=12)
        head.pack(fill="x", pady=(0, 8))
        self.memory_canvas = tk.Canvas(head, width=190, height=184, bg=PANEL, highlightthickness=0)
        self.memory_canvas.pack(side="left", padx=(0, 16))
        stats = ttk.Frame(head, style="Panel.TFrame")
        stats.pack(side="left", fill="both", expand=True)
        self.memory_vars = {key: tk.StringVar(value="—") for key in ("load", "available", "commit", "cache", "pools", "objects", "pressure")}
        memory_stats = (("PHYSICAL LOAD", "load"), ("AVAILABLE NOW", "available"), ("SYSTEM COMMIT", "commit"),
                        ("SYSTEM CACHE", "cache"), ("KERNEL POOLS", "pools"), ("PROCESSES / HANDLES", "objects"),
                        ("PRESSURE", "pressure"))
        for row, (title, key) in enumerate(memory_stats):
            ttk.Label(stats, text=title, style="MetricName.TLabel").grid(row=row, column=0, sticky="w", padx=(0, 16), pady=4)
            ttk.Label(stats, textvariable=self.memory_vars[key], style="MetricName.TLabel", foreground=TEXT).grid(row=row, column=1, sticky="w", pady=4)
        note = ttk.Label(head, text="HONEST MEMORY POLICY\nWindows cache is useful. SpaceMedic does not fake free RAM by repeatedly flushing standby memory.\nRelief trims SpaceMedic itself; real gains come from closing a memory-heavy app or reducing startup load.",
                         style="MetricName.TLabel", foreground=MUTED, justify="left", wraplength=420)
        note.pack(side="right", padx=12)

        smart_bar = ttk.Frame(self.memory_tab, style="Card.TFrame", padding=(12, 10))
        smart_bar.pack(fill="x", pady=(0, 8))
        ttk.Button(smart_bar, text="Smart optimize", style="Accent.TButton", command=self.smart_optimize).pack(side="left")
        ttk.Label(smart_bar, text="One guided workflow: assess pressure, review safe app-close candidates, release SpaceMedic memory, verify results, and record every action.",
                  style="MetricName.TLabel", wraplength=760).pack(side="left", padx=14)
        actions = ttk.Frame(self.memory_tab)
        actions.pack(fill="x", pady=(0, 8))
        action_specs = (("Refresh telemetry", self.refresh_memory_center), ("Safe memory relief", self.safe_memory_relief),
                        ("Close selected app", self.close_selected_memory_app), ("Advanced: trim idle app", self.trim_selected_memory_app),
                        ("Explain finding", self.explain_selected_memory_finding),
                        ("Task Manager", open_task_manager), ("Resource Monitor", open_resource_monitor),
                        ("Memory Diagnostic", open_memory_diagnostic), ("Performance options", open_performance_options))
        for col in range(4): actions.columnconfigure(col, weight=1)
        for index, (text, command) in enumerate(action_specs):
            ttk.Button(actions, text=text, command=command).grid(row=index // 4, column=index % 4, sticky="ew", padx=2, pady=2)
        self.memory_plan_var = tk.StringVar(value="Collecting a baseline. Leak analysis needs sustained samples; no immediate spike is labeled a leak.")
        ttk.Label(self.memory_tab, textvariable=self.memory_plan_var, style="Muted.TLabel", wraplength=1050).pack(fill="x", pady=(0, 8))
        self.memory_tree = self._tree(
            self.memory_tab,
            ("PID", "Process", "Working set", "Private bytes", "Handles", "GDI", "Growth / hour", "Confidence", "State / window"),
            (70, 150, 110, 110, 85, 70, 120, 95, 330)
        )
        self.after(1200, self.refresh_memory_center)

    def _draw_memory_gauge(self, load: int, pressure: str) -> None:
        c = self.memory_canvas; c.delete("all")
        color = GREEN if pressure == "healthy" else AMBER if pressure in {"moderate", "high"} else RED
        c.create_arc(18, 10, 172, 164, start=135, extent=270, style="arc", outline="#173e51", width=14)
        c.create_arc(18, 10, 172, 164, start=135, extent=270 * min(100, load) / 100, style="arc", outline=color, width=14)
        c.create_text(95, 72, text=f"{load}%", fill=TEXT, font=("Segoe UI Semibold", 25))
        c.create_text(95, 103, text="PHYSICAL RAM", fill=MUTED, font=("Consolas", 9))
        c.create_line(54,127,136,127, fill=color, width=2)

    def refresh_memory_center(self) -> None:
        if os.name != "nt" or self._memory_refresh_running: return
        self._memory_refresh_running = True
        if self._memory_timer:
            try: self.after_cancel(self._memory_timer)
            except Exception: pass
            self._memory_timer = None
        self.status_var.set("Reading Windows memory telemetry, process commit and resource trends…")
        def work():
            try:
                snap, rows = memory_snapshot(), memory_processes()
                fg = foreground_pid()
                self.memory_intelligence.record(snap, rows, fg)
                findings = self.memory_intelligence.findings(rows)
                plan = self.memory_intelligence.plan(snap, rows, findings)
                self.after(0, done, snap, rows, findings, plan, None)
            except Exception as exc:
                self.after(0, done, None, [], [], None, str(exc))
        def done(snap, rows, findings, plan, error):
            self._memory_refresh_running = False
            if error:
                self.status_var.set(f"Memory telemetry failed: {error}")
                self._memory_timer = self.after(60000, self.refresh_memory_center)
                return
            self.memory_findings = findings
            self.memory_vars["load"].set(f"{snap.load_percent}% of {format_bytes(snap.total_physical)}")
            self.memory_vars["available"].set(format_bytes(snap.available_physical))
            self.memory_vars["commit"].set(f"{format_bytes(snap.commit_total)} / {format_bytes(snap.commit_limit)}")
            self.memory_vars["cache"].set(format_bytes(snap.system_cache))
            self.memory_vars["pools"].set(f"Paged {format_bytes(snap.kernel_paged)} • Nonpaged {format_bytes(snap.kernel_nonpaged)}")
            self.memory_vars["objects"].set(f"{snap.process_count:,} processes • {snap.handle_count:,} handles")
            low_note = " • Windows low-memory signal" if self.memory_intelligence.low_memory_signal() else ""
            self.memory_vars["pressure"].set(snap.pressure.upper() + low_note)
            self._draw_memory_gauge(snap.load_percent, snap.pressure)
            finding_map = {f.identity: f for f in findings}
            current_fg = foreground_pid()
            self._clear(self.memory_tree)
            for item in rows[:250]:
                finding = finding_map.get(self.memory_intelligence.identity(item))
                state = "PROTECTED" if item.protected else ("FOREGROUND" if item.pid == current_fg else (item.window_title or "Background process"))
                growth = confidence = "—"
                if finding:
                    growth = format_bytes(int(finding.rate_per_hour)) + "/h" if "memory" in finding.kind else f"{finding.rate_per_hour:.0f}/h"
                    confidence = f"{finding.confidence * 100:.0f}% {finding.kind}"
                    state = "REVIEW: " + state
                iid = self.memory_tree.insert("", "end", iid=self._new_iid(), values=(
                    item.pid, item.name, format_bytes(item.working_set), format_bytes(item.private_bytes),
                    f"{item.handle_count:,}", f"{item.gdi_count:,}", growth, confidence, state
                ), tags=("memory-alert" if finding else "",))
                self.row_objects[iid] = item
            self.memory_tree.tag_configure("memory-alert", foreground=AMBER)
            recs = "  •  ".join(plan.recommendations[:3]) if plan.recommendations else "No intervention recommended."
            self.memory_plan_var.set(f"{plan.headline}. {recs} Automatic action: {plan.automatic_action}.")
            self.status_var.set(f"Memory intelligence updated • {snap.pressure} pressure • {format_bytes(snap.available_physical)} available • {len(findings)} sustained finding(s)")
            self._apply_search()
            self._memory_timer = self.after(60000, self.refresh_memory_center)
        threading.Thread(target=work, daemon=True).start()

    def _selected_memory_process(self) -> ProcessMemory | None:
        selected = self.memory_tree.selection()
        if len(selected) != 1: messagebox.showinfo(APP_NAME, "Select exactly one process in Memory Center."); return None
        item = self.row_objects.get(selected[0])
        return item if isinstance(item, ProcessMemory) else None

    def smart_optimize(self) -> None:
        if os.name != "nt": return
        self.status_var.set("Building a safe optimization plan…")
        def work():
            try:
                snapshot, rows = memory_snapshot(), memory_processes()
                findings = self.memory_intelligence.findings(rows)
                plan = self.memory_intelligence.plan(snapshot, rows, findings)
                self.after(0, self._show_smart_optimize_dialog, snapshot, rows, findings, plan)
            except Exception as exc:
                self.after(0, messagebox.showerror, APP_NAME, str(exc))
        threading.Thread(target=work, daemon=True).start()

    def _show_smart_optimize_dialog(self, snapshot, rows, findings, plan) -> None:
        fg = foreground_pid()
        candidates = [p for p in rows if not p.protected and p.pid != fg and p.window_title]
        candidates.sort(key=lambda p: (p.private_bytes, p.working_set), reverse=True)
        candidates = candidates[:8]
        dialog = tk.Toplevel(self)
        dialog.title("Smart optimize — review plan")
        dialog.geometry("760x620")
        dialog.minsize(680, 520)
        dialog.configure(bg=BG)
        dialog.transient(self); dialog.grab_set()
        outer = ttk.Frame(dialog, padding=20)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Smart optimization plan", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(outer, text=f"{plan.headline} • {snapshot.load_percent}% physical load • {format_bytes(snapshot.available_physical)} available • {format_bytes(snapshot.commit_total)} / {format_bytes(snapshot.commit_limit)} commit",
                  style="Muted.TLabel", wraplength=700).pack(anchor="w", pady=(4, 14))
        info = ttk.Frame(outer, style="Card.TFrame", padding=12)
        info.pack(fill="x", pady=(0, 12))
        ttk.Label(info, text="What SpaceMedic will do", style="MetricName.TLabel", foreground=TEXT).pack(anchor="w")
        ttk.Label(info, text="1. Release only SpaceMedic’s own unused memory.\n2. Ask only the apps you select below to close normally—never force terminate.\n3. Re-measure available memory and commit after the actions.\n4. Record success, failure, and real before/after values.\n\nIt will not flush standby cache, disable services, alter CPU priority, modify the pagefile, or claim to make the processor physically faster.",
                  style="Muted.TLabel", justify="left", wraplength=690).pack(anchor="w", pady=(6, 0))
        release_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(outer, text="Release SpaceMedic’s own unused working memory", variable=release_var).pack(anchor="w", pady=(2, 8))
        ttk.Label(outer, text="Optional app closures — save work first", style="MetricName.TLabel", foreground=TEXT).pack(anchor="w", pady=(4, 4))
        candidate_frame = ttk.Frame(outer, style="Panel.TFrame", padding=8)
        candidate_frame.pack(fill="both", expand=True)
        selections: list[tuple[ProcessMemory, tk.BooleanVar]] = []
        if not candidates:
            ttk.Label(candidate_frame, text="No safe normal-window candidates were found. System, foreground, protected, and background-service processes are excluded.", style="Muted.TLabel", wraplength=650).pack(anchor="w", padx=6, pady=8)
        for item in candidates:
            variable = tk.BooleanVar(value=False)
            text = f"{item.name}  —  private {format_bytes(item.private_bytes)}  •  working set {format_bytes(item.working_set)}"
            if not item.responding: text += "  •  not responding"
            ttk.Checkbutton(candidate_frame, text=text, variable=variable).pack(anchor="w", fill="x", padx=6, pady=3)
            selections.append((item, variable))
        if findings:
            ttk.Label(outer, text=f"{len(findings)} sustained resource-growth finding(s) exist. Trimming cannot repair a leak; investigate or restart/update the owning application.",
                      foreground=AMBER, background=BG, wraplength=700).pack(anchor="w", pady=(8, 0))
        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(14, 0))
        ttk.Button(footer, text="Startup apps", command=open_startup_apps).pack(side="left")
        ttk.Button(footer, text="Power mode", command=open_power_mode).pack(side="left", padx=6)
        ttk.Button(footer, text="Cancel", command=dialog.destroy).pack(side="right")
        def execute():
            selected = [item for item, variable in selections if variable.get()]
            dialog.destroy()
            self._execute_smart_optimize(snapshot, selected, release_var.get())
        ttk.Button(footer, text="Run safe optimization", style="Accent.TButton", command=execute).pack(side="right", padx=8)

    def _execute_smart_optimize(self, before, selected: list[ProcessMemory], release_self: bool) -> None:
        self.progress.start(10); self.status_var.set("Running safe optimization and verifying the result…")
        def work():
            own_result = (True, "Skipped")
            if release_self: own_result = trim_self()
            closed, failed = [], []
            current_foreground = foreground_pid()
            live = {p.pid: p for p in memory_processes()}
            for item in selected:
                current = live.get(item.pid)
                if not current or current.name.casefold() != item.name.casefold() or (item.start_key != "0" and current.start_key != item.start_key):
                    failed.append((item.name, "Process ended or PID identity changed")); continue
                if current.protected or current.pid == current_foreground or not current.window_title:
                    failed.append((item.name, "Protected, foreground, or no longer a normal windowed app")); continue
                ok, detail = close_process_gracefully(current.pid)
                (closed if ok else failed).append((item.name, detail))
            time.sleep(2.0)
            try: after = memory_snapshot()
            except Exception: after = before
            self.after(0, done, own_result, closed, failed, after)
        def done(own_result, closed, failed, after):
            self.progress.stop()
            available_delta = after.available_physical - before.available_physical
            commit_delta = after.commit_total - before.commit_total
            record_history("smart_optimize", developer=DEVELOPER, self_trim=own_result, closed=closed, failed=failed,
                           available_before=before.available_physical, available_after=after.available_physical,
                           commit_before=before.commit_total, commit_after=after.commit_total)
            report = (
                f"Safe optimization completed.\n\n"
                f"Available memory: {format_bytes(before.available_physical)} → {format_bytes(after.available_physical)} "
                f"({'+' if available_delta >= 0 else '-'}{format_bytes(abs(available_delta))})\n"
                f"System commit: {format_bytes(before.commit_total)} → {format_bytes(after.commit_total)} "
                f"({'+' if commit_delta >= 0 else '-'}{format_bytes(abs(commit_delta))})\n"
                f"Apps closed normally: {len(closed)}\nFailed/skipped: {len(failed)}\n\n"
                "Results can fluctuate while Windows and applications run. A larger free-memory number alone is not proof of faster performance."
            )
            messagebox.showinfo("Smart optimize result", report)
            self.refresh_memory_center()
            self.refresh_history()
        threading.Thread(target=work, daemon=True).start()

    def explain_selected_memory_finding(self) -> None:
        item = self._selected_memory_process()
        if not item: return
        identity = self.memory_intelligence.identity(item)
        matches = [f for f in self.memory_findings if f.identity == identity]
        if not matches:
            messagebox.showinfo("Memory intelligence", "No sustained leak/resource-growth finding exists for this process yet. A meaningful result needs at least eight samples over five minutes; workload growth is not automatically a leak.")
            return
        text = []
        for finding in matches:
            rate = format_bytes(int(finding.rate_per_hour)) + "/hour" if "memory" in finding.kind else f"{finding.rate_per_hour:.0f}/hour"
            text.append(f"{finding.kind}\nConfidence: {finding.confidence*100:.0f}%\nRate: {rate}\nCurrent value: {finding.current_value:,}\nObserved: {finding.duration_seconds/60:.0f} minutes\n\n{finding.explanation}")
        messagebox.showwarning(f"Review {item.name}", "\n\n────────────\n\n".join(text))

    def safe_memory_relief(self) -> None:
        try:
            before = memory_snapshot(); ok, detail = trim_self(); after = memory_snapshot()
            gained = max(0, after.available_physical - before.available_physical)
            record_history("safe_memory_relief", success=ok, available_delta=gained, detail=detail)
            messagebox.showinfo("Safe memory relief", f"SpaceMedic released its own unused Python memory and requested a trim of its own working set.\n\nAvailable-memory change: {format_bytes(gained)}\n\nNo other app, standby cache, pagefile, service, or system process was modified. This is not a magic speed boost.")
            self.refresh_memory_center()
        except Exception as exc: messagebox.showerror(APP_NAME, str(exc))

    def close_selected_memory_app(self) -> None:
        item = self._selected_memory_process()
        if not item: return
        if item.protected:
            messagebox.showwarning(APP_NAME, "This process is protected by SpaceMedic's safety policy and cannot be closed here."); return
        if not item.window_title:
            messagebox.showwarning(APP_NAME, "This process has no normal app window. Use its own exit command or Task Manager after verifying ownership."); return
        if not messagebox.askyesno(APP_NAME, f"Ask {item.name} (PID {item.pid}) to close normally?\n\nSave work first. SpaceMedic will not use force termination.", icon="warning"): return
        ok, detail = close_process_gracefully(item.pid)
        record_history("memory_close_app", pid=item.pid, process=item.name, success=ok, detail=detail)
        (messagebox.showinfo if ok else messagebox.showerror)(APP_NAME, detail or ("Close request sent" if ok else "Close request failed"))
        self.after(800, self.refresh_memory_center)

    def trim_selected_memory_app(self) -> None:
        item = self._selected_memory_process()
        if not item: return
        if item.protected: messagebox.showwarning(APP_NAME, "Protected/system processes cannot be trimmed here."); return
        warning = (f"Trim the working set of {item.name} (PID {item.pid})?\n\n"
                   "Microsoft documents EmptyWorkingSet primarily for testing and tuning. The visible RAM number may drop temporarily, but the app can page-fault data back and become slower. This does not reduce its committed/private memory or fix a leak. Use only on an idle app under real memory pressure.")
        if not messagebox.askyesno("Advanced working-set trim", warning, icon="warning"): return
        ok, detail = trim_process(item.pid)
        record_history("memory_trim_process", pid=item.pid, process=item.name, success=ok, detail=detail)
        (messagebox.showinfo if ok else messagebox.showerror)(APP_NAME, detail)
        self.after(500, self.refresh_memory_center)

    def _build_tools(self) -> None:
        intro = ttk.Label(self.tools_tab, text="Use Microsoft-supported tools for Windows system files. SpaceMedic never manually deletes WinSxS, System32, pagefile.sys, or update components.", wraplength=1050)
        intro.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))
        tools = [
            ("Emergency rescue scan", "Measures safe/review/system junk first and builds a staged low-space recovery list without automatic deletion.", self.scan_caches),
            ("Temporary files & Storage Sense", "Microsoft cleanup for old updates, WER reports, dumps, thumbnails, Delivery Optimization, shader cache and Windows.old.", wt.launch_storage_settings),
            ("Disk Cleanup (system files)", "Review Windows Update Cleanup, error reports, memory dumps, temporary setup files and previous installations.", wt.launch_cleanup),
            ("Analyze old update components", "Read-only DISM component-store analysis: true size, reclaimable packages and cleanup recommendation.", wt.analyze_component_store),
            ("Clean superseded update components", "Runs standard DISM StartComponentCleanup. Irreversible /ResetBase is intentionally never used.", self._confirm_component_cleanup),
            ("Clear Delivery Optimization cache", "Uses the Windows PowerShell cmdlet; update payloads can be downloaded again when needed.", self._confirm_delivery_cleanup),
            ("Reliability Monitor / crash history", "Inspect app crashes and Windows failures before removing WER reports or memory dumps.", wt.launch_reliability_monitor),
            ("Windows Update history", "Check recently installed updates before removing previous-installation rollback files.", wt.launch_update_history),
            ("Delivery Optimization settings", "Control downloads from other PCs so the update-sharing cache is less likely to grow again.", wt.launch_delivery_optimization),
            ("System file integrity check", "Runs Microsoft SFC /scannow. This repairs protected files; it is not a space cleaner.", self._confirm_sfc),
            ("Restore points / shadow storage", "Inspect VSS allocation, then open System Protection to manage it without manually deleting snapshots.", wt.inspect_shadow_storage),
            ("System Protection settings", "Create or manage restore points through Windows.", wt.launch_system_protection),
            ("Reserved Storage status", "Read-only DISM query; reserved space helps Windows updates succeed.", wt.inspect_reserved_storage),
            ("Disable hibernation", "Can recover several GB, but disables Hibernate and Fast Startup. Reversible with powercfg /hibernate on.", self._confirm_hibernate),
            ("Installed apps", "Uninstall large, unused software through Windows Settings—never delete Program Files manually.", wt.launch_uninstall_settings),
        ]
        for col in range(3): self.tools_tab.columnconfigure(col, weight=1)
        for index, (title, desc, cmd) in enumerate(tools):
            row = ttk.Frame(self.tools_tab, style="Panel.TFrame", padding=10)
            row.grid(row=1 + index // 3, column=index % 3, sticky="nsew", padx=4, pady=4)
            ttk.Label(row, text=title, style="MetricName.TLabel", foreground=TEXT).pack(anchor="w")
            ttk.Label(row, text=desc, style="MetricName.TLabel", wraplength=290).pack(anchor="w", fill="x", pady=(3, 8))
            ttk.Button(row, text="Open / Run", command=cmd).pack(anchor="e")

    def _show_onboarding(self) -> None:
        message = (
            "Welcome to SpaceMedic Public Edition.\n\n"
            "• Scans are read-only until you explicitly choose an action.\n"
            "• SpaceMedic works offline and sends no telemetry.\n"
            "• Review every cleanup candidate; keep backups of irreplaceable data.\n"
            "• System, driver, security, WSL and VM data must use supported Windows/vendor workflows.\n"
            "• Diagnostic bundles are saved locally and must be reviewed before sharing.\n\n"
            "Choose your interface language in Settings."
        )
        messagebox.showinfo("Welcome to SpaceMedic", message)
        self.settings.onboarding_complete = True
        save_settings(self.settings)

    def _build_settings(self) -> None:
        ttk.Label(self.settings_tab, text="Public edition settings", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self.settings_tab, text=f"SpaceMedic {VERSION} • Developed by {DEVELOPER} • MIT licensed • Offline by default", style="Muted.TLabel").pack(anchor="w", pady=(2, 12))
        panel = ttk.Frame(self.settings_tab, style="Panel.TFrame", padding=16)
        panel.pack(fill="x")
        ttk.Label(panel, text="Interface language", style="MetricName.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=6)
        self.language_var = tk.StringVar(value=LANGUAGES.get(self.settings.language, "English"))
        language_box = ttk.Combobox(panel, textvariable=self.language_var, values=list(LANGUAGES.values()), state="readonly", width=24)
        language_box.grid(row=0, column=1, sticky="w", pady=6)
        ttk.Label(panel, text="Interface theme", style="MetricName.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 12), pady=6)
        self.theme_var = tk.StringVar(value="Orbital HUD" if self.settings.theme == "hud" else "Professional Dark")
        ttk.Combobox(panel, textvariable=self.theme_var, values=("Orbital HUD", "Professional Dark"), state="readonly", width=24).grid(row=1, column=1, sticky="w", pady=6)
        ttk.Label(panel, text="Fast-scan workers (0 = automatic)", style="MetricName.TLabel").grid(row=2, column=0, sticky="w", padx=(0, 12), pady=6)
        self.worker_var = tk.IntVar(value=self.settings.scan_workers)
        ttk.Spinbox(panel, from_=0, to=16, textvariable=self.worker_var, width=8).grid(row=2, column=1, sticky="w", pady=6)
        ttk.Label(panel, text="Privacy", style="MetricName.TLabel").grid(row=3, column=0, sticky="w", padx=(0, 12), pady=6)
        ttk.Label(panel, text="Fully offline. No telemetry, analytics, account, or automatic upload.", style="MetricName.TLabel").grid(row=3, column=1, sticky="w", pady=6)
        ttk.Button(panel, text="Save settings", style="Accent.TButton", command=self._save_public_settings).grid(row=4, column=1, sticky="w", pady=(14, 4))
        ttk.Button(panel, text="Open community cleanup rules", command=self._open_user_rules).grid(row=5, column=1, sticky="w", pady=4)
        ttk.Separator(self.settings_tab).pack(fill="x", pady=18)
        ttk.Label(self.settings_tab, text="Safety defaults", style="MetricName.TLabel", foreground=TEXT).pack(anchor="w")
        ttk.Label(self.settings_tab, text="• Read-only scanning by default\n• Recycle Bin for approved files\n• Microsoft/vendor tools for protected components\n• No generic Registry cleaner\n• Destructive actions require explicit confirmation", style="Muted.TLabel", justify="left").pack(anchor="w", pady=8)

    def _open_user_rules(self) -> None:
        target = user_rules_path()
        if not target.exists():
            try: target.write_text("[]\n", encoding="utf-8")
            except OSError as exc: messagebox.showerror(APP_NAME, str(exc)); return
        wt.reveal_path(str(target))
        messagebox.showinfo(APP_NAME, "Rules are JSON and load on the next junk scan. Absolute paths and '..' traversal are rejected. SYSTEM rules can never enable direct cleanup. Review community rules before installing them.")

    def _save_public_settings(self) -> None:
        reverse = {name: code for code, name in LANGUAGES.items()}
        self.settings.language = reverse.get(self.language_var.get(), "en")
        self.settings.theme = "hud" if self.theme_var.get() == "Orbital HUD" else "professional"
        try: self.settings.scan_workers = max(0, min(16, int(self.worker_var.get())))
        except (ValueError, tk.TclError): self.settings.scan_workers = 0
        self.settings.last_scan_path = self.path_var.get()
        self.settings.onboarding_complete = True
        self.settings.update_checks = False
        save_settings(self.settings)
        messagebox.showinfo(APP_NAME, "Restart SpaceMedic to apply the selected language and interface theme.")

    def _dismiss_alert(self) -> None:
        for child in self.alert_host.winfo_children(): child.destroy()

    def _show_inline_alert(self, title: str, message: str, level: str = "warning", action_text: str = "Review", action=None) -> None:
        self._dismiss_alert()
        palette = {
            "warning": ("#332a18", AMBER, "!"),
            "error": ("#3a2024", RED, "×"),
            "info": ("#1b2b3b", BLUE, "i"),
            "success": ("#173126", GREEN, "✓"),
        }
        background, accent, symbol = palette.get(level, palette["warning"])
        panel = tk.Frame(self.alert_host, bg=background, highlightbackground=accent, highlightthickness=1)
        panel.pack(fill="x", padx=20, pady=(10, 0))
        icon = tk.Label(panel, text=symbol, bg=accent, fg="#101217", width=2, font=("Segoe UI Semibold", 13))
        icon.pack(side="left", fill="y")
        copy = tk.Frame(panel, bg=background)
        copy.pack(side="left", fill="x", expand=True, padx=12, pady=9)
        tk.Label(copy, text=title, bg=background, fg=TEXT, anchor="w", font=("Segoe UI Semibold", 10)).pack(fill="x")
        tk.Label(copy, text=message, bg=background, fg=MUTED, anchor="w", justify="left", wraplength=900, font=("Segoe UI", 9)).pack(fill="x", pady=(2, 0))
        ttk.Button(panel, text="Dismiss", command=self._dismiss_alert).pack(side="right", padx=(4, 10), pady=10)
        if action:
            ttk.Button(panel, text=action_text, style="Accent.TButton", command=action).pack(side="right", padx=4, pady=10)

    def refresh_drive(self) -> None:
        try:
            path = self.path_var.get()
            anchor = Path(path).anchor or path
            total, used, free = wt.drive_stats(anchor)
            self.metric_vars[0].set(f"{format_bytes(used)} / {format_bytes(total)}")
            self.metric_vars[1].set(format_bytes(free))
        except OSError:
            pass

    def browse(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.path_var.get() if os.path.exists(self.path_var.get()) else None)
        if selected:
            self.path_var.set(selected)
            self.refresh_drive()

    def start_scan(self) -> None:
        self.scan_backend = "recursive"
        path = os.path.abspath(os.path.expandvars(os.path.expanduser(self.path_var.get().strip())))
        if not os.path.isdir(path):
            messagebox.showerror(APP_NAME, "Please choose an existing folder or drive.")
            return
        self.path_var.set(path)
        self.settings.last_scan_path = path
        save_settings(self.settings)
        self.cancel.clear()
        self.scan_btn.configure(state="disabled")
        self.fast_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.progress.start(10)
        self.status_var.set("Scanning read-only… protected/inaccessible files will be counted as errors, not modified.")
        self.worker = threading.Thread(target=self._scan_worker, args=(path,), daemon=True)
        self.worker.start()

    def start_fast_scan(self) -> None:
        path = os.path.abspath(os.path.expandvars(os.path.expanduser(self.path_var.get().strip())))
        if not os.path.isdir(path): messagebox.showerror(APP_NAME, "Choose an existing drive/folder."); return
        has_mft, detail = fast_scan_available()
        use_mft = bool(has_mft and os.name == "nt" and wt.is_admin())
        if has_mft and os.name == "nt" and not wt.is_admin():
            use_mft = False  # accelerated native fallback works without elevation
        self.scan_backend = "wiztree-mft" if use_mft else "parallel-native"
        self.path_var.set(path); self.settings.last_scan_path = path; save_settings(self.settings)
        self.cancel.clear(); self.scan_btn.configure(state="disabled"); self.fast_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal"); self.progress.start(10)
        if use_mft:
            self.status_var.set(f"Optional MFT provider: {detail}. Exporting and validating CSV…")
        else:
            self.status_var.set("Dependency-free fast scan: scanning independent top-level branches in parallel…")
        self.worker = threading.Thread(target=self._fast_scan_worker, args=(path, use_mft), daemon=True); self.worker.start()

    def _fast_scan_worker(self, path: str, use_mft: bool) -> None:
        try:
            callback = lambda p, f, d: self.after(0, self._progress_update, p, f, d)
            result = fast_scan(path, self.cancel, callback) if use_mft else ParallelDiskScanner(workers=self.settings.scan_workers or None).scan(path, self.cancel, callback)
            self.after(0, self._scan_done, result)
        except Exception as exc:
            self.after(0, self._scan_failed, f"Fast scan failed safely: {exc}\n\nUse the standard Analyze scanner as fallback.")

    def _scan_worker(self, path: str) -> None:
        try:
            scanner = DiskScanner()
            result = scanner.scan(path, self.cancel, lambda p, f, d: self.after(0, self._progress_update, p, f, d))
            self.after(0, self._scan_done, result)
        except Exception as exc:
            self.after(0, self._scan_failed, str(exc))

    def _progress_update(self, path: str, files: int, folders: int) -> None:
        short = path if len(path) < 110 else "…" + path[-107:]
        self.status_var.set(f"{files:,} files • {folders:,} folders • {short}")

    def stop_scan(self) -> None:
        self.cancel.set()
        self.status_var.set("Stopping safely…")

    def _scan_done(self, result: ScanResult) -> None:
        self.result = result
        self.progress.stop()
        self.scan_btn.configure(state="normal")
        self.fast_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.metric_vars[2].set(format_bytes(result.total_size))
        self.metric_vars[3].set(format_bytes(result.reclaimable + sum(x.size for x in self.cache_items)))
        duration = result.finished - result.started
        previous = latest_scan(result.root)
        self.change_report = compare_scan(previous, result)
        cache_path = save_scan(result, self.scan_backend)
        delta = self.change_report.get("total_delta", 0)
        delta_text = f" • change {format_bytes(abs(delta))} {'larger' if delta > 0 else 'smaller'}" if self.change_report.get("available") and delta else ""
        self.status_var.set(f"{self.scan_backend} done in {duration:.1f}s • {result.file_count:,} files • {result.folder_count:,} folders • {result.errors:,} errors{delta_text}")
        self.treemap_view_root = result.root
        self._populate_result()
        self._draw_treemap()
        record_history("disk_scan", root=result.root, backend=self.scan_backend, total_bytes=result.total_size, files=result.file_count, folders=result.folder_count, errors=result.errors, cache=cache_path, total_delta=delta)
        self.refresh_history()
        self.refresh_drive()

    def _scan_failed(self, error: str) -> None:
        self.progress.stop()
        self.scan_btn.configure(state="normal")
        self.fast_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status_var.set("Scan failed.")
        messagebox.showerror(APP_NAME, error)

    def _populate_result(self) -> None:
        assert self.result
        self._clear(self.largest_tree)
        self._clear(self.project_tree)
        self.row_objects.clear()
        combined = self.result.top_folders[:60] + self.result.top_files[:60]
        combined.sort(key=lambda x: x.size, reverse=True)
        for item in combined[:100]:
            iid = self.largest_tree.insert("", "end", iid=self._new_iid(), values=(item.kind.title(), format_bytes(item.size), self._date(item.modified), item.path))
            self.row_objects[iid] = item
        for project in self.result.projects:
            iid = self.project_tree.insert("", "end", iid=self._new_iid(), values=(project.ecosystem, format_bytes(project.total_size), format_bytes(project.dependency_size),
                format_bytes(project.build_size), format_bytes(project.reclaimable), self._project_rebuild(project), project.root))
            self.row_objects[iid] = project
        self._populate_cleanup()
        self._populate_changes()
        self._apply_search()

    def _populate_changes(self) -> None:
        self._clear(self.change_tree)
        if not self.change_report.get("available"):
            self.change_tree.insert("", "end", iid=self._new_iid(), values=("Baseline", "—", "No previous scan for this location; this scan is now the baseline."))
            return
        for row in self.change_report.get("new_large", []):
            self.change_tree.insert("", "end", iid=self._new_iid(), values=("New large item", format_bytes(row["size"]), row["path"]))
        for row in self.change_report.get("grown", []):
            self.change_tree.insert("", "end", iid=self._new_iid(), values=("Grown", "+" + format_bytes(row["delta"]), row["path"]))
        for row in self.change_report.get("removed", []):
            self.change_tree.insert("", "end", iid=self._new_iid(), values=("No longer in top results", format_bytes(row["previous_size"]), row["path"]))

    def _populate_cleanup(self) -> None:
        self._clear(self.cleanup_tree)
        items = (self.result.cleanup if self.result else []) + self.cache_items + self.app_leftovers
        dedup: dict[str, ScanItem] = {os.path.normcase(x.path): x for x in items}
        for item in sorted(dedup.values(), key=lambda x: x.size, reverse=True):
            if not os.path.exists(item.path):
                continue
            iid = self.cleanup_tree.insert("", "end", iid=self._new_iid(), values=(item.risk.upper(), format_bytes(item.size), item.category, item.reason, item.path),
                                                   tags=(item.risk,))
            self.row_objects[iid] = item
        self.cleanup_tree.tag_configure("safe", foreground=GREEN)
        self.cleanup_tree.tag_configure("review", foreground=AMBER)
        self.cleanup_tree.tag_configure("system", foreground=RED)
        self._apply_search()

    def _set_treemap_mode(self, mode: str) -> None:
        self.treemap_mode = mode
        self._draw_treemap()

    def _treemap_back(self) -> None:
        if not self.result: return
        current = self.treemap_view_root or self.result.root
        if os.path.normcase(current) != os.path.normcase(self.result.root):
            parent = os.path.dirname(current)
            root = os.path.abspath(self.result.root)
            self.treemap_view_root = parent if os.path.normcase(parent).startswith(os.path.normcase(root)) else root
        self._draw_treemap()

    def _draw_treemap(self) -> None:
        canvas = getattr(self, "treemap_canvas", None)
        if not canvas: return
        canvas.delete("all")
        if not self.result:
            canvas.create_text(30, 30, anchor="nw", fill=MUTED, text="Run a disk/folder analysis to generate the treemap.", font=("Segoe UI", 12)); return
        if self.treemap_mode == "types":
            items = [(name, size, "", False) for name, size in list(self.result.extension_sizes.items())[:40]]
            self.treemap_path_var.set("File type distribution")
        else:
            view = self.treemap_view_root or self.result.root
            self.treemap_path_var.set(view)
            view_norm = os.path.normcase(os.path.abspath(view))
            found = [x for x in self.result.top_folders if os.path.normcase(os.path.abspath(os.path.dirname(x.path))) == view_norm]
            found += [x for x in self.result.top_files if os.path.normcase(os.path.abspath(os.path.dirname(x.path))) == view_norm]
            items = [(x.name, x.size, x.path, x.kind == "folder") for x in sorted(found, key=lambda z: z.size, reverse=True)[:40]]
        total = sum(x[1] for x in items)
        if not total:
            canvas.create_text(25, 25, anchor="nw", fill=MUTED, text="No child items are available in the retained top-results cache. Rescan this folder directly for deeper zoom."); return
        width, height = max(100, canvas.winfo_width()), max(100, canvas.winfo_height())
        colors = ["#1f6feb", "#2ea043", "#a371f7", "#d29922", "#db6d28", "#f85149", "#238636", "#388bfd"]
        x = y = 0.0; remaining = total; horizontal = width >= height; available_w, available_h = float(width), float(height)
        for i, (name, size, path, is_folder) in enumerate(items):
            if remaining <= 0: break
            ratio = size / remaining
            if horizontal:
                span = available_w * ratio; coords = (x, y, x + span, y + available_h); x += span; available_w -= span
            else:
                span = available_h * ratio; coords = (x, y, x + available_w, y + span); y += span; available_h -= span
            remaining -= size; horizontal = available_w >= available_h
            tag = f"map-item-{i}"
            canvas.create_rectangle(*coords, fill=colors[i % len(colors)], outline=BG, width=2, tags=(tag,))
            if coords[2] - coords[0] > 90 and coords[3] - coords[1] > 35:
                canvas.create_text(coords[0] + 7, coords[1] + 7, anchor="nw", fill="white", width=max(60, coords[2]-coords[0]-14), text=f"{name}\n{format_bytes(size)}", font=("Segoe UI Semibold", 9), tags=(tag,))
            if path:
                if is_folder: canvas.tag_bind(tag, "<Button-1>", lambda e, p=path: self._treemap_zoom(p))
                canvas.tag_bind(tag, "<Double-1>", lambda e, p=path: wt.reveal_path(p))

    def _treemap_zoom(self, path: str) -> None:
        self.treemap_view_root = path
        self._draw_treemap()

    def start_duplicate_scan(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_NAME, "Another scan is already running."); return
        root = self.path_var.get()
        self.cancel.clear(); self.progress.start(10)
        self.status_var.set("Finding duplicate candidates, then verifying samples and full SHA-256 hashes…")
        def work():
            groups, errors = find_duplicates(root, cancel=self.cancel, progress=lambda p, n: self.after(0, self.status_var.set, f"Duplicate scan: {n:,} files • {p[-80:]}"))
            self.after(0, done, groups, errors)
        def done(groups, errors):
            self.progress.stop(); self.duplicate_groups = groups; self._clear(self.duplicate_tree)
            self.row_objects = {k: v for k, v in self.row_objects.items() if not str(k).startswith("dup-")}
            for gi, group in enumerate(groups, 1):
                for pi, path in enumerate(group.paths):
                    iid = f"dup-{gi}-{pi}-{self._new_iid()}"
                    self.duplicate_tree.insert("", "end", iid=iid, values=(gi, format_bytes(group.size), format_bytes(group.reclaimable), path))
                    self.row_objects[iid] = (gi, path, group)
            saving = sum(g.reclaimable for g in groups)
            self.status_var.set(f"Found {len(groups)} byte-identical groups; maximum theoretical saving {format_bytes(saving)}; {errors} errors.")
            record_history("duplicate_scan", root=root, groups=len(groups), potential_bytes=saving, errors=errors); self.refresh_history(); self._apply_search()
        self.worker = threading.Thread(target=work, daemon=True); self.worker.start()

    def recycle_duplicate_selected(self) -> None:
        rows = [self.row_objects.get(x) for x in self.duplicate_tree.selection()]
        rows = [x for x in rows if isinstance(x, tuple) and len(x) == 3]
        if not rows: messagebox.showinfo(APP_NAME, "Select duplicate copies to recycle."); return
        by_group = {}
        for gi, path, group in rows: by_group.setdefault(gi, []).append(path)
        for gi, paths in by_group.items():
            group = next(x[2] for x in rows if x[0] == gi)
            existing = [p for p in group.paths if os.path.exists(p)]
            if len(paths) >= len(existing):
                messagebox.showerror(APP_NAME, f"Group {gi}: SpaceMedic will not remove every copy. Leave at least one file unselected."); return
        if not messagebox.askyesno(APP_NAME, f"Move {len(rows)} verified duplicate copy/copies to Recycle Bin?\n\nReview paths carefully; identical content does not mean every location is unimportant.", icon="warning"): return
        success, failed = wt.recycle([x[1] for x in rows])
        record_history("duplicate_recycle", succeeded=success, failed=failed)
        for iid in list(self.duplicate_tree.selection()):
            obj = self.row_objects.get(iid)
            if isinstance(obj, tuple) and obj[1] in success: self.duplicate_tree.delete(iid)
        self.refresh_history()
        if failed: messagebox.showwarning(APP_NAME, f"Recycled {len(success)}; failed/skipped {len(failed)}.")

    def load_insights(self) -> None:
        self.progress.start(10); self.status_var.set("Inspecting system, Docker, WSL and virtual disks…")
        def work(): self.after(0, done, system_storage() + developer_platforms())
        def done(rows): self.progress.stop(); self._show_insights(rows); self.status_var.set(f"Loaded {len(rows)} system/developer storage insights.")
        threading.Thread(target=work, daemon=True).start()

    def load_startup(self) -> None:
        self.progress.start(10); self.status_var.set("Reading startup entries, automatic services and scheduled tasks…")
        def work(): self.after(0, done, startup_inventory())
        def done(rows): self.progress.stop(); self._show_insights(rows); self.status_var.set(f"Loaded {len(rows)} background entries (analysis only).")
        threading.Thread(target=work, daemon=True).start()

    def _show_insights(self, rows: list[Insight]) -> None:
        self._clear(self.insight_tree)
        for row in rows:
            value = format_bytes(int(row.value)) if row.value.isdigit() else row.value
            self.insight_tree.insert("", "end", iid=self._new_iid(), values=(row.category, row.name, value, row.detail))
        self._apply_search()

    def begin_install_monitor(self) -> None:
        if self.worker and self.worker.is_alive(): messagebox.showinfo(APP_NAME, "Another scan is running."); return
        if not messagebox.askyesno(APP_NAME, "Create a before-install snapshot?\n\nThis scans common app locations and report-only Registry data. It can take several minutes and may use tens of MB. Close unrelated apps first."): return
        self.cancel.clear(); self.progress.start(10); self.status_var.set("Creating before-install snapshot…")
        def work():
            try: path = take_snapshot("before", self.cancel, lambda p, n: self.after(0, self.status_var.set, f"Install snapshot: {n:,} files • {p[-80:]}")); self.after(0, done, str(path), None)
            except Exception as exc: self.after(0, done, "", str(exc))
        def done(path, error):
            self.progress.stop()
            if error: messagebox.showerror(APP_NAME, error); return
            self.monitor_before = path; record_history("install_monitor_begin", snapshot=path); self.refresh_history()
            self.status_var.set("Before snapshot saved. Install one application now, then click Finish & compare.")
        self.worker = threading.Thread(target=work, daemon=True); self.worker.start()

    def finish_install_monitor(self) -> None:
        if not self.monitor_before or not os.path.exists(self.monitor_before):
            messagebox.showinfo(APP_NAME, "Begin a snapshot first, then install one application."); return
        self.progress.start(10); self.status_var.set("Creating after snapshot…")
        def work():
            try:
                after = take_snapshot("after", self.cancel, lambda p, n: self.after(0, self.status_var.set, f"After snapshot: {n:,} files • {p[-80:]}"))
                report = compare_snapshots(self.monitor_before, str(after)); self.after(0, done, report, None)
            except Exception as exc: self.after(0, done, None, str(exc))
        def done(report, error):
            self.progress.stop()
            if error: messagebox.showerror(APP_NAME, error); return
            record_history("install_monitor_complete", report=report["report_path"], created=len(report["created"]), modified=len(report["modified"]), registry_added=len(report["registry_added_report_only"])); self.refresh_history()
            self.status_var.set(f"Install trace saved: {len(report['created'])} created, {len(report['modified'])} modified. Registry changes are report-only.")
            wt.reveal_path(report["report_path"])
        self.worker = threading.Thread(target=work, daemon=True); self.worker.start()

    def refresh_history(self) -> None:
        if not hasattr(self, "monitor_tree"): return
        self._clear(self.monitor_tree)
        for row in load_history(200):
            when = datetime.fromtimestamp(row.get("time", 0)).strftime("%Y-%m-%d %H:%M:%S")
            details = ", ".join(f"{k}={v}" for k, v in row.items() if k not in {"time", "action"})
            self.monitor_tree.insert("", "end", iid=self._new_iid(), values=(when, row.get("action", ""), details[:1500]))
        self._apply_search()

    def migrate_selected_cache(self) -> None:
        selected = self.cleanup_tree.selection()
        if len(selected) != 1: messagebox.showinfo(APP_NAME, "Select exactly one supported cache."); return
        item = self.row_objects.get(selected[0])
        if not isinstance(item, ScanItem) or not identify_cache(item.name):
            messagebox.showinfo(APP_NAME, "Supported relocation adapters: pip, npm, uv, Hugging Face and Ollama caches."); return
        destination = filedialog.askdirectory(title="Choose destination drive/folder")
        if not destination: return
        if not messagebox.askyesno(APP_NAME, f"Copy {item.name} to {destination}, configure its official cache location, and keep the source for rollback?\n\nThe old source will NOT be deleted automatically."): return
        self.cancel.clear(); self.progress.start(10); self.status_var.set(f"Copying {item.name} safely…")
        def work(): self.after(0, done, *migrate_cache(item.path, item.name, destination, self.cancel, lambda p: self.after(0, self.status_var.set, f"Copying… {p[-90:]}")))
        def done(ok, detail, target):
            self.progress.stop(); record_history("cache_migration", source=item.path, destination=target, success=ok, detail=detail); self.refresh_history()
            (messagebox.showinfo if ok else messagebox.showerror)(APP_NAME, detail)
        threading.Thread(target=work, daemon=True).start()

    def scan_caches(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_NAME, "Please let the current scan finish first.")
            return
        self.cancel.clear(); self.progress.start(10)
        self.status_var.set("Measuring temporary files, crash reports, browser/developer caches and Windows-managed junk…")
        def work():
            items = known_global_caches(self.cancel, lambda p, f, d: self.after(0, self.status_var.set, p))
            self.after(0, done, items)
        def done(items):
            self.cache_items = items; self.progress.stop(); self._populate_cleanup()
            reclaim = (self.result.reclaimable if self.result else 0) + sum(x.size for x in items)
            self.metric_vars[3].set(format_bytes(reclaim))
            direct = sum(x.size for x in items if x.reclaimable)
            system = sum(x.size for x in items if not x.reclaimable)
            self.status_var.set(f"Found {len(items)} junk/cache locations: {format_bytes(direct)} direct-review + {format_bytes(system)} Windows-managed.")
        self.worker = threading.Thread(target=work, daemon=True); self.worker.start()

    def load_apps(self) -> None:
        self.status_var.set("Reading installed-app metadata…")
        def work(): self.after(0, done, wt.installed_apps())
        def done(apps):
            self.installed_app_rows = apps
            self._clear(self.apps_tree)
            for app in apps:
                state = app.app_type + (" • protected" if app.protected else "")
                iid = self.apps_tree.insert("", "end", iid=self._new_iid(), values=(state, format_bytes(app.estimated_size) if app.estimated_size else "Unknown", app.name, app.version, app.publisher, app.install_location))
                self.row_objects[iid] = app
            self.status_var.set(f"Loaded {len(apps)} desktop and Store/MSIX app entries. Unknown sizes are normal for some installers.")
            self._apply_search()
        threading.Thread(target=work, daemon=True).start()

    def _selected_app(self) -> wt.InstalledApp | None:
        selected = self.apps_tree.selection()
        if len(selected) != 1:
            messagebox.showinfo(APP_NAME, "Select exactly one installed app.")
            return None
        app = self.row_objects.get(selected[0])
        return app if isinstance(app, wt.InstalledApp) else None

    def uninstall_selected_app(self) -> None:
        app = self._selected_app()
        if not app: return
        if app.protected:
            messagebox.showwarning(APP_NAME, "Windows/publisher marks this app as protected, or it has no registered uninstaller. SpaceMedic will not force-delete it.")
            return
        warning = (
            f"Safely uninstall “{app.name}”?\n\n"
            "SpaceMedic will first inventory only exact, high-confidence app paths. It will then run the app's registered publisher/Windows uninstaller interactively. "
            "After it finishes—and after any requested reboot—return and click Scan leftovers.\n\n"
            "Important: no generic tool can prove ownership of every registry key, driver, service, shared runtime, license, or user document. "
            "SpaceMedic deliberately leaves ambiguous/shared items alone rather than risk another app."
        )
        if not messagebox.askyesno("Safe uninstall", warning, icon="warning"): return
        self.status_var.set(f"Creating pre-uninstall inventory for {app.name}…")
        self.progress.start(10)
        def work():
            try:
                apps = self.installed_app_rows or wt.installed_apps()
                session = capture_inventory(app, apps)
                self.after(0, done, session, None)
            except Exception as exc:
                self.after(0, done, None, str(exc))
        def done(session, error):
            self.progress.stop()
            if error or not session:
                messagebox.showerror(APP_NAME, f"Could not create the safety inventory:\n{error}")
                return
            self.removal_session = session
            ok, detail = wt.launch_uninstall(app)
            if not ok:
                messagebox.showerror(APP_NAME, detail)
                return
            notes = "\n".join(f"• {x}" for x in session.warnings[:5])
            self.status_var.set(f"Uninstaller launched for {app.name}. Finish it, reboot if requested, then click Scan leftovers.")
            messagebox.showinfo("Uninstaller launched", f"Captured {len(session.inventory)} exact candidate path(s) before uninstall.\n\n{detail}\n\n{notes}".strip())
        threading.Thread(target=work, daemon=True).start()

    def scan_app_leftovers(self) -> None:
        session = self.removal_session or load_session()
        if not session:
            messagebox.showinfo(APP_NAME, "No uninstall session exists. Select an app and use Safe uninstall selected first.")
            return
        self.status_var.set("Refreshing installed apps and verifying pre-uninstall paths…")
        self.progress.start(10)
        def work():
            try:
                apps = wt.installed_apps()
                leftovers, warnings = scan_session_leftovers(session, apps)
                self.after(0, done, apps, leftovers, warnings, None)
            except Exception as exc:
                self.after(0, done, [], [], [], str(exc))
        def done(apps, leftovers, warnings, error):
            self.progress.stop()
            if error:
                messagebox.showerror(APP_NAME, error); return
            self.installed_app_rows = apps
            self.app_leftovers = leftovers
            self._populate_cleanup()
            self.tabs.select(self.cleanup_tab)
            total = sum(x.size for x in leftovers)
            base = (self.result.reclaimable if self.result else 0) + sum(x.size for x in self.cache_items)
            self.metric_vars[3].set(format_bytes(base + total))
            self.status_var.set(f"Verified {len(leftovers)} high-confidence leftover(s), {format_bytes(total)}. Review them in Junk & caches.")
            details = "\n".join(f"• {x}" for x in warnings[:8])
            if not leftovers:
                messagebox.showinfo("Leftover verification", "No removable high-confidence leftovers were found.\n\n" + (details or "The publisher uninstaller appears to have cleaned the captured paths."))
            elif warnings:
                messagebox.showwarning("Review required", f"Found {len(leftovers)} candidate(s). Nothing was deleted automatically.\n\n{details}")
        threading.Thread(target=work, daemon=True).start()

    def recycle_selected(self) -> None:
        selected = self.cleanup_tree.selection()
        chosen = [self.row_objects.get(i) for i in selected]
        blocked = [x for x in chosen if isinstance(x, ScanItem) and not x.reclaimable]
        items = [x for x in chosen if isinstance(x, ScanItem) and x.reclaimable and os.path.exists(x.path)]
        if not items:
            if blocked:
                messagebox.showinfo(APP_NAME, "Selected SYSTEM/protected items are analysis-only. Use Windows tools → Temporary files or Disk Cleanup so Windows removes them safely.")
            else:
                messagebox.showinfo(APP_NAME, "Select one or more cleanup candidates first.")
            return
        total = sum(x.size for x in items)
        review = [x for x in items if x.risk != "safe"]
        warning = f"Move {len(items)} approved item(s), about {format_bytes(total)}, to Recycle Bin?\n\n"
        if blocked:
            warning += f"{len(blocked)} SYSTEM/protected item(s) will be skipped; use Windows tools for those.\n\n"
        if review:
            warning += f"{len(review)} item(s) are REVIEW FIRST. They may need re-download/reinstall.\n\n"
        warning += "Source code and project manifests are not selected automatically. Very large items may not fit in Recycle Bin; Windows will warn you."
        if not messagebox.askyesno("Confirm cleanup", warning, icon="warning"):
            return
        verified = allowed_program_area_paths(self.removal_session) if self.removal_session else set()
        success, failed = wt.recycle([x.path for x in items], verified_exact=verified)
        if failed:
            messagebox.showerror(APP_NAME, "Windows could not recycle one or more items. They may be in use, protected, or too long. Nothing is force-deleted by SpaceMedic.")
        else:
            messagebox.showinfo(APP_NAME, f"Moved {len(success)} item(s) to Recycle Bin. Empty the bin only after checking your projects.")
        record_history("recycle_cleanup", succeeded=success, failed=failed, requested_bytes=total)
        self.refresh_history()
        self.app_leftovers = [x for x in self.app_leftovers if x.path not in success]
        self.cache_items = [x for x in self.cache_items if x.path not in success]
        for iid, obj in list(self.row_objects.items()):
            if isinstance(obj, ScanItem) and obj.path in success:
                try: self.cleanup_tree.delete(iid)
                except tk.TclError: pass

    def _open_selected(self, tree: ttk.Treeview) -> None:
        sel = tree.selection()
        if not sel: return
        obj = self.row_objects.get(sel[0])
        path = getattr(obj, "path", None) or getattr(obj, "root", None) or getattr(obj, "install_location", None)
        if path and os.path.exists(path): wt.reveal_path(path)

    def _context_menu(self, event, tree: ttk.Treeview) -> None:
        row = tree.identify_row(event.y)
        if row: tree.selection_set(row)
        menu = tk.Menu(self, tearoff=False, bg=PANEL2, fg=TEXT)
        menu.add_command(label="Show in File Explorer", command=lambda: self._open_selected(tree))
        menu.tk_popup(event.x_root, event.y_root)

    def export_diagnostics(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("ZIP diagnostic bundle", "*.zip")], initialfile=f"SpaceMedic-diagnostics-{datetime.now():%Y%m%d-%H%M}.zip")
        if not path: return
        try:
            create_diagnostic_bundle(path)
            messagebox.showinfo(APP_NAME, "Privacy-redacted diagnostic bundle created.\n\nPlease open the ZIP and review diagnostics.json before sharing it.")
        except Exception as exc: messagebox.showerror(APP_NAME, str(exc))

    def export_report(self) -> None:
        if not self.result:
            messagebox.showinfo(APP_NAME, "Run an analysis first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON report", "*.json"), ("CSV cleanup list", "*.csv")], initialfile=f"SpaceMedic-{datetime.now():%Y%m%d-%H%M}.json")
        if not path: return
        if path.lower().endswith(".csv"):
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f); writer.writerow(["safety", "size_bytes", "category", "reason", "path"])
                for x in self.result.cleanup + self.cache_items + self.app_leftovers: writer.writerow([x.risk, x.size, x.category, x.reason, x.path])
        else:
            data = self.result.to_dict(); data["known_caches"] = [x.to_dict() for x in self.cache_items]
            data["verified_app_leftovers"] = [x.to_dict() for x in self.app_leftovers]
            with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2, ensure_ascii=False)
        messagebox.showinfo(APP_NAME, f"Report saved:\n{path}")

    def _confirm_component_cleanup(self):
        if messagebox.askyesno(APP_NAME, "Run Microsoft DISM standard component cleanup?\n\nThis removes superseded Windows components. SpaceMedic intentionally does NOT use /ResetBase, so the aggressive rollback-blocking mode is avoided."):
            wt.cleanup_component_store()

    def _confirm_delivery_cleanup(self):
        if messagebox.askyesno(APP_NAME, "Clear Windows Delivery Optimization cache?\n\nThis removes cached Windows/Store update payloads, not installed updates. Windows can download them again if required."):
            wt.cleanup_delivery_optimization()

    def _confirm_sfc(self):
        if messagebox.askyesno(APP_NAME, "Run SFC /scannow as Administrator?\n\nThis checks and repairs protected Windows files. It can take some time and is included for health checking, not for freeing disk space."):
            wt.run_system_file_check()

    def _confirm_hibernate(self):
        if messagebox.askyesno(APP_NAME, "Disable hibernation?\n\nThis can free several GB but also disables Hibernate and Windows Fast Startup. You can reverse it later with: powercfg /hibernate on", icon="warning"):
            wt.disable_hibernation()

    def _on_windows_low_memory(self) -> None:
        """Validate the OS event against current telemetry and show a non-modal in-app banner."""
        try:
            snapshot = memory_snapshot()
        except Exception as exc:
            record_history("windows_low_memory_signal_unverified", error=str(exc))
            return
        commit_ratio = snapshot.commit_total / snapshot.commit_limit if snapshot.commit_limit else 0.0
        if not confirmed_low_memory(snapshot):
            record_history("windows_low_memory_signal_ignored", available=snapshot.available_physical,
                           total=snapshot.total_physical, commit_ratio=commit_ratio)
            self.status_var.set("A transient Windows memory signal was ignored after current telemetry showed adequate headroom.")
            return
        now = time.time()
        if now - self._last_low_memory_alert < 15 * 60:
            return
        self._last_low_memory_alert = now
        record_history("windows_low_memory_signal_confirmed", available=snapshot.available_physical,
                       total=snapshot.total_physical, commit_ratio=commit_ratio)
        self.status_var.set("Confirmed low-memory pressure. Review Memory Center and save active work.")
        def review():
            self._dismiss_alert(); self._select_nav(8); self.refresh_memory_center()
        self._show_inline_alert(
            "Low-memory pressure detected",
            f"Available physical memory is {format_bytes(snapshot.available_physical)} and commit is {commit_ratio*100:.0f}% of its limit. Save work, review the largest normal applications, and close only an app you no longer need. SpaceMedic will not flush caches or trim every process automatically.",
            level="warning", action_text="Open Memory Center", action=review
        )

    def _on_close(self) -> None:
        if self._memory_timer:
            try: self.after_cancel(self._memory_timer)
            except Exception: pass
        self.memory_intelligence.close()
        self.destroy()

    def _elevate(self):
        if wt.relaunch_as_admin(): self.after(500, self._on_close)

    @staticmethod
    def _project_rebuild(project) -> str:
        root = project.root
        eco = project.ecosystem
        if eco == "Node.js":
            if os.path.exists(os.path.join(root, "pnpm-lock.yaml")): return "pnpm install --frozen-lockfile"
            if os.path.exists(os.path.join(root, "yarn.lock")): return "yarn install --frozen-lockfile"
            if os.path.exists(os.path.join(root, "package-lock.json")): return "npm ci"
            return "npm install (no lockfile)"
        if eco == "Python":
            if os.path.exists(os.path.join(root, "poetry.lock")): return "poetry install"
            if os.path.exists(os.path.join(root, "uv.lock")): return "uv sync"
            return "python -m pip install -r requirements.txt"
        return {"Rust": "cargo build", "Go": "go mod download", "Java/Maven": "mvn package", "Java/Gradle": "gradlew build", ".NET": "dotnet restore", "PHP": "composer install", "Ruby": "bundle install"}.get(eco, "Review project manifest")

    def _new_iid(self) -> str:
        self._row_seq += 1
        return f"row-{self._row_seq}"

    def _clear(self, tree):
        items = list(tree.get_children()) + list(self.detached_rows.get(tree, []))
        for item in dict.fromkeys(items):
            if tree.exists(item): tree.delete(item)
        self.detached_rows[tree] = []

    @staticmethod
    def _date(timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M") if timestamp else "—"


def main() -> None:
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # per-monitor v2
        except Exception:
            try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception: pass
    app = SpaceMedicApp()
    app.mainloop()
