import re
import unittest
from pathlib import Path


class BuildAsonninoHotstuffScriptTests(unittest.TestCase):
    def test_rust_toolchain_is_new_enough_for_current_dependencies(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "script"
            / "remote"
            / "linux"
            / "apt"
            / "build-asonnino-hotstuff"
        )
        content = script_path.read_text(encoding="utf-8")

        m = re.search(r"asdf_install\s+rust\s+(\d+)\.(\d+)\.(\d+)", content)
        self.assertIsNotNone(m, "missing rust toolchain pin in build script")

        version = tuple(int(x) for x in m.groups())
        self.assertGreaterEqual(
            version,
            (1, 77, 0),
            "Rust toolchain must be >= 1.77.0 because current dependency graph requires it",
        )


if __name__ == "__main__":
    unittest.main()
