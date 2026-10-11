from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Mapping

import pandas as pd
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from finance_app.commercial_analytics import CommercialAnalyticsResult
from finance_app.lead_intelligence import compute_lead_kpis, compute_product_performance


import datetime


MONTHS = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


@dataclass(frozen=True)
class MonthlyReport:
    month: str
    executive_summary: pd.DataFrame
    leads: pd.DataFrame
    investment: pd.DataFrame
    opportunities: pd.DataFrame
    products: pd.DataFrame
    insights: tuple[str, ...]


def available_months(
    commercial: CommercialAnalyticsResult | None = None,
    leads_by_sheet: Mapping[str, pd.DataFrame] | None = None,
) -> list[str]:
    present = set()
    if commercial is not None:
        if not commercial.df_monthly_summary.empty and "Mes" in commercial.df_monthly_summary.columns:
            present.update(commercial.df_monthly_summary["Mes"].dropna().astype(str))
        if not commercial.df_opportunities.empty and "Mes" in commercial.df_opportunities.columns:
            present.update(commercial.df_opportunities["Mes"].dropna().astype(str))
        if not commercial.df_spend.empty and "Mes" in commercial.df_spend.columns:
            present.update(commercial.df_spend["Mes"].dropna().astype(str))

    if leads_by_sheet:
        master = leads_by_sheet.get("Leeds", pd.DataFrame())
        date_cols = [c for c in master.columns if "FECHA" in str(c).upper()]
        for c in date_cols:
            d = pd.to_datetime(master[c], errors="coerce").dropna()
            for m_num in d.dt.month.unique():
                if 1 <= m_num <= 12:
                    present.add(MONTHS[m_num - 1])

    if present:
        return [month for month in MONTHS if month in present]
    
    # Por defecto ofrecer hasta el mes en curso (ej: Septiembre)
    curr_m = datetime.datetime.now().month
    return MONTHS[:max(curr_m, 9)]


def build_monthly_report(
    month: str,
    leads_by_sheet: Mapping[str, pd.DataFrame],
    commercial: CommercialAnalyticsResult | None = None,
) -> MonthlyReport:
    leads = leads_by_sheet.get("Leeds", pd.DataFrame()).copy()
    month_number = MONTHS.index(month) + 1 if month in MONTHS else 1

    date_cols = [c for c in leads.columns if "FECHA" in str(c).upper()]
    mask = pd.Series(False, index=leads.index)
    for c in date_cols:
        d = pd.to_datetime(leads[c], errors="coerce")
        mask = mask | d.dt.month.eq(month_number)

    dated = leads[mask]
    leads_month = dated.copy() if date_cols else leads.copy()

    if commercial is not None:
        investment = commercial.df_spend.loc[commercial.df_spend["Mes"].eq(month)].copy() if not commercial.df_spend.empty else pd.DataFrame()
        opportunities = commercial.df_opportunities.loc[commercial.df_opportunities["Mes"].eq(month)].copy() if not commercial.df_opportunities.empty else pd.DataFrame()
    else:
        investment = pd.DataFrame()
        opportunities = pd.DataFrame()
    kpis = compute_lead_kpis(leads_month)
    total_investment = float(investment["Inversion_ARS"].sum()) if not investment.empty else 0.0
    conversations = int(investment["Conversaciones"].sum()) if not investment.empty else 0
    reach = int(investment["Alcance"].sum()) if not investment.empty else 0
    quoted = float(opportunities["Monto_Cotizado"].sum()) if not opportunities.empty else 0.0
    cpl = total_investment / conversations if conversations else 0.0

    summary = pd.DataFrame(
        [
            ("Leads analizados", kpis.total_leads, "registros"),
            ("Leads convertidos", kpis.convertidos, "registros"),
            ("Tasa de conversión", kpis.tasa_conversion_pct, "%"),
            ("Inversión publicitaria", total_investment, "ARS"),
            ("Alcance", reach, "personas"),
            ("Conversaciones", conversations, "conversaciones"),
            ("Costo por conversación", cpl, "ARS"),
            ("Oportunidades comerciales", len(opportunities), "registros"),
            ("Monto cotizado", quoted, "ARS"),
        ],
        columns=["Indicador", "Valor", "Unidad"],
    )

    products = compute_product_performance(leads_month)
    if commercial is not None and not commercial.df_social.empty:
        social = commercial.df_social.loc[commercial.df_social['Mes'].eq(month)]
        extra = []
        for _, row in social.iterrows():
            for column, value in row.items():
                if column not in ('Año', 'Mes') and pd.notna(value):
                    extra.append((f'Instagram · {column}', value, '%' if '%' in column else 'registros'))
        if extra:
            summary = pd.concat([summary, pd.DataFrame(extra, columns=summary.columns)], ignore_index=True)
    best_product = "Sin datos"
    if not investment.empty:
        ranked = investment.sort_values("Conversaciones", ascending=False)
        best_product = str(ranked.iloc[0]["Producto"])
    insights = (
        f"La inversión del período fue de ARS {total_investment:,.0f} y generó {conversations:,} conversaciones.",
        f"El costo promedio por conversación fue de ARS {cpl:,.0f}.",
        f"{best_product} lideró el volumen de conversaciones de pauta en {month}.",
        f"Se registraron {len(opportunities)} oportunidades por un monto cotizado de ARS {quoted:,.0f}.",
    )
    if commercial is not None and not commercial.df_report_notes.empty:
        notes = commercial.df_report_notes
        insights += tuple(notes.loc[notes['Mes'].isin(['General', month]), 'Observación'].dropna().astype(str))
    return MonthlyReport(month, summary, leads_month, investment, opportunities, products, insights)


def report_to_excel(report: MonthlyReport) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        report.executive_summary.to_excel(writer, sheet_name="Resumen ejecutivo", index=False, startrow=4)
        report.investment.to_excel(writer, sheet_name="Pauta por producto", index=False)
        report.opportunities.to_excel(writer, sheet_name="Oportunidades", index=False)
        report.products.to_excel(writer, sheet_name="Rendimiento CRM", index=False)
        safe_leads = report.leads.drop(columns=["Intent_Tags"], errors="ignore")
        safe_leads.to_excel(writer, sheet_name="Detalle de leads", index=False)

        wb = writer.book
        ws = wb["Resumen ejecutivo"]
        ws["A1"] = "INFORME EJECUTIVO MENSUAL"
        ws["A2"] = report.month.upper()
        ws["A3"] = "Fuentes exclusivas: Leeds orden.xlsx + Comercial.xlsx"
        ws["A1"].font = Font(size=20, bold=True, color="FFFFFF")
        ws["A2"].font = Font(size=14, bold=True, color="D8B4FE")
        ws["A3"].font = Font(size=10, color="CBD5E1")
        for cell in ws[1]:
            cell.fill = PatternFill("solid", fgColor="172033")
        ws.merge_cells("A1:C1")
        ws.merge_cells("A2:C2")
        ws.merge_cells("A3:C3")
        start = len(report.executive_summary) + 7
        ws.cell(start, 1, "Hallazgos principales").font = Font(bold=True, color="FFFFFF")
        ws.cell(start, 1).fill = PatternFill("solid", fgColor="6D28D9")
        for offset, insight in enumerate(report.insights, 1):
            ws.cell(start + offset, 1, f"• {insight}")
            ws.merge_cells(start_row=start + offset, start_column=1, end_row=start + offset, end_column=3)

        for sheet in wb.worksheets:
            sheet.freeze_panes = "A2" if sheet.title != "Resumen ejecutivo" else "A6"
            sheet.auto_filter.ref = sheet.dimensions
            for cell in next(sheet.iter_rows(min_row=1 if sheet.title != "Resumen ejecutivo" else 5, max_row=1 if sheet.title != "Resumen ejecutivo" else 5)):
                cell.fill = PatternFill("solid", fgColor="26334D")
                cell.font = Font(bold=True, color="FFFFFF")
                cell.alignment = Alignment(horizontal="center")
            for col in range(1, min(sheet.max_column, 20) + 1):
                values = [str(sheet.cell(row, col).value or "") for row in range(1, min(sheet.max_row, 100) + 1)]
                sheet.column_dimensions[get_column_letter(col)].width = min(max(max(map(len, values)) + 2, 12), 42)

        if not report.investment.empty:
            chart_ws = wb["Pauta por producto"]
            bar = BarChart()
            bar.title = f"Inversión por producto — {report.month}"
            data_col = list(report.investment.columns).index("Inversion_ARS") + 1
            cat_col = list(report.investment.columns).index("Producto") + 1
            bar.add_data(Reference(chart_ws, min_col=data_col, min_row=1, max_row=chart_ws.max_row), titles_from_data=True)
            bar.set_categories(Reference(chart_ws, min_col=cat_col, min_row=2, max_row=chart_ws.max_row))
            bar.height, bar.width = 7, 13
            chart_ws.add_chart(bar, "J2")

    return output.getvalue()
