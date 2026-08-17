# Changelog

## 3.6.0 — Orbital HUD theme

- Added original sci-fi HUD palette, angular top frame, concentric mark, segmented telemetry and clipped chrome.
- Added HUD metric modules and page telemetry dividers across the full feature workspace.
- Preserved professional information architecture, scrolling and data density.
- Added Orbital HUD / Professional Dark selector and settings migration.
- No supplied image asset or watermark is redistributed.
- Added theme-migration regression coverage; 30 tests total.

## 3.5.0 — Integrated alerts and false-warning fix

- Replaced modal low-memory popup with a non-blocking in-app alert banner.
- Added live physical/commit validation before displaying the Windows event.
- Added transient-signal ignore logging, 15-minute cooldown, signal de-duplication and native wait-failure handling.
- Added regression coverage; 29 tests total.

## 3.4.0 — Guided Smart Optimize

- Added one primary Smart optimize button with assessment, explicit review, safe execution, verification and history.
- Added optional user-selected graceful app closures with foreground/system/protected/background-service exclusion and no force kill.
- Added Startup Apps and Power mode entry points without silently changing Windows configuration.
- Added real available-memory and commit before/after reporting.
- Explicitly prohibited cache flushing, blanket trimming, service disabling and High/Realtime priority manipulation.
- Added developer attribution for M.Abdullah Amjid.

## 3.3.0 — Explainable Memory Intelligence

- Replaced PowerShell process polling with native Toolhelp/PSAPI/User32 snapshots.
- Added private commit, page faults, handles, GDI/USER objects, threads, CPU time, start identity and foreground/window state.
- Added event-driven Windows low-memory notification without automatic destructive action.
- Added bounded SQLite telemetry (7-day system, 48-hour selected process retention) and sustained private-memory/handle/GDI trend findings.
- Added explainable confidence, rate, duration, workload penalty and confirmation guidance.
- Added foreground protection and critical-pressure plans that require explicit user action.
- Added detailed review of accepted/rejected research claims.
- Expanded tests from 25 to 28.

## 3.2.0 — Professional Workspace and scrollable navigation

- Replaced decorative HUD chrome with a restrained Fluent-inspired application bar.
- Added a fully scrollable categorized navigation pane with scrollbar, mouse wheel, synchronized width/scroll region and Settings pinned at the bottom.
- Added persistent page title and purpose description to every destination.
- Reworked color, typography, border and spacing tokens for clearer enterprise-level hierarchy.
- Reduced decorative visual noise and preserved maximum width for data-heavy tables.
- Added horizontal table scrolling and per-monitor-v2 DPI awareness fallback.
- Kept all storage, uninstall, memory, search and safety behavior unchanged.
- Reviewed Microsoft Windows/Fluent navigation and settings guidance plus IBM Carbon data-table/dashboard guidance.

## 3.1.0 — Command Deck UI and honest Memory Center

- Replaced top tab strip with an original futuristic command-deck header and left navigation rail.
- Added angular telemetry lines, cyan/green accents, stronger storage cards and hidden content deck without copying supplied artwork.
- Added Windows physical/available/commit memory telemetry and pressure classification.
- Added process working set, private bytes, CPU and window/protection inventory.
- Added safe self-only memory relief, graceful app-close requests and an advanced warned idle-app working-set trim.
- Added Task Manager, Resource Monitor, Windows Memory Diagnostic and Performance Options shortcuts.
- Explicitly rejected fake standby-list flushing and permanent speed claims.
- Added memory policy tests; 25 tests total.

## 3.0.0 — Public Edition foundation

- Refactored product direction for general Windows 10/11 x64 users rather than a single-PC workflow.
- Added persistent per-user settings, last path, worker configuration and offline defaults.
- Added first-run privacy/safety onboarding.
- Added core UI translation catalogues for English, Urdu, Spanish, French, German, Arabic, Hindi and Simplified Chinese.
- Added Settings tab and restart-to-apply language selection.
- Added local community cleanup-rule engine with schema validation, relative-root restriction, traversal prevention and SYSTEM-action enforcement.
- Added bundled GPU, Slack, JetBrains and Steam cache rules.
- Added PRIVACY, SECURITY, CONTRIBUTING, SUPPORT and CODE_OF_CONDUCT documents plus structured issue templates.
- Expanded tests from 20 to 23.

## 2.3.0 — Dependency-free fast scan

- Fixed Fast NTFS doing nothing when WizTree was absent.
- Added built-in concurrent top-level branch scanner with exact merged totals and cancellation.
- Fast scan automatically chooses optional elevated MFT provider when available, otherwise the native parallel backend.
- Removed the missing-dependency popup and renamed the button to Fast scan.
- Added standard-versus-parallel scanner regression test; 20 tests total.

## 2.2.0 — Global search and Docker residual fix

- Added one live search field across all loaded feature tables with safe detach/restore behavior.
- Added Docker's official Windows residual paths as an exact vendor profile.
- Fixed old/empty Docker uninstall sessions reporting “no leftovers” while `%LOCALAPPDATA%\\Docker` remained.
- Added Docker WSL-registration check; VHDX/folder recycling is blocked while Docker WSL distributions remain registered.
- Added destructive-data warnings for containers, images, volumes and credentials.
- Added regression test; 19 tests total.

## 2.1.0 — Performance and visualization

- Added optional user-installed WizTree MFT/CSV backend with provider detection, schema validation, cancellation, temporary-export cleanup and built-in-scanner fallback. Nothing is downloaded or redistributed.
- Added compressed scan snapshots, five-snapshot retention and change tracking.
- Added Changes tab for total deltas, new large entries, growth and removals from retained top results.
- Upgraded treemap with folder zoom, Back navigation, double-click reveal and extension mode.
- Added privacy-redacted diagnostic ZIP for real Windows testing.
- Expanded automated tests from 15 to 18.

## 2.0.0 — Storage intelligence suite

- Added clickable treemap visualization.
- Added exact duplicate finder with size/sample/full SHA-256 stages and hard-link protection.
- Added persistent action history and cleanup audit records.
- Added before/after Installation Monitor with compressed filesystem snapshots, report-only Registry diffs and conservative caps.
- Added system storage, Docker, WSL, virtual-disk, startup, service and scheduled-task analysis.
- Added safe cache relocation adapters for pip, npm, uv, Hugging Face and Ollama; source is retained for rollback.
- Added restore-point/shadow-storage and Reserved Storage inspection.
- Added optional certificate signing and Inno Setup installer to GitHub Actions; portable ZIP remains available.
- Expanded tests from 10 to 15.
- Documented that the native raw-NTFS MFT backend and full Urdu localization remain separate audited work rather than unsafe placeholder claims.

## 1.2.0 — Safe App Removal

- Unified registered desktop and current-user Store/MSIX app inventory.
- Added pre-uninstall, exact-path inventory saved across restarts.
- Launches the registered publisher uninstaller or Windows MSIX removal—no undocumented silent switches.
- Post-uninstall identity verification prevents cleanup while the same product is still registered.
- Leftover candidates must have existed before uninstall and survive afterward.
- Exact app/folder matching only; fuzzy substring deletion is forbidden.
- Checks every candidate against remaining apps' registered install locations to avoid shared-path deletion.
- Captures exact AppData, LocalLow, ProgramData, program-location, MSIX package-family data, and exact shortcuts.
- Added deep-integration guard for drivers, security/VPN tools, runtimes/frameworks, databases, firmware, and virtualization.
- Broad vendor folders, Common Files, WindowsApps, Windows Installer cache, Documents, services, drivers, and Registry entries are never heuristically removed.
- Verified leftovers go to Recycle Bin, including exact former app paths under Program Files/ProgramData through a narrowly scoped safety exception.
- Added five app-removal safety tests (10 total).

## 1.1.0 — Junk, crash, and Windows-update intelligence

- Added Windows Error Reporting archive/queue detection for per-user and system locations.
- Added application crash dumps, system minidumps, `MEMORY.DMP`, Windows Temp, `Windows.old`, and `$WINDOWS.~BT` analysis.
- Added multi-profile Edge, Chrome, and Firefox caches.
- Added Discord, DirectX, NVIDIA, and Windows internet caches.
- Added **SYSTEM** safety class. These findings are measured but cannot be directly recycled; users are routed to Windows Storage or Disk Cleanup.
- Added Reliability Monitor and Windows Update History shortcuts so diagnostic/rollback data can be reviewed first.
- Added supported Delivery Optimization cache cleanup.
- Expanded old-update workflow with DISM analysis and standard component cleanup. `/ResetBase` remains intentionally excluded.
- Added SFC system-file health check.
- Hardened cleanup boundary against Windows, Program Files, ProgramData, drive roots, Recycle Bin, and System Volume Information.
- Added wildcard cache scanner and five automated tests.

## 1.0.0

- Initial disk analyzer, project detection, developer caches, installed-app inventory, Recycle-Bin cleanup, reports, CLI, and Windows build workflow.
