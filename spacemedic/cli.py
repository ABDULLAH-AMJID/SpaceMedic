from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .scanner import DiskScanner, format_bytes, known_global_caches


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="spacemedic", description="Read-only Windows disk and developer-project analyzer")
    sub = parser.add_subparsers(dest="command")
    scan = sub.add_parser("scan", help="scan a drive or folder")
    scan.add_argument("path", nargs="?", default="C:\\" if os.name == "nt" else str(Path.home()))
    scan.add_argument("--json", dest="json_path", help="save full JSON report")
    scan.add_argument("--top", type=int, default=20)
    sub.add_parser("caches", help="measure known developer/app caches")
    args = parser.parse_args(argv)

    if args.command == "caches":
        items = known_global_caches(progress=lambda p, *_: print(f"\r{p:<80}", end="", file=sys.stderr))
        print(file=sys.stderr)
        for x in items:
            print(f"{format_bytes(x.size):>12}  {x.risk.upper():<7} {x.name:<24} {x.path}")
        print(f"\nPotential total: {format_bytes(sum(x.size for x in items))}")
        return 0

    if args.command != "scan":
        parser.print_help()
        return 0
    result = DiskScanner(top_limit=max(20, args.top)).scan(
        args.path, progress=lambda p, f, d: print(f"\r{f:,} files | {d:,} folders | {p[-70:]:<70}", end="", file=sys.stderr)
    )
    print(file=sys.stderr)
    print(f"Scanned: {result.root}\nSize: {format_bytes(result.total_size)} | Files: {result.file_count:,} | Errors: {result.errors:,}")
    print(f"Potentially reclaimable project artifacts: {format_bytes(result.reclaimable)}\n")
    print("Largest folders:")
    for x in result.top_folders[:args.top]: print(f"  {format_bytes(x.size):>12}  {x.path}")
    print("\nProjects:")
    for p in result.projects[:args.top]: print(f"  {format_bytes(p.total_size):>12}  reclaim {format_bytes(p.reclaimable):>10}  [{p.ecosystem}] {p.root}")
    print("\nCleanup candidates:")
    for x in result.cleanup[:args.top]: print(f"  {format_bytes(x.size):>12}  {x.risk.upper():<7} {x.path}")
    if args.json_path:
        with open(args.json_path, "w", encoding="utf-8") as f: json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"\nSaved {args.json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
