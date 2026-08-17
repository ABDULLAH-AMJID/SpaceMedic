import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spacemedic.app_removal import aliases, capture_inventory, scan_session_leftovers, is_high_risk, RemovalSession
from spacemedic.windows_tools import InstalledApp, _safe_verified_leftover


class AppRemovalTests(unittest.TestCase):
    def test_exact_pre_and_post_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            local = root / "Local"
            roaming = root / "Roaming"
            program = root / "ProgramFiles"
            data = root / "ProgramData"
            for p in (local, roaming, program, data): p.mkdir()
            app_data = local / "Acme Editor"
            app_data.mkdir()
            (app_data / "cache.bin").write_bytes(b"x" * 500)
            install = program / "Acme Editor"
            install.mkdir()
            (install / "editor.exe").write_bytes(b"x" * 700)
            unrelated = local / "Acme Other"
            unrelated.mkdir()
            (unrelated / "keep.dat").write_bytes(b"x" * 900)
            env = {
                "LOCALAPPDATA": str(local), "APPDATA": str(roaming), "PROGRAMFILES": str(program),
                "PROGRAMFILES(X86)": str(root / "PF86"), "PROGRAMDATA": str(data), "USERPROFILE": str(root),
            }
            app = InstalledApp("Acme Editor", "Acme Corp", "1.0", install_location=str(install),
                               uninstall_string="uninstall.exe", registry_id="{APP}")
            with patch.dict(os.environ, env, clear=False):
                session = capture_inventory(app, [app])
                paths = {os.path.normcase(x["path"]) for x in session.inventory}
                self.assertIn(os.path.normcase(str(app_data)), paths)
                self.assertIn(os.path.normcase(str(install)), paths)
                self.assertNotIn(os.path.normcase(str(unrelated)), paths)
                leftovers, warnings = scan_session_leftovers(session, [])
                self.assertEqual(sum(x.size for x in leftovers), 1200)

    def test_shared_claim_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            shared = Path(tmp) / "SharedProduct"
            shared.mkdir()
            app = InstalledApp("SharedProduct", install_location=str(shared), uninstall_string="u.exe", registry_id="A")
            other = InstalledApp("Other", install_location=str(shared), uninstall_string="u2.exe", registry_id="B")
            with patch.dict(os.environ, {"LOCALAPPDATA": tmp, "APPDATA": tmp, "PROGRAMDATA": tmp}, clear=False):
                session = capture_inventory(app, [app, other])
            self.assertFalse(session.inventory)
            self.assertTrue(any("another installed app" in x for x in session.warnings))

    def test_high_risk_app_disables_heuristics(self):
        app = InstalledApp("Example VPN Driver", "Example", uninstall_string="u.exe")
        self.assertTrue(is_high_risk(app))

    def test_aliases_are_not_generic(self):
        app = InstalledApp("Acme Studio Professional", "Acme Corp")
        names = aliases(app)
        self.assertIn("acmestudioprofessional", names)
        self.assertNotIn("studio", names)

    def test_verified_leftover_guard(self):
        self.assertFalse(_safe_verified_leftover(r"C:\Program Files"))
        self.assertFalse(_safe_verified_leftover(r"C:\Program Files\Common Files\Vendor"))

    def test_docker_vendor_documented_residual_after_old_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "Local"; roaming = Path(tmp) / "Roaming"; data = Path(tmp) / "ProgramData"; pf = Path(tmp) / "PF"
            for p in (local, roaming, data, pf): p.mkdir()
            docker = local / "Docker"; docker.mkdir(); (docker / "docker_data.vhdx").write_bytes(b"x" * 2048)
            app = InstalledApp("Docker Desktop", "Docker Inc.", registry_id="docker", uninstall_string="u.exe")
            session = RemovalSession(app.__dict__ if hasattr(app, "__dict__") else {
                "name": app.name, "publisher": app.publisher, "version": app.version, "estimated_size": 0,
                "install_location": "", "uninstall_string": "u.exe", "app_type": "Desktop", "registry_id": "docker",
                "package_full_name": "", "package_family_name": "", "protected": False}, 1.0, [], [])
            env = {"LOCALAPPDATA": str(local), "APPDATA": str(roaming), "PROGRAMDATA": str(data), "PROGRAMFILES": str(pf), "USERPROFILE": tmp}
            with patch.dict(os.environ, env, clear=False):
                leftovers, warnings = scan_session_leftovers(session, [])
            self.assertTrue(any(Path(x.path).name == "Docker" for x in leftovers))
            self.assertEqual(sum(x.size for x in leftovers), 2048)


if __name__ == "__main__":
    unittest.main()
