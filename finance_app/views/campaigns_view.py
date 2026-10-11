"""
Nexo Analytics - Vista de Auditoría y Gestión de Campañas Publicitarias (Streamlit)
Métricas de Meta Ads, rendimiento por producto, remarketing CRM y proyecciones de inversión.
"""

from __future__ import annotations
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional, Any

from finance_app.commercial_analytics import CommercialAnalyticsResult


def _money(val: float | int | None) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "$0"
    return f"${val:,.0f}".replace(",", ".")


def _render_kpi_card(title: str, value: str, subtext: str, color: str = "#38bdf8"):
    """Renderiza una tarjeta KPI con microestilos corporativos oscuros y alta legibilidad."""
    st.markdown(f"""
    <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255,255,255,0.12); 
                border-top: 4px solid {color}; border-radius: 12px; padding: 18px 16px; text-align: center;
                box-shadow: 0 4px 14px rgba(0,0,0,0.3); min-height: 140px; display: flex; flex-direction: column; justify-content: space-between;">
        <div style="font-size: 16px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.8px;">{title}</div>
        <div style="font-size: 38px; font-weight: 800; color: #f8fafc; margin: 6px 0; line-height: 1.15;">{value}</div>
        <div style="font-size: 15.5px; color: {color}; font-weight: 600;">{subtext}</div>
    </div>
    """, unsafe_allow_html=True)


def _render_meta_ads_live_tab(comm: Optional[CommercialAnalyticsResult]):
    """Renderiza el panel de conexión directa con la API de Meta Ads (Solo Lectura)."""
    import datetime
    from finance_app.services.meta_ads_service import (
        get_meta_ads_status,
        fetch_meta_ads_insights,
        generate_demo_meta_campaigns,
        merge_meta_insights_into_commercial_result,
        build_commercial_dataframe_from_meta,
        MetaCampaignInsight,
    )

    st.markdown("#### 🔗 Conexión Oficial con Meta Marketing API")
    st.caption("Extracción directa de métricas de campañas activas en Facebook e Instagram Ads en modo estricto de **Solo Lectura (Read-Only)**.")

    status = get_meta_ads_status()

    col_stat1, col_stat2 = st.columns([2, 1.2])

    with col_stat1:
        if status["configured"]:
            st.markdown(f"""
            <div style="background: rgba(16, 185, 129, 0.12); border: 1.5px solid #10b981; border-radius: 10px; padding: 14px 18px; margin-bottom: 15px;">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <div>
                        <div style="font-size: 16px; font-weight: 800; color: #34d399;">● Conectado a Meta Graph API ({status['api_version']})</div>
                        <div style="font-size: 13.5px; color: #cbd5e1; margin-top: 3px;">Cuenta Publicitaria: <code>{status['ad_account_id']}</code></div>
                        <div style="font-size: 12.5px; color: #94a3b8; margin-top: 2px;">Permisos: <b>ads_read, read_insights</b> (Solo Lectura · Sin riesgo de modificación)</div>
                    </div>
                    <span style="font-size: 32px;">🛡️</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background: rgba(56, 189, 248, 0.10); border: 1.5px solid #38bdf8; border-radius: 10px; padding: 14px 18px; margin-bottom: 15px;">
                <div style="font-size: 16px; font-weight: 800; color: #38bdf8;">📡 Conexión con Meta Marketing API</div>
                <div style="font-size: 13.5px; color: #cbd5e1; margin-top: 4px;">
                    Para leer las campañas activas directamente de Meta, configure <code>META_ACCESS_TOKEN</code> y <code>META_AD_ACCOUNT_ID</code> en el archivo <code>.env</code> o pruébelo interactivamente abajo.
                </div>
                <div style="font-size: 12px; color: #94a3b8; margin-top: 6px;">
                    Garantía: La API opera únicamente con permisos <code>ads_read</code> y <code>read_insights</code> (imposible modificar o pausar anuncios).
                </div>
            </div>
            """, unsafe_allow_html=True)

    with col_stat2:
        date_preset = st.selectbox(
            "Período de Análisis:",
            ["maximum", "this_month", "last_30d", "last_90d", "this_year"],
            format_func=lambda x: {
                "maximum": "Histórico Completo (Maximum)",
                "this_month": "Mes en Curso",
                "last_30d": "Últimos 30 días",
                "last_90d": "Últimos 90 días",
                "this_year": "Año en Curso",
            }.get(x, x),
            key="meta_date_preset"
        )

    # Botones de acción
    col_btn1, col_btn2, col_btn3 = st.columns([1.5, 1.5, 1.2])

    with col_btn1:
        if st.button("🔄 Sincronizar desde Meta Ads", type="primary", use_container_width=True, key="btn_sync_meta_live"):
            with st.spinner("Consultando Meta Marketing API (Solo Lectura)..."):
                ok, err, insights = fetch_meta_ads_insights(date_preset=date_preset)
                if ok and insights:
                    st.session_state["meta_live_insights"] = insights
                    st.session_state["meta_sync_time"] = datetime.datetime.now().strftime("%H:%M:%S")
                    st.success(f"✓ {len(insights)} campañas obtenidas de Meta Ads.")
                    st.rerun()
                else:
                    st.error(f"Error al conectar con Meta Ads: {err}")

    with col_btn2:
        if st.button("🧪 Probar con Demo de Campañas", use_container_width=True, key="btn_sync_meta_demo"):
            demo_insights = generate_demo_meta_campaigns()
            st.session_state["meta_live_insights"] = demo_insights
            st.session_state["meta_sync_time"] = datetime.datetime.now().strftime("%H:%M:%S") + " (Simulación Demo)"
            st.info(f"✓ 5 campañas demo cargadas para previsualización.")
            st.rerun()

    with col_btn3:
        if st.session_state.get("meta_live_insights"):
            if st.button("🧹 Limpiar", use_container_width=True, key="btn_clear_meta_insights"):
                st.session_state["meta_live_insights"] = None
                st.rerun()

    # Si hay insights cargados
    insights_list: List[MetaCampaignInsight] = st.session_state.get("meta_live_insights", [])
    if insights_list:
        st.markdown("---")
        st.markdown(f"##### 📊 Métricas en Vivo de Meta Ads (Actualizado: {st.session_state.get('meta_sync_time', '')})")

        m_inv = sum(i.spend for i in insights_list)
        m_alc = sum(i.reach for i in insights_list)
        m_conv = sum(i.conversations for i in insights_list)
        m_cpl = (m_inv / m_conv) if m_conv > 0 else 0.0

        mc1, mc2, mc3, mc4 = st.columns(4)
        with mc1:
            _render_kpi_card("Inversión Meta Ads", _money(m_inv), f"{len(insights_list)} campañas activas", "#38bdf8")
        with mc2:
            _render_kpi_card("Conversaciones / Leads", f"{m_conv:,}", "Generadas en Meta", "#10b981")
        with mc3:
            _render_kpi_card("CPL Promedio Meta", _money(m_cpl), "Por conversación", "#f59e0b")
        with mc4:
            _render_kpi_card("Alcance Total Meta", f"{m_alc:,}", "Impactos directos", "#a855f7")

        st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

        df_meta = build_commercial_dataframe_from_meta(insights_list)
        
        # Botón para inyectar en el resultado comercial global
        col_apply, col_info = st.columns([1.5, 2.5], vertical_alignment="center")
        with col_apply:
            if st.button("📥 Aplicar a toda la Plataforma (Dashboard + PDF)", type="primary", use_container_width=True, key="btn_apply_meta_to_global"):
                updated_comm = merge_meta_insights_into_commercial_result(comm, insights_list)
                st.session_state["comm_data"] = updated_comm
                st.session_state["comm_source_name"] = "Meta Marketing API (En vivo)"
                st.success("✓ Base comercial actualizada con datos en vivo de Meta Ads.")
                st.rerun()
        with col_info:
            st.caption("Al aplicar, todos los gráficos, el funnel comercial y el **Informe Ejecutivo en PDF** se generarán con los datos en vivo de Meta Ads.")

        st.dataframe(
            df_meta[["Campaña", "Producto", "Inversion_ARS", "Alcance", "Conversaciones", "CPL_ARS", "CPM_ARS", "Objetivo"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Inversion_ARS": st.column_config.NumberColumn("Inversión ($ ARS)", format="$ %,.0f"),
                "CPL_ARS": st.column_config.NumberColumn("CPL ($ ARS)", format="$ %,.2f"),
                "CPM_ARS": st.column_config.NumberColumn("CPM ($ ARS)", format="$ %,.2f"),
                "Alcance": st.column_config.NumberColumn("Alcance", format="%,d"),
                "Conversaciones": st.column_config.NumberColumn("Conversaciones", format="%,d"),
            }
        )


def render_campaigns_view(comm: Optional[CommercialAnalyticsResult], sheets: dict, master: pd.DataFrame, df_filtered: pd.DataFrame):
    """Renderiza el módulo integral de Campañas Publicitarias y Remarketing."""
    st.markdown("## Gestión & Auditoría de Campañas Publicitarias")
    st.caption("Control integral de inversión en Meta Ads, rendimiento por línea, campañas de remarketing y proyecciones de pauta.")

    has_comm_data = comm is not None and comm.df_spend is not None and not comm.df_spend.empty
    if has_comm_data:
        df_spend = comm.df_spend.copy()
        total_inv = float(df_spend["Inversion_ARS"].sum())
        total_conv = int(df_spend["Conversaciones"].sum())
        total_reach = int(df_spend["Alcance"].sum())
        cpl_global = (total_inv / total_conv) if total_conv > 0 else 0.0

        with_conv = df_spend[df_spend["Conversaciones"] > 0]
        best_cpl_campaign = "N/A"
        best_cpl_val = 0.0
        if not with_conv.empty:
            best_row = with_conv.sort_values("CPL_ARS", ascending=True).iloc[0]
            best_cpl_campaign = f"{best_row['Producto']} ({best_row['Mes']})"
            best_cpl_val = float(best_row["CPL_ARS"])
    else:
        df_spend = pd.DataFrame()
        total_inv = 0.0
        total_conv = 0
        total_reach = 0
        cpl_global = 0.0
        best_cpl_campaign = "N/A"
        best_cpl_val = 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _render_kpi_card("Inversión Total Pauta", _money(total_inv), f"{len(df_spend)} partidas registradas", "#38bdf8")
    with c2:
        _render_kpi_card("Conversaciones Pauta", f"{total_conv:,}", f"{total_reach:,} alcance total", "#10b981")
    with c3:
        _render_kpi_card("CPL Promedio Global", _money(cpl_global), "Costo por conversación", "#f59e0b")
    with c4:
        _render_kpi_card("Alcance Publicitario", f"{total_reach:,}", "Impactos directos", "#a855f7")
    with c5:
        _render_kpi_card("Campaña Más Eficiente", _money(best_cpl_val), best_cpl_campaign, "#06b6d4")

    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

    # -------------------------------------------------------------
    # PESTAÑAS PRINCIPALES DEL MÓDULO
    # -------------------------------------------------------------
    tab_meta_live, tab_ads, tab_remarketing, tab_audit = st.tabs([
        "📡 Meta Ads API (En Vivo)",
        "Rendimiento de Campañas (Histórico)",
        "Remarketing & Proyección Comercial",
        "Redes Sociales & Auditoría Técnica",
    ])

    with tab_meta_live:
        _render_meta_ads_live_tab(comm)

    # -------------------------------------------------------------
    # TAB 2: RENDIMIENTO DE CAMPAÑAS META ADS HISTÓRICO
    # -------------------------------------------------------------
    with tab_ads:
        st.markdown("#### Auditoría y Desglose de Campañas Publicitarias")
        if df_spend.empty:
            st.info("No hay datos históricos cargados de Comercial.xlsx. Utilice la pestaña 'Meta Ads API' para sincronizar campañas en vivo.")
            return

        # Filtros locales interactivos
        f_col1, f_col2 = st.columns([1, 1])
        with f_col1:
            all_months = ["Todos"] + sorted(list(df_spend["Mes"].unique()), key=lambda x: ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'].index(x) if x in ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'] else 99)
            sel_month = st.selectbox("Filtrar por Mes:", all_months, key="camp_filter_month")
        with f_col2:
            camp_types = ["Todas las Campañas", "Solo Meta Ads Explícitas", "Campañas por Producto"]
            sel_type = st.selectbox("Tipo de Campaña:", camp_types, key="camp_filter_type")


        # Aplicar filtros
        filtered_spend = df_spend.copy()
        if sel_month != "Todos":
            filtered_spend = filtered_spend[filtered_spend["Mes"] == sel_month]

        if sel_type == "Solo Meta Ads Explícitas":
            filtered_spend = filtered_spend[filtered_spend["Producto"].str.contains("Meta Ads", case=False, na=False)]
        elif sel_type == "Campañas por Producto":
            filtered_spend = filtered_spend[~filtered_spend["Producto"].str.contains("Meta Ads", case=False, na=False)]

        if filtered_spend.empty:
            st.info("No se encontraron campañas con los filtros seleccionados.")
        else:
            # Gráficos de Inversión y Conversiones
            col_g1, col_g2 = st.columns(2)

            with col_g1:
                st.markdown("##### Inversión y Conversaciones por Campaña")
                fig_bar = px.bar(
                    filtered_spend,
                    x="Inversion_ARS",
                    y="Producto",
                    orientation="h",
                    color="CPL_ARS",
                    color_continuous_scale="Viridis_r",
                    hover_data=["Mes", "Alcance", "Conversaciones", "CPL_ARS"],
                    labels={
                        "Inversion_ARS": "Inversión ($ ARS)",
                        "Producto": "Campaña / Línea",
                        "CPL_ARS": "CPL ($)",
                    },
                    title="Inversión ($ ARS) coloreada por CPL (Más oscuro = menor costo)",
                    template="plotly_dark",
                )
                fig_bar.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(tickprefix="$", showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
                    yaxis=dict(autorange="reversed"),
                    height=380,
                )
                st.plotly_chart(fig_bar, use_container_width=True)

            with col_g2:
                st.markdown("##### ⚖️ Matriz de Eficiencia (CPL vs Conversaciones)")
                # Filtrar campañas con inversión para el scatter
                scatter_df = filtered_spend[filtered_spend["Inversion_ARS"] > 0].copy()
                scatter_df["Tamaño_Burbuja"] = scatter_df["Alcance"].apply(lambda x: max(x, 2000))
                
                fig_scatter = px.scatter(
                    scatter_df,
                    x="Inversion_ARS",
                    y="Conversaciones",
                    size="Tamaño_Burbuja",
                    color="CPL_ARS",
                    color_continuous_scale="Portland_r",
                    hover_name="Producto",
                    hover_data=["Mes", "CPL_ARS", "Alcance"],
                    labels={
                        "Inversion_ARS": "Inversión ($ ARS)",
                        "Conversaciones": "Conversaciones Generadas",
                        "CPL_ARS": "CPL ($)",
                    },
                    title="Eficiencia: Inversión vs Conversaciones (Tamaño = Alcance)",
                    template="plotly_dark",
                )
                fig_scatter.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(tickprefix="$", showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
                    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
                    height=380,
                )
                st.plotly_chart(fig_scatter, use_container_width=True)

            # Evolución Temporal de Campañas
            st.markdown("##### Evolución Mensual del Costo por Lead (CPL) y Volumen")
            monthly_agg = df_spend.groupby("Mes", sort=False).agg(
                Inversion_ARS=("Inversion_ARS", "sum"),
                Conversaciones=("Conversaciones", "sum"),
            ).reset_index()
            monthly_agg["CPL_Mes"] = monthly_agg.apply(
                lambda r: (r["Inversion_ARS"] / r["Conversaciones"]) if r["Conversaciones"] > 0 else 0, axis=1
            )

            fig_trend = go.Figure()
            fig_trend.add_trace(go.Bar(
                x=monthly_agg["Mes"],
                y=monthly_agg["Inversion_ARS"],
                name="Inversión ($ ARS)",
                marker_color="#38bdf8",
                yaxis="y",
            ))
            fig_trend.add_trace(go.Scatter(
                x=monthly_agg["Mes"],
                y=monthly_agg["CPL_Mes"],
                name="CPL Mensual ($)",
                mode="lines+markers+text",
                text=[f"${v:,.0f}" if v > 0 else "-" for v in monthly_agg["CPL_Mes"]],
                textposition="top center",
                line=dict(color="#f59e0b", width=3),
                marker=dict(size=8, color="#f59e0b"),
                yaxis="y2",
            ))
            fig_trend.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(title="Inversión ($ ARS)", tickprefix="$", showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
                yaxis2=dict(title="CPL ($)", overlaying="y", side="right", tickprefix="$", showgrid=False),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                height=340,
            )
            st.plotly_chart(fig_trend, use_container_width=True)

            # Tabla Matriz Detallada
            st.markdown("##### Matriz Detallada de Campañas")
            table_display = filtered_spend.copy()
            table_display["Eficiencia"] = table_display.apply(
                lambda r: "Alta" if 0 < r["CPL_ARS"] <= 2500 else "Media" if 2500 < r["CPL_ARS"] <= 4000 else "A Optimizar" if r["CPL_ARS"] > 4000 else "Sin Conversiones",
                axis=1
            )
            table_display["Inversión ($)"] = table_display["Inversion_ARS"].apply(lambda v: f"${v:,.2f}")
            table_display["Alcance"] = table_display["Alcance"].apply(lambda v: f"{v:,}" if v > 0 else "No inf.")
            table_display["Conversaciones"] = table_display["Conversaciones"].apply(lambda v: f"{v:,}" if v > 0 else "-")
            table_display["CPL ($)"] = table_display["CPL_ARS"].apply(lambda v: f"${v:,.2f}" if v > 0 else "-")
            table_display["CPM ($)"] = table_display["CPM_ARS"].apply(lambda v: f"${v:,.2f}" if v > 0 else "-")

            cols_order = ["Mes", "Producto", "Inversión ($)", "Alcance", "Conversaciones", "CPL ($)", "CPM ($)", "Eficiencia"]
            st.dataframe(table_display[cols_order], width="stretch", hide_index=True)

    # -------------------------------------------------------------
    # TAB 2: REMARKETING & PROYECCIÓN COMERCIAL
    # -------------------------------------------------------------
    with tab_remarketing:
        st.markdown("#### Análisis de Remarketing & Planificación de Presupuesto")

        col_rem1, col_rem2 = st.columns([1.2, 1])

        with col_rem1:
            st.markdown("##### Impacto de Campaña de Remarketing CRM")
            # Extraer métricas de remarketing de master si existe
            rem_col = None
            for c in master.columns:
                if "remarketing" in str(c).lower():
                    rem_col = c
                    break

            if rem_col is not None:
                rem_leads = master[master[rem_col] == 1]
                total_rem = len(rem_leads)
                
                # Conversión de remarketing
                conv_col = "ESTADO_HOMOLOGADO" if "ESTADO_HOMOLOGADO" in master.columns else None
                conv_rem = 0
                if conv_col:
                    conv_rem = int(rem_leads[conv_col].isin(["GANADO", "CONVERTIDO", "DERIVADO"]).sum())
                
                tasa_rem = (conv_rem / total_rem * 100) if total_rem > 0 else 0.0

                r_k1, r_k2, r_k3 = st.columns(3)
                with r_k1:
                    _render_kpi_card("Leads en Remarketing", f"{total_rem:,}", "Campaña 01/06/26", "#38bdf8")
                with r_k2:
                    _render_kpi_card("Leads Convertidos", f"{conv_rem:,}", "Oportunidades ganadas", "#10b981")
                with r_k3:
                    _render_kpi_card("Tasa de Cierre Rem.", f"{tasa_rem:.1f}%", "Efectividad recontacto", "#f59e0b")

                st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)
                
                # Distribución de leads de remarketing por producto
                if "PRODUCTO" in rem_leads.columns:
                    rem_by_prod = rem_leads["PRODUCTO"].value_counts().reset_index()
                    rem_by_prod.columns = ["Producto", "Total_Leads"]
                    fig_rem = px.pie(
                        rem_by_prod,
                        names="Producto",
                        values="Total_Leads",
                        title="Distribución de Leads de Remarketing por Línea",
                        template="plotly_dark",
                        hole=0.4,
                    )
                    fig_rem.update_layout(paper_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_rem, use_container_width=True)
            else:
                st.info("No se encontró la columna de remarketing específica en la base de datos actual.")

        with col_rem2:
            st.markdown("##### Simulador / Calculadora de Inversión en Pauta")
            st.caption("Proyecte conversaciones, oportunidades y facturación esperada según los benchmarks históricos.")

            with st.form("form_campaign_simulator"):
                sim_budget = st.number_input(
                    "Presupuesto a Invertir ($ ARS):",
                    min_value=50000.0,
                    max_value=10000000.0,
                    value=300000.0,
                    step=50000.0,
                )
                sim_prod = st.selectbox(
                    "Línea de Producto Objetivo:",
                    ["General (Promedio)", "Davis", "Sentek", "Raphael", "Jardinería", "GSI"],
                )
                sim_ticket = st.number_input(
                    "Ticket Promedio Estimado de Venta ($ ARS):",
                    min_value=100000.0,
                    max_value=20000000.0,
                    value=1500000.0,
                    step=100000.0,
                )
                btn_sim = st.form_submit_button("Calcular Proyección", use_container_width=True)

            # Benchmarks históricos de CPL
            cpl_benchmarks = {
                "General (Promedio)": cpl_global if cpl_global > 0 else 2564.0,
                "Davis": 1896.41,
                "Sentek": 3545.12,
                "Raphael": 2766.20,
                "Jardinería": 3899.72,
                "GSI": 8760.33,
            }
            # Tasa de conversión histórica estimada (~10-15%)
            conv_rate_benchmark = 0.12

            target_cpl = cpl_benchmarks.get(sim_prod, cpl_global)
            est_convs = int(sim_budget / target_cpl) if target_cpl > 0 else 0
            est_sales = max(1, int(est_convs * conv_rate_benchmark))
            est_revenue = est_sales * sim_ticket
            est_roas = (est_revenue / sim_budget) if sim_budget > 0 else 0.0

            st.markdown(f"""
            <div style="background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 12px; padding: 18px 20px; margin-top: 12px;">
                <div style="font-size: 18px; font-weight: 700; color: #38bdf8; margin-bottom: 12px;">Resultados Estimados de la Campaña</div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <span style="color: #cbd5e1; font-size: 16px;">CPL Histórico de Referencia:</span>
                    <b style="color: #f8fafc; font-size: 17px;">{_money(target_cpl)}</b>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <span style="color: #cbd5e1; font-size: 16px;">Conversaciones Esperadas:</span>
                    <b style="color: #10b981; font-size: 17px;">~{est_convs:,} contactos</b>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <span style="color: #cbd5e1; font-size: 16px;">Ventas Proyectadas (12% tasa):</span>
                    <b style="color: #f8fafc; font-size: 17px;">~{est_sales} operaciones</b>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <span style="color: #cbd5e1; font-size: 16px;">Facturación Bruta Proyectada:</span>
                    <b style="color: #38bdf8; font-size: 18px;">{_money(est_revenue)}</b>
                </div>
                <div style="display: flex; justify-content: space-between; border-top: 1px solid rgba(255,255,255,0.15); padding-top: 10px; margin-top: 10px;">
                    <span style="color: #f59e0b; font-size: 16.5px; font-weight: 700;">ROAS Estimado:</span>
                    <b style="color: #f59e0b; font-size: 18px;">{est_roas:.1f}x</b>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # -------------------------------------------------------------
    # TAB 3: REDES SOCIALES & AUDITORÍA TÉCNICA
    # -------------------------------------------------------------
    with tab_audit:
        st.markdown("#### Métricas de Redes Sociales & Auditoría Técnica Oficial")

        col_aud1, col_aud2 = st.columns([1.2, 1])

        with col_aud1:
            st.markdown("##### Rendimiento en Instagram & Formatos de Contenido")
            if comm.df_social is not None and not comm.df_social.empty:
                df_soc = comm.df_social.copy()
                
                # Gráfico de visualizaciones
                if "Visualizaciones reels %" in df_soc.columns and "Visualizaciones historias %" in df_soc.columns:
                    fig_soc = go.Figure()
                    fig_soc.add_trace(go.Bar(
                        x=df_soc["Mes"],
                        y=df_soc["Visualizaciones reels %"],
                        name="Visualizaciones Reels (%)",
                        marker_color="#ec4899",
                    ))
                    fig_soc.add_trace(go.Bar(
                        x=df_soc["Mes"],
                        y=df_soc["Visualizaciones historias %"],
                        name="Visualizaciones Historias (%)",
                        marker_color="#8b5cf6",
                    ))
                    fig_soc.update_layout(
                        barmode="group",
                        template="plotly_dark",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        yaxis=dict(ticksuffix="%", showgrid=True, gridcolor="rgba(255,255,255,0.06)"),
                        height=340,
                        title="Distribución de Visualizaciones por Formato",
                    )
                    st.plotly_chart(fig_soc, use_container_width=True)

                st.dataframe(df_soc, width="stretch", hide_index=True)
            else:
                st.info("No hay datos cargados de redes sociales.")

        with col_aud2:
            st.markdown("##### Observaciones Técnicas de Reportes")
            st.caption("Notas oficiales extraídas de las auditorías de pauta y control de calidad de datos.")

            if comm.df_report_notes is not None and not comm.df_report_notes.empty:
                for _, row in comm.df_report_notes.iterrows():
                    mes = row.get("Mes", "General")
                    obs = row.get("Observación", "")
                    with st.expander(f"Período: {mes}", expanded=False):
                        st.markdown(f"<p style='color: #cbd5e1; font-size: 15.5px; line-height: 1.5;'>{obs}</p>", unsafe_allow_html=True)
            else:
                st.info("No hay notas de auditoría registradas.")
