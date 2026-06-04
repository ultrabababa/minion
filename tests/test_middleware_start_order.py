import unittest
from pathlib import Path


class MiddlewareStartOrderTests(unittest.TestCase):
    def test_fault_mode_starts_primary_then_secondaries_then_observers(self):
        middleware_path = Path(__file__).resolve().parents[1] / "bin" / "middleware"
        content = middleware_path.read_text(encoding="utf-8")

        primary_start = "if ($runner->run($diablo, [ 'diablo', 'start-primary' ])->wait() != 0) {"
        observer_start = "if ($runner->run($chain, [ 'diablo-observer', 'start' ])->wait() != 0) {"
        secondary_start = "if ($runner->run($diablo, [ 'diablo', 'start-secondaries' ])->wait() != 0) {"

        self.assertIn(primary_start, content)
        self.assertIn(observer_start, content)
        self.assertIn(secondary_start, content)
        self.assertLess(content.index(primary_start), content.index(secondary_start))
        self.assertLess(content.index(secondary_start), content.index(observer_start))


if __name__ == "__main__":
    unittest.main()
