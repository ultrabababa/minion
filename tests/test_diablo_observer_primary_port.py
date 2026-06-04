import re
import unittest
from pathlib import Path


class DiabloObserverPrimaryPortTests(unittest.TestCase):
    def test_observer_uses_diablo_observer_port(self):
        root = Path(__file__).resolve().parents[1]
        diablo = (root / "script" / "local" / "deploy-diablo.pm").read_text(encoding="utf-8")
        observer = (root / "script" / "local" / "deploy-diablo-observer.pm").read_text(encoding="utf-8")

        diablo_port = re.search(r"my \$PRIMARY_TCP_PORT = (\d+);", diablo)

        self.assertIsNotNone(diablo_port)
        self.assertIn("my $OBSERVER_TCP_PORT = $PRIMARY_TCP_PORT + 1;", observer)
        self.assertIn("$primary . ':' . $OBSERVER_TCP_PORT", observer)


if __name__ == "__main__":
    unittest.main()
