from io import BytesIO
from pathlib import Path
import pytest
from finance_app.lead_intelligence import load_and_enrich_leads
from finance_app.commercial_analytics import load_and_analyze_commercial_data


def test_load_leads_from_bytesio():
    path = Path("Leeds orden.xlsx")
    if path.exists():
        with open(path, "rb") as f:
            content = f.read()
        
        buffer = BytesIO(content)
        sheets = load_and_enrich_leads(buffer)
        assert "Leeds" in sheets
        assert len(sheets["Leeds"]) >= 288
        assert "Provincia" in sheets["Leeds"].columns
        assert "Lead_Score" in sheets["Leeds"].columns


def test_load_commercial_from_bytesio():
    path = Path("Comercial.xlsx")
    if path.exists():
        with open(path, "rb") as f:
            content = f.read()
            
        buffer = BytesIO(content)
        res = load_and_analyze_commercial_data(buffer)
        assert res is not None
        assert res.kpis.total_inversion_ars > 0
        assert not res.df_monthly_summary.empty
        assert not res.df_opportunities.empty
