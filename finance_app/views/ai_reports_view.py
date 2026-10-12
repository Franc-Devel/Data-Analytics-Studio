"""
FAUVOR Analytics - Vista de Informes de IA y Discriminación de Demanda en WhatsApp
Segmenta y analiza todo el historial de chats entrantes, identifica requerimientos específicos
y permite filtrar dinámicamente por rangos de fechas, campañas publicitarias, productos e intenciones.
"""

from __future__ import annotations
from datetime import datetime, date
from io import BytesIO
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from finance_app.services.whatsapp_ai_analyzer import analyze_all_whatsapp_conversations
from finance_app.services.ai_service import (
    get_ai_status,
    is_ai_available,
    analyze_conversation_history,
    process_document_with_ai,
    save_document_to_database,
)
from finance_app.logging_config import get_logger

logger = get_logger("ai_reports_view")


@st.cache_data(show_spinner=False, ttl=60)
def _get_cached_whatsapp_analysis(master_df_serialized: Optional[bytes] = None) -> pd.DataFrame:
    """Carga y procesa en caché el historial completo de WhatsApp correlacionado con los leads."""
    master_df = None
    if master_df_serialized is not None:
        try:
            master_df = pd.read_parquet(BytesIO(master_df_serialized))
        except Exception:
            master_df = None
    return analyze_all_whatsapp_conversations(master_df)


def _render_document_coequiper_tab(current_user: Optional[Dict[str, Any]] = None) -> None:
    """Renderiza el módulo interactivo del Coequiper IA para procesamiento y control de documentos."""
    st.markdown("#### Coequiper IA · Procesamiento, Auditoría y Control de Documentos")
    st.caption("Adjunte facturas, presupuestos, notas de pedido o remitos. La IA analiza los datos, audita matemáticamente las cuentas (precios, subtotales, IVA y total) y presenta una primera devolución. Al ser aceptada, los datos se suman a la base del proyecto.")

    ai_status = get_ai_status()
    last_err = ai_status.get("last_error", "")
    c_st1, c_st2, c_st3, c_st4 = st.columns(4)
    if last_err and "429" in last_err:
        c_st1.metric("Estado IA", "Sin Saldo (429)", delta="Recargar saldo", delta_color="inverse")
    elif ai_status.get("available"):
        c_st1.metric("Estado IA", "Conectado", delta="API Activa", delta_color="normal")
    else:
        c_st1.metric("Estado IA", "Sin API Key", delta="Fallback Activo", delta_color="off")
    model_label = ai_status.get("current_model", "qwen/qwen3.8-27b")
    provider_label = ai_status.get("provider", "Groq Cloud")
    c_st2.metric("Modelo LLM", model_label)
    c_st3.metric("Proveedor", provider_label)
    c_st4.metric("Consumo Tokens", "Optimizado (Bajo)")

    if last_err and "429" in last_err:
        st.warning(f"⚠️ **{provider_label} informó límite de tasa o saldo (Error 429):** {last_err}")
    elif not ai_status.get("available"):
        st.info("💡 Para activar la inferencia en la nube o local, defina las credenciales de API en `.env`. El sistema puede procesar de todas formas en modo heurístico preliminar.")


    st.markdown("---")

    col_up1, col_up2 = st.columns([1.5, 1.0])
    with col_up1:
        uploaded_doc = st.file_uploader(
            "Seleccionar Comprobante o Documento Comercial:",
            type=["pdf", "jpg", "jpeg", "png", "webp", "xlsx", "csv", "txt"],
            key="coequiper_doc_uploader",
            help="Soporta imágenes de facturas, PDFs digitales, planillas Excel o archivos de texto."
        )

    with col_up2:
        st.markdown("""
        <div style="background: rgba(30, 41, 59, 0.5); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 10px; padding: 14px 16px;">
            <b style="color: #895522;">¿Qué controla el Coequiper IA?</b>
            <ul style="margin: 6px 0 0 0; padding-left: 18px; color: #2B211A; font-size: 13.5px;">
                <li>Coherencia aritmética: <code>cant × precio = subtotal</code>.</li>
                <li>Neto gravado vs suma de ítems.</li>
                <li>Cálculo de alícuota de IVA y total general.</li>
                <li>Detección de cliente, CUIT y localidad de origen.</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)

    if uploaded_doc is not None:
        if st.button("🔍 Procesar, Analizar y Controlar con IA", type="primary", use_container_width=True):
            with st.spinner("Procesando y auditando documento comercial con IA..."):
                file_bytes = uploaded_doc.getvalue()
                res = process_document_with_ai(file_bytes, uploaded_doc.name, uploaded_doc.type)
                st.session_state["doc_analysis_result"] = res
                st.success(f"✓ Documento '{uploaded_doc.name}' analizado y auditado.")

    # Mostrar Primera Devolución si hay un resultado cargado
    doc_res = st.session_state.get("doc_analysis_result")
    if doc_res:
        st.markdown("---")
        st.markdown("### 📋 Primera Devolución del Coequiper IA")
        devolucion = doc_res.get("primera_devolucion", {})
        datos = doc_res.get("datos", {})

        # 1. Semáforo de auditoría de cuentas
        if doc_res.get("cuentas_cierran"):
            st.markdown("""
            <div style="background: rgba(16, 185, 129, 0.15); border-left: 4px solid #47664F; border-radius: 8px; padding: 12px 16px; margin-bottom: 14px;">
                <b style="color: #47664F; font-size: 15px;">✅ AUDITORÍA CONTABLE EXITOSA: LAS CUENTAS CIERRAN</b>
                <p style="margin: 4px 0 0 0; color: #2B211A; font-size: 14px;">Todos los subtotales de ítems, el neto gravado, el IVA y el total coinciden aritméticamente sin discrepancias.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background: rgba(239, 68, 68, 0.15); border-left: 4px solid #ef4444; border-radius: 8px; padding: 12px 16px; margin-bottom: 14px;">
                <b style="color: #ef4444; font-size: 15px;">⚠️ OBSERVACIONES Y DISCREPANCIAS DETECTADAS</b>
                <p style="margin: 4px 0 0 0; color: #2B211A; font-size: 14px;">Se encontraron inconsistencias numéricas o campos de identificación incompletos. Revise el detalle antes de aprobar.</p>
            </div>
            """, unsafe_allow_html=True)
            for adv in doc_res.get("advertencias", []):
                st.warning(f"• {adv}")

        # 2. Métricas y totales
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Tipo Documento", devolucion.get("titulo", "Comprobante"))
        col_m2.metric("Total General", f"${devolucion.get('total', 0.0):,.2f} {devolucion.get('moneda', 'ARS')}")
        col_m3.metric("Neto Gravado", f"${devolucion.get('neto', 0.0):,.2f}")
        col_m4.metric("IVA Liquidado", f"${devolucion.get('iva', 0.0):,.2f}")

        # 3. Datos de Emisor y Cliente
        col_e, col_c = st.columns(2)
        emisor = devolucion.get("emisor") or {}
        cliente = devolucion.get("cliente") or {}

        with col_e:
            st.markdown(f"""
            <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 10px; padding: 14px;">
                <b style="color: #786451; font-size: 13px; text-transform: uppercase;">Emisor del Documento</b>
                <p style="margin: 6px 0 2px 0; color: #2B211A; font-size: 16px; font-weight: 600;">{emisor.get('nombre') or 'No detectado'}</p>
                <p style="margin: 0; color: #786451; font-size: 13px;">CUIT: <code>{emisor.get('cuit') or 'S/D'}</code></p>
                <p style="margin: 0; color: #786451; font-size: 13px;">Dirección: {emisor.get('direccion') or 'S/D'}</p>
            </div>
            """, unsafe_allow_html=True)

        with col_c:
            loc_cliente = cliente.get('localidad')
            loc_display = f"<span style='color: #895522;'>{loc_cliente}, {cliente.get('provincia') or ''}</span>" if loc_cliente else "<span style='color: #9B732A;'>⚠️ No informada en documento</span>"
            st.markdown(f"""
            <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 10px; padding: 14px;">
                <b style="color: #786451; font-size: 13px; text-transform: uppercase;">Cliente / Receptor</b>
                <p style="margin: 6px 0 2px 0; color: #2B211A; font-size: 16px; font-weight: 600;">{cliente.get('nombre') or 'No detectado'}</p>
                <p style="margin: 0; color: #786451; font-size: 13px;">CUIT: <code>{cliente.get('cuit') or 'S/D'}</code> | Tel: {cliente.get('telefono') or 'S/D'}</p>
                <p style="margin: 0; color: #786451; font-size: 13px;">Localidad: {loc_display}</p>
            </div>
            """, unsafe_allow_html=True)

        # 4. Tabla de Ítems
        st.markdown("##### Desglose de Ítems y Conceptos Facturados")
        items = devolucion.get("items") or []
        if items:
            df_items = pd.DataFrame(items)
            df_items.columns = [c.capitalize() for c in df_items.columns]
            st.dataframe(df_items, use_container_width=True, hide_index=True)
        else:
            st.info("No se extrajeron ítems desglosados en este comprobante.")

        # 5. Resumen Ejecutivo
        st.markdown(f"""
        <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 10px; padding: 14px; margin: 14px 0;">
            <b style="color: #B18450;">Síntesis Ejecutiva de la IA:</b>
            <p style="margin: 4px 0 0 0; color: #2B211A; font-size: 14.5px;">{devolucion.get('resumen')}</p>
        </div>
        """, unsafe_allow_html=True)

        # 6. Botón de Aceptación para sumar a la Base de Datos del Proyecto
        col_btn1, col_btn2 = st.columns([2, 1])
        with col_btn1:
            if st.button("💾 Aceptar e Incorporar a la Base de Datos del Proyecto", type="primary", use_container_width=True):
                with st.spinner("Guardando cliente, oportunidad comercial y registrando en auditoría..."):
                    save_res = save_document_to_database(doc_res, user_actor=current_user)
                    st.success(f"✓ {save_res.get('message')}")
                    st.balloons()
        with col_btn2:
            if st.button("🗑️ Descartar Devolución", use_container_width=True):
                st.session_state["doc_analysis_result"] = None
                st.rerun()


def render_ai_reports_view(master_df: pd.DataFrame, comm_data: Any = None, current_user: Optional[Dict[str, Any]] = None) -> None:
    """Renderiza la vista completa de Informes IA en Streamlit."""
    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%);
                border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 14px; padding: 24px 28px; margin-bottom: 22px;">
        <h3 style="margin: 0; color: #2B211A; font-size: 24px; font-weight: 700; letter-spacing: -0.5px;">
            Coequiper IA · Análisis, Control Documental y Segmentación de Demanda
        </h3>
        <p style="margin: 6px 0 0 0; color: #786451; font-size: 14.5px;">
            Procesamiento y auditoría de documentos comerciales, y discriminación semántica profunda del historial de WhatsApp en tiempo real.
        </p>
    </div>
    """, unsafe_allow_html=True)

    tab_docs, tab_chats = st.tabs([
        "📄 Coequiper IA · Control y Carga de Documentos",
        "📊 Discriminación de Demanda y Segmentación de Chats WhatsApp"
    ])

    with tab_docs:
        _render_document_coequiper_tab(current_user)

    with tab_chats:
        _render_whatsapp_demand_tab(master_df, comm_data, current_user)


def _render_whatsapp_demand_tab(master_df: pd.DataFrame, comm_data: Any = None, current_user: Optional[Dict[str, Any]] = None) -> None:
    """Renderiza el análisis y segmentación de chats de WhatsApp."""
    # 1. Cargar datos analizados
    with st.spinner("Procesando y categorizando el historial completo de conversaciones con IA..."):
        try:
            # Serializar master_df de forma liviana para la caché
            serialized = None
            if not master_df.empty:
                buf = BytesIO()
                master_df.to_parquet(buf)
                serialized = buf.getvalue()
            df_chats = _get_cached_whatsapp_analysis(serialized)
        except Exception as e:
            logger.warning(f"Fallback a análisis directo sin parquet: {e}")
            df_chats = analyze_all_whatsapp_conversations(master_df)

    if df_chats.empty:
        st.warning("⚠️ No se encontraron conversaciones registradas en `whatsapp_inbox/live_incoming_messages.json`.")
        return

    # Normalizar columnas de fecha a datetime tz-naive para evitar errores de comparación
    for col in ["Fecha_Primer_Mensaje", "Fecha_Ultimo_Mensaje"]:
        if col in df_chats.columns:
            df_chats[col] = pd.to_datetime(df_chats[col], errors="coerce")
            if hasattr(df_chats[col].dt, "tz") and df_chats[col].dt.tz is not None:
                df_chats[col] = df_chats[col].dt.tz_localize(None)

    # =========================================================================
    # BARRA DE FILTROS DINÁMICOS (FECHAS, CAMPAÑAS, PRODUCTOS, INTENCIONES)
    # =========================================================================
    st.markdown("#### Filtros de Segmentación Inteligente")

    col_date, col_camp, col_prod, col_intent = st.columns([1.2, 1.4, 1.4, 1.4])

    # Fechas min y max
    min_date = df_chats["Fecha_Primer_Mensaje"].dropna().min()
    max_date = df_chats["Fecha_Ultimo_Mensaje"].dropna().max()
    d_start = min_date.date() if pd.notna(min_date) else date(2026, 1, 1)
    d_end = max_date.date() if pd.notna(max_date) else date(2026, 12, 31)
    if d_start > d_end:
        d_start, d_end = d_end, d_start

    with col_date:
        selected_dates = st.date_input(
            "Rango de Fechas:",
            value=(d_start, d_end),
            min_value=d_start,
            max_value=d_end,
            key="ai_filter_dates",
        )

    # Campañas disponibles
    camp_options = sorted(list(df_chats["Campana_Origen"].dropna().unique()))
    with col_camp:
        selected_camps = st.multiselect(
            "Campaña / Fuente:",
            options=camp_options,
            default=camp_options,
            key="ai_filter_camps",
            help="Filtra por campaña publicitaria de Meta Ads o canal de ingreso.",
        )

    # Productos disponibles
    prod_options = sorted(list(df_chats["Producto_Principal"].dropna().unique()))
    with col_prod:
        selected_prods = st.multiselect(
            "Producto Demandado:",
            options=prod_options,
            default=prod_options,
            key="ai_filter_prods",
            help="Línea técnica consultada por el cliente.",
        )

    # Intenciones disponibles
    intent_options = sorted(list(df_chats["Intencion_Principal"].dropna().unique()))
    with col_intent:
        selected_intents = st.multiselect(
            "Tipo de Requerimiento:",
            options=intent_options,
            default=intent_options,
            key="ai_filter_intents",
            help="Qué es lo que pide concretamente el usuario.",
        )

    # Buscador de texto libre
    search_q = st.text_input(
        "Buscar por Cliente, Teléfono, Cultivo o palabra clave en el requerimiento:",
        placeholder="Ej: papa, kiwi, 60cm, pivot, kilimo, estela, ducret...",
        key="ai_filter_search",
    )

    # =========================================================================
    # APLICACIÓN DE FILTROS
    # =========================================================================
    df_filtered = df_chats.copy()

    # Filtro fecha
    if isinstance(selected_dates, (tuple, list)):
        col_dates = pd.to_datetime(df_filtered["Fecha_Ultimo_Mensaje"], errors="coerce")
        if hasattr(col_dates.dt, "tz") and col_dates.dt.tz is not None:
            col_dates = col_dates.dt.tz_localize(None)

        if len(selected_dates) == 2 and selected_dates[0] and selected_dates[1]:
            start_dt = pd.to_datetime(f"{selected_dates[0]} 00:00:00")
            end_dt = pd.to_datetime(f"{selected_dates[1]} 23:59:59")
            if getattr(start_dt, "tzinfo", None) is not None:
                start_dt = start_dt.tz_localize(None)
            if getattr(end_dt, "tzinfo", None) is not None:
                end_dt = end_dt.tz_localize(None)
            if start_dt > end_dt:
                start_dt, end_dt = end_dt, start_dt

            df_filtered = df_filtered[
                (col_dates >= start_dt) & (col_dates <= end_dt)
            ]
        elif len(selected_dates) == 1 and selected_dates[0]:
            start_dt = pd.to_datetime(f"{selected_dates[0]} 00:00:00")
            if getattr(start_dt, "tzinfo", None) is not None:
                start_dt = start_dt.tz_localize(None)
            df_filtered = df_filtered[col_dates >= start_dt]
    elif selected_dates:
        start_dt = pd.to_datetime(f"{selected_dates} 00:00:00")
        end_dt = pd.to_datetime(f"{selected_dates} 23:59:59")
        if getattr(start_dt, "tzinfo", None) is not None:
            start_dt = start_dt.tz_localize(None)
        if getattr(end_dt, "tzinfo", None) is not None:
            end_dt = end_dt.tz_localize(None)
        col_dates = pd.to_datetime(df_filtered["Fecha_Ultimo_Mensaje"], errors="coerce")
        if hasattr(col_dates.dt, "tz") and col_dates.dt.tz is not None:
            col_dates = col_dates.dt.tz_localize(None)
        df_filtered = df_filtered[(col_dates >= start_dt) & (col_dates <= end_dt)]

    # Filtro campañas
    if selected_camps:
        df_filtered = df_filtered[df_filtered["Campana_Origen"].isin(selected_camps)]

    # Filtro productos
    if selected_prods:
        df_filtered = df_filtered[df_filtered["Producto_Principal"].isin(selected_prods)]

    # Filtro intenciones
    if selected_intents:
        df_filtered = df_filtered[df_filtered["Intencion_Principal"].isin(selected_intents)]

    # Filtro búsqueda
    if search_q.strip():
        q_clean = search_q.strip().lower()
        mask_search = (
            df_filtered["Cliente"].str.lower().str.contains(q_clean, na=False) |
            df_filtered["Telefono"].str.lower().str.contains(q_clean, na=False) |
            df_filtered["Que_Pide_El_Cliente"].str.lower().str.contains(q_clean, na=False) |
            df_filtered["Cultivo_Aplicacion"].str.lower().str.contains(q_clean, na=False) |
            df_filtered["Objeciones"].str.lower().str.contains(q_clean, na=False) |
            df_filtered["Provincia"].str.lower().str.contains(q_clean, na=False)
        )
        df_filtered = df_filtered[mask_search]

    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

    # =========================================================================
    # TARJETAS DE KPIS DINÁMICOS
    # =========================================================================
    k1, k2, k3, k4, k5 = st.columns(5)

    tot_convs = len(df_filtered)
    tot_msgs = int(df_filtered["Total_Mensajes"].sum()) if tot_convs > 0 else 0
    pide_presupuesto = int(df_filtered["Intenciones_Detectadas"].apply(
        lambda l: any("Presupuesto" in x for x in l) if isinstance(l, list) else False
    ).sum()) if tot_convs > 0 else 0
    pide_meet = int(df_filtered["Intenciones_Detectadas"].apply(
        lambda l: any("Reunión" in x for x in l) if isinstance(l, list) else False
    ).sum()) if tot_convs > 0 else 0
    top_prod = df_filtered["Producto_Principal"].mode()[0] if tot_convs > 0 else "N/A"

    pct_presup = (pide_presupuesto / tot_convs * 100) if tot_convs > 0 else 0.0

    with k1:
        _render_metric_card("Clientes en Vista", f"{tot_convs:,}", f"de {len(df_chats):,} analizados", "#895522")
    with k2:
        _render_metric_card("Mensajes en Vista", f"{tot_msgs:,}", f"{df_filtered['Mensajes_Entrantes'].sum():,} entrantes", "#B18450")
    with k3:
        _render_metric_card("Piden Cotización", f"{pide_presupuesto}", f"{pct_presup:.1f}% de tasa comercial", "#47664F")
    with k4:
        _render_metric_card("Piden Reunión / Meet", f"{pide_meet}", "Agendas pendientes", "#9B732A")
    with k5:
        _render_metric_card("Mayor Demanda", top_prod.split("(")[0].strip()[:18], "Producto líder", "#985A4E")

    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

    if df_filtered.empty:
        st.info("ℹ️ No hay conversaciones que coincidan con la combinación de filtros seleccionada. Ajuste las fechas o campañas.")
        return

    # =========================================================================
    # PESTAÑAS DE VISUALIZACIÓN Y ANÁLISIS
    # =========================================================================
    tab_overview, tab_table, tab_chat = st.tabs([
        "Matriz y Gráficos de Demanda",
        "Catálogo Discriminado de Prospectos",
        "Visor 360° de Conversación & Diagnóstico IA",
    ])

    # -------------------------------------------------------------------------
    # TAB 1: GRÁFICOS Y DISCRIMINACIÓN VISUAL
    # -------------------------------------------------------------------------
    with tab_overview:
        g1, g2 = st.columns([1.2, 1.2])

        with g1:
            st.markdown("##### ¿Qué productos piden los clientes?")
            prod_counts = df_filtered["Producto_Principal"].value_counts().reset_index()
            prod_counts.columns = ["Producto", "Clientes"]
            fig_prod = px.pie(
                prod_counts,
                values="Clientes",
                names="Producto",
                hole=0.45,
                color_discrete_sequence=["#895522", "#536B70", "#47664F", "#9B732A", "#985A4E", "#80634F", "#64748b"],
            )
            fig_prod.update_layout(
                template="fauvor",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=340,
                margin=dict(l=20, r=20, t=10, b=10),
                legend=dict(orientation="v", y=0.5, font=dict(size=12)),
            )
            st.plotly_chart(fig_prod, width="stretch")

        with g2:
            st.markdown("##### ¿Qué tipo de requerimiento tienen?")
            intent_counts = df_filtered["Intencion_Principal"].value_counts().reset_index()
            intent_counts.columns = ["Requerimiento", "Clientes"]
            fig_intent = px.bar(
                intent_counts,
                x="Clientes",
                y="Requerimiento",
                orientation="h",
                color="Clientes",
                color_continuous_scale="Viridis",
            )
            fig_intent.update_layout(
                template="fauvor",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                height=340,
                margin=dict(l=20, r=20, t=10, b=10),
                yaxis=dict(autorange="reversed"),
                coloraxis_showscale=False,
            )
            st.plotly_chart(fig_intent, width="stretch")

        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

        g3, g4 = st.columns([1.5, 1])

        with g3:
            st.markdown("##### Demanda por Campaña Publicitaria de Origen")

            camp_view_mode = st.radio(
                "Modo de vista campaña:",
                ["Ranking Total de Clientes", "Desglose por Producto"],
                horizontal=True,
                label_visibility="collapsed",
                key="ai_camp_view_mode",
            )

            camp_counts = df_filtered["Campana_Origen"].value_counts().reset_index()
            camp_counts.columns = ["Campana", "Clientes"]
            camp_counts = camp_counts.sort_values(by="Clientes", ascending=True)

            if camp_view_mode == "Ranking Total de Clientes":
                top_prods = (
                    df_filtered.groupby("Campana_Origen")["Producto_Principal"]
                    .agg(lambda s: s.mode()[0] if not s.empty else "-")
                    .to_dict()
                )
                camp_counts["Producto_Lider"] = camp_counts["Campana"].map(top_prods)
                tot_c = len(df_filtered)
                camp_counts["Pct"] = (camp_counts["Clientes"] / tot_c * 100) if tot_c > 0 else 0.0

                fig_camp = px.bar(
                    camp_counts,
                    x="Clientes",
                    y="Campana",
                    orientation="h",
                    text="Clientes",
                    color="Clientes",
                    color_continuous_scale=[[0, "#895522"], [0.5, "#895522"], [1.0, "#4338ca"]],
                    custom_data=["Producto_Lider", "Pct"],
                )
                fig_camp.update_traces(
                    textposition="outside",
                    texttemplate="<b>%{text}</b>",
                    textfont=dict(size=12, color="#2B211A"),
                    hovertemplate="<b>%{y}</b><br>Clientes: <b>%{x}</b> (%{customdata[1]:.1f}%)<br>Línea Principal: <b>%{customdata[0]}</b><extra></extra>",
                    marker=dict(line=dict(width=0)),
                )
                fig_camp.update_layout(
                    template="fauvor",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=max(330, len(camp_counts) * 44),
                    margin=dict(l=10, r=45, t=10, b=10),
                    xaxis=dict(title="", showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
                    yaxis=dict(title="", tickfont=dict(size=12, color="#2B211A")),
                    coloraxis_showscale=False,
                )
            else:
                camp_prod = pd.crosstab(df_filtered["Campana_Origen"], df_filtered["Producto_Principal"]).reindex(camp_counts["Campana"])
                fig_camp = px.bar(
                    camp_prod,
                    orientation="h",
                    barmode="stack",
                    color_discrete_sequence=["#47664F", "#9B732A", "#895522", "#536B70", "#985A4E", "#80634F", "#64748b"],
                )
                fig_camp.update_layout(
                    template="fauvor",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=max(340, len(camp_counts) * 44),
                    margin=dict(l=10, r=20, t=10, b=65),
                    legend=dict(
                        orientation="h",
                        y=-0.22,
                        x=0.5,
                        xanchor="center",
                        font=dict(size=10),
                        title=dict(text=""),
                    ),
                    xaxis=dict(title="", showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
                    yaxis=dict(title="", tickfont=dict(size=12, color="#2B211A")),
                )
            st.plotly_chart(fig_camp, width="stretch")

        with g4:
            st.markdown("##### Cultivos y Aplicaciones Más Frecuentes")
            crops_list = []
            for c in df_filtered["Cultivo_Aplicacion"].dropna():
                if c != "No especificado":
                    crops_list.extend([x.strip() for x in c.split(",")])
            if crops_list:
                df_crops = pd.Series(crops_list).value_counts().head(8).reset_index()
                df_crops.columns = ["Cultivo", "Menciones"]
                fig_crop = px.bar(
                    df_crops,
                    x="Menciones",
                    y="Cultivo",
                    orientation="h",
                    color="Menciones",
                    color_continuous_scale="Teal",
                )
                fig_crop.update_layout(
                    template="fauvor",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=340,
                    margin=dict(l=10, r=10, t=20, b=20),
                    yaxis=dict(autorange="reversed"),
                    coloraxis_showscale=False,
                )
                st.plotly_chart(fig_crop, width="stretch")
            else:
                st.info("Sin mención explícita de cultivos en este recorte.")

    # -------------------------------------------------------------------------
    # TAB 2: CATÁLOGO DISCRIMINADO Y TABLA
    # -------------------------------------------------------------------------
    with tab_table:
        st.markdown("##### Listado Detallado de Prospectos y lo que Piden")
        st.caption(f"Mostrando **{len(df_filtered)}** prospectos clasificados. Puede ordenar por columnas o exportar a Excel.")

        # Botón de exportación
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            export_cols = [
                "Cliente", "Telefono", "Campana_Origen", "Producto_Principal",
                "Intencion_Principal", "Que_Pide_El_Cliente", "Cultivo_Aplicacion",
                "Objeciones", "Temperatura", "Total_Mensajes", "Fecha_Ultimo_Str",
                "Provincia", "Accion_Sugerida"
            ]
            df_filtered[export_cols].to_excel(writer, sheet_name="Informes_IA_Demandas", index=False)
        st.download_button(
            label=f"Descargar Reporte en Excel ({len(df_filtered)} registros)",
            data=output.getvalue(),
            file_name="nexo_analytics_informe_demandas_ia.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        display_df = df_filtered[[
            "Cliente", "Telefono", "Campana_Origen", "Producto_Principal",
            "Intencion_Principal", "Que_Pide_El_Cliente", "Cultivo_Aplicacion",
            "Temperatura", "Fecha_Ultimo_Str"
        ]].copy()
        display_df.columns = [
            "Cliente", "Teléfono", "Campaña Origen", "Producto",
            "Intención", "¿Qué pide exactamente?", "Cultivo",
            "Prioridad", "Último Contacto"
        ]

        st.dataframe(
            display_df,
            width="stretch",
            hide_index=True,
            height=480,
        )

    # -------------------------------------------------------------------------
    # TAB 3: VISOR 360° DE CONVERSACIÓN & DIAGNÓSTICO IA
    # -------------------------------------------------------------------------
    with tab_chat:
        st.markdown("##### Visor 360° de Conversación & Diagnóstico con IA")
        st.caption("Seleccione cualquier cliente para inspeccionar el chat completo, analizar objeciones y responder con 1 clic.")

        client_options = {
            f"{row['Cliente']} ({row['Telefono']}) - {row['Producto_Principal'].split('(')[0].strip()}": row
            for _, row in df_filtered.iterrows()
        }

        if not client_options:
            st.info("No hay clientes disponibles con los filtros actuales.")
            return

        selected_label = st.selectbox(
            "Seleccionar Cliente / Conversación:",
            options=list(client_options.keys()),
            key="ai_view_selected_client",
        )

        selected_row = client_options[selected_label]

        col_c_info, col_c_chat = st.columns([1.1, 1.4])

        with col_c_info:
            st.markdown(f"""
            <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 12px; padding: 18px 20px; margin-bottom: 16px;">
                <h4 style="margin: 0 0 12px 0; color: #895522; font-size: 20px; font-weight: 700;">{selected_row['Cliente']}</h4>
                <p style="margin: 4px 0; font-size: 16.5px; color: #2B211A;"><b>Teléfono:</b> <code>{selected_row['Telefono']}</code></p>
                <p style="margin: 4px 0; font-size: 16.5px; color: #2B211A;"><b>Campaña:</b> <span style="color: #a78bfa;">{selected_row['Campana_Origen']}</span></p>
                <p style="margin: 4px 0; font-size: 16.5px; color: #2B211A;"><b>Producto:</b> {selected_row['Producto_Principal']}</p>
                <p style="margin: 4px 0; font-size: 16.5px; color: #2B211A;"><b>Cultivo:</b> {selected_row['Cultivo_Aplicacion']}</p>
                <p style="margin: 4px 0; font-size: 16.5px; color: #2B211A;"><b>Ubicación:</b> {selected_row['Localidad']}, {selected_row['Provincia']}</p>
                <p style="margin: 4px 0; font-size: 16.5px; color: #2B211A;"><b>Prioridad:</b> {selected_row['Temperatura']}</p>
                <p style="margin: 4px 0; font-size: 16.5px; color: #2B211A;"><b>Mensajes:</b> {selected_row['Total_Mensajes']} ({selected_row['Mensajes_Entrantes']} de cliente)</p>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div style="background: rgba(15, 23, 42, 0.6); border-left: 4px solid #47664F; border-radius: 8px; padding: 14px 16px; margin-bottom: 14px;">
                <b style="color: #47664F; font-size: 14.5px; text-transform: uppercase; letter-spacing: 0.5px;">Síntesis de la Demanda:</b>
                <p style="margin: 6px 0 0 0; color: #2B211A; font-size: 16.5px; line-height: 1.55;">""" + selected_row["Que_Pide_El_Cliente"] + """</p>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("""
            <div style="background: rgba(15, 23, 42, 0.6); border-left: 4px solid #9B732A; border-radius: 8px; padding: 14px 16px; margin-bottom: 14px;">
                <b style="color: #9B732A; font-size: 14.5px; text-transform: uppercase; letter-spacing: 0.5px;">Acción Comercial Sugerida:</b>
                <p style="margin: 6px 0 0 0; color: #2B211A; font-size: 16.5px; line-height: 1.55;">""" + selected_row["Accion_Sugerida"] + """</p>
            </div>
            """, unsafe_allow_html=True)

            st.link_button(
                "Abrir Chat en WhatsApp con Respuesta Sugerida",
                url=selected_row["WhatsApp_Link"],
                width="stretch",
            )

            # Botón opcional para análisis con Copiloto IA (API LLM)
            ai_stat = get_ai_status(force_refresh=False)
            if ai_stat.get("available"):
                if st.button("Generar Diagnóstico con Copiloto IA", width="stretch"):
                    with st.spinner("Analizando conversación con Copiloto IA..."):
                        diag = analyze_conversation_history(
                            messages=selected_row.get("Historial_Mensajes", []),
                            client_name=selected_row.get("Cliente", "Cliente"),
                        )
                        st.markdown("##### Diagnóstico IA en Tiempo Real:")
                        topics = ", ".join(diag.get("key_topics", [])) or "No especificados"
                        issues = ", ".join(diag.get("pending_issues", [])) or "Sin objeciones detectadas"
                        st.markdown(f"""
                        <div style="background: rgba(30, 41, 59, 0.9); border: 1px solid #895522; border-radius: 10px; padding: 16px; font-size: 16.5px; color: #2B211A;">
                            <p style="margin: 0 0 6px 0;"><b>Resumen:</b> {diag.get('summary', '-')}</p>
                            <p style="margin: 0 0 6px 0;"><b>Temas Clave:</b> {topics}</p>
                            <p style="margin: 0 0 6px 0;"><b>Objeciones / Pendientes:</b> {issues}</p>
                            <p style="margin: 0;"><b>Estrategia Sugerida:</b> <span style="color: #47664F;">{diag.get('next_step', '-')}</span></p>
                        </div>
                        """, unsafe_allow_html=True)

        with col_c_chat:
            st.markdown("##### Historial del Chat en WhatsApp")
            chat_history = selected_row.get("Historial_Mensajes", [])
            if chat_history:
                chat_container_html = "<div style='max-height: 480px; overflow-y: auto; padding: 14px; background: rgba(15, 23, 42, 0.7); border-radius: 12px; border: 1px solid rgba(51, 65, 85, 0.4);'>"
                for m in chat_history:
                    is_me = m.get("is_from_me")
                    align = "flex-end" if is_me else "flex-start"
                    bg_color = "rgba(16, 185, 129, 0.25)" if is_me else "rgba(51, 65, 85, 0.7)"
                    border_color = "#47664F" if is_me else "#475569"
                    sender_lbl = "Empresa" if is_me else selected_row["Cliente"]
                    time_lbl = m.get("timestamp", "")

                    m_text_clean = m.get('text', '').replace('\n', '<br>')
                    chat_container_html += (
                        f'<div style="display: flex; justify-content: {align}; margin-bottom: 12px;">'
                        f'<div style="max-width: 82%; background: {bg_color}; border: 1px solid {border_color}; border-radius: 10px; padding: 10px 14px;">'
                        f'<div style="display: flex; justify-content: space-between; gap: 12px; font-size: 13.5px; color: #786451; margin-bottom: 4px;">'
                        f'<b>{sender_lbl}</b><span>{time_lbl}</span>'
                        f'</div>'
                        f'<div style="font-size: 16.5px; color: #2B211A; line-height: 1.5;">{m_text_clean}</div>'
                        f'</div>'
                        f'</div>'
                    )
                chat_container_html += "</div>"
                st.markdown(chat_container_html, unsafe_allow_html=True)
            else:
                st.info("No hay mensajes de texto registrados en esta conversación.")


def _render_metric_card(label: str, value: str, caption: str, accent_color: str) -> None:
    """Renderiza una tarjeta métrica con diseño glassmorphism ampliado."""
    st.markdown(f"""
    <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(148, 163, 184, 0.15);
                border-top: 3.5px solid {accent_color}; border-radius: 14px; padding: 18px 20px; margin-bottom: 14px;
                min-height: 130px; display: flex; flex-direction: column; justify-content: space-between;">
        <div style="font-size: 15px; color: #786451; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{label}</div>
        <div style="font-size: 34px; color: #2B211A; font-weight: 800; margin: 6px 0 4px 0; line-height: 1.15;">{value}</div>
        <div style="font-size: 15px; color: #786451; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{caption}</div>
    </div>
    """, unsafe_allow_html=True)
