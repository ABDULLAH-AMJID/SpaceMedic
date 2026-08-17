import json
import os
import tempfile
import unittest
from pathlib import Path

from spacemedic.scanner import DiskScanner, format_bytes, known_global_caches
from spacemedic.windows_tools import _allowed_cleanup_target


class ScannerTests(unittest.TestCase):
    def test_project_and_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo"
            (root / "node_modules" / "pkg").mkdir(parents=True)
            (root / ".next" / "cache").mkdir(parents=True)
            (root / "src").mkdir()
            (root / "package.json").write_text('{"name":"demo"}')
            (root / "package-lock.json").write_text("{}")
            (root / "node_modules" / "pkg" / "big.js").write_bytes(b"x" * 4096)
            (root / ".next" / "cache" / "data").write_bytes(b"x" * 2048)
            (root / "src" / "index.js").write_text("console.log('safe source')")
            result = DiskScanner(min_large_file=1).scan(str(root))
            self.assertEqual(len(result.projects), 1)
            project = result.projects[0]
            self.assertEqual(project.ecosystem, "Node.js")
            self.assertGreaterEqual(project.dependency_size, 4096)
            self.assertGreaterEqual(project.reclaimable, 6144)
            cleanup_names = {x.name for x in result.cleanup}
            self.assertIn("node_modules", cleanup_names)
            self.assertIn(".next", cleanup_names)
            self.assertNotIn("src", cleanup_names)
            json.dumps(result.to_dict())

    def test_nested_cleanup_not_double_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "package.json").write_text("{}")
            nested = root / "node_modules" / "x" / "__pycache__"
            nested.mkdir(parents=True)
            (nested / "a.pyc").write_bytes(b"x" * 100)
            result = DiskScanner().scan(str(root))
            self.assertEqual([x.name for x in result.cleanup], ["node_modules"])
            self.assertEqual(result.reclaimable, 100)

    def test_known_junk_and_browser_globs(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "Local"
            (local / "Temp").mkdir(parents=True)
            (local / "Temp" / "junk.tmp").write_bytes(b"x" * 200)
            cache = local / "Google" / "Chrome" / "User Data" / "Profile 1" / "Cache"
            cache.mkdir(parents=True)
            (cache / "data").write_bytes(b"x" * 300)
            old = os.environ.get("LOCALAPPDATA")
            os.environ["LOCALAPPDATA"] = str(local)
            try:
                items = known_global_caches()
            finally:
                if old is None: os.environ.pop("LOCALAPPDATA", None)
                else: os.environ["LOCALAPPDATA"] = old
            names = {x.name for x in items}
            self.assertIn("User temporary files", names)
            self.assertTrue(any("Chrome browser cache" in n for n in names))
            self.assertEqual(sum(x.size for x in items), 500)

    def test_protected_cleanup_boundary(self):
        self.assertFalse(_allowed_cleanup_target(r"C:\\Windows\\Temp"))
        self.assertFalse(_allowed_cleanup_target(r"C:\\Program Files\\App\\cache"))
        self.assertTrue(_allowed_cleanup_target(r"C:\\Users\\Demo\\AppData\\Local\\Temp\\old"))

    def test_format(self):
        self.assertEqual(format_bytes(0), "0 B")
        self.assertIn("GB", format_bytes(3 * 1024**3))


if __name__ == "__main__":
    unittest.main()
