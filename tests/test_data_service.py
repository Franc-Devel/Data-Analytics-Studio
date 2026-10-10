import tempfile
import unittest
from pathlib import Path

from finance_app.data_service import DataLoadError, load_dataset


class DataServiceTests(unittest.TestCase):
    def test_loads_semicolon_csv_and_normalizes_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "datos.csv"
            path.write_text(" importe ;importe\n10;20\n", encoding="utf-8")
            loaded = load_dataset(path)
            self.assertEqual(loaded.frame.columns.tolist(), ["importe", "importe_2"])
            self.assertEqual(loaded.frame.iloc[0].tolist(), [10, 20])

    def test_rejects_unsupported_extension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "datos.txt"
            path.write_text("dato", encoding="utf-8")
            with self.assertRaises(DataLoadError):
                load_dataset(path)


if __name__ == "__main__":
    unittest.main()

