from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import numpy as np


@dataclass
class ServiceTypeKPI:
    tipo: str
    venta: float
    costo: float
    margen: float
    pct_margen: float
    color: str


@dataclass
class ServiceAnalyticsResult:
    kpis_por_tipo: List[ServiceTypeKPI]
    resumen_tipos_df: pd.DataFrame
    historico_df: pd.DataFrame
    venta_total: float
    costo_total: float
    margen_total: float
    pct_margen_global: float


DEFAULT_SERVICE_COLORS = {
    "PRESTACION": "#ef4444",  # Rojo/Marrón
    "PRESTACIONES": "#ef4444",
    "INSUMO": "#3b82f6",     # Azul/Gris
    "INSUMOS": "#3b82f6",
    "LECHE": "#10b981",      # Verde
    "LECHES": "#10b981",
    "ALIMENTO": "#10b981",
    "ALIMENTOS": "#10b981",
    "ALQUILER": "#d97706",   # Ocre/Naranja
    "ALQUILERES": "#d97706",
    "EXPRESO": "#8b5cf6",    # Violeta/Púrpura
    "EXPRESOS": "#8b5cf6",
    "SERVICIO DE ENVIO": "#8b5cf6",
}


def analyze_service_types(
    df: pd.DataFrame,
    service_col: Optional[str] = None,
    venta_col: Optional[str] = None,
    costo_col: Optional[str] = None,
    year_col: Optional[str] = None,
    month_col: Optional[str] = None,
    selected_years: Optional[List[Any]] = None,
    selected_months: Optional[List[Any]] = None,
    currency_rate: float = 1.0,
) -> ServiceAnalyticsResult:
    """
    Analiza la valorización y rentabilidad por Tipo de Prestación (Prestaciones, Insumos, Leches, Alquileres, Expresos)
    y su evolución histórica.
    """
    filtered = df.copy()

    # Detectar columnas si no se pasan
    if not service_col or service_col not in filtered.columns:
        for c in ["Tipo_Prestacion", "TipoPrestacion", "tipo_prestacion", "Servicio", "Categoria", "Tipo"]:
            if c in filtered.columns:
                service_col = c
                break
        if not service_col or service_col not in filtered.columns:
            filtered["Tipo_Prestacion"] = "PRESTACION"
            service_col = "Tipo_Prestacion"

    if not venta_col or venta_col not in filtered.columns:
        for c in ["Venta", "Venta_OS", "ventas", "monto", "importe"]:
            if c in filtered.columns:
                venta_col = c
                break
        if not venta_col:
            filtered["Venta"] = 0.0
            venta_col = "Venta"

    if not costo_col or costo_col not in filtered.columns:
        for c in ["Costo", "costos", "costo_total", "egreso"]:
            if c in filtered.columns:
                costo_col = c
                break
        if not costo_col:
            filtered["Costo"] = filtered[venta_col] * 0.25
            costo_col = "Costo"

    if not year_col or year_col not in filtered.columns:
        for c in ["Año", "anio", "year", "ejercicio", "Año_Calculado"]:
            if c in filtered.columns:
                year_col = c
                break

    if not month_col or month_col not in filtered.columns:
        for c in ["Mes", "month", "mes_nombre", "periodo", "Mes_Calculado"]:
            if c in filtered.columns:
                month_col = c
                break

    # Filtrar por año
    if year_col and year_col in filtered.columns and selected_years:
        filtered = filtered[filtered[year_col].isin(selected_years)]

    # Filtrar por mes
    if month_col and month_col in filtered.columns and selected_months:
        from finance_app.patient_analytics import get_month_name
        month_series = filtered[month_col].apply(get_month_name)
        selected_norm = [get_month_name(m) for m in selected_months]
        filtered = filtered[month_series.isin(selected_norm)]

    # Ajuste de moneda
    rate = currency_rate if currency_rate > 0 else 1.0
    filtered["_V_Moneda"] = pd.to_numeric(filtered[venta_col], errors="coerce").fillna(0.0) / rate
    filtered["_C_Moneda"] = pd.to_numeric(filtered[costo_col], errors="coerce").fillna(0.0) / rate

    # Normalizar nombres de tipos de prestación
    def clean_type(val: Any) -> str:
        s = str(val).upper().strip()
        if "PRESTAC" in s or "INTERNAC" in s or "CUIDADO" in s:
            return "PRESTACION"
        elif "INSUM" in s or "DESCART" in s:
            return "INSUMO"
        elif "LECH" in s or "ALIMENT" in s or "NUTRIC" in s:
            return "LECHE"
        elif "ALQUIL" in s or "EQUIP" in s or "OXIGEN" in s:
            return "ALQUILER"
        elif "EXPRES" in s or "ENVIO" in s or "FLETE" in s or "LOGIST" in s:
            return "EXPRESO"
        return s

    filtered["_Tipo_Norm"] = filtered[service_col].apply(clean_type)

    # Agrupar por Tipo de Prestación
    grouped = (
        filtered.groupby("_Tipo_Norm", as_index=False)
        .agg({"_V_Moneda": "sum", "_C_Moneda": "sum"})
        .rename(columns={"_Tipo_Norm": "TipoPrestacion", "_V_Moneda": "Venta", "_C_Moneda": "Costo"})
    )

    grouped["Margen"] = grouped["Venta"] - grouped["Costo"]
    grouped["% Margen"] = np.where(grouped["Venta"] > 0, (grouped["Margen"] / grouped["Venta"]) * 100, 0.0)

    # Ordenar por % Margen desc para el gráfico horizontal
    grouped = grouped.sort_values(by="% Margen", ascending=False).reset_index(drop=True)

    # KPIs por tipo
    kpis_list: List[ServiceTypeKPI] = []
    # Asegurar orden visual estándar: Prestaciones, Insumos, Leches, Alquileres, Expresos
    standard_types = ["PRESTACION", "INSUMO", "LECHE", "ALQUILER", "EXPRESO"]
    
    for st_name in standard_types:
        row = grouped[grouped["TipoPrestacion"] == st_name]
        if not row.empty:
            v = float(row["Venta"].iloc[0])
            c = float(row["Costo"].iloc[0])
            m = float(row["Margen"].iloc[0])
            pct = float(row["% Margen"].iloc[0])
        else:
            v, c, m, pct = 0.0, 0.0, 0.0, 0.0
            
        color = DEFAULT_SERVICE_COLORS.get(st_name, "#64748b")
        display_name = (
            "Prestaciones" if st_name == "PRESTACION" else (
                "Insumos" if st_name == "INSUMO" else (
                    "Leches" if st_name == "LECHE" else (
                        "Alquileres" if st_name == "ALQUILER" else "Expresos"
                    )
                )
            )
        )
        kpis_list.append(ServiceTypeKPI(tipo=display_name, venta=v, costo=c, margen=m, pct_margen=pct, color=color))

    # Totales globales
    tot_v = grouped["Venta"].sum()
    tot_c = grouped["Costo"].sum()
    tot_m = tot_v - tot_c
    pct_m_global = (tot_m / tot_v * 100) if tot_v > 0 else 0.0

    # Evolución Histórica (por Periodo Año-Mes)
    # Extraer periodos disponibles de todo el dataset original (o filtrado si aplica)
    hist_source = df.copy()
    hist_source["_V"] = pd.to_numeric(hist_source[venta_col], errors="coerce").fillna(0.0) / rate
    hist_source["_C"] = pd.to_numeric(hist_source[costo_col], errors="coerce").fillna(0.0) / rate

    # Determinar columna de periodo
    if "Año" in hist_source.columns and "Mes" in hist_source.columns:
        from finance_app.patient_analytics import get_month_number
        hist_source["Mes_Num"] = hist_source["Mes"].apply(lambda m: f"{get_month_number(str(m)):02d}")
        hist_source["Periodo"] = hist_source["Año"].astype(str) + "-" + hist_source["Mes_Num"]
    elif "Fecha" in hist_source.columns:
        hist_source["Periodo"] = pd.to_datetime(hist_source["Fecha"], errors="coerce").dt.strftime("%Y-%m")
    else:
        hist_source["Periodo"] = "2026-02"

    hist_df = (
        hist_source.groupby("Periodo", as_index=False)
        .agg({"_V": "sum", "_C": "sum"})
        .rename(columns={"_V": "Venta OS Total", "_C": "Costo Total"})
    )
    hist_df["Margen Total"] = hist_df["Venta OS Total"] - hist_df["Costo Total"]
    hist_df["% Margen"] = np.where(
        hist_df["Venta OS Total"] > 0,
        (hist_df["Margen Total"] / hist_df["Venta OS Total"]) * 100,
        0.0
    )
    hist_df = hist_df.sort_values(by="Periodo").reset_index(drop=True)

    return ServiceAnalyticsResult(
        kpis_por_tipo=kpis_list,
        resumen_tipos_df=grouped,
        historico_df=hist_df,
        venta_total=tot_v,
        costo_total=tot_c,
        margen_total=tot_m,
        pct_margen_global=pct_m_global,
    )
