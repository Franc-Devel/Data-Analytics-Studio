import unittest

import pandas as pd

from finance_app.analysis import numeric_summary, profile_dataset, quality_issues, recommend_chart


class AnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = pd.DataFrame({"fecha": pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"]), "ventas": [10.0, 20.0, 30.0], "rubro": ["A", "A", None]})

    def test_profile(self) -> None:
        profile = profile_dataset(self.frame)
        self.assertEqual(profile["filas"], 3)
        self.assertEqual(profile["celdas_faltantes"], 1)
        self.assertEqual(profile["numericas"], 1)

    def test_summary(self) -> None:
        result = numeric_summary(self.frame).set_index("Variable")
        self.assertEqual(result.loc["ventas", "Media"], 20.0)
        self.assertEqual(result.loc["ventas", "Mediana"], 20.0)

    def test_quality_detects_missing(self) -> None:
        self.assertTrue(any(issue.area == "rubro" and issue.affected == 1 for issue in quality_issues(self.frame)))

    def test_chart_recommendation(self) -> None:
        title, _ = recommend_chart(self.frame, ["fecha", "ventas"])
        self.assertEqual(title, "Línea temporal")


if __name__ == "__main__":
    unittest.main()
