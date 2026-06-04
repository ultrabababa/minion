import unittest
from pathlib import Path


class AptHelperProxyEnvironmentTests(unittest.TestCase):
    def test_helper_loads_proxy_environment_files(self):
        helper = (
            Path(__file__).resolve().parents[1]
            / "script"
            / "remote"
            / "linux"
            / "apt"
            / "helper"
        )
        content = helper.read_text(encoding="utf-8")

        self.assertIn("load_env_file /etc/environment", content)
        self.assertIn('load_env_file "$HOME/.minion-env"', content)
        self.assertLess(
            content.index("load_env_file /etc/environment"),
            content.index('. "$HOME/.asdf/asdf.sh"'),
        )


if __name__ == "__main__":
    unittest.main()
