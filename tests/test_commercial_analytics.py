import pandas as pd
import pytest
from pathlib import Path
from finance_app.commercial_analytics import load_and_analyze_commercial_data


def test_load_and_analyze_commercial_data():
    path = Path("Comercial.xlsx")
    if path.exists():
        res = load_and_analyze_commercial_data(path)
        assert res is not None
        assert res.kpis.total_inversion_ars > 500000.0
        assert res.kpis.total_alcance > 50000
        assert res.kpis.total_conversaciones > 100
        assert res.kpis.cpl_promedio_ars > 0.0

        # Check monthly summary
        assert not res.df_monthly_summary.empty
        assert "Enero" in res.df_monthly_summary["Mes"].values
        assert "Febrero" in res.df_monthly_summary["Mes"].values

        # Check product summary
        assert not res.df_product_summary.empty
        assert "Sentek" in res.df_product_summary["Producto"].values
        assert "Davis" in res.df_product_summary["Producto"].values

        # Check opportunities
        assert not res.df_opportunities.empty
        assert len(res.df_opportunities) > 20
        assert "Cliente" in res.df_opportunities.columns
