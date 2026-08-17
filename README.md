# SpaceMedic

**Version 3.6 Public Edition — Windows storage, performance, and explainable memory intelligence.**

**Developer:** M.Abdullah Amjid

SpaceMedic answers two different questions in one offline app:

1. *What is using my disk?* — largest folders/files, installed-app metadata, extension breakdown.
2. *What can I safely reclaim?* — project dependencies/build outputs, package caches, temporary files, and supported Windows maintenance tools.

It is designed for developers who collect GitHub projects, `node_modules`, Python virtual environments, build outputs, package caches, AI models, and IDE caches.

> SpaceMedic is read-only until the user explicitly selects cleanup candidates. File cleanup uses the Windows Recycle Bin. It never acts as a registry cleaner and never manually deletes `Windows`, `System32`, `WinSxS`, `Program Files`, `pagefile.sys`, or other protected system data.

## Public Edition principles

SpaceMedic 3.0 is designed for general Windows users, developers, support technicians, gamers, creators, students, and small organizations—not for one computer or one username.

- Free and open source under the MIT license.
- Windows 10 and Windows 11 x64 target.
- Fully offline by default, with no telemetry, ads, account, cloud dependency, or automatic upload.
- Portable source launcher, portable EXE build, and installer build.
- Per-user settings stored under `%LOCALAPPDATA%\\SpaceMedic`; no hard-coded username or personal path.
- First-run safety/privacy onboarding.
- Core interface localization framework for English, Urdu, Spanish, French, German, Arabic, Hindi, and Simplified Chinese. Detailed technical findings remain English until native-speaker review expands each catalogue.
- Public Settings tab for language, parallel worker count, privacy status, and community cleanup rules.
- Validated, local-only community cleanup-rule system. Rules cannot use absolute paths or parent traversal; SYSTEM rules cannot become directly cleanable.
- Public governance documents: Privacy, Security, Contributing, Support, Code of Conduct, and structured issue templates.

## Current features

### SpaceMedic 3.6 Orbital HUD theme

- Added a complete original **Orbital HUD** visual theme inspired by the general language of science-fiction control interfaces, without embedding or copying the supplied UI-kit image.
- Added a custom angular top frame, concentric SpaceMedic mark, segmented telemetry lines, build/access indicators, clipped lower edge and click-to-elevate region.
- Added HUD metric modules with technical labels, segmented status strips, cyan/green semantic channels and high-contrast values.
- Added page telemetry dividers, status nodes, dark navy layered surfaces, silver-blue borders and coordinated warning/success colors across every existing feature.
- Preserved the professional scrollable navigation, full-width tables, horizontal/vertical scrolling, page hierarchy, inline alerts, Memory Center, Smart Optimize and all storage/application tools.
- Added a Settings theme selector: **Orbital HUD** or **Professional Dark**. Existing pre-3.6 `dark` settings migrate to Orbital HUD; theme changes apply after restart.
- All visual elements are drawn locally with Tk canvas primitives; no copyrighted reference artwork, watermark, texture or external image is included.

### SpaceMedic 3.5 In-app alerts and low-memory validation

- Replaced the intrusive native low-memory popup with a professional non-modal notification banner inside the main application layout.
- The banner includes a semantic icon, concise title, current measured values, Dismiss and Open Memory Center actions and does not block the rest of SpaceMedic.
- Added two-stage validation: a Windows low-memory event must also be supported by current telemetry—available physical memory below `max(512 MB, 3% of installed RAM)` or commit at/above 95%.
- Transient/stale signals are logged and ignored instead of alarming the user.
- Added a 15-minute alert cooldown and event-state de-duplication.
- Added `WAIT_FAILED` handling for the native notification watcher.
- Added a regression test for healthy, low-physical and commit-exhaustion cases; 29 tests total.

### SpaceMedic 3.4 Smart Optimize

- Added one prominent **Smart optimize** button in Memory Center.
- The button performs a complete safe workflow: assess physical/commit pressure, load sustained findings, exclude foreground/system/protected/background-service processes, show a review plan, release SpaceMedic's own unused memory, optionally request graceful closure of user-selected normal applications, wait, remeasure, verify, and record every result.
- No application is preselected for closing. Users must save work and explicitly choose normal windowed applications; force termination is never used.
- Added direct links to Startup Apps and Power mode. Microsoft recommends reducing startup/background apps and optionally selecting Best performance when power, heat and battery life are acceptable.
- Smart Optimize never flushes standby cache, empties all working sets, disables Windows services, changes arbitrary CPU priorities, modifies pagefile/Registry settings, or claims to physically increase processor speed.
- Results report available-memory and system-commit before/after values, closures, failures and uncertainty.
- Added developer attribution: **M.Abdullah Amjid** in Settings, package metadata, README and optimization history.

Processor performance cannot be increased by a RAM-cleaner button. Responsiveness can improve when the user closes an unnecessary CPU/memory-heavy application, reduces startup/background activity, chooses an appropriate Windows power mode, and resolves real storage/memory pressure. Microsoft warns that High/Realtime priorities can starve Windows, prevent cache flushing, or make input unresponsive, so SpaceMedic does not apply them.

Official basis: Microsoft [Tips to improve PC performance in Windows](https://support.microsoft.com/en-us/windows/tips-to-improve-pc-performance-in-windows-b3b3ef5b-5953-fb6a-2528-4bbed82fba96), [`SetPriorityClass`](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-setpriorityclass), and Windows [Quality of Service](https://learn.microsoft.com/en-us/windows/win32/procthread/quality-of-service).

### SpaceMedic 3.3 Explainable Memory Intelligence

- Replaced PowerShell process polling with a low-overhead native Toolhelp/PSAPI/User32 process snapshot: working set, private commit, cumulative page faults, handles, GDI/USER objects, threads, CPU time, start identity, visible window and responsiveness.
- Added event-driven Windows low-memory notification using `CreateMemoryResourceNotification` and `WaitForSingleObject`; the event opens Memory Center and asks for explicit user action without automatic cache flushing.
- Added bounded SQLite telemetry with WAL mode and automatic retention: seven days for compact system samples and 48 hours for selected/top process samples to prevent an unbounded monitoring database.
- Added sustained process-resource trend detection for private bytes, handles and GDI objects using explainable linear regression, R², monotonicity, minimum observation time/growth/rate and a workload activity penalty.
- Findings show confidence, rate and duration and are explicitly labeled as evidence requiring confirmation—not proof.
- Added real memory-pressure plans based on available physical memory and commit ratio. Plans never automatically trim foreground/system processes.
- Added foreground-process protection to the manual advanced trim.
- Added detailed “Explain finding” workflow and direct guidance to PerfMon, Process Explorer, VMMap, WPR/WPA, DebugDiag and vendor support.
- Added `MEMORY_RESEARCH_REVIEW.md`, documenting which submitted ideas are valid and which were rejected as unsafe, unsupported or misleading.
- 28 automated tests.

SpaceMedic intentionally does not claim to be the world's best until independent benchmarks prove no regressions across representative hardware and workloads. It targets the safest, lowest-overhead and most transparent consumer memory workflow.

Official implementation references:

- Microsoft [`CreateMemoryResourceNotification`](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-creatememoryresourcenotification) and [`QueryMemoryResourceNotification`](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-querymemoryresourcenotification).
- Microsoft [`PROCESS_MEMORY_COUNTERS_EX`](https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters_ex) and [`GetProcessMemoryInfo`](https://learn.microsoft.com/en-us/windows/win32/api/psapi/nf-psapi-getprocessmemoryinfo).
- Microsoft [`GetGuiResources`](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getguiresources) for per-process GDI/USER object counts.
- Microsoft [Performance Monitor guidance for finding user-mode memory leaks](https://learn.microsoft.com/en-us/windows-hardware/drivers/debugger/using-performance-monitor-to-find-a-user-mode-memory-leak), which emphasizes sustained Private Bytes/Virtual Bytes observation over time.

### SpaceMedic 3.2 Professional Workspace

- Replaced the decorative sci-fi header with a restrained Windows-style application bar, compact brand mark, clear product identity, access badge and conventional administrator action.
- Replaced the crowded command deck with a **fully scrollable 224 px navigation pane**. The pane has categorized destinations, a real scrollbar, mouse-wheel support over labels and buttons, synchronized scroll-region/width handling, persistent offline status, and Settings pinned at the bottom in line with Windows guidance.
- Added page titles and concise descriptions above every workspace, so users always know where they are and what the page is for.
- Introduced a restrained semantic token palette, consistent 4/8/12/16/24 px spacing rhythm, Segoe UI hierarchy, neutral surfaces, subtle borders, one primary action color, separate warning/danger colors and less decorative noise.
- Kept dense data tables in the main content region with maximum available width, consistent 30 px rows, and both vertical and horizontal scrollbars instead of shrinking them inside decorative panels.
- Added per-monitor-v2 DPI awareness with compatibility fallback for crisp rendering on scaled Windows displays.
- Navigation is grouped into Overview, Cleanup & analysis, System, and Tools to reduce cognitive load; Settings is separated from task navigation.
- The content deck remains keyboard-focusable and global search remains available across all loaded tables.

Design research:

- Microsoft Windows [design guidelines](https://learn.microsoft.com/en-us/windows/apps/design/guidelines-overview) emphasize consistent layout, navigation, typography, color, materials and hierarchy.
- Microsoft [Navigation basics](https://learn.microsoft.com/en-us/windows/apps/design/basics/navigation-basics) recommends simple, familiar navigation and warns against overwhelming users with too many peers.
- Fluent 2 [Nav guidance](https://fluent2.microsoft.design/components/web/react/core/nav/usage) describes a roughly 260 px inline drawer, brief labels, grouping and reflow/overflow behavior.
- Microsoft [app settings guidance](https://learn.microsoft.com/en-us/windows/apps/design/app-settings/guidelines-for-app-settings) recommends placing Settings as the final/pinned navigation item.
- IBM Carbon [data table guidance](https://carbondesignsystem.com/components/data-table/usage/) recommends giving dense tables the main content width and using consistent header/row sizing.
- Carbon dashboard guidance emphasizes hierarchy, restrained color, whitespace and consistent spacing rather than making every element visually dominant.

### SpaceMedic 3.1 Command Deck and Memory Center

- Replaced the conventional tab-strip layout with an original **SpaceMedic Command Deck**: angular telemetry header, cyan/green storage waveform accents, left navigation rail, hidden content deck, stronger metric cards and responsive status controls. The supplied reference image was used only as broad futuristic inspiration; no artwork, watermark, geometry, logo, or layout was copied.
- Added **Memory Center** using Microsoft Windows APIs: `GlobalMemoryStatusEx`, `GetPerformanceInfo`, process working/private memory telemetry and pressure classification.
- Added live physical load, available memory, system commit and top-process views.
- Added **Safe memory relief**, which runs Python garbage collection and trims only SpaceMedic's own working set. It never flushes system standby memory or manipulates unrelated apps.
- Added graceful close for a selected normal windowed app, with protected process names and no forced termination.
- Added an explicitly advanced, warned working-set trim for a selected non-protected idle app. Microsoft describes `EmptyWorkingSet` primarily as a testing/tuning operation; it may cause later page faults and is not represented as a permanent speed boost.
- Added Task Manager, Resource Monitor, Windows Memory Diagnostic and Performance Options launchers.
- Added memory operations to local history.
- 25 automated tests.

#### What “memory boost” honestly means

SpaceMedic does not chase a cosmetically low RAM percentage. Windows deliberately uses otherwise-idle RAM for cache, and available memory already includes reusable standby pages. Repeatedly emptying working sets or standby memory can force disk reads/page faults and make applications slower. The useful workflow is: measure real pressure, identify a growing process, save work and close an unnecessary app, reduce startup load, keep a suitable pagefile, diagnose leaks/hardware, and add RAM when the workload genuinely exceeds capacity.

Official research basis:

- Microsoft Learn: [Memory performance information](https://learn.microsoft.com/en-us/windows/win32/memory/memory-performance-information) and [`GlobalMemoryStatusEx`](https://learn.microsoft.com/en-us/windows/win32/api/sysinfoapi/nf-sysinfoapi-globalmemorystatusex) for physical/available/commit telemetry.
- Microsoft Learn: [Working Set](https://learn.microsoft.com/en-us/windows/win32/memory/working-set) and [`EmptyWorkingSet`](https://learn.microsoft.com/en-us/windows/win32/psapi/working-set-information), which describes trimming as primarily useful for testing and tuning.
- Microsoft Learn warns in [`SetProcessWorkingSetSize`](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-setprocessworkingsetsize) that working-set changes must consider whole-system performance and can degrade other applications.
- Microsoft Windows Performance documentation notes that emptying working sets can significantly affect performance because processes must fault pages back in.

### SpaceMedic 3.0 public-platform additions

- Persistent public settings and last scan location.
- Eight-language core navigation catalogue with restart-to-apply selection.
- Offline/no-telemetry policy enforced in defaults and documented in `PRIVACY.md`.
- First-run safety onboarding for every new Windows profile.
- Extensible bundled/user cleanup rules with schema and path-safety validation.
- Added Chrome/Edge GPU, Slack, JetBrains and Steam web-cache community rules.
- 23 automated tests.

### SpaceMedic 2.3 dependency-free fast scanning

- **Fast scan now always works without WizTree.** When an optional administrator-access MFT provider is unavailable, SpaceMedic automatically uses its built-in parallel scanner instead of showing a dependency error.
- The parallel backend scans independent top-level branches concurrently, merges exact size/file/folder counts, project findings, cleanup candidates, categories and extension statistics, and supports cancellation.
- If a separately installed WizTree CLI is detected and SpaceMedic is elevated, the optional validated MFT path is still used. Otherwise there is no popup, download or extra installation requirement.
- Button renamed from **Fast NTFS** to **Fast scan** so its behavior is accurate.
- 20 automated tests.

### SpaceMedic 2.2 search and vendor-leftover fixes

- Global live search filters every loaded table: largest items, changes, projects, duplicates, junk/caches, installed apps, system/startup and install-monitor history.
- Search safely detaches non-matching rows rather than deleting scan data; Clear restores all rows.
- Docker Desktop now has a vendor-documented residual profile based on Docker's official Windows uninstall documentation. It detects `ProgramData\\Docker`, `ProgramData\\DockerDesktop`, `Program Files\\Docker`, Local/Roaming AppData Docker folders and the user's `.docker` folder even when an older uninstall session captured no heuristic leftovers.
- Docker residuals are explicitly marked destructive because they may contain containers, images, volumes, credentials and the large WSL VHDX.
- If `docker-desktop`/`docker-desktop-data` is still registered in WSL, raw folder/VHDX deletion is blocked and the result is shown as **SYSTEM** with an unregister/backup warning.
- 19 automated tests.

### SpaceMedic 2.1 performance additions

- Optional fast NTFS/MFT provider through a separately installed WizTree CLI. SpaceMedic does not download or redistribute it; licensing remains between the user and WizTree. CSV schema and output are validated, with safe fallback to the built-in scanner.
- Persistent compressed scan cache retaining the latest five snapshots per location.
- **Changes** view for total-size deltas, newly large items, growth and items no longer present in retained top results.
- Zoomable folder treemap with breadcrumb/back navigation, double-click reveal, and a file-extension visualization mode.
- Privacy-redacted Windows testing bundle containing version/platform/performance history but no file contents, source code, app inventory, browser history, registry dump or credentials.
- 18 automated tests.

### SpaceMedic 2.0 additions

- Interactive, clickable treemap for non-overlapping top-level scan results.
- Three-stage duplicate detection: size → sampled SHA-256 → complete SHA-256; NTFS hard links are excluded from reclaim totals and deleting every copy is blocked.
- Emergency storage workflow through the existing junk/system classifications and Microsoft cleanup actions.
- Install Monitor with compressed before/after file snapshots and report-only Registry differences. Snapshot results are never treated as automatic proof of ownership.
- Persistent cleanup, migration, uninstall-monitor and duplicate-scan history.
- System storage dashboard for hibernation, pagefile, swapfile, crash dumps and low-space state.
- Docker, WSL and large VHD/VHDX/VMDK/QCOW2 visibility; destructive VM cleanup remains in the owning platform.
- Analysis-only startup, automatic-service and scheduled-task inventory.
- Safe cache relocation adapters for pip, npm, uv, Hugging Face and Ollama: copy → configure → retain source → user verifies → optional recycle.
- Restore-point/shadow-storage and Reserved Storage inspection through Windows tools.
- Signed-build-ready GitHub workflow, portable ZIP and Inno Setup installer. Signing activates only when repository certificate secrets are configured.
- 15 automated safety and integrity tests.

### Existing analysis and cleanup

- Background scan of any drive or folder; does not follow symlinks/reparse points.
- Largest folders and files, sortable tables, paths, modified dates, type breakdown in exported JSON.
- Project auto-detection for Node.js, Python, Rust, Go, Maven, Gradle, .NET, PHP, and Ruby.
- Per-project totals for dependencies, Git history, and build/cache output.
- Recognizes `node_modules`, `.venv`, `venv`, `.next`, `.nuxt`, `.svelte-kit`, `target`, `dist`, `build`, `bin`, `obj`, `.vs`, `.gradle`, test/linter caches, and more.
- Measures known caches for npm, pip, uv, Cargo, Gradle, Maven, NuGet, Playwright, Puppeteer, VS Code, Hugging Face, PyTorch, Whisper, and Ollama.
- Safety labels: **SAFE** or **REVIEW** with a plain-language reason.
- Cleanup sends selected items to Recycle Bin; large-item warning remains enabled.
- Unified installed-app inventory: registered 32-bit/64-bit desktop apps, per-user desktop apps, and current-user Store/MSIX packages.
- **Safe App Removal** workflow: pre-uninstall inventory → registered publisher/Windows uninstaller → reboot if requested → identity re-check → high-confidence leftover review.
- Shared-path collision check against all other installed apps before and after uninstall.
- Exact MSIX package-family data detection and exact app/publisher folder matching in AppData, ProgramData, and program locations.
- High-risk guard for drivers, VPN/security tools, runtimes, frameworks, databases, virtualization, firmware, and similar deep integrations; these require the publisher's cleanup tool.
- No generic Registry cleaner. Ambiguous registry keys, shared components, services, drivers, user Documents, broad vendor directories, and non-exact name matches are deliberately left alone.
- Buttons for Windows Storage settings, Disk Cleanup, DISM component-store analysis/standard cleanup, and optional hibernation disable.
- JSON and CSV reports.
- CLI mode for machines too constrained for a full GUI workflow.
- Zero third-party runtime dependencies; network is not required.

## Quick start (Roman Urdu)

### Aap ke PC par abhi sirf 3 GB free hai

Pehle emergency buffer banayein:

1. **Settings → System → Storage → Cleanup recommendations** khol kar Temporary files review karein.
2. Recycle Bin empty karein *sirf agar us mein zaroori files nahin*.
3. SpaceMedic mein pehle `C:\Users\AapKaName` scan karein. Full `C:\` scan baad mein Administrator mode mein karein.
4. **Cleanup candidates** mein `node_modules`, `.venv`, `.next`, build outputs aur caches ko size ke hisaab se dekhein.
5. Purane/inactive project ke regenerable folders select karke **Recycle selected** karein. Project source, `package.json`, lockfiles, `requirements.txt`, `pyproject.toml`, aur GitHub code delete na karein.
6. `Program Files`, `Windows`, ya `Users` folder ko manually delete na karein. Apps ko **Installed apps** se uninstall karein.
7. C: par kam az kam 15–20 GB working room banana practical target hai, especially Windows updates ke liye; exact requirement update aur machine par depend karti hai.

### Run from source

Requirements: Windows 10/11 and Python 3.10+ (your Python 3.14 installation is suitable).

```bat
git clone YOUR_REPOSITORY_URL
cd SpaceMedic
SpaceMedic.bat
```

Or:

```bat
py -3 -m spacemedic
```

CLI:

```bat
py -3 -m spacemedic.cli scan C:\Users\YourName --top 30 --json report.json
py -3 -m spacemedic.cli caches
```

### Build a portable EXE locally

```bat
py -3 -m pip install pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name SpaceMedic --add-data "spacemedic/cleanup_rules.json;spacemedic" run_spacemedic.pyw
```

The EXE appears at `dist\SpaceMedic.exe`. The included GitHub Actions workflow builds and uploads a Windows x64 ZIP automatically for tags such as `v1.0.0`.

## Safe App Removal (v1.2)

1. Open **Installed apps** and click **Refresh all apps**.
2. Select exactly one app and choose **Safe uninstall selected**.
3. SpaceMedic inventories exact, high-confidence paths *before* anything changes. This is crucial: it will never perform a whole-disk fuzzy-name deletion after the fact.
4. The app's own registered interactive uninstaller—or Windows `Remove-AppxPackage` for MSIX—is launched. SpaceMedic does not invent undocumented silent switches.
5. Complete the publisher wizard and reboot if it requests one.
6. Reopen SpaceMedic and click **Scan leftovers**.
7. SpaceMedic verifies that the same registry product/package identity is no longer installed, checks every captured path against all remaining apps' install locations, and shows only surviving high-confidence paths in **Junk & caches**.
8. Review and send selected leftovers to Recycle Bin. Nothing is deleted automatically.

### Why it cannot honestly promise “as if it was never installed”

Windows has no universal ownership database for everything an app creates while running. Apps may share MSI components, runtimes, COM registrations, services, drivers, scheduled tasks, browser engines, vendor folders, licenses, and user-generated data. Microsoft Windows Installer itself uses component/reference rules so a resource may intentionally remain while another product still needs it. A heuristic tool that deletes every name match can break unrelated apps or Windows.

SpaceMedic therefore provides the strongest safe guarantee it can defend:

- Runs the supported uninstaller first.
- Captures candidates before uninstall and verifies them afterward.
- Requires exact product/folder identity—never substring-only matches.
- Skips paths claimed by another installed app.
- Never removes Documents, projects, saves, broad publisher folders, Common Files, WindowsApps, Windows Installer cache, services, drivers, or Registry keys heuristically.
- Moves approved files/folders to Recycle Bin.
- Blocks forced cleanup for security software, VPNs, drivers, frameworks/runtimes, databases, firmware, virtualization software, and other deep integrations. Use the publisher's official cleanup utility for those.

Registry leftovers usually consume negligible disk space. SpaceMedic prioritizes system reliability over cosmetic “zero traces” claims and does not include an unsupported registry cleaner.

## Understanding the safety labels

| Label | Meaning | Examples |
|---|---|---|
| SAFE | Generated cache/build data normally recreated by a tool | `__pycache__`, `.next`, `.pytest_cache`, npm/pip cache |
| REVIEW | Regenerable or removable, but may cost time/bandwidth or affect offline work | `.venv`, `node_modules`, Maven/NuGet cache, AI models |
| SYSTEM | Measured by SpaceMedic, but cleaned only through Microsoft-supported tools | old updates, Windows.old, WER system reports, memory dumps, Windows Temp |
| Protected/not offered | Never manually removed by SpaceMedic | WinSxS internals, Program Files, pagefile, System32 |

`node_modules` and virtual environments can usually be recreated, but only if the project has correct manifests/lockfiles and dependencies remain available. SpaceMedic therefore labels them **REVIEW**, not blindly safe.

## Why Explorer's folder numbers can be confusing

The screenshot sizes are not a list of folders you should delete. In particular:

- `C:\Users` contains personal files, projects, AppData, cloud sync data, and caches. Analyze inside it; never delete the entire folder.
- `C:\Windows` includes the component store and hard-linked files. Explorer can overcount apparent folder size. Use `DISM /Online /Cleanup-Image /AnalyzeComponentStore` for the supported, accurate component-store report.
- `C:\Program Files` and `C:\Program Files (x86)` contain installed applications. Uninstall through Windows Settings; deleting these folders manually leaves broken services, registry entries, and shared components.
- Logical **Size** and allocated **Size on disk** can differ because of compression, sparse files, hard links, and allocation units.

## Design and safety decisions

- **No automatic “clean everything.”** A storage utility should explain and preview before acting.
- **Recycle Bin by default.** The implementation uses the Windows shell operation with `FOF_ALLOWUNDO`; Windows documentation says this sends deleted objects to Recycle Bin. Windows can still warn if an object is too large.
- **No direct WinSxS deletion.** Only supported DISM commands are surfaced. `/ResetBase` is intentionally excluded because it prevents rollback of superseded updates.
- **No pagefile manipulation.** Removing or shrinking paging can destabilize low-memory systems.
- **No Downloads auto-delete.** Downloads often contain important work. Open and review them manually.
- **No duplicate deletion by filename alone.** Same names do not prove same content. Duplicate hashing is planned for a later version.
- **Offline first.** No telemetry, account, upload, or API key.

## Research basis

SpaceMedic's workflow combines ideas proven by disk analyzers with Microsoft-supported cleanup paths:

- Microsoft: [Free up drive space in Windows](https://support.microsoft.com/en-us/windows/free-up-drive-space-in-windows-85529ccb-c365-490d-b548-831022bc9b32) — Cleanup recommendations, Storage Sense, moving files, OneDrive Files On-Demand.
- Microsoft: [Free up space for Windows updates](https://support.microsoft.com/en-us/windows/deployment/updates-lifecycle/free-up-space-for-windows-updates) — update working-space guidance and external-storage option.
- Microsoft Learn: [Configure Storage Sense](https://learn.microsoft.com/en-us/windows/configuration/storage/storage-sense) — temp, Recycle Bin, Downloads, and cloud-content policies.
- Microsoft Learn: [Clean up the WinSxS folder](https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/clean-up-the-winsxs-folder?view=windows-11) and [determine its actual size](https://learn.microsoft.com/en-us/windows-hardware/manufacture/desktop/determine-the-actual-size-of-the-winsxs-folder?view=windows-11) — supported old-component cleanup, hard-link-aware size, and the reason manual deletion is forbidden.
- Microsoft Learn: [Windows Error Reporting reports](https://learn.microsoft.com/en-us/windows-server/failover-clustering/troubleshooting-using-wer-reports) — system report queue/archive location and diagnostic purpose.
- Microsoft Learn: [Windows Installer uninstall registry key](https://learn.microsoft.com/en-us/windows/win32/msi/uninstall-registry-key) — `DisplayName`, `EstimatedSize`, `InstallLocation`, and registered uninstall metadata.
- Microsoft Learn: [Windows Installer Component table](https://learn.microsoft.com/en-us/windows/win32/msi/component-table) and [Removing stranded files](https://learn.microsoft.com/en-us/windows/win32/msi/removing-stranded-files) — shared/permanent components, reference counts, and protected resources explain why generic forced deletion is unsafe.
- Microsoft Learn: [WinGet uninstall](https://learn.microsoft.com/en-us/windows/package-manager/winget/uninstall) — exact app/package selection and supported uninstall behavior.
- Revo's documented [analyze → built-in uninstaller → scan → review](https://www.revouninstaller.com/online-manual/) workflow informed the staged design; SpaceMedic uses stricter exact-path matching and omits automatic Registry deletion.
- Microsoft Learn: [SHFileOperation](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shfileoperationw) — Windows shell file operation used for Recycle Bin cleanup.
- [WinDirStat](https://github.com/windirstat/windirstat) — directory tree, largest files, extension statistics, treemap, and maintenance-tool workflow.
- [WizTree command-line export guide](https://www.diskanalyzer.com/guide) — optional user-supplied MFT scan provider and documented CSV export parameters. SpaceMedic does not redistribute WizTree.
- Docker Docs: [Uninstall Docker Desktop](https://docs.docker.com/desktop/uninstall/) — authoritative Windows residual-folder list and warning that uninstall/removal destroys local containers, images, volumes and related data.
- Developer-storage research: [DiskSage](https://github.com/DonkRonk17/DiskSage), [disk-space-analyzer-skill](https://github.com/WhiteMinds/disk-space-analyzer-skill), and [Jharu](https://github.com/riponcm/Jharu) — age/type analysis, safety levels, build artifacts, package caches, and AI model caches.
- Cache conventions are also consistent with package-tool documentation and common CI cache paths (`node_modules`, pip, Gradle, Maven, NuGet).

## Testing

```bat
py -3 -m unittest discover -s tests -v
```

Tests create temporary projects and verify project detection, size aggregation, regenerable-artifact classification, non-overlapping reclaim totals, and JSON serialization.

## Known limitations / honest safety boundaries

- The built-in scanner remains a portable recursive scanner. SpaceMedic 2.1 can use a user-installed WizTree CLI as an optional MFT-backed provider, but does not bundle/download it because its licence and executable supply chain are separate. Raw-volume parsing is therefore never silently introduced. The built-in fallback avoids reparse points and remains dependency-free.
- Install Monitor snapshots common application locations and Registry text, with a 600,000-file safety cap. Background Windows/app activity may also appear in a diff, so trace items require review and Registry differences are report-only.
- “All installed apps” means registered desktop entries plus current-user Store/MSIX packages. Windows components, drivers, optional features and packages installed only for other users are intentionally not presented as ordinary removable apps.
- Cache relocation currently has verified adapters for pip, npm, uv, Hugging Face and Ollama. Gradle/Maven/NuGet/Cargo migrations remain analysis-only because relocating only part of their stores can break tool invariants.
- Windows installer `EstimatedSize` is optional and may be inaccurate.
- Recycle Bin shell operations have long-path and volume-policy edge cases; SpaceMedic fails closed instead of force-deleting.
- Startup/services/tasks and Docker/WSL/VM findings are analysis-only. The owning vendor/Windows tool must perform destructive changes.
- Code signing requires the project owner to provide a valid PFX certificate through GitHub secrets; unsigned local/source builds cannot manufacture a trusted publisher identity.
- Full Urdu UI localization and a separately audited native MFT plugin remain future work.

## License

MIT. Review the source before running cleanup software; keep backups of irreplaceable work.
