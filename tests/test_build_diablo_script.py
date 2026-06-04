import re
import unittest
from pathlib import Path


class BuildDiabloScriptTests(unittest.TestCase):
    def test_build_diablo_uses_go_version_from_diablo_go_mod(self):
        repo_root = Path(__file__).resolve().parents[2]
        script = repo_root / "minion" / "script" / "remote" / "linux" / "apt" / "build-diablo"
        go_mod = repo_root / "diablo" / "go.mod"

        script_content = script.read_text(encoding="utf-8")
        go_mod_content = go_mod.read_text(encoding="utf-8")

        script_match = re.search(r"golang_version='([^']+)'", script_content)
        go_mod_match = re.search(r"^go\s+([0-9.]+)\s*$", go_mod_content, re.MULTILINE)

        self.assertIsNotNone(script_match)
        self.assertIsNotNone(go_mod_match)
        self.assertEqual(go_mod_match.group(1), script_match.group(1))


if __name__ == "__main__":
    unittest.main()
