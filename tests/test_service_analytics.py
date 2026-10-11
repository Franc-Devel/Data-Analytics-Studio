import pandas as pd
import pytest
from finance_app.service_analytics import analyze_service_types


def test_service_types_analysis():
    df = pd.DataFrame([
        {"Año": 2026, "Mes": "febrero", "Tipo_Prestacion": "PRESTACION", "Venta": 291180000.0, "Costo": 66660000.0},
        {"Año": 2026, "Mes": "febrero", "Tipo_Prestacion": "INSUMO", "Venta": 149380000.0, "Costo": 34390000.0},
        {"Año": 2026, "Mes": "febrero", "Tipo_Prestacion": "LECHE", "Venta": 36990000.0, "Costo": 9270000.0},
        {"Año": 2026, "Mes": "febrero", "Tipo_Prestacion": "ALQUILER", "Venta": 36200000.0, "Costo": 12770000.0},
        {"Año": 2026, "Mes": "febrero", "Tipo_Prestacion": "EXPRESO", "Venta": 5330000.0, "Costo": 1330000.0},
        {"Año": 2025, "Mes": "febrero", "Tipo_Prestacion": "PRESTACION", "Venta": 182800000.0, "Costo": 42460000.0},
    ])

    res = analyze_service_types(df, selected_years=[2026], selected_months=["febrero"])

    assert len(res.kpis_por_tipo) == 5
    
    # Check Prestaciones
    prest = next(k for k in res.kpis_por_tipo if k.tipo == "Prestaciones")
    assert prest.venta == 291180000.0
    assert prest.costo == 66660000.0
    assert round(prest.pct_margen, 1) == 77.1

    # Check Insumos
    insumo = next(k for k in res.kpis_por_tipo if k.tipo == "Insumos")
    assert insumo.venta == 149380000.0
    assert insumo.costo == 34390000.0

    # Check historical evolution
    assert not res.historico_df.empty
    assert "2026-02" in res.historico_df["Periodo"].values
    assert "2025-02" in res.historico_df["Periodo"].values
