from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys

import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}


class DataLoadError(ValueError):
    """Error entendible para el usuario durante la importación."""


@dataclass(frozen=True)
class LoadedDataset:
    frame: pd.DataFrame
    source: Path
    sheet: str | None = None


def excel_sheets(path: str | Path) -> list[str]:
    source = Path(path)
    _validate_source(source, {".xlsx"})
    _require_excel_engine()
    try:
        return pd.ExcelFile(source).sheet_names
    except Exception as exc:
        raise DataLoadError(f"No se pudieron leer las hojas: {exc}") from exc


def load_dataset(path: str | Path, sheet: str | None = None) -> LoadedDataset:
    source = Path(path)
    _validate_source(source, SUPPORTED_EXTENSIONS)
    try:
        if source.suffix.lower() == ".csv":
            frame = _read_csv(source)
        else:
            _require_excel_engine()
            frame = pd.read_excel(source, sheet_name=sheet or 0)
    except Exception as exc:
        raise DataLoadError(f"No se pudo importar el archivo: {exc}") from exc

    if frame.empty and len(frame.columns) == 0:
        raise DataLoadError("El archivo no contiene columnas ni filas.")
    frame.columns = _unique_column_names(frame.columns)
    return LoadedDataset(frame=frame, source=source, sheet=sheet)


def _require_excel_engine() -> None:
    if importlib.util.find_spec("openpyxl") is not None:
        return
    executable = sys.executable
    raise DataLoadError(
        "Falta el componente necesario para leer archivos Excel (openpyxl).\n\n"
        "Cierre la aplicación y ejecute iniciar.bat, o escriba este comando en la "
        "terminal del mismo entorno de Python:\n\n"
        f'"{executable}" -m pip install openpyxl'
    )


def _read_csv(path: Path) -> pd.DataFrame:
    attempts: list[Exception] = []
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return pd.read_csv(path, sep=None, engine="python", encoding=encoding)
        except (UnicodeDecodeError, pd.errors.ParserError) as exc:
            attempts.append(exc)
    raise attempts[-1]


def _validate_source(source: Path, allowed: set[str]) -> None:
    if not source.exists() or not source.is_file():
        raise DataLoadError("El archivo seleccionado no existe.")
    if source.suffix.lower() not in allowed:
        extensions = ", ".join(sorted(allowed))
        raise DataLoadError(f"Formato no admitido. Use: {extensions}.")


def _unique_column_names(columns: pd.Index) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for position, value in enumerate(columns, start=1):
        base = str(value).strip() or f"columna_{position}"
        count = seen.get(base, 0)
        seen[base] = count + 1
        result.append(base if count == 0 else f"{base}_{count + 1}")
    return result
