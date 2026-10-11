import pandas as pd
import pytest
from finance_app.concessionaire_analytics import (
    compute_concessionaire_statement,
    generate_waterfall_bridge_data,
    get_default_concessionaire_data,
)


def test_concessionaire_statement_computation():
    df = pd.DataFrame([
        {
            "Año": 2024,
            "Mes": "enero",
            "Tipo_Concepto": "Venta Modelo",
            "Concepto": "ONIX",
            "Sucursal": "Casa Central",
            "Venta": 1000000.0,
            "Margen_Contribucion": 60000.0,
            "Unidades": 2,
            "Monto": 1000000.0,
        },
        {
            "Año": 2024,
            "Mes": "enero",
            "Tipo_Concepto": "Otro Ingreso",
            "Concepto": "INTERES FINANCIACION",
            "Sucursal": "Casa Central",
            "Venta": 0.0,
            "Margen_Contribucion": 0.0,
            "Unidades": 0,
            "Monto": 20000.0,
        },
        {
            "Año": 2024,
            "Mes": "enero",
            "Tipo_Concepto": "Costo Directo",
            "Concepto": "GASTOS EN ENTREGA",
            "Sucursal": "Casa Central",
            "Venta": 0.0,
            "Margen_Contribucion": 0.0,
            "Unidades": 0,
            "Monto": 15000.0,
        },
        {
            "Año": 2024,
            "Mes": "enero",
            "Tipo_Concepto": "Costo Indirecto",
            "Concepto": "ALQUILERES",
            "Sucursal": "Casa Central",
            "Venta": 0.0,
            "Margen_Contribucion": 0.0,
            "Unidades": 0,
            "Monto": 10000.0,
        },
    ])

    kpis, m_mod, m_oi, m_cd, m_ci, m_res, m_inf = compute_concessionaire_statement(df, selected_year=2024)

    assert kpis.ventas_totales == 1000000.0
    assert kpis.contribucion_marginal == 60000.0
    assert kpis.pct_contribucion_marginal == 6.0
    assert kpis.unidades_vendidas == 2
    # Operativo = 60000 + 20000 - 15000 - 10000 = 55000
    assert kpis.resultado_operativo == 55000.0
    assert not m_mod.empty
    assert m_mod.iloc[0]["Modelo"] == "ONIX"
    assert not m_oi.empty
    assert not m_cd.empty
    assert not m_ci.empty
    assert not m_res.empty


def test_waterfall_bridge_data():
    df = get_default_concessionaire_data()
    if not df.empty:
        kpis, _, _, _, _, _, _ = compute_concessionaire_statement(df, selected_year=2024)
        bridge = generate_waterfall_bridge_data(kpis, 1000.0, 500.0, 300.0)
        assert "measures" in bridge
        assert "x" in bridge
        assert "y" in bridge
        assert len(bridge["x"]) == 7
