import unittest
from pathlib import Path


class SshScpRetryTests(unittest.TestCase):
    def test_ssh_module_retries_scp_on_transient_disconnects(self):
        module_path = Path(__file__).resolve().parents[1] / "lib" / "Minion" / "Ssh.pm"
        content = module_path.read_text(encoding="utf-8")

        self.assertIn("sub _scp_with_retry", content)
        self.assertIn("lost connection", content)
        self.assertIn("kex_exchange_identification: Connection", content)
        self.assertIn("No route to host", content)
        self.assertIn("Connection reset by peer", content)
        self.assertIn("return $self->_scp_with_retry", content)


if __name__ == "__main__":
    unittest.main()
