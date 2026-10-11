"""
Pruebas unitarias para el servicio de Meta Ads (Marketing API - Modo Solo Lectura)
y detección dinámica del proveedor LLM (Groq Cloud).
"""
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO
import json
import pandas as pd

from finance_app.services.meta_ads_service import (
    infer_product_from_campaign_name,
    get_meta_ads_status,
    generate_demo_meta_campaigns,
    build_commercial_dataframe_from_meta,
    merge_meta_insights_into_commercial_result,
    fetch_meta_ads_insights,
    MetaCampaignInsight,
)
from finance_app.config import AppConfig


def test_infer_product_from_campaign_name():
    assert infer_product_from_campaign_name("Sondas Sentek - Agro Región Centro") == "Sentek"
    assert infer_product_from_campaign_name("Estaciones Davis Vantage Pro 2026") == "Davis"
    assert infer_product_from_campaign_name("Monitoreo GSI Silos Cereal") == "GSI"
    assert infer_product_from_campaign_name("Válvulas Raphael Bermad Riego") == "Raphael"
    assert infer_product_from_campaign_name("Control Heladas Huertas") == "Control de Heladas"
    assert infer_product_from_campaign_name("Kits de Riego Jardín Urbano") == "Jardinería"
    assert infer_product_from_campaign_name("Campaña Institucional Brand Awareness") == "Meta Ads General"


def test_meta_ads_status():
    status_no_cfg = get_meta_ads_status()
    assert isinstance(status_no_cfg, dict)
    assert "configured" in status_no_cfg
    assert "read_only" in status_no_cfg
    assert status_no_cfg["read_only"] is True


def test_generate_demo_meta_campaigns():
    demos = generate_demo_meta_campaigns()
    assert len(demos) >= 4
    for item in demos:
        assert isinstance(item, MetaCampaignInsight)
        assert item.spend > 0
        assert item.impressions > 0
        assert item.product in ["Sentek", "Davis", "GSI", "Raphael", "Jardinería", "Control de Heladas", "Meta Ads General"]


def test_build_commercial_dataframe_from_meta():
    demos = generate_demo_meta_campaigns()
    df = build_commercial_dataframe_from_meta(demos)
    assert not df.empty
    assert "Producto" in df.columns
    assert "Campaña" in df.columns
    assert "Inversion_ARS" in df.columns
    assert "Conversaciones" in df.columns
    assert "CPL_ARS" in df.columns
    assert len(df) == len(demos)


def test_merge_meta_insights_into_commercial_result():
    demos = generate_demo_meta_campaigns()
    # Test passing (insights, base_result) or base_result=None
    result = merge_meta_insights_into_commercial_result(demos, base_result=None)
    assert result is not None
    assert not result.df_spend.empty
    assert result.kpis.total_inversion_ars > 0
    assert result.kpis.total_conversaciones > 0
    assert result.kpis.cpl_promedio_ars > 0

    # Test passing (comm, insights)
    result2 = merge_meta_insights_into_commercial_result(None, demos)
    assert result2 is not None
    assert result2.kpis.total_inversion_ars == result.kpis.total_inversion_ars


@patch("urllib.request.urlopen")
def test_fetch_meta_ads_insights_mock(mock_urlopen):
    payload = {
        "data": [
            {
                "campaign_id": "12345",
                "campaign_name": "Sentek Humedad Suelo 2026",
                "spend": "150000.50",
                "impressions": "45000",
                "clicks": "1200",
                "reach": "32000",
                "cpm": "3333.34",
                "cpc": "125.00",
                "actions": [
                    {"action_type": "onsite_conversion.messaging_conversation_started_7d", "value": "85"},
                    {"action_type": "link_click", "value": "1200"}
                ],
                "date_start": "2026-09-01",
                "date_stop": "2026-09-30",
            }
        ]
    }
    
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp
    mock_urlopen.return_value = mock_resp

    success, err, insights = fetch_meta_ads_insights(access_token="EAAX_test_token", account_id="act_123456789")
    assert success is True
    assert err is None
    assert len(insights) == 1
    assert insights[0].campaign_name == "Sentek Humedad Suelo 2026"
    assert insights[0].product == "Sentek"
    assert insights[0].spend == 150000.50
    assert insights[0].conversations == 85


def test_llm_provider_detection_groq():
    cfg = AppConfig(
        app_env="development",
        app_secret_key="a" * 32,
        app_encryption_key="b" * 32,
        llm_api_key="gsk_1234567890abcdef",
        llm_base_url="https://api.groq.com/openai/v1",
        llm_model="qwen/qwen3.8-27b",
    )
    assert "Groq Cloud" in cfg.llm_provider_name
