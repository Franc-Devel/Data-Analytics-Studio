from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class QualityIssue:
    severity: str
    area: str
    detail: str
    affected: int


STATISTIC_HELP = {
    "Media": "Promedio. Resume el nivel general, pero es sensible a valores extremos.",
    "Mediana": "Valor central. Es preferible cuando hay importes atípicos o asimetría.",
    "Moda": "Valor más frecuente. Es útil en categorías y valores repetidos.",
    "Desvío": "Mide cuánto se dispersan los valores respecto de la media.",
    "Cuartiles": "Dividen los datos ordenados y ayudan a detectar dispersión y extremos.",
}


def profile_dataset(frame: pd.DataFrame) -> dict[str, Any]:
    total_cells = frame.shape[0] * frame.shape[1]
    missing = int(frame.isna().sum().sum())
    return {
        "filas": int(frame.shape[0]),
        "columnas": int(frame.shape[1]),
        "celdas_faltantes": missing,
        "porcentaje_completo": 100.0 if total_cells == 0 else (total_cells - missing) / total_cells * 100,
        "duplicados": int(frame.duplicated().sum()),
        "numericas": int(len(frame.select_dtypes(include="number").columns)),
        "fechas": int(len(frame.select_dtypes(include=["datetime", "datetimetz"]).columns)),
        "categoricas": int(len(frame.select_dtypes(exclude=["number", "datetime", "datetimetz"]).columns)),
    }


def quality_issues(frame: pd.DataFrame) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    duplicates = int(frame.duplicated().sum())
    if duplicates:
        issues.append(QualityIssue("Alta", "Duplicados", "Filas completamente repetidas", duplicates))

    for column in frame.columns:
        missing = int(frame[column].isna().sum())
        if missing:
            ratio = missing / max(len(frame), 1)
            severity = "Alta" if ratio >= 0.30 else "Media" if ratio >= 0.05 else "Baja"
            issues.append(QualityIssue(severity, str(column), f"Valores faltantes ({ratio:.1%})", missing))
        if len(frame) and frame[column].nunique(dropna=True) <= 1:
            issues.append(QualityIssue("Baja", str(column), "Columna constante o sin información variable", len(frame)))
        if frame[column].dtype == "object":
            stripped = frame[column].dropna().astype(str).str.strip()
            whitespace = int((stripped != frame[column].dropna().astype(str)).sum())
            if whitespace:
                issues.append(QualityIssue("Baja", str(column), "Textos con espacios al inicio o al final", whitespace))

    return issues or [QualityIssue("OK", "General", "No se detectaron problemas básicos", 0)]


def numeric_summary(frame: pd.DataFrame) -> pd.DataFrame:
    numeric = frame.select_dtypes(include="number")
    if numeric.empty:
        return pd.DataFrame()
    result = pd.DataFrame(index=numeric.columns)
    result["Cantidad"] = numeric.count()
    result["Faltantes"] = numeric.isna().sum()
    result["Media"] = numeric.mean()
    result["Mediana"] = numeric.median()
    modes = numeric.mode(dropna=True)
    result["Moda"] = modes.iloc[0] if not modes.empty else pd.NA
    result["Mínimo"] = numeric.min()
    result["Q1"] = numeric.quantile(0.25)
    result["Q3"] = numeric.quantile(0.75)
    result["Máximo"] = numeric.max()
    result["Desvío"] = numeric.std()
    return result.reset_index(names="Variable")


def recommend_chart(frame: pd.DataFrame, columns: list[str]) -> tuple[str, str]:
    valid = [column for column in columns if column in frame.columns]
    if not valid:
        return "Seleccione variables", "Elija una o dos columnas para obtener una recomendación contextual."
    if len(valid) > 2:
        return "Matriz o panel", "Con más de dos variables conviene separar vistas o usar una matriz de correlación para variables numéricas."

    numeric = [column for column in valid if pd.api.types.is_numeric_dtype(frame[column])]
    dates = [column for column in valid if pd.api.types.is_datetime64_any_dtype(frame[column])]
    categorical = [column for column in valid if column not in numeric and column not in dates]

    if len(valid) == 1 and numeric:
        return "Histograma y caja", "El histograma muestra la distribución; el diagrama de caja destaca mediana, dispersión y valores atípicos."
    if len(valid) == 1:
        return "Barras", "Compara frecuencias entre categorías. Evite tortas cuando hay muchas categorías o diferencias pequeñas."
    if dates and numeric:
        return "Línea temporal", "Muestra evolución, tendencia, estacionalidad y cambios de un indicador financiero en el tiempo."
    if len(numeric) == 2:
        return "Dispersión", "Permite evaluar relación, agrupamientos y valores atípicos entre dos magnitudes numéricas."
    if categorical and numeric:
        return "Barras o caja por categoría", "Barras compara agregados; cajas compara distribuciones sin ocultar dispersión y extremos."
    return "Barras agrupadas", "Sirve para comparar categorías relacionadas; limite la cantidad para conservar legibilidad."
