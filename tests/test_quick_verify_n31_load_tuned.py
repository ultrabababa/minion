import re
import unittest
from pathlib import Path


class QuickVerifyN31LoadTunedTests(unittest.TestCase):
    def test_total_tps_matches_known_good_n31_baseline_40(self):
        path = Path(__file__).resolve().parents[1] / "setups" / "hotstuff-quick-verify-n31.yaml"
        text = path.read_text(encoding="utf-8")

        m_workers = re.search(r"^\s*-\s*number:\s*(\d+)\s*$", text, re.MULTILINE)
        m_load = re.search(r"load:\s*\n\s*0:\s*(\d+)", text, re.MULTILINE)
        self.assertIsNotNone(m_workers)
        self.assertIsNotNone(m_load)

        workers = int(m_workers.group(1))
        per_worker = int(m_load.group(1))

        self.assertEqual(workers * per_worker, 40)


if __name__ == "__main__":
    unittest.main()
