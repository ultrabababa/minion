import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


def _load_module(script_path: Path):
    spec = importlib.util.spec_from_file_location("plot_f_by_mode", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PlotFByModeTests(unittest.TestCase):
    def test_parse_tarball_name(self):
        module = _load_module(Path(__file__).resolve().parents[1] / "plot_f_by_mode.py")
        parsed = module.parse_tarball_name(
            "asonnino-hotstuff-1-5-10-crash-3-1_2026-03-23-10-18-18.results.tar.gz"
        )
        self.assertEqual(parsed, ("asonnino-hotstuff", "crash", 3, 1))

    def test_select_latest_by_mtime(self):
        module = _load_module(Path(__file__).resolve().parents[1] / "plot_f_by_mode.py")

        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            older = base / "asonnino-hotstuff-1-5-10-crash-2-1_2026-03-23-10-00-00.results.tar.gz"
            newer = base / "asonnino-hotstuff-1-5-10-crash-2-1_2026-03-23-11-00-00.results.tar.gz"
            older.write_bytes(b"")
            newer.write_bytes(b"")
            os.utime(older, (1000, 1000))
            os.utime(newer, (2000, 2000))

            records = [
                {"path": str(older), "blockchain": "asonnino-hotstuff", "mode": "crash", "failures": 2, "redundancy": 1},
                {"path": str(newer), "blockchain": "asonnino-hotstuff", "mode": "crash", "failures": 2, "redundancy": 1},
            ]
            sel = module.select_latest_matching(records, "asonnino-hotstuff", "crash", 2, 1)
            self.assertEqual(sel["path"], str(newer))

    def test_parse_redundant_none_tarball(self):
        module = _load_module(Path(__file__).resolve().parents[1] / "plot_f_by_mode.py")
        parsed = module.parse_tarball_name(
            "asonnino-hotstuff-redundant-1-5-10-none-0-4_2026-03-22-19-19-25.results.tar.gz"
        )
        self.assertEqual(parsed, ("asonnino-hotstuff-redundant", "none", 0, 4))


if __name__ == "__main__":
    unittest.main()
