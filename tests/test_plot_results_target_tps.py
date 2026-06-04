import importlib.util
import unittest
from pathlib import Path


def _load_module(script_path: Path):
    spec = importlib.util.spec_from_file_location("plot_results", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PlotResultsTargetTpsTests(unittest.TestCase):
    def setUp(self):
        self.module = _load_module(Path(__file__).resolve().parents[1] / "plot_results.py")

    def test_infer_target_tps_from_workload_text_n10_like(self):
        workload_text = """
name: "x"
workloads:
  - number: 5
    client:
      behavior:
        - interaction: !transfer { from: a, to: b }
          load:
            0: 40
            60: 40
"""
        self.assertEqual(self.module._infer_target_tps_from_workload_text(workload_text), 200)

    def test_infer_target_tps_from_workload_text_n22_like(self):
        workload_text = """
name: "x"
workloads:
  - number: 5
    client:
      behavior:
        - interaction: !transfer { from: a, to: b }
          load:
            0: 20
            60: 20
"""
        self.assertEqual(self.module._infer_target_tps_from_workload_text(workload_text), 100)

    def test_override_target_tps_wins_over_inferred(self):
        self.assertEqual(self.module._resolve_target_tps(100, 250), 250)
        self.assertEqual(self.module._resolve_target_tps(None, 250), 250)

    def test_make_banner_text_uses_target_tps(self):
        banner = self.module._make_banner_text(10, 3, 200)
        self.assertIn("N=10", banner)
        self.assertIn("f_max=3", banner)
        self.assertIn("200 TPS target", banner)


if __name__ == "__main__":
    unittest.main()
