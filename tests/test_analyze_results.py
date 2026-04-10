import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from minion.analyze_results import analyze_results


class AnalyzeResultsTests(unittest.TestCase):
    def test_summary_uses_submitted_denominator(self):
        data = {
            "Locations": [
                {
                    "Clients": [
                        {
                            "Interactions": [
                                {"SubmitTime": 1.0, "CommitTime": 2.0, "AbortTime": -1, "HasError": False},
                                {"SubmitTime": 3.0, "CommitTime": -1, "AbortTime": 4.0, "HasError": True},
                                {"SubmitTime": -1, "CommitTime": -1, "AbortTime": -1, "HasError": False},
                            ]
                        }
                    ]
                }
            ]
        }

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "results.json"
            p.write_text(json.dumps(data), encoding="utf-8")

            out = io.StringIO()
            with redirect_stdout(out):
                analyze_results(str(p))
            text = out.getvalue()

        self.assertIn("Planned Interactions: 3", text)
        self.assertIn("Submitted:            2", text)
        self.assertIn("Committed:            1 (50.0% of submitted", text)


if __name__ == "__main__":
    unittest.main()
