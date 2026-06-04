import unittest
from pathlib import Path


class AsonninoHotstuffStartCleanupTests(unittest.TestCase):
    def test_start_script_cleans_up_existing_processes_before_restart(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "script"
            / "remote"
            / "asonnino-hotstuff"
        )
        content = script_path.read_text(encoding="utf-8")

        self.assertIn(
            "pkill -f \"${install_root}/node -vv run --keys ${install_root}/config/node_${node_index}.json\"",
            content,
            "start path must kill stale node process for the same key before launching",
        )
        self.assertIn(
            "pkill -f \"asonnino-hotstuff-observer.*--port ${bridge_port}\"",
            content,
            "start path must kill stale observer bridge process for the same port before launching",
        )


if __name__ == "__main__":
    unittest.main()
