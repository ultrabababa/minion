import unittest
from pathlib import Path


class MiddlewareObserverLogCollectionTests(unittest.TestCase):
    def test_observer_logs_are_collected_only_when_fault_observer_is_needed(self):
        middleware_path = Path(__file__).resolve().parents[1] / "bin" / "middleware"
        content = middleware_path.read_text(encoding="utf-8")

        observer_out = "deploy/diablo-observer/out"
        observer_err = "deploy/diablo-observer/err"

        self.assertIn("if ($need_fault_observer) {", content)
        self.assertIn(observer_out, content)
        self.assertIn(observer_err, content)
        self.assertLess(content.rfind("if ($need_fault_observer) {", 0, content.index(observer_out)), content.index(observer_out))
        self.assertLess(content.rfind("if ($need_fault_observer) {", 0, content.index(observer_err)), content.index(observer_err))


if __name__ == "__main__":
    unittest.main()
