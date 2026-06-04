import unittest
from pathlib import Path


class MiddlewareDiabloWaitTimeoutTests(unittest.TestCase):
    def test_middleware_guards_diablo_wait_with_timeout(self):
        middleware_path = Path(__file__).resolve().parents[1] / "bin" / "middleware"
        content = middleware_path.read_text(encoding="utf-8")

        self.assertIn("MINION_DIABLO_WAIT_TIMEOUT_SEC", content)
        self.assertIn("__DIABLO_WAIT_TIMEOUT__", content)
        self.assertIn("diablo wait timed out", content)
        self.assertIn("if ($runner->run($diablo, [ 'diablo', 'stop' ])->wait() != 0)", content)


if __name__ == "__main__":
    unittest.main()
