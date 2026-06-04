import unittest
from pathlib import Path


class ObserverStartupDiagnosticsTests(unittest.TestCase):
    def test_observer_reports_local_node_directory_mismatch(self):
        observer_path = Path(__file__).resolve().parents[1] / "observer.py"
        content = observer_path.read_text(encoding="utf-8")

        self.assertIn("expected exactly one local node directory", content)
        self.assertIn("found {nodes}", content)


if __name__ == "__main__":
    unittest.main()
