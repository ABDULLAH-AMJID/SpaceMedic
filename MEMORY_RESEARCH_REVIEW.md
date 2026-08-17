# Memory Research Review — What SpaceMedic Accepts and Rejects

The submitted research contains useful architecture ideas, but it also mixes public Win32 APIs, undocumented/version-sensitive behavior, speculation, and unsafe optimization claims. SpaceMedic implements only behavior that can be defended and tested.

## Accepted and implemented

- `GlobalMemoryStatusEx` and `GetPerformanceInfo` for physical, available and commit telemetry.
- Native Toolhelp process enumeration and `GetProcessMemoryInfo` for working set, private commit and cumulative page faults.
- `GetProcessHandleCount`, `GetGuiResources`, thread count, CPU time and process-start identity.
- `CreateMemoryResourceNotification` with an event-driven Windows low-memory watcher.
- Persistent seven-day SQLite samples with bounded retention and WAL mode.
- Sustained private-byte, handle and GDI growth analysis using linear regression, R², monotonicity, minimum growth/rate/duration and workload confidence penalty.
- Foreground, system, security and SpaceMedic process protection.
- Advisory-only leak findings. The owning process/vendor must repair a leak; an external tool cannot free live heap allocations safely.
- Graceful closing of a selected normal app and an explicitly warned, manual idle-process working-set trim.
- Local operation history and transparent explanations.

## Rejected as unsafe, unsupported, or misleading

- **“Free leaked memory externally.”** Only the allocating process can correctly release its heap/objects. Working-set trimming does not fix a leak.
- **Automatic all-process trimming.** This creates page faults and can reduce performance.
- **Automatic standby-list or modified-list purge.** Standby pages are useful reusable cache. Modified pages represent writes Windows schedules safely.
- **Undocumented `NtSetSystemInformation` commands in an automatic consumer tool.** Values and privilege behavior are version-sensitive and not a stable public contract.
- **“Intelligent selective standby purge.”** Windows does not expose an API that lets a user-mode app identify and evict arbitrary cold standby pages by file/access frequency as proposed.
- **Chunking physical-page combine in 1 GB blocks.** The described system command does not expose that control.
- **Working-set rollback.** Removed resident pages cannot be restored as a transaction; the process faults them back when used.
- **Externally unloading unused DLLs.** Module residency is not proof that unloading is safe; forced unload can corrupt a process.
- **Closing leaked handles externally.** Handle ownership and invariants belong to the process; forced closure can corrupt it.
- **Fixed file-cache percentages based only on RAM.** Cache value depends on workload and Windows already manages it dynamically.
- **More aggressive cache purging on SSD/NVMe.** Faster storage does not make destructive cache invalidation a performance optimization.
- **Generic pagefile multipliers.** Commit requirements and crash-dump policy are workload-specific; system-managed is usually the safe default.
- **Disabling Windows Update, BITS, Search, telemetry, SysMain, Print Spooler, or security services as a “memory boost.”** This can break features, security, updates and accessibility for trivial or temporary savings.
- **Automatic memory-compression changes.** Windows compression is kernel-managed and commonly improves responsiveness by avoiding disk I/O.
- **A universal “optimization score.”** A single score would hide uncertainty and encourage cosmetic actions.
- **Machine learning claims without validated training data.** SpaceMedic uses explainable statistics, not an unverified AI label.

## Leak finding is not a diagnosis

A rising private-byte trend may be a leak, but it may also be a legitimate workload, browser tab growth, compilation, model loading, cache warming, a database buffer pool, or a long-running task. SpaceMedic therefore requires multiple samples over time and reports confidence, rate, observation duration and caveats. Confirmation should use Performance Monitor, Process Explorer/VMMap, Windows Performance Recorder/Analyzer, DebugDiag, application logs, or vendor support.

## Release claim policy

SpaceMedic will not claim to be the “world’s best” memory booster until independent Windows 10/11 benchmarks show no regression in app launch time, file I/O, compilation, game frame-time, foreground responsiveness and page-fault rate across representative 4/8/16/32+ GB systems. The current goal is the safest and most transparent memory intelligence workflow—not the largest before/after free-RAM number.
