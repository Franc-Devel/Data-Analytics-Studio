import pandas as pd
import pytest
from finance_app.patient_analytics import (
    detect_columns,
    prepare_dataset,
    analyze_patients,
    classify_margin_health,
    get_month_name,
)


def test_detect_columns():
    df = pd.DataFrame({
        "Paciente": ["PAC-01", "PAC-02"],
        "Obra_Social": ["OSPIT", "OSPIN"],
        "Venta": [1000.0, 2000.0],
        "Costo": [250.0, 500.0],
        "Año": [2026, 2026],
        "Mes": ["febrero", "febrero"],
    })
    col_map = detect_columns(df)
    assert col_map["paciente"] == "Paciente"
    assert col_map["obra_social"] == "Obra_Social"
    assert col_map["venta"] == "Venta"
    assert col_map["costo"] == "Costo"
    assert col_map["año"] == "Año"
    assert col_map["mes"] == "Mes"


def test_classify_margin_health():
    assert classify_margin_health(75.0) == "SALUDABLE"
    assert classify_margin_health(50.0) == "ATENCIÓN"
    assert classify_margin_health(30.0) == "CRÍTICO"


def test_analyze_patients():
    df = pd.DataFrame({
        "Paciente": ["PAC-01", "PAC-02", "PAC-03", "PAC-04"],
        "Obra_Social": ["OSPIT", "OSPIN", "OSPIT", "M3F"],
        "Venta": [10000.0, 5000.0, 2000.0, 0.0],
        "Costo": [2500.0, 2000.0, 500.0, 0.0],
        "Año": [2026, 2026, 2026, 2026],
        "Mes": ["febrero", "febrero", "febrero", "febrero"],
    })
    col_map = detect_columns(df)
    prepared = prepare_dataset(df, col_map)
    kpis, p_df, os_df = analyze_patients(
        df=prepared,
        patient_col="Paciente",
        obra_social_col="Obra_Social",
        venta_col="Venta",
        costo_col="Costo",
        year_col="Año",
        month_col="Mes",
        selected_years=[2026],
        selected_months=["febrero"],
    )

    assert kpis.total_venta == 17000.0
    assert kpis.total_costo == 5000.0
    assert kpis.total_margen == 12000.0
    assert round(kpis.pct_margen, 1) == 70.6
    assert kpis.alerta_global == "SALUDABLE"
    assert kpis.pacientes_activos == 3
    assert kpis.pacientes_sin_consumo == 1
    assert len(p_df) == 4
    # Check Pareto sorting: PAC-01 should be first
    assert p_df.iloc[0]["Paciente"] == "PAC-01"
    assert p_df.iloc[0]["% Acumulado Pareto"] == (10000.0 / 17000.0) * 100
    # Obra Social aggregation
    assert len(os_df) == 3
