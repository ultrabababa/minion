import unittest
from pathlib import Path


class MiddlewareDiabloArchiveReceiveTests(unittest.TestCase):
    def test_diablo_archive_is_received_to_expected_file_path(self):
        middleware = Path(__file__).resolve().parents[1] / "bin" / "middleware"
        content = middleware.read_text(encoding="utf-8")

        self.assertIn(
            "$builder->recv(['install/diablo.tar.gz'], TARGET => 'binaries/diablo.tar.gz' )",
            content,
        )
        self.assertIn("install_archive($fleet, 'binaries/diablo.tar.gz'", content)
        self.assertNotIn("TARGET => 'binaries/' )->wait() != 0){\n\t\tfatal(\"failed to receive diablo\")", content)


if __name__ == "__main__":
    unittest.main()
