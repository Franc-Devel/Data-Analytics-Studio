"""
FAUVOR Analytics - Vista de Resumen Ejecutivo y Métricas Consolidadas (Streamlit)
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from finance_app.commercial_analytics import CommercialAnalyticsResult
from finance_app.lead_intelligence import LeadKPISummary


def money(val: float | int) -> str:
    """Formatea moneda en pesos argentinos."""
    return f"${val:,.0f}".replace(",", ".")


def render_kpi_card(title: str, value: str, detail: str, highlight_color: str = "#895522"):
    """Tarjeta de KPI ejecutiva con dark glassmorphism y alta legibilidad."""
    st.markdown(f"""
    <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(255, 255, 255, 0.12); border-radius: 12px; padding: 18px 20px; border-left: 5px solid {highlight_color}; box-shadow: 0 4px 14px rgba(0,0,0,0.3); min-height: 140px; display: flex; flex-direction: column; justify-content: space-between;">
        <div style="font-size: 16px; font-weight: 700; color: #786451; text-transform: uppercase; letter-spacing: 0.8px;">{title}</div>
        <div style="font-size: 38px; font-weight: 800; color: {highlight_color}; margin: 6px 0; line-height: 1.15;">{value}</div>
        <div style="font-size: 15.5px; font-weight: 500; color: #cbd5e1;">{detail}</div>
    </div>
    """, unsafe_allow_html=True)


def render_executive_view(kpis: LeadKPISummary, comm: CommercialAnalyticsResult, total_master_leads: int):
    """Renderiza el resumen ejecutivo con KPIs macro y gráficos de evolución."""
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_kpi_card("Leads Analizados", f"{kpis.total_leads:,}", f"{total_master_leads:,} en base total", "#895522")
    with c2:
        render_kpi_card("Conversión CRM", f"{kpis.tasa_conversion_pct:.1f}%", f"{kpis.convertidos} ganados/derivados", "#4ade80")
    with c3:
        render_kpi_card("Pauta Acumulada", money(comm.kpis.total_inversion_ars), "Inversión 7 meses", "#B18450")
    with c4:
        render_kpi_card("CPL Promedio", money(comm.kpis.cpl_promedio_ars), f"{comm.kpis.total_conversaciones:,} conversaciones", "#c084fc")
    with c5:
        render_kpi_card("Pipeline Cotizado", money(comm.kpis.presupuesto_cotizado_total), f"{comm.kpis.total_oportunidades} cotizaciones", "#f472b6")

    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)

    col_chart, col_prod = st.columns([1.6, 1])

    with col_chart:
        st.markdown("#### Evolución Mensual de Inversión y Conversaciones")
        df_m = comm.df_monthly_summary
        fig_evol = go.Figure()
        fig_evol.add_trace(go.Bar(
            x=df_m["Mes"],
            y=df_m["Inversion_Total"],
            name="Inversión ($)",
            marker_color="#895522",
            yaxis="y",
        ))
        fig_evol.add_trace(go.Scatter(
            x=df_m["Mes"],
            y=df_m["Conversaciones_Total"],
            name="Conversaciones",
            mode="lines+markers",
            marker=dict(size=9, color="#f59e0b"),
            line=dict(width=3.5, color="#f59e0b"),
            yaxis="y2",
        ))
        fig_evol.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#cbd5e1", size=15, family="Inter, Segoe UI, sans-serif"),
            margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=14)),
            yaxis=dict(title="Inversión ($)", showgrid=True, gridcolor="rgba(255,255,255,0.06)", tickfont=dict(size=13)),
            yaxis2=dict(title="Conversaciones", overlaying="y", side="right", showgrid=False, tickfont=dict(size=13)),
            height=360,
        )
        st.plotly_chart(fig_evol, use_container_width=True)

    with col_prod:
        st.markdown("#### Rendimiento por Línea de Negocio")
        st.dataframe(
            comm.df_product_summary.style.format({
                "Inversion_Total": "${:,.0f}",
                "CPL_Promedio": "${:,.0f}",
                "CPM_Promedio": "${:,.0f}",
                "Conversaciones_Total": "{:,}",
                "Alcance_Total": "{:,}",
            }),
            use_container_width=True,
            height=360,
            hide_index=True,
        )
