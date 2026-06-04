import unittest
from pathlib import Path


class DeployAsonninoHotStuffMempoolModeTests(unittest.TestCase):
    def test_deploy_script_emits_configurable_client_mempool_mode(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "script"
            / "local"
            / "deploy-asonnino-hotstuff.pm"
        )
        content = script_path.read_text(encoding="utf-8")

        self.assertIn("ASONNINO_HOTSTUFF_CLIENT_MEMPOOL_MODE", content)
        self.assertIn("client_mempool_mode", content)
        self.assertIn("'round_robin'", content)
        self.assertIn("'single'", content)


if __name__ == "__main__":
    unittest.main()
