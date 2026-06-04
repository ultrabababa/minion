import unittest
from pathlib import Path


class DiabloWorkerObserverArgsTests(unittest.TestCase):
    def test_primary_omits_observer_flag_when_no_observers_are_deployed(self):
        worker_path = Path(__file__).resolve().parents[1] / "script" / "remote" / "diablo-worker"
        content = worker_path.read_text(encoding="utf-8")

        self.assertIn("observer_args=()", content)
        self.assertIn('if [ "${nobserver}" -gt 0 ] ; then', content)
        self.assertIn('observer_args=(--observers "${nobserver}")', content)
        self.assertIn('"${observer_args[@]}"', content)
        self.assertNotIn("--observers ${nobserver}", content)


if __name__ == "__main__":
    unittest.main()
