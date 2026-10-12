from __future__ import annotations

from finance_app.chart_theme import apply_chart_theme
apply_chart_theme()

import datetime
import os
from io import BytesIO
from pathlib import Path
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from finance_app.commercial_analytics import load_and_analyze_commercial_data, CommercialAnalyticsResult
from finance_app.lead_intelligence import (
    load_and_enrich_leads,
    compute_lead_kpis,
    compute_product_performance,
    compute_province_performance,
    compute_regional_performance,
    build_whatsapp_link,
    calculate_recontact_recommendation,
    generate_reactivation_message,
    get_daily_reactivation_batch,
    extract_meetings_and_technical_leads,
    compute_meeting_kpis,
    sanitize_display_name,
)
from finance_app.monthly_reports import available_months, build_monthly_report, report_to_excel
from finance_app.pdf_reports import generate_executive_pdf_report, generate_monthly_pdf_report
from finance_app.whatsapp_service import (
    sync_whatsapp_leads,
    simulate_incoming_whatsapp_message,
    WhatsAppMessage,
    WhatsAppSyncState,
    get_whatsapp_gateway_status,
    ensure_whatsapp_bridge_running,
    generate_qr_code_image,
    request_whatsapp_pairing_code,
    reset_whatsapp_session,
    start_background_auto_sync,
    is_background_sync_active,
    get_lead_chat_timeline,
    clean_phone_number,
    register_lead_contact_event,
    parse_whatsapp_export_file,
    import_and_sync_chat_history,
    get_whatsapp_history_stats,
    CONFIG_FILE,
)
from finance_app.config import get_config
from finance_app.logging_config import get_logger
from finance_app.backup_manager import create_backup
from finance_app.services.meta_ads_service import (
    fetch_meta_ads_insights,
    merge_meta_insights_into_commercial_result,
    generate_demo_meta_campaigns,
)
from finance_app.views import (
    render_login_form,
    render_user_sidebar_badge,
    render_user_header_badge,
    logout_user,
    init_auth_session,
    render_crm_view,
    render_admin_view,
    render_whatsapp_view,
    render_reports_view,
    render_campaigns_view,
    render_ai_reports_view,
)

logger = get_logger("dashboard")
_cfg = get_config()

# Validación obligatoria de seguridad en producción
try:
    _cfg.validate_production_readiness()
except RuntimeError as e:
    st.set_page_config(page_title="Security Alert", layout="centered")
    st.error(f"**ERROR CRÍTICO DE SEGURIDAD EN PRODUCCIÓN**:\n\n{e}")
    st.stop()

# Configuración de página
st.set_page_config(
    page_title="FAUVOR Analytics · Intelligence & Reporting Suite",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Cabeceras de Ciberseguridad del Navegador (CSP, Anti-Sniff, Anti-Clickjacking)
st.markdown("""
<head>
    <meta http-equiv="Content-Security-Policy" content="default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: https:; img-src 'self' data: https: blob:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' data: https://fonts.gstatic.com;">
    <meta http-equiv="X-Content-Type-Options" content="nosniff">
    <meta name="referrer" content="strict-origin-when-cross-origin">
</head>
""", unsafe_allow_html=True)

# Estilos CSS personalizados (Dark Glassmorphism de alta gama y Accesibilidad Visual Total)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    html {
        font-size: 20px !important; /* Escala base generosa para personas con visión reducida y pantallas estándar */
    }

    body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    .stApp {
        background: radial-gradient(circle at 85% 5%, #FFFAF2 0%, #F7F1E6 50%, #F7F1E6 100%);
        color: #2B211A;
    }

    /* Contenedor principal expandido para que quepa todo el aumento sin apretar columnas */
    .block-container {
        max-width: 96% !important;
        width: 96% !important;
        padding-top: 1.5rem !important;
        padding-bottom: 4rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }

    /* Columnas flexibles y estables para que no desborden */
    [data-testid="column"] {
        min-width: 0 !important;
    }

    [data-testid="stSidebar"] {
        background: #F7F1E6;
        border-right: 1px solid #B18450;
        min-width: 370px !important;
        width: 370px !important;
    }

    /* Navegación Sidebar: Mismo tamaño uniforme para todas las opciones, legible para personas con problemas de vista */
    [data-testid="stSidebar"] [data-testid="stRadio"] > label,
    [data-testid="stSidebar"] [data-testid="stRadio"] [data-testid="stWidgetLabel"] p {
        font-size: 18px !important;
        font-weight: 800 !important;
        color: #895522 !important;
        text-transform: uppercase !important;
        letter-spacing: 1.2px !important;
        margin-bottom: 14px !important;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] {
        gap: 8px !important;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label {
        min-height: 52px !important;
        display: flex !important;
        align-items: center !important;
        padding: 12px 18px !important;
        border-radius: 10px !important;
        transition: all 0.2s ease !important;
        margin: 3px 0 !important;
        cursor: pointer !important;
        border: 1px solid transparent !important;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:hover {
        background: rgba(169,111,53,0.2) !important;
        border-color: rgba(169,111,53,0.35) !important;
        transform: translateX(4px) !important;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label p,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label span,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label div {
        font-size: 19px !important;
        font-weight: 600 !important;
        color: #2B211A !important;
        line-height: 1.4 !important;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {
        background: linear-gradient(90deg, rgba(169,111,53,0.35) 0%, rgba(169,111,53,0.15) 100%) !important;
        border-left: 5px solid #B18450 !important;
        border-color: rgba(169,111,53,0.5) !important;
        box-shadow: 0 4px 14px rgba(74,42,24,0.16) !important;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) p,
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) span {
        font-weight: 800 !important;
        color: #2B211A !important;
        font-size: 19.5px !important;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] input[type="radio"] {
        transform: scale(1.4) !important;
        margin-right: 12px !important;
    }

    .hero-banner {
        padding: 24px 32px !important;
        border: 1px solid #B18450;
        border-radius: 16px;
        background: linear-gradient(135deg, #FFFAF2, #FFFAF2);
        backdrop-filter: blur(12px);
        margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(74,42,24,0.16);
    }

    .hero-banner h1 {
        margin: 0 0 8px 0;
        font-size: 36px !important;
        font-weight: 800;
        background: linear-gradient(90deg, #FFFAF2, #FFFAF2, #FFFAF2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .hero-banner p {
        margin: 0;
        color: #2B211A !important;
        font-size: 18px !important;
        line-height: 1.55 !important;
    }

    .kpi-card {
        padding: 22px 24px !important;
        border: 1px solid #B18450;
        border-radius: 14px;
        background: linear-gradient(145deg, #F7F1E6, #F7F1E6);
        min-height: 145px !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: space-between !important;
        transition: transform 0.2s ease, border-color 0.2s ease;
    }

    .kpi-card:hover {
        border-color: #B18450;
        transform: translateY(-2px);
    }

    .kpi-label {
        color: #895522;
        font-size: 16px !important;
        text-transform: uppercase;
        font-weight: 700;
        letter-spacing: 0.8px;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    .kpi-value {
        font-size: 40px !important;
        font-weight: 800;
        margin: 8px 0 6px 0 !important;
        color: #2B211A;
        line-height: 1.15 !important;
    }

    .kpi-detail {
        color: #47664F;
        font-size: 16px !important;
        font-weight: 600;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    .status-badge {
        display: inline-block;
        padding: 8px 16px;
        border-radius: 8px;
        font-size: 16px !important;
        font-weight: 600;
        background: rgba(16, 185, 129, 0.15);
        color: #47664F;
        border: 1px solid rgba(169,111,53,0.3);
    }

    /* Controles de Formularios, Selects y DatePickers a escala */
    div[data-testid="stWidgetLabel"] p,
    div[data-testid="stWidgetLabel"] label,
    label[data-testid="stWidgetLabel"] {
        font-size: 18.5px !important;
        font-weight: 700 !important;
        color: #2B211A !important;
        margin-bottom: 8px !important;
    }

    div[data-baseweb="input"] input,
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input,
    div[data-testid="stTextArea"] textarea {
        font-size: 18px !important;
        padding: 12px 16px !important;
        color: #2B211A !important;
    }

    div[data-baseweb="select"],
    div[data-baseweb="select"] * {
        font-size: 18px !important;
    }

    div[data-baseweb="select"] div[role="button"] {
        min-height: 52px !important;
        padding: 8px 16px !important;
    }

    div[data-testid="stDateInput"] input {
        font-size: 18px !important;
        padding: 12px 16px !important;
    }

    /* Radio buttons en el contenido principal */
    div[data-testid="stRadio"] div[role="radiogroup"] label {
        font-size: 18px !important;
        padding: 10px 14px !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] label p,
    div[data-testid="stRadio"] div[role="radiogroup"] label span {
        font-size: 18px !important;
        font-weight: 500 !important;
        color: #2B211A !important;
    }
    div[data-testid="stRadio"] div[role="radiogroup"] input[type="radio"] {
        transform: scale(1.35) !important;
    }

    /* Pestañas (st.tabs) ampliadas */
    button[data-baseweb="tab"] {
        font-size: 18.5px !important;
        font-weight: 700 !important;
        padding: 14px 26px !important;
    }
    button[data-baseweb="tab"] div {
        font-size: 18.5px !important;
        font-weight: 700 !important;
    }

    /* Botones ampliados */
    .stButton > button,
    button[kind="primary"],
    button[kind="secondary"],
    a[kind="primary"],
    a[kind="secondary"],
    [data-testid="stLinkButton"] a {
        font-size: 18px !important;
        font-weight: 700 !important;
        padding: 14px 28px !important;
        border-radius: 10px !important;
        min-height: 50px !important;
    }

    /* Tablas y DataFrames a escala */
    div[data-testid="stDataFrame"],
    div[data-testid="stDataFrame"] * {
        font-size: 17.5px !important;
    }
    div[data-testid="stDataFrame"] {
        border: 1px solid #B18450;
        border-radius: 14px;
        overflow: hidden;
        background: #F7F1E6;
    }

    /* Pills */
    button[data-testid="stBaseButton-pills"],
    div[data-testid="stPills"] button {
        font-size: 17px !important;
        padding: 10px 18px !important;
        font-weight: 600 !important;
    }

    /* Títulos generales */
    h1, .stMarkdown h1 { font-size: 36px !important; font-weight: 800; }
    h2, .stMarkdown h2 { font-size: 30px !important; font-weight: 700; }
    h3, .stMarkdown h3 { font-size: 25px !important; font-weight: 700; }
    h4, .stMarkdown h4 { font-size: 22px !important; font-weight: 700; }
    h5, .stMarkdown h5 { font-size: 19.5px !important; font-weight: 700; }
    p, span, div, li { font-size: 18px; line-height: 1.6; }
    .stCaption, small { font-size: 16px !important; color: #895522 !important; }

    .wa-chat-box {
        background: #F7F1E6;
        border: 1px solid #B18450;
        border-radius: 12px;
        padding: 18px;
        max-height: 400px;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        gap: 12px;
    }
    .wa-bubble-in {
        align-self: flex-start;
        background: #FFFAF2;
        color: #2B211A;
        padding: 12px 18px;
        border-radius: 12px 12px 12px 2px;
        max-width: 85%;
        font-size: 17.5px !important;
        border: 1px solid #B18450;
        box-shadow: 0 2px 5px rgba(74,42,24,0.16);
    }
    .wa-bubble-out {
        align-self: flex-end;
        background: #064e3b;
        color: #2B211A;
        padding: 12px 18px;
        border-radius: 12px 12px 2px 12px;
        max-width: 85%;
        font-size: 17.5px !important;
        border: 1px solid #059669;
        box-shadow: 0 2px 5px rgba(74,42,24,0.16);
    }
    .wa-bubble-note {
        align-self: center;
        background: rgba(169,111,53,0.15);
        color: #895522;
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 16px !important;
        border: 1px solid rgba(169,111,53,0.3);
        text-align: center;
        max-width: 90%;
    }
    .wa-time {
        font-size: 14.5px !important;
        color: #895522;
        margin-top: 4px;
        text-align: right;
    }
    .lead-profile-card {
        background: linear-gradient(145deg, #F7F1E6, #F7F1E6);
        border: 1px solid #B18450;
        border-radius: 14px;
        padding: 22px;
        margin-bottom: 18px;
    }

    div[data-testid="stPlotlyChart"], div[data-testid="stDataFrame"] {
        border: 1px solid #B18450;
        border-radius: 14px;
        overflow: hidden;
        background: #F7F1E6;
    }

    /* Regla universal para eliminar cualquier letra chica (< 17px) en estilos inline */
    [style*="font-size: 8px"], [style*="font-size:8px"],
    [style*="font-size: 9px"], [style*="font-size:9px"],
    [style*="font-size: 10px"], [style*="font-size:10px"],
    [style*="font-size: 10.5px"], [style*="font-size:10.5px"],
    [style*="font-size: 11px"], [style*="font-size:11px"],
    [style*="font-size: 11.5px"], [style*="font-size:11.5px"],
    [style*="font-size: 12px"], [style*="font-size:12px"],
    [style*="font-size: 12.5px"], [style*="font-size:12.5px"],
    [style*="font-size: 13px"], [style*="font-size:13px"],
    [style*="font-size: 13.5px"], [style*="font-size:13.5px"],
    [style*="font-size: 14px"], [style*="font-size:14px"],
    [style*="font-size: 14.5px"], [style*="font-size:14.5px"],
    [style*="font-size: 15px"], [style*="font-size:15px"],
    [style*="font-size: 15.5px"], [style*="font-size:15.5px"],
    [style*="font-size: 16px"], [style*="font-size:16px"],
    [style*="font-size: 16.5px"], [style*="font-size:16.5px"] {
        font-size: 17.5px !important;
    }

/* FAUVOR: ivory surfaces, bronze accents and readable controls. */
:root { color-scheme: light; --bs-body-bg:#F7F1E6; --bs-body-color:#2B211A; --bs-primary:#895522; --bs-primary-rgb:137,85,34; --bs-border-color:#D6C0A3; }
body { background-color:#F7F1E6; color:#2B211A; }
h1,h2,h3 { font-family:Georgia,'Times New Roman',serif; }
button,input,select,textarea { font-family:inherit; }
input,select,textarea,.form-control,.form-select { color:#2B211A; background-color:#FFFAF2; border-color:#D6C0A3; }
input::placeholder,textarea::placeholder { color:#786451; opacity:1; }
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible { outline:2px solid #895522; outline-offset:3px; }
.btn-primary,.btn-cyan,.btn-card-primary { background:#895522; border-color:#895522; color:#FFFAF2; }
.btn-primary:hover,.btn-cyan:hover { background:#4A2A18; border-color:#4A2A18; color:#FFFAF2; }
.btn-primary,.btn-success,.btn-danger,.btn-warning { --bs-btn-color:#FFFAF2; }
.text-white,.text-light { color:#2B211A!important; }
.bg-dark { background-color:#EFE5D6!important; }
.border-secondary { border-color:#D6C0A3!important; }
.text-celeste,.text-info,.text-primary { color:#895522!important; }
.swal2-popup { background:#FFFAF2!important; color:#2B211A!important; }
.swal2-confirm { background:#895522!important; color:#FFFAF2!important; }

[data-testid="stAppViewContainer"],[data-testid="stHeader"]{background:#F7F1E6;color:#2B211A}</style>
""", unsafe_allow_html=True)

# Control de Autenticación y Sesión de Usuario
init_auth_session()
if not render_login_form():
    st.stop()

current_user = st.session_state["current_user"]


def money(v: float) -> str:
    if v >= 1_000_000:
        return f"$ {v/1_000_000:.2f} M"
    return f"$ {v:,.0f}"


def render_kpi(label: str, value: str, detail: str, highlight_color: str = "#2B211A"):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value" style="color: {highlight_color}">{value}</div>
        <div class="kpi-detail">{detail}</div>
    </div>
    """, unsafe_allow_html=True)


# =========================================================================
# GESTIÓN Y CARGA DINÁMICA DE BASES DE DATOS
# =========================================================================
DEFAULT_LEADS_PATH = _cfg.resolve_leads_path()
DEFAULT_COMM_PATH = _cfg.resolve_commercial_path()


@st.cache_data(show_spinner=False, max_entries=4)
def _load_default_leads(path_text: str, mtime_ns: int, size: int):
    """Cache enriched CRM data until the source file actually changes."""
    del mtime_ns, size
    return load_and_enrich_leads(Path(path_text))


@st.cache_data(show_spinner=False, max_entries=2)
def _load_default_commercial(path_text: str, mtime_ns: int, size: int):
    del mtime_ns, size
    return load_and_analyze_commercial_data(Path(path_text))

# Iniciar sincronización autónoma en segundo plano (Worker Thread en tiempo real)
start_background_auto_sync(DEFAULT_LEADS_PATH, interval_seconds=3)

# Estado de sesión para datasets en memoria o subidos
if "leads_data" not in st.session_state:
    st.session_state["leads_data"] = None
    st.session_state["leads_source_name"] = f"{DEFAULT_LEADS_PATH.name} (Por defecto)"

if "comm_data" not in st.session_state:
    st.session_state["comm_data"] = None
    st.session_state["comm_source_name"] = f"{DEFAULT_COMM_PATH.name} (Por defecto)"


def get_active_data():
    """Retorna los datos activos (de sesión o disco con sincronización en tiempo real)."""
    # 1. Leeds Data
    if st.session_state["leads_source_name"] == "Leeds orden.xlsx (Por defecto)":
        if DEFAULT_LEADS_PATH.exists():
            stat = DEFAULT_LEADS_PATH.stat()
            st.session_state["leads_data"] = _load_default_leads(str(DEFAULT_LEADS_PATH.resolve()), stat.st_mtime_ns, stat.st_size)
        else:
            st.session_state["leads_data"] = {}
    elif st.session_state["leads_data"] is None:
        if DEFAULT_LEADS_PATH.exists():
            stat = DEFAULT_LEADS_PATH.stat()
            st.session_state["leads_data"] = _load_default_leads(str(DEFAULT_LEADS_PATH.resolve()), stat.st_mtime_ns, stat.st_size)
        else:
            st.session_state["leads_data"] = {}

    # 2. Commercial Data
    if st.session_state["comm_data"] is None and DEFAULT_COMM_PATH.exists():
        stat = DEFAULT_COMM_PATH.stat()
        st.session_state["comm_data"] = _load_default_commercial(str(DEFAULT_COMM_PATH.resolve()), stat.st_mtime_ns, stat.st_size)
        st.session_state["comm_source_name"] = "Comercial.xlsx (Por defecto)"

    return st.session_state["leads_data"], st.session_state["comm_data"]


# =========================================================================
# BARRA LATERAL (SIDEBAR) & CONTROL DE FUENTES
# =========================================================================
sheets, comm = get_active_data()
master = sheets.get("Leeds", pd.DataFrame()) if sheets else pd.DataFrame()

with st.sidebar:
    st.image(str(Path(__file__).parent / "assets" / "fauvor" / "symbol.png"), width=64)
    st.markdown("""
    <div style="padding: 6px 4px 12px 4px;">
        <div style="font-size: 26px; font-weight: 800; color: #2B211A; letter-spacing: -0.5px;">FAUVOR Analytics</div>
        <div style="font-size: 13.5px; font-weight: 700; color: #786451; letter-spacing: 1.2px; text-transform: uppercase; margin-top: 3px;">Commercial & CRM Suite</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)
    render_user_sidebar_badge()
    st.markdown("<div style='margin-bottom: 14px;'></div>", unsafe_allow_html=True)

    nav_options = [
        "Resumen ejecutivo",
        "Ficha 360° & Pipeline CRM",
        "Informes IA",
        "CRM & Leads (Explorador)",
        "Plan de Reactivación",
        "Reuniones & Fichas Técnicas",
        "Pauta & Conversión",
        "Campañas",
        "Geografía & Territorio",
        "Informes mensuales & PDF",
        "WhatsApp & Cola de Salida",
        "Calidad de datos",
        "Administración & Auditoría",
    ]

    page = st.radio(
        "Navegación",
        nav_options,
        index=0
    )

    st.divider()

    # -------------------------------------------------------------
    # PANEL DE COEQUIPER IA (AUDITORÍA Y PROCESAMIENTO DOCUMENTAL)
    # -------------------------------------------------------------
    with st.expander("📄 Coequiper IA: Cargar Documento", expanded=False):
        st.markdown("<small>Adjunte facturas, remitos o presupuestos para auditar con IA y sumar a la base de datos.</small>", unsafe_allow_html=True)
        quick_doc = st.file_uploader("Documento Comercial (.pdf, .jpg, .png, .xlsx)", type=["pdf", "jpg", "jpeg", "png", "webp", "xlsx", "csv"], key="quick_doc_uploader")
        if quick_doc is not None:
            if st.button("Auditar y Procesar con IA", width="stretch", key="btn_quick_audit"):
                with st.spinner("Procesando y auditando con IA..."):
                    from finance_app.services.ai_service import process_document_with_ai
                    doc_res = process_document_with_ai(quick_doc.getvalue(), quick_doc.name, quick_doc.type)
                    st.session_state["doc_analysis_result"] = doc_res
                    st.success(f"✓ '{quick_doc.name}' procesado.")
                    st.rerun()

    # -------------------------------------------------------------
    # PANEL DE CARGA Y ACTUALIZACIÓN DINÁMICA DE BASES DE DATOS
    # -------------------------------------------------------------
    with st.expander("Actualizar Bases de Datos", expanded=False):
        st.markdown("<small>Suba archivos Excel actualizados para refrescar todo el análisis en tiempo real.</small>", unsafe_allow_html=True)

        uploaded_leads = st.file_uploader("Base CRM / Leads (.xlsx)", type=["xlsx", "csv"], key="uploader_leads")
        if uploaded_leads is not None:
            if st.button("Aplicar Base de Leads", width="stretch"):
                content = uploaded_leads.getvalue()
                from finance_app.services.file_security import validate_uploaded_file
                is_valid, err_msg = validate_uploaded_file(content, uploaded_leads.name, allowed_types=(".xlsx", ".csv"))
                if not is_valid:
                    st.error(f"Archivo rechazado por seguridad: {err_msg}")
                else:
                    loaded_sheets = load_and_enrich_leads(BytesIO(content))
                    if loaded_sheets:
                        st.session_state["leads_data"] = loaded_sheets
                        st.session_state["leads_source_name"] = f"{uploaded_leads.name} (Subido)"
                        st.success(f"✓ Leads cargados: {len(loaded_sheets.get('Leeds', []))} registros.")
                        st.rerun()
                    else:
                        st.error("No se pudo procesar el archivo de leads.")

        uploaded_comm = st.file_uploader("Base Comercial / Pauta (.xlsx)", type=["xlsx"], key="uploader_comm")
        if uploaded_comm is not None:
            if st.button("Aplicar Base Comercial", width="stretch"):
                content_comm = uploaded_comm.getvalue()
                from finance_app.services.file_security import validate_uploaded_file
                is_valid, err_msg = validate_uploaded_file(content_comm, uploaded_comm.name, allowed_types=(".xlsx",))
                if not is_valid:
                    st.error(f"Archivo rechazado por seguridad: {err_msg}")
                else:
                    loaded_comm = load_and_analyze_commercial_data(BytesIO(content_comm))
                    if loaded_comm:
                        st.session_state["comm_data"] = loaded_comm
                        st.session_state["comm_source_name"] = f"{uploaded_comm.name} (Subido)"
                        st.success("✓ Base comercial procesada con éxito.")
                        st.rerun()
                    else:
                        st.error("No se pudo procesar el archivo comercial.")


        if st.button("Restablecer Bases Originales", width="stretch"):
            st.session_state["leads_data"] = None
            st.session_state["comm_data"] = None
            st.session_state["leads_source_name"] = f"{DEFAULT_LEADS_PATH.name} (Por defecto)"
            st.session_state["comm_source_name"] = f"{DEFAULT_COMM_PATH.name} (Por defecto)"
            st.rerun()

    # -------------------------------------------------------------
    # PANEL DE SINCRONIZACIÓN AUTOMÁTICA DE WHATSAPP
    # -------------------------------------------------------------
    with st.expander("WhatsApp Live Sync (Automático)", expanded=False):
        wa_state = WhatsAppSyncState()
        st.markdown("<div style='background: rgba(16, 185, 129, 0.15); border-left: 3px solid #47664F; padding: 8px 12px; border-radius: 6px; margin-bottom: 8px;'><small><b>Auto-Sync en Vivo: ACTIVO</b><br>El sistema escucha y guarda los mensajes de WhatsApp en tiempo real sin requerir acciones manuales.</small></div>", unsafe_allow_html=True)
        st.markdown(f"<small><b>Última actividad:</b> {wa_state.last_sync_iso[:19].replace('T', ' ')}</small>", unsafe_allow_html=True)
        st.markdown(f"<small><b>Leads WhatsApp:</b> {wa_state.total_synced_leads} registros</small>", unsafe_allow_html=True)

        if st.button("Forzar Verificación Inmediata", width="stretch"):
            res = sync_whatsapp_leads(DEFAULT_LEADS_PATH)
            st.session_state["leads_data"] = None
            if res.new_leads > 0 or res.updated_leads > 0:
                st.success(f"✓ {res.new_leads} nuevos | {res.updated_leads} actualizados.")
            st.rerun()

        st.markdown("---")
        st.markdown("<small><b>Probar Mensaje Entrante</b></small>", unsafe_allow_html=True)
        sim_name = st.text_input("Nombre contacto", "Productor Agro Test", key="sim_name")
        sim_phone = st.text_input("Teléfono", "3512 88-9900", key="sim_phone")
        sim_text = st.text_input("Mensaje", "Hola, necesito cotización por estación meteorológica Davis", key="sim_text")
        if st.button("Inyectar Mensaje WhatsApp", width="stretch"):
            sim_obj = simulate_incoming_whatsapp_message(sim_name, sim_phone, sim_text)
            res = sync_whatsapp_leads(DEFAULT_LEADS_PATH, extra_messages=[sim_obj])
            st.session_state["leads_data"] = None
            st.success("✓ Mensaje procesado: lead integrado al sistema.")
            st.rerun()

    # -------------------------------------------------------------
    # PANEL DE SINCRONIZACIÓN META ADS (MARKETING API - READ-ONLY)
    # -------------------------------------------------------------
    with st.expander("📡 Meta Ads Sync (Lectura API)", expanded=False):
        meta_tok = getattr(_cfg, "meta_access_token", None) or os.getenv("META_ACCESS_TOKEN", "")
        meta_acc = getattr(_cfg, "meta_ad_account_id", None) or os.getenv("META_AD_ACCOUNT_ID", "")
        if meta_tok and meta_acc:
            st.markdown(
                "<div style='background: rgba(16, 185, 129, 0.15); border-left: 3px solid #47664F; "
                "padding: 8px 12px; border-radius: 6px; margin-bottom: 8px;'>"
                "<small><b>API Meta: Configurada</b><br>Modo estricto Solo Lectura (ads_read)</small></div>",
                unsafe_allow_html=True,
            )
            if st.button("Sincronizar Campañas Meta", width="stretch", key="sb_sync_meta_ads"):
                with st.spinner("Consultando Meta Marketing API..."):
                    insights, err = fetch_meta_ads_insights(access_token=meta_tok, account_id=meta_acc)
                    if err:
                        st.error(f"Error Meta: {err}")
                    elif not insights:
                        st.warning("No se encontraron campañas activas en el período.")
                    else:
                        base_comm = st.session_state.get("comm_data") or comm
                        st.session_state["comm_data"] = merge_meta_insights_into_commercial_result(insights, base_comm)
                        st.session_state["comm_source_name"] = f"Meta Ads Live ({len(insights)} campañas)"
                        st.success(f"✓ {len(insights)} campañas integradas a la analítica comercial.")
                        st.rerun()
        else:
            st.markdown(
                "<div style='background: rgba(245, 158, 11, 0.15); border-left: 3px solid #9B732A; "
                "padding: 8px 12px; border-radius: 6px; margin-bottom: 8px;'>"
                "<small><b>Meta Token Pendiente</b><br>Configure META_ACCESS_TOKEN en .env o pruebe con el dataset simulador.</small></div>",
                unsafe_allow_html=True,
            )
            if st.button("Cargar Campañas Demo Meta", width="stretch", key="sb_demo_meta_ads"):
                demo_insights = generate_demo_meta_campaigns()
                base_comm = st.session_state.get("comm_data") or comm
                st.session_state["comm_data"] = merge_meta_insights_into_commercial_result(demo_insights, base_comm)
                st.session_state["comm_source_name"] = f"Meta Ads Demo ({len(demo_insights)} campañas)"
                st.success(f"✓ {len(demo_insights)} campañas demo cargadas en analítica.")
                st.rerun()

    st.divider()
    st.markdown(f"<div class='status-badge'>{st.session_state['leads_source_name']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='status-badge' style='margin-top:6px;'>{st.session_state['comm_source_name']}</div>", unsafe_allow_html=True)


# =========================================================================
# FILTRADO DE DATOS Y PREPARACIÓN
# =========================================================================
if master.empty:
    st.error("No hay base de datos de Leads disponible. Por favor cargue 'Leeds orden.xlsx'.")
    st.stop()

if comm is None:
    st.error("No hay base comercial disponible. Por favor cargue 'Comercial.xlsx'.")
    st.stop()

df_filtered = master.copy()
kpis = compute_lead_kpis(df_filtered)


# =========================================================================
# HEADER PRINCIPAL Y BOTÓN DE INFORME PDF COMPLETO
# =========================================================================
col_header_left, col_header_right = st.columns([3, 1.4])

with col_header_left:
    st.markdown(f"""
    <div class="hero-banner">
        <h1>{page}</h1>
        <p>Inteligencia de negocios y Data Science comercial · <b>{len(df_filtered):,}</b> leads seleccionados de <b>{len(master):,}</b> totales</p>
    </div>
    """, unsafe_allow_html=True)

with col_header_right:
    render_user_header_badge()
    # Generador de PDF en tiempo real
    # PDF generation is expensive; only build it on report-oriented pages.
    if page in ["Resumen ejecutivo", "Informes mensuales", "Informes mensuales & PDF"]:
        st.markdown("<div style='margin-top: 6px;'></div>", unsafe_allow_html=True)
        pdf_bytes_executive = generate_executive_pdf_report(sheets, comm)
        today_str = datetime.datetime.now().strftime("%Y%m%d")
        st.download_button(
            label="Descargar Informe PDF Completo",
            data=pdf_bytes_executive,
            file_name=f"Informe_Ejecutivo_Nexo_Analytics_{today_str}.pdf",
            mime="application/pdf",
            width="stretch",
            type="primary"
        )


if df_filtered.empty and page in ["Resumen ejecutivo", "CRM & Leads", "Geografía & Territorio"]:
    st.warning(f"Sin prospectos con los filtros actuales: Hay 0 leads seleccionados de {len(master):,} totales. Selecciona al menos una Línea de Producto o Región Geográfica en la barra lateral izquierda para habilitar las visualizaciones.")


# =========================================================================
# VISTA 1: RESUMEN EJECUTIVO
# =========================================================================
if page == "Resumen ejecutivo":
    # 5 Tarjetas de KPI principales
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_kpi("Leads Analizados", f"{kpis.total_leads:,}", f"{len(master):,} en base total", "#895522")
    with c2:
        render_kpi("Conversión CRM", f"{kpis.tasa_conversion_pct:.1f}%", f"{kpis.convertidos} ganados/derivados", "#47664F")
    with c3:
        render_kpi("Pauta Acumulada", money(comm.kpis.total_inversion_ars), "Inversión 7 meses", "#B18450")
    with c4:
        render_kpi("CPL Promedio", money(comm.kpis.cpl_promedio_ars), f"{comm.kpis.total_conversaciones:,} conversaciones", "#80634F")
    with c5:
        render_kpi("Pipeline Cotizado", money(comm.kpis.presupuesto_cotizado_total), f"{comm.kpis.total_oportunidades} cotizaciones", "#985A4E")

    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

    # Gráfico de Evolución Mensual y Resumen por Producto
    col_chart, col_prod = st.columns([1.6, 1])

    with col_chart:
        st.markdown("#### Evolución Mensual de Inversión y Conversaciones")
        df_m = comm.df_monthly_summary
        fig_evol = go.Figure()
        fig_evol.add_trace(go.Bar(
            x=df_m["Mes"],
            y=df_m["Inversion_Total"],
            name="Inversión ($ ARS)",
            marker_color="#895522",
            yaxis="y1"
        ))
        fig_evol.add_trace(go.Scatter(
            x=df_m["Mes"],
            y=df_m["Conversaciones_Total"],
            name="Conversaciones",
            mode="lines+markers",
            marker=dict(size=8, color="#47664F"),
            line=dict(width=3, color="#47664F"),
            yaxis="y2"
        ))
        fig_evol.update_layout(
            template="fauvor",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            height=340,
            margin=dict(l=20, r=20, t=20, b=20),
            yaxis=dict(title="Inversión ($ ARS)", showgrid=True, gridcolor="#EFE5D6"),
            yaxis2=dict(title="Conversaciones", overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_evol, width="stretch")

    with col_prod:
        st.markdown("#### Rendimiento por Producto")
        prod_table = compute_product_performance(df_filtered)
        st.dataframe(prod_table, width="stretch", hide_index=True, height=340)


# =========================================================================
# VISTA: FICHA 360° & PIPELINE CRM RELACIONAL (NÚCLEO EMPRESARIAL)
# =========================================================================
elif page == "Ficha 360° & Pipeline CRM":
    render_crm_view(current_user)


# =========================================================================
# VISTA: INFORMES IA · DISCRIMINACIÓN DE DEMANDA EN WHATSAPP
# =========================================================================
elif page == "Informes IA":
    render_ai_reports_view(master, comm, current_user)


# =========================================================================
# VISTA 2: CRM & LEADS (EXPLORADOR)
# =========================================================================
elif page in ["CRM & Leads (Explorador)", "CRM & Leads"]:
    # 1. 5 Tarjetas de KPI principales con indicadores de Recontacto
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_kpi("Leads en Vista", f"{len(df_filtered):,}", f"{len(master):,} en base total", "#895522")
    with c2:
        render_kpi("Conversión CRM", f"{kpis.tasa_conversion_pct:.1f}%", f"{kpis.convertidos} ganados/derivados", "#47664F")
    with c3:
        render_kpi("Hablados Hoy", f"{kpis.contactados_hoy:,}", "Contactados hoy (al día)", "#47664F")
    with c4:
        render_kpi("Urgentes ≥14d", f"{kpis.recontacto_urgente:,}", "Sin contacto por ≥2 semanas", "#985A4E")
    with c5:
        render_kpi("En Seguimiento", f"{kpis.en_seguimiento:,}", f"{kpis.leads_hot} Hot | {kpis.leads_warm} Warm", "#9B732A")

    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

    opt_all = f"Todos ({len(df_filtered)})"
    opt_urg = f"Urgentes ≥14d ({kpis.recontacto_urgente})"
    opt_today = f"Hablados Hoy ({kpis.contactados_hoy})"
    opt_follow = f"En Seguimiento ({kpis.en_seguimiento})"
    opt_hot = f"Hot & Warm ({kpis.leads_hot + kpis.leads_warm})"
    opt_won = f"Ganados ({kpis.convertidos})"
    opt_rem = f"Remarketing ({kpis.remarketing_total})"
    opt_cold = f"Fríos ({kpis.leads_cold + kpis.descartados})"

    view_opts = [opt_all, opt_urg, opt_today, opt_follow, opt_hot, opt_won, opt_rem, opt_cold]

    if "crm_view_pills" not in st.session_state or st.session_state["crm_view_pills"] not in view_opts:
        st.session_state["crm_view_pills"] = view_opts[0]

    def _select_crm_segment(segment_name: str):
        st.session_state["crm_view_pills"] = segment_name

    # Banner informativo y botón de acción rápida para Recontacto Urgente
    if kpis.recontacto_urgente > 0:
        is_viewing_urg = "Urgentes" in str(st.session_state.get("crm_view_pills", ""))
        col_banner_txt, col_banner_btn = st.columns([3.4, 1.2])
        with col_banner_txt:
            st.markdown(f"""
            <div style="background: rgba(236, 72, 153, 0.12); border-left: 4px solid #985A4E; padding: 12px 18px; border-radius: 10px; margin-bottom: 10px;">
                <span style="font-size: 16.5px; color: #fbcfe8; line-height: 1.5;">
                    <b>Oportunidades de Recontacto:</b> Hay <b>{kpis.recontacto_urgente} prospectos con más de 2 semanas sin contacto (URGENTES)</b>. Haz clic en <b>'Chatear'</b> en la tabla o presiona el botón para filtrarlos de inmediato.
                </span>
            </div>
            """, unsafe_allow_html=True)
        with col_banner_btn:
            if is_viewing_urg:
                st.button("Viendo Urgentes", disabled=True, width="stretch", key="btn_urg_active")
            else:
                st.button(
                    f"Filtrar {kpis.recontacto_urgente} Urgentes (≥14d)",
                    type="primary",
                    width="stretch",
                    key="btn_filter_urg",
                    on_click=_select_crm_segment,
                    args=(opt_urg,)
                )

    # 2. Selector de Filtros Rápidos (Pills / Segmentos) & Buscador en Vivo
    col_filters_left, col_search_right = st.columns([2.2, 1.2])

    with col_filters_left:
        selected_view_label = st.pills(
            "Filtrar lista por segmento:",
            view_opts,
            key="crm_view_pills"
        ) or view_opts[0]

    with col_search_right:
        crm_search = st.text_input(
            "Buscar contacto, teléfono o consulta:",
            placeholder="Ej: Roberto, 351, Sentek, Córdoba...",
            key="crm_search_input"
        )

    # Filtrar según la opción seleccionada
    if "Urgentes" in selected_view_label:
        df_crm_view = df_filtered[
            (df_filtered["Recontacto_Prioridad"].str.contains("Urgente", na=False)) &
            (df_filtered["Convertido_Derivado"] == 0)
        ].copy()
    elif "Hablados Hoy" in selected_view_label:
        df_crm_view = df_filtered[
            (df_filtered["Recontacto_Prioridad"].str.contains("Hoy", na=False)) |
            (df_filtered.get("Dias_Sin_Contacto", 999) == 0)
        ].copy()
    elif "En Seguimiento" in selected_view_label:
        df_crm_view = df_filtered[
            (df_filtered["Recontacto_Prioridad"].str.contains("Seguimiento", na=False)) |
            (df_filtered["Recontacto_Prioridad"].astype(str).str.contains("Media", na=False))
        ].copy()
    elif "Hot & Warm" in selected_view_label:
        df_crm_view = df_filtered[
            df_filtered["Estado_Lead"].str.contains("Hot|Warm", regex=True, na=False)
        ].copy()
    elif "Ganados" in selected_view_label:
        df_crm_view = df_filtered[df_filtered["Convertido_Derivado"] == 1].copy()
    elif "Remarketing" in selected_view_label:
        df_crm_view = df_filtered[df_filtered["Remarketing"] == 1].copy()
    elif "Fríos" in selected_view_label:
        df_crm_view = df_filtered[
            df_filtered["Estado_Lead"].str.contains("Cold|Descartado", regex=True, na=False)
        ].copy()
    else:
        df_crm_view = df_filtered.copy()

    # Búsqueda por texto libre
    if crm_search and crm_search.strip():
        q = crm_search.strip().lower()
        search_cols = [c for c in ["Contacto", "Telefono", "Provincia", "Localidad", "Linea_Producto", "Consulta_Detalle", "Accion_Sugerida", "Estado_Lead", "Ultimo_Contacto_Label"] if c in df_crm_view.columns]
        mask_search = df_crm_view[search_cols].astype(str).apply(lambda row: row.str.lower().str.contains(q, regex=False, na=False)).any(axis=1)
        df_crm_view = df_crm_view[mask_search]

    # 3. Tabla Interactiva de Leads
    display_cols = [
        c for c in [
            "ID_Lead", "Contacto", "Telefono", "WhatsApp_Link", "Linea_Producto",
            "Lead_Score", "Ultimo_Contacto_Label", "Recontacto_Prioridad", "Accion_Sugerida",
            "Estado_Lead", "Provincia", "Cant_Contactos", "Consulta_Detalle"
        ] if c in df_crm_view.columns
    ]

    col_config = {
        "WhatsApp_Link": st.column_config.LinkColumn(
            "WhatsApp",
            help="Haz clic para abrir el chat en WhatsApp Web o Móvil",
            display_text="Chatear",
            validate=r"^https://wa\.me/.*$",
        ),
        "Lead_Score": st.column_config.ProgressColumn(
            "Score",
            help="Probabilidad y calidad comercial (0 a 100 puntos)",
            format="%d pts",
            min_value=0,
            max_value=100,
        ),
        "ID_Lead": st.column_config.NumberColumn("ID", format="%d", width="small"),
        "Contacto": st.column_config.TextColumn("Nombre Contacto", width="medium"),
        "Telefono": st.column_config.TextColumn("Teléfono", width="medium"),
        "Linea_Producto": st.column_config.TextColumn("Producto", width="small"),
        "Ultimo_Contacto_Label": st.column_config.TextColumn("Último Contacto", help="Tiempo transcurrido desde la última interacción", width="medium"),
        "Recontacto_Prioridad": st.column_config.TextColumn("Prioridad Recontacto", width="small"),
        "Accion_Sugerida": st.column_config.TextColumn("Acción Recomendada", width="large"),
        "Estado_Lead": st.column_config.TextColumn("Estado CRM", width="medium"),
        "Provincia": st.column_config.TextColumn("Provincia", width="small"),
        "Cant_Contactos": st.column_config.NumberColumn("Toques", format="%d", width="small"),
        "Consulta_Detalle": st.column_config.TextColumn("Detalle Consulta", width="large"),
    }

    selected_lead = None

    if df_crm_view.empty:
        st.info("No se encontraron prospectos con el filtro o término de búsqueda seleccionado.")
    else:
        st.caption(f"Mostrando **{len(df_crm_view):,}** prospectos. *(Haz clic en **'Chatear'** para ir a WhatsApp, o selecciona una fila para ver la **Ficha 360° y Chat**)*")
        table_selection = st.dataframe(
            df_crm_view[display_cols],
            width="stretch",
            hide_index=True,
            height=400,
            on_select="rerun",
            selection_mode="single-row",
            column_config=col_config,
            key="crm_interactive_table"
        )

        selected_rows = table_selection.selection.rows if table_selection and hasattr(table_selection, "selection") else []
        if selected_rows:
            selected_idx = selected_rows[0]
            selected_lead = df_crm_view.iloc[selected_idx]

    # 4. Ficha 360° del Prospecto & Hub de Chat de WhatsApp
    st.markdown("---")
    st.markdown("### Ficha 360° del Prospecto & Centro de Interacción WhatsApp")

    col_lead_pick, col_lead_help = st.columns([1.5, 2])
    with col_lead_pick:
        lead_source_df = df_crm_view if not df_crm_view.empty else df_filtered
        lead_options = {
            f"#{r['ID_Lead']} - {r['Contacto']} ({r['Telefono']}) · {r['Linea_Producto']} · Score {r['Lead_Score']} · {r.get('Recontacto_Prioridad', '')}": idx
            for idx, r in lead_source_df.iterrows()
        }
        chosen_lead_key = st.selectbox(
            "Seleccione prospecto para inspeccionar o chatear:",
            options=list(lead_options.keys()),
            index=0 if not lead_options else 0,
            key="lead_picker_select"
        )
        if selected_lead is None and chosen_lead_key and lead_options:
            selected_lead = lead_source_df.loc[lead_options[chosen_lead_key]]

    if selected_lead is not None:
        lead_name = str(selected_lead.get("Contacto", "Cliente")).strip()
        lead_phone = str(selected_lead.get("Telefono", "")).strip()
        lead_prod = str(selected_lead.get("Linea_Producto", "Equipos")).strip()
        lead_score = int(selected_lead.get("Lead_Score", 30))
        lead_estado = str(selected_lead.get("Estado_Lead", "En Prospección"))
        lead_rec_pri = str(selected_lead.get("Recontacto_Prioridad", "Rutina"))
        lead_action = str(selected_lead.get("Accion_Sugerida", "Enviar seguimiento"))
        lead_motivo = str(selected_lead.get("Motivo_Recontacto", "Prospecto activo"))
        lead_wa_link = selected_lead.get("WhatsApp_Link", "") or build_whatsapp_link(lead_phone, lead_name, lead_prod)
        lead_prov = str(selected_lead.get("Provincia", "Argentina"))
        lead_loc = str(selected_lead.get("Localidad", "Sin especificar"))
        lead_reg = str(selected_lead.get("Region", "Centro"))
        lead_cont = int(selected_lead.get("Cant_Contactos", 1))
        lead_dias = int(selected_lead.get("Dias_En_Pipeline", 0))
        lead_dias_sin = int(selected_lead.get("Dias_Sin_Contacto", 999))
        lead_lbl_cont = str(selected_lead.get("Ultimo_Contacto_Label", "Sin contacto"))

        col_drawer_left, col_drawer_right = st.columns([1.2, 1.8])

        with col_drawer_left:
            diag_color_bg = "rgba(16, 185, 129, 0.12)" if lead_dias_sin == 0 else ("rgba(236, 72, 153, 0.12)" if "Urgente" in lead_rec_pri else "rgba(245, 158, 11, 0.12)")
            diag_color_border = "rgba(16, 185, 129, 0.4)" if lead_dias_sin == 0 else ("rgba(236, 72, 153, 0.4)" if "Urgente" in lead_rec_pri else "rgba(245, 158, 11, 0.4)")
            diag_color_title = "#47664F" if lead_dias_sin == 0 else ("#985A4E" if "Urgente" in lead_rec_pri else "#9B732A")

            drawer_card_html = (
                f'<div class="lead-profile-card">'
                f'<div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;">'
                f'<div>'
                f'<h3 style="margin: 0; font-size: 22px; font-weight: 700; color: #2B211A;">{lead_name}</h3>'
                f'<span style="color: #786451; font-size: 16px;">ID #{selected_lead.get("ID_Lead", "")} · {lead_phone}</span>'
                f'</div>'
                f'<span class="status-badge" style="background: rgba(99, 102, 241, 0.2); color: #B18450; border-color: rgba(99, 102, 241, 0.4);">{lead_prod}</span>'
                f'</div>'
                f'<div style="margin-bottom: 16px;">'
                f'<div style="display: flex; justify-content: space-between; font-size: 15px; margin-bottom: 6px;">'
                f'<span style="color: #786451; font-weight: 700;">LEAD SCORE</span>'
                f'<span style="color: #895522; font-weight: 800;">{lead_score} / 100 pts</span>'
                f'</div>'
                f'<div style="background: #EFE5D6; border-radius: 6px; height: 10px; overflow: hidden;">'
                f'<div style="background: linear-gradient(90deg, #895522, #B18450, #985A4E); width: {lead_score}%; height: 100%;"></div>'
                f'</div>'
                f'</div>'
                f'<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px;">'
                f'<div style="background: #F7F1E6; padding: 12px 14px; border-radius: 10px; border: 1px solid #EFE5D6;">'
                f'<span style="font-size: 14px; color: #786451; text-transform: uppercase; font-weight: 600;">Estado CRM</span><br>'
                f'<b style="font-size: 16.5px; color: #2B211A;">{lead_estado}</b>'
                f'</div>'
                f'<div style="background: #F7F1E6; padding: 12px 14px; border-radius: 10px; border: 1px solid #EFE5D6;">'
                f'<span style="font-size: 14px; color: #786451; text-transform: uppercase; font-weight: 600;">Último Contacto</span><br>'
                f'<b style="font-size: 16.5px; color: {"#47664F" if lead_dias_sin == 0 else ("#f87171" if lead_dias_sin >= 14 else "#fcd34d")};">{lead_lbl_cont}</b>'
                f'</div>'
                f'<div style="background: #F7F1E6; padding: 12px 14px; border-radius: 10px; border: 1px solid #EFE5D6;">'
                f'<span style="font-size: 14px; color: #786451; text-transform: uppercase; font-weight: 600;">Contactos</span><br>'
                f'<b style="font-size: 16.5px; color: #2B211A;">{lead_cont} interacción(es)</b>'
                f'</div>'
                f'<div style="background: #F7F1E6; padding: 12px 14px; border-radius: 10px; border: 1px solid #EFE5D6;">'
                f'<span style="font-size: 14px; color: #786451; text-transform: uppercase; font-weight: 600;">Días en Pipeline</span><br>'
                f'<b style="font-size: 16.5px; color: #2B211A;">{lead_dias} días</b>'
                f'</div>'
                f'</div>'
                f'<div style="background: {diag_color_bg}; border: 1px solid {diag_color_border}; border-radius: 12px; padding: 16px 18px; margin-bottom: 16px;">'
                f'<div style="font-size: 14.5px; font-weight: 700; color: {diag_color_title}; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">Diagnóstico de Recontacto: {lead_rec_pri}</div>'
                f'<div style="font-size: 16.5px; color: #fdf2f8; font-weight: 600; margin-bottom: 6px; line-height: 1.5;">{lead_action}</div>'
                f'<div style="font-size: 15px; color: #fbcfe8; line-height: 1.5;">{lead_motivo}</div>'
                f'</div>'
                f'</div>'
            )
            st.markdown(drawer_card_html, unsafe_allow_html=True)

            c_wa_btn1, c_wa_btn2 = st.columns(2)
            with c_wa_btn1:
                if lead_wa_link:
                    st.link_button(
                        label="Abrir WhatsApp",
                        url=lead_wa_link,
                        type="primary",
                        width="stretch"
                    )
            with c_wa_btn2:
                if st.button("Registrar Contacto", width="stretch", key=f"btn_quick_contact_{selected_lead.get('ID_Lead')}"):
                    register_lead_contact_event(DEFAULT_LEADS_PATH, selected_lead.get("ID_Lead"), "Contacto realizado por WhatsApp", "Seguimiento Manual")
                    st.session_state["leads_data"] = None
                    st.toast(f"✓ Contacto registrado para {lead_name}")
                    st.rerun()

        with col_drawer_right:
            if lead_dias_sin == 0 or "Hoy" in lead_rec_pri:
                st.markdown("""
                <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 10px; padding: 14px 18px; margin-bottom: 14px; display: flex; align-items: center; gap: 10px;">
                    <span style="color: #6ee7b7; font-size: 16px; font-weight: 600; line-height: 1.5;">
                        <b>Cliente Hablado Hoy:</b> Ya se registró contacto durante el día de hoy. Se sugiere esperar su respuesta antes de reiterar para no saturar al cliente.
                    </span>
                </div>
                """, unsafe_allow_html=True)
            elif lead_dias_sin >= 14 and "⚪" not in lead_rec_pri:
                st.markdown(f"""
                <div style="background: rgba(239, 68, 68, 0.15); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 10px; padding: 14px 18px; margin-bottom: 14px; display: flex; align-items: center; gap: 10px;">
                    <span style="color: #fca5a5; font-size: 16px; font-weight: 600; line-height: 1.5;">
                        <b>Recontacto Urgente (≥14 días):</b> Hace {lead_dias_sin if lead_dias_sin < 900 else 'más de 2 semanas'} sin interacción. Oportunidad ideal para reactivar con una propuesta o novedad.
                    </span>
                </div>
                """, unsafe_allow_html=True)

            tab_chat_history, tab_quick_replies, tab_notes = st.tabs([
                "Historial de Conversación & Chat",
                "Plantillas de Respuesta Rápida (1 Clic)",
                "Detalle Completo del Lead"
            ])

            with tab_chat_history:
                timeline = get_lead_chat_timeline(selected_lead)
                if not timeline:
                    st.info("No hay mensajes registrados para este contacto.")
                else:
                    chat_html = "<div class='wa-chat-box'>"
                    for item in timeline:
                        t_type = item.get("type", "")
                        sender = sanitize_display_name(item.get("sender", ""))
                        txt = item.get("text", "")
                        time_lbl = item.get("time", "")

                        if t_type == "whatsapp_out":
                            chat_html += (
                                f'<div class="wa-bubble-out">'
                                f'<b style="color: #6ee7b7;">{sender}</b><br>'
                                f'{txt}'
                                f'<div class="wa-time">{time_lbl} · Enviado por Empresa</div>'
                                f'</div>'
                            )
                        elif t_type in ["whatsapp_in", "whatsapp_live"]:
                            chat_html += (
                                f'<div class="wa-bubble-in">'
                                f'<b style="color: #895522;">{sender}</b><br>'
                                f'{txt}'
                                f'<div class="wa-time">{time_lbl} · Recibido Cliente</div>'
                                f'</div>'
                            )
                        else:
                            chat_html += (
                                f'<div class="wa-bubble-note">'
                                f'<b>{sender} ({time_lbl}):</b> {txt}'
                                f'</div>'
                            )
                    chat_html += "</div>"
                    st.markdown(chat_html, unsafe_allow_html=True)

                st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
                custom_msg = st.text_input(
                    "Escribir mensaje personalizado para enviar por WhatsApp:",
                    placeholder=f"Hola {lead_name}, te escribo de Abatech para retomar el contacto...",
                    key="custom_lead_msg_input"
                )
                if custom_msg.strip():
                    custom_url = build_whatsapp_link(lead_phone, lead_name, lead_prod, custom_text=custom_msg)
                    c_cmsg1, c_cmsg2 = st.columns(2)
                    with c_cmsg1:
                        st.link_button("Abrir y Enviar por WhatsApp", custom_url, type="primary", width="stretch")
                    with c_cmsg2:
                        if st.button("Guardar y Registrar Envío", width="stretch", key="btn_save_custom_outreach"):
                            register_lead_contact_event(DEFAULT_LEADS_PATH, selected_lead.get("ID_Lead"), custom_msg, "Mensaje Personalizado")
                            st.session_state["leads_data"] = None
                            st.toast("✓ Mensaje registrado en el historial del prospecto.")
                            st.rerun()

            with tab_quick_replies:
                st.markdown("##### Selecciona una plantilla para enviar con 1 Clic:")

                # Plantilla 0: Lanzamiento Davis Vantage Vue (Reactivación Comercial)
                msg_template_0 = (
                    f"Hola {lead_name}! ¿Cómo estás? Te escribimos de parte del equipo de Abatech.\n\n"
                    f"Como anteriormente nos habías consultado por estaciones meteorológicas Davis, queríamos contarte que ya disponemos de la nueva Vantage Vue, con condiciones especiales de lanzamiento y stock para entrega inmediata.\n\n"
                    f"Si todavía estás evaluando incorporar o renovar tecnología en tu campo, consultanos hoy por la propuesta y valor promocional."
                )
                st.markdown(f"""
                <div style="background: rgba(16, 185, 129, 0.12); padding: 16px 18px; border-radius: 10px; margin-bottom: 10px; border: 1px solid rgba(16, 185, 129, 0.4); font-size: 16.5px;">
                    <b style="color: #47664F; font-size: 17px;">1. Lanzamiento Davis Vantage Vue (Reactivación & Novedad):</b><br>
                    <span style="color: #ecfdf5; white-space: pre-line; line-height: 1.6;">"{msg_template_0}"</span>
                </div>
                """, unsafe_allow_html=True)
                url_t0 = build_whatsapp_link(lead_phone, lead_name, lead_prod, custom_text=msg_template_0)
                c_tpl0_a, c_tpl0_b = st.columns([1.5, 1.2])
                with c_tpl0_a:
                    st.link_button("Abrir en WhatsApp (Vantage Vue)", url_t0, type="primary", width="stretch")
                with c_tpl0_b:
                    if st.button("Marcar como Enviado", width="stretch", key="btn_reg_tpl_vantage"):
                        register_lead_contact_event(DEFAULT_LEADS_PATH, selected_lead.get("ID_Lead"), msg_template_0, "Lanzamiento Vantage Vue")
                        st.session_state["leads_data"] = None
                        st.toast("✓ Plantilla Vantage Vue registrada como enviada.")
                        st.rerun()

                st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)

                # Plantilla 1: Seguimiento / Recontacto de Cotización
                msg_template_1 = f"Hola {lead_name}! ¿Cómo estás? Te contacto de parte del equipo de Abatech para retomar la conversación sobre {lead_prod}. ¿Pudiste revisar los números o necesitás que ajustemos la propuesta a las necesidades actuales de tu campo?"
                st.markdown(f"""
                <div style="background: #EFE5D6; padding: 16px 18px; border-radius: 10px; margin-bottom: 10px; border: 1px solid #334155; font-size: 16.5px;">
                    <b style="color: #895522; font-size: 17px;">2. Recontacto y Seguimiento de Cotización:</b><br>
                    <span style="color: #2B211A; line-height: 1.6;">"{msg_template_1}"</span>
                </div>
                """, unsafe_allow_html=True)
                url_t1 = build_whatsapp_link(lead_phone, lead_name, lead_prod, custom_text=msg_template_1)
                c_tpl1_a, c_tpl1_b = st.columns([1.5, 1.2])
                with c_tpl1_a:
                    st.link_button("Abrir en WhatsApp (Cotización)", url_t1, width="stretch")
                with c_tpl1_b:
                    if st.button("Marcar como Enviado", width="stretch", key="btn_reg_tpl_cotiz"):
                        register_lead_contact_event(DEFAULT_LEADS_PATH, selected_lead.get("ID_Lead"), msg_template_1, "Seguimiento Cotización")
                        st.session_state["leads_data"] = None
                        st.toast("✓ Plantilla de cotización registrada como enviada.")
                        st.rerun()

                st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)

                # Plantilla 2: Ficha Técnica y Asesoramiento
                msg_template_2 = f"Hola {lead_name}, un gusto saludarte nuevamente. Te escribo de Abatech para acercarte la ficha técnica y especificaciones de {lead_prod}. ¿Te gustaría que coordinemos una breve llamada de 10 minutos con nuestro especialista técnico para evaluar la instalación y despejar dudas?"
                st.markdown(f"""
                <div style="background: #EFE5D6; padding: 16px 18px; border-radius: 10px; margin-bottom: 10px; border: 1px solid #334155; font-size: 16.5px;">
                    <b style="color: #47664F; font-size: 17px;">3. Envío de Ficha Técnica & Asesoramiento:</b><br>
                    <span style="color: #2B211A; line-height: 1.6;">"{msg_template_2}"</span>
                </div>
                """, unsafe_allow_html=True)
                url_t2 = build_whatsapp_link(lead_phone, lead_name, lead_prod, custom_text=msg_template_2)
                c_tpl2_a, c_tpl2_b = st.columns([1.5, 1.2])
                with c_tpl2_a:
                    st.link_button("Abrir en WhatsApp (Técnica)", url_t2, width="stretch")
                with c_tpl2_b:
                    if st.button("Marcar como Enviado", width="stretch", key="btn_reg_tpl_tech"):
                        register_lead_contact_event(DEFAULT_LEADS_PATH, selected_lead.get("ID_Lead"), msg_template_2, "Ficha Técnica")
                        st.session_state["leads_data"] = None
                        st.toast("✓ Plantilla técnica registrada como enviada.")
                        st.rerun()

                st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)

                # Plantilla 3: Reactivación Comercial / Bonificación Especial
                msg_template_3 = f"Hola {lead_name}! ¿Cómo estás? Te escribo del equipo de Abatech. Retomamos contacto porque tenemos vigentes condiciones comerciales especiales y bonificaciones para {lead_prod}. ¿Seguís interesado en incorporar esta tecnología en esta campaña? Quedamos a disposición para pasarte los detalles."
                st.markdown(f"""
                <div style="background: #EFE5D6; padding: 16px 18px; border-radius: 10px; margin-bottom: 10px; border: 1px solid #334155; font-size: 16.5px;">
                    <b style="color: #9B732A; font-size: 17px;">4. Reactivación Comercial / Bonificación Especial:</b><br>
                    <span style="color: #2B211A; line-height: 1.6;">"{msg_template_3}"</span>
                </div>
                """, unsafe_allow_html=True)
                url_t3 = build_whatsapp_link(lead_phone, lead_name, lead_prod, custom_text=msg_template_3)
                c_tpl3_a, c_tpl3_b = st.columns([1.5, 1.2])
                with c_tpl3_a:
                    st.link_button("Abrir en WhatsApp (Reactivación)", url_t3, width="stretch")
                with c_tpl3_b:
                    if st.button("Marcar como Enviado", width="stretch", key="btn_reg_tpl_react"):
                        register_lead_contact_event(DEFAULT_LEADS_PATH, selected_lead.get("ID_Lead"), msg_template_3, "Reactivación Comercial")
                        st.session_state["leads_data"] = None
                        st.toast("✓ Plantilla de reactivación registrada como enviada.")
                        st.rerun()

            with tab_notes:
                st.markdown(f"**Detalle Completo de la Consulta:**")
                st.info(selected_lead.get("Consulta_Detalle", "Sin detalle registrado"))
                st.markdown(f"**Localidad:** {lead_loc} | **Provincia:** {lead_prov} | **Región:** {lead_reg}")
                st.markdown(f"**Tags de Intención:** `{', '.join(selected_lead.get('Intent_Tags', ['General']))}`")
                st.markdown(f"**Primer Contacto:** `{selected_lead.get('Fecha_Primer_Contacto', 'N/D')}` | **Último Contacto:** `{selected_lead.get('Fecha_Ultimo_Contacto', 'N/D')}`")


# =========================================================================
# VISTA: PLAN DE REACTIVACIÓN COMERCIAL & ANTI-BLOQUEO
# =========================================================================
elif page == "Plan de Reactivación":
    # 1. Tarjetas de KPI principales de Reactivación
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi("Fríos para Reactivar", f"{kpis.total_frios_reactivables:,}", "Sin contacto por ≥14 días", "#895522")
    with c2:
        render_kpi("Reactivados Exitosos", f"{kpis.leads_reactivados:,}", "Clientes que respondieron", "#47664F")
    with c3:
        render_kpi("Tasa de Reactivación", f"{kpis.tasa_reactivacion_pct:.1f}%", "Efectividad sobre base inactiva", "#80634F")
    with c4:
        render_kpi("Lote Sugerido Hoy", f"{kpis.lote_diario_count} prospectos", "Límite seguro anti-bloqueo", "#9B732A")

    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

    # Banner del Protocolo Anti-Bloqueo de Meta
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(30, 27, 75, 0.7), rgba(15, 23, 42, 0.9)); border: 1px solid #4338ca; border-radius: 14px; padding: 18px 22px; margin-bottom: 20px;">
        <div style="margin-bottom: 8px;">
            <b style="color: #a5b4fc; font-size: 18px;">Protocolo Empresarial Anti-Bloqueo de WhatsApp:</b>
        </div>
        <div style="color: #2B211A; font-size: 16.5px; line-height: 1.6;">
            • <b>Spintax y Mensajes Únicos:</b> El motor genera variantes aleatorias en cada envío para evitar patrones repetitivos.<br>
            • <b>Cadencia Controlada:</b> Recomendamos reactivar entre <b>15 y 20 contactos por día</b> (lote diario sugerido) para proteger la reputación de la línea.<br>
            • <b>Detección Automática de Respuestas:</b> Cuando un cliente responda, el sistema lo moverá automáticamente a <i>'Hablados Hoy'</i> y <i>'En Seguimiento'</i>.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 2. Selección de Lote Diario y Filtros
    daily_batch = get_daily_reactivation_batch(df_filtered, batch_size=20)

    if daily_batch.empty:
        st.success("Excelente trabajo. No hay prospectos fríos pendientes de reactivación con los filtros actuales.")
    else:
        col_batch_list, col_batch_studio = st.columns([1.3, 1.7])

        with col_batch_list:
            st.markdown(f"#### Lote Prioritario del Día ({len(daily_batch)} prospectos)")
            st.caption("Ordenados por mayor Lead Score y tiempo sin contacto para maximizar conversión.")

            batch_options = {
                f"#{r['ID_Lead']} - {r['Contacto']} ({r['Telefono']}) · {r['Linea_Producto']} · Score {r['Lead_Score']}": idx
                for idx, r in daily_batch.iterrows()
            }

            chosen_batch_key = st.selectbox(
                "Selecciona un prospecto para redactar mensaje:",
                options=list(batch_options.keys()),
                index=0,
                key="react_batch_select"
            )
            react_lead = daily_batch.loc[batch_options[chosen_batch_key]]

            # Tabla compacta del lote
            cols_to_show = [c for c in ["ID_Lead", "Contacto", "Telefono", "Linea_Producto", "Lead_Score", "Dias_Sin_Contacto", "Provincia"] if c in daily_batch.columns]
            st.dataframe(
                daily_batch[cols_to_show],
                width="stretch",
                hide_index=True,
                height=340,
                column_config={
                    "ID_Lead": st.column_config.NumberColumn("ID", format="%d", width="small"),
                    "Contacto": st.column_config.TextColumn("Contacto", width="medium"),
                    "Telefono": st.column_config.TextColumn("Teléfono", width="medium"),
                    "Linea_Producto": st.column_config.TextColumn("Producto", width="small"),
                    "Lead_Score": st.column_config.ProgressColumn("Score", format="%d pts", min_value=0, max_value=100),
                    "Dias_Sin_Contacto": st.column_config.NumberColumn("Días Inactivo", format="%d d"),
                }
            )

        with col_batch_studio:
            st.markdown("#### Estudio de Mensajes con Spintax Anti-Bloqueo")

            r_name = str(react_lead.get("Contacto", "Cliente")).strip()
            r_phone = str(react_lead.get("Telefono", "")).strip()
            r_prod = str(react_lead.get("Linea_Producto", "Equipos")).strip()
            r_score = int(react_lead.get("Lead_Score", 30))
            r_dias = int(react_lead.get("Dias_Sin_Contacto", 999))
            r_loc = str(react_lead.get("Localidad", "Sin Localidad"))
            r_prov = str(react_lead.get("Provincia", "Argentina"))

            st.markdown(f"""
            <div style="background: #131b2e; border: 1px solid #26334d; border-radius: 12px; padding: 16px 20px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <b style="color: #2B211A; font-size: 19px;">{r_name}</b> <span style="color: #786451; font-size: 16px;">(ID #{react_lead.get('ID_Lead')} · {r_phone})</span><br>
                    <span style="color: #B18450; font-size: 16px; font-weight: 500;">{r_prod} · {r_prov} · {r_dias} días sin contacto</span>
                </div>
                <div style="text-align: right;">
                    <span style="color: #895522; font-weight: 800; font-size: 19px;">Score: {r_score} pts</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Selector de Estrategia Comercial
            strat_choice = st.radio(
                "Selecciona la Estrategia Comercial de Reactivación:",
                [
                    "Pregunta Corta (Curiosidad sin fricción)",
                    "Novedad Técnica / Caso de Éxito Zonal",
                    "Actualización de Cotización & Financiación",
                    "Cierre por Descarte (Confirmar continuidad)",
                ],
                index=0,
                key="react_strat_radio"
            )

            strat_key_map = {
                "Pregunta Corta (Curiosidad sin fricción)": "short",
                "Novedad Técnica / Caso de Éxito Zonal": "news",
                "Actualización de Cotización & Financiación": "budget",
                "Cierre por Descarte (Confirmar continuidad)": "discard",
            }
            strat_key = strat_key_map[strat_choice]

            # Semilla Spintax aleatoria para regeneración instantánea
            if "react_seed" not in st.session_state:
                import random
                st.session_state["react_seed"] = random.randint(1, 100000)

            c_regen1, c_regen2 = st.columns([2.5, 1])
            with c_regen2:
                if st.button("Nueva Variante", width="stretch", key="btn_regen_spintax", help="Genera una variación distinta con Spintax para evitar textos repetitivos."):
                    import random
                    st.session_state["react_seed"] = random.randint(1, 100000)
                    st.rerun()

            gen_msg = generate_reactivation_message(react_lead, strategy=strat_key, variant_seed=st.session_state["react_seed"])

            st.markdown(f"""
            <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.35); border-radius: 12px; padding: 18px 22px; margin-bottom: 18px;">
                <span style="font-size: 15px; font-weight: 700; color: #47664F; text-transform: uppercase; letter-spacing: 0.5px;">Vista Previa del Mensaje Generado (Spintax Único):</span>
                <p style="color: #ecfdf5; font-size: 17.5px; margin: 10px 0 0 0; line-height: 1.6; font-weight: 500;">
                    "{gen_msg}"
                </p>
            </div>
            """, unsafe_allow_html=True)

            wa_react_link = build_whatsapp_link(r_phone, r_name, r_prod, custom_text=gen_msg)

            c_act1, c_act2 = st.columns(2)
            with c_act1:
                st.link_button(
                    "Abrir y Enviar por WhatsApp",
                    wa_react_link,
                    type="primary",
                    width="stretch"
                )
            with c_act2:
                if st.button("Registrar Envío en CRM", width="stretch", key=f"btn_reg_react_sent_{react_lead.get('ID_Lead')}"):
                    strat_short_name = strat_choice.split()[0] if strat_choice else "Reactivación"
                    success = register_lead_contact_event(
                        DEFAULT_LEADS_PATH,
                        react_lead.get("ID_Lead"),
                        gen_msg,
                        f"Reactivación - {strat_short_name}"
                    )
                    st.session_state["leads_data"] = None
                    if success:
                        st.toast(f"✓ Envío de reactivación registrado para {r_name}.")
                    st.rerun()

    # 3. Feed de Leads Reactivados con Éxito
    reactivados_df = df_filtered[df_filtered.get("Is_Reactivado", 0) == 1].copy() if "Is_Reactivado" in df_filtered.columns else pd.DataFrame()
    if not reactivados_df.empty:
        st.markdown("---")
        st.markdown(f"#### Prospectos Reactivados con Éxito ({len(reactivados_df)})")
        st.caption("Clientes que estaban inactivos y respondieron a los mensajes de reactivación.")
        cols_won = [c for c in ["ID_Lead", "Contacto", "Telefono", "Linea_Producto", "Lead_Score", "Estado_Lead", "Recontacto_Prioridad", "Ultimo_Contacto_Label"] if c in reactivados_df.columns]
        st.dataframe(reactivados_df[cols_won], width="stretch", hide_index=True, height=220)


# =========================================================================
# VISTA: REUNIONES & FICHAS TÉCNICAS (DOSSIER AGRONÓMICO & CLOSERS)
# =========================================================================
elif page == "Reuniones & Fichas Técnicas":
    df_opps = comm.df_opportunities if comm is not None else None
    df_meetings = extract_meetings_and_technical_leads(df_filtered, df_opps=df_opps)
    m_kpis = compute_meeting_kpis(df_meetings)

    # 1. Tarjetas de KPI principales
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi("Reuniones & Derivaciones", f"{m_kpis.total_reuniones_derivaciones:,}", f"{m_kpis.meets_agendados} Meets | {m_kpis.derivados_closers} Closers", "#895522")
    with c2:
        render_kpi("Superficie Total Relevada", f"{int(m_kpis.superficie_total_ha):,} ha", "Hectáreas en seguimiento técnico", "#47664F")
    with c3:
        render_kpi("Closers Asignados", f"{m_kpis.closers_activos_count} ejecutivos", "Jony, Luisa, Sergio, Celina...", "#80634F")
    with c4:
        render_kpi("Rubros Relevados", f"{m_kpis.total_cultivos_relevados} cultivos", "Papa, Granos, Olivos, Ajo, Vid...", "#9B732A")

    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

    # Banner descriptivo de auditoría técnica
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.9), rgba(30, 41, 59, 0.8)); border: 1px solid #334155; border-radius: 14px; padding: 18px 22px; margin-bottom: 20px;">
        <div style="margin-bottom: 8px;">
            <b style="color: #895522; font-size: 18px;">Centro de Auditoría de Reuniones & Dossier Agronómico:</b>
        </div>
        <div style="color: #2B211A; font-size: 16.5px; line-height: 1.6;">
            Esta sección extrae automáticamente cada encuentro coordinado (Google Meet, Zoom, llamadas técnicas) y releva los datos agronómicos del campo: <b>superficie en hectáreas, tipo de cultivo, sistema de riego existente y acuerdos de reunión</b>.
        </div>
    </div>
    """, unsafe_allow_html=True)

    if df_meetings.empty:
        st.info("No se encontraron registros de reuniones o fichas técnicas.")
    else:
        # 2. Barra de Filtros Interactivos
        col_f1, col_f2, col_f3, col_f4 = st.columns([1.5, 1.2, 1.2, 1.5])

        with col_f1:
            tipo_opts = ["Todos los Encuentros", "Meet / Zoom Agendado", "Derivación a Closer", "Dossier Técnico / Campo"]
            sel_tipo = st.selectbox("Filtrar por Tipo de Evento:", tipo_opts, index=0, key="meet_filter_tipo")

        with col_f2:
            closers_list = sorted(list(df_meetings["Closer"].dropna().unique()))
            sel_closer = st.multiselect("Closer Asignado:", closers_list, default=closers_list, key="meet_filter_closer")

        with col_f3:
            cultivos_available = sorted(list(set(c for sub in df_meetings["Cultivos"].dropna() for c in sub.split(", "))))
            sel_cultivo = st.multiselect("Cultivo / Rubro:", cultivos_available, default=cultivos_available, key="meet_filter_cultivo")

        with col_f4:
            search_meet = st.text_input("Buscar reunión, contacto o campo:", placeholder="Ej: German, 140 ha, Papa, Jony...", key="meet_search_input")

        # Aplicar filtros
        df_view = df_meetings.copy()
        if sel_tipo != "Todos los Encuentros":
            df_view = df_view[df_view["Tipo_Evento"] == sel_tipo]

        if sel_closer:
            df_view = df_view[df_view["Closer"].isin(sel_closer)]

        if sel_cultivo:
            df_view = df_view[df_view["Cultivos"].apply(lambda x: any(c in str(x) for c in sel_cultivo))]

        if search_meet.strip():
            q_m = search_meet.strip().lower()
            m_cols = ["Contacto", "Telefono", "Closer", "Cultivos", "Tecnologia_Riego", "Acuerdo_Reunion", "Provincia", "Detalle_Completo"]
            mask_q = df_view[m_cols].astype(str).apply(lambda row: row.str.lower().str.contains(q_m, regex=False, na=False)).any(axis=1)
            df_view = df_view[mask_q]

        # 3. Tabla Interactiva de Reuniones
        cols_tbl = [
            "ID_Lead", "Tipo_Evento", "Contacto", "Telefono", "Closer", "Superficie",
            "Cultivos", "Tecnologia_Riego", "Acuerdo_Reunion", "Provincia", "Lead_Score", "WhatsApp_Link"
        ]
        cols_tbl = [c for c in cols_tbl if c in df_view.columns]

        st.caption(f"Mostrando **{len(df_view)}** reuniones y fichas técnicas identificadas. *(Haz clic en una fila para ver el Dossier Completo)*")

        table_selection = st.dataframe(
            df_view[cols_tbl],
            width="stretch",
            hide_index=True,
            height=340,
            on_select="rerun",
            selection_mode="single-row",
            column_config={
                "ID_Lead": st.column_config.NumberColumn("ID", format="%d", width="small"),
                "Tipo_Evento": st.column_config.TextColumn("Evento", width="medium"),
                "Contacto": st.column_config.TextColumn("Contacto", width="medium"),
                "Telefono": st.column_config.TextColumn("Teléfono", width="medium"),
                "Closer": st.column_config.TextColumn("Closer / Responsable", width="small"),
                "Superficie": st.column_config.TextColumn("Hectáreas", width="small"),
                "Cultivos": st.column_config.TextColumn("Cultivo / Rubro", width="medium"),
                "Tecnologia_Riego": st.column_config.TextColumn("Tecnología / Riego", width="medium"),
                "Acuerdo_Reunion": st.column_config.TextColumn("Acuerdo / Estado", width="large"),
                "Lead_Score": st.column_config.ProgressColumn("Score", format="%d pts", min_value=0, max_value=100),
                "WhatsApp_Link": st.column_config.LinkColumn("WhatsApp", display_text="Chatear"),
            },
            key="meetings_interactive_table"
        )

        selected_meeting = None
        selected_rows = table_selection.selection.rows if table_selection and hasattr(table_selection, "selection") else []
        if selected_rows:
            selected_meeting = df_view.iloc[selected_rows[0]]
        elif not df_view.empty:
            selected_meeting = df_view.iloc[0]

        # 4. Dossier Agronómico & Ficha 360° del Encuentro
        if selected_meeting is not None:
            st.markdown("---")
            st.markdown("### Ficha 360° del Encuentro & Dossier Agronómico")

            col_card_left, col_card_right = st.columns([1.3, 1.7])

            with col_card_left:
                m_nom = sanitize_display_name(str(selected_meeting.get("Contacto", "Cliente")))
                m_tel = str(selected_meeting.get("Telefono", ""))
                m_prod = str(selected_meeting.get("Linea_Producto", "Equipos"))
                m_closer = str(selected_meeting.get("Closer", "Equipo"))
                m_ha = str(selected_meeting.get("Superficie", "-"))
                m_cult = str(selected_meeting.get("Cultivos", "General"))
                m_tech = str(selected_meeting.get("Tecnologia_Riego", "Monitoreo"))
                m_acuerdo = sanitize_display_name(str(selected_meeting.get("Acuerdo_Reunion", "Reunión agendada")))
                m_prov = str(selected_meeting.get("Provincia", "Argentina"))
                m_loc = str(selected_meeting.get("Localidad", "Sin Localidad"))
                m_tipo = sanitize_display_name(str(selected_meeting.get("Tipo_Evento", "Meet")))
                m_score = int(selected_meeting.get("Lead_Score", 30))
                m_link = selected_meeting.get("WhatsApp_Link", "")

                meeting_card_html = (
                    f'<div class="lead-profile-card">'
                    f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">'
                    f'<div>'
                    f'<h3 style="margin: 0; font-size: 22px; font-weight: 700; color: #2B211A;">{m_nom}</h3>'
                    f'<span style="color: #786451; font-size: 16px;">ID #{selected_meeting.get("ID_Lead")} · {m_tel}</span>'
                    f'</div>'
                    f'<span class="status-badge" style="background: rgba(56, 189, 248, 0.2); color: #895522; border-color: rgba(56, 189, 248, 0.4); font-size: 15px; font-weight: 700; padding: 6px 14px;">{m_tipo}</span>'
                    f'</div>'
                    f'<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 16px;">'
                    f'<div style="background: #F7F1E6; padding: 12px 14px; border-radius: 10px; border: 1px solid #EFE5D6;">'
                    f'<span style="font-size: 14px; color: #786451; text-transform: uppercase; font-weight: 600;">Superficie</span><br>'
                    f'<b style="font-size: 16.5px; color: #47664F;">{m_ha}</b>'
                    f'</div>'
                    f'<div style="background: #F7F1E6; padding: 12px 14px; border-radius: 10px; border: 1px solid #EFE5D6;">'
                    f'<span style="font-size: 14px; color: #786451; text-transform: uppercase; font-weight: 600;">Cultivo / Rubro</span><br>'
                    f'<b style="font-size: 16.5px; color: #9B732A;">{m_cult}</b>'
                    f'</div>'
                    f'<div style="background: #F7F1E6; padding: 12px 14px; border-radius: 10px; border: 1px solid #EFE5D6;">'
                    f'<span style="font-size: 14px; color: #786451; text-transform: uppercase; font-weight: 600;">Sistema & Riego</span><br>'
                    f'<b style="font-size: 16.5px; color: #2B211A;">{m_tech}</b>'
                    f'</div>'
                    f'<div style="background: #F7F1E6; padding: 12px 14px; border-radius: 10px; border: 1px solid #EFE5D6;">'
                    f'<span style="font-size: 14px; color: #786451; text-transform: uppercase; font-weight: 600;">Closer Asignado</span><br>'
                    f'<b style="font-size: 16.5px; color: #B18450;">{m_closer}</b>'
                    f'</div>'
                    f'</div>'
                    f'<div style="background: rgba(99, 102, 241, 0.12); border: 1px solid rgba(99, 102, 241, 0.4); border-radius: 12px; padding: 16px 18px; margin-bottom: 16px;">'
                    f'<div style="font-size: 14.5px; font-weight: 700; color: #B18450; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px;">Acuerdo & Estado de la Reunión</div>'
                    f'<div style="font-size: 16.5px; color: #2B211A; font-weight: 600; line-height: 1.5;">{m_acuerdo}</div>'
                    f'</div>'
                    f'</div>'
                )
                st.markdown(meeting_card_html, unsafe_allow_html=True)

                c_m_btn1, c_m_btn2 = st.columns(2)
                with c_m_btn1:
                    if m_link:
                        st.link_button("Abrir WhatsApp", m_link, type="primary", width="stretch")
                with c_m_btn2:
                    if st.button("Registrar Minuta / Seguimiento", width="stretch", key=f"btn_meet_reg_{selected_meeting.get('ID_Lead')}"):
                        register_lead_contact_event(DEFAULT_LEADS_PATH, selected_meeting.get("ID_Lead"), "Reunión / Seguimiento realizado", f"Meet con {m_closer}")
                        st.session_state["leads_data"] = None
                        st.toast(f"✓ Minuta registrada para {m_nom}.")
                        st.rerun()

            with col_card_right:
                st.markdown("##### Historial de Conversación & Notas del Encuentro")
                meet_lead_row = df_filtered[df_filtered["ID_Lead"] == selected_meeting.get("ID_Lead")]
                lead_data_for_timeline = meet_lead_row.iloc[0] if not meet_lead_row.empty else selected_meeting

                timeline = get_lead_chat_timeline(lead_data_for_timeline)
                if timeline:
                    chat_html = "<div class='wa-chat-box' style='max-height: 320px;'>"
                    for item in timeline:
                        t_type = item.get("type", "")
                        sender = sanitize_display_name(item.get("sender", ""))
                        txt = item.get("text", "")
                        time_lbl = item.get("time", "")

                        if t_type == "whatsapp_out":
                            chat_html += (
                                f'<div class="wa-bubble-out">'
                                f'<b style="color: #6ee7b7;">{sender}</b><br>'
                                f'{txt}'
                                f'<div class="wa-time">{time_lbl}</div>'
                                f'</div>'
                            )
                        elif t_type in ["whatsapp_in", "whatsapp_live"]:
                            chat_html += (
                                f'<div class="wa-bubble-in">'
                                f'<b style="color: #895522;">{sender}</b><br>'
                                f'{txt}'
                                f'<div class="wa-time">{time_lbl}</div>'
                                f'</div>'
                            )
                        else:
                            chat_html += (
                                f'<div class="wa-bubble-note">'
                                f'<b>{sender} ({time_lbl}):</b> {txt}'
                                f'</div>'
                            )
                    chat_html += "</div>"
                    st.markdown(chat_html, unsafe_allow_html=True)
                else:
                    st.info("Detalle de la consulta:")
                    st.write(selected_meeting.get("Detalle_Completo", "Sin detalle adicional"))

                # Caja para registrar minuta técnica o acuerdo
                st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
                meet_note = st.text_input("Agregar minuta técnica o resultado de la reunión:", placeholder="Ej: Se acordó envío de cotización por 2 sondas de 120cm con entrega en septiembre...", key="meet_note_input")
                if meet_note.strip():
                    if st.button("Guardar Minuta en CRM", width="stretch", key="btn_save_meet_note"):
                        register_lead_contact_event(DEFAULT_LEADS_PATH, selected_meeting.get("ID_Lead"), meet_note, f"Minuta Meet ({m_closer})")
                        st.session_state["leads_data"] = None
                        st.toast("✓ Minuta agregada al historial del cliente.")
                        st.rerun()


# =========================================================================
# VISTA 3: PAUTA & CONVERSIÓN
# =========================================================================
elif page == "Pauta & Conversión":
    col_p1, col_p2 = st.columns([1.3, 1.0])
    with col_p1:
        st.markdown("#### Rendimiento Publicitario por Línea de Producto")

        tab_inv, tab_cpl, tab_conv = st.tabs([
            "Inversión ($ ARS)",
            "Costo por Lead (CPL)",
            "Conversaciones Generadas"
        ])

        df_p = comm.df_product_summary.copy()

        with tab_inv:
            df_inv = df_p.sort_values(by="Inversion_Total", ascending=True).copy()
            df_inv["Text_Bar"] = df_inv.apply(lambda r: f" ${r['Inversion_Total']:,.0f} ({r['Pct_Inversion']:.1f}%)", axis=1)

            fig_inv = go.Figure(go.Bar(
                y=df_inv["Producto"],
                x=df_inv["Inversion_Total"],
                orientation="h",
                text=df_inv["Text_Bar"],
                textposition="auto",
                marker=dict(
                    color=df_inv["Inversion_Total"],
                    colorscale=[[0.0, "#B18450"], [1.0, "#895522"]],
                    line=dict(color="#895522", width=1),
                ),
                customdata=df_inv[["Pct_Inversion", "Conversaciones_Total", "CPL_Promedio"]],
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "Inversión: $%{x:,.0f} ARS (%{customdata[0]:.1f}%)<br>"
                    "Conversaciones: %{customdata[1]} leads<br>"
                    "CPL Promedio: $%{customdata[2]:,.0f} / lead<extra></extra>"
                ),
            ))
            fig_inv.update_layout(
                title=dict(text="Inversión Total por Producto ($ ARS y % del Total)", font=dict(size=16, color="#2B211A")),
                template="fauvor",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="#FFFAF2",
                xaxis=dict(
                    title="Inversión Acumulada ($ ARS)",
                    tickprefix="$",
                    gridcolor="rgba(51, 65, 85, 0.4)",
                    tickfont=dict(size=13, color="#786451"),
                ),
                yaxis=dict(
                    tickfont=dict(size=14, color="#2B211A", weight=600),
                    automargin=True,
                ),
                margin=dict(l=10, r=20, t=40, b=40),
                height=450,
            )
            st.plotly_chart(fig_inv, width="stretch")

        with tab_cpl:
            df_cpl = df_p[df_p["CPL_Promedio"] > 0].sort_values(by="CPL_Promedio", ascending=False).copy()
            df_cpl["Text_CPL"] = df_cpl["CPL_Promedio"].apply(lambda x: f" ${x:,.0f} / lead")

            fig_cpl = go.Figure(go.Bar(
                y=df_cpl["Producto"],
                x=df_cpl["CPL_Promedio"],
                orientation="h",
                text=df_cpl["Text_CPL"],
                textposition="auto",
                marker=dict(
                    color=df_cpl["CPL_Promedio"],
                    colorscale=[[0, "#D8AA63"], [1, "#895522"]],
                    showscale=False,
                    line=dict(color="#2B211A", width=0.5),
                ),
                customdata=df_cpl[["Inversion_Total", "Conversaciones_Total"]],
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "Costo por Lead: $%{x:,.0f} ARS<br>"
                    "Inversión: $%{customdata[0]:,.0f}<br>"
                    "Leads: %{customdata[1]}<extra></extra>"
                ),
            ))
            fig_cpl.update_layout(
                title=dict(text="Costo por Lead Adquirido (Menor CPL = Mayor Eficiencia)", font=dict(size=16, color="#2B211A")),
                template="fauvor",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="#FFFAF2",
                xaxis=dict(
                    title="Costo por Lead ($ ARS / lead)",
                    tickprefix="$",
                    gridcolor="rgba(51, 65, 85, 0.4)",
                    tickfont=dict(size=13, color="#786451"),
                ),
                yaxis=dict(
                    tickfont=dict(size=14, color="#2B211A", weight=600),
                    automargin=True,
                ),
                margin=dict(l=10, r=20, t=40, b=40),
                height=450,
            )
            st.plotly_chart(fig_cpl, width="stretch")

        with tab_conv:
            df_conv = df_p.sort_values(by="Conversaciones_Total", ascending=True).copy()
            df_conv["Text_Conv"] = df_conv["Conversaciones_Total"].apply(lambda x: f" {int(x)} leads" if x > 0 else " Sin leads")

            fig_conv = go.Figure(go.Bar(
                y=df_conv["Producto"],
                x=df_conv["Conversaciones_Total"],
                orientation="h",
                text=df_conv["Text_Conv"],
                textposition="auto",
                marker=dict(
                    color="#47664F",
                    line=dict(color="#059669", width=1),
                ),
                customdata=df_conv[["Inversion_Total", "CPL_Promedio"]],
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "Conversaciones: %{x} leads<br>"
                    "Inversión: $%{customdata[0]:,.0f}<br>"
                    "CPL: $%{customdata[1]:,.0f} / lead<extra></extra>"
                ),
            ))
            fig_conv.update_layout(
                title=dict(text="Volumen de Conversaciones Generadas por Producto", font=dict(size=16, color="#2B211A")),
                template="fauvor",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="#FFFAF2",
                xaxis=dict(
                    title="Conversaciones (Leads)",
                    gridcolor="rgba(51, 65, 85, 0.4)",
                    tickfont=dict(size=13, color="#786451"),
                ),
                yaxis=dict(
                    tickfont=dict(size=14, color="#2B211A", weight=600),
                    automargin=True,
                ),
                margin=dict(l=10, r=20, t=40, b=40),
                height=450,
            )
            st.plotly_chart(fig_conv, width="stretch")

    with col_p2:
        st.markdown("#### Resumen Mensual de Pauta")
        st.dataframe(
            comm.df_monthly_summary,
            width="stretch",
            hide_index=True,
            height=495,
            column_config={
                "Mes": st.column_config.TextColumn("Mes"),
                "Inversion_Total": st.column_config.NumberColumn("Inversión ($)", format="$%,.0f"),
                "Alcance_Total": st.column_config.NumberColumn("Alcance", format="%,.0f"),
                "Conversaciones_Total": st.column_config.NumberColumn("Conversaciones", format="%d"),
                "CPL_Promedio": st.column_config.NumberColumn("CPL ($)", format="$%,.0f"),
                "CPM_Promedio": st.column_config.NumberColumn("CPM ($)", format="$%,.0f"),
            }
        )

    st.markdown("#### Pipeline de Oportunidades & Cotizaciones")
    st.dataframe(
        comm.df_opportunities,
        width="stretch",
        hide_index=True,
        height=320,
        column_config={
            "Mes": st.column_config.TextColumn("Mes", width="small"),
            "Cliente": st.column_config.TextColumn("Cliente", width="medium"),
            "Contacto": st.column_config.TextColumn("Teléfono / Contacto", width="medium"),
            "Producto": st.column_config.TextColumn("Producto", width="small"),
            "Monto_Cotizado": st.column_config.NumberColumn("Monto Cotizado", format="$%,.0f"),
            "Prob_Cierre": st.column_config.ProgressColumn("Prob. Cierre", min_value=0, max_value=1, format="%.0f%%"),
            "Closer_Limpio": st.column_config.TextColumn("Closer", width="small"),
            "Provincia": st.column_config.TextColumn("Provincia", width="small"),
        }
    )


# =========================================================================
# VISTA: GESTIÓN & AUDITORÍA DE CAMPAÑAS
# =========================================================================
elif page == "Campañas":
    render_campaigns_view(comm, sheets, master, df_filtered)


# =========================================================================
# VISTA 4: GEOGRAFÍA & TERRITORIO
# =========================================================================
elif page == "Geografía & Territorio":
    prov_df = compute_province_performance(df_filtered)
    reg_df = compute_regional_performance(df_filtered)

    if prov_df.empty:
        st.warning("No se encontraron datos para los filtros seleccionados. Por favor seleccione al menos una Línea de Producto o Región en la barra lateral.")
    else:
        col_g1, col_g2 = st.columns([1.5, 1])
        with col_g1:
            st.markdown("#### Demanda por Provincia")
            top_prov_chart = prov_df.head(12).copy()
            max_val = float(top_prov_chart["Total_Leads"].max()) if not top_prov_chart.empty else 100

            top_prov_chart["Etiqueta"] = top_prov_chart.apply(
                lambda r: f" {int(r['Total_Leads'])} leads ({r['Tasa_Conversion_Pct']:.1f}%)", axis=1
            )
            fig_prov = px.bar(
                top_prov_chart,
                x="Total_Leads",
                y="Provincia",
                orientation="h",
                color="Tasa_Conversion_Pct",
                color_continuous_scale=[
                    [0.0, "#ef4444"],    # Rojo: baja conversión
                    [0.35, "#9B732A"],   # Ámbar: conversión media
                    [0.70, "#47664F"],   # Verde: conversión alta
                    [1.0, "#47664F"],    # Esmeralda: excelente
                ],
                text="Etiqueta",
                labels={
                    "Total_Leads": "Volumen de Leads",
                    "Provincia": "Provincia",
                    "Tasa_Conversion_Pct": "Conversión (%)",
                },
                title="Top 12 Provincias: Volumen y Tasa de Cierre",
                template="fauvor"
            )
            fig_prov.update_traces(
                textposition="outside",
                cliponaxis=False,
                textfont=dict(size=14, color="#2B211A"),
                hovertemplate="<b>%{y}</b><br>• Total Prospectos: <b>%{x}</b><br>• Tasa Conversión: <b>%{marker.color:.1f}%</b><extra></extra>",
            )
            fig_prov.update_coloraxes(showscale=False)
            fig_prov.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(autorange="reversed"),
                xaxis=dict(
                    range=[0, max_val * 1.30],
                    showgrid=True,
                    gridcolor="rgba(255,255,255,0.08)"
                ),
                margin=dict(l=10, r=20, t=40, b=20),
            )
            st.plotly_chart(fig_prov, width="stretch")
            st.caption("**Efectividad:** Alta (>15%)  ·  Media (7–15%)  ·  Baja / Sin cierres (<7%)")

        with col_g2:
            st.markdown("#### Ranking Oficial de Provincias")
            st.dataframe(prov_df, width="stretch", hide_index=True, height=420)

        # Explorador Interactivo de Prospectos por Provincia
        st.markdown("---")
        st.markdown("#### Explorador de Prospectos por Provincia")
        provinces_available = sorted(list(df_filtered["Provincia"].dropna().unique()))
        if provinces_available:
            chosen_prov = st.selectbox(
                "Seleccione una provincia para ver y contactar a sus clientes:",
                provinces_available,
                key="geo_prov_selector"
            )
            df_prov_leads = df_filtered[df_filtered["Provincia"] == chosen_prov].copy()
            st.caption(f"Mostrando **{len(df_prov_leads)}** prospectos en **{chosen_prov}**:")
            cols_geo_leads = [
                c for c in [
                    "ID_Lead", "Contacto", "Telefono", "WhatsApp_Link", "Linea_Producto",
                    "Lead_Score", "Recontacto_Prioridad", "Accion_Sugerida", "Estado_Lead", "Localidad"
                ] if c in df_prov_leads.columns
            ]
            st.dataframe(
                df_prov_leads[cols_geo_leads],
                width="stretch",
                hide_index=True,
                height=320,
                column_config={
                    "WhatsApp_Link": st.column_config.LinkColumn("WhatsApp", display_text="Chatear"),
                    "Lead_Score": st.column_config.ProgressColumn("Score", format="%d pts", min_value=0, max_value=100),
                    "ID_Lead": st.column_config.NumberColumn("ID", format="%d", width="small"),
                }
            )


# =========================================================================
# VISTA 5: INFORMES MENSUALES & PDF
# =========================================================================
elif page in ["Informes mensuales & PDF", "Informes mensuales"]:
    render_reports_view(sheets, comm, current_user)


# =========================================================================
# VISTA 6: CALIDAD DE DATOS
# =========================================================================
elif page == "Calidad de datos":
    c1, c2 = st.columns(2)
    with c1:
        render_kpi("Fuentes Conectadas", "2 / 2", "Leads + Comercial", "#895522")
    with c2:
        render_kpi("Registros Totales", f"{len(master):,}", "Base CRM", "#47664F")

    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
    st.markdown("#### Diagnóstico de Valores Faltantes en Base CRM")
    missing_df = df_filtered.isna().sum().sort_values(ascending=False).reset_index()
    missing_df.columns = ["Columna", "Valores_Faltantes"]
    total_len = len(df_filtered)
    if total_len > 0:
        missing_df["Porcentaje_Faltante"] = (missing_df["Valores_Faltantes"] / total_len * 100).round(1).astype(str) + "%"
    else:
        missing_df["Porcentaje_Faltante"] = "0.0%"
    st.dataframe(missing_df, width="stretch", hide_index=True)


# =========================================================================
# VISTA 7: ADMINISTRACIÓN & AUDITORÍA (SOLO ADMIN/MANAGER)
# =========================================================================
elif page == "Administración & Auditoría":
    render_admin_view(current_user)


# =========================================================================
# VISTA 8: CONEXIÓN WHATSAPP, QR & COLA DE SALIDA
# =========================================================================
elif page == "WhatsApp & Cola de Salida":
    render_whatsapp_view(current_user)

else:
    render_whatsapp_view(current_user)
