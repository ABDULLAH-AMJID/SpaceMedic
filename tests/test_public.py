import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spacemedic.config import Settings, load, save
from spacemedic.i18n import LANGUAGES, tr
from spacemedic.rules import load_cache_rules


class PublicEditionTests(unittest.TestCase):
    def test_settings_round_trip_and_offline_default(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"LOCALAPPDATA": tmp}):
            settings = Settings(language="es", scan_workers=4)
            save(settings)
            restored = load()
            self.assertEqual(restored.language, "es")
            self.assertEqual(restored.scan_workers, 4)
            self.assertFalse(restored.update_checks)

    def test_pre_hud_theme_migrates(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"LOCALAPPDATA": tmp}):
            target = Path(tmp) / "SpaceMedic" / "settings.json"
            target.parent.mkdir()
            target.write_text(json.dumps({"theme": "dark"}), encoding="utf-8")
            self.assertEqual(load().theme, "hud")

    def test_all_public_languages_have_core_navigation(self):
        keys = ("analyze", "fast_scan", "search", "apps", "memory", "settings", "privacy")
        self.assertEqual(len(LANGUAGES), 8)
        for language in LANGUAGES:
            for key in keys:
                self.assertTrue(tr(language, key))
                self.assertNotEqual(tr(language, key), key)

    def test_unsafe_community_rule_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"LOCALAPPDATA": tmp}), \
             patch("spacemedic.rules.bundled_rules_path", return_value=Path(tmp) / "missing.json"):
            target = Path(tmp) / "SpaceMedic" / "cleanup_rules.json"
            target.parent.mkdir()
            target.write_text(json.dumps([{"env":"LOCALAPPDATA","path":"../Windows","label":"Unsafe","risk":"safe","direct_cleanup":True}]))
            rules, errors = load_cache_rules()
            self.assertFalse(rules)
            self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
