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

    def test_prepare_build_retries_asdf_clone_and_cleans_partial_checkout(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "script"
            / "remote"
            / "linux"
            / "apt"
            / "prepare-build"
        )
        content = script_path.read_text(encoding="utf-8")

        self.assertIn("clone_asdf()", content)
        self.assertIn('rm -rf "$HOME/.asdf"', content)
        self.assertIn("git -c http.version=HTTP/1.1 clone --depth 1 --branch v0.14.0", content)
        self.assertIn('if [ ! -f "$HOME/.asdf/asdf.sh" ]; then', content)


if __name__ == "__main__":
    unittest.main()
