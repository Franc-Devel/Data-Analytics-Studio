"""Generate deterministic, entirely synthetic accounting data."""
import csv
from pathlib import Path

DATA_PATH = Path(__file__).parent / "data" / "movimientos_sinteticos.csv"
CATEGORIES = (
    ("Ventas", 10000),
    ("Servicios", 2000),
    ("Otros Ingresos", 500),
    ("Costo de Ventas", 4000),
    ("Gastos Operativos", 1500),
    ("Impuestos", 600),
    ("Otros Gastos", 200),
)


def generate(path: Path = DATA_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["fecha", "categoria", "monto", "origen"])
        for month in range(1, 4):
            for category, base in CATEGORIES:
                writer.writerow([f"2026-{month:02d}-01", category, base * month, "SINTETICO"])
    return path


if __name__ == "__main__":
    print(generate())
