import pandas as pd
import pytest
from pathlib import Path
from finance_app.lead_intelligence import (
    load_and_enrich_leads,
    compute_lead_kpis,
    compute_product_performance,
    compute_regional_performance,
    compute_province_performance,
    extract_geo_from_phone,
    extract_intent_tags,
    calculate_lead_score,
)


def test_extract_geo_from_phone():
    prov, loc, reg = extract_geo_from_phone("2615 53-4316")
    assert prov == "Mendoza"
    assert "Mendoza" in loc
    assert reg == "Cuyo"

    prov_cba, loc_cba, reg_cba = extract_geo_from_phone("3512 38-3481")
    assert prov_cba == "Córdoba"
    assert "Córdoba" in loc_cba
    assert reg_cba == "Centro"

    prov_ba, loc_ba, reg_ba = extract_geo_from_phone("11 6512-1123")
    assert prov_ba == "Buenos Aires"
    assert reg_ba == "AMBA"


def test_extract_intent_tags():
    tags_davis = extract_intent_tags("Promo verano Estacion Davis - interesado")
    assert "Estación Meteorológica" in tags_davis

    tags_sentek = extract_intent_tags("Sonda de humedad y monitoreo de suelo")
    assert "Sonda de Humedad" in tags_sentek

    tags_jony = extract_intent_tags("Derivado a Jony para cierre")
    assert "Derivado / En Cierre" in tags_jony


def test_calculate_lead_score():
    row_hot = pd.Series({
        "Convertido_Derivado": 1,
        "Cant_Contactos": 4,
        "Intent_Tags": ["Sonda de Humedad", "Derivado / En Cierre"],
        "Linea_Producto": "Sentek",
        "Remarketing": 0,
        "Consulta_Detalle": "Meet con Celina"
    })
    score, estado = calculate_lead_score(row_hot)
    assert score >= 80
    assert "🏆 Ganado" in estado or "🔥 Hot" in estado


def test_load_and_enrich_leads_master_and_province_ranking():
    path = Path("Leeds orden.xlsx")
    if path.exists():
        sheets = load_and_enrich_leads(path)
        assert "Leeds" in sheets
        master = sheets["Leeds"]
        assert len(master) >= 288
        assert "Provincia" in master.columns
        assert "Region" in master.columns
        assert "Lead_Score" in master.columns
        assert "Estado_Lead" in master.columns

        # Check KPIs
        kpis = compute_lead_kpis(master)
        assert kpis.total_leads >= 288
        assert kpis.convertidos >= 27
        assert kpis.remarketing_total == 172

        # Check Province Ranking
        prov_df = compute_province_performance(master)
        assert not prov_df.empty
        assert "Ranking" in prov_df.columns
        assert "Buenos Aires" in prov_df["Provincia"].values
        assert "Córdoba" in prov_df["Provincia"].values
        assert "Mendoza" in prov_df["Provincia"].values
        assert "Santa Fe" in prov_df["Provincia"].values

        # Check Recontact and WhatsApp Enrichment
        assert "Recontacto_Prioridad" in master.columns
        assert "Accion_Sugerida" in master.columns
        assert "WhatsApp_Link" in master.columns
        assert kpis.recontacto_sugerido > 0


def test_build_whatsapp_link():
    from finance_app.lead_intelligence import build_whatsapp_link
    link = build_whatsapp_link("3512 38-3481", name="Juan Perez", product="Davis")
    assert "https://wa.me/5493512383481" in link
    assert "Juan%20Perez" in link
    assert "Davis" in link


def test_calculate_recontact_recommendation():
    from finance_app.lead_intelligence import calculate_recontact_recommendation
    
    # 1. Lead sin contacto por 15 días (≥14d) -> 🔴 Urgente
    row_urgent = pd.Series({
        "Convertido_Derivado": 0,
        "Lead_Score": 75,
        "Estado_Lead": "🔥 Hot (Alta Prioridad)",
        "Linea_Producto": "Sentek",
        "Consulta_Detalle": "Necesito cotización de sonda",
        "Cant_Contactos": 1,
        "Dias_Sin_Contacto": 15,
        "Remarketing": 0,
    })
    pri, action, motivo = calculate_recontact_recommendation(row_urgent)
    assert pri == "🔴 Urgente"
    assert "Sentek" in action
    assert "15 días" in motivo

    # 2. Lead contactado hoy (Dias_Sin_Contacto = 0) -> 🟢 Hablado Hoy (anti-saturación)
    row_today = pd.Series({
        "Convertido_Derivado": 0,
        "Lead_Score": 70,
        "Estado_Lead": "⚡ Warm (En Seguimiento)",
        "Linea_Producto": "Davis",
        "Consulta_Detalle": "WA Saliente: Hola, te enviamos propuesta",
        "Cant_Contactos": 2,
        "Dias_Sin_Contacto": 0,
        "Remarketing": 0,
    })
    pri_t, action_t, motivo_t = calculate_recontact_recommendation(row_today)
    assert pri_t == "🟢 Hablado Hoy"
    assert "espera" in action_t.lower() or "hoy" in action_t.lower()

    # 3. Lead contactado hace 4 días (1 a 13 días) -> 🟡 En Seguimiento
    row_follow = pd.Series({
        "Convertido_Derivado": 0,
        "Lead_Score": 60,
        "Estado_Lead": "⚡ Warm (En Seguimiento)",
        "Linea_Producto": "Davis",
        "Consulta_Detalle": "Consulta por Vantage Vue",
        "Cant_Contactos": 2,
        "Dias_Sin_Contacto": 4,
        "Remarketing": 0,
    })
    pri_f, action_f, motivo_f = calculate_recontact_recommendation(row_follow)
    assert pri_f == "🟡 En Seguimiento"
    assert "4 día" in motivo_f

    # 4. Lead Ganado/Derivado -> ⚪ No Requiere
    row_converted = pd.Series({
        "Convertido_Derivado": 1,
        "Lead_Score": 90,
        "Estado_Lead": "🏆 Ganado / Derivado",
        "Linea_Producto": "Davis",
    })
    pri_c, action_c, _ = calculate_recontact_recommendation(row_converted)
    assert pri_c == "⚪ No Requiere"


