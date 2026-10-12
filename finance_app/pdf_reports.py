from __future__ import annotations

import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from finance_app.commercial_analytics import CommercialAnalyticsResult
from finance_app.lead_intelligence import (
    compute_lead_kpis,
    compute_product_performance,
    compute_province_performance,
    compute_regional_performance,
)
from finance_app.monthly_reports import build_monthly_report, MonthlyReport


# =========================================================================
# ESTILOS Y COLORES CORPORATIVOS
# =========================================================================
PRIMARY_DARK = colors.HexColor("#0F172A")      # Slate 900
PRIMARY_NAVY = colors.HexColor("#1E293B")      # Slate 800
ACCENT_PURPLE = colors.HexColor("#6366F1")     # Indigo 500
ACCENT_BLUE = colors.HexColor("#0284C7")       # Sky 600
ACCENT_EMERALD = colors.HexColor("#059669")    # Emerald 600
TEXT_MAIN = colors.HexColor("#1E293B")         # Dark text
TEXT_MUTED = colors.HexColor("#64748B")        # Muted slate text
BG_LIGHT = colors.HexColor("#F8FAFC")          # Slate 50
BG_CARD = colors.HexColor("#F1F5F9")           # Slate 100
BORDER_COLOR = colors.HexColor("#CBD5E1")      # Slate 300
BORDER_LIGHT = colors.HexColor("#E2E8F0")      # Slate 200
WHITE = colors.HexColor("#FFFFFF")


class NumberedCanvas(canvas.Canvas):
    """Canvas de dos pasadas para numerar páginas exactamente (Página X de Y) y cabecera/pie continuo."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(TEXT_MUTED)

        # Header (en páginas > 1)
        if self._pageNumber > 1:
            self.setStrokeColor(BORDER_LIGHT)
            self.setLineWidth(0.6)
            self.line(36, 756, 576, 756)
            self.drawString(36, 762, "NEXO ANALYTICS · INFORME EJECUTIVO DE INTELIGENCIA COMERCIAL")
            self.drawRightString(576, 762, datetime.datetime.now().strftime("%d/%m/%Y"))

        # Footer (en todas las páginas)
        self.setStrokeColor(BORDER_LIGHT)
        self.setLineWidth(0.6)
        self.line(36, 36, 576, 36)
        self.drawString(36, 25, "Documento Confidencial · Generado automáticamente por Suite de Consultoría")
        page_str = f"Página {self._pageNumber} de {page_count}"
        self.drawRightString(576, 25, page_str)
        self.restoreState()


def _get_report_styles():
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=WHITE,
        alignment=TA_LEFT,
    )
    subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=12.5,
        textColor=colors.HexColor("#E0E7FF"),
        alignment=TA_LEFT,
    )
    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=PRIMARY_NAVY,
        spaceBefore=8,
        spaceAfter=3,
    )
    h2_style = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12.5,
        textColor=ACCENT_PURPLE,
        spaceBefore=5,
        spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11.5,
        textColor=TEXT_MAIN,
    )
    body_bold = ParagraphStyle(
        "Body_Bold",
        parent=body_style,
        fontName="Helvetica-Bold",
    )
    kpi_num_style = ParagraphStyle(
        "KPINumber",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=16,
        textColor=PRIMARY_DARK,
        alignment=TA_CENTER,
    )
    kpi_lbl_style = ParagraphStyle(
        "KPILabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.2,
        leading=8.5,
        textColor=TEXT_MUTED,
        alignment=TA_CENTER,
    )
    kpi_sub_style = ParagraphStyle(
        "KPISubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.8,
        leading=8,
        textColor=ACCENT_EMERALD,
        alignment=TA_CENTER,
    )
    th_style = ParagraphStyle(
        "TableHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.8,
        leading=9.5,
        textColor=WHITE,
        alignment=TA_CENTER,
    )
    tc_style = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=9.2,
        textColor=TEXT_MAIN,
        alignment=TA_LEFT,
    )
    tc_center = ParagraphStyle("TCCenter", parent=tc_style, alignment=TA_CENTER)
    tc_right = ParagraphStyle("TCRight", parent=tc_style, alignment=TA_RIGHT)
    tc_bold = ParagraphStyle("TCBold", parent=tc_style, fontName="Helvetica-Bold")
    tc_bold_right = ParagraphStyle("TCBoldRight", parent=tc_right, fontName="Helvetica-Bold")

    insight_style = ParagraphStyle(
        "InsightText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.2,
        leading=11,
        textColor=PRIMARY_NAVY,
    )

    return {
        "title": title_style,
        "subtitle": subtitle_style,
        "h1": h1_style,
        "h2": h2_style,
        "body": body_style,
        "body_bold": body_bold,
        "kpi_num": kpi_num_style,
        "kpi_lbl": kpi_lbl_style,
        "kpi_sub": kpi_sub_style,
        "th": th_style,
        "tc": tc_style,
        "tc_center": tc_center,
        "tc_right": tc_right,
        "tc_bold": tc_bold,
        "tc_bold_right": tc_bold_right,
        "insight": insight_style,
    }


# =========================================================================
# GENERACIÓN DE GRÁFICOS MATPLOTLIB EN MEMORIA
# =========================================================================
def _chart_commercial_monthly(commercial: CommercialAnalyticsResult) -> Image | None:
    if commercial is None or commercial.df_monthly_summary.empty:
        return None
    df = commercial.df_monthly_summary
    fig, ax1 = plt.subplots(figsize=(6.8, 2.2), dpi=200)
    fig.patch.set_facecolor("#FFFFFF")
    ax1.set_facecolor("#F8FAFC")

    x = np.arange(len(df))
    width = 0.42

    bars = ax1.bar(x - width/2, df["Inversion_Total"] / 1000, width, label="Inversión ($k ARS)", color="#6366F1", edgecolor="none", zorder=3)
    ax1.set_ylabel("Inversión ($k ARS)", color="#4338CA", fontsize=7.5, fontweight="bold")
    ax1.tick_params(axis="y", labelcolor="#4338CA", labelsize=7)
    ax1.set_xticks(x)
    ax1.set_xticklabels(df["Mes"], fontsize=7.2)
    ax1.grid(axis="y", color="#E2E8F0", linestyle="--", linewidth=0.5, zorder=0)

    ax2 = ax1.twinx()
    conv_line = ax2.plot(x + width/2, df["Conversaciones_Total"], color="#059669", marker="o", linewidth=1.8, markersize=3.8, label="Conversaciones", zorder=4)
    ax2.set_ylabel("Conversaciones", color="#047857", fontsize=7.5, fontweight="bold")
    ax2.tick_params(axis="y", labelcolor="#047857", labelsize=7)

    ax1.set_title("Evolución Mensual: Inversión Publicitaria vs. Conversaciones Generadas", fontsize=8.5, fontweight="bold", pad=6, color="#1E293B")
    for spine in ["top", "right", "left", "bottom"]:
        ax1.spines[spine].set_color("#CBD5E1")
        ax2.spines[spine].set_color("#CBD5E1")

    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=200)
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=540, height=170)


def _chart_lead_funnel(leads_df: pd.DataFrame) -> Image | None:
    if leads_df is None or leads_df.empty:
        return None
    kpis = compute_lead_kpis(leads_df)
    stages = ["Total Leads", "Calificados", "Interés Alto/Medio", "Derivados / Ganados"]
    values = [
        kpis.total_leads,
        int(leads_df["Calificado"].astype(str).str.contains("True|1|si", case=False).sum()) if "Calificado" in leads_df.columns else kpis.total_leads,
        kpis.leads_hot + kpis.leads_warm,
        kpis.convertidos,
    ]
    colors_list = ["#3B82F6", "#6366F1", "#8B5CF6", "#47664F"]

    fig, ax = plt.subplots(figsize=(6.8, 1.7), dpi=200)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8FAFC")

    y_pos = np.arange(len(stages))[::-1]
    bars = ax.barh(y_pos, values, color=colors_list, height=0.52, edgecolor="none", zorder=3)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(stages, fontsize=7.2, fontweight="bold", color="#1E293B")
    ax.tick_params(axis="x", labelsize=7, labelcolor="#64748B")
    ax.grid(axis="x", color="#E2E8F0", linestyle="--", linewidth=0.5, zorder=0)
    ax.set_title("Embudo de Conversión Comercial (Lead Funnel)", fontsize=8.5, fontweight="bold", pad=5, color="#1E293B")

    for bar, val in zip(bars, values):
        pct = (val / kpis.total_leads * 100) if kpis.total_leads else 0
        ax.text(val + max(values) * 0.02, bar.get_y() + bar.get_height() / 2, f"{val:,} ({pct:.1f}%)", va="center", ha="left", fontsize=7, fontweight="bold", color="#1E293B")

    ax.set_xlim(0, max(values) * 1.25)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color("#CBD5E1")

    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=200)
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=540, height=135)


def _chart_province_ranking(leads_df: pd.DataFrame) -> Image | None:
    if leads_df is None or leads_df.empty:
        return None
    prov_df = compute_province_performance(leads_df).head(8)
    if prov_df.empty:
        return None

    fig, ax = plt.subplots(figsize=(6.8, 1.8), dpi=200)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#F8FAFC")

    y_pos = np.arange(len(prov_df))[::-1]
    provinces = prov_df["Provincia"].tolist()
    totals = prov_df["Total_Leads"].tolist()
    converted = prov_df["Convertidos"].tolist()

    ax.barh(y_pos, totals, color="#94A3B8", height=0.52, label="Total Leads", zorder=3)
    ax.barh(y_pos, converted, color="#6366F1", height=0.52, label="Derivados/Ganados", zorder=4)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(provinces, fontsize=7.2, color="#1E293B", fontweight="bold")
    ax.tick_params(axis="x", labelsize=7, labelcolor="#64748B")
    ax.grid(axis="x", color="#E2E8F0", linestyle="--", linewidth=0.5, zorder=0)
    ax.set_title("Top 8 Provincias por Volumen de Leads y Conversión", fontsize=8.5, fontweight="bold", pad=5, color="#1E293B")
    ax.legend(fontsize=6.8, loc="lower right", framealpha=0.9)

    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color("#CBD5E1")

    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=200)
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=540, height=145)


# =========================================================================
# GENERACIÓN DEL INFORME EJECUTIVO COMPLETO EN PDF
# =========================================================================
def generate_executive_pdf_report(
    leads_by_sheet: Mapping[str, pd.DataFrame],
    commercial: CommercialAnalyticsResult | None,
    output_path_or_buffer: str | Path | BytesIO | None = None,
) -> bytes:
    """
    Genera un informe ejecutivo integral y completo en PDF con diseño editorial de consultoría,
    incluyendo portada, KPIs, análisis de pauta, CRM, rankings provinciales, closers y gráficos.
    """
    buffer = BytesIO() if output_path_or_buffer is None or isinstance(output_path_or_buffer, BytesIO) else output_path_or_buffer
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=38,
    )

    st = _get_report_styles()
    story = []

    master_leads = leads_by_sheet.get("Leeds", pd.DataFrame()) if leads_by_sheet else pd.DataFrame()
    kpis_leads = compute_lead_kpis(master_leads) if not master_leads.empty else None

    # -------------------------------------------------------------
    # 1. ENCABEZADO / BANNER PRINCIPAL
    # -------------------------------------------------------------
    date_str = datetime.datetime.now().strftime("%d de %B de %Y").capitalize()
    banner_content = [
        [
            Paragraph("<b>NEXO ANALYTICS · CONSULTORÍA ESTRATÉGICA</b>", st["subtitle"]),
            Paragraph(f"<b>Fecha:</b> {date_str}", ParagraphStyle("HDate", parent=st["subtitle"], alignment=TA_RIGHT)),
        ],
        [
            Paragraph("INFORME EJECUTIVO DE INTELIGENCIA COMERCIAL & CRM", st["title"]),
            Paragraph("<b>Estado:</b> Auditoría Completa", ParagraphStyle("HStatus", parent=st["subtitle"], alignment=TA_RIGHT)),
        ],
        [
            Paragraph("Consolidación analítica basada en Leeds orden.xlsx y Comercial.xlsx", st["subtitle"]),
            Paragraph(f"<b>Total Registros:</b> {len(master_leads):,} leads", ParagraphStyle("HRec", parent=st["subtitle"], alignment=TA_RIGHT)),
        ],
    ]
    banner_table = Table(banner_content, colWidths=[380, 160])
    banner_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PRIMARY_NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(banner_table)
    story.append(Spacer(1, 8))

    # -------------------------------------------------------------
    # 2. TARJETAS DE KPIS PRINCIPALES (6 Tarjetas en grilla 2x3)
    # -------------------------------------------------------------
    tot_leads = f"{kpis_leads.total_leads:,}" if kpis_leads else "0"
    conv_str = f"{kpis_leads.convertidos:,} ({kpis_leads.tasa_conversion_pct:.1f}%)" if kpis_leads else "0 (0.0%)"
    inv_total = f"$ {commercial.kpis.total_inversion_ars:,.0f}" if commercial else "$ 0"
    cpl_prom = f"$ {commercial.kpis.cpl_promedio_ars:,.0f}" if commercial else "$ 0"
    pipe_val = f"$ {commercial.kpis.presupuesto_cotizado_total:,.0f}" if commercial else "$ 0"
    opps_val = f"{commercial.kpis.total_oportunidades} cotizaciones" if commercial else "0"
    hot_warm = f"{(kpis_leads.leads_hot + kpis_leads.leads_warm):,}" if kpis_leads else "0"

    kpi_cards_data = [
        [
            Paragraph("TOTAL LEADS ANALIZADOS", st["kpi_lbl"]),
            Paragraph("LEADS CONVERTIDOS / GANADOS", st["kpi_lbl"]),
            Paragraph("INVERSIÓN PUBLICITARIA", st["kpi_lbl"]),
        ],
        [
            Paragraph(tot_leads, st["kpi_num"]),
            Paragraph(conv_str, st["kpi_num"]),
            Paragraph(inv_total, st["kpi_num"]),
        ],
        [
            Paragraph("Base maestra Leeds", st["kpi_sub"]),
            Paragraph("Derivados a closers", st["kpi_sub"]),
            Paragraph("Acumulado 7 meses", st["kpi_sub"]),
        ],
        [
            Paragraph("COSTO PROMEDIO / CONVERSACIÓN", st["kpi_lbl"]),
            Paragraph("PIPELINE TOTAL COTIZADO", st["kpi_lbl"]),
            Paragraph("LEADS CALIFICADOS HOT / WARM", st["kpi_lbl"]),
        ],
        [
            Paragraph(cpl_prom, st["kpi_num"]),
            Paragraph(pipe_val, st["kpi_num"]),
            Paragraph(hot_warm, st["kpi_num"]),
        ],
        [
            Paragraph(f"{commercial.kpis.total_conversaciones if commercial else 0:,} conversaciones", st["kpi_sub"]),
            Paragraph(opps_val, st["kpi_sub"]),
            Paragraph(f"Score >= 50 puntos", st["kpi_sub"]),
        ],
    ]
    kpi_table = Table(kpi_cards_data, colWidths=[176, 176, 176])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 2), BG_CARD),
        ("BACKGROUND", (1, 0), (1, 2), BG_CARD),
        ("BACKGROUND", (2, 0), (2, 2), BG_CARD),
        ("BACKGROUND", (0, 3), (0, 5), BG_CARD),
        ("BACKGROUND", (1, 3), (1, 5), BG_CARD),
        ("BACKGROUND", (2, 3), (2, 5), BG_CARD),
        ("BOX", (0, 0), (0, 2), 0.8, BORDER_COLOR),
        ("BOX", (1, 0), (1, 2), 0.8, BORDER_COLOR),
        ("BOX", (2, 0), (2, 2), 0.8, BORDER_COLOR),
        ("BOX", (0, 3), (0, 5), 0.8, BORDER_COLOR),
        ("BOX", (1, 3), (1, 5), 0.8, BORDER_COLOR),
        ("BOX", (2, 3), (2, 5), 0.8, BORDER_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 8))

    # -------------------------------------------------------------
    # 3. HALLAZGOS Y CONCLUSIONES ESTRATÉGICAS (Callout Box)
    # -------------------------------------------------------------
    best_prod = "Sin datos"
    if commercial and not commercial.df_product_summary.empty:
        best_prod = str(commercial.df_product_summary.iloc[0]["Producto"])

    top_prov = "Buenos Aires"
    if not master_leads.empty:
        prov_top_df = compute_province_performance(master_leads)
        if not prov_top_df.empty:
            top_prov = str(prov_top_df.iloc[0]["Provincia"])

    insights_rows = [
        [
            Paragraph("<b>📌 SÍNTESIS EJECUTIVA & RECOMENDACIONES CLAVE</b>", ParagraphStyle("IBold", parent=st["insight"], fontName="Helvetica-Bold", textColor=PRIMARY_DARK)),
        ],
        [
            Paragraph(f"• <b>Eficiencia de Captación:</b> Se analizaron <b>{tot_leads}</b> leads con una tasa de conversión a derivación del <b>{kpis_leads.tasa_conversion_pct:.1f}%</b> ({kpis_leads.convertidos} oportunidades ganadas/derivadas).", st["insight"]),
        ],
        [
            Paragraph(f"• <b>Inversión y Retorno:</b> La pauta publicitaria acumuló <b>{inv_total} ARS</b>, generando <b>{commercial.kpis.total_conversaciones if commercial else 0:,}</b> conversaciones comerciales con un CPL promedio de <b>{cpl_prom} ARS</b>.", st["insight"]),
        ],
        [
            Paragraph(f"• <b>Línea Líder & Geomarketing:</b> La línea con mayor inversión y demanda fue <b>{best_prod}</b>. A nivel territorial, <b>{top_prov}</b> concentró la mayor cantidad de consultas y volumen de cierre.", st["insight"]),
        ],
        [
            Paragraph(f"• <b>Pipeline Activo:</b> Se registraron <b>{commercial.kpis.total_oportunidades if commercial else 0}</b> cotizaciones por un monto de <b>{pipe_val} ARS</b> asignadas a closers especializados.", st["insight"]),
        ],
    ]
    insights_table = Table(insights_rows, colWidths=[540])
    insights_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG_LIGHT),
        ("BOX", (0, 0), (-1, -1), 1, ACCENT_PURPLE),
        ("LINEBELOW", (0, 0), (0, 0), 1, BORDER_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(insights_table)
    story.append(Spacer(1, 8))

    # -------------------------------------------------------------
    # 4. RENDIMIENTO POR LÍNEA DE PRODUCTO Y EMBUDO CRM
    # -------------------------------------------------------------
    story.append(Paragraph("1. Rendimiento y Conversión por Línea de Producto (CRM)", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceBefore=2, spaceAfter=5))

    prod_perf = compute_product_performance(master_leads) if not master_leads.empty else pd.DataFrame()
    if not prod_perf.empty:
        prod_table_data = [[
            Paragraph("Línea de Producto", st["th"]),
            Paragraph("Total Leads", st["th"]),
            Paragraph("Convertidos", st["th"]),
            Paragraph("Tasa Conv. %", st["th"]),
            Paragraph("Remarketing", st["th"]),
            Paragraph("Prom. Toques", st["th"]),
            Paragraph("Score Prom.", st["th"]),
        ]]
        for _, r in prod_perf.iterrows():
            prod_table_data.append([
                Paragraph(f"<b>{r['Linea_Producto']}</b>", st["tc_bold"]),
                Paragraph(f"{r['Total_Leads']:,}", st["tc_center"]),
                Paragraph(f"{r['Convertidos']:,}", st["tc_center"]),
                Paragraph(f"{r['Tasa_Conversion_Pct']:.1f}%", st["tc_bold_right"]),
                Paragraph(f"{r.get('Remarketing', 0):,}", st["tc_center"]),
                Paragraph(f"{r['Promedio_Contactos']:.1f}", st["tc_center"]),
                Paragraph(f"{r['Score_Promedio']:.1f}", st["tc_center"]),
            ])
        pt = Table(prod_table_data, colWidths=[120, 68, 68, 74, 70, 70, 70])
        pt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BG_LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(pt)
        story.append(Spacer(1, 6))

    # Gráfico del embudo
    funnel_img = _chart_lead_funnel(master_leads)
    if funnel_img:
        story.append(funnel_img)
        story.append(Spacer(1, 6))

    # -------------------------------------------------------------
    # 5. PAUTA PUBLICITARIA Y GASTOS COMERCIALES (Página 2)
    # -------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("2. Auditoría de Pauta Publicitaria y Gastos Comerciales", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceBefore=2, spaceAfter=5))

    if commercial and not commercial.df_monthly_summary.empty:
        # Tabla resumen mensual
        month_data = [[
            Paragraph("Mes", st["th"]),
            Paragraph("Inversión Total ($ ARS)", st["th"]),
            Paragraph("Alcance Personas", st["th"]),
            Paragraph("Conversaciones", st["th"]),
            Paragraph("CPL Promedio ($)", st["th"]),
            Paragraph("CPM Promedio ($)", st["th"]),
        ]]
        for _, r in commercial.df_monthly_summary.iterrows():
            month_data.append([
                Paragraph(f"<b>{r['Mes']}</b>", st["tc_bold"]),
                Paragraph(f"$ {r['Inversion_Total']:,.2f}", st["tc_right"]),
                Paragraph(f"{int(r['Alcance_Total']):,}", st["tc_center"]),
                Paragraph(f"{int(r['Conversaciones_Total']):,}", st["tc_center"]),
                Paragraph(f"$ {r['CPL_Promedio']:,.2f}", st["tc_right"]),
                Paragraph(f"$ {r['CPM_Promedio']:,.2f}", st["tc_right"]),
            ])
        # Fila Total
        month_data.append([
            Paragraph("<b>TOTAL CONSOLIDADO</b>", st["tc_bold"]),
            Paragraph(f"<b>$ {commercial.kpis.total_inversion_ars:,.2f}</b>", st["tc_bold_right"]),
            Paragraph(f"<b>{commercial.kpis.total_alcance:,}</b>", ParagraphStyle("TB", parent=st["tc_center"], fontName="Helvetica-Bold")),
            Paragraph(f"<b>{commercial.kpis.total_conversaciones:,}</b>", ParagraphStyle("TB2", parent=st["tc_center"], fontName="Helvetica-Bold")),
            Paragraph(f"<b>$ {commercial.kpis.cpl_promedio_ars:,.2f}</b>", st["tc_bold_right"]),
            Paragraph(f"<b>$ {commercial.kpis.cpm_promedio_ars:,.2f}</b>", st["tc_bold_right"]),
        ])
        mt = Table(month_data, colWidths=[90, 110, 95, 80, 85, 80])
        mt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [WHITE, BG_LIGHT]),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E2E8F0")),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(mt)
        story.append(Spacer(1, 6))

        # Gráfico evolución mensual
        comm_img = _chart_commercial_monthly(commercial)
        if comm_img:
            story.append(comm_img)
            story.append(Spacer(1, 6))

    # -------------------------------------------------------------
    # 6. GEOMARKETING & RANKING DE PROVINCIAS
    # -------------------------------------------------------------
    story.append(Paragraph("3. Análisis Territorial y Ranking de Provincias (Geomarketing)", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceBefore=2, spaceAfter=5))

    prov_df = compute_province_performance(master_leads).head(10) if not master_leads.empty else pd.DataFrame()
    if not prov_df.empty:
        prov_data = [[
            Paragraph("Rank", st["th"]),
            Paragraph("Provincia", st["th"]),
            Paragraph("Región", st["th"]),
            Paragraph("Total Leads", st["th"]),
            Paragraph("% de Base", st["th"]),
            Paragraph("Convertidos", st["th"]),
            Paragraph("Tasa Conv. %", st["th"]),
            Paragraph("Score", st["th"]),
        ]]
        for _, r in prov_df.iterrows():
            prov_data.append([
                Paragraph(f"#{r['Ranking']}", st["tc_center"]),
                Paragraph(f"<b>{r['Provincia']}</b>", st["tc_bold"]),
                Paragraph(f"{r['Region']}", st["tc_center"]),
                Paragraph(f"{r['Total_Leads']:,}", st["tc_center"]),
                Paragraph(f"{r['Porcentaje_Base_Pct']:.1f}%", st["tc_center"]),
                Paragraph(f"{r['Convertidos']:,}", st["tc_center"]),
                Paragraph(f"{r['Tasa_Conversion_Pct']:.1f}%", st["tc_bold_right"]),
                Paragraph(f"{r['Score_Promedio']:.1f}", st["tc_center"]),
            ])
        pr_t = Table(prov_data, colWidths=[38, 120, 75, 62, 60, 60, 68, 57])
        pr_t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BG_LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 2.8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(pr_t)
        story.append(Spacer(1, 6))

    prov_chart_img = _chart_province_ranking(master_leads)
    if prov_chart_img:
        story.append(prov_chart_img)
        story.append(Spacer(1, 6))

    # -------------------------------------------------------------
    # 7. PIPELINE COMERCIAL, COTIZACIONES Y CLOSERS (Página 3)
    # -------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("4. Pipeline Comercial, Cotizaciones y Rendimiento de Closers", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceBefore=2, spaceAfter=5))

    if commercial and not commercial.df_closers_summary.empty:
        closer_data = [[
            Paragraph("Closer / Responsable Comercial", st["th"]),
            Paragraph("Oportunidades Asignadas", st["th"]),
            Paragraph("Monto Total Cotizado ($ ARS)", st["th"]),
            Paragraph("Ticket Promedio ($ ARS)", st["th"]),
        ]]
        for _, r in commercial.df_closers_summary.iterrows():
            opps_cnt = int(r["Oportunidades"])
            monto_tot = float(r["Monto_Total_Cotizado"])
            t_prom = (monto_tot / opps_cnt) if opps_cnt > 0 else 0.0
            closer_data.append([
                Paragraph(f"<b>{r['Closer_Limpio']}</b>", st["tc_bold"]),
                Paragraph(f"{opps_cnt:,}", st["tc_center"]),
                Paragraph(f"$ {monto_tot:,.2f}", st["tc_bold_right"]),
                Paragraph(f"$ {t_prom:,.2f}", st["tc_right"]),
            ])
        cl_t = Table(closer_data, colWidths=[160, 110, 140, 130])
        cl_t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BG_LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(cl_t)
        story.append(Spacer(1, 8))

    if commercial and not commercial.df_opportunities.empty:
        story.append(Paragraph("Muestra de Oportunidades Principales en Cotización", st["h2"]))
        opps_sample = commercial.df_opportunities.head(8)
        opps_data = [[
            Paragraph("Mes", st["th"]),
            Paragraph("Cliente", st["th"]),
            Paragraph("Producto", st["th"]),
            Paragraph("Monto ($ ARS)", st["th"]),
            Paragraph("Closer", st["th"]),
            Paragraph("Provincia", st["th"]),
            Paragraph("Estado / Prob.", st["th"]),
        ]]
        for _, r in opps_sample.iterrows():
            monto = float(r["Monto_Cotizado"])
            monto_str = f"$ {monto:,.2f}" if monto > 0 else "A presupuestar"
            opps_data.append([
                Paragraph(str(r.get("Mes", "-")), st["tc_center"]),
                Paragraph(f"<b>{str(r.get('Cliente', '-'))[:22]}</b>", st["tc_bold"]),
                Paragraph(str(r.get("Producto", "-"))[:18], st["tc"]),
                Paragraph(monto_str, st["tc_right"]),
                Paragraph(str(r.get("Derivado_A", "-")), st["tc_center"]),
                Paragraph(str(r.get("Provincia", "-")), st["tc_center"]),
                Paragraph(str(r.get("Prob_Cierre", "-")), st["tc_center"]),
            ])
        opp_t = Table(opps_data, colWidths=[55, 115, 95, 95, 65, 60, 55])
        opp_t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BG_LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 2.8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(opp_t)
        story.append(Spacer(1, 8))

    # Construir documento
    doc.build(story, canvasmaker=NumberedCanvas)

    if isinstance(buffer, BytesIO):
        return buffer.getvalue()
    return b""


# =========================================================================
# GENERACIÓN DEL INFORME MENSUAL ESPECÍFICO EN PDF
# =========================================================================
def generate_monthly_pdf_report(
    month: str,
    leads_by_sheet: Mapping[str, pd.DataFrame],
    commercial: CommercialAnalyticsResult,
    output_path_or_buffer: str | Path | BytesIO | None = None,
) -> bytes:
    """
    Genera un informe mensual en PDF para un mes específico (Enero, Febrero, etc.)
    con sus indicadores ejecutivos, desglose de pauta, cotizaciones y hallazgos.
    """
    report = build_monthly_report(month, leads_by_sheet, commercial)
    buffer = BytesIO() if output_path_or_buffer is None or isinstance(output_path_or_buffer, BytesIO) else output_path_or_buffer

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=38,
    )

    st = _get_report_styles()
    story = []

    # Banner mensual
    banner_content = [
        [
            Paragraph(f"<b>NEXO ANALYTICS · INFORME MENSUAL EJECUTIVO</b>", st["subtitle"]),
            Paragraph(f"<b>Período:</b> {month.upper()} 2026", ParagraphStyle("HDateM", parent=st["subtitle"], alignment=TA_RIGHT)),
        ],
        [
            Paragraph(f"REPORTE MENSUAL DE PAUTA Y RENDIMIENTO COMERCIAL: {month.upper()}", st["title"]),
            Paragraph("<b>Base Oficial</b>", ParagraphStyle("HStatM", parent=st["subtitle"], alignment=TA_RIGHT)),
        ],
        [
            Paragraph("Fuentes consolidadas: Leeds orden.xlsx + Comercial.xlsx", st["subtitle"]),
            Paragraph(f"<b>Generado:</b> {datetime.datetime.now().strftime('%d/%m/%Y')}", ParagraphStyle("HRecM", parent=st["subtitle"], alignment=TA_RIGHT)),
        ],
    ]
    banner_table = Table(banner_content, colWidths=[380, 160])
    banner_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PRIMARY_NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(banner_table)
    story.append(Spacer(1, 8))

    # Hallazgos del mes
    insights_rows = [
        [Paragraph(f"<b>📌 HALLAZGOS PRINCIPALES DEL MES DE {month.upper()}</b>", ParagraphStyle("IMTitle", parent=st["insight"], fontName="Helvetica-Bold", textColor=PRIMARY_DARK))],
    ]
    for insight in report.insights:
        insights_rows.append([Paragraph(f"• {insight}", st["insight"])])

    ins_table = Table(insights_rows, colWidths=[540])
    ins_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG_LIGHT),
        ("BOX", (0, 0), (-1, -1), 1, ACCENT_PURPLE),
        ("LINEBELOW", (0, 0), (0, 0), 1, BORDER_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(ins_table)
    story.append(Spacer(1, 8))

    # Resumen de Indicadores
    story.append(Paragraph("1. Tabla de Indicadores Clave del Período", st["h1"]))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceBefore=2, spaceAfter=5))

    sum_data = [[
        Paragraph("Indicador", st["th"]),
        Paragraph("Valor Obtenido", st["th"]),
        Paragraph("Unidad de Medida", st["th"]),
    ]]
    for _, r in report.executive_summary.iterrows():
        val = r["Valor"]
        if isinstance(val, float):
            val_str = f"{val:,.2f}"
        elif isinstance(val, int):
            val_str = f"{val:,}"
        else:
            val_str = str(val)
        sum_data.append([
            Paragraph(f"<b>{r['Indicador']}</b>", st["tc_bold"]),
            Paragraph(val_str, st["tc_bold_right"]),
            Paragraph(str(r["Unidad"]), st["tc_center"]),
        ])
    st_table = Table(sum_data, colWidths=[240, 150, 150])
    st_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BG_LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(st_table)
    story.append(Spacer(1, 8))

    # Desglose de pauta del mes
    if not report.investment.empty:
        story.append(Paragraph("2. Inversión y Eficiencia Publicitaria por Producto", st["h1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceBefore=2, spaceAfter=5))

        inv_data = [[
            Paragraph("Línea de Producto", st["th"]),
            Paragraph("Inversión ($ ARS)", st["th"]),
            Paragraph("Alcance", st["th"]),
            Paragraph("Conversaciones", st["th"]),
            Paragraph("CPL ($ ARS)", st["th"]),
            Paragraph("CPM ($ ARS)", st["th"]),
        ]]
        for _, r in report.investment.iterrows():
            inv_data.append([
                Paragraph(f"<b>{r['Producto']}</b>", st["tc_bold"]),
                Paragraph(f"$ {r['Inversion_ARS']:,.2f}", st["tc_right"]),
                Paragraph(f"{int(r['Alcance']):,}", st["tc_center"]),
                Paragraph(f"{int(r['Conversaciones']):,}", st["tc_center"]),
                Paragraph(f"$ {r['CPL_ARS']:,.2f}", st["tc_right"]),
                Paragraph(f"$ {r['CPM_ARS']:,.2f}", st["tc_right"]),
            ])
        it_table = Table(inv_data, colWidths=[120, 100, 80, 80, 80, 80])
        it_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BG_LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(it_table)
        story.append(Spacer(1, 8))

    # Oportunidades del mes
    if not report.opportunities.empty:
        story.append(Paragraph("3. Oportunidades y Cotizaciones Registradas", st["h1"]))
        story.append(HRFlowable(width="100%", thickness=1, color=BORDER_COLOR, spaceBefore=2, spaceAfter=5))

        opp_data = [[
            Paragraph("Cliente", st["th"]),
            Paragraph("Producto", st["th"]),
            Paragraph("Monto ($ ARS)", st["th"]),
            Paragraph("Probabilidad", st["th"]),
            Paragraph("Closer", st["th"]),
            Paragraph("Provincia", st["th"]),
        ]]
        for _, r in report.opportunities.iterrows():
            monto = float(r["Monto_Cotizado"])
            monto_str = f"$ {monto:,.2f}" if monto > 0 else "A presupuestar"
            opp_data.append([
                Paragraph(f"<b>{str(r.get('Cliente', '-'))[:25]}</b>", st["tc_bold"]),
                Paragraph(str(r.get("Producto", "-"))[:20], st["tc"]),
                Paragraph(monto_str, st["tc_right"]),
                Paragraph(str(r.get("Prob_Cierre", "-")), st["tc_center"]),
                Paragraph(str(r.get("Derivado_A", "-")), st["tc_center"]),
                Paragraph(str(r.get("Provincia", "-")), st["tc_center"]),
            ])
        ot_table = Table(opp_data, colWidths=[140, 100, 95, 75, 70, 60])
        ot_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_NAVY),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BG_LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER_LIGHT),
            ("TOPPADDING", (0, 0), (-1, -1), 2.8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(ot_table)
        story.append(Spacer(1, 8))

    doc.build(story, canvasmaker=NumberedCanvas)

    if isinstance(buffer, BytesIO):
        return buffer.getvalue()
    return b""
