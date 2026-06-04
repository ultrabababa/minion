import unittest
from pathlib import Path


class DiabloObserverStartFailureTests(unittest.TestCase):
    def test_observer_start_suppresses_kill_noise_and_fails_after_retries(self):
        script_path = Path(__file__).resolve().parents[1] / "script" / "remote" / "diablo-observer"
        content = script_path.read_text(encoding="utf-8")

        self.assertIn('kill -0 "$pid" 2> \'/dev/null\'', content)
        self.assertIn("observer failed to start after retries", content)
        self.assertIn("observer not connected, restarting", content)
        self.assertIn("grep -q '^connected$'", content)
        self.assertIn("python3 -u", content)
        self.assertIn('tail -20 "${dir}/err"', content)
        self.assertIn('tail -80 "${dir}/err"', content)


if __name__ == "__main__":
    unittest.main()
