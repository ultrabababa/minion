import re
import unittest
from pathlib import Path


class BenchmarkN31FaultViewTests(unittest.TestCase):
    def test_n31_benchmark_targets_80_tps_and_safe_crash11_mempool_view(self):
        path = Path(__file__).resolve().parents[1] / "setups" / "hotstuff-benchmark-n31.yaml"
        text = path.read_text(encoding="utf-8")

        m_workers = re.search(r"^\s*-\s*number:\s*(\d+)\s*$", text, re.MULTILINE)
        m_load = re.search(r"load:\s*\n\s*0:\s*(\d+)", text, re.MULTILINE)
        m_endpoint = re.search(r'!endpoint \[ "(.+)" \]', text)
        self.assertIsNotNone(m_workers)
        self.assertIsNotNone(m_load)
        self.assertIsNotNone(m_endpoint)

        workers = int(m_workers.group(1))
        per_worker = int(m_load.group(1))
        self.assertEqual(workers * per_worker, 80)

        pattern = re.compile(m_endpoint.group(1).encode().decode("unicode_escape"))
        matched = [i for i in range(1, 32) if pattern.match(f"10.30.10.{i}")]
        self.assertEqual(matched, list(range(1, 21)))


if __name__ == "__main__":
    unittest.main()
