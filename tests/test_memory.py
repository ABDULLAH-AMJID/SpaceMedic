import tempfile
import time
import unittest
from pathlib import Path

from spacemedic.memory_tools import MemorySnapshot, ProcessMemory
from spacemedic.memory_intelligence import MemoryIntelligence, _regression, confirmed_low_memory


class MemoryPolicyTests(unittest.TestCase):
    def test_pressure_classification(self):
        gb = 1024 ** 3
        self.assertEqual(MemorySnapshot(16*gb, 8*gb, 50, 0, 0, 0).pressure, "healthy")
        self.assertEqual(MemorySnapshot(16*gb, 3*gb, 75, 0, 0, 0).pressure, "moderate")
        self.assertEqual(MemorySnapshot(16*gb, int(1.5*gb), 85, 0, 0, 0).pressure, "high")
        self.assertEqual(MemorySnapshot(16*gb, int(0.5*gb), 95, 0, 0, 0).pressure, "critical")

    def test_used_physical_never_negative(self):
        snap = MemorySnapshot(100, 120, 0, 0, 0, 0)
        self.assertEqual(snap.used_physical, 0)

    def test_regression_detects_linear_growth(self):
        slope, r2 = _regression([(0, 10), (60, 20), (120, 30), (180, 40)])
        self.assertAlmostEqual(slope, 1/6, places=5)
        self.assertGreater(r2, 0.99)

    def test_persistent_private_memory_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            intelligence = MemoryIntelligence(str(Path(tmp) / "memory.db"))
            item = ProcessMemory(123, "leaky-app", 300*1024**2, 400*1024**2, 10, "Leaky App", True, False, start_key="start")
            identity = intelligence.identity(item)
            base = time.time() - 9 * 60
            with intelligence._connect() as db:
                for index in range(10):
                    private = (120 + index * 24) * 1024**2
                    db.execute("INSERT INTO process_samples VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               (base + index*60, identity, 123, "leaky-app", private, private, 100, 20, 20, 5, 1000+index, index*0.2, 0))
            findings = intelligence.findings([item])
            self.assertTrue(any(x.kind == "private-memory trend" for x in findings))
            intelligence.close()

    def test_low_memory_event_requires_current_evidence(self):
        gb = 1024**3
        healthy = MemorySnapshot(16*gb, 6*gb, 62, 8*gb, 24*gb, 16*gb)
        low_physical = MemorySnapshot(16*gb, 300*1024**2, 97, 12*gb, 24*gb, 12*gb)
        commit_exhausted = MemorySnapshot(16*gb, 4*gb, 75, 23*gb, 24*gb, gb)
        self.assertFalse(confirmed_low_memory(healthy))
        self.assertTrue(confirmed_low_memory(low_physical))
        self.assertTrue(confirmed_low_memory(commit_exhausted))

    def test_critical_plan_never_auto_trims(self):
        with tempfile.TemporaryDirectory() as tmp:
            intelligence = MemoryIntelligence(str(Path(tmp) / "memory.db"))
            gb = 1024**3
            snap = MemorySnapshot(8*gb, int(0.4*gb), 95, int(15*gb), 16*gb, gb)
            plan = intelligence.plan(snap, [], [])
            self.assertEqual(plan.state, "critical")
            self.assertIn("explicit user action", plan.automatic_action)
            intelligence.close()


if __name__ == "__main__":
    unittest.main()
