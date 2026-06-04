import unittest
from pathlib import Path


class DiabloSplitStartTests(unittest.TestCase):
    def test_diablo_local_script_exposes_primary_and_secondary_start_actions(self):
        script_path = Path(__file__).resolve().parents[1] / "script" / "local" / "diablo.pm"
        content = script_path.read_text(encoding="utf-8")

        self.assertIn("sub start_primary", content)
        self.assertIn("sub start_secondaries", content)
        self.assertIn("$action eq 'start-primary'", content)
        self.assertIn("$action eq 'start-secondaries'", content)


if __name__ == "__main__":
    unittest.main()
