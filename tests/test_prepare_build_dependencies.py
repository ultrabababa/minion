import unittest
from pathlib import Path


class PrepareBuildDependenciesTests(unittest.TestCase):
    def test_prepare_build_installs_curl_for_asdf_plugin_downloads(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "script"
            / "remote"
            / "linux"
            / "apt"
            / "prepare-build"
        )
        content = script_path.read_text(encoding="utf-8")

        self.assertIn("'curl'", content)


if __name__ == "__main__":
    unittest.main()
