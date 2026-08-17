import gzip
import json
import os
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from spacemedic.cache_migration import identify
from spacemedic.duplicates import find_duplicates
from spacemedic.install_monitor import compare
from spacemedic.history import record, load
from spacemedic.scan_cache import save as save_scan, latest as latest_scan, compare as compare_scan
from spacemedic.models import ScanResult, ScanItem
from spacemedic.diagnostics import create_bundle
from spacemedic.fast_scanner import _integer
from spacemedic.parallel_scanner import ParallelDiskScanner
from spacemedic.scanner import DiskScanner


class AdvancedTests(unittest.TestCase):
    def test_duplicates_require_exact_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.bin").write_bytes(b"same" * 300_000)
            (root / "b.bin").write_bytes(b"same" * 300_000)
            (root / "c.bin").write_bytes(b"diff" * 300_000)
            groups, errors = find_duplicates(tmp, min_size=100)
            self.assertEqual(errors, 0)
            self.assertEqual(len(groups), 1)
            self.assertEqual({Path(x).name for x in groups[0].paths}, {"a.bin", "b.bin"})

    def test_hardlinks_not_false_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a", Path(tmp) / "b"
            a.write_bytes(b"x" * 1000)
            try: os.link(a, b)
            except OSError: self.skipTest("hard links unavailable")
            groups, _ = find_duplicates(tmp, min_size=1)
            self.assertFalse(groups)

    def test_install_snapshot_compare(self):
        with tempfile.TemporaryDirectory() as tmp:
            before, after = Path(tmp) / "before.gz", Path(tmp) / "after.gz"
            with gzip.open(before, "wt", encoding="utf-8") as f:
                json.dump({"files": {"old": [1, 1]}, "registry": ["A"], "truncated": False}, f)
            with gzip.open(after, "wt", encoding="utf-8") as f:
                json.dump({"files": {"old": [2, 2], "new": [3, 3]}, "registry": ["A", "B"], "truncated": False}, f)
            with patch("spacemedic.install_monitor.monitor_dir", return_value=Path(tmp)):
                report = compare(str(before), str(after))
            self.assertEqual(report["created"][0]["path"], "new")
            self.assertEqual(report["registry_added_report_only"], ["B"])

    def test_cache_adapters(self):
        self.assertEqual(identify("npm cache"), "npm")
        self.assertEqual(identify("Hugging Face models"), "huggingface")
        self.assertIsNone(identify("Unknown cache"))

    def test_history(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"LOCALAPPDATA": tmp}):
            record("unit_test", answer=42)
            rows = load()
            self.assertEqual(rows[0]["action"], "unit_test")
            self.assertEqual(rows[0]["answer"], 42)

    def test_scan_cache_and_change_tracking(self):
        import time
        with tempfile.TemporaryDirectory() as tmp, patch("spacemedic.scan_cache.cache_dir", return_value=Path(tmp)):
            old = ScanResult("X", time.time(), finished=time.time(), total_size=100, top_files=[ScanItem("X/a", "a", 100, kind="file")])
            save_scan(old)
            previous = latest_scan("X")
            now = ScanResult("X", time.time(), finished=time.time(), total_size=175, top_files=[ScanItem("X/a", "a", 150, kind="file"), ScanItem("X/b", "b", 25, kind="file")])
            delta = compare_scan(previous, now)
            self.assertEqual(delta["total_delta"], 75)
            self.assertEqual(delta["grown"][0]["delta"], 50)

    def test_diagnostics_bundle(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"LOCALAPPDATA": tmp}):
            output = str(Path(tmp) / "diag.zip")
            self.assertEqual(create_bundle(output), output)
            self.assertTrue(Path(output).is_file())

    def test_fast_csv_integer(self):
        self.assertEqual(_integer("1,234,567"), 1234567)
        self.assertEqual(_integer("bad"), 0)

    def test_parallel_scanner_matches_standard_totals(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for branch, size in (("one", 1111), ("two", 2222), ("three", 3333)):
                folder = root / branch; folder.mkdir(); (folder / "data.bin").write_bytes(b"x" * size)
            (root / "root.bin").write_bytes(b"z" * 444)
            standard = DiskScanner(min_large_file=1).scan(tmp)
            fast = ParallelDiskScanner(workers=3, min_large_file=1).scan(tmp)
            self.assertEqual(fast.total_size, standard.total_size)
            self.assertEqual(fast.file_count, standard.file_count)
            self.assertEqual(fast.folder_count, standard.folder_count)


if __name__ == "__main__":
    unittest.main()
