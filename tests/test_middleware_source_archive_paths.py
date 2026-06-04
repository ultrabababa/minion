import unittest
from pathlib import Path


class MiddlewareSourceArchivePathTests(unittest.TestCase):
    def test_build_archives_sources_from_current_or_parent_directory(self):
        middleware = Path(__file__).resolve().parents[1] / "bin" / "middleware"
        content = middleware.read_text(encoding="utf-8")

        self.assertIn("foreach my $parent ('.', '..')", content)
        self.assertIn("my $candidate = \"$parent/$name\";", content)
        self.assertIn("'-C', $srcdirs{diablo}->[0], $srcdirs{diablo}->[1]", content)
        self.assertIn("'-C', $srcdirs{hotstuff}->[0], $srcdirs{hotstuff}->[1]", content)
        self.assertNotIn("tar --exclude='diablo/.git' -czhf diablo-src.tar.gz diablo/", content)


if __name__ == "__main__":
    unittest.main()
