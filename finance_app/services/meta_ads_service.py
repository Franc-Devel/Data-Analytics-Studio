"""
Nexo Analytics - Servicio de Integración con Meta Marketing API (Facebook & Instagram Ads)
Operación 100% de Solo Lectura (Read-Only) para ingestión de métricas, pauta y auditoría de campañas.
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
import os
import datetime
import json
import re
import urllib.request
import urllib.parse
from urllib.error import HTTPError, URLError
from typing import Optional, Dict, Any, List, Tuple
import pandas as pd
import numpy as np

from finance_app.config import get_config
from finance_app.logging_config import get_logger
from finance_app.commercial_analytics import (
    CommercialAnalyticsResult,
    CommercialKPISummary,
)

logger = get_logger("meta_ads_service")


@dataclass
class MetaCampaignInsight:
    """Métricas consolidadas de una campaña publicitaria en Meta Ads."""
    campaign_id: str
    campaign_name: str
    status: str
    objective: str
    product: str
    spend: float
    reach: int
    impressions: int
    clicks: int
    conversations: int
    cpl: float
    cpm: float
    cpc: float
    date_start: str
    date_stop: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def infer_product_from_campaign_name(campaign_name: str) -> str:
    """Identifica la línea comercial o producto a partir del nombre de la campaña en Meta Ads."""
    name_low = (campaign_name or "").lower().strip()
    
    if "sentek" in name_low:
        return "Sentek"
    elif "davis" in name_low or "clima" in name_low or "vantage" in name_low:
        return "Davis"
    elif "gsi" in name_low or "galcon ag" in name_low:
        return "GSI"
    elif "raphael" in name_low or "valvula" in name_low:
        return "Raphael"
    elif "helada" in name_low:
        return "Control de Heladas"
    elif "jardin" in name_low or "galcon gar" in name_low or "riego" in name_low:
        return "Jardinería"
    elif "regional" in name_low:
        return "Meta Ads Regional"
    elif "remarketing" in name_low or "retargeting" in name_low:
        return "Remarketing CRM"
    
    return "Meta Ads General"


def get_meta_ads_status() -> Dict[str, Any]:
    """Retorna el estado de configuración de la integración con Meta Ads."""
    cfg = get_config()
    meta_token = getattr(cfg, "meta_access_token", None) or os.getenv("META_ACCESS_TOKEN", "")
    meta_account = getattr(cfg, "meta_ad_account_id", None) or os.getenv("META_AD_ACCOUNT_ID", "")
    enabled = getattr(cfg, "meta_ads_enabled", True)
    api_version = getattr(cfg, "meta_api_version", "v21.0")

    has_token = bool(meta_token and meta_token.strip())
    has_account = bool(meta_account and meta_account.strip())
    
    account_clean = meta_account.strip() if has_account else ""
    if account_clean and not account_clean.startswith("act_"):
        account_clean = f"act_{account_clean}"

    return {
        "enabled": enabled,
        "configured": bool(has_token and has_account),
        "read_only": True,
        "has_token": has_token,
        "has_account": has_account,
        "ad_account_id": account_clean,
        "api_version": api_version,
    }


def fetch_meta_ads_insights(
    ad_account_id: Optional[str] = None,
    access_token: Optional[str] = None,
    date_preset: str = "maximum",
    api_version: Optional[str] = None,
    account_id: Optional[str] = None,
) -> Tuple[bool, Optional[str], List[MetaCampaignInsight]]:
    """
    Consulta la API de Meta Graph para obtener métricas agregadas por campaña.
    Garantía de Seguridad: Ejecuta exclusivamente peticiones HTTP GET (Solo Lectura).
    """
    cfg = get_config()
    meta_token = getattr(cfg, "meta_access_token", None) or os.getenv("META_ACCESS_TOKEN", "")
    meta_account = getattr(cfg, "meta_ad_account_id", None) or os.getenv("META_AD_ACCOUNT_ID", "")
    default_version = getattr(cfg, "meta_api_version", "v21.0")

    token = (access_token or meta_token).strip()
    acc_id = (ad_account_id or account_id or meta_account).strip()
    version = (api_version or default_version).strip() or "v21.0"

    if not token or not acc_id:
        return False, "Faltan credenciales: configure META_ACCESS_TOKEN y META_AD_ACCOUNT_ID en .env", []

    if not acc_id.startswith("act_"):
        acc_id = f"act_{acc_id}"

    # Parámetros estrictamente de LECTURA (GET)
    params = {
        "access_token": token,
        "level": "campaign",
        "fields": "campaign_id,campaign_name,objective,spend,reach,impressions,clicks,cpc,cpm,actions,cost_per_action_type,date_start,date_stop",
        "date_preset": date_preset,
        "limit": "100",
    }
    
    query_str = urllib.parse.urlencode(params)
    endpoint = f"https://graph.facebook.com/{version}/{acc_id}/insights?{query_str}"

    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) NexoAnalytics/1.0",
    }

    req = urllib.request.Request(endpoint, headers=headers, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        logger.error(f"Error HTTP {e.code} consultando Meta Marketing API: {err_body}")
        try:
            err_json = json.loads(err_body)
            msg = err_json.get("error", {}).get("message", f"HTTP {e.code}")
            user_msg = err_json.get("error", {}).get("error_user_msg")
            full_msg = f"{msg} ({user_msg})" if user_msg else msg
            return False, f"Error de Meta API ({e.code}): {full_msg}", []
        except Exception:
            return False, f"Error HTTP {e.code} en Meta Ads API: {err_body[:200]}", []
    except URLError as e:
        logger.error(f"Falla de red contactando a Meta Graph API: {e.reason}")
        return False, f"Falla de conexión con graph.facebook.com: {e.reason}", []
    except Exception as e:
        logger.error(f"Excepción inesperada en Meta Ads Service: {e}", exc_info=True)
        return False, f"Error inesperado: {str(e)}", []

    raw_items = data.get("data", [])
    results: List[MetaCampaignInsight] = []

    for item in raw_items:
        c_id = item.get("campaign_id", "")
        c_name = item.get("campaign_name", "Campaña sin nombre")
        spend = float(item.get("spend", 0.0))
        reach = int(item.get("reach", 0))
        impressions = int(item.get("impressions", 0))
        clicks = int(item.get("clicks", 0))
        cpc = float(item.get("cpc", 0.0))
        cpm = float(item.get("cpm", 0.0))
        objective = item.get("objective", "LEAD_GENERATION")
        d_start = item.get("date_start", "")
        d_stop = item.get("date_stop", "")

        # Extracción de conversaciones / leads desde actions
        conversations = 0
        actions = item.get("actions", [])
        if isinstance(actions, list):
            for act in actions:
                a_type = act.get("action_type", "")
                # Mensajería WhatsApp, Messenger o Leads Onsite
                if any(k in a_type for k in ("messaging_conversation_started", "onsite_conversion.lead_grouped", "lead", "contact")):
                    conversations += int(act.get("value", 0))

        # Si no hubo acción específica de mensajería, usar clics calificados como piso
        if conversations == 0 and clicks > 0 and "message" in c_name.lower():
            conversations = max(1, int(clicks * 0.4))

        cpl = (spend / conversations) if conversations > 0 else 0.0
        product = infer_product_from_campaign_name(c_name)

        results.append(MetaCampaignInsight(
            campaign_id=c_id,
            campaign_name=c_name,
            status="ACTIVE",
            objective=objective,
            product=product,
            spend=spend,
            reach=reach,
            impressions=impressions,
            clicks=clicks,
            conversations=conversations,
            cpl=cpl,
            cpm=cpm,
            cpc=cpc,
            date_start=d_start,
            date_stop=d_stop,
        ))

    logger.info(f"Meta Ads API: Obtenidas {len(results)} campañas ({sum(r.spend for r in results):,.2f} invertidos)")
    return True, None, results


def build_commercial_dataframe_from_meta(insights: List[MetaCampaignInsight]) -> pd.DataFrame:
    """Convierte los insights de Meta Ads en un DataFrame normalizado compatible con Nexo Analytics."""
    if not insights:
        return pd.DataFrame()

    now_month = datetime.datetime.now().strftime("%B")
    month_translation = {
        "January": "Enero", "February": "Febrero", "March": "Marzo",
        "April": "Abril", "May": "Mayo", "June": "Junio",
        "July": "Julio", "August": "Agosto", "September": "Septiembre",
        "October": "Octubre", "November": "Noviembre", "December": "Diciembre"
    }
    mes_es = month_translation.get(now_month, "Octubre")

    rows = []
    for r in insights:
        rows.append({
            "Mes": mes_es,
            "Campaña": r.campaign_name,
            "Producto": r.product,
            "Inversion_ARS": r.spend,
            "Alcance": r.reach,
            "Impresiones": r.impressions,
            "Clicks": r.clicks,
            "Conversaciones": r.conversations,
            "CPL_ARS": r.cpl,
            "CPM_ARS": r.cpm,
            "CPC_ARS": r.cpc,
            "Objetivo": r.objective,
            "Fuente": "Meta Marketing API (En vivo)",
            "Fecha_Inicio": r.date_start,
            "Fecha_Fin": r.date_stop,
        })

    return pd.DataFrame(rows)


def generate_demo_meta_campaigns() -> List[MetaCampaignInsight]:
    """Genera datos de demostración de campañas activas en Meta para previsualización."""
    return [
        MetaCampaignInsight(
            campaign_id="meta_101",
            campaign_name="[Meta Ads] Sentek Sondas de Humedad - Clientes Agro Campaña 2026",
            status="ACTIVE",
            objective="OUTCOME_LEADS",
            product="Sentek",
            spend=185400.0,
            reach=14200,
            impressions=28400,
            clicks=412,
            conversations=38,
            cpl=4878.95,
            cpm=13056.34,
            cpc=450.0,
            date_start="2026-09-01",
            date_stop="2026-10-04",
        ),
        MetaCampaignInsight(
            campaign_id="meta_102",
            campaign_name="[Meta Ads] Davis Vantage Pro 2 Estaciones Meteorológicas",
            status="ACTIVE",
            objective="MESSAGES",
            product="Davis",
            spend=142000.0,
            reach=11800,
            impressions=21500,
            clicks=320,
            conversations=29,
            cpl=4896.55,
            cpm=12033.90,
            cpc=443.75,
            date_start="2026-09-05",
            date_stop="2026-10-04",
        ),
        MetaCampaignInsight(
            campaign_id="meta_103",
            campaign_name="[Meta Ads] Raphael Válvulas de Alivio y Presión Hidráulica",
            status="ACTIVE",
            objective="OUTCOME_LEADS",
            product="Raphael",
            spend=95000.0,
            reach=7400,
            impressions=13900,
            clicks=195,
            conversations=16,
            cpl=5937.50,
            cpm=12837.84,
            cpc=487.18,
            date_start="2026-09-10",
            date_stop="2026-10-04",
        ),
        MetaCampaignInsight(
            campaign_id="meta_104",
            campaign_name="[Meta Ads] Galcon / Jardinería Controladores de Riego Residencial",
            status="ACTIVE",
            objective="MESSAGES",
            product="Jardinería",
            spend=68000.0,
            reach=9200,
            impressions=16400,
            clicks=210,
            conversations=22,
            cpl=3090.91,
            cpm=7391.30,
            cpc=323.81,
            date_start="2026-09-15",
            date_stop="2026-10-04",
        ),
        MetaCampaignInsight(
            campaign_id="meta_105",
            campaign_name="[Meta Ads] GSI Monitoreo de Granos y Silos",
            status="ACTIVE",
            objective="OUTCOME_LEADS",
            product="GSI",
            spend=82000.0,
            reach=6100,
            impressions=11200,
            clicks=160,
            conversations=14,
            cpl=5857.14,
            cpm=13442.62,
            cpc=512.50,
            date_start="2026-09-20",
            date_stop="2026-10-04",
        ),
    ]


def merge_meta_insights_into_commercial_result(
    current_comm: Any = None,
    insights: Any = None,
    base_result: Optional[CommercialAnalyticsResult] = None,
) -> Optional[CommercialAnalyticsResult]:
    """
    Integra los datos en vivo de Meta Ads dentro del resultado de análisis comercial (CommercialAnalyticsResult).
    Actualiza la inversión, alcance, conversaciones y recalcula los KPIs y resúmenes mensuales/productos.
    Acepta tanto (comm, insights) como (insights, comm) o base_result=comm.
    """
    if isinstance(current_comm, list) and (insights is None or isinstance(insights, CommercialAnalyticsResult)):
        insights, current_comm = current_comm, insights
    if base_result is not None:
        current_comm = base_result

    if not insights:
        return current_comm

    df_meta = build_commercial_dataframe_from_meta(insights)
    if df_meta.empty:
        return current_comm

    if current_comm is None:
        tot_inv = float(df_meta["Inversion_ARS"].sum())
        tot_alc = int(df_meta["Alcance"].sum())
        tot_conv = int(df_meta["Conversaciones"].sum())
        cpl_prom = (tot_inv / tot_conv) if tot_conv > 0 else 0.0
        cpm_prom = ((tot_inv / tot_alc) * 1000) if tot_alc > 0 else 0.0

        kpis = CommercialKPISummary(
            total_inversion_ars=tot_inv,
            total_alcance=tot_alc,
            total_conversaciones=tot_conv,
            cpl_promedio_ars=cpl_prom,
            cpm_promedio_ars=cpm_prom,
            total_oportunidades=0,
            presupuesto_cotizado_total=0.0,
            closers_activos=0,
        )
        return CommercialAnalyticsResult(
            kpis=kpis,
            df_spend=df_meta,
            df_monthly_summary=df_meta.groupby("Mes", as_index=False).agg(
                Inversion_Total=("Inversion_ARS", "sum"),
                Alcance_Total=("Alcance", "sum"),
                Conversaciones_Total=("Conversaciones", "sum"),
            ),
            df_product_summary=df_meta.groupby("Producto", as_index=False).agg(
                Inversion_Total=("Inversion_ARS", "sum"),
                Alcance_Total=("Alcance", "sum"),
                Conversaciones_Total=("Conversaciones", "sum"),
            ),
            df_opportunities=pd.DataFrame(),
            df_closers_summary=pd.DataFrame(),
        )

    existing_spend = current_comm.df_spend.copy() if current_comm.df_spend is not None else pd.DataFrame()
    if "Fuente" in existing_spend.columns:
        existing_spend = existing_spend[existing_spend["Fuente"] != "Meta Marketing API (En vivo)"]
    
    combined_spend = pd.concat([existing_spend, df_meta], ignore_index=True)

    tot_inv = float(combined_spend["Inversion_ARS"].sum())
    tot_alc = int(combined_spend["Alcance"].sum())
    tot_conv = int(combined_spend["Conversaciones"].sum())
    cpl_prom = (tot_inv / tot_conv) if tot_conv > 0 else 0.0
    cpm_prom = ((tot_inv / tot_alc) * 1000) if tot_alc > 0 else 0.0

    updated_kpis = CommercialKPISummary(
        total_inversion_ars=tot_inv,
        total_alcance=tot_alc,
        total_conversaciones=tot_conv,
        cpl_promedio_ars=cpl_prom,
        cpm_promedio_ars=cpm_prom,
        total_oportunidades=current_comm.kpis.total_oportunidades,
        presupuesto_cotizado_total=current_comm.kpis.presupuesto_cotizado_total,
        closers_activos=current_comm.kpis.closers_activos,
    )

    months = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
              'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    month_order = {m: i for i, m in enumerate(months)}

    df_monthly = (
        combined_spend.groupby('Mes', as_index=False)
        .agg(
            Inversion_Total=('Inversion_ARS', 'sum'),
            Alcance_Total=('Alcance', 'sum'),
            Conversaciones_Total=('Conversaciones', 'sum'),
        )
    )
    df_monthly['CPL_Promedio'] = np.where(
        df_monthly['Conversaciones_Total'] > 0,
        (df_monthly['Inversion_Total'] / df_monthly['Conversaciones_Total']).round(2),
        0.0
    )
    df_monthly['CPM_Promedio'] = np.where(
        df_monthly['Alcance_Total'] > 0,
        ((df_monthly['Inversion_Total'] / df_monthly['Alcance_Total']) * 1000).round(2),
        0.0
    )
    df_monthly['sort_key'] = df_monthly['Mes'].map(month_order).fillna(99)
    df_monthly = df_monthly.sort_values(by='sort_key').drop(columns=['sort_key']).reset_index(drop=True)

    df_product = (
        combined_spend.groupby('Producto', as_index=False)
        .agg(
            Inversion_Total=('Inversion_ARS', 'sum'),
            Alcance_Total=('Alcance', 'sum'),
            Conversaciones_Total=('Conversaciones', 'sum'),
        )
    )
    tot_p_inv = df_product['Inversion_Total'].sum()
    df_product['Pct_Inversion'] = ((df_product['Inversion_Total'] / tot_p_inv) * 100).round(1) if tot_p_inv > 0 else 0.0
    df_product['CPL_Promedio'] = np.where(
        df_product['Conversaciones_Total'] > 0,
        (df_product['Inversion_Total'] / df_product['Conversaciones_Total']).round(2),
        0.0
    )
    df_product = df_product.sort_values(by='Inversion_Total', ascending=False).reset_index(drop=True)

    return CommercialAnalyticsResult(
        kpis=updated_kpis,
        df_spend=combined_spend,
        df_monthly_summary=df_monthly,
        df_product_summary=df_product,
        df_opportunities=current_comm.df_opportunities,
        df_closers_summary=current_comm.df_closers_summary,
        df_social=current_comm.df_social,
        df_report_notes=current_comm.df_report_notes,
    )

