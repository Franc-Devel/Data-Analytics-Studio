"""
FAUVOR Analytics - Vista de Informes Mensuales y Descargas Ejecutivas (Streamlit)
"""

import datetime
import streamlit as st
import pandas as pd
from finance_app.monthly_reports import available_months, build_monthly_report, report_to_excel
from finance_app.pdf_reports import generate_executive_pdf_report, generate_monthly_pdf_report


def render_reports_view(sheets: dict, comm, current_user: dict):
    """Renderiza el generador y visor de informes ejecutivos mensuales y anuales."""
    st.markdown("## Centro de Informes Ejecutivos & Reportes")
    st.caption("Generación de documentos PDF de alta gama y exportación de balances mensuales en Excel.")
    if comm is not None and not comm.df_social.empty:
        with st.expander("Métricas de Instagram · reportes incorporados", expanded=True):
            st.dataframe(comm.df_social, use_container_width=True, hide_index=True)
            st.caption("Las celdas vacías corresponden a datos no informados o inconsistentes en la fuente.")
    if comm is not None and not comm.df_report_notes.empty:
        with st.expander("Observaciones y datos pendientes de conciliación"):
            st.dataframe(comm.df_report_notes, use_container_width=True, hide_index=True)

    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        st.markdown("""
        <div style="background: rgba(30, 41, 59, 0.7); border-radius: 12px; padding: 20px; border-left: 5px solid #895522; min-height: 140px; display: flex; flex-direction: column; justify-content: space-between;">
            <h4 style="color: #2B211A; margin-bottom: 8px; font-size: 22px;">Informe Ejecutivo Completo (PDF)</h4>
            <p style="color: #2B211A; font-size: 16.5px; line-height: 1.55;">Documento integral con portada corporativa, tarjetas de KPIs, gráficos de alta resolución, embudo de conversión y análisis territorial.</p>
        </div>
        """, unsafe_allow_html=True)

        pdf_bytes_exec = generate_executive_pdf_report(sheets, comm)
        today_str = datetime.datetime.now().strftime("%Y%m%d")
        st.download_button(
            label="Descargar Informe Ejecutivo Completo (.pdf)",
            data=pdf_bytes_exec,
            file_name=f"Informe_Ejecutivo_Nexo_Analytics_{today_str}.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
        )

    with col_opt2:
        st.markdown("""
        <div style="background: rgba(30, 41, 59, 0.7); border-radius: 12px; padding: 20px; border-left: 5px solid #47664F; min-height: 140px; display: flex; flex-direction: column; justify-content: space-between;">
            <h4 style="color: #2B211A; margin-bottom: 8px; font-size: 22px;">Informes Mensuales Específicos</h4>
            <p style="color: #2B211A; font-size: 16.5px; line-height: 1.55;">Seleccione un mes para auditar la inversión, alcance, CPL y prospectos generados en ese período.</p>
        </div>
        """, unsafe_allow_html=True)

        months = available_months(comm, sheets)
        selected_month = st.selectbox("Seleccionar Mes de Análisis", months, index=len(months) - 1 if months else 0)

        report_data = None
        if selected_month:
            report_data = build_monthly_report(selected_month, sheets, comm)
            today_str = datetime.datetime.now().strftime("%Y%m%d")

            if report_data:
                c_btn1, c_btn2 = st.columns(2)
                with c_btn1:
                    pdf_m = generate_monthly_pdf_report(selected_month, sheets, comm)
                    st.download_button(
                        label=f"Descargar {selected_month} (PDF)",
                        data=pdf_m,
                        file_name=f"Reporte_Mensual_{selected_month}_{today_str}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
                with c_btn2:
                    excel_m = report_to_excel(report_data)
                    st.download_button(
                        label=f"Descargar {selected_month} (Excel)",
                        data=excel_m,
                        file_name=f"Reporte_Mensual_{selected_month}_{today_str}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )

    if selected_month and report_data:
        st.divider()
        st.markdown(f"### Hallazgos Principales — {selected_month.upper()}")
        for ins in report_data.insights:
            st.markdown(f"- {ins}")

        st.markdown("#### Resumen Ejecutivo del Mes")
        st.dataframe(report_data.executive_summary, use_container_width=True, hide_index=True)

    # -------------------------------------------------------------
    # DOCUMENTACIÓN TÉCNICA E INFORME DE OPTIMIZACIÓN IA LOCAL
    # -------------------------------------------------------------
    st.divider()
    with st.expander("Documentación Técnica · Arquitectura IA & CRM Cognitivo", expanded=False):
        st.markdown("""
        **Informe Técnico de Infraestructura & Patrón Lightfield CRM**
        Diagnóstico formal de arquitectura de inferencia, cuantización Q4_K_M de Qwen 2.5 7B,
        aislamiento de tensores y arquitectura autónoma con validación humana en 1 clic.
        """)
        report_file_path = "docs/INFORME_OPTIMIZACION_IA_LOCAL.md"
        try:
            with open(report_file_path, "r", encoding="utf-8") as f:
                report_content = f.read()

            st.download_button(
                label="Descargar Informe Técnico de Optimización (.md)",
                data=report_content,
                file_name="INFORME_OPTIMIZACION_IA_LOCAL.md",
                mime="text/markdown",
                use_container_width=True,
            )
        except Exception:
            st.caption("El documento no se encuentra disponible en docs/INFORME_OPTIMIZACION_IA_LOCAL.md")

